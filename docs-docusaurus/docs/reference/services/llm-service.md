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

### Pattern 1b: Direct prompt-caching call

Prompt caching is supported only on realtime text paths and only for providers marked cache-capable in `routing.provider_capabilities`.

```python
response = llm_service.call_llm(
    provider="anthropic",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Reusable prefix",
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": "Answer the follow-up question."},
            ],
        }
    ],
)
```

If prompt caching is requested for a provider not marked cache-capable, `LLMService` raises `LLMServiceError` before creating the provider client.

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

### Pattern 3b: Routed prompt-caching call

Use `routing_context["requires_prompt_caching"] = True` when the request must stay on cache-capable providers:

```python
response = llm_service.call_llm(
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Long shared context",
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": "Summarize the delta."},
            ],
        }
    ],
    routing_context={
        "task_type": "general",
        "requires_prompt_caching": True,
    },
)
```

Routing filters candidates to providers whose `routing.provider_capabilities.<provider>.prompt_caching` value is `true`. If no eligible provider remains, the call fails with an explicit `LLMServiceError` instead of silently degrading to a non-cache provider.

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
| `requires_prompt_caching` | `False` | Restrict routing to providers marked cache-capable for realtime text execution |

---

## `max_tokens` Priority

When using routing, `max_tokens` is resolved from multiple sources in this priority order:

1. **Node context** — `routing_context["max_tokens"]` or `max_tokens` in the CSV `context` field
2. **Activity config** — `max_tokens` set at the tier or candidate level in the activity definition
3. **Provider default** — `max_tokens` in the provider's `llm:` config section

If no source sets `max_tokens`, the provider's built-in default is used. Setting `max_tokens` to `0` at any level means "no limit" — it actively suppresses any provider default.

For direct calls (no routing), `max_tokens` passed to `call_llm()` overrides the provider config default.

---

## Provider-Agnostic Prompt Caching

The `cache_system_prompt=True` parameter lets you declare caching intent without constructing provider-native `cache_control` blocks. AgentMap injects the correct metadata before calling the provider — or silently no-ops for providers that handle caching automatically.

### Per-provider behavior

| Provider | Effect of `cache_system_prompt=True` |
|---|---|
| **Anthropic** | Injects `cache_control: {"type": "ephemeral"}` on the system message before provider invocation. Requires a system-role message in `messages`. |
| **OpenAI** | No-op. OpenAI automatically caches prompts over 1024 tokens — no explicit metadata is needed. The call proceeds unchanged. |
| **Google (Gemini)** | Unsupported. Raises `LLMServiceError` before provider invocation. Gemini prompt caching is out of scope for this feature. |

Capability is gated through `routing.provider_capabilities` for most providers. **OpenAI is exempt from this check** — it is always treated as a no-op (automatic server-side caching) regardless of the `prompt_caching` config value. For all other providers, passing `cache_system_prompt=True` to a provider not marked cache-capable raises `LLMServiceError` before the client is created.

### `call_llm()` example

```python
response = llm_service.call_llm(
    provider="anthropic",
    messages=[
        {"role": "system", "content": "You are a helpful assistant with deep knowledge of Python."},
        {"role": "user", "content": "Explain generator expressions."},
    ],
    cache_system_prompt=True,
)
```

AgentMap wraps the system message content with `cache_control: {"type": "ephemeral"}` before calling Anthropic. On subsequent calls with the same system message the cached tokens are served from Anthropic's prompt cache.

### `ask()` example

`ask()` passes `cache_system_prompt=True` through to `call_llm()` via `**kwargs`. Because `ask()` constructs a user-role message only (no system message), injection is a no-op — the kwarg is forwarded without error:

```python
response = llm_service.ask(
    "Summarize this document.",
    provider="anthropic",
    cache_system_prompt=True,
)
```

To cache a system prompt with `ask()`, use `call_llm()` directly with an explicit system-role message.

### `LLMRequest` fan-out example

Fan-out submissions can declare caching intent per-request via the `cache_system_prompt` field on `LLMRequest`:

```python
from agentmap.models.llm_execution import LLMRequest

requests = [
    LLMRequest(
        request_id="item-1",
        messages=[
            {"role": "system", "content": "You are an expert code reviewer."},
            {"role": "user", "content": "Review this function for edge cases."},
        ],
        provider="anthropic",
        cache_system_prompt=True,
    ),
    LLMRequest(
        request_id="item-2",
        messages=[
            {"role": "system", "content": "You are an expert code reviewer."},
            {"role": "user", "content": "Suggest a refactoring for the same function."},
        ],
        provider="anthropic",
        cache_system_prompt=True,
    ),
]

results = await llm_service.call_llm_many_async(requests=requests, max_concurrency=2)
```

Each fan-out item applies the same provider-specific injection as the single-call path. The shared system message is cached after the first request and served from cache on subsequent identical requests.

### Coexistence with manual `cache_control` passthrough

If you already have `cache_control` blocks in your messages (E05-F01 passthrough style) and also set `cache_system_prompt=True`, AgentMap does not double-wrap blocks that already carry `cache_control`. You can safely combine both styles — the injection is idempotent.

For advanced manual `cache_control` construction see [Pattern 1b: Direct prompt-caching call](#pattern-1b-direct-prompt-caching-call) and [Pattern 3b: Routed prompt-caching call](#pattern-3b-routed-prompt-caching-call).

---

## Prompt-Caching Limits

- Supported execution paths in this feature slice: `call_llm()`, `call_llm_async()`, `ask()`, `ask_async()`
- Unsupported execution path in this feature slice: `ask_vision()`
- Prompt caching is provider-gated through `routing.provider_capabilities`
- Existing plain-text and non-cache structured requests keep their prior behavior

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

`call_llm_many_async()` submits many LLM requests in a single async call and returns one terminal result record per submitted request. It reuses the existing async realtime path — routing, retries, timeouts, fallback, circuit-breaker, and E05-F01 cache-aware request support all apply per item.

Fan-out is additive. The synchronous `call_llm() -> str` and the high-level `ask()`, `ask_async()`, `ask_vision()` interfaces are unchanged. The internal `call_llm_async()` method now returns `LLMResponse` (carrying resolved provider, model, and usage) rather than a plain `str`; the public `ask_async()` method continues to return `str` by extracting `.text` from the response.

### Request shape

```python
from agentmap.models.llm_execution import LLMRequest, LLMFanoutResult, LLMUsage

requests = [
    # Direct provider item
    LLMRequest(
        request_id="item-1",
        messages=[{"role": "user", "content": "Translate to French: Hello"}],
        provider="openai",
        model="gpt-4o-mini",
        temperature=0.3,
    ),
    # Routed item — routing selects provider and model
    LLMRequest(
        request_id="item-2",
        messages=[{"role": "user", "content": "Summarize this report."}],
        routing_context={"task_type": "summarization"},
    ),
    # Cache-aware item (E05-F01 compatible)
    LLMRequest(
        request_id="item-3",
        messages=[
            {"role": "system", "content": [{"type": "text", "text": "You are helpful."}]},
            {"role": "user", "content": "What is 2+2?"},
        ],
        provider="anthropic",
        request_options={"requires_prompt_caching": True, "cache_mode": "ephemeral"},
    ),
]

results: list[LLMFanoutResult] = await llm_service.call_llm_many_async(
    requests=requests,
    max_concurrency=4,
)
```

**`LLMRequest` fields**

| Field | Type | Required | Description |
|---|---|---|---|
| `request_id` | `str` | Yes | Unique identifier for this item within the submission. Must be unique across all items in a single call. |
| `messages` | `List[Dict]` | Yes | Messages list in the same shape as `call_llm()`. Supports both plain string content and structured content blocks (E05-F01). |
| `provider` | `Optional[str]` | No | Target provider for direct execution. Ignored when `routing_context` is provided. |
| `model` | `Optional[str]` | No | Model override. Ignored when `routing_context` is provided. |
| `temperature` | `Optional[float]` | No | Temperature override for this item. |
| `routing_context` | `Optional[Dict]` | No | Routing context. When present, routing selects provider and model — same semantics as `call_llm()`. |
| `request_options` | `Dict[str, Any]` | No | Additional keyword arguments forwarded to `call_llm_async()` unchanged. Use for cache-aware fields such as `requires_prompt_caching` and `cache_mode`. |

### `request_id` uniqueness rule

Each `request_id` must be unique within one `call_llm_many_async()` submission. Duplicate `request_id` values cause the entire submission to fail before any provider call begins.

### Concurrency limit (`max_concurrency`)

`max_concurrency` caps the number of in-flight provider calls at any time. Must be an integer >= 1.

- `max_concurrency=1` — fully sequential; no two items execute at the same time.
- `max_concurrency=N` — up to N items execute concurrently.
- The fan-out enforces this cap via `asyncio.Semaphore`; no item bypasses it.

### Result shape

`call_llm_many_async()` returns a `List[LLMFanoutResult]` with the same length and positional order as `requests`. Order is stable even when provider responses arrive out of order.

```python
for result in results:
    if result.status == "succeeded":
        print(f"{result.request_id}: {result.text}")
        if result.usage:
            print(f"  tokens: {result.usage.input_tokens} in / {result.usage.output_tokens} out")
            if result.usage.cache_read_input_tokens:
                print(f"  cache read: {result.usage.cache_read_input_tokens} tokens")
    else:
        print(f"{result.request_id} failed: {result.error.message} ({result.error.error_type})")
```

**`LLMFanoutResult` fields**

| Field | Type | Description |
|---|---|---|
| `request_id` | `str` | The `request_id` from the originating `LLMRequest`. Always present, including on failure. |
| `status` | `str` | `"succeeded"` or `"failed"`. |
| `resolved_provider` | `Optional[str]` | The provider that **actually handled** this item (after routing or fallback tier selection). `None` only when a routing failure occurred before provider resolution. |
| `resolved_model` | `Optional[str]` | The model that **actually handled** this item (after routing or fallback tier selection). `None` only when a routing failure occurred before model resolution. |
| `text` | `Optional[str]` | Response text. Present only on success. |
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

- Pre-execution validation failures (empty submission, duplicate `request_id`, invalid `max_concurrency`) raise `LLMServiceError` before any provider call begins.
- Once execution starts, per-item errors are captured as `LLMFanoutResult` records with `status="failed"`. The submission-level `call_llm_many_async()` call does not re-raise item exceptions.
- Sibling items continue to completion regardless of another item's failure.

**Failure-path resolved identity**

When a fan-out item fails *after* routing or fallback selected a concrete provider and model, the failure record carries that resolved identity:

```python
# Spec requests no specific provider — routing selects anthropic:claude-haiku.
# The call then times out. The failure record still names the provider tried.
request = LLMRequest(
    request_id="routed-item",
    messages=[{"role": "user", "content": "hello"}],
    provider=None,  # routing chooses the provider
    routing_context={"routing_enabled": True},
)
results = await llm_service.call_llm_many_async([request], max_concurrency=1)
r = results[0]
assert r.status == "failed"
assert r.resolved_provider == "anthropic"    # resolved before the failure
assert r.resolved_model == "claude-haiku"    # resolved before the failure
assert r.error.error_type == "LLMTimeoutError"
```

When failure occurs before any provider was selected (e.g., the routing service itself raises), `result.resolved_provider` and `result.resolved_model` remain `None` — they are never fabricated.

This behaviour is implemented via the `LLMResolvedCallError` exception (subclass of `LLMServiceError`). The fan-out layer catches it and extracts the resolved identity. Single-call callers using `call_llm_async()` directly receive `LLMResolvedCallError` propagated unchanged; existing `except LLMServiceError` handlers continue to match.

**`LLMResolvedCallError` attributes**

| Attribute | Type | Description |
|---|---|---|
| `resolved_provider` | `Optional[str]` | The concrete provider that was attempted before the failure. |
| `resolved_model` | `Optional[str]` | The concrete model that was attempted before the failure. |
| `cause` | `BaseException` | The underlying typed exception (e.g. `LLMProviderError`, `LLMTimeoutError`) that triggered the failure. |

```python
requests = [
    LLMRequest(request_id="ok", messages=[...], provider="openai"),
    LLMRequest(request_id="bad-cache", messages=[...], provider="openai",
                request_options={"requires_prompt_caching": True}),
]
results = await llm_service.call_llm_many_async(requests, max_concurrency=2)
# results[0].status == "succeeded"
# results[1].status == "failed"  — unsupported cache mode on this provider
```

### Cache-aware requests (E05-F01 compatibility)

Fan-out items fully support E05-F01 structured message content and cache-aware request options. Pass structured blocks and caching metadata through `request_options` — the fan-out layer forwards them unchanged to `call_llm_async()`:

```python
LLMRequest(
    request_id="cached-system",
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

When a cache-aware item succeeds, the resolved provider and cache usage are both visible on the result — even when routing selected a different model than the request's nominal provider:

```python
result = results[0]  # request_id="cached-system"
assert result.status == "succeeded"
assert result.resolved_provider == "anthropic"           # resolved provider (after any routing)
assert result.resolved_model == "claude-3-haiku"         # resolved model (after any routing)
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

`LLMService` now exposes a provider-agnostic batch surface backed by a
provider-to-adapter registry. Callers submit one `LLMBatchSubmitRequest`,
receive one serializable `LLMBatchHandle`, and drive the lifecycle the same way
for Anthropic, OpenAI, and Gemini.

For the full batch docs, use:

- [LLM Batch User Guide](./llm-batch-user-guide)
- [LLM Batch Adapter Developer Guide](./llm-batch-adapter-developer-guide)

### Batch surface

| Method | Purpose |
|---|---|
| `submit_batch()` / `asubmit_batch()` | Submit a batch and return a serializable `LLMBatchHandle` |
| `restore_batch()` | Rebuild a handle from stored `handle.to_dict()` data |
| `poll_batch()` / `apoll_batch()` | Refresh batch status through the registered provider adapter |
| `cancel_batch()` / `acancel_batch()` | Request cancellation, then re-poll the handle |
| `fetch_batch_results()` / `afetch_batch_results()` | Fetch terminal results as `LLMBatchResult` items |
| `wait_for_batch()` | Async poll loop with capped exponential backoff |
| `submit_and_wait()` | Sync convenience wrapper around submit + wait; not for active event loops |
| `batch_capabilities()` | Report adapter capability metadata for one provider |
| `results_by_request_id()` | Index results by caller `request_id` |
| `reconcile_batch_results()` | Report missing records for submitted `request_id` values |

### Provider capability matrix

| Capability | Anthropic | OpenAI | Gemini Developer API |
|---|---|---|---|
| Registered under canonical provider key | `anthropic` | `openai` | `google` |
| Common aliases accepted by `LLMService` | `claude` | `gpt` | `gemini` |
| Sync lifecycle surface | Yes | Yes | Yes |
| Async lifecycle surface | Yes | Yes | Yes |
| `supports_cancel` | `True` | `True` | `True` |
| Completion window reported by `batch_capabilities()` | `24h` | `24h` | `24h` |
| `partial_fetch` reported by `batch_capabilities()` | `False` | `False` | `False` |
| Result delivery used by the adapter | Provider batch results stream | `output_file_id` file download | Inline responses only |

Gemini-specific constraints:

- Gemini inline batches require a single model across every request in the batch.
- `system` messages are mapped to Gemini `system_instruction`, not `contents`.
- Non-string message content is rejected for Gemini batch submission instead of being stringified.

### Install and registration

Batch SDKs are optional extras:

```bash
pip install "agentmap[batch]"
pip install "agentmap[all]"
```

The `batch` extra installs `anthropic`, `openai`, and `google-genai`. If an SDK
is missing, that adapter raises `LLMDependencyError` at construction time; the
DI container logs the problem and omits that provider from the registry.

### Minimal usage

```python
from agentmap.models.llm_execution import LLMBatchSubmitRequest, LLMRequest

request = LLMBatchSubmitRequest(
    provider="gemini",  # normalized to the canonical registry key "google"
    model="models/gemini-2.5-flash",
    max_tokens=256,
    requests=[
        LLMRequest(
            request_id="job-1",
            messages=[{"role": "user", "content": "Summarize this changelog."}],
        ),
        LLMRequest(
            request_id="job-2",
            messages=[{"role": "user", "content": "List the breaking changes."}],
        ),
    ],
)

handle = llm_service.submit_batch(request)
handle = llm_service.submit_and_wait(request, poll_interval=10.0, timeout=900)
records = llm_service.fetch_batch_results(handle)
```

```python
import asyncio

async def run_batch(request):
    handle = await llm_service.asubmit_batch(request)
    handle = await llm_service.wait_for_batch(
        handle,
        poll_interval=10.0,
        timeout=900,
    )
    return await llm_service.afetch_batch_results(handle)

records = asyncio.run(run_batch(request))
```

`submit_and_wait()` is sync-context only. If you are already inside an event loop,
use `await llm_service.asubmit_batch(...)` plus `await llm_service.wait_for_batch(...)`.

### Status model

Every adapter returns the same normalized `LLMBatchStatus` values:

- `submitted`
- `in_progress`
- `canceling`
- `canceled`
- `ended`
- `expired`
- `failed`

`canceled`, `ended`, `expired`, and `failed` are terminal from the service's
perspective. `restore_batch()` is intentionally network-free; a restored handle
may be stale until you call `poll_batch()` or `apoll_batch()`.

### Core validation rules

- `provider` is batch-level only. Setting `LLMRequest.provider` is rejected.
- Reserved params are centrally resolved before adapter dispatch:
  `model`, `temperature`, `max_tokens`.
- `max_output_tokens` is treated as an alias of `max_tokens`.
- Conflicting values across any supported surface raise
  `LLMBatchParamConflictError`.
- Batch-incompatible params such as `stream=True` and `max_tokens=0` raise
  `LLMServiceError`.

### Batch-specific types

| Type | Purpose |
|---|---|
| `LLMBatchSubmitRequest` | Batch request envelope |
| `LLMRequest` | One caller-owned request inside the batch |
| `LLMBatchHandle` | Serializable lifecycle handle |
| `BatchPollResult` | Adapter-owned normalized poll result |
| `LLMBatchResult` | One terminal result keyed by caller `request_id` |
| `LLMBatchRequestCounts` | Normalized provider request counts snapshot |

### Batch-specific errors

| Exception | Raised when |
|---|---|
| `LLMBatchUnsupportedProviderError` | No adapter is registered for the requested provider |
| `LLMBatchParamConflictError` | A logical parameter is set in conflicting ways |
| `LLMBatchCancelNotSupportedError` | Cancel is requested for a terminal batch, or the adapter does not support cancel |
| `LLMBatchNotReadyError` | Results are fetched before the batch reaches `ended` |
| `LLMBatchExpiredError` | An operation targets an expired handle |
| `LLMBatchResultIntegrityError` | Gemini inline result counts make positional demux unsafe |

### Persistence

`LLMBatchHandle.to_dict()` contains AgentMap-owned metadata only. It does not
store messages, request options, API keys, or provider SDK objects. The default
file-backed repository persists those handle dicts under `llm.batch_dir`.

### Implementation notes

- The adapter registry is assembled in `src/agentmap/di/container_parts/llm.py`.
- `BatchAdapterProtocol` is defined in
  `src/agentmap/services/protocols/service_protocols.py`.
- Canonical parameter resolution lives in
  `src/agentmap/services/llm/_param_resolution.py`.
- The optional dependency decision is documented in
  `docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F04-cross-provider-batch-expansion-and-usage-normaliza/adr-001-batch-optional-deps.md`.

---

## Next Steps

- **[LLM Configuration](../../configuration/llm-config)** — Provider setup, resilience tuning, and routing matrix
- **[Storage Services](./storage-services-overview)** — Data persistence options
- **[Capability Protocols](../capabilities/)** — Agent protocol reference
- **[Agent Development](../agents/custom-agents)** — Build custom LLM agents
