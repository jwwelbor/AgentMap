"""Unit tests for OTELTelemetryService (mocked OTEL, no SDK required)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agentmap.services.telemetry.protocol import TelemetryServiceProtocol


class TestOTELTelemetryService:
    """TC-010 through TC-016, TC-070, TC-072."""

    def _make_service(self, mock_tracer: MagicMock | None = None) -> object:
        """Create an OTELTelemetryService with a mocked tracer."""
        if mock_tracer is None:
            mock_tracer = MagicMock()
        with patch(
            "agentmap.services.telemetry.otel_telemetry_service.trace"
        ) as mock_trace:
            mock_trace.get_tracer.return_value = mock_tracer
            # Re-import to get fresh instance
            from agentmap.services.telemetry.otel_telemetry_service import (
                OTELTelemetryService,
            )

            svc = OTELTelemetryService()
        # Patch the tracer to use our mock
        svc._tracer = mock_tracer
        return svc

    def test_constructor_calls_get_tracer(self) -> None:
        """TC-010: Constructor calls get_tracer with correct args."""
        with patch(
            "agentmap.services.telemetry.otel_telemetry_service.trace"
        ) as mock_trace:
            mock_trace.get_tracer.return_value = MagicMock()
            from agentmap.services.telemetry.otel_telemetry_service import (
                OTELTelemetryService,
            )

            svc = OTELTelemetryService()
            mock_trace.get_tracer.assert_called_once()
            call_args = mock_trace.get_tracer.call_args
            assert call_args[0][0] == "agentmap"
            # instrumenting_library_version keyword argument should be a string
            assert isinstance(
                call_args[1].get("instrumenting_library_version", ""), str
            )

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
