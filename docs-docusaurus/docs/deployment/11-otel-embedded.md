---
sidebar_position: 11
title: OpenTelemetry - Embedded Integration
description: Add AgentMap distributed tracing to your existing host application's OpenTelemetry setup with zero configuration
keywords: [OpenTelemetry, OTEL, embedded, distributed tracing, observability, host application, FastAPI, Django]
---

# OpenTelemetry - Embedded Integration

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>OTEL Embedded</strong></span>
</div>

When AgentMap is embedded in a host application (FastAPI, Django, or any Python service), its OpenTelemetry spans automatically nest inside your existing traces. No AgentMap-side configuration is required — AgentMap discovers the host's `TracerProvider` at runtime.

## How It Works

AgentMap uses `opentelemetry-api` as a required dependency. The `OTELTelemetryService` calls `trace.get_tracer("agentmap")`, which automatically participates in whatever `TracerProvider` is already configured in the process. When your host application creates a span (e.g., an HTTP request handler), AgentMap's workflow and agent spans appear as children of that span.

**Golden rule**: AgentMap never configures the global `TracerProvider` when embedded. Your host application owns the tracing infrastructure.

```
[host.api.request] POST /analyze                    ← Host span
  └── [agentmap.workflow.run] graph=MyWorkflow       ← AgentMap root span
        ├── [agentmap.agent.run] name=input_node, type=InputAgent
        ├── [agentmap.agent.run] name=analyzer, type=LLMAgent
        │     └── [gen_ai.chat] system=anthropic, model=claude-3-sonnet
        │           └── [agentmap.llm.routing] complexity=MEDIUM
        ├── [agentmap.agent.run] name=brancher, type=BranchingAgent
        ├── [agentmap.agent.run] name=writer, type=CSVWriterAgent
        └── [agentmap.agent.run] name=output, type=DefaultAgent
```

## Prerequisites

Your host application must have a `TracerProvider` configured before AgentMap workflows execute. AgentMap requires only the API package (already included as a dependency):

```bash
# AgentMap already includes opentelemetry-api (~100KB)
# Your host application provides the SDK and exporters
pip install opentelemetry-sdk opentelemetry-exporter-otlp
```

## FastAPI Integration Example

```python
# main.py
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from agentmap.services.fastapi import include_agentmap_routes

# 1. Configure YOUR TracerProvider (host owns this)
resource = Resource.create({
    "service.name": "my-api-service",
    "deployment.environment": "production",
})
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://jaeger:4317"))
)
trace.set_tracer_provider(provider)

# 2. Create and instrument your FastAPI app
app = FastAPI(title="My Service")
FastAPIInstrumentor.instrument_app(app)

# 3. Add AgentMap routes — spans auto-nest under host spans
include_agentmap_routes(app, prefix="/workflows")

@app.post("/analyze")
async def analyze(data: dict):
    # Any AgentMap workflow called here will produce child spans
    # under the FastAPI request span
    from agentmap import runtime_api
    result = runtime_api.run_workflow("AnalysisWorkflow", data)
    return {"result": result}
```

Every call to `run_workflow()` within a request handler produces spans nested under the FastAPI request span. No AgentMap configuration needed.

## Django Integration Example

```python
# settings.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

resource = Resource.create({
    "service.name": "my-django-service",
    "deployment.environment": "production",
})
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://tempo:4317"))
)
trace.set_tracer_provider(provider)


# views.py
from agentmap import runtime_api

def process_order(request):
    # AgentMap spans appear as children of the Django request span
    result = runtime_api.run_workflow("OrderProcessing", {
        "order_id": request.POST["order_id"],
    })
    return JsonResponse(result)
```

## Generic Python Application

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# Configure host TracerProvider
resource = Resource.create({"service.name": "my-service"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317"))
)
trace.set_tracer_provider(provider)

# Use AgentMap — spans auto-nest
from agentmap import runtime_api

tracer = trace.get_tracer("my-service")

with tracer.start_as_current_span("batch-job") as span:
    # AgentMap workflow spans become children of "batch-job"
    result = runtime_api.run_workflow("DataPipeline", {"source": "s3://bucket"})
    span.set_attribute("workflow.result", str(result.get("success")))
```

## Enabling Content Capture

By default, AgentMap does not capture agent inputs/outputs or LLM prompts/responses in span attributes (privacy-safe defaults). To opt in, add a `telemetry` section to your `agentmap_config.yaml`:

```yaml
# agentmap_config.yaml
telemetry:
  enabled: true

  # Content capture flags (all default to false)
  traces:
    agent_inputs: true      # Capture agent input values
    agent_outputs: true     # Capture agent output values
    llm_prompts: false      # Capture full LLM prompt text
    llm_responses: false    # Capture full LLM response text
```

In embedded mode, the `exporter`, `endpoint`, and `protocol` settings are ignored — the host's `TracerProvider` handles span export. Only `enabled` and `traces` settings are relevant.

## Instrumentation Layers

AgentMap instruments three layers automatically:

| Layer | Span Name | Key Attributes |
|-------|-----------|----------------|
| Workflow | `agentmap.workflow.run` | `graph.name`, `graph.node_count`, `graph.duration_ms` |
| Agent | `agentmap.agent.run` | `agent.name`, `agent.type`, `agent.duration_ms`, `agent.success` |
| LLM | `gen_ai.chat` | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |
| LLM Routing | `agentmap.llm.routing` | `routing.complexity`, `routing.confidence`, `routing.provider` |
| Storage | `agentmap.storage.*` | Operation-specific attributes |

All spans are created automatically — no code changes to your agents or workflows.

## Metrics

When the OTEL SDK is configured, AgentMap also emits metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `agentmap.llm.duration` | Histogram | LLM call latency by provider/model |
| `agentmap.llm.tokens.input` | Counter | Input tokens by provider/model |
| `agentmap.llm.tokens.output` | Counter | Output tokens by provider/model |
| `agentmap.llm.errors` | Counter | LLM errors by provider/model/type |
| `agentmap.llm.fallback` | Counter | Fallback triggers by tier |

## Layering with OpenInference

For deeper LangChain-level visibility, you can optionally add the OpenInference LangChain instrumentor. It layers underneath AgentMap's spans:

```python
# Optional: Add OpenInference for raw LangChain call visibility
pip install openinference-instrumentation-langchain
```

```python
from openinference.instrumentation.langchain import LangChainInstrumentor

# Enable OpenInference (uses the same TracerProvider)
LangChainInstrumentor().instrument(tracer_provider=provider)
```

The resulting trace hierarchy:

```
[host.api.request] POST /analyze
  └── [agentmap.workflow.run] graph=MyWorkflow
        └── [agentmap.agent.run] name=analyzer, type=LLMAgent
              └── [gen_ai.chat] system=anthropic, model=claude-3-sonnet
                    └── [agentmap.llm.routing] complexity=MEDIUM
                          └── [LLM] model=claude-3-sonnet  ← OpenInference span
```

AgentMap does not manage OpenInference — you enable it independently and it shares the same trace context.

## Zero-Cost When Disabled

If your host application does not configure a `TracerProvider`, all AgentMap instrumentation becomes a zero-cost no-op automatically. The `opentelemetry-api` package returns built-in no-op tracers and meters when no SDK is configured. No conditional guards are needed anywhere in your code.

## Troubleshooting

**AgentMap spans not appearing in traces**
- Verify your host `TracerProvider` is set before AgentMap workflows execute
- Check that `telemetry.enabled` is `true` in `agentmap_config.yaml`
- Ensure the OTEL SDK is installed: `pip install opentelemetry-sdk`

**Spans appear but have no content attributes**
- Content capture is disabled by default for privacy. Enable specific flags in `traces` config.

**AgentMap bootstraps its own TracerProvider**
- This only happens when AgentMap detects no real `TracerProvider` (i.e., only the default `ProxyTracerProvider` exists). Ensure your host configures its provider before AgentMap's DI container initializes.

## Next Steps

- **[OpenTelemetry - Standalone Setup](./otel-standalone)**: Configure AgentMap as a standalone service with its own OTEL exporters
- **[FastAPI Integration Guide](./fastapi-integration)**: Embed AgentMap into existing FastAPI apps
- **[FastAPI Standalone Guide](./fastapi-standalone)**: Deploy AgentMap as a standalone HTTP service
