---
sidebar_position: 12
title: OpenTelemetry - Standalone Setup
description: Configure OpenTelemetry tracing and metrics for AgentMap running as a standalone service or CLI tool
keywords: [OpenTelemetry, OTEL, standalone, distributed tracing, observability, Jaeger, Grafana Tempo, Datadog]
---

# OpenTelemetry - Standalone Setup

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>📍 <a href="/docs/intro">AgentMap</a> → <a href="/docs/deployment">Deployment</a> → <strong>OTEL Standalone</strong></span>
</div>

When AgentMap runs as a standalone service (CLI, `agentmap serve`, or serverless handler), it bootstraps its own `TracerProvider` and exports spans to your OTEL-compatible backend. This guide covers installation, configuration, and backend integration.

## Installation

Install AgentMap with the telemetry extras:

```bash
pip install agentmap[telemetry]
```

This adds:
- `opentelemetry-sdk` — TracerProvider, span processors, resource management
- `opentelemetry-exporter-otlp` — OTLP gRPC and HTTP exporters

The base `opentelemetry-api` package (~100KB) is already a required dependency and provides zero-cost no-op behavior when the SDK is not installed.

## Configuration

Add a `telemetry` section to your `agentmap_config.yaml`:

```yaml
# agentmap_config.yaml
telemetry:
  enabled: true

  # Exporter: otlp | console | none
  exporter: "otlp"

  # OTLP collector endpoint
  endpoint: "http://localhost:4317"

  # Protocol: grpc | http/protobuf
  protocol: "grpc"

  # Content capture flags (all default to false for privacy)
  traces:
    agent_inputs: false
    agent_outputs: false
    llm_prompts: false
    llm_responses: false

  # Resource attributes added to all telemetry
  resource:
    service.name: "agentmap"
    deployment.environment: "production"
```

### Configuration Reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable telemetry instrumentation |
| `exporter` | string | `"none"` | Span exporter: `otlp`, `console`, or `none` |
| `endpoint` | string | `"http://localhost:4317"` | OTLP collector endpoint |
| `protocol` | string | `"grpc"` | OTLP transport: `grpc` or `http/protobuf` |
| `traces.agent_inputs` | bool | `false` | Capture agent input values in spans |
| `traces.agent_outputs` | bool | `false` | Capture agent output values in spans |
| `traces.llm_prompts` | bool | `false` | Capture full LLM prompt text in spans |
| `traces.llm_responses` | bool | `false` | Capture full LLM response text in spans |
| `resource.*` | string | — | Custom OTEL resource attributes (all values must be strings) |

## Bootstrap Behavior

When AgentMap starts in standalone mode, the bootstrap process:

1. Reads telemetry config from `agentmap_config.yaml`
2. Checks if a real `TracerProvider` already exists — if so, skips bootstrap (another library or init script already configured one)
3. Creates a `Resource` with your configured attributes plus `agentmap.version`
4. Creates the configured exporter (OTLP gRPC, OTLP HTTP, or console)
5. Sets up a `BatchSpanProcessor` and registers the `TracerProvider` globally

If anything fails during bootstrap (missing SDK, invalid config, network error), AgentMap gracefully degrades to no-op telemetry and logs a warning. Workflow execution is never blocked by telemetry failures.

## Trace Hierarchy

A typical standalone trace:

```
[agentmap.workflow.run] graph=MyWorkflow, nodes=5, duration=3.2s
  ├── [agentmap.agent.run] name=input_node, type=InputAgent, 12ms
  ├── [agentmap.agent.run] name=analyzer, type=LLMAgent, 1.8s
  │     └── [gen_ai.chat] system=anthropic, model=claude-3-sonnet, tokens=1247
  │           └── [agentmap.llm.routing] complexity=MEDIUM, confidence=0.92
  ├── [agentmap.agent.run] name=brancher, type=BranchingAgent, 5ms
  ├── [agentmap.agent.run] name=writer, type=CSVWriterAgent, 45ms
  └── [agentmap.agent.run] name=output, type=DefaultAgent, 2ms
```

### Instrumentation Layers

| Layer | Span Name | Key Attributes |
|-------|-----------|----------------|
| Workflow | `agentmap.workflow.run` | `graph.name`, `graph.node_count`, `graph.duration_ms` |
| Agent | `agentmap.agent.run` | `agent.name`, `agent.type`, `agent.duration_ms`, `agent.success` |
| LLM | `gen_ai.chat` | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |
| LLM Routing | `agentmap.llm.routing` | `routing.complexity`, `routing.confidence`, `routing.provider` |
| Storage | `agentmap.storage.*` | Operation-specific attributes |

All agents (builtin and custom) receive spans automatically through `BaseAgent.run()` instrumentation. No code changes are needed for existing or new agents.

### Metrics

AgentMap emits the following metrics when the SDK is configured:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `agentmap.llm.duration` | Histogram | provider, model | LLM call latency |
| `agentmap.llm.tokens.input` | Counter | provider, model | Input token count |
| `agentmap.llm.tokens.output` | Counter | provider, model | Output token count |
| `agentmap.llm.errors` | Counter | provider, model, error_type | LLM call errors |
| `agentmap.llm.fallback` | Counter | tier | Fallback triggers |
| `agentmap.llm.routing.cache_hit` | Counter | — | Routing cache hits |
| `agentmap.llm.circuit_breaker` | UpDownCounter | — | Open circuit breaker gauge |

## Backend Integration Examples

### Jaeger

```yaml
# agentmap_config.yaml
telemetry:
  enabled: true
  exporter: "otlp"
  endpoint: "http://jaeger:4317"
  protocol: "grpc"
  resource:
    service.name: "agentmap-workflows"
```

```yaml
# docker-compose.yaml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "4317:4317"     # OTLP gRPC
      - "16686:16686"   # Jaeger UI
    environment:
      COLLECTOR_OTLP_ENABLED: "true"

  agentmap:
    build: .
    environment:
      AGENTMAP_CONFIG: /app/agentmap_config.yaml
    depends_on:
      - jaeger
```

### Grafana Tempo

```yaml
# agentmap_config.yaml
telemetry:
  enabled: true
  exporter: "otlp"
  endpoint: "http://tempo:4317"
  protocol: "grpc"
  resource:
    service.name: "agentmap-workflows"
    deployment.environment: "production"
```

### Datadog

```yaml
# agentmap_config.yaml
telemetry:
  enabled: true
  exporter: "otlp"
  endpoint: "http://datadog-agent:4317"
  protocol: "grpc"
  resource:
    service.name: "agentmap-workflows"
    deployment.environment: "production"
```

Datadog's OTLP ingest endpoint accepts standard OTLP traces on port 4317 when configured with `DD_OTLP_CONFIG_RECEIVER_PROTOCOLS_GRPC_ENDPOINT=0.0.0.0:4317`.

### Honeycomb

```yaml
# agentmap_config.yaml
telemetry:
  enabled: true
  exporter: "otlp"
  endpoint: "https://api.honeycomb.io:443"
  protocol: "grpc"
  resource:
    service.name: "agentmap-workflows"
```

Set the Honeycomb API key via the standard OTEL environment variable:

```bash
export OTEL_EXPORTER_OTLP_HEADERS="x-honeycomb-team=YOUR_API_KEY"
```

### Console (Development)

For local development and debugging, use the console exporter to print spans to stdout:

```yaml
# agentmap_config.yaml
telemetry:
  enabled: true
  exporter: "console"
  traces:
    agent_inputs: true
    agent_outputs: true
    llm_prompts: true
    llm_responses: true
```

## Privacy Controls

All content capture is disabled by default. This means that with default settings, no agent inputs/outputs or LLM prompts/responses appear in span attributes — only structural metadata (span names, durations, agent types, token counts).

Enable content capture selectively based on your environment:

```yaml
# Development: full visibility
telemetry:
  enabled: true
  exporter: "console"
  traces:
    agent_inputs: true
    agent_outputs: true
    llm_prompts: true
    llm_responses: true

# Production: structure only, no PII risk
telemetry:
  enabled: true
  exporter: "otlp"
  endpoint: "http://collector:4317"
  traces:
    agent_inputs: false
    agent_outputs: false
    llm_prompts: false
    llm_responses: false
```

## Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY workflows/ ./workflows/
COPY agentmap_config.yaml .
COPY main.py .

EXPOSE 8000
CMD ["python", "main.py"]
```

```txt
# requirements.txt
agentmap[telemetry]
uvicorn
```

## Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agentmap-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: agentmap
  template:
    metadata:
      labels:
        app: agentmap
    spec:
      containers:
      - name: agentmap
        image: your-repo/agentmap:latest
        ports:
        - containerPort: 8000
        env:
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://otel-collector:4317"
        volumeMounts:
        - name: config
          mountPath: /app/agentmap_config.yaml
          subPath: agentmap_config.yaml
      volumes:
      - name: config
        configMap:
          name: agentmap-config
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: agentmap-config
data:
  agentmap_config.yaml: |
    telemetry:
      enabled: true
      exporter: "otlp"
      endpoint: "http://otel-collector:4317"
      protocol: "grpc"
      resource:
        service.name: "agentmap-workflows"
        deployment.environment: "production"
```

## OpenInference Layering

For deeper LangChain-level span visibility, optionally add the OpenInference instrumentor:

```bash
pip install openinference-instrumentation-langchain
```

```python
from openinference.instrumentation.langchain import LangChainInstrumentor

# Enable after AgentMap bootstrap
LangChainInstrumentor().instrument()
```

OpenInference spans appear as children of AgentMap's LLM spans, providing raw LangChain API call details (message content, token counts at the LangChain level). AgentMap does not manage OpenInference — you enable it independently.

## Graceful Degradation

AgentMap's telemetry is designed to never break your application:

- **SDK not installed**: All `tracer.start_as_current_span()` calls become zero-cost no-ops via the `opentelemetry-api` built-in no-op implementation
- **Bootstrap fails**: A warning is logged and execution continues with no-op telemetry
- **Exporter unreachable**: The `BatchSpanProcessor` buffers and retries; span creation is never blocked by export failures
- **Config missing**: Safe defaults are used (telemetry disabled, no content capture)
- **Invalid config values**: A `ConfigurationException` is raised at startup with a clear message about the invalid value

## Troubleshooting

**No spans appearing in backend**
- Verify `telemetry.enabled: true` in config
- Check that `agentmap[telemetry]` extras are installed: `pip list | grep opentelemetry`
- Verify the collector endpoint is reachable from the AgentMap process
- Check AgentMap logs for "Telemetry bootstrap failed" warnings

**Spans appear but metrics are missing**
- Ensure your OTEL collector is configured to receive metrics (port 4317 handles both traces and metrics with gRPC)
- Verify the metrics pipeline is configured in your collector config

**"Telemetry enabled but opentelemetry-sdk is not installed"**
- Install the telemetry extras: `pip install agentmap[telemetry]`

**Config validation errors**
- `exporter` must be one of: `otlp`, `console`, `none`
- `protocol` must be one of: `grpc`, `http/protobuf`
- All `traces.*` flags must be boolean (`true`/`false`)
- All `resource.*` values must be strings

## Next Steps

- **[OpenTelemetry - Embedded Integration](./otel-embedded)**: Use AgentMap's tracing within a host application's existing OTEL setup
- **[Grafana Dashboards](./grafana-dashboards)**: Import pre-built Grafana dashboards for AgentMap LLM metrics and workflow traces
- **[FastAPI Standalone Guide](./fastapi-standalone)**: Deploy AgentMap as a standalone HTTP service
- **[CLI Commands Reference](./cli-commands)**: Run workflows from the command line
