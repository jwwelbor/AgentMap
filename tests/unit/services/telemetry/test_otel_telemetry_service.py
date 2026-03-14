"""Unit tests for OTELTelemetryService (mocked OTEL, no SDK required)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agentmap.services.telemetry.noop_telemetry_service import (
    _NOOP_COUNTER,
    _NOOP_HISTOGRAM,
    _NOOP_UP_DOWN_COUNTER,
)
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol


class TestOTELTelemetryService:
    """TC-010 through TC-016, TC-070, TC-072."""

    def _make_service(
        self,
        mock_tracer: MagicMock | None = None,
        mock_meter: MagicMock | None = None,
    ) -> object:
        """Create an OTELTelemetryService with mocked tracer and meter."""
        if mock_tracer is None:
            mock_tracer = MagicMock()
        if mock_meter is None:
            mock_meter = MagicMock()
        with (
            patch(
                "agentmap.services.telemetry.otel_telemetry_service.trace"
            ) as mock_trace,
            patch(
                "agentmap.services.telemetry.otel_telemetry_service.metrics"
            ) as mock_metrics,
        ):
            mock_trace.get_tracer.return_value = mock_tracer
            mock_metrics.get_meter.return_value = mock_meter
            from agentmap.services.telemetry.otel_telemetry_service import (
                OTELTelemetryService,
            )

            svc = OTELTelemetryService()
        # Patch to use our mocks
        svc._tracer = mock_tracer
        svc._meter = mock_meter
        return svc

    def test_constructor_calls_get_tracer(self) -> None:
        """TC-010: Constructor calls get_tracer with correct args."""
        with (
            patch(
                "agentmap.services.telemetry.otel_telemetry_service.trace"
            ) as mock_trace,
            patch(
                "agentmap.services.telemetry.otel_telemetry_service.metrics"
            ) as mock_metrics,
        ):
            mock_trace.get_tracer.return_value = MagicMock()
            mock_metrics.get_meter.return_value = MagicMock()
            from agentmap.services.telemetry.otel_telemetry_service import (
                OTELTelemetryService,
            )

            OTELTelemetryService()
            mock_trace.get_tracer.assert_called_once()
            call_args = mock_trace.get_tracer.call_args
            assert call_args[0][0] == "agentmap"
            # instrumenting_library_version keyword argument should be a string
            assert isinstance(
                call_args[1].get("instrumenting_library_version", ""), str
            )

    def test_constructor_calls_get_meter(self) -> None:
        """Constructor calls metrics.get_meter with correct args."""
        with (
            patch(
                "agentmap.services.telemetry.otel_telemetry_service.trace"
            ) as mock_trace,
            patch(
                "agentmap.services.telemetry.otel_telemetry_service.metrics"
            ) as mock_metrics,
        ):
            mock_trace.get_tracer.return_value = MagicMock()
            mock_metrics.get_meter.return_value = MagicMock()
            from agentmap.services.telemetry.otel_telemetry_service import (
                OTELTelemetryService,
            )

            svc = OTELTelemetryService()
            mock_metrics.get_meter.assert_called_once()
            call_args = mock_metrics.get_meter.call_args
            assert call_args[0][0] == "agentmap"
            assert svc._meter is not None

    def test_isinstance_protocol(self) -> None:
        """TC-011: OTELTelemetryService satisfies TelemetryServiceProtocol."""
        svc = self._make_service()
        assert isinstance(svc, TelemetryServiceProtocol)

    def test_start_span_delegates_to_tracer(self) -> None:
        """TC-012: start_span delegates to tracer.start_as_current_span."""
        mock_tracer = MagicMock()
        svc = self._make_service(mock_tracer)
        attrs = {"key": "value"}
        svc.start_span("test.span", attributes=attrs)
        mock_tracer.start_as_current_span.assert_called_once_with(
            "test.span", attributes=attrs
        )

    def test_start_span_with_kind(self) -> None:
        """start_span passes kind to tracer."""
        mock_tracer = MagicMock()
        svc = self._make_service(mock_tracer)
        svc.start_span("test.span", kind="SERVER")
        mock_tracer.start_as_current_span.assert_called_once_with(
            "test.span", kind="SERVER"
        )

    def test_record_exception_delegates(self) -> None:
        """TC-013: record_exception delegates and sets ERROR status."""
        svc = self._make_service()
        mock_span = MagicMock()
        exc = ValueError("test error")
        svc.record_exception(mock_span, exc)
        mock_span.record_exception.assert_called_once_with(exc)
        mock_span.set_status.assert_called_once()

    def test_set_span_attributes_iterates(self) -> None:
        """TC-014: set_span_attributes calls set_attribute per key."""
        svc = self._make_service()
        mock_span = MagicMock()
        attrs = {"key1": "val1", "key2": 42}
        svc.set_span_attributes(mock_span, attrs)
        assert mock_span.set_attribute.call_count == 2
        mock_span.set_attribute.assert_any_call("key1", "val1")
        mock_span.set_attribute.assert_any_call("key2", 42)

    def test_add_span_event_delegates(self) -> None:
        """TC-015: add_span_event delegates to span.add_event."""
        svc = self._make_service()
        mock_span = MagicMock()
        svc.add_span_event(mock_span, "my_event", {"k": "v"})
        mock_span.add_event.assert_called_once_with("my_event", attributes={"k": "v"})

    def test_get_tracer_returns_tracer(self) -> None:
        """TC-016: get_tracer returns the stored tracer."""
        mock_tracer = MagicMock()
        svc = self._make_service(mock_tracer)
        assert svc.get_tracer() is mock_tracer

    def test_set_span_attributes_catches_type_error(self) -> None:
        """TC-070: set_span_attributes catches TypeError, logs warning."""
        svc = self._make_service()
        mock_span = MagicMock()
        mock_span.set_attribute.side_effect = TypeError("bad type")
        # Should NOT raise
        svc.set_span_attributes(mock_span, {"bad_key": object()})

    def test_set_span_attributes_catches_value_error(self) -> None:
        """set_span_attributes catches ValueError."""
        svc = self._make_service()
        mock_span = MagicMock()
        mock_span.set_attribute.side_effect = ValueError("bad value")
        svc.set_span_attributes(mock_span, {"key": "val"})

    def test_record_exception_handles_errors(self) -> None:
        """TC-072: record_exception does not propagate telemetry errors."""
        svc = self._make_service()
        mock_span = MagicMock()
        mock_span.record_exception.side_effect = RuntimeError("otel fail")
        # Should NOT raise
        svc.record_exception(mock_span, ValueError("test"))

    def test_add_span_event_handles_errors(self) -> None:
        """add_span_event does not propagate errors."""
        svc = self._make_service()
        mock_span = MagicMock()
        mock_span.add_event.side_effect = RuntimeError("otel fail")
        # Should NOT raise
        svc.add_span_event(mock_span, "ev")

    # -- Metrics methods (T-E02-F07-001) ------------------------------------

    def test_get_meter_returns_meter(self) -> None:
        """get_meter returns an OTEL Meter object."""
        svc = self._make_service()
        with patch(
            "agentmap.services.telemetry.otel_telemetry_service.metrics"
        ) as mock_metrics:
            mock_meter = MagicMock()
            mock_metrics.get_meter.return_value = mock_meter
            result = svc.get_meter("test.meter", version="1.0")
            mock_metrics.get_meter.assert_called_once_with("test.meter", version="1.0")
            assert result is mock_meter

    def test_get_meter_default_version(self) -> None:
        """get_meter uses None as default version."""
        svc = self._make_service()
        with patch(
            "agentmap.services.telemetry.otel_telemetry_service.metrics"
        ) as mock_metrics:
            mock_meter = MagicMock()
            mock_metrics.get_meter.return_value = mock_meter
            svc.get_meter("test.meter")
            mock_metrics.get_meter.assert_called_once_with("test.meter", version=None)

    def test_create_counter_delegates_to_meter(self) -> None:
        """create_counter creates a counter via the stored meter."""
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_meter.create_counter.return_value = mock_counter
        svc = self._make_service(mock_meter=mock_meter)
        result = svc.create_counter(
            "test.counter", unit="1", description="A test counter"
        )
        mock_meter.create_counter.assert_called_once_with(
            "test.counter", unit="1", description="A test counter"
        )
        assert result is mock_counter

    def test_create_histogram_delegates_to_meter(self) -> None:
        """create_histogram creates a histogram via the stored meter."""
        mock_meter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter.create_histogram.return_value = mock_histogram
        svc = self._make_service(mock_meter=mock_meter)
        result = svc.create_histogram(
            "test.histogram", unit="ms", description="A test histogram"
        )
        mock_meter.create_histogram.assert_called_once_with(
            "test.histogram", unit="ms", description="A test histogram"
        )
        assert result is mock_histogram

    def test_create_up_down_counter_delegates_to_meter(self) -> None:
        """create_up_down_counter creates via the stored meter."""
        mock_meter = MagicMock()
        mock_udc = MagicMock()
        mock_meter.create_up_down_counter.return_value = mock_udc
        svc = self._make_service(mock_meter=mock_meter)
        result = svc.create_up_down_counter(
            "test.gauge", unit="1", description="A test gauge"
        )
        mock_meter.create_up_down_counter.assert_called_once_with(
            "test.gauge", unit="1", description="A test gauge"
        )
        assert result is mock_udc

    def test_create_counter_default_params(self) -> None:
        """create_counter uses empty string defaults for unit and description."""
        mock_meter = MagicMock()
        svc = self._make_service(mock_meter=mock_meter)
        svc.create_counter("test.counter")
        mock_meter.create_counter.assert_called_once_with(
            "test.counter", unit="", description=""
        )

    def test_metrics_methods_handle_errors_gracefully(self) -> None:
        """Metrics creation methods should not propagate exceptions."""
        svc = self._make_service()
        with patch(
            "agentmap.services.telemetry.otel_telemetry_service.metrics"
        ) as mock_metrics:
            mock_metrics.get_meter.side_effect = RuntimeError("otel fail")
            # get_meter should handle errors and return None
            result = svc.get_meter("bad")
            assert result is None

    # -- ISSUE-6: Error fallback to NoOp instruments -------------------------

    def test_create_counter_error_returns_noop_counter(self) -> None:
        """create_counter returns NoOp counter when OTEL raises."""
        mock_meter = MagicMock()
        mock_meter.create_counter.side_effect = RuntimeError("otel fail")
        svc = self._make_service(mock_meter=mock_meter)
        result = svc.create_counter("bad.counter")
        assert result is _NOOP_COUNTER

    def test_create_histogram_error_returns_noop_histogram(self) -> None:
        """create_histogram returns NoOp histogram when OTEL raises."""
        mock_meter = MagicMock()
        mock_meter.create_histogram.side_effect = RuntimeError("otel fail")
        svc = self._make_service(mock_meter=mock_meter)
        result = svc.create_histogram("bad.histogram")
        assert result is _NOOP_HISTOGRAM

    def test_create_up_down_counter_error_returns_noop_udc(self) -> None:
        """create_up_down_counter returns NoOp UDC when OTEL raises."""
        mock_meter = MagicMock()
        mock_meter.create_up_down_counter.side_effect = RuntimeError("otel fail")
        svc = self._make_service(mock_meter=mock_meter)
        result = svc.create_up_down_counter("bad.gauge")
        assert result is _NOOP_UP_DOWN_COUNTER
