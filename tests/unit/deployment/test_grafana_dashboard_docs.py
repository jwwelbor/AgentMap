"""
Unit tests for Grafana Dashboard Documentation (T-E02-F07-005).

These tests validate the documentation deliverables:
1. Docusaurus page at docs-docusaurus/docs/deployment/13-grafana-dashboards.md
2. Dashboard directory README at dashboards/grafana/README.md
3. Cross-reference updates to 11-otel-embedded.md and 12-otel-standalone.md

Acceptance Criteria covered:
- AC1.1-AC1.3: Quick Start documentation
- AC2.1-AC2.3: Provisioning Setup documentation
- AC3.1-AC3.3: Dashboard Overview documentation
- AC4.1-AC4.3: OTEL Collector Configuration
- AC5.1-AC5.4: Metric and Span Name Accuracy
- AC6.1-AC6.2: Template Variable Customization
- AC7.1-AC7.2: Troubleshooting
- AC8.1-AC8.3: Dashboard Directory README
- Contract 7: Cross-Reference Updates
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_DIR = REPO_ROOT / "docs-docusaurus" / "docs" / "deployment"
GRAFANA_DOCS_PATH = DOCS_DIR / "13-grafana-dashboards.md"
OTEL_EMBEDDED_PATH = DOCS_DIR / "11-otel-embedded.md"
OTEL_STANDALONE_PATH = DOCS_DIR / "12-otel-standalone.md"
DASH_DIR = REPO_ROOT / "dashboards" / "grafana"
README_PATH = DASH_DIR / "README.md"

# ---------------------------------------------------------------------------
# Constants from constants.py for validation
# ---------------------------------------------------------------------------

OTEL_METRIC_NAMES = [
    "agentmap.llm.duration",
    "agentmap.llm.tokens.input",
    "agentmap.llm.tokens.output",
    "agentmap.llm.errors",
    "agentmap.llm.routing.cache_hit",
    "agentmap.llm.circuit_breaker",
    "agentmap.llm.fallback",
]

PROMETHEUS_METRIC_NAMES = [
    "agentmap_llm_duration_seconds",
    "agentmap_llm_tokens_input_total",
    "agentmap_llm_tokens_output_total",
    "agentmap_llm_errors_total",
    "agentmap_llm_routing_cache_hit_total",
    "agentmap_llm_circuit_breaker",
    "agentmap_llm_fallback_total",
]

METRIC_DIMENSIONS = ["provider", "model", "error_type", "tier"]

SPAN_NAMES = [
    "agentmap.workflow.run",
    "agentmap.agent.run",
    "gen_ai.chat",
    "agentmap.storage.read",
    "agentmap.storage.write",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def grafana_docs_content() -> str:
    """Load the Grafana dashboards Docusaurus page."""
    assert GRAFANA_DOCS_PATH.exists(), f"Docusaurus page not found: {GRAFANA_DOCS_PATH}"
    return GRAFANA_DOCS_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def readme_content() -> str:
    """Load the dashboard directory README."""
    assert README_PATH.exists(), f"README not found: {README_PATH}"
    return README_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def otel_embedded_content() -> str:
    """Load the OTEL embedded docs page."""
    assert (
        OTEL_EMBEDDED_PATH.exists()
    ), f"OTEL embedded page not found: {OTEL_EMBEDDED_PATH}"
    return OTEL_EMBEDDED_PATH.read_text(encoding="utf-8")


@pytest.fixture()
def otel_standalone_content() -> str:
    """Load the OTEL standalone docs page."""
    assert (
        OTEL_STANDALONE_PATH.exists()
    ), f"OTEL standalone page not found: {OTEL_STANDALONE_PATH}"
    return OTEL_STANDALONE_PATH.read_text(encoding="utf-8")


# ===========================================================================
# Docusaurus Page Tests (13-grafana-dashboards.md)
# ===========================================================================


class TestDocusaurusPageStructure:
    """Validate the Docusaurus page structure per Contract 6."""

    def test_page_exists(self) -> None:
        """13-grafana-dashboards.md exists."""
        assert (
            GRAFANA_DOCS_PATH.exists()
        ), f"Docusaurus page not found: {GRAFANA_DOCS_PATH}"

    def test_frontmatter_sidebar_position(self, grafana_docs_content: str) -> None:
        """Frontmatter has sidebar_position: 13."""
        assert "sidebar_position: 13" in grafana_docs_content

    def test_frontmatter_title(self, grafana_docs_content: str) -> None:
        """Frontmatter has correct title."""
        assert (
            'title: "Grafana Dashboards"' in grafana_docs_content
            or "title: Grafana Dashboards" in grafana_docs_content
        )

    def test_frontmatter_description(self, grafana_docs_content: str) -> None:
        """Frontmatter has description field."""
        assert "description:" in grafana_docs_content

    def test_frontmatter_keywords(self, grafana_docs_content: str) -> None:
        """Frontmatter has keywords field."""
        assert "keywords:" in grafana_docs_content

    def test_breadcrumb_div(self, grafana_docs_content: str) -> None:
        """Page has breadcrumb div matching existing page format."""
        assert "Grafana Dashboards</strong>" in grafana_docs_content
        assert "marginBottom" in grafana_docs_content

    def test_h1_heading(self, grafana_docs_content: str) -> None:
        """Page has correct H1 heading."""
        assert "# Grafana Dashboards" in grafana_docs_content

    def test_prerequisites_section(self, grafana_docs_content: str) -> None:
        """Page has Prerequisites section with subsections."""
        assert "## Prerequisites" in grafana_docs_content
        assert "### Infrastructure" in grafana_docs_content
        assert "### AgentMap Configuration" in grafana_docs_content

    def test_quick_start_section(self, grafana_docs_content: str) -> None:
        """Page has Quick Start section."""
        assert "## Quick Start" in grafana_docs_content

    def test_provisioning_section(self, grafana_docs_content: str) -> None:
        """Page has Provisioning Setup section."""
        assert "## Provisioning Setup" in grafana_docs_content
        assert "### Self-Hosted Grafana" in grafana_docs_content

    def test_dashboard_overview_section(self, grafana_docs_content: str) -> None:
        """Page has Dashboard Overview with subsections."""
        assert "## Dashboard Overview" in grafana_docs_content
        assert "### LLM Operations Dashboard" in grafana_docs_content
        assert "### Workflow & Trace Explorer Dashboard" in grafana_docs_content

    def test_metrics_reference_section(self, grafana_docs_content: str) -> None:
        """Page has Metrics Reference section."""
        assert "## Metrics Reference" in grafana_docs_content

    def test_span_reference_section(self, grafana_docs_content: str) -> None:
        """Page has Span Reference section."""
        assert "## Span Reference" in grafana_docs_content

    def test_collector_config_section(self, grafana_docs_content: str) -> None:
        """Page has OTEL Collector Configuration with subsections."""
        assert "## OTEL Collector Configuration" in grafana_docs_content
        assert "### Add to Existing Collector" in grafana_docs_content
        assert "### Complete Standalone Configuration" in grafana_docs_content

    def test_customization_section(self, grafana_docs_content: str) -> None:
        """Page has Customization section with subsections."""
        assert "## Customization" in grafana_docs_content
        assert "### Cost Variables" in grafana_docs_content
        assert "### Provider and Model Filtering" in grafana_docs_content
        assert "### Time Range and Refresh" in grafana_docs_content

    def test_troubleshooting_section(self, grafana_docs_content: str) -> None:
        """Page has Troubleshooting section."""
        assert "## Troubleshooting" in grafana_docs_content

    def test_next_steps_section(self, grafana_docs_content: str) -> None:
        """Page has Next Steps section."""
        assert "## Next Steps" in grafana_docs_content


# ===========================================================================
# AC1: Quick Start (Story 1)
# ===========================================================================


class TestAC1_QuickStart:
    """AC1: Quick Start enables dashboard import within 10 minutes."""

    def test_ac1_1_import_steps(self, grafana_docs_content: str) -> None:
        """AC1.1: Quick Start has import steps for Grafana UI."""
        content_lower = grafana_docs_content.lower()
        assert "dashboards" in content_lower
        assert "import" in content_lower
        assert "upload" in content_lower or "json" in content_lower

    def test_ac1_2_prerequisites_infrastructure(
        self, grafana_docs_content: str
    ) -> None:
        """AC1.2: Prerequisites list Grafana 10+, Prometheus, Tempo."""
        assert (
            "Grafana 10" in grafana_docs_content
            or "Grafana 10+" in grafana_docs_content
        )
        assert "Prometheus" in grafana_docs_content
        assert "Tempo" in grafana_docs_content

    def test_ac1_3_agentmap_prerequisites(self, grafana_docs_content: str) -> None:
        """AC1.3: Prerequisites specify agentmap[telemetry] and config."""
        assert "agentmap[telemetry]" in grafana_docs_content
        assert "telemetry" in grafana_docs_content.lower()
        assert "enabled" in grafana_docs_content.lower()


# ===========================================================================
# AC2: Provisioning Setup (Story 2)
# ===========================================================================


class TestAC2_ProvisioningSetup:
    """AC2: Provisioning instructions reference correct files and paths."""

    def test_ac2_1_provisioning_file_references(
        self, grafana_docs_content: str
    ) -> None:
        """AC2.1: References exact provisioning filenames."""
        assert "datasources.yaml" in grafana_docs_content
        assert "dashboards.yaml" in grafana_docs_content

    def test_ac2_2_mount_paths(self, grafana_docs_content: str) -> None:
        """AC2.2: Volume mounts use standard Grafana paths."""
        assert "/etc/grafana/provisioning/" in grafana_docs_content
        assert "/var/lib/grafana/dashboards/" in grafana_docs_content

    def test_ac2_3_disable_deletion(self, grafana_docs_content: str) -> None:
        """AC2.3: Provisioning config includes disableDeletion."""
        assert "disableDeletion" in grafana_docs_content


# ===========================================================================
# AC3: Dashboard Overview (Story 3)
# ===========================================================================


class TestAC3_DashboardOverview:
    """AC3: Dashboard overview lists all panel rows."""

    def test_ac3_1_llm_ops_panel_rows(self, grafana_docs_content: str) -> None:
        """AC3.1: LLM Operations lists 6 panel rows."""
        assert "Overview" in grafana_docs_content
        assert "Latency" in grafana_docs_content
        assert "Token Usage" in grafana_docs_content
        assert "Errors" in grafana_docs_content
        assert "Routing Intelligence" in grafana_docs_content
        assert "Cost Estimation" in grafana_docs_content

    def test_ac3_2_workflow_panel_rows(self, grafana_docs_content: str) -> None:
        """AC3.2: Workflow Explorer lists 5 panel rows."""
        assert "Workflow Overview" in grafana_docs_content
        assert "Agent Breakdown" in grafana_docs_content
        assert "Storage Operations" in grafana_docs_content
        assert "Trace Search" in grafana_docs_content
        assert "Service Graph" in grafana_docs_content

    def test_ac3_3_datasource_requirements(self, grafana_docs_content: str) -> None:
        """AC3.3: Each dashboard specifies datasource requirements."""
        # LLM Ops requires Prometheus only; Workflow needs both
        content_lower = grafana_docs_content.lower()
        assert "prometheus" in content_lower
        assert "tempo" in content_lower


# ===========================================================================
# AC4: OTEL Collector Configuration (Story 4)
# ===========================================================================


class TestAC4_CollectorConfig:
    """AC4: Complete OTEL Collector configuration."""

    def test_ac4_1_collector_components(self, grafana_docs_content: str) -> None:
        """AC4.1: Config includes otlp receiver, prometheus exporter, tempo."""
        assert "otlp:" in grafana_docs_content
        assert "4317" in grafana_docs_content
        assert "prometheus:" in grafana_docs_content
        assert "tempo" in grafana_docs_content.lower()

    def test_ac4_2_pipelines(self, grafana_docs_content: str) -> None:
        """AC4.2: Config includes metrics and traces pipelines."""
        assert "pipelines:" in grafana_docs_content
        assert "traces:" in grafana_docs_content
        assert "metrics:" in grafana_docs_content

    def test_ac4_3_yaml_validity(self, grafana_docs_content: str) -> None:
        """AC4.3: The standalone collector config is valid YAML."""
        # Extract the YAML code block after "Complete Standalone Configuration"
        pattern = re.compile(
            r"### Complete Standalone Configuration.*?```yaml\n(.*?)```",
            re.DOTALL,
        )
        match = pattern.search(grafana_docs_content)
        assert (
            match is not None
        ), "Could not find YAML block in Complete Standalone Configuration"
        yaml_content = match.group(1)
        config = yaml.safe_load(yaml_content)
        assert isinstance(config, dict)
        assert "receivers" in config
        assert "exporters" in config
        assert "service" in config

    def test_spanmetrics_documented(self, grafana_docs_content: str) -> None:
        """ADR-T005-005: Spanmetrics connector documented as requirement."""
        assert "spanmetrics" in grafana_docs_content


# ===========================================================================
# AC5: Metric and Span Name Accuracy (Story 5)
# ===========================================================================


class TestAC5_MetricSpanAccuracy:
    """AC5: All metric and span names from constants.py documented."""

    def test_ac5_1_all_metrics_listed(self, grafana_docs_content: str) -> None:
        """AC5.1: All 7 OTEL metric names from constants.py are listed."""
        for metric in OTEL_METRIC_NAMES:
            assert metric in grafana_docs_content, f"Missing OTEL metric name: {metric}"

    def test_ac5_2_prometheus_translations(self, grafana_docs_content: str) -> None:
        """AC5.2: Correct Prometheus-translated names for all 7 metrics."""
        for prom_name in PROMETHEUS_METRIC_NAMES:
            assert (
                prom_name in grafana_docs_content
            ), f"Missing Prometheus metric name: {prom_name}"

    def test_ac5_3_dimensions_listed(self, grafana_docs_content: str) -> None:
        """AC5.3: All 4 dimension constants are listed."""
        for dim in METRIC_DIMENSIONS:
            assert dim in grafana_docs_content, f"Missing metric dimension: {dim}"

    def test_ac5_4_span_names_listed(self, grafana_docs_content: str) -> None:
        """AC5.4: All 5 span types are listed."""
        for span in SPAN_NAMES:
            assert span in grafana_docs_content, f"Missing span name: {span}"


# ===========================================================================
# AC6: Template Variable Customization (Story 6)
# ===========================================================================


class TestAC6_Customization:
    """AC6: Cost variables and provider/model filtering documented."""

    def test_ac6_1_cost_variables(self, grafana_docs_content: str) -> None:
        """AC6.1: Cost variables with defaults documented."""
        assert "cost_per_input_token" in grafana_docs_content
        assert "cost_per_output_token" in grafana_docs_content
        assert "0.000003" in grafana_docs_content
        assert "0.000015" in grafana_docs_content

    def test_ac6_2_provider_model_filtering(self, grafana_docs_content: str) -> None:
        """AC6.2: Provider/model filtering documented."""
        content_lower = grafana_docs_content.lower()
        assert "provider" in content_lower
        assert "model" in content_lower
        assert "multi" in content_lower or "dropdown" in content_lower


# ===========================================================================
# AC7: Troubleshooting (Story 7)
# ===========================================================================


class TestAC7_Troubleshooting:
    """AC7: Troubleshooting section with 5+ items and diagnostics."""

    def test_ac7_1_minimum_items(self, grafana_docs_content: str) -> None:
        """AC7.1: At least 5 troubleshooting items covering required areas."""
        # Extract the troubleshooting section
        ts_start = grafana_docs_content.find("## Troubleshooting")
        assert ts_start >= 0, "Troubleshooting section not found"

        # Find the next ## heading (or end of file)
        ts_section = grafana_docs_content[ts_start:]
        next_h2 = ts_section.find("\n## ", 1)
        if next_h2 > 0:
            ts_section = ts_section[:next_h2]

        # Count bold headings (symptom items) -- e.g., **Metrics not appearing**
        items = re.findall(r"\*\*[^*]+\*\*", ts_section)
        assert (
            len(items) >= 5
        ), f"Expected at least 5 troubleshooting items, found {len(items)}"

    def test_ac7_1_covers_metrics_not_appearing(
        self, grafana_docs_content: str
    ) -> None:
        """AC7.1a: Covers metrics not appearing in Prometheus."""
        ts_start = grafana_docs_content.find("## Troubleshooting")
        ts_section = grafana_docs_content[ts_start:].lower()
        assert "metrics" in ts_section and (
            "prometheus" in ts_section or "not appearing" in ts_section
        )

    def test_ac7_1_covers_traces_not_appearing(self, grafana_docs_content: str) -> None:
        """AC7.1b: Covers traces not appearing in Tempo."""
        ts_start = grafana_docs_content.find("## Troubleshooting")
        ts_section = grafana_docs_content[ts_start:].lower()
        assert "traces" in ts_section or "tempo" in ts_section

    def test_ac7_1_covers_no_data(self, grafana_docs_content: str) -> None:
        """AC7.1c: Covers dashboard panels showing 'No data'."""
        ts_start = grafana_docs_content.find("## Troubleshooting")
        ts_section = grafana_docs_content[ts_start:].lower()
        assert "no data" in ts_section

    def test_ac7_1_covers_cost_panels(self, grafana_docs_content: str) -> None:
        """AC7.1e: Covers cost panels showing zero."""
        ts_start = grafana_docs_content.find("## Troubleshooting")
        ts_section = grafana_docs_content[ts_start:].lower()
        assert "cost" in ts_section

    def test_ac7_2_diagnostic_commands(self, grafana_docs_content: str) -> None:
        """AC7.2: Troubleshooting items include diagnostic commands."""
        ts_start = grafana_docs_content.find("## Troubleshooting")
        ts_section = grafana_docs_content[ts_start:]

        # Check for code blocks (diagnostic commands) in troubleshooting
        code_blocks = re.findall(r"```", ts_section)
        assert (
            len(code_blocks) >= 2
        ), "Expected at least 1 code block (diagnostic command) in troubleshooting"


# ===========================================================================
# AC8: Dashboard Directory README (Story 8)
# ===========================================================================


class TestAC8_DashboardREADME:
    """AC8: Dashboard directory README completeness."""

    def test_ac8_1_readme_structure(self, readme_content: str) -> None:
        """AC8.1: README has description, file listing, requirements, import."""
        content_lower = readme_content.lower()
        # One-paragraph description
        assert "agentmap" in content_lower
        assert "grafana" in content_lower
        # File listing
        assert "agentmap-llm-operations.json" in readme_content
        assert "agentmap-workflow-explorer.json" in readme_content
        # Infrastructure requirements
        assert "Grafana" in readme_content
        assert "Prometheus" in readme_content
        assert "Tempo" in readme_content
        # Quick import
        assert "import" in content_lower

    def test_ac8_2_dashboard_descriptions(self, readme_content: str) -> None:
        """AC8.2: Each dashboard has a 1-2 sentence description."""
        # LLM Operations described
        assert "LLM" in readme_content
        # Workflow Explorer described
        assert "Workflow" in readme_content

    def test_ac8_3_docusaurus_link(self, readme_content: str) -> None:
        """AC8.3: README links to Docusaurus page."""
        assert (
            "13-grafana-dashboards" in readme_content
            or "grafana-dashboards" in readme_content
        )


# ===========================================================================
# Contract 7: Cross-Reference Updates
# ===========================================================================


class TestContract7_CrossReferences:
    """Cross-reference updates to existing OTEL docs."""

    def test_embedded_next_steps_grafana_link(self, otel_embedded_content: str) -> None:
        """11-otel-embedded.md Next Steps includes Grafana Dashboards link."""
        assert "Grafana Dashboards" in otel_embedded_content
        assert "grafana-dashboards" in otel_embedded_content

    def test_embedded_metrics_cache_hit(self, otel_embedded_content: str) -> None:
        """11-otel-embedded.md metrics table includes cache_hit."""
        assert "agentmap.llm.routing.cache_hit" in otel_embedded_content

    def test_embedded_metrics_circuit_breaker(self, otel_embedded_content: str) -> None:
        """11-otel-embedded.md metrics table includes circuit_breaker."""
        assert "agentmap.llm.circuit_breaker" in otel_embedded_content

    def test_standalone_next_steps_grafana_link(
        self, otel_standalone_content: str
    ) -> None:
        """12-otel-standalone.md Next Steps includes Grafana Dashboards link."""
        assert "Grafana Dashboards" in otel_standalone_content
        assert "grafana-dashboards" in otel_standalone_content

    def test_standalone_metrics_cache_hit(self, otel_standalone_content: str) -> None:
        """12-otel-standalone.md metrics table includes cache_hit."""
        assert "agentmap.llm.routing.cache_hit" in otel_standalone_content

    def test_standalone_metrics_circuit_breaker(
        self, otel_standalone_content: str
    ) -> None:
        """12-otel-standalone.md metrics table includes circuit_breaker."""
        assert "agentmap.llm.circuit_breaker" in otel_standalone_content


# ===========================================================================
# ADR-T005-002: Minimal Addition Pattern
# ===========================================================================


class TestADR_MinimalAdditionPattern:
    """ADR-T005-002: Both additive and standalone collector configs present."""

    def test_add_to_existing_section(self, grafana_docs_content: str) -> None:
        """Docs have 'Add to Existing Collector' section."""
        assert "### Add to Existing Collector" in grafana_docs_content

    def test_standalone_section(self, grafana_docs_content: str) -> None:
        """Docs have 'Complete Standalone Configuration' section."""
        assert "### Complete Standalone Configuration" in grafana_docs_content


# ===========================================================================
# ADR-T005-003: Page style matches existing OTEL pages
# ===========================================================================


class TestADR_PageStyleConsistency:
    """ADR-T005-003: New page follows existing OTEL page conventions."""

    def test_uses_mdx_breadcrumb(self, grafana_docs_content: str) -> None:
        """Page uses JSX-style breadcrumb div (MDX format)."""
        assert "style={{" in grafana_docs_content

    def test_next_steps_uses_relative_links(self, grafana_docs_content: str) -> None:
        """Next Steps links use relative Docusaurus paths."""
        assert "./otel-embedded" in grafana_docs_content
        assert "./otel-standalone" in grafana_docs_content


# ===========================================================================
# Security: TLS Note
# ===========================================================================


class TestSecurity:
    """Security considerations in documentation."""

    def test_tls_callout(self, grafana_docs_content: str) -> None:
        """Documentation includes TLS note for production."""
        content_lower = grafana_docs_content.lower()
        assert "tls" in content_lower


# ===========================================================================
# Edge Case: Prometheus-only users
# ===========================================================================


class TestEdgeCases:
    """Edge case documentation."""

    def test_prometheus_only_clarification(self, grafana_docs_content: str) -> None:
        """Docs clarify LLM Ops works with Prometheus only."""
        # Should mention LLM Operations works without Tempo
        content_lower = grafana_docs_content.lower()
        assert "prometheus" in content_lower
        # Should clarify which dashboard needs what
        assert "requires" in content_lower or "only" in content_lower

    def test_grafana_cloud_note(self, grafana_docs_content: str) -> None:
        """Docs mention Grafana Cloud limitations for provisioning."""
        assert "Grafana Cloud" in grafana_docs_content
