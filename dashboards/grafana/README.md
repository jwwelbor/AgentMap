# AgentMap Grafana Dashboard Templates

Pre-built Grafana dashboard templates for monitoring AgentMap's OpenTelemetry-instrumented LLM operations, workflow execution, and trace exploration.

## Dashboards Included

| Dashboard | File | Data Sources | Purpose |
|-----------|------|-------------|---------|
| **LLM Operations** | `agentmap-llm-operations.json` | Prometheus | LLM latency, token usage, errors, routing, cost estimation |
| **Workflow & Trace Explorer** | `agentmap-workflow-explorer.json` | Prometheus + Tempo | Workflow execution rates, agent breakdown, trace search |

## Prerequisites

### Required Infrastructure

- **Grafana** 10.0 or later (dashboards use schemaVersion 39+ features)
- **Prometheus** for metrics storage (any recent version)
- **Tempo** for trace storage (required for the Workflow Explorer dashboard's trace panels)
- **OpenTelemetry Collector** configured to receive AgentMap telemetry and export to Prometheus and Tempo

### AgentMap Telemetry Configuration

AgentMap must be configured to export OTEL telemetry. In your `agentmap_config.yaml`, ensure the telemetry section is enabled:

```yaml
telemetry:
  enabled: true
  service_name: agentmap
  exporter:
    type: otlp
    endpoint: "http://localhost:4317"  # Your OTEL Collector endpoint
```

The dashboards rely on the 7 metric instruments and 5 span types defined in AgentMap's telemetry constants. No code changes to AgentMap are required.

## Import via Grafana UI

1. Open your Grafana instance in a browser.
2. Navigate to **Dashboards** in the left sidebar.
3. Click the **New** button, then select **Import**.
4. Click **Upload dashboard JSON file** and select either `agentmap-llm-operations.json` or `agentmap-workflow-explorer.json`.
5. On the import screen, select your Prometheus datasource from the dropdown (and Tempo datasource for the Workflow Explorer).
6. Click **Import** to complete the process.
7. Repeat steps 3-6 for the second dashboard.

## Provisioning Deployment

For automated deployment via Grafana's provisioning system (infrastructure-as-code):

1. Copy the dashboard JSON files to your Grafana dashboard provisioning directory (e.g., `/var/lib/grafana/dashboards/agentmap/`).
2. Copy `provisioning/datasources.yaml` to your Grafana provisioning datasources directory (e.g., `/etc/grafana/provisioning/datasources/`).
3. Copy `provisioning/dashboards.yaml` to your Grafana provisioning dashboards directory (e.g., `/etc/grafana/provisioning/dashboards/`).
4. Update the datasource URLs in `datasources.yaml` to match your actual Prometheus and Tempo endpoints. The default placeholders (`http://prometheus:9090` and `http://tempo:3200`) are examples only.
5. Restart Grafana to load the provisioned configuration.

See the `provisioning/` directory for the configuration files.

## OTEL Collector Pipeline Configuration

The dashboards require specific OTEL Collector pipeline configuration. The LLM Operations dashboard reads metrics directly exported by AgentMap via the OTEL Prometheus exporter. The Workflow Explorer dashboard additionally requires the **spanmetrics connector** to generate metrics from trace data.

### Required Collector Configuration

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

connectors:
  spanmetrics:
    histogram:
      explicit:
        buckets: [5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s]
    dimensions:
      - name: agentmap.graph.name
      - name: agentmap.agent.type
      - name: agentmap.agent.name
      - name: agentmap.storage.backend
      - name: agentmap.storage.operation
    dimensions_cache_size: 1000
    aggregation_temporality: "AGGREGATION_TEMPORALITY_CUMULATIVE"

exporters:
  prometheus:
    endpoint: 0.0.0.0:8889
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [otlp/tempo, spanmetrics]
    metrics:
      receivers: [otlp, spanmetrics]
      exporters: [prometheus]
```

The `spanmetrics` connector is critical for the Workflow Explorer dashboard's metrics panels (workflow execution rate, agent breakdown, storage operations). Without it, those panels will show "No data" but the Tempo trace search panels will still function.

## Template Variable Customization

### LLM Operations Dashboard Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `datasource` | Select Prometheus datasource | Auto-detected |
| `provider` | Filter by LLM provider (multi-select) | All |
| `model` | Filter by model, dependent on provider (multi-select) | All |
| `interval` | Rate calculation interval | auto |
| `cost_per_input_token` | Cost per input token in USD | `0.000003` |
| `cost_per_output_token` | Cost per output token in USD | `0.000015` |

### Cost-per-Token Configuration

The cost estimation panels calculate estimated LLM spend using configurable cost-per-token rates. The default values (`$0.000003` per input token, `$0.000015` per output token) are illustrative only.

To set your organization's actual pricing:

1. Open the LLM Operations dashboard.
2. Click the **Cost per Input Token ($)** dropdown at the top of the dashboard.
3. Enter your negotiated rate (e.g., `0.00001` for $0.01 per 1000 tokens).
4. Repeat for **Cost per Output Token ($)**.

Note: Different providers and models have different pricing. The cost panels apply a single rate across all providers. For per-model pricing, fork the dashboard and create separate cost panels per model.

### Workflow Explorer Dashboard Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `datasource_prometheus` | Select Prometheus datasource | Auto-detected |
| `datasource_tempo` | Select Tempo datasource | Auto-detected |
| `workflow` | Filter by workflow name (multi-select) | All |
| `agent_type` | Filter by agent type (multi-select) | All |

## Metrics Reference

The dashboards visualize these AgentMap OTEL metrics:

| OTEL Metric Name | Prometheus Name | Type |
|-------------------|-----------------|------|
| `agentmap.llm.duration` | `agentmap_llm_duration_seconds_*` | Histogram |
| `agentmap.llm.tokens.input` | `agentmap_llm_tokens_input_total` | Counter |
| `agentmap.llm.tokens.output` | `agentmap_llm_tokens_output_total` | Counter |
| `agentmap.llm.errors` | `agentmap_llm_errors_total` | Counter |
| `agentmap.llm.routing.cache_hit` | `agentmap_llm_routing_cache_hit_total` | Counter |
| `agentmap.llm.circuit_breaker` | `agentmap_llm_circuit_breaker` | UpDownCounter |
| `agentmap.llm.fallback` | `agentmap_llm_fallback_total` | Counter |

## Troubleshooting

- **Panels show "No data"**: Ensure AgentMap telemetry is enabled and the OTEL Collector is receiving data. Check the Collector logs for connection errors.
- **Workflow Explorer metrics panels empty**: Verify the spanmetrics connector is configured in your OTEL Collector pipeline.
- **Trace search returns no results**: Confirm Tempo is receiving traces and the datasource is correctly configured in Grafana.
- **Cost panels show unexpected values**: Verify the cost_per_input_token and cost_per_output_token variables are set to your actual rates.

## Minimum Version Requirements

- Grafana: 10.0+
- Grafana dashboard schemaVersion: 39+
- OTEL Collector: any version supporting the spanmetrics connector

Dashboards may not render correctly on Grafana 9.x or earlier due to panel type and schema changes.
