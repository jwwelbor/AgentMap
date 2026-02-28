---
title: LLM Configuration
sidebar_position: 3
description: Configure LLM providers, resilience (retry and circuit breaker), and the routing matrix in agentmap_config.yaml.
keywords: [LLM configuration, providers, retry, circuit breaker, resilience, routing matrix]
---

# LLM Configuration

All LLM settings live under the `llm:` and `routing:` sections of `agentmap_config.yaml`. Run `agentmap init-config` to generate a template with all options.

---

## Provider Setup

Configure one or more LLM providers. Each provider needs an API key and a default model:

```yaml
llm:
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-sonnet-4-6"
    temperature: 0.7

  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4.1-mini"
    temperature: 0.7

  google:
    api_key: "${GOOGLE_API_KEY}"
    model: "gemini-2.5-flash"
    temperature: 0.5
```

- `api_key` — use `${ENV_VAR}` syntax to reference environment variables (recommended) or set directly
- `model` — default model used when no override is specified in `call_llm()`, CSV context, or matrix configuration
- `temperature` — default creativity (0.0 = deterministic, 1.0 = creative)
- Only providers with a valid API key are available at runtime. Check with `llm_service.get_available_providers()`

Note: Store API keys in environment variables, never in the config file. See [Environment Variables](./environment-variables) for setup instructions.

---

## Resilience

Every LLM call is automatically protected by retry with exponential backoff and a circuit breaker. Configure under `llm.resilience`:

```yaml
llm:
  # ... provider config above ...

  resilience:
    retry:
      max_attempts: 3          # retries per provider:model call
      backoff_base: 2.0        # exponential backoff: 1s, 2s, 4s...
      backoff_max: 30.0        # cap on backoff delay (seconds)
      jitter: true             # randomize delay to avoid thundering herd
    circuit_breaker:
      failure_threshold: 5     # failures before circuit opens for a provider:model
      reset_timeout: 60        # seconds before half-open (allows one retry)
```

### How retries work

When a transient error occurs (rate limit, timeout, server error), the call is retried up to `max_attempts` times. Each retry waits longer than the last (exponential backoff). Non-transient errors — bad API key, invalid model, missing package — fail immediately without retrying.

| Error type | Example | Retried? |
|---|---|---|
| Rate limit (429) | Too many requests, quota exceeded | Yes |
| Timeout / connection | Server unreachable, connection reset, 502/503/504 | Yes |
| Authentication | Invalid API key, permission denied | No |
| Configuration | Model not found, invalid model | No |
| Missing dependency | `anthropic` package not installed | No |

### How the circuit breaker works

The circuit breaker tracks failures per provider:model pair (e.g., `anthropic:claude-sonnet-4-6`):

1. **Closed** (normal) — calls go through normally
2. **Open** — after `failure_threshold` consecutive failures, the circuit opens. Subsequent calls fail immediately without contacting the provider, returning a `LLMProviderError`
3. **Half-open** — after `reset_timeout` seconds, one call is allowed through. If it succeeds, the circuit closes. If it fails, the circuit re-opens

This prevents wasting time and quota on a provider that is down.

### Tuning tips

- **High-throughput applications**: Lower `failure_threshold` (e.g., 3) to open the circuit faster and reduce wasted calls
- **Latency-sensitive applications**: Lower `max_attempts` (e.g., 2) and `backoff_max` (e.g., 10) to fail faster
- **Cost-sensitive applications**: Keep defaults — retries help avoid unnecessary fallback to more expensive providers
- **Disable retries**: Set `max_attempts: 1` (not recommended for production)

---

## Routing Matrix

The routing matrix maps each provider and complexity level to a specific model. It is used by the routing system and the tiered fallback strategy:

```yaml
routing:
  enabled: true

  routing_matrix:
    anthropic:
      low: "claude-haiku-4-5-20251001"
      medium: "claude-sonnet-4-6"
      high: "claude-sonnet-4-6"
      critical: "claude-opus-4-6"

    openai:
      low: "gpt-4o-mini"
      medium: "gpt-4.1-mini"
      high: "gpt-4.1"
      critical: "o3"

    google:
      low: "gemini-2.5-flash-lite"
      medium: "gemini-2.5-flash"
      high: "gemini-2.5-pro"
      critical: "gemini-2.5-pro"
```

The matrix serves two purposes:
1. **Routing**: When using `routing_context` in `call_llm()`, the router picks the model matching the detected complexity
2. **Fallback**: When a call fails, the fallback system uses the matrix to find a lower-complexity model to try

### Fallback behavior

When a call fails after all retries are exhausted, the fallback system tries these tiers in order:

| Tier | Strategy | Example |
|---|---|---|
| 1 | Same provider, `low` complexity model from the matrix | `anthropic:claude-opus-4-6` → `anthropic:claude-haiku-4-5` |
| 2 | Configured fallback provider (`routing.fallback.default_provider`) | Switch to `openai:gpt-4o-mini` |
| 3 | Emergency — first available provider not yet tried | Try `google:gemini-2.5-flash-lite` |
| 4 | All fallbacks exhausted — raises `LLMServiceError` | — |

Configure the default fallback provider:

```yaml
routing:
  fallback:
    default_provider: "anthropic"
    default_model: "claude-haiku-4-5-20251001"
    retry_with_lower_complexity: true
```

Note: Configuration errors (bad API key) and dependency errors (missing package) skip fallback entirely — only transient provider errors trigger fallback.

---

## Task Types

AgentMap offers two approaches to control which LLM model handles a request. **Task types** provide soft guidance — they influence provider preference and help detect complexity from prompt keywords, but the final model is looked up from the routing matrix. **Activities** provide hard control — they pin exact provider:model pairs per complexity tier, bypassing the matrix entirely.

Most users need only one approach. Use task types when you want the system to pick the best model for you. Use activities when you need deterministic model selection.

Task types influence which provider is preferred and how prompt complexity is detected. Define them under `routing.task_types`:

```yaml
routing:
  task_types:
    general:
      description: "General purpose tasks and queries"
      provider_preference: ["anthropic", "openai", "google"]
      default_complexity: "medium"
      complexity_keywords:
        low: ["simple", "basic", "quick", "summarize"]
        medium: ["analyze", "process", "standard", "explain"]
        high: ["complex", "detailed", "comprehensive", "advanced"]
        critical: ["urgent", "critical", "important", "emergency"]

    code_generation:
      description: "Writing, refactoring, or debugging code"
      provider_preference: ["anthropic", "openai"]
      default_complexity: "high"
      complexity_keywords:
        low: ["comment", "format", "simple function"]
        medium: ["implement", "refactor", "debug"]
        high: ["architecture", "system design", "complex algorithm"]
        critical: ["security critical", "performance critical", "production"]

    customer_support:
      description: "Customer service, support tickets, FAQs"
      provider_preference: ["anthropic", "openai"]
      default_complexity: "low"
      complexity_keywords:
        low: ["faq", "simple question", "basic support"]
        medium: ["troubleshooting", "detailed question"]
        high: ["complex issue", "escalation", "technical"]
        critical: ["urgent", "vip customer", "critical issue"]
```

| Field | Purpose |
|---|---|
| `description` | Human-readable label (optional) |
| `provider_preference` | Ordered list of preferred providers for this task type |
| `default_complexity` | Complexity tier used when auto-detection finds no signal |
| `complexity_keywords` | Keywords in the prompt that bump the complexity tier up or down |

At runtime:

- Set `task_type` in the routing context (CSV context or `call_llm()` call)
- The routing system scans the prompt for `complexity_keywords` to determine the complexity tier
- If no keywords match, `default_complexity` is used
- The `provider_preference` list determines which provider is tried first
- The final model is looked up from the `routing_matrix` using the chosen provider + complexity tier

```python
# In a host application
response = llm_service.call_llm(
    messages=[{"role": "user", "content": "Debug this null pointer exception"}],
    routing_context={"task_type": "code_generation"},
)
# → detects "debug" keyword → medium complexity
# → prefers anthropic → picks claude-sonnet-4-6 from routing_matrix
```

```csv
# In a CSV workflow
workflow,node,description,type,next_node,error_node,input_fields,output_field,prompt,context
Support,Respond,Handle ticket,llm,Done,Error,ticket,reply,You are a support agent,"{""routing_context"": {""task_type"": ""customer_support""}}"
```

Note: You can define your own task types — just add entries under `routing.task_types` with the same structure.

---

## Activities

Activities provide explicit control over exactly which provider and model are used for each complexity tier. Unlike task types (which influence the routing matrix lookup), activities bypass the matrix entirely and pin specific provider:model pairs.

```yaml
routing:
  activities:
    code_generation:
      low:
        primary:
          provider: "anthropic"
          model: "claude-haiku-4-5-20251001"
        fallbacks:
          - provider: "openai"
            model: "gpt-4o-mini"
      medium:
        primary:
          provider: "anthropic"
          model: "claude-sonnet-4-6"
        fallbacks:
          - provider: "openai"
            model: "gpt-4.1-mini"
      high:
        primary:
          provider: "anthropic"
          model: "claude-sonnet-4-6"
        fallbacks:
          - provider: "openai"
            model: "gpt-4.1"
      critical:
        primary:
          provider: "openai"
          model: "o3"
        fallbacks:
          - provider: "anthropic"
            model: "claude-opus-4-6"

    customer_support:
      any:
        primary:
          provider: "anthropic"
          model: "claude-haiku-4-5-20251001"
        fallbacks:
          - provider: "openai"
            model: "gpt-4o-mini"
```

- Each activity maps complexity tiers to explicit primary + fallback provider:model pairs
- Use `any` instead of individual tiers when you want the same model regardless of complexity
- `fallbacks` is optional — if the primary fails, these are tried in order
- Activities take priority over task types. When both `activity` and `task_type` are set, `activity` is evaluated first

Activities use the same complexity tiers (`low`, `medium`, `high`, `critical`) as the routing matrix, but instead of looking up a model from the matrix, they specify exact provider:model pairs. Use the `any` tier when the same model should handle all complexity levels.

```python
# Approach 1: Task type — system picks the model
response = llm_service.call_llm(
    messages=messages,
    routing_context={"task_type": "code_generation"},
)
# "debug" in the prompt → medium complexity → anthropic preferred
# → picks claude-sonnet-4-6 from routing_matrix

# Approach 2: Activity — you pick the model
response = llm_service.call_llm(
    messages=messages,
    routing_context={
        "activity": "code_generation",
        "complexity_override": "high",
    },
)
# → uses exactly anthropic:claude-sonnet-4-6 (the primary for code_generation:high)
# → if it fails, tries openai:gpt-4.1 (the configured fallback)
```

### Choosing between task types and activities

These are **alternative approaches**, not layers you need to stack:

| Approach | How it works | Best for |
|---|---|---|
| **Task types only** | You set provider preferences and complexity keywords. The routing matrix picks the model. | Most applications — simple setup, automatic model selection |
| **Activities only** | You pin exact provider:model pairs per complexity tier. Pass `complexity_override` to set the tier directly. | Workloads where you need a specific model every time |
| **Both** | Task type provides complexity keyword detection; activity pins the model for the detected tier. | Advanced — when you want keyword-based complexity detection AND pinned models |

If you're unsure, start with task types. Add activities later only if you need to lock down specific models.

When both are set with the same name (e.g., `task_type: "code_generation"` and `activity: "code_generation"`), the activity controls model selection and the task type is only used for its complexity keywords. If you also pass `complexity_override`, the task type has no effect at all.

---

## Complete Example

A production-ready LLM configuration with all options:

```yaml
llm:
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-sonnet-4-6"
    temperature: 0.7

  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4.1-mini"
    temperature: 0.7

  google:
    api_key: "${GOOGLE_API_KEY}"
    model: "gemini-2.5-flash"
    temperature: 0.5

  resilience:
    retry:
      max_attempts: 3
      backoff_base: 2.0
      backoff_max: 30.0
      jitter: true
    circuit_breaker:
      failure_threshold: 5
      reset_timeout: 60

routing:
  enabled: true

  routing_matrix:
    anthropic:
      low: "claude-haiku-4-5-20251001"
      medium: "claude-sonnet-4-6"
      high: "claude-sonnet-4-6"
      critical: "claude-opus-4-6"
    openai:
      low: "gpt-4o-mini"
      medium: "gpt-4.1-mini"
      high: "gpt-4.1"
      critical: "o3"
    google:
      low: "gemini-2.5-flash-lite"
      medium: "gemini-2.5-flash"
      high: "gemini-2.5-pro"
      critical: "gemini-2.5-pro"

  fallback:
    default_provider: "anthropic"
    default_model: "claude-haiku-4-5-20251001"
    retry_with_lower_complexity: true
```

---

## Next Steps

- **[LLM Service Reference](../reference/services/llm-service)** — API usage, error handling, and code examples
- **[Main Configuration](./main-config)** — Memory, execution, logging, and other settings
- **[Environment Variables](./environment-variables)** — Secure API key management
