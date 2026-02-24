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

## Routing System

### Activity vs Task Type

| Concept | Config key | Evaluated | Purpose |
|---|---|---|---|
| `activity` | `routing.activities` | **First** | Explicit per-activity routing plan: primary provider/model + fallbacks per complexity tier |
| `task_type` | `routing.task_types` | Fallback | General classification; drives provider preference and complexity keyword detection |

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

| Exception | When raised |
|---|---|
| `LLMConfigurationError` | Bad API key, auth failure, model config error |
| `LLMDependencyError` | Missing provider package (e.g. `anthropic` not installed) |
| `LLMProviderError` | Provider-level errors |
| `LLMServiceError` | General service errors, routing failure |

```python
from agentmap.exceptions import LLMServiceError, LLMConfigurationError

try:
    response = llm_service.call_llm(provider="anthropic", messages=messages)
except LLMConfigurationError:
    # Bad API key, invalid config
    raise
except LLMServiceError as e:
    # Routing failure, general service error
    self.log_error(f"LLM call failed: {e}")
    raise
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

## Best Practices

1. **Store API keys in environment variables** — never hardcode them.
2. **Use routing for complex pipelines** — activities give you explicit control; task_types offer keyword-driven automation.
3. **Use `ask()` for quick one-off prompts** — only reach for `call_llm()` when you need messages, routing, or model overrides.
4. **Cap complexity tier with `max_cost_tier`** — prevents accidentally routing simple tasks to expensive models.
5. **Keep conversation history reasonable** — 10–20 messages is a good ceiling; trim older messages when memory grows.

---

## Next Steps

- **[Storage Services](./storage-services-overview)** — Data persistence options
- **[Capability Protocols](../capabilities/)** — Agent protocol reference
- **[Agent Development](../agents/custom-agents)** — Build custom LLM agents
