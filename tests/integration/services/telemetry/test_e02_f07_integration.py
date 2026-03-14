"""Integration tests for E02-F07 LLM Metrics Instrumentation.

These tests verify end-to-end metrics recording using InMemoryMetricReader
with the real OTEL SDK. Tests confirm that LLM calls produce real metric
data points with correct instrument names, values, and dimension attributes.

Test IDs: INT-700 through INT-730 (task T-E02-F07-003).

Requires ``opentelemetry-sdk`` to be installed.  The entire module is
skipped automatically when the SDK is unavailable.
"""

from __future__ import annotations

from unittest.mock import MagicMock, create_autospec

import pytest

# ---------------------------------------------------------------------------
# Graceful skip when OTEL SDK is not installed
# ---------------------------------------------------------------------------
try:
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    _sdk_available = True
except ImportError:
    _sdk_available = False

pytestmark = pytest.mark.skipif(
    not _sdk_available,
    reason="opentelemetry-sdk not installed -- skipping OTEL integration tests",
)

from agentmap.services.telemetry.constants import (  # noqa: E402
    METRIC_DIM_ERROR_TYPE,
    METRIC_DIM_MODEL,
    METRIC_DIM_PROVIDER,
    METRIC_DIM_TIER,
    METRIC_LLM_CIRCUIT_BREAKER,
    METRIC_LLM_DURATION,
    METRIC_LLM_ERRORS,
    METRIC_LLM_FALLBACK,
    METRIC_LLM_ROUTING_CACHE_HIT,
    METRIC_LLM_TOKENS_INPUT,
    METRIC_LLM_TOKENS_OUTPUT,
)
from agentmap.services.telemetry.noop_telemetry_service import (  # noqa: E402
    NoOpTelemetryService,
)
from agentmap.services.telemetry.otel_telemetry_service import (  # noqa: E402
    OTELTelemetryService,
)
from agentmap.services.telemetry.protocol import (  # noqa: E402
    TelemetryServiceProtocol,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_metric(metrics_data, metric_name):
    """Find a metric by name in InMemoryMetricReader output.

    Returns the metric object or None.
    """
    for resource_metrics in metrics_data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name == metric_name:
                    return metric
    return None


def _get_data_points(metric):
    """Extract data points from a metric, handling both Sum and Histogram."""
    if metric is None:
        return []
    data = metric.data
    if hasattr(data, "data_points"):
        return list(data.data_points)
    return []


def _make_mock_llm_response(
    content="test response",
    input_tokens=None,
    output_tokens=None,
):
    """Create a mock LLM response with optional token usage metadata."""
    response = MagicMock()
    response.content = content

    if input_tokens is not None or output_tokens is not None:
        usage = {}
        if input_tokens is not None:
            usage["input_tokens"] = input_tokens
        if output_tokens is not None:
            usage["output_tokens"] = output_tokens
        response.usage_metadata = usage
    else:
        response.usage_metadata = None

    response.response_metadata = {}
    return response


def _make_llm_service(telemetry_service=None):
    """Create an LLMService with mocked dependencies and optional telemetry.

    Returns (llm_service, mock_client) so tests can control the client.
    """
    from agentmap.services.config.app_config_service import AppConfigService
    from agentmap.services.config.llm_models_config_service import (
        LLMModelsConfigService,
    )
    from agentmap.services.llm_service import LLMService
    from agentmap.services.logging_service import LoggingService
    from agentmap.services.routing.routing_service import LLMRoutingService

    mock_config = create_autospec(AppConfigService, instance=True)
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {"max_attempts": 1, "backoff_base": 0.01, "backoff_max": 0.01},
        "circuit_breaker": {"failure_threshold": 5, "reset_timeout": 60},
    }
    mock_logging = create_autospec(LoggingService, instance=True)
    mock_logging.get_class_logger.return_value = MagicMock()
    mock_routing = create_autospec(LLMRoutingService, instance=True)
    mock_models = create_autospec(LLMModelsConfigService, instance=True)

    svc = LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing,
        llm_models_config_service=mock_models,
        telemetry_service=telemetry_service,
    )

    # Create a mock client and patch the factory to return it
    mock_client = MagicMock()
    svc._client_factory.get_or_create_client = MagicMock(return_value=mock_client)

    # Mock provider utils to return config
    svc._provider_utils.normalize_provider = MagicMock(side_effect=lambda p: p)
    svc._provider_utils.get_provider_config = MagicMock(
        return_value={"model": "claude-3-sonnet"}
    )
    svc._provider_utils.get_available_providers = MagicMock(return_value=["anthropic"])

    return svc, mock_client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _otel_metrics_provider():
    """Create a per-test MeterProvider + InMemoryMetricReader pair."""
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return reader, provider


@pytest.fixture()
def telemetry_service_with_metrics(_otel_metrics_provider):
    """Create a real OTELTelemetryService with meter from test provider."""
    reader, provider = _otel_metrics_provider
    svc = OTELTelemetryService()
    svc._meter = provider.get_meter("agentmap")
    return svc, reader


@pytest.fixture()
def _otel_full_provider():
    """Create both TracerProvider and MeterProvider for coexistence tests."""
    # Tracing
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))

    # Metrics
    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])

    return span_exporter, tracer_provider, metric_reader, meter_provider


@pytest.fixture()
def telemetry_service_full(_otel_full_provider):
    """OTELTelemetryService with both tracer and meter from test providers."""
    span_exporter, tracer_provider, metric_reader, meter_provider = _otel_full_provider
    svc = OTELTelemetryService()
    svc._tracer = tracer_provider.get_tracer("agentmap")
    svc._meter = meter_provider.get_meter("agentmap")
    return svc, span_exporter, metric_reader


# ---------------------------------------------------------------------------
# INT-700: End-to-end LLM metrics with InMemoryMetricReader
# ---------------------------------------------------------------------------


class TestEndToEndLLMMetrics:
    """INT-700: Verify LLM metrics recorded via real OTEL SDK."""

    def test_duration_histogram_recorded(
        self,
        telemetry_service_with_metrics,
    ) -> None:
        """INT-700: agentmap.llm.duration histogram has data point."""
        svc, reader = telemetry_service_with_metrics
        llm_svc, mock_client = _make_llm_service(telemetry_service=svc)

        mock_response = _make_mock_llm_response(input_tokens=340, output_tokens=907)
        mock_client.invoke.return_value = mock_response

        llm_svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        metrics_data = reader.get_metrics_data()
        duration_metric = _find_metric(metrics_data, METRIC_LLM_DURATION)
        assert (
            duration_metric is not None
        ), f"Expected '{METRIC_LLM_DURATION}' metric to be recorded"

        points = _get_data_points(duration_metric)
        assert len(points) >= 1, "Expected at least one duration data point"

        # Verify attributes contain provider and model
        point = points[0]
        attrs = dict(point.attributes)
        assert attrs.get(METRIC_DIM_PROVIDER) == "anthropic"
        assert attrs.get(METRIC_DIM_MODEL) == "claude-3-sonnet"

    def test_input_token_counter_recorded(
        self,
        telemetry_service_with_metrics,
    ) -> None:
        """INT-700: agentmap.llm.tokens.input counter sum equals 340."""
        svc, reader = telemetry_service_with_metrics
        llm_svc, mock_client = _make_llm_service(telemetry_service=svc)

        mock_response = _make_mock_llm_response(input_tokens=340, output_tokens=907)
        mock_client.invoke.return_value = mock_response

        llm_svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        metrics_data = reader.get_metrics_data()
        input_metric = _find_metric(metrics_data, METRIC_LLM_TOKENS_INPUT)
        assert (
            input_metric is not None
        ), f"Expected '{METRIC_LLM_TOKENS_INPUT}' metric to be recorded"

        points = _get_data_points(input_metric)
        assert len(points) >= 1
        # Sum should be 340
        total = sum(p.value for p in points)
        assert total == 340, f"Expected input token sum 340, got {total}"

        # Verify attributes
        attrs = dict(points[0].attributes)
        assert attrs.get(METRIC_DIM_PROVIDER) == "anthropic"
        assert attrs.get(METRIC_DIM_MODEL) == "claude-3-sonnet"

    def test_output_token_counter_recorded(
        self,
        telemetry_service_with_metrics,
    ) -> None:
        """INT-700: agentmap.llm.tokens.output counter sum equals 907."""
        svc, reader = telemetry_service_with_metrics
        llm_svc, mock_client = _make_llm_service(telemetry_service=svc)

        mock_response = _make_mock_llm_response(input_tokens=340, output_tokens=907)
        mock_client.invoke.return_value = mock_response

        llm_svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        metrics_data = reader.get_metrics_data()
        output_metric = _find_metric(metrics_data, METRIC_LLM_TOKENS_OUTPUT)
        assert (
            output_metric is not None
        ), f"Expected '{METRIC_LLM_TOKENS_OUTPUT}' metric to be recorded"

        points = _get_data_points(output_metric)
        assert len(points) >= 1
        total = sum(p.value for p in points)
        assert total == 907, f"Expected output token sum 907, got {total}"

        attrs = dict(points[0].attributes)
        assert attrs.get(METRIC_DIM_PROVIDER) == "anthropic"
        assert attrs.get(METRIC_DIM_MODEL) == "claude-3-sonnet"


# ---------------------------------------------------------------------------
# INT-701: Error metrics with real OTEL SDK
# ---------------------------------------------------------------------------


class TestErrorMetrics:
    """INT-701: Verify error counter with error_type dimension on failure."""

    def test_error_counter_on_timeout(
        self,
        telemetry_service_with_metrics,
    ) -> None:
        """INT-701: agentmap.llm.errors counter incremented on timeout."""
        svc, reader = telemetry_service_with_metrics
        llm_svc, mock_client = _make_llm_service(telemetry_service=svc)

        # Simulate a timeout error
        mock_client.invoke.side_effect = TimeoutError("Request timed out")

        with pytest.raises(Exception):
            llm_svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )

        metrics_data = reader.get_metrics_data()
        error_metric = _find_metric(metrics_data, METRIC_LLM_ERRORS)
        assert (
            error_metric is not None
        ), f"Expected '{METRIC_LLM_ERRORS}' metric to be recorded"

        points = _get_data_points(error_metric)
        assert len(points) >= 1, "Expected at least one error data point"

        total = sum(p.value for p in points)
        assert total == 1, f"Expected error count 1, got {total}"

        # Verify attributes include error_type, provider, model
        attrs = dict(points[0].attributes)
        assert (
            METRIC_DIM_ERROR_TYPE in attrs
        ), "Expected error_type dimension in error metric"
        assert attrs.get(METRIC_DIM_PROVIDER) == "anthropic"
        assert attrs.get(METRIC_DIM_MODEL) == "claude-3-sonnet"


# ---------------------------------------------------------------------------
# INT-702: No MeterProvider -- automatic no-op
# ---------------------------------------------------------------------------


class TestNoMeterProvider:
    """INT-702: Verify no exceptions when no MeterProvider is configured."""

    def test_no_exception_without_meter_provider(self) -> None:
        """INT-702: LLM call succeeds with OTEL service but no MeterProvider.

        When OTELTelemetryService is created without configuring a
        MeterProvider, the OTEL API returns built-in no-op instruments.
        The LLM call should complete normally.
        """
        # Create a service using default (no-op) MeterProvider
        svc = OTELTelemetryService()
        llm_svc, mock_client = _make_llm_service(telemetry_service=svc)

        mock_response = _make_mock_llm_response(input_tokens=100, output_tokens=50)
        mock_client.invoke.return_value = mock_response

        # Should not raise any exception
        result = llm_svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )
        assert result == "test response"

    def test_no_exception_with_noop_telemetry(self) -> None:
        """INT-702: LLM call succeeds with NoOpTelemetryService."""
        noop = NoOpTelemetryService()
        llm_svc, mock_client = _make_llm_service(telemetry_service=noop)

        mock_response = _make_mock_llm_response(input_tokens=100, output_tokens=50)
        mock_client.invoke.return_value = mock_response

        result = llm_svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )
        assert result == "test response"

    def test_no_exception_with_none_telemetry(self) -> None:
        """INT-702: LLM call succeeds with telemetry_service=None."""
        llm_svc, mock_client = _make_llm_service(telemetry_service=None)

        mock_response = _make_mock_llm_response(input_tokens=100, output_tokens=50)
        mock_client.invoke.return_value = mock_response

        result = llm_svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )
        assert result == "test response"


# ---------------------------------------------------------------------------
# INT-703: Routing cache hit and fallback counters
# ---------------------------------------------------------------------------


class TestRoutingMetrics:
    """INT-703: Verify routing-related counters with real OTEL SDK."""

    def test_cache_hit_counter(
        self,
        telemetry_service_with_metrics,
    ) -> None:
        """INT-703: agentmap.llm.routing.cache_hit counter incremented."""
        svc, reader = telemetry_service_with_metrics
        llm_svc, mock_client = _make_llm_service(telemetry_service=svc)

        # Directly call the cache hit metric to simulate routing cache hit
        if hasattr(llm_svc, "_metric_cache_hit"):
            llm_svc._metric_cache_hit.add(1)

        metrics_data = reader.get_metrics_data()
        cache_metric = _find_metric(metrics_data, METRIC_LLM_ROUTING_CACHE_HIT)
        assert (
            cache_metric is not None
        ), f"Expected '{METRIC_LLM_ROUTING_CACHE_HIT}' metric"

        points = _get_data_points(cache_metric)
        assert len(points) >= 1
        total = sum(p.value for p in points)
        assert total == 1, f"Expected cache hit count 1, got {total}"

    def test_fallback_counter_with_tier(
        self,
        telemetry_service_with_metrics,
    ) -> None:
        """INT-703: agentmap.llm.fallback counter with tier attribute."""
        svc, reader = telemetry_service_with_metrics
        llm_svc, mock_client = _make_llm_service(telemetry_service=svc)

        # Directly call the fallback metric to simulate tier-2 fallback
        if hasattr(llm_svc, "_metric_fallback"):
            llm_svc._metric_fallback.add(1, {METRIC_DIM_TIER: "2"})

        metrics_data = reader.get_metrics_data()
        fallback_metric = _find_metric(metrics_data, METRIC_LLM_FALLBACK)
        assert fallback_metric is not None, f"Expected '{METRIC_LLM_FALLBACK}' metric"

        points = _get_data_points(fallback_metric)
        assert len(points) >= 1
        total = sum(p.value for p in points)
        assert total == 1, f"Expected fallback count 1, got {total}"

        attrs = dict(points[0].attributes)
        assert attrs.get(METRIC_DIM_TIER) == "2"

    def test_circuit_breaker_up_down_counter(
        self,
        telemetry_service_with_metrics,
    ) -> None:
        """INT-703: agentmap.llm.circuit_breaker UpDownCounter works."""
        svc, reader = telemetry_service_with_metrics
        llm_svc, mock_client = _make_llm_service(telemetry_service=svc)

        # Simulate circuit open then close
        if hasattr(llm_svc, "_metric_circuit_breaker"):
            llm_svc._metric_circuit_breaker.add(1)  # open
            llm_svc._metric_circuit_breaker.add(-1)  # close

        metrics_data = reader.get_metrics_data()
        cb_metric = _find_metric(metrics_data, METRIC_LLM_CIRCUIT_BREAKER)
        assert cb_metric is not None, f"Expected '{METRIC_LLM_CIRCUIT_BREAKER}' metric"

        points = _get_data_points(cb_metric)
        assert len(points) >= 1
        # Net effect should be 0 (opened then closed)
        total = sum(p.value for p in points)
        assert total == 0, f"Expected net circuit breaker count 0, got {total}"


# ---------------------------------------------------------------------------
# INT-710: Protocol backward compatibility
# ---------------------------------------------------------------------------


class TestProtocolBackwardCompatibility:
    """INT-710: Existing protocol consumers unaffected by extension."""

    def test_otel_service_satisfies_protocol(self) -> None:
        """INT-710: OTELTelemetryService satisfies extended protocol."""
        svc = OTELTelemetryService()
        assert isinstance(svc, TelemetryServiceProtocol)

    def test_noop_service_satisfies_protocol(self) -> None:
        """INT-710: NoOpTelemetryService satisfies extended protocol."""
        svc = NoOpTelemetryService()
        assert isinstance(svc, TelemetryServiceProtocol)

    def test_existing_tracing_methods_unchanged(self) -> None:
        """INT-710: Existing tracing methods still work on both services."""
        for svc in [OTELTelemetryService(), NoOpTelemetryService()]:
            # All five existing methods should exist and be callable
            assert hasattr(svc, "start_span")
            assert hasattr(svc, "record_exception")
            assert hasattr(svc, "set_span_attributes")
            assert hasattr(svc, "add_span_event")
            assert hasattr(svc, "get_tracer")

            # Metrics methods should also exist
            assert hasattr(svc, "get_meter")
            assert hasattr(svc, "create_counter")
            assert hasattr(svc, "create_histogram")
            assert hasattr(svc, "create_up_down_counter")

    def test_noop_start_span_still_works(self) -> None:
        """INT-710: NoOp start_span still returns context manager."""
        noop = NoOpTelemetryService()
        with noop.start_span("test.span") as span:
            noop.set_span_attributes(span, {"key": "value"})
            noop.add_span_event(span, "test.event")
        # No exception means it works


# ---------------------------------------------------------------------------
# INT-711: Tracing and metrics coexistence
# ---------------------------------------------------------------------------


class TestTracingAndMetricsCoexistence:
    """INT-711: Both span and metric data collected simultaneously."""

    def test_span_and_metrics_coexist(
        self,
        telemetry_service_full,
    ) -> None:
        """INT-711: Span creation and metric recording both succeed."""
        svc, span_exporter, metric_reader = telemetry_service_full

        # Create an LLM service with the full telemetry service
        llm_svc, mock_client = _make_llm_service(telemetry_service=svc)

        mock_response = _make_mock_llm_response(input_tokens=100, output_tokens=50)
        mock_client.invoke.return_value = mock_response

        # Make the LLM call -- this should produce both spans and metrics
        result = llm_svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )
        assert result == "test response"

        # Verify span was created (tracing still works)
        spans = span_exporter.get_finished_spans()
        assert len(spans) >= 1, "Expected at least one span from LLM call"

        # Verify metrics were recorded (metrics also work)
        metrics_data = metric_reader.get_metrics_data()
        duration_metric = _find_metric(metrics_data, METRIC_LLM_DURATION)
        assert (
            duration_metric is not None
        ), "Expected duration metric recorded alongside span"

    def test_span_error_and_error_metric_coexist(
        self,
        telemetry_service_full,
    ) -> None:
        """INT-711: Error span and error metric both recorded on failure."""
        svc, span_exporter, metric_reader = telemetry_service_full
        llm_svc, mock_client = _make_llm_service(telemetry_service=svc)

        mock_client.invoke.side_effect = TimeoutError("timed out")

        with pytest.raises(Exception):
            llm_svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )

        # Verify span was created
        spans = span_exporter.get_finished_spans()
        assert len(spans) >= 1, "Expected at least one span"

        # Verify error metric was recorded
        metrics_data = metric_reader.get_metrics_data()
        error_metric = _find_metric(metrics_data, METRIC_LLM_ERRORS)
        assert (
            error_metric is not None
        ), "Expected error metric recorded alongside error span"


# ---------------------------------------------------------------------------
# INT-720: DI container resolves service with metrics methods
# ---------------------------------------------------------------------------


class TestDIContainerResolution:
    """INT-720: DI container resolves extended telemetry service."""

    def test_di_resolves_service_with_metrics_methods(self) -> None:
        """INT-720: Resolved service has both tracing and metrics methods."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_ls = MagicMock()
        mock_ls.get_logger.return_value = MagicMock()
        container = TelemetryContainer(logging_service=mock_ls)
        svc = container.telemetry_service()

        assert isinstance(svc, TelemetryServiceProtocol)

        # Tracing methods
        assert hasattr(svc, "start_span")
        assert hasattr(svc, "get_tracer")

        # Metrics methods
        assert hasattr(svc, "create_counter")
        assert hasattr(svc, "create_histogram")
        assert hasattr(svc, "create_up_down_counter")
        assert hasattr(svc, "get_meter")

    def test_di_singleton_identity(self) -> None:
        """INT-720: Same singleton for tracing and metrics consumers."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_ls = MagicMock()
        mock_ls.get_logger.return_value = MagicMock()
        container = TelemetryContainer(logging_service=mock_ls)

        svc1 = container.telemetry_service()
        svc2 = container.telemetry_service()
        assert svc1 is svc2

    def test_di_resolved_service_creates_instruments(self) -> None:
        """INT-720: Resolved service can create metric instruments."""
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        mock_ls = MagicMock()
        mock_ls.get_logger.return_value = MagicMock()
        container = TelemetryContainer(logging_service=mock_ls)
        svc = container.telemetry_service()

        # Should not raise
        counter = svc.create_counter("test.counter", unit="1")
        histogram = svc.create_histogram("test.hist", unit="s")
        udc = svc.create_up_down_counter("test.udc", unit="1")

        assert counter is not None
        assert histogram is not None
        assert udc is not None

        # Instruments should support their respective methods
        counter.add(1)
        histogram.record(0.5)
        udc.add(1)
        udc.add(-1)
