"""Unit tests for NoOpTelemetryService."""

from __future__ import annotations

import contextlib
import inspect

import pytest

from agentmap.services.telemetry.noop_telemetry_service import (
    _NOOP_SPAN,
    NoOpTelemetryService,
)
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol


class TestNoOpTelemetryService:
    """TC-020 through TC-028, TC-071."""

    def test_isinstance_protocol(self) -> None:
        """TC-020: NoOpTelemetryService satisfies TelemetryServiceProtocol."""
        svc = NoOpTelemetryService()
        assert isinstance(svc, TelemetryServiceProtocol)

    def test_start_span_returns_context_manager_with_noop_span(self) -> None:
        """TC-021: start_span returns nullcontext yielding _NoOpSpan."""
        svc = NoOpTelemetryService()
        cm = svc.start_span("test.span")
        with cm as span:
            assert span is _NOOP_SPAN

    def test_noop_span_supports_all_methods(self) -> None:
        """TC-022: _NoOpSpan supports set_attribute, add_event, record_exception, set_status."""
        svc = NoOpTelemetryService()
        with svc.start_span("test.span") as span:
            # All calls should be silent no-ops -- no exceptions
            span.set_attribute("key", "value")
            span.add_event("event_name", {"attr": "val"})
            span.record_exception(ValueError("test"))
            span.set_status("OK")
            span.set_status("ERROR", "some description")

    def test_no_opentelemetry_imports(self) -> None:
        """TC-023: No opentelemetry imports in noop_telemetry_service.py source."""
        import agentmap.services.telemetry.noop_telemetry_service as mod

        source = inspect.getsource(mod)
        assert "opentelemetry" not in source

    def test_record_exception_is_noop(self) -> None:
        """TC-024: record_exception returns None and does nothing."""
        svc = NoOpTelemetryService()
        result = svc.record_exception(None, ValueError("test"))
        assert result is None

    def test_set_span_attributes_is_noop(self) -> None:
        """TC-025: set_span_attributes returns None and does nothing."""
        svc = NoOpTelemetryService()
        result = svc.set_span_attributes(None, {"key": "value"})
        assert result is None

    def test_add_span_event_is_noop(self) -> None:
        """TC-026: add_span_event returns None and does nothing."""
        svc = NoOpTelemetryService()
        result = svc.add_span_event(None, "event")
        assert result is None

    def test_get_tracer_returns_none(self) -> None:
        """TC-027: get_tracer returns None."""
        svc = NoOpTelemetryService()
        assert svc.get_tracer() is None

    def test_noop_span_reused(self) -> None:
        """TC-028: Pre-allocated _NOOP_SPAN is reused across calls (identity)."""
        svc = NoOpTelemetryService()
        with svc.start_span("span1") as span1:
            pass
        with svc.start_span("span2") as span2:
            pass
        assert span1 is span2
        assert span1 is _NOOP_SPAN

    def test_accepts_invalid_attribute_types_silently(self) -> None:
        """TC-071: NoOp accepts non-serializable attribute values."""
        svc = NoOpTelemetryService()
        # Should not raise
        svc.set_span_attributes(None, {"key": object(), 123: "value"})
        with svc.start_span("s") as span:
            span.set_attribute("key", object())
