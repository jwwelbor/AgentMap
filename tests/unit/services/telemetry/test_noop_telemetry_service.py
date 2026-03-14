"""Unit tests for NoOpTelemetryService."""

from __future__ import annotations

import inspect

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

    # -- Metrics methods (T-E02-F07-001) ------------------------------------

    def test_get_meter_returns_none(self) -> None:
        """get_meter returns None for NoOp implementation."""
        svc = NoOpTelemetryService()
        result = svc.get_meter("test.meter")
        assert result is None

    def test_create_counter_returns_noop_counter(self) -> None:
        """create_counter returns a no-op counter with add method."""
        svc = NoOpTelemetryService()
        counter = svc.create_counter("test.counter")
        assert counter is not None
        # Should have an add method that does nothing
        counter.add(1)
        counter.add(5, {"key": "value"})

    def test_create_histogram_returns_noop_histogram(self) -> None:
        """create_histogram returns a no-op histogram with record method."""
        svc = NoOpTelemetryService()
        histogram = svc.create_histogram("test.histogram")
        assert histogram is not None
        # Should have a record method that does nothing
        histogram.record(1.5)
        histogram.record(42.0, {"key": "value"})

    def test_create_up_down_counter_returns_noop_up_down_counter(self) -> None:
        """create_up_down_counter returns a no-op up-down counter with add method."""
        svc = NoOpTelemetryService()
        udc = svc.create_up_down_counter("test.gauge")
        assert udc is not None
        # Should have an add method that does nothing
        udc.add(1)
        udc.add(-1, {"key": "value"})

    def test_noop_counter_is_singleton(self) -> None:
        """NoOp counter instances are reused (singleton pattern)."""
        svc = NoOpTelemetryService()
        c1 = svc.create_counter("counter.a")
        c2 = svc.create_counter("counter.b")
        assert c1 is c2

    def test_noop_histogram_is_singleton(self) -> None:
        """NoOp histogram instances are reused (singleton pattern)."""
        svc = NoOpTelemetryService()
        h1 = svc.create_histogram("hist.a")
        h2 = svc.create_histogram("hist.b")
        assert h1 is h2

    def test_noop_up_down_counter_is_singleton(self) -> None:
        """NoOp up-down counter instances are reused (singleton pattern)."""
        svc = NoOpTelemetryService()
        u1 = svc.create_up_down_counter("udc.a")
        u2 = svc.create_up_down_counter("udc.b")
        assert u1 is u2

    def test_noop_instruments_satisfy_protocol_after_metrics_extension(self) -> None:
        """NoOpTelemetryService still satisfies the protocol with metrics methods."""
        svc = NoOpTelemetryService()
        assert isinstance(svc, TelemetryServiceProtocol)

    # -- ISSUE-7: Edge case tests for NoOp instruments -----------------------

    def test_noop_counter_accepts_zero_amount(self) -> None:
        """NoOp counter silently accepts zero amount."""
        svc = NoOpTelemetryService()
        counter = svc.create_counter("test.counter")
        counter.add(0)
        counter.add(0, {"key": "value"})

    def test_noop_counter_accepts_negative_amount(self) -> None:
        """NoOp counter silently accepts negative amount."""
        svc = NoOpTelemetryService()
        counter = svc.create_counter("test.counter")
        counter.add(-5)
        counter.add(-1, {"key": "value"})

    def test_noop_counter_accepts_float_amount(self) -> None:
        """NoOp counter silently accepts float amount."""
        svc = NoOpTelemetryService()
        counter = svc.create_counter("test.counter")
        counter.add(1.5)
        counter.add(0.001, {"key": "value"})

    def test_noop_histogram_accepts_zero_value(self) -> None:
        """NoOp histogram silently accepts zero value."""
        svc = NoOpTelemetryService()
        histogram = svc.create_histogram("test.histogram")
        histogram.record(0)
        histogram.record(0, {"key": "value"})

    def test_noop_histogram_accepts_negative_value(self) -> None:
        """NoOp histogram silently accepts negative value."""
        svc = NoOpTelemetryService()
        histogram = svc.create_histogram("test.histogram")
        histogram.record(-1.5)
        histogram.record(-100, {"key": "value"})

    def test_noop_histogram_accepts_float_value(self) -> None:
        """NoOp histogram silently accepts float value."""
        svc = NoOpTelemetryService()
        histogram = svc.create_histogram("test.histogram")
        histogram.record(3.14159)
        histogram.record(0.0001, {"key": "value"})

    def test_noop_up_down_counter_accepts_zero_amount(self) -> None:
        """NoOp up-down counter silently accepts zero amount."""
        svc = NoOpTelemetryService()
        udc = svc.create_up_down_counter("test.gauge")
        udc.add(0)
        udc.add(0, {"key": "value"})

    def test_noop_up_down_counter_accepts_negative_amount(self) -> None:
        """NoOp up-down counter silently accepts negative amount."""
        svc = NoOpTelemetryService()
        udc = svc.create_up_down_counter("test.gauge")
        udc.add(-10)
        udc.add(-1, {"key": "value"})

    def test_noop_up_down_counter_accepts_float_amount(self) -> None:
        """NoOp up-down counter silently accepts float amount."""
        svc = NoOpTelemetryService()
        udc = svc.create_up_down_counter("test.gauge")
        udc.add(2.5)
        udc.add(0.1, {"key": "value"})
