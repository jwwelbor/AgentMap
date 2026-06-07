---
sidebar_position: 2
title: LLM Service
description: Unified LLM interface with optional intelligent routing across providers
keywords: [LLM service, OpenAI, Anthropic, Google, routing, language models]
---

# LLM Service

`LLMService` provides a unified interface for calling language model providers (Anthropic, OpenAI, Google) with optional intelligent routing that selects the best provider and model based on task type, complexity, and cost preferences.

---

## Configuration

`LLMService` is configured entirely through `agentmap_config.yaml`. There are two top-level sections.

### Provider config (`llm:`)

API keys, default model, and temperature per provider:

```yaml
llm:
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-sonnet-4-6"
    temperature: 0.7
    max_tokens: 4096
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o"
    temperature: 0.7
  google:
    api_key: "${GOOGLE_API_KEY}"
    model: "gemini-2.5-flash"
    temperature: 0.5
```

- `max_tokens` — (optional) maximum number of tokens in the LLM response. Omit or set to `null` to use the provider's default. Set to `0` to explicitly mean "no limit". Can be overridden per-call via `call_llm(max_tokens=...)` or via `routing_context`.

### Routing config (`routing:`)

Opt-in intelligent routing. Key sub-sections:

| Sub-section | Purpose |
|---|---|
| `routing_matrix` | Provider × complexity → model mapping (used as fallback when no activity matches) |
| `activities` | Explicit provider/model plans per activity + complexity tier — evaluated **first** |
| `task_types` | Keyword-based complexity detection and provider preferences (used when no activity is set) |
| `complexity_analysis` | Thresholds for auto-detecting complexity from prompt length, keywords, memory size |
| `cost_optimization` | Prefer cost-effective models |
| `fallback` | Default provider/model when routing fails |

See `src/agentmap/templates/config/agentmap_config.yaml.template` (lines 105–365) for the full annotated routing config.

---

## Execution Patterns

`call_llm()` has two mutually exclusive modes:

| Mode | Triggered by | `provider` | `model` |
|---|---|---|---|
| Direct | no `routing_context` | Required — target provider | Optional — overrides config default |
| Routing | `routing_context` present | **Ignored** (warning logged) | **Ignored** (warning logged) |

Use `routing_context['provider_preference']` / `routing_context['fallback_provider']` and `routing_context['model_override']` to control those within the routing path.

### Pattern 1: Direct provider call

Specify the provider directly, optionally overriding model and temperature. `provider` is required in this path.

```python
response = llm_service.call_llm(
    provider="anthropic",
    messages=[{"role": "user", "content": "Explain quantum entanglement"}],
    model="claude-sonnet-4-6",  # optional override
    temperature=0.2,                      # optional override
    max_tokens=2048,                      # optional override
)
```

### Pattern 2: Simple string prompt (`ask()`)

Convenience wrapper for single plain-string prompts — no messages list required:

```python
response = llm_service.ask("Summarize this document: ...")
response = llm_service.ask("...", provider="openai", temperature=0.5)
```

`ask()` constructs `[{"role": "user", "content": prompt}]` and calls `call_llm()`. The default provider is `"anthropic"`.

### Pattern 3: Intelligent routing

Pass a `routing_context` dict to let the routing system select provider and model. When `routing_context` is present, **routing owns all provider and model selection** — the `provider` and `model` parameters are ignored and a warning is logged if you pass them.

```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Write a short story about a robot who learns to paint."}
]

# Route by task type
response = llm_service.call_llm(
    messages=messages,
    routing_context={"task_type": "code_generation"}
)

# Route by activity (takes priority over task_type)
response = llm_service.call_llm(
    messages=messages,
    routing_context={"activity": "code_generation"}
)

# Force a specific model through routing
response = llm_service.call_llm(
    messages=messages,
    routing_context={"task_type": "code_generation", "model_override": "claude-sonnet-4-6"}
)

# Set a fallback if routing fails
response = llm_service.call_llm(
    messages=messages,
    routing_context={"task_type": "code_generation", "fallback_provider": "openai"}
)
```

---

## Resilience & Retries

Every LLM call is automatically protected by retry with exponential backoff and a circuit breaker. No additional configuration is required to get these protections — they are on by default.

### Configuration

Configure resilience behavior in `agentmap_config.yaml` under `llm.resilience`:

```yaml
llm:
  resilience:
    retry:
      max_attempts: 3        # retries per provider:model
      backoff_base: 2.0      # exponential backoff base (seconds): 1s, 2s, 4s...
      backoff_max: 30.0      # cap on backoff delay
      jitter: true           # randomize delay to avoid thundering herd
    circuit_breaker:
      failure_threshold: 5   # failures before opening circuit for a provider:model
      reset_timeout: 60      # seconds before half-open (allows one retry)
```

### Retry behavior

Transient errors — rate limits, timeouts, and 5xx server errors — are retried automatically up to `max_attempts` times with exponential backoff. Non-transient errors (bad API key, missing model, missing package) fail immediately without retrying.

### Circuit breaker behavior

After `failure_threshold` consecutive failures for a given provider:model pair, the circuit opens. While open, calls to that provider:model fail fast without making an API request. After `reset_timeout` seconds, the circuit enters a half-open state and allows one request through. A success closes the circuit; another failure re-opens it.

These protections apply to all LLM calls — direct provider calls, routed calls, and fallback attempts.

See [LLM Configuration](../../configuration/llm-config) for the full configuration reference.

---

## Tiered Fallback

When a call fails after all retries are exhausted, a tiered fallback strategy kicks in. Fallback requires routing to be configured.

| Tier | Strategy | Example |
|------|----------|---------|
| 1 | Same provider, lower-complexity model from routing matrix | `anthropic:claude-opus-4-6` → `anthropic:claude-haiku-4-5` |
| 2 | Configured fallback provider (`routing.fallback.default_provider`) | Switch to `openai:gpt-4o-mini` |
| 3 | Emergency — first available provider not yet tried | Try `google:gemini-2.5-flash-lite` |
| 4 | All fallbacks exhausted — raises `LLMServiceError` with full context | — |

Dependency errors (missing packages) and configuration errors (bad API key) skip fallback entirely. Only transient provider errors trigger the fallback chain.

---

## Routing System

### Task Types vs Activities

These are two alternative approaches to controlling model selection:

| Approach | What you configure | How the model is chosen |
|---|---|---|
| **Task type** | Provider preferences + complexity keywords | Routing matrix lookup (provider + complexity → model) |
| **Activity** | Exact provider:model pairs per complexity tier | Direct — bypasses the routing matrix |

**Task types** provide soft guidance. You list preferred providers and keywords that detect complexity from the prompt. The system looks up the final model from the routing matrix. Good for most use cases.

**Activities** provide hard control. You pin exact models for each complexity tier with explicit fallback chains. The routing matrix is bypassed. Use when you need a specific model every time.

Most users need only one. If you set both with the same name (e.g., `"code_generation"`), the activity controls model selection and the task type only contributes complexity keyword detection.

#### Task type example

```python
# System picks the model based on prompt analysis and provider preferences
response = llm_service.call_llm(
    messages=messages,
    routing_context={"task_type": "code_generation"},
)
# "debug" in prompt → medium complexity → anthropic preferred → claude-sonnet-4-6
```

#### Activity example

```python
# You control exactly which model is used
response = llm_service.call_llm(
    messages=messages,
    routing_context={
        "activity": "code_generation",
        "complexity_override": "high",
    },
)
# → anthropic:claude-sonnet-4-6 (primary for code_generation:high)
# → falls back to openai:gpt-4.1 if primary fails
```

See [LLM Configuration](../../configuration/llm-config) for the full task type and activity configuration reference.

### How routing selects a model

1. Determine complexity (from `complexity_analysis` config — prompt length, keywords, memory size)
2. Check routing cache
3. If `activity` is set → look up activity routing table → get ordered candidates
4. If no activity candidates → fall back to `routing_matrix` (task_type + complexity → model)
5. On failure → use `fallback.default_provider` + `fallback.default_model`

### `routing_context` fields

All fields are optional. Routing is activated by passing a `routing_context` dict — no flag required.

| Field | Default | Description |
|---|---|---|
| `task_type` | `"general"` | Task classification; valid values come from `routing.task_types` in config |
| `activity` | `None` | Explicit activity name; takes priority over task_type |
| `complexity_override` | `None` | Skip auto-detection: `"low"`, `"medium"`, `"high"`, `"critical"` |
| `auto_detect_complexity` | `True` | Enable keyword/length-based complexity analysis |
| `provider_preference` | `[]` | Override provider order |
| `excluded_providers` | `[]` | Providers to skip |
| `model_override` | `None` | Force a specific model |
| `max_cost_tier` | `None` | Cap complexity tier (e.g. `"medium"` prevents high/critical models) |
| `cost_optimization` | `True` | Prefer cost-effective models |
| `prefer_speed` | `False` | Bias toward faster models |
| `prefer_quality` | `False` | Bias toward highest-quality models |
| `fallback_provider` | `None` | Override fallback provider for this call |
| `fallback_model` | `None` | Override fallback model for this call |
| `retry_with_lower_complexity` | `True` | On failure, retry with lower complexity tier |
| `max_tokens` | `None` | Max response tokens for this call. Overrides provider and activity defaults. `0` = no limit |

---

## `max_tokens` Priority

When using routing, `max_tokens` is resolved from multiple sources in this priority order:

1. **Node context** — `routing_context["max_tokens"]` or `max_tokens` in the CSV `context` field
2. **Activity config** — `max_tokens` set at the tier or candidate level in the activity definition
3. **Provider default** — `max_tokens` in the provider's `llm:` config section

If no source sets `max_tokens`, the provider's built-in default is used. Setting `max_tokens` to `0` at any level means "no limit" — it actively suppresses any provider default.

For direct calls (no routing), `max_tokens` passed to `call_llm()` overrides the provider config default.

---

## Exception Types

Import from `agentmap.exceptions`.

| Exception | When raised | Retryable? |
|---|---|---|
| `LLMConfigurationError` | Bad API key, auth failure, invalid model | No |
| `LLMDependencyError` | Missing provider package (e.g. `anthropic` not installed) | No |
| `LLMProviderError` | Generic provider-level errors | No |
| `LLMTimeoutError` | Timeout, connection errors, 5xx server errors | Yes (automatic) |
| `LLMRateLimitError` | 429 / rate limit / quota exceeded | Yes (automatic) |
| `LLMServiceError` | General service errors, all fallbacks exhausted | No |

`LLMTimeoutError` and `LLMRateLimitError` are subclasses of `LLMProviderError`, which is a subclass of `LLMServiceError`.

### Error handling in a host application

```python
import logging
from agentmap.exceptions import (
    LLMServiceError,
    LLMConfigurationError,
    LLMDependencyError,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

def fallback_response():
    """Placeholder for your application's fallback logic."""
    return "Service is temporarily unavailable. Please try again later."

try:
    response = llm_service.call_llm(
        provider="anthropic",
        messages=[{"role": "user", "content": "Summarize this report"}],
    )
except LLMConfigurationError as e:
    # Bad API key or invalid model — fix your configuration
    logger.error(f"Configuration error: {e}")
    raise
except LLMDependencyError as e:
    # Missing provider package — install it (e.g. pip install anthropic)
    logger.error(f"Missing dependency: {e}")
    raise
except LLMRateLimitError as e:
    # Rate limited even after automatic retries — back off at application level
    logger.warning(f"Rate limited after retries: {e}")
    return fallback_response()
except LLMTimeoutError as e:
    # Timeout/connection error after retries — provider may be down
    logger.warning(f"Provider unreachable after retries: {e}")
    return fallback_response()
except LLMServiceError as e:
    # All fallback tiers exhausted
    logger.error(f"LLM call failed completely: {e}")
    raise
```

### Error handling in a custom agent

```python
class MyAgent(BaseAgent, LLMCapableAgent):
    def process(self, inputs):
        try:
            return self.llm_service.call_llm(
                provider="anthropic",
                messages=[{"role": "user", "content": inputs["query"]}],
            )
        except LLMConfigurationError:
            # Surface config errors — the workflow operator needs to fix this
            raise
        except LLMServiceError:
            # Transient errors were already retried; fallback was attempted.
            # Return a graceful degradation or let the error_node handle it.
            return "I'm sorry, I couldn't process your request right now."
```

---

## Available Providers

```python
providers = llm_service.get_available_providers()
# Returns: ['anthropic', 'openai', 'google']  (only those with API keys configured)
```

---

## Agent Integration

Agents that need LLM access implement the `LLMCapableAgent` protocol:

```python
from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols.llm_protocol import LLMCapableAgent, LLMServiceProtocol
from typing import Any, Dict

class MyLLMAgent(BaseAgent, LLMCapableAgent):
    def configure_llm_service(self, llm_service: LLMServiceProtocol) -> None:
        self._llm_service = llm_service

    @property
    def llm_service(self) -> LLMServiceProtocol:
        if self._llm_service is None:
            raise ValueError(f"LLM service not configured for agent '{self.name}'")
        return self._llm_service

    def process(self, inputs: Dict[str, Any]) -> Any:
        provider = self.context.get("provider", "anthropic")
        messages = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": inputs.get("query", "")}
        ]
        return self.llm_service.call_llm(
            provider=provider,
            messages=messages,
            temperature=self.context.get("temperature", 0.7),
        )
```

### CSV configuration

The `context` field contains JSON. In CSV, double quotes inside a quoted field must be escaped as `""` — this is standard CSV encoding, not AgentMap-specific.

Direct provider call:

```csv
workflow,node,description,type,next_node,error_node,input_fields,output_field,prompt,context
ChatBot,Chat,Chat with AI,llm,Chat,Error,message,response,You are a helpful assistant,"{""provider"": ""anthropic"", ""model"": ""claude-sonnet-4-6"", ""temperature"": 0.7, ""max_tokens"": 2048}"
```

With routing context — routing selects the provider and model; `provider` and `model` are omitted:

```csv
workflow,node,description,type,next_node,error_node,input_fields,output_field,prompt,context
CodeBot,Generate,Generate code,llm,Review,Error,request,code,You are an expert software engineer,"{""routing_context"": {""activity"": ""code_generation"", ""complexity_override"": ""high""}, ""temperature"": 0.2}"
```

With task-type routing and a cost cap:

```csv
workflow,node,description,type,next_node,error_node,input_fields,output_field,prompt,context
Analyst,Analyze,Analyze data,llm,Output,Error,data,analysis,You are a data analyst,"{""routing_context"": {""task_type"": ""data_analysis"", ""max_cost_tier"": ""medium""}, ""temperature"": 0.5}"
```

With an activity for pinned model selection:

```csv
workflow,node,description,type,next_node,error_node,input_fields,output_field,prompt,context
CodeBot,Review,Review code,llm,Done,Error,code,feedback,You are a code reviewer,"{""routing_context"": {""activity"": ""code_generation"", ""complexity_override"": ""high""}, ""temperature"": 0.2}"
```

---

## Async Fan-Out (`call_llm_many_async`)

`call_llm_many_async()` submits many LLM call specs in a single async call and returns one terminal result record per submitted spec. It reuses the existing async realtime path — routing, retries, timeouts, fallback, circuit-breaker, and E05-F01 cache-aware request support all apply per item.

Fan-out is additive. The synchronous `call_llm() -> str` and the high-level `ask()`, `ask_async()`, `ask_vision()` interfaces are unchanged. The internal `call_llm_async()` method now returns `LLMResponse` (carrying resolved provider, model, and usage) rather than a plain `str`; the public `ask_async()` method continues to return `str` by extracting `.text` from the response.

### Request shape

```python
from agentmap.models.llm_execution import LLMCallSpec, LLMCallResult, LLMUsage

specs = [
    # Direct provider item
    LLMCallSpec(
        spec_id="item-1",
        messages=[{"role": "user", "content": "Translate to French: Hello"}],
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.3,
    ),
    # Routed item — routing selects provider and model
    LLMCallSpec(
        spec_id="item-2",
        messages=[{"role": "user", "content": "Summarize this report."}],
        routing_context={"task_type": "summarization"},
    ),
    # Cache-aware item (E05-F01 compatible)
    LLMCallSpec(
        spec_id="item-3",
        messages=[
            {"role": "system", "content": [{"type": "text", "text": "You are helpful."}]},
            {"role": "user", "content": "What is 2+2?"},
        ],
        provider="anthropic",
        request_options={"requires_prompt_caching": True, "cache_mode": "ephemeral"},
    ),
]

results: list[LLMCallResult] = await llm_service.call_llm_many_async(
    call_specs=specs,
    max_concurrency=4,
)
```

**`LLMCallSpec` fields**

| Field | Type | Required | Description |
|---|---|---|---|
| `spec_id` | `str` | Yes | Unique identifier for this item within the submission. Must be unique across all items in a single call. |
| `messages` | `List[Dict]` | Yes | Messages list in the same shape as `call_llm()`. Supports both plain string content and structured content blocks (E05-F01). |
| `provider` | `Optional[str]` | No | Target provider for direct execution. Ignored when `routing_context` is provided. |
| `model` | `Optional[str]` | No | Model override. Ignored when `routing_context` is provided. |
| `temperature` | `Optional[float]` | No | Temperature override for this item. |
| `routing_context` | `Optional[Dict]` | No | Routing context. When present, routing selects provider and model — same semantics as `call_llm()`. |
| `request_options` | `Dict[str, Any]` | No | Additional keyword arguments forwarded to `call_llm_async()` unchanged. Use for cache-aware fields such as `requires_prompt_caching` and `cache_mode`. |

### `spec_id` uniqueness rule

Each `spec_id` must be unique within one `call_llm_many_async()` submission. Duplicate `spec_id` values cause the entire submission to fail before any provider call begins.

### Concurrency limit (`max_concurrency`)

`max_concurrency` caps the number of in-flight provider calls at any time. Must be an integer >= 1.

- `max_concurrency=1` — fully sequential; no two items execute at the same time.
- `max_concurrency=N` — up to N items execute concurrently.
- The fan-out enforces this cap via `asyncio.Semaphore`; no item bypasses it.

### Result shape

`call_llm_many_async()` returns a `List[LLMCallResult]` with the same length and positional order as `call_specs`. Order is stable even when provider responses arrive out of order.

```python
for result in results:
    if result.status == "succeeded":
        print(f"{result.spec_id}: {result.content}")
        if result.usage:
            print(f"  tokens: {result.usage.input_tokens} in / {result.usage.output_tokens} out")
            if result.usage.cache_read_input_tokens:
                print(f"  cache read: {result.usage.cache_read_input_tokens} tokens")
    else:
        print(f"{result.spec_id} failed: {result.error.message} ({result.error.error_type})")
```

**`LLMCallResult` fields**

| Field | Type | Description |
|---|---|---|
| `spec_id` | `str` | The `spec_id` from the originating `LLMCallSpec`. Always present, including on failure. |
| `status` | `str` | `"succeeded"` or `"failed"`. |
| `provider` | `Optional[str]` | The provider that **actually handled** this item (after routing or fallback tier selection). `None` only when a routing failure occurred before provider resolution. |
| `model` | `Optional[str]` | The model that **actually handled** this item (after routing or fallback tier selection). `None` only when a routing failure occurred before model resolution. |
| `content` | `Optional[str]` | Response text. Present only on success. |
| `usage` | `Optional[LLMUsage]` | Normalized usage envelope. Present when the provider returned usage metadata. This includes routed and fallback items — the resolved provider's raw response is used to extract usage, so cache-aware fields such as `cache_read_input_tokens` are available on routed cache-aware requests. |
| `error` | `Optional[LLMExecutionError]` | Structured error payload. Present only on failure. |

**`LLMUsage` fields** (all `Optional[int]`)

| Field | Description |
|---|---|
| `input_tokens` | Prompt tokens consumed. |
| `output_tokens` | Completion tokens generated. |
| `cache_creation_input_tokens` | Tokens written to the prompt cache (Anthropic cache-aware requests). |
| `cache_read_input_tokens` | Tokens served from the prompt cache (Anthropic cache-aware requests). |

Absent fields remain `None` rather than being filled with a default value.

**`LLMExecutionError` fields**

| Field | Type | Description |
|---|---|---|
| `error_type` | `str` | Exception class name (e.g. `"LLMTimeoutError"`, `"RuntimeError"`). |
| `message` | `str` | Human-readable error message. |
| `retryable` | `bool` | Whether the error class is retryable per the resilience configuration. |

### Partial-failure semantics

A single failing item does not cancel, abort, or modify sibling items. Each item is independent:

- Pre-execution validation failures (empty submission, duplicate `spec_id`, invalid `max_concurrency`) raise `LLMServiceError` before any provider call begins.
- Once execution starts, per-item errors are captured as `LLMCallResult` records with `status="failed"`. The submission-level `call_llm_many_async()` call does not re-raise item exceptions.
- Sibling items continue to completion regardless of another item's failure.

**Failure-path resolved identity**

When a fan-out item fails *after* routing or fallback selected a concrete provider and model, the failure record carries that resolved identity:

```python
# Spec requests no specific provider — routing selects anthropic:claude-haiku.
# The call then times out. The failure record still names the provider tried.
spec = LLMCallSpec(
    spec_id="routed-item",
    messages=[{"role": "user", "content": "hello"}],
    provider=None,  # routing chooses the provider
    routing_context={"routing_enabled": True},
)
results = await llm_service.call_llm_many_async([spec], max_concurrency=1)
r = results[0]
assert r.status == "failed"
assert r.provider == "anthropic"    # resolved before the failure
assert r.model == "claude-haiku"    # resolved before the failure
assert r.error.error_type == "LLMTimeoutError"
```

When failure occurs before any provider was selected (e.g., the routing service itself raises), `result.provider` and `result.model` remain `None` — they are never fabricated.

This behaviour is implemented via the `LLMResolvedCallError` exception (subclass of `LLMServiceError`). The fan-out layer catches it and extracts the resolved identity. Single-call callers using `call_llm_async()` directly receive `LLMResolvedCallError` propagated unchanged; existing `except LLMServiceError` handlers continue to match.

**`LLMResolvedCallError` attributes**

| Attribute | Type | Description |
|---|---|---|
| `resolved_provider` | `Optional[str]` | The concrete provider that was attempted before the failure. |
| `resolved_model` | `Optional[str]` | The concrete model that was attempted before the failure. |
| `cause` | `BaseException` | The underlying typed exception (e.g. `LLMProviderError`, `LLMTimeoutError`) that triggered the failure. |

```python
specs = [
    LLMCallSpec(spec_id="ok", messages=[...], provider="openai"),
    LLMCallSpec(spec_id="bad-cache", messages=[...], provider="openai",
                request_options={"requires_prompt_caching": True}),
]
results = await llm_service.call_llm_many_async(specs, max_concurrency=2)
# results[0].status == "succeeded"
# results[1].status == "failed"  — unsupported cache mode on this provider
```

### Cache-aware requests (E05-F01 compatibility)

Fan-out items fully support E05-F01 structured message content and cache-aware request options. Pass structured blocks and caching metadata through `request_options` — the fan-out layer forwards them unchanged to `call_llm_async()`:

```python
LLMCallSpec(
    spec_id="cached-system",
    messages=[
        {
            "role": "system",
            "content": [
                {"type": "text", "text": "Long system prompt...", "cache_control": {"type": "ephemeral"}}
            ],
        },
        {"role": "user", "content": "Question here"},
    ],
    provider="anthropic",
    request_options={"requires_prompt_caching": True},
)
```

When a cache-aware item succeeds, the resolved provider and cache usage are both visible on the result — even when routing selected a different model than the spec's nominal provider:

```python
result = results[0]  # spec_id="cached-system"
assert result.status == "succeeded"
assert result.provider == "anthropic"           # resolved provider (after any routing)
assert result.model == "claude-3-haiku"         # resolved model (after any routing)
assert result.usage.cache_creation_input_tokens == 1024  # tokens written to cache
assert result.usage.cache_read_input_tokens == 0         # first request — nothing cached yet
# On a subsequent identical request:
# result.usage.cache_read_input_tokens == 1024  # served from cache
# result.usage.cache_creation_input_tokens == 0
```

An unsupported cache mode (e.g. requesting prompt caching from a provider that does not support it) fails the item with the same `LLMServiceError` family as the single-call path, without affecting sibling items.

---

## External Usage

```python
from agentmap import agentmap_initialize
from agentmap.runtime_api import get_container  # not exported from top-level agentmap

agentmap_initialize()
llm_service = get_container().llm_service()

response = llm_service.call_llm(
    provider="anthropic",
    messages=[{"role": "user", "content": "Hello"}]
)
```

---

## Monitoring

Use `get_routing_stats()` to inspect circuit breaker state and identify providers experiencing issues:

```python
stats = llm_service.get_routing_stats()
# Returns:
# {
#     "circuit_breaker": {
#         "open_circuits": ["anthropic:claude-opus-4-6"],
#         "failure_counts": {"anthropic:claude-opus-4-6": 5}
#     },
#     ...routing stats...
# }
```

Open circuits indicate a provider:model pair that has hit the failure threshold and is currently being bypassed. Monitor this in production to detect persistent provider outages or configuration issues early.

---

## Best Practices

1. **Store API keys in environment variables** — never hardcode them.
2. **Use routing for complex pipelines** — activities give you explicit control; task_types offer keyword-driven automation.
3. **Use `ask()` for quick one-off prompts** — only reach for `call_llm()` when you need messages, routing, or model overrides.
4. **Cap complexity tier with `max_cost_tier`** — prevents accidentally routing simple tasks to expensive models.
5. **Keep conversation history reasonable** — 10–20 messages is a good ceiling; trim older messages when memory grows.
6. **Let retries handle transient failures** — don't add your own retry loop around `call_llm()`; the service already retries rate limits and timeouts automatically.
7. **Catch specific exceptions** — handle `LLMConfigurationError` (fix your config) differently from `LLMServiceError` (transient, may resolve later).
8. **Monitor circuit breaker state** — use `get_routing_stats()` to detect providers that are consistently failing.

---

## Batch Execution

`LLMService` exposes five additive methods for provider-native batch execution,
supporting Anthropic, OpenAI, and Gemini.  Batch execution submits many
independent requests to the provider in a single API call, which providers
typically price at a significant discount (e.g. Anthropic at 50 % of the
per-token rate).  No provider SDK types cross the service boundary — all callers
work exclusively with AgentMap-owned data classes.

### Provider capability matrix

| Capability | Anthropic | OpenAI | Gemini |
|---|---|---|---|
| `submit_batch` / `asubmit_batch` | Yes | Yes | Yes |
| `poll_batch` / `apoll_batch` | Yes | Yes | Yes |
| `cancel_batch` / `acancel_batch` | Yes | Yes | Yes |
| `fetch_batch_results` / `afetch_batch_results` | Yes | Yes | Yes |
| `wait_for_batch` | Yes | Yes | Yes |
| `restore_batch` (cross-process handle reload) | Yes | Yes | Yes |
| Gemini delivery mechanism | inline | — | inline only (File API / Vertex / GCS / BigQuery are out of scope) |
| Normalized `LLMBatchStatus` | Yes | Yes | Yes |
| `supports_cancel` (`batch_capabilities` key) | `True` | `True` | `True` |

`batch_capabilities(provider)` returns a dict with at minimum these keys:

| Key | Type | Description |
|---|---|---|
| `supports_cancel` | `bool` | Whether the adapter supports `cancel_batch` (all three providers: `True`) |
| `provider_name` | `str` | Canonical adapter provider name string |
| `supported` | `bool` | Whether an adapter is registered for this provider |

### Installation

The batch SDKs are optional extras.  Install the providers you need:

```bash
pip install "agentmap[batch]"         # all three: anthropic, openai, google-genai
pip install "agentmap[all]"           # everything including batch
```

Or individually:

```bash
pip install anthropic openai google-genai
```

If a provider SDK is not installed, its adapter is silently absent from the
registry (a warning is logged).  Attempting `submit_batch` for an unregistered
provider raises `LLMBatchUnsupportedProviderError`.

### Sync usage example

```python
from agentmap.models.llm_execution import LLMBatchSubmitRequest, LLMCallSpec

request = LLMBatchSubmitRequest(
    provider="openai",          # or "anthropic" or "google"
    model="gpt-4o-mini",
    max_tokens=512,
    call_specs=[
        LLMCallSpec(spec_id="q1", messages=[{"role": "user", "content": "What is 2+2?"}]),
        LLMCallSpec(spec_id="q2", messages=[{"role": "user", "content": "What is the capital of France?"}]),
    ],
)
handle = llm_service.submit_batch(request)

# Poll until complete
import time
while handle.status not in ("ended", "expired", "failed"):
    time.sleep(30)
    handle = llm_service.poll_batch(handle)

results = llm_service.fetch_batch_results(handle)
for record in results:
    print(record.spec_id, record.content)
```

### Async usage example

```python
import asyncio

async def run():
    handle = await llm_service.asubmit_batch(request)
    handle = await llm_service.wait_for_batch(handle, poll_interval=30.0)
    results = await llm_service.afetch_batch_results(handle)
    return results

results = asyncio.run(run())
```

### Restore-after-restart pattern (all providers)

`LLMBatchHandle` is fully serializable and provider-agnostic.
The `provider` field on the handle drives all dispatch decisions:

```python
# Process 1 — submit
handle = llm_service.submit_batch(request)
store_to_db(handle.agentmap_batch_id, handle.to_dict())

# Process 2 — poll after restart (provider re-resolved from handle.provider)
handle_data = load_from_db(agentmap_batch_id)
handle = llm_service.restore_batch(handle_data)
handle = llm_service.poll_batch(handle)   # dispatches to correct adapter via registry
```

### Configuration

Add a `batch_dir` key under `llm:` in `agentmap_config.yaml`:

```yaml
llm:
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-sonnet-4-6"
  batch_dir: "agentmap_data/llm_batches"   # file-backed handle storage
```

`batch_dir` is the directory where `LLMBatchHandle` JSON files are persisted.
The directory is created automatically if it does not exist.

### Data classes

| Class | Description |
|---|---|
| `LLMBatchSubmitRequest` | Input to `submit_batch` — provider, model, list of `LLMCallSpec`, `max_tokens` |
| `LLMCallSpec` | Single request within a batch — `spec_id`, `messages`, optional `request_options` |
| `LLMBatchHandle` | Returned by `submit_batch` and all lifecycle methods — serializable, no SDK types |
| `LLMBatchResultRecord` | Per-item result keyed by `spec_id` — `status`, `content`, `usage`, `error` |
| `LLMUsage` | Normalized token usage — `input_tokens`, `output_tokens`, optional cache fields |
| `LLMExecutionError` | Structured error for errored items — `error_type`, `message`, `retryable` |

### Canonical parameter resolution (D-8)

`LLMBatchSubmitRequest` and each `LLMCallSpec` each expose multiple "surfaces"
where the same logical parameter can be set:

| Surface | Example |
|---|---|
| S1 — per-spec direct field | `spec.temperature = 0.2` |
| S2 — per-spec `request_options` | `spec.request_options = {"temperature": 0.2}` |
| S3 — batch-level direct field | `request.max_tokens = 1024` |
| S4 — batch-level `request_options` | `request.request_options = {"temperature": 0.2}` |

**Reserved parameters** (`temperature`, `model`, `max_tokens`) are detected across all
applicable surfaces.  The resolution rule, applied per spec before any adapter call:

- **One surface set** — that value is applied.
- **Multiple surfaces, all equal** — applied; no error.
- **Multiple surfaces with different values** — `LLMBatchParamConflictError` is raised,
  naming the `spec_id`, the logical parameter, and each conflicting surface with its value.
  Nothing is silently dropped.

Pass-through keys (any `request_options` key not in the reserved list) obey the same
rule: present in one dict → applied; present in both with the same value → applied;
present in both with different values → `LLMBatchParamConflictError`.

**Batch-incompatible params** (`stream=True`, `max_tokens=0`) are always rejected with
`LLMServiceError`, regardless of which surface they appear on.

```python
# WRONG — same parameter on two surfaces with different values
spec = LLMCallSpec(
    spec_id="q1",
    messages=[...],
    temperature=0.2,                          # S1
    request_options={"temperature": 0.9},     # S2 — CONFLICT
)
# → LLMBatchParamConflictError: spec_id='q1': conflicting values for parameter
#     'temperature' — spec direct field=0.2, spec.request_options=0.9.
#     Set this parameter on exactly one surface.

# CORRECT — single surface
spec = LLMCallSpec(spec_id="q1", messages=[...], temperature=0.2)
```

### Typed batch errors

| Exception | When raised |
|---|---|
| `LLMBatchUnsupportedProviderError` | `provider` has no registered adapter (SDK absent or unconfigured) |
| `LLMBatchParamConflictError` | Same logical parameter set on two surfaces with different values (D-8) |
| `LLMBatchResultIntegrityError` | Gemini returned a different number of inline responses than were submitted; positional demux would misattribute results (D-9) |
| `LLMBatchCancelNotSupportedError` | `cancel_batch` called on a terminal handle (`ended` or `expired`) |
| `LLMBatchNotReadyError` | `fetch_batch_results` called before status is `ended` |
| `LLMBatchExpiredError` | Operation attempted on an expired batch |

All batch errors subclass `LLMServiceError`.

#### `LLMBatchResultIntegrityError` — Gemini demux integrity (D-9)

Gemini inline batches carry no per-response key; results are correlated by position.
If the provider returns fewer responses than were submitted, the adapter raises
`LLMBatchResultIntegrityError` (naming the batch id, submitted count, and returned
count) rather than silently shifting results onto wrong `spec_id` values.

When a short-tail response set is detected at the service level (result count < spec
count after a successful fetch), missing records are synthesized as errored
`LLMBatchResultRecord` entries with `error_type="missing_result"` so every submitted
`spec_id` always has a corresponding record.  OpenAI and Anthropic are unaffected —
they demux by `custom_id`/key.

### Normalized status values

| Status | Meaning |
|---|---|
| `submitted` | Batch submitted; not yet processing |
| `in_progress` | Provider is processing requests |
| `canceling` | Cancel initiated; not yet terminal |
| `canceled` | Batch was canceled by the caller |
| `ended` | Processing complete; results available |
| `expired` | Batch expired before completion |
| `failed` | Unknown or unrecognized provider status |

### `spec_id` / `custom_id` mapping

Anthropic requires `custom_id` values to match `^[a-zA-Z0-9_-]{1,64}$`.
`LLMService` sanitizes spec_ids that violate this pattern using a deterministic
SHA-1 hash and stores the `spec_id -> custom_id` map in the handle.  On
`fetch_batch_results`, results are re-keyed by the original caller `spec_id`.

### Batch lifecycle methods

#### `submit_batch(request: LLMBatchSubmitRequest) -> LLMBatchHandle`

Validates the request, submits to the provider, persists the handle to `batch_dir`,
and returns an `LLMBatchHandle`.  Supported providers: `"anthropic"`, `"openai"`, `"google"`.

**Validation errors (raised before any network call):**
- `LLMBatchUnsupportedProviderError` — provider has no registered adapter (SDK absent or unconfigured)
- `LLMServiceError` — `call_specs` is empty, contains duplicate `spec_id` values,
  or a spec has batch-incompatible `request_options` (`stream=True`, `max_tokens=0`)

```python
from agentmap.models.llm_execution import LLMBatchSubmitRequest, LLMCallSpec

# Works for any registered provider: "anthropic", "openai", or "google"
request = LLMBatchSubmitRequest(
    provider="anthropic",          # or "openai" or "google"
    model="claude-sonnet-4-6",     # provider-specific model name
    max_tokens=1024,
    call_specs=[
        LLMCallSpec(spec_id="task-1", messages=[{"role": "user", "content": "Q1"}]),
        LLMCallSpec(spec_id="task-2", messages=[{"role": "user", "content": "Q2"}]),
    ],
)
handle = llm_service.submit_batch(request)
print(handle.agentmap_batch_id)   # "amatch_..."
print(handle.status)              # LLMBatchStatus.SUBMITTED
```

#### `restore_batch(handle_data: dict) -> LLMBatchHandle`

Reconstructs an `LLMBatchHandle` from a serialized `dict` (e.g. loaded from a
database or message queue after a process restart).  Validates that required
fields (`provider_batch_id`, `agentmap_batch_id`, `spec_id_map`) are present.

**Error:** `LLMServiceError` — required field missing from `handle_data`.

```python
# After restart — load the dict from wherever you stored it
handle = llm_service.restore_batch(handle_data)
```

#### `poll_batch(handle: LLMBatchHandle) -> LLMBatchHandle`

Queries the provider for the current processing status and returns an updated
handle.  The returned handle's `status` is one of the six normalized values
above.  Unknown provider statuses map to `"failed"`.

```python
updated_handle = llm_service.poll_batch(handle)
if updated_handle.status == LLMBatchStatus.ENDED:
    results = llm_service.fetch_batch_results(updated_handle)
```

#### `cancel_batch(handle: LLMBatchHandle) -> LLMBatchHandle`

Requests cancellation from the provider and returns an updated handle.

**Error:** `LLMBatchCancelNotSupportedError` — handle is already in a terminal
state (`ended` or `expired`).  Cancellation of a batch already in `canceling`
state is a no-op (re-triggers the provider cancel request).

#### `fetch_batch_results(handle: LLMBatchHandle) -> list[LLMBatchResultRecord]`

Fetches results for an `ended` batch.  Returns one `LLMBatchResultRecord` per
`spec_id` in submission order.

**Error:** `LLMBatchNotReadyError` — handle status is not `"ended"` (i.e.
`submitted`, `in_progress`, or `canceling`).

```python
results = llm_service.fetch_batch_results(ended_handle)
for record in results:
    if record.status == "succeeded":
        print(record.spec_id, record.content)
        print(record.usage.input_tokens, record.usage.output_tokens)
    elif record.status == "errored":
        print(record.spec_id, record.error.error_type, record.error.message)
    else:
        # "canceled" or "expired"
        print(record.spec_id, record.status)
```

#### `wait_for_batch(handle, *, poll_interval=5.0, timeout=None) -> LLMBatchHandle` (async)

Polls `apoll_batch` with capped exponential backoff until the batch reaches a
terminal status (`ended`, `canceled`, `expired`, `failed`) or `timeout` seconds
elapse.  Pass `timeout=None` (the default) to wait indefinitely.

**Error:** `TimeoutError` — if `timeout` is set and the batch has not reached a
terminal status within that many seconds.

```python
# Wait at most 10 minutes
handle = await llm_service.wait_for_batch(handle, poll_interval=30.0, timeout=600)

# Wait indefinitely
handle = await llm_service.wait_for_batch(handle, poll_interval=30.0)
```

#### `submit_and_wait(request, *, poll_interval=5.0, timeout=None) -> LLMBatchHandle` (sync)

Synchronous convenience: submit a batch then block until it reaches a terminal
status.  Internally calls `asyncio.run` and delegates to `wait_for_batch`.

#### `batch_capabilities(provider: str) -> dict`

Returns capability metadata for a registered provider adapter.  See the
capability matrix above for the key definitions.

**Error:** `LLMBatchUnsupportedProviderError` — provider has no registered adapter.

```python
caps = llm_service.batch_capabilities("google")
# {"supports_cancel": True, "provider_name": "google", "supported": True, ...}
```

#### `results_by_spec_id(records) -> dict[str, LLMBatchResultRecord]` (static)

Index a list of result records by `spec_id` for O(1) lookups.

```python
by_id = LLMService.results_by_spec_id(results)
print(by_id["task-1"].content)
```

#### `reconcile_batch_results(submitted_spec_ids, records) -> dict[str, LLMBatchResultRecord | None]` (static)

Reconcile submitted spec_ids against the records returned by
`fetch_batch_results` (REQ-F-009c).  Returns a dict mapping every submitted
`spec_id` to its `LLMBatchResultRecord` if the provider returned one, or `None`
if the provider returned no result for that spec_id.  A `None` value indicates
possible silent data loss and should be investigated.

```python
reconciled = LLMService.reconcile_batch_results(
    submitted_spec_ids=["task-1", "task-2", "task-3"],
    records=results,
)
for spec_id, record in reconciled.items():
    if record is None:
        print(f"WARNING: no result for {spec_id} — investigate")
    elif record.status == "succeeded":
        print(spec_id, record.content)
```

### Error conditions reference

| Exception | Raised by | Condition |
|---|---|---|
| `LLMBatchUnsupportedProviderError` | `submit_batch` | Provider has no registered adapter (SDK absent or unconfigured) |
| `LLMServiceError` | `submit_batch` | Empty `call_specs`, duplicate `spec_id`, batch-incompatible params |
| `LLMServiceError` / `ValueError` | `restore_batch` | Missing required field in `handle_data` |
| `LLMBatchCancelNotSupportedError` | `cancel_batch` | Handle already in terminal state |
| `LLMBatchNotReadyError` | `fetch_batch_results` | Handle status is not `"ended"` |
| `LLMDependencyError` | Adapter init | Provider SDK not importable (`anthropic`, `openai`, or `google-genai`) |

### Restore-after-restart pattern

`LLMBatchHandle` is fully serializable.  Store `handle.to_dict()` to any
persistence layer (database, Redis, S3) and reconstruct with `restore_batch`:

```python
# Process 1 — submit
handle = llm_service.submit_batch(request)
store_to_db(handle.agentmap_batch_id, handle.to_dict())

# Process 2 — poll (different process, after restart)
handle_data = load_from_db(agentmap_batch_id)
handle = llm_service.restore_batch(handle_data)
handle = llm_service.poll_batch(handle)
```

The persisted JSON file in `batch_dir` is an additional recovery path — it is
**never written with an `api_key`** field (security requirement).

### DI wiring

All three batch adapters (`AnthropicBatchAdapter`, `OpenAIBatchAdapter`,
`GeminiBatchAdapter`) and `BatchHandleRepository` are registered as singletons
in `LLMContainer`.  No manual wiring is required when using the DI container.
Each adapter factory catches `LLMDependencyError` (raised when the provider SDK
is not installed) and returns `None`; the container then omits that provider from
the registry.  Only adapters with a working SDK and configured API key are
registered.

---

## Next Steps

- **[LLM Configuration](../../configuration/llm-config)** — Provider setup, resilience tuning, and routing matrix
- **[Storage Services](./storage-services-overview)** — Data persistence options
- **[Capability Protocols](../capabilities/)** — Agent protocol reference
- **[Agent Development](../agents/custom-agents)** — Build custom LLM agents
