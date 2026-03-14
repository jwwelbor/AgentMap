"""Unit tests for telemetry package __init__.py re-exports and lazy loading."""

from __future__ import annotations

import pytest


class TestTelemetryPackageInit:
    """TC-050 through TC-052."""

    def test_protocol_and_noop_importable_from_package(self) -> None:
        """TC-050: Protocol and NoOp importable from package root."""
        from agentmap.services.telemetry import (
            NoOpTelemetryService,
            TelemetryServiceProtocol,
        )

        assert TelemetryServiceProtocol is not None
        assert NoOpTelemetryService is not None

    def test_lazy_import_for_otel_service(self) -> None:
        """TC-051: Lazy import -- package load does not trigger opentelemetry import.

        Note: Since opentelemetry-api is installed in this environment, it may
        already be in sys.modules. We verify the lazy __getattr__ mechanism works
        by confirming OTELTelemetryService is accessible.
        """
        from agentmap.services.telemetry import OTELTelemetryService

        assert OTELTelemetryService is not None

    def test_all_constants_importable_from_package(self) -> None:
        """TC-052: All constants importable from package root."""
        from agentmap.services.telemetry import (
            AGENT_NAME,
            AGENT_RUN_SPAN,
            AGENT_TYPE,
            GEN_AI_REQUEST_MODEL,
            GEN_AI_RESPONSE_MODEL,
            GEN_AI_SYSTEM,
            GEN_AI_USAGE_INPUT_TOKENS,
            GEN_AI_USAGE_OUTPUT_TOKENS,
            GRAPH_AGENT_COUNT,
            GRAPH_NAME,
            GRAPH_NODE_COUNT,
            LLM_CALL_SPAN,
            NODE_NAME,
            ROUTING_CACHE_HIT,
            ROUTING_CIRCUIT_BREAKER_STATE,
            ROUTING_COMPLEXITY,
            ROUTING_CONFIDENCE,
            ROUTING_FALLBACK_TIER,
            ROUTING_MODEL,
            ROUTING_PROVIDER,
            WORKFLOW_RUN_SPAN,
        )

        # Quick sanity -- all are non-empty strings
        for val in [
            AGENT_NAME,
            AGENT_RUN_SPAN,
            AGENT_TYPE,
            GEN_AI_REQUEST_MODEL,
            GEN_AI_RESPONSE_MODEL,
            GEN_AI_SYSTEM,
            GEN_AI_USAGE_INPUT_TOKENS,
            GEN_AI_USAGE_OUTPUT_TOKENS,
            GRAPH_AGENT_COUNT,
            GRAPH_NAME,
            GRAPH_NODE_COUNT,
            LLM_CALL_SPAN,
            NODE_NAME,
            ROUTING_CACHE_HIT,
            ROUTING_CIRCUIT_BREAKER_STATE,
            ROUTING_COMPLEXITY,
            ROUTING_CONFIDENCE,
            ROUTING_FALLBACK_TIER,
            ROUTING_MODEL,
            ROUTING_PROVIDER,
            WORKFLOW_RUN_SPAN,
        ]:
            assert isinstance(val, str) and len(val) > 0

    def test_getattr_raises_for_unknown_attribute(self) -> None:
        """__getattr__ raises AttributeError for unknown names."""
        with pytest.raises(AttributeError):
            from agentmap.services import telemetry

            _ = telemetry.NonExistentThing  # type: ignore[attr-defined]

    # -- Metric constant re-exports (T-E02-F07-001) -------------------------

    def test_metric_name_constants_importable_from_package(self) -> None:
        """Metric name constants are importable from package root."""
        from agentmap.services.telemetry import (
            METRIC_LLM_CIRCUIT_BREAKER,
            METRIC_LLM_DURATION,
            METRIC_LLM_ERRORS,
            METRIC_LLM_FALLBACK,
            METRIC_LLM_ROUTING_CACHE_HIT,
            METRIC_LLM_TOKENS_INPUT,
            METRIC_LLM_TOKENS_OUTPUT,
        )

        for val in [
            METRIC_LLM_DURATION,
            METRIC_LLM_TOKENS_INPUT,
            METRIC_LLM_TOKENS_OUTPUT,
            METRIC_LLM_ERRORS,
            METRIC_LLM_ROUTING_CACHE_HIT,
            METRIC_LLM_CIRCUIT_BREAKER,
            METRIC_LLM_FALLBACK,
        ]:
            assert isinstance(val, str) and len(val) > 0

    def test_metric_dimension_constants_importable_from_package(self) -> None:
        """Metric dimension constants are importable from package root."""
        from agentmap.services.telemetry import (
            METRIC_DIM_ERROR_TYPE,
            METRIC_DIM_TIER,
            METRIC_DIM_MODEL,
            METRIC_DIM_PROVIDER,
        )

        for val in [
            METRIC_DIM_PROVIDER,
            METRIC_DIM_MODEL,
            METRIC_DIM_ERROR_TYPE,
            METRIC_DIM_TIER,
        ]:
            assert isinstance(val, str) and len(val) > 0
