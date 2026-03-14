# AgentMap Grafana Dashboards

Pre-built Grafana dashboard templates for monitoring AgentMap's OpenTelemetry-instrumented LLM operations, workflow execution, and trace exploration. These dashboards visualize the 7 metric instruments and 5 span types emitted by AgentMap's telemetry layer, providing real-time visibility into LLM latency, token usage, error rates, routing decisions, and estimated costs.

## Dashboards

| File | Dashboard | Datasource | Description |
|------|-----------|------------|-------------|
| `agentmap-llm-operations.json` | LLM Operations | Prometheus | LLM latency, token usage, errors, routing intelligence, and cost estimation panels |
| `agentmap-workflow-explorer.json` | Workflow & Trace Explorer | Prometheus + Tempo | Workflow execution rates, agent breakdown, storage operations, trace search, and service graph |

## Directory Structure

```
dashboards/grafana/
  agentmap-llm-operations.json
  agentmap-workflow-explorer.json
  provisioning/
    datasources.yaml        # Prometheus + Tempo datasource definitions
    dashboards.yaml          # Grafana dashboard provider config
  README.md                  # This file
```

## Requirements

- **Grafana 10+** (schemaVersion 39+)
- **Prometheus** for metrics storage
- **Tempo** for trace storage (required for Workflow Explorer trace panels)
- **OpenTelemetry Collector** with OTLP receiver, Prometheus exporter, and spanmetrics connector

## Quick Import

1. Download or clone the dashboard JSON files from this directory.
2. In Grafana, go to **Dashboards** > **New** > **Import** > **Upload dashboard JSON file**.
3. Select your Prometheus datasource (and Tempo datasource for the Workflow Explorer) and click **Import**.

## Provisioning

For automated deployment, copy the files from the `provisioning/` directory to your Grafana provisioning paths:

- `provisioning/datasources.yaml` -> `/etc/grafana/provisioning/datasources/`
- `provisioning/dashboards.yaml` -> `/etc/grafana/provisioning/dashboards/`
- Dashboard JSON files -> `/var/lib/grafana/dashboards/agentmap/`

Update the datasource URLs in `datasources.yaml` to match your environment.

## Documentation

For complete setup instructions, OTEL Collector configuration, metrics reference, customization, and troubleshooting, see the full documentation:

[docs/deployment/13-grafana-dashboards.md](../../docs-docusaurus/docs/deployment/13-grafana-dashboards.md)
