"""
Unit tests for Grafana dashboard templates (T-E02-F07-004).

These tests validate the structural correctness of the dashboard JSON files,
provisioning YAML configs, and README documentation without requiring a
running Grafana instance.

Acceptance Criteria covered:
- AC1: Dashboard JSON Structural Validity
- AC2: Prometheus Metric Name Accuracy
- AC3: Template Variable Functionality
- AC4: Tempo TraceQL Correctness
- AC5: Datasource Portability (No Hardcoded UIDs)
- AC6: Cost Estimation Panel Configurability
- AC7: Panel Descriptions Present
- AC8: Provisioning Configuration Validity
- AC9: Documentation Completeness
- AC10: Metric Dimension Filtering
- AC11: Modern Panel Types Only
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
DASH_DIR = REPO_ROOT / "dashboards" / "grafana"
LLM_OPS_PATH = DASH_DIR / "agentmap-llm-operations.json"
WORKFLOW_PATH = DASH_DIR / "agentmap-workflow-explorer.json"
PROV_DIR = DASH_DIR / "provisioning"
DS_YAML = PROV_DIR / "datasources.yaml"
DASH_YAML = PROV_DIR / "dashboards.yaml"
README_PATH = DASH_DIR / "README.md"

# ---------------------------------------------------------------------------
# Valid Prometheus metric names from constants.py
# ---------------------------------------------------------------------------

VALID_AGENTMAP_METRICS = {
    # Histogram variants
    "agentmap_llm_duration_seconds_bucket",
    "agentmap_llm_duration_seconds_sum",
    "agentmap_llm_duration_seconds_count",
    # Counters (with _total suffix)
    "agentmap_llm_tokens_input_total",
    "agentmap_llm_tokens_output_total",
    "agentmap_llm_errors_total",
    "agentmap_llm_routing_cache_hit_total",
    "agentmap_llm_fallback_total",
    # UpDownCounter (no suffix)
    "agentmap_llm_circuit_breaker",
}

# Metrics that carry provider/model dimensions
METRICS_WITH_PROVIDER_MODEL = {
    "agentmap_llm_duration_seconds_bucket",
    "agentmap_llm_duration_seconds_sum",
    "agentmap_llm_duration_seconds_count",
    "agentmap_llm_tokens_input_total",
    "agentmap_llm_tokens_output_total",
    "agentmap_llm_errors_total",
}

# Metrics that must NOT have provider/model filters
METRICS_WITHOUT_PROVIDER_MODEL = {
    "agentmap_llm_routing_cache_hit_total",
    "agentmap_llm_circuit_breaker",
    "agentmap_llm_fallback_total",
}

# Deprecated Grafana panel types
DEPRECATED_PANEL_TYPES = {"graph", "singlestat", "table-old"}

# Modern panel types allowed
MODERN_PANEL_TYPES = {
    "timeseries",
    "stat",
    "gauge",
    "table",
    "heatmap",
    "traces",
    "nodeGraph",
    "row",
    "text",
}

# Valid span attribute names from constants.py
VALID_SPAN_ATTRIBUTES = {
    "agentmap.graph.name",
    "agentmap.graph.node_count",
    "agentmap.graph.agent_count",
    "agentmap.agent.name",
    "agentmap.agent.type",
    "agentmap.node.name",
    "agentmap.storage.backend",
    "agentmap.storage.operation",
    "agentmap.storage.record_count",
    "gen_ai.system",
    "gen_ai.request.model",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any]:
    """Load and parse a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_panels(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    """Recursively extract all panels (including those inside rows)."""
    panels: list[dict[str, Any]] = []
    for panel in dashboard.get("panels", []):
        panels.append(panel)
        # Rows can contain nested panels
        if panel.get("type") == "row":
            panels.extend(panel.get("panels", []))
    return panels


def _extract_promql_exprs(dashboard: dict[str, Any]) -> list[str]:
    """Extract all PromQL expression strings from a dashboard."""
    exprs: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            # Targets with expr field contain PromQL
            if "expr" in obj and isinstance(obj["expr"], str):
                exprs.append(obj["expr"])
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(dashboard)
    return exprs


def _extract_traceql_exprs(dashboard: dict[str, Any]) -> list[str]:
    """Extract TraceQL query strings from a dashboard."""
    exprs: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            # TraceQL queries appear in 'query' field for tempo datasource targets
            if "query" in obj and isinstance(obj["query"], str):
                q = obj["query"]
                # TraceQL queries use curly braces
                if "{" in q and ("name=" in q or "span." in q or "resource." in q):
                    exprs.append(q)
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(dashboard)
    return exprs


def _extract_datasource_uids(dashboard: dict[str, Any]) -> list[str]:
    """Extract all datasource uid values from a dashboard."""
    uids: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if "datasource" in obj and isinstance(obj["datasource"], dict):
                uid = obj["datasource"].get("uid")
                if uid is not None:
                    uids.append(uid)
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(dashboard)
    return uids


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def llm_ops_dashboard() -> dict[str, Any]:
    """Load LLM Operations dashboard JSON."""
    assert LLM_OPS_PATH.exists(), f"Dashboard file not found: {LLM_OPS_PATH}"
    return _load_json(LLM_OPS_PATH)


@pytest.fixture()
def workflow_dashboard() -> dict[str, Any]:
    """Load Workflow Explorer dashboard JSON."""
    assert WORKFLOW_PATH.exists(), f"Dashboard file not found: {WORKFLOW_PATH}"
    return _load_json(WORKFLOW_PATH)


# ---------------------------------------------------------------------------
# AC1: Dashboard JSON Structural Validity
# ---------------------------------------------------------------------------


class TestAC1_JsonStructuralValidity:
    """AC1: Dashboard JSON files are valid and have required structure."""

    def test_llm_ops_json_valid(self) -> None:
        """LLM Operations dashboard parses as valid JSON."""
        assert LLM_OPS_PATH.exists(), f"File not found: {LLM_OPS_PATH}"
        dashboard = _load_json(LLM_OPS_PATH)
        assert isinstance(dashboard, dict)

    def test_workflow_json_valid(self) -> None:
        """Workflow Explorer dashboard parses as valid JSON."""
        assert WORKFLOW_PATH.exists(), f"File not found: {WORKFLOW_PATH}"
        dashboard = _load_json(WORKFLOW_PATH)
        assert isinstance(dashboard, dict)

    def test_llm_ops_has_inputs(self, llm_ops_dashboard: dict) -> None:
        """LLM Operations has __inputs with at least one datasource."""
        inputs = llm_ops_dashboard.get("__inputs", [])
        assert len(inputs) >= 1
        ds_inputs = [i for i in inputs if i.get("type") == "datasource"]
        assert len(ds_inputs) >= 1

    def test_workflow_has_inputs(self, workflow_dashboard: dict) -> None:
        """Workflow Explorer has __inputs with at least one datasource."""
        inputs = workflow_dashboard.get("__inputs", [])
        assert len(inputs) >= 1
        ds_inputs = [i for i in inputs if i.get("type") == "datasource"]
        assert len(ds_inputs) >= 1

    def test_llm_ops_has_templating(self, llm_ops_dashboard: dict) -> None:
        """LLM Operations has templating.list with required variables."""
        tlist = llm_ops_dashboard.get("templating", {}).get("list", [])
        var_names = {v["name"] for v in tlist}
        required = {
            "datasource",
            "provider",
            "model",
            "interval",
            "cost_per_input_token",
            "cost_per_output_token",
        }
        assert required.issubset(
            var_names
        ), f"Missing template variables: {required - var_names}"

    def test_workflow_has_templating(self, workflow_dashboard: dict) -> None:
        """Workflow Explorer has templating.list with required variables."""
        tlist = workflow_dashboard.get("templating", {}).get("list", [])
        var_names = {v["name"] for v in tlist}
        required = {
            "datasource_prometheus",
            "datasource_tempo",
            "workflow",
            "agent_type",
        }
        assert required.issubset(
            var_names
        ), f"Missing template variables: {required - var_names}"

    def test_llm_ops_schema_version(self, llm_ops_dashboard: dict) -> None:
        """LLM Operations schemaVersion >= 39."""
        assert llm_ops_dashboard.get("schemaVersion", 0) >= 39

    def test_workflow_schema_version(self, workflow_dashboard: dict) -> None:
        """Workflow Explorer schemaVersion >= 39."""
        assert workflow_dashboard.get("schemaVersion", 0) >= 39

    def test_llm_ops_has_agentmap_tag(self, llm_ops_dashboard: dict) -> None:
        """LLM Operations has 'agentmap' tag."""
        assert "agentmap" in llm_ops_dashboard.get("tags", [])

    def test_workflow_has_agentmap_tag(self, workflow_dashboard: dict) -> None:
        """Workflow Explorer has 'agentmap' tag."""
        assert "agentmap" in workflow_dashboard.get("tags", [])

    def test_llm_ops_id_null(self, llm_ops_dashboard: dict) -> None:
        """LLM Operations has id: null for import."""
        assert llm_ops_dashboard.get("id") is None

    def test_workflow_id_null(self, workflow_dashboard: dict) -> None:
        """Workflow Explorer has id: null for import."""
        assert workflow_dashboard.get("id") is None

    def test_llm_ops_shared_crosshair(self, llm_ops_dashboard: dict) -> None:
        """LLM Operations uses shared crosshair (graphTooltip: 1)."""
        assert llm_ops_dashboard.get("graphTooltip") == 1

    def test_workflow_shared_crosshair(self, workflow_dashboard: dict) -> None:
        """Workflow Explorer uses shared crosshair (graphTooltip: 1)."""
        assert workflow_dashboard.get("graphTooltip") == 1


# ---------------------------------------------------------------------------
# AC2: Prometheus Metric Name Accuracy
# ---------------------------------------------------------------------------


class TestAC2_PrometheusMetricNames:
    """AC2: All PromQL references use correct Prometheus-translated names."""

    def test_llm_ops_metric_names_valid(self, llm_ops_dashboard: dict) -> None:
        """All agentmap metric references in LLM Ops use valid names."""
        exprs = _extract_promql_exprs(llm_ops_dashboard)
        assert len(exprs) > 0, "No PromQL expressions found"

        # Extract metric names from PromQL (word before { or [)
        metric_pattern = re.compile(r"(agentmap_\w+)")
        for expr in exprs:
            for match in metric_pattern.finditer(expr):
                name = match.group(1)
                assert (
                    name in VALID_AGENTMAP_METRICS
                ), f"Invalid metric name '{name}' in PromQL: {expr}"

    def test_counters_have_total_suffix(self, llm_ops_dashboard: dict) -> None:
        """Counter metrics use _total suffix."""
        exprs = _extract_promql_exprs(llm_ops_dashboard)
        # These must appear with _total, never without
        counter_bases = [
            "agentmap_llm_tokens_input",
            "agentmap_llm_tokens_output",
            "agentmap_llm_errors",
            "agentmap_llm_routing_cache_hit",
            "agentmap_llm_fallback",
        ]
        for expr in exprs:
            for base in counter_bases:
                # If base appears, it must be followed by _total
                if base in expr:
                    # Check it's not base without _total suffix
                    pattern = re.compile(rf"{base}(?!_total)\b")
                    assert not pattern.search(
                        expr
                    ), f"Counter '{base}' missing _total suffix in: {expr}"

    def test_updowncounter_no_total_suffix(self, llm_ops_dashboard: dict) -> None:
        """UpDownCounter agentmap_llm_circuit_breaker has no _total suffix."""
        exprs = _extract_promql_exprs(llm_ops_dashboard)
        for expr in exprs:
            assert (
                "agentmap_llm_circuit_breaker_total" not in expr
            ), f"UpDownCounter should not have _total suffix: {expr}"

    def test_no_dot_notation_metrics(self, llm_ops_dashboard: dict) -> None:
        """No PromQL uses dot-notation for agentmap metrics."""
        exprs = _extract_promql_exprs(llm_ops_dashboard)
        for expr in exprs:
            # agentmap.llm would be wrong -- should be agentmap_llm
            assert (
                "agentmap.llm" not in expr
            ), f"Dot notation found in PromQL (should be underscore): {expr}"


# ---------------------------------------------------------------------------
# AC3: Template Variable Functionality
# ---------------------------------------------------------------------------


class TestAC3_TemplateVariables:
    """AC3: Template variables are correctly configured."""

    def test_datasource_variable_type(self, llm_ops_dashboard: dict) -> None:
        """Datasource variable is type 'datasource' querying prometheus."""
        tlist = llm_ops_dashboard["templating"]["list"]
        ds_var = next(v for v in tlist if v["name"] == "datasource")
        assert ds_var["type"] == "datasource"
        assert ds_var["query"] == "prometheus"

    def test_provider_multi_select(self, llm_ops_dashboard: dict) -> None:
        """Provider variable supports multi-select and queries label_values."""
        tlist = llm_ops_dashboard["templating"]["list"]
        prov_var = next(v for v in tlist if v["name"] == "provider")
        assert prov_var["multi"] is True
        assert prov_var["includeAll"] is True
        # Check definition or query references correct metric
        defn = prov_var.get("definition", "")
        assert "agentmap_llm_duration_seconds_bucket" in defn
        assert "provider" in defn

    def test_model_depends_on_provider(self, llm_ops_dashboard: dict) -> None:
        """Model variable query includes provider filter."""
        tlist = llm_ops_dashboard["templating"]["list"]
        model_var = next(v for v in tlist if v["name"] == "model")
        assert model_var["multi"] is True
        defn = model_var.get("definition", "")
        assert 'provider=~"$provider"' in defn or "provider=~" in defn

    def test_cost_input_token_default(self, llm_ops_dashboard: dict) -> None:
        """cost_per_input_token is textbox with default 0.000003."""
        tlist = llm_ops_dashboard["templating"]["list"]
        cost_var = next(v for v in tlist if v["name"] == "cost_per_input_token")
        assert cost_var["type"] == "textbox"
        assert cost_var["query"] == "0.000003"

    def test_cost_output_token_default(self, llm_ops_dashboard: dict) -> None:
        """cost_per_output_token is textbox with default 0.000015."""
        tlist = llm_ops_dashboard["templating"]["list"]
        cost_var = next(v for v in tlist if v["name"] == "cost_per_output_token")
        assert cost_var["type"] == "textbox"
        assert cost_var["query"] == "0.000015"


# ---------------------------------------------------------------------------
# AC4: Tempo TraceQL Correctness
# ---------------------------------------------------------------------------


class TestAC4_TraceQLCorrectness:
    """AC4: TraceQL queries use correct span names and attributes."""

    def test_workflow_traces_query_correct_span(self, workflow_dashboard: dict) -> None:
        """Trace search filters on agentmap.workflow.run span name."""
        exprs = _extract_traceql_exprs(workflow_dashboard)
        found_workflow = any("agentmap.workflow.run" in expr for expr in exprs)
        assert found_workflow, "No TraceQL query references agentmap.workflow.run"

    def test_traceql_attributes_valid(self, workflow_dashboard: dict) -> None:
        """TraceQL attribute references use names from constants.py."""
        exprs = _extract_traceql_exprs(workflow_dashboard)
        # Extract span.X or resource.X attribute references
        attr_pattern = re.compile(r"span\.(agentmap\.\w+(?:\.\w+)*)")
        for expr in exprs:
            for match in attr_pattern.finditer(expr):
                attr = match.group(1)
                assert (
                    attr in VALID_SPAN_ATTRIBUTES
                ), f"Invalid span attribute '{attr}' in TraceQL: {expr}"


# ---------------------------------------------------------------------------
# AC5: Datasource Portability
# ---------------------------------------------------------------------------


class TestAC5_DatasourcePortability:
    """AC5: No hardcoded datasource UIDs."""

    def test_llm_ops_no_hardcoded_uids(self, llm_ops_dashboard: dict) -> None:
        """All datasource UIDs in LLM Ops reference variables."""
        uids = _extract_datasource_uids(llm_ops_dashboard)
        for uid in uids:
            assert uid.startswith("${"), f"Hardcoded datasource UID found: '{uid}'"

    def test_workflow_no_hardcoded_uids(self, workflow_dashboard: dict) -> None:
        """All datasource UIDs in Workflow Explorer reference variables."""
        uids = _extract_datasource_uids(workflow_dashboard)
        for uid in uids:
            assert uid.startswith("${"), f"Hardcoded datasource UID found: '{uid}'"

    def test_llm_ops_inputs_declare_prometheus(self, llm_ops_dashboard: dict) -> None:
        """LLM Ops __inputs declares prometheus datasource."""
        inputs = llm_ops_dashboard["__inputs"]
        plugin_ids = {i.get("pluginId") for i in inputs}
        assert "prometheus" in plugin_ids

    def test_workflow_inputs_declare_both(self, workflow_dashboard: dict) -> None:
        """Workflow Explorer __inputs declares prometheus and tempo."""
        inputs = workflow_dashboard["__inputs"]
        plugin_ids = {i.get("pluginId") for i in inputs}
        assert "prometheus" in plugin_ids
        assert "tempo" in plugin_ids


# ---------------------------------------------------------------------------
# AC6: Cost Estimation Panel Configurability
# ---------------------------------------------------------------------------


class TestAC6_CostEstimation:
    """AC6: Cost panels use template variables, no hardcoded costs."""

    def test_cost_panels_use_variables(self, llm_ops_dashboard: dict) -> None:
        """Cost PromQL expressions use $cost_per_input_token / $cost_per_output_token."""
        panels = _extract_panels(llm_ops_dashboard)
        cost_panels = [
            p
            for p in panels
            if p.get("title", "")
            .lower()
            .startswith(("estimated cost", "total estimated"))
        ]
        assert len(cost_panels) >= 2, "Expected at least 2 cost panels"

        for panel in cost_panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                if expr:
                    assert (
                        "$cost_per_input_token" in expr
                        or "$cost_per_output_token" in expr
                    ), f"Cost panel '{panel.get('title')}' missing cost variables in: {expr}"

    def test_no_hardcoded_cost_values(self, llm_ops_dashboard: dict) -> None:
        """No cost panel contains hardcoded numeric cost multiplier."""
        panels = _extract_panels(llm_ops_dashboard)
        cost_panels = [
            p
            for p in panels
            if p.get("title", "")
            .lower()
            .startswith(("estimated cost", "total estimated"))
        ]
        for panel in cost_panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                if expr:
                    # Should not contain patterns like * 0.000003 (hardcoded cost)
                    hardcoded = re.search(r"\*\s*0\.\d+", expr)
                    assert (
                        hardcoded is None
                    ), f"Hardcoded cost value in panel '{panel.get('title')}': {expr}"


# ---------------------------------------------------------------------------
# AC7: Panel Descriptions Present
# ---------------------------------------------------------------------------


class TestAC7_PanelDescriptions:
    """AC7: Every non-row panel has a non-empty description (min 10 chars)."""

    def test_llm_ops_descriptions(self, llm_ops_dashboard: dict) -> None:
        """All non-row panels in LLM Ops have descriptions >= 10 chars."""
        panels = _extract_panels(llm_ops_dashboard)
        non_row_panels = [p for p in panels if p.get("type") != "row"]
        assert len(non_row_panels) > 0, "No non-row panels found"

        for panel in non_row_panels:
            desc = panel.get("description", "")
            title = panel.get("title", "<untitled>")
            assert (
                len(desc) >= 10
            ), f"Panel '{title}' has description shorter than 10 chars: '{desc}'"

    def test_workflow_descriptions(self, workflow_dashboard: dict) -> None:
        """All non-row panels in Workflow Explorer have descriptions >= 10 chars."""
        panels = _extract_panels(workflow_dashboard)
        non_row_panels = [p for p in panels if p.get("type") != "row"]
        assert len(non_row_panels) > 0, "No non-row panels found"

        for panel in non_row_panels:
            desc = panel.get("description", "")
            title = panel.get("title", "<untitled>")
            assert (
                len(desc) >= 10
            ), f"Panel '{title}' has description shorter than 10 chars: '{desc}'"


# ---------------------------------------------------------------------------
# AC8: Provisioning Configuration Validity
# ---------------------------------------------------------------------------


class TestAC8_ProvisioningConfig:
    """AC8: Provisioning YAML files are valid."""

    def test_datasources_yaml_valid(self) -> None:
        """datasources.yaml parses as valid YAML."""
        assert DS_YAML.exists(), f"File not found: {DS_YAML}"
        data = yaml.safe_load(DS_YAML.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_dashboards_yaml_valid(self) -> None:
        """dashboards.yaml parses as valid YAML."""
        assert DASH_YAML.exists(), f"File not found: {DASH_YAML}"
        data = yaml.safe_load(DASH_YAML.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_datasources_has_prometheus_and_tempo(self) -> None:
        """datasources.yaml defines Prometheus and Tempo datasources."""
        data = yaml.safe_load(DS_YAML.read_text(encoding="utf-8"))
        assert "datasources" in data
        ds_types = {ds.get("type") for ds in data["datasources"]}
        assert "prometheus" in ds_types
        assert "tempo" in ds_types

    def test_datasources_has_api_version(self) -> None:
        """datasources.yaml has apiVersion key."""
        data = yaml.safe_load(DS_YAML.read_text(encoding="utf-8"))
        assert "apiVersion" in data

    def test_dashboards_has_providers(self) -> None:
        """dashboards.yaml defines providers with path."""
        data = yaml.safe_load(DASH_YAML.read_text(encoding="utf-8"))
        assert "providers" in data
        providers = data["providers"]
        assert len(providers) >= 1
        # At least one provider has a path in options
        found_path = any(p.get("options", {}).get("path") for p in providers)
        assert found_path, "No provider has an options.path"

    def test_dashboards_has_api_version(self) -> None:
        """dashboards.yaml has apiVersion key."""
        data = yaml.safe_load(DASH_YAML.read_text(encoding="utf-8"))
        assert "apiVersion" in data


# ---------------------------------------------------------------------------
# AC9: Documentation Completeness
# ---------------------------------------------------------------------------


class TestAC9_DocumentationCompleteness:
    """AC9: README.md contains all required sections."""

    def test_readme_exists(self) -> None:
        """README.md exists."""
        assert README_PATH.exists(), f"File not found: {README_PATH}"

    def test_readme_has_ui_import(self) -> None:
        """README contains UI import instructions."""
        content = README_PATH.read_text(encoding="utf-8").lower()
        assert "import" in content
        # Should have numbered steps or step references
        assert re.search(
            r"(step|1\.|1\))", content
        ), "README missing numbered import steps"

    def test_readme_has_provisioning(self) -> None:
        """README contains provisioning deployment instructions."""
        content = README_PATH.read_text(encoding="utf-8").lower()
        assert "provisioning" in content

    def test_readme_has_infrastructure_requirements(self) -> None:
        """README mentions required infrastructure (Prometheus, Tempo)."""
        content = README_PATH.read_text(encoding="utf-8").lower()
        assert "prometheus" in content
        assert "tempo" in content

    def test_readme_has_collector_config(self) -> None:
        """README has OTEL Collector pipeline configuration."""
        content = README_PATH.read_text(encoding="utf-8").lower()
        assert "collector" in content or "otel" in content
        assert "spanmetrics" in content

    def test_readme_has_cost_customization(self) -> None:
        """README covers cost-per-token variable customization."""
        content = README_PATH.read_text(encoding="utf-8").lower()
        assert "cost" in content
        assert "token" in content

    def test_readme_has_agentmap_config(self) -> None:
        """README covers AgentMap telemetry configuration requirements."""
        content = README_PATH.read_text(encoding="utf-8").lower()
        assert "telemetry" in content
        assert "agentmap" in content


# ---------------------------------------------------------------------------
# AC10: Metric Dimension Filtering
# ---------------------------------------------------------------------------


class TestAC10_MetricDimensionFiltering:
    """AC10: PromQL filters match the metric-to-dimension matrix."""

    def test_metrics_with_provider_have_filter(self, llm_ops_dashboard: dict) -> None:
        """Metrics with provider/model dimensions include those filters.

        Exception: The Cache Hit Ratio panel uses agentmap_llm_duration_seconds_count
        as a total calls baseline WITHOUT provider/model filter, per the task spec:
        'No provider/model filter on cache hit; no filter on duration count either
        (total calls baseline)'. We skip expressions that also contain
        agentmap_llm_routing_cache_hit_total (indicating the ratio calculation).
        """
        exprs = _extract_promql_exprs(llm_ops_dashboard)
        for expr in exprs:
            # Skip the cache hit ratio expression (intentionally unfiltered baseline)
            if "agentmap_llm_routing_cache_hit_total" in expr:
                continue
            for metric in METRICS_WITH_PROVIDER_MODEL:
                if metric in expr:
                    # Should have provider filter
                    assert (
                        'provider=~"$provider"' in expr or "provider=~" in expr
                    ), f"Metric '{metric}' missing provider filter in: {expr}"

    def test_metrics_without_provider_no_filter(self, llm_ops_dashboard: dict) -> None:
        """Metrics without provider/model dimensions do NOT include those filters."""
        exprs = _extract_promql_exprs(llm_ops_dashboard)
        for expr in exprs:
            for metric in METRICS_WITHOUT_PROVIDER_MODEL:
                if metric in expr:
                    assert (
                        "provider=~" not in expr
                    ), f"Metric '{metric}' should NOT have provider filter: {expr}"
                    assert (
                        "model=~" not in expr
                    ), f"Metric '{metric}' should NOT have model filter: {expr}"


# ---------------------------------------------------------------------------
# AC11: Modern Panel Types Only
# ---------------------------------------------------------------------------


class TestAC11_ModernPanelTypes:
    """AC11: No deprecated panel types used."""

    def test_llm_ops_no_deprecated(self, llm_ops_dashboard: dict) -> None:
        """LLM Ops uses no deprecated panel types."""
        panels = _extract_panels(llm_ops_dashboard)
        for panel in panels:
            ptype = panel.get("type", "")
            assert (
                ptype not in DEPRECATED_PANEL_TYPES
            ), f"Deprecated panel type '{ptype}' in panel '{panel.get('title')}'"
            if ptype != "row":
                assert (
                    ptype in MODERN_PANEL_TYPES
                ), f"Unknown panel type '{ptype}' in panel '{panel.get('title')}'"

    def test_workflow_no_deprecated(self, workflow_dashboard: dict) -> None:
        """Workflow Explorer uses no deprecated panel types."""
        panels = _extract_panels(workflow_dashboard)
        for panel in panels:
            ptype = panel.get("type", "")
            assert (
                ptype not in DEPRECATED_PANEL_TYPES
            ), f"Deprecated panel type '{ptype}' in panel '{panel.get('title')}'"
            if ptype != "row":
                assert (
                    ptype in MODERN_PANEL_TYPES
                ), f"Unknown panel type '{ptype}' in panel '{panel.get('title')}'"


# ---------------------------------------------------------------------------
# Panel Count Validation
# ---------------------------------------------------------------------------


class TestPanelCounts:
    """Verify correct number of panels in each dashboard."""

    def test_llm_ops_panel_count(self, llm_ops_dashboard: dict) -> None:
        """LLM Operations has 22 panels (6 rows + 16 content panels)."""
        panels = _extract_panels(llm_ops_dashboard)
        # 6 rows + 16 content panels = 22
        assert len(panels) == 22, f"Expected 22 panels, got {len(panels)}"

    def test_workflow_panel_count(self, workflow_dashboard: dict) -> None:
        """Workflow Explorer has 15 panels (5 rows + 10 content panels).

        Grid layout from task spec: 5 rows (Workflow Overview, Agent Breakdown,
        Storage, Trace Search, Service Graph) + 10 content panels.
        """
        panels = _extract_panels(workflow_dashboard)
        assert len(panels) == 15, f"Expected 15 panels, got {len(panels)}"


# ---------------------------------------------------------------------------
# Required Panel Titles
# ---------------------------------------------------------------------------


class TestRequiredPanels:
    """Verify all required panels exist by title."""

    LLM_OPS_REQUIRED_PANELS = [
        "Total LLM Calls",
        "Total Tokens",
        "Error Rate",
        "Avg Latency",
    ]

    WORKFLOW_REQUIRED_PANELS = [
        "Execution Rate",
        "Avg Duration",
    ]

    def test_llm_ops_required_panels_present(self, llm_ops_dashboard: dict) -> None:
        """LLM Ops contains all required overview panels."""
        panels = _extract_panels(llm_ops_dashboard)
        titles = {p.get("title", "") for p in panels}
        for required in self.LLM_OPS_REQUIRED_PANELS:
            assert required in titles, f"Missing required panel: '{required}'"

    def test_workflow_required_panels_present(self, workflow_dashboard: dict) -> None:
        """Workflow Explorer contains required overview panels."""
        panels = _extract_panels(workflow_dashboard)
        titles = {p.get("title", "") for p in panels}
        for required in self.WORKFLOW_REQUIRED_PANELS:
            assert required in titles, f"Missing required panel: '{required}'"
