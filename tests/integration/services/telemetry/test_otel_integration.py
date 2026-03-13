"""Integration tests for OTELTelemetryService with real OTEL SDK.

These tests require ``opentelemetry-sdk`` to be installed.  They are
skipped automatically when the SDK is not available.
"""

from __future__ import annotations

import pytest

# Skip the entire module if opentelemetry-sdk is not installed.
try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export.in_memory import InMemorySpanExporter

    _sdk_available = True
except ImportError:
    _sdk_available = False

pytestmark = pytest.mark.skipif(
    not _sdk_available,
    reason="opentelemetry-sdk not installed",
)


@pytest.fixture()
def otel_exporter():
    """Set up an InMemorySpanExporter TracerProvider and tear down after test."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Save original provider and set our test provider
    original_provider = trace.get_tracer_provider()
    trace.set_tracer_provider(provider)

    yield exporter

    # Restore original provider
    trace.set_tracer_provider(original_provider)


class TestOTELIntegration:
    """INT-010, INT-012: Real OTEL span production."""

    def test_start_span_produces_real_span(self, otel_exporter) -> None:
        """INT-010: start_span produces a real span with correct name/attributes."""
        from agentmap.services.telemetry.otel_telemetry_service import (
            OTELTelemetryService,
        )

        svc = OTELTelemetryService()
        with svc.start_span("test.span", attributes={"key": "value"}) as span:
            pass

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test.span"
        assert spans[0].attributes.get("key") == "value"
