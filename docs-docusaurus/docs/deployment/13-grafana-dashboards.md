---
sidebar_position: 13
title: "Grafana Dashboards"
description: "Import pre-built Grafana dashboards for AgentMap LLM metrics, workflow traces, and cost estimation"
keywords: [Grafana, dashboards, Prometheus, Tempo, OTEL, metrics, observability, LLM monitoring]
---

# Grafana Dashboards

<div style={{marginBottom: '1rem', fontSize: '0.9rem', color: '#666'}}>
  <span>AgentMap > Deployment > <strong>Grafana Dashboards</strong></span>
</div>

AgentMap ships two pre-built Grafana dashboard templates that visualize LLM operation metrics, workflow execution traces, and estimated costs. The dashboards connect to Prometheus (for metrics) and Tempo (for traces) and require no code changes to AgentMap — only that telemetry is enabled.

## Prerequisites

### Infrastructure

- **Grafana 10+** (dashboards use schemaVersion 39+ features)
- **Prometheus-compatible datasource** receiving OTEL metrics from the collector
- **Tempo-compatible datasource** receiving OTEL traces (optional — required only for the Workflow Explorer dashboard)
- **OpenTelemetry Collector** configured to receive AgentMap telemetry and export to Prometheus and Tempo

The LLM Operations dashboard requires only Prometheus. The Workflow Explorer dashboard requires both Prometheus and Tempo.

### AgentMap Configuration

Install AgentMap with telemetry extras:

```bash
pip install agentmap[telemetry]
```

Enable telemetry in your `agentmap_config.yaml`:

```yaml
telemetry:
  enabled: true
  exporter: "otlp"
  endpoint: "http://localhost:4317"
  protocol: "grpc"
```

## Quick Start

Import the dashboards via the Grafana UI in under 5 minutes:

1. Clone or download the dashboard JSON files from the repository's `dashboards/grafana/` directory:
   - `agentmap-llm-operations.json`
   - `agentmap-workflow-explorer.json`
2. Open your Grafana instance in a browser.
3. Navigate to **Dashboards** in the left sidebar.
4. Click **New** > **Import**.
5. Click **Upload dashboard JSON file** and select one of the JSON files.
6. When prompted, select your Prometheus datasource (and Tempo datasource for the Workflow Explorer).
7. Click **Import** to finish.
8. Repeat steps 4-7 for the second dashboard.

This works on both self-hosted Grafana and Grafana Cloud.

## Provisioning Setup

### Self-Hosted Grafana

For automated deployment via Grafana's provisioning system (infrastructure-as-code), use the files in `dashboards/grafana/provisioning/`:

- `dashboards/grafana/provisioning/datasources.yaml` — Prometheus and Tempo datasource definitions
- `dashboards/grafana/provisioning/dashboards.yaml` — Dashboard provider configuration

Mount these into the standard Grafana provisioning directories using Docker volumes:

```yaml
services:
  grafana:
    image: grafana/grafana:latest
    volumes:
      # Datasource provisioning
      - ./dashboards/grafana/provisioning/datasources.yaml:/etc/grafana/provisioning/datasources/agentmap-datasources.yaml
      # Dashboard provisioning config
      - ./dashboards/grafana/provisioning/dashboards.yaml:/etc/grafana/provisioning/dashboards/agentmap-dashboards.yaml
      # Dashboard JSON files
      - ./dashboards/grafana/agentmap-llm-operations.json:/var/lib/grafana/dashboards/agentmap/agentmap-llm-operations.json
      - ./dashboards/grafana/agentmap-workflow-explorer.json:/var/lib/grafana/dashboards/agentmap/agentmap-workflow-explorer.json
    ports:
      - "3000:3000"
```

The dashboard provisioning config uses `disableDeletion: false` by default. To prevent accidental deletion of provisioned dashboards, set `disableDeletion: true` in `dashboards.yaml`:

```yaml
providers:
  - name: AgentMap
    disableDeletion: true
    options:
      path: /var/lib/grafana/dashboards/agentmap
```

Update the datasource URLs in `datasources.yaml` to match your actual Prometheus and Tempo endpoints. The defaults (`http://prometheus:9090` and `http://tempo:3200`) are placeholders.

### Grafana Cloud Note

Grafana Cloud does not support file-based provisioning. Use the UI import method described in Quick Start, or use the [Grafana HTTP API](https://grafana.com/docs/grafana/latest/developers/http_api/dashboard/) to import dashboards programmatically.

## Dashboard Overview

### LLM Operations Dashboard

**File**: `agentmap-llm-operations.json`
**Datasource**: Prometheus only

| Row | Panels | Description |
|-----|--------|-------------|
| Overview | 4 | Total LLM calls, total tokens, error rate, average latency |
| Latency | 2 | P50/P95/P99 latency by provider and latency heatmap |
| Token Usage | 3 | Input/output token rates, cumulative token counts, tokens by model |
| Errors & Reliability | 3 | Error rate by type, error breakdown by provider, circuit breaker state |
| Routing Intelligence | 2 | Cache hit ratio and fallback events by tier |
| Cost Estimation | 2 | Estimated cost rate and total estimated cost using configurable per-token rates |

### Workflow & Trace Explorer Dashboard

**File**: `agentmap-workflow-explorer.json`
**Datasource**: Prometheus and Tempo

| Row | Panels | Description |
|-----|--------|-------------|
| Workflow Overview | 2 | Workflow execution rate and average duration (requires spanmetrics connector) |
| Agent Breakdown | 2 | Agent execution counts and duration by agent type (requires spanmetrics connector) |
| Storage Operations | 2 | Storage read/write rates and duration by backend (requires spanmetrics connector) |
| Trace Search | 2 | Tempo trace search panel and trace detail viewer |
| Service Graph | 2 | Node graph and service dependency map |

:::note
The Workflow Overview, Agent Breakdown, and Storage Operations rows require the OTEL Collector's **spanmetrics connector** to generate Prometheus metrics from trace data. Without it, these panels show "No data" but the Trace Search and Service Graph panels still function.
:::

## Metrics Reference

All metric names are defined in `src/agentmap/services/telemetry/constants.py` and translated to Prometheus names by the OTEL Collector's Prometheus exporter.

| OTEL Metric Name | Type | Prometheus Name | Dimensions |
|---|---|---|---|
| `agentmap.llm.duration` | Histogram | `agentmap_llm_duration_seconds` (`_bucket`, `_sum`, `_count`) | `provider`, `model` |
| `agentmap.llm.tokens.input` | Counter | `agentmap_llm_tokens_input_total` | `provider`, `model` |
| `agentmap.llm.tokens.output` | Counter | `agentmap_llm_tokens_output_total` | `provider`, `model` |
| `agentmap.llm.errors` | Counter | `agentmap_llm_errors_total` | `provider`, `model`, `error_type` |
| `agentmap.llm.routing.cache_hit` | Counter | `agentmap_llm_routing_cache_hit_total` | (none) |
| `agentmap.llm.circuit_breaker` | UpDownCounter | `agentmap_llm_circuit_breaker` | (none) |
| `agentmap.llm.fallback` | Counter | `agentmap_llm_fallback_total` | `tier` |

### Metric Dimensions

| Dimension | Constant | Value | Applied To |
|---|---|---|---|
| Provider | `METRIC_DIM_PROVIDER` | `provider` | `agentmap.llm.duration`, `agentmap.llm.tokens.input`, `agentmap.llm.tokens.output`, `agentmap.llm.errors` |
| Model | `METRIC_DIM_MODEL` | `model` | `agentmap.llm.duration`, `agentmap.llm.tokens.input`, `agentmap.llm.tokens.output`, `agentmap.llm.errors` |
| Error Type | `METRIC_DIM_ERROR_TYPE` | `error_type` | `agentmap.llm.errors` |
| Tier | `METRIC_DIM_TIER` | `tier` | `agentmap.llm.fallback` |

**Note**: `agentmap.llm.routing.cache_hit` and `agentmap.llm.circuit_breaker` have no dimensions. PromQL queries for these metrics must not include `provider` or `model` label filters.

## Span Reference

All span names are defined in `src/agentmap/services/telemetry/constants.py`.

| Span Name | Constant | Key Attributes |
|---|---|---|
| `agentmap.workflow.run` | `WORKFLOW_RUN_SPAN` | `agentmap.graph.name`, `agentmap.graph.node_count`, `agentmap.graph.agent_count` |
| `agentmap.agent.run` | `AGENT_RUN_SPAN` | `agentmap.agent.name`, `agentmap.agent.type`, `agentmap.node.name` |
| `gen_ai.chat` | `LLM_CALL_SPAN` | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |
| `agentmap.storage.read` | `STORAGE_READ_SPAN` | `agentmap.storage.backend`, `agentmap.storage.operation`, `agentmap.storage.record_count` |
| `agentmap.storage.write` | `STORAGE_WRITE_SPAN` | `agentmap.storage.backend`, `agentmap.storage.operation`, `agentmap.storage.record_count` |

## OTEL Collector Configuration

### Add to Existing Collector

If you already run an OTEL Collector, add these components to your existing configuration:

**Receivers** — ensure you have an OTLP receiver:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"
```

**Exporters** — add Prometheus and Tempo exporters:

```yaml
exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
    resource_to_telemetry_conversion:
      enabled: true
  otlp/tempo:
    endpoint: "tempo:4317"
    tls:
      insecure: true
```

**Connectors** — add the spanmetrics connector (required for Workflow Explorer metric panels):

```yaml
connectors:
  spanmetrics:
    namespace: "span"
    dimensions:
      - name: "agentmap.graph.name"
      - name: "agentmap.agent.type"
      - name: "agentmap.storage.backend"
```

**Pipelines** — add or extend your traces and metrics pipelines:

```yaml
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/tempo, spanmetrics]
    metrics:
      receivers: [otlp, spanmetrics]
      processors: [batch]
      exporters: [prometheus]
```

The `spanmetrics` connector appears as an exporter in the `traces` pipeline and as a receiver in the `metrics` pipeline. This is how OTEL Collector connectors bridge pipeline types.

:::caution
The example uses `tls.insecure: true` for local development. Production deployments should configure proper TLS certificates for the Tempo exporter endpoint.
:::

### Complete Standalone Configuration

For greenfield deployments, use this complete collector configuration:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: "0.0.0.0:4317"

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024

exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
    resource_to_telemetry_conversion:
      enabled: true
  otlp/tempo:
    endpoint: "tempo:4317"
    tls:
      insecure: true

connectors:
  spanmetrics:
    namespace: "span"
    dimensions:
      - name: "agentmap.graph.name"
      - name: "agentmap.agent.type"
      - name: "agentmap.storage.backend"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/tempo, spanmetrics]
    metrics:
      receivers: [otlp, spanmetrics]
      processors: [batch]
      exporters: [prometheus]
```

## Customization

### Cost Variables

The LLM Operations dashboard includes cost estimation panels that calculate estimated LLM spend using configurable per-token rates. The two template variables are:

- **`cost_per_input_token`** — cost per input token in USD (default: `0.000003`)
- **`cost_per_output_token`** — cost per output token in USD (default: `0.000015`)

To update these values:

1. Open the LLM Operations dashboard.
2. Click the **Cost per Input Token ($)** dropdown at the top of the dashboard.
3. Enter your actual rate (e.g., `0.00001` for $0.01 per 1000 tokens).
4. Repeat for **Cost per Output Token ($)**.

Different providers and models have different pricing. The cost panels apply a single rate across all providers. For per-model pricing, fork the dashboard and create separate cost panels per model.

### Provider and Model Filtering

The `provider` and `model` template variables are multi-value dropdowns that auto-populate from Prometheus label values. Select one or more providers/models to filter all panels simultaneously.

The `model` variable is dependent on the selected `provider` — it only shows models for the currently selected provider(s).

### Time Range and Refresh

Default dashboard settings:

- **Time range**: Last 1 hour
- **Auto-refresh**: 30 seconds

Adjust these using the standard Grafana time picker in the top-right corner of the dashboard.

## Troubleshooting

**Metrics not appearing in Prometheus**

Likely cause: The OTEL Collector is not receiving metrics from AgentMap or not exporting to Prometheus.

```bash
curl http://prometheus:9090/api/v1/label/__name__/values | grep agentmap
```

Resolution: Verify that AgentMap has `telemetry.enabled: true` in `agentmap_config.yaml`, that `agentmap[telemetry]` is installed, and that the collector's OTLP receiver is reachable from the AgentMap process on port 4317.

**Traces not appearing in Tempo**

Likely cause: The OTEL Collector's traces pipeline is not configured to export to Tempo, or Tempo is unreachable.

```bash
curl -s http://tempo:3200/api/search?q=\{name%3D%22agentmap.workflow.run%22\} | python -m json.tool
```

Resolution: Verify the `otlp/tempo` exporter endpoint in the collector config matches your Tempo instance. Check collector logs for connection errors.

**Dashboard panels showing "No data"**

Likely cause: Datasource misconfiguration, or AgentMap has not yet generated telemetry data.

```bash
# Check if any agentmap metrics exist in Prometheus
curl -s http://prometheus:9090/api/v1/query?query=agentmap_llm_duration_seconds_count | python -m json.tool
```

Resolution: Run an AgentMap workflow with an LLM agent to generate metrics. Verify the Grafana datasource points to the correct Prometheus/Tempo URLs.

**Missing label values in dropdowns**

Likely cause: The `provider` or `model` label values have not been recorded yet, or the time range does not cover the data.

```bash
curl -s http://prometheus:9090/api/v1/label/provider/values | python -m json.tool
```

Resolution: Ensure LLM calls have been made (which populates the `provider` and `model` labels). Expand the dashboard time range to cover the period when data was generated.

**Cost panels showing zero**

Likely cause: Token counter metrics have not been recorded, or the cost template variables are set to zero.

```bash
curl -s http://prometheus:9090/api/v1/query?query=agentmap_llm_tokens_input_total | python -m json.tool
```

Resolution: Verify that `cost_per_input_token` and `cost_per_output_token` template variables are set to non-zero values. Ensure LLM calls are generating token usage metrics (the LLM provider must return usage metadata).

**Workflow Explorer metric panels empty but trace panels work**

Likely cause: The spanmetrics connector is not configured in the OTEL Collector pipeline.

```bash
# Check if span-derived metrics exist
curl -s http://prometheus:9090/api/v1/label/__name__/values | grep span_
```

Resolution: Add the `spanmetrics` connector to your collector config as described in the OTEL Collector Configuration section. The connector must appear as an exporter in the `traces` pipeline and as a receiver in the `metrics` pipeline.

## Next Steps

- **[OpenTelemetry - Embedded Integration](./otel-embedded)**: Use AgentMap's tracing within a host application's existing OTEL setup
- **[OpenTelemetry - Standalone Setup](./otel-standalone)**: Configure AgentMap as a standalone service with its own OTEL exporters
