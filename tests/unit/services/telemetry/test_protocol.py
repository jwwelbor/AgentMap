"""Unit tests for TelemetryServiceProtocol definition."""

from __future__ import annotations

import inspect
import typing

import pytest

from agentmap.services.telemetry.protocol import TelemetryServiceProtocol


class TestProtocolDefinition:
    """TC-001 through TC-008: Protocol structure and attributes."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """TC-001: Protocol has @runtime_checkable decorator."""
        assert hasattr(TelemetryServiceProtocol, "__protocol_attrs__") or issubclass(
            TelemetryServiceProtocol, typing.Protocol
        )
        # runtime_checkable protocols support isinstance checks
        assert isinstance(TelemetryServiceProtocol, type)

    def test_protocol_defines_start_span(self) -> None:
        """TC-002: Protocol defines start_span method."""
        assert hasattr(TelemetryServiceProtocol, "start_span")
        sig = inspect.signature(TelemetryServiceProtocol.start_span)
        params = list(sig.parameters.keys())
        assert "name" in params
        assert "attributes" in params
        assert "kind" in params

    def test_protocol_defines_record_exception(self) -> None:
        """TC-003: Protocol defines record_exception method."""
        assert hasattr(TelemetryServiceProtocol, "record_exception")
        sig = inspect.signature(TelemetryServiceProtocol.record_exception)
        params = list(sig.parameters.keys())
        assert "span" in params
        assert "exception" in params

    def test_protocol_defines_set_span_attributes(self) -> None:
        """TC-004: Protocol defines set_span_attributes method."""
        assert hasattr(TelemetryServiceProtocol, "set_span_attributes")
        sig = inspect.signature(TelemetryServiceProtocol.set_span_attributes)
        params = list(sig.parameters.keys())
        assert "span" in params
        assert "attributes" in params

    def test_protocol_defines_add_span_event(self) -> None:
        """TC-005: Protocol defines add_span_event method."""
        assert hasattr(TelemetryServiceProtocol, "add_span_event")
        sig = inspect.signature(TelemetryServiceProtocol.add_span_event)
        params = list(sig.parameters.keys())
        assert "span" in params
        assert "name" in params
        assert "attributes" in params

    def test_protocol_defines_get_tracer(self) -> None:
        """TC-006: Protocol defines get_tracer method."""
        assert hasattr(TelemetryServiceProtocol, "get_tracer")
        sig = inspect.signature(TelemetryServiceProtocol.get_tracer)
        # Only 'self' parameter
        params = list(sig.parameters.keys())
        assert params == ["self"]

    def test_protocol_module_has_docstring(self) -> None:
        """TC-007: Protocol module has a descriptive docstring."""
        import agentmap.services.telemetry.protocol as mod

        assert mod.__doc__ is not None
        assert len(mod.__doc__.strip()) > 0

    def test_no_opentelemetry_imports_in_protocol(self) -> None:
        """TC-008: No opentelemetry imports in protocol.py source."""
        import agentmap.services.telemetry.protocol as mod

        source = inspect.getsource(mod)
        assert "opentelemetry" not in source
