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
    model: "claude-3-5-sonnet-20241022"
    temperature: 0.7
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o"
    temperature: 0.7
  google:
    api_key: "${GOOGLE_API_KEY}"
    model: "gemini-1.5-pro"
    temperature: 0.5
```

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
    model="claude-3-5-sonnet-20241022",  # optional override
    temperature=0.2,                      # optional override
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
    routing_context={"task_type": "code_generation", "model_override": "claude-3-5-sonnet-20241022"}
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
| 1 | Same provider, lower-complexity model from routing matrix | `anthropic:claude-3-opus` → `anthropic:claude-3-haiku` |
| 2 | Configured fallback provider (`routing.fallback.default_provider`) | Switch to `openai:gpt-3.5-turbo` |
| 3 | Emergency — first available provider not yet tried | Try `google:gemini-1.5-flash` |
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
# "debug" in prompt → medium complexity → anthropic preferred → claude-3-5-sonnet
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
# → anthropic:claude-sonnet-4 (primary for code_generation:high)
# → falls back to openai:gpt-4o if primary fails
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
from agentmap.exceptions import (
    LLMServiceError,
    LLMConfigurationError,
    LLMDependencyError,
    LLMRateLimitError,
    LLMTimeoutError,
)

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
ChatBot,Chat,Chat with AI,llm,Chat,Error,message,response,You are a helpful assistant,"{""provider"": ""anthropic"", ""model"": ""claude-3-5-sonnet-20241022"", ""temperature"": 0.7}"
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
#         "open_circuits": ["anthropic:claude-3-opus"],
#         "failure_counts": {"anthropic:claude-3-opus": 5}
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

## Next Steps

- **[LLM Configuration](../../configuration/llm-config)** — Provider setup, resilience tuning, and routing matrix
- **[Storage Services](./storage-services-overview)** — Data persistence options
- **[Capability Protocols](../capabilities/)** — Agent protocol reference
- **[Agent Development](../agents/custom-agents)** — Build custom LLM agents
