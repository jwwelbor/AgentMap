"""
Tests for BaseAgent telemetry constructor parameter and helper methods.

Covers task T-E02-F02-001: BaseAgent Constructor and Telemetry Helpers.
Test cases TC-140 through TC-154, TC-170 through TC-174.
"""

from unittest.mock import MagicMock, create_autospec, patch

import pytest

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol


class ConcreteTestAgent(BaseAgent):
    """Minimal concrete agent subclass for testing."""

    def process(self, inputs):
        return "test_output"


def _make_agent(**kwargs):
    """Create a ConcreteTestAgent with sensible defaults."""
    defaults = {
        "name": "test_agent",
        "prompt": "test prompt",
    }
    defaults.update(kwargs)
    return ConcreteTestAgent(**defaults)


def _make_mock_telemetry():
    """Create a properly specced mock telemetry service."""
    return create_autospec(TelemetryServiceProtocol, instance=True)


class TestConstructorTelemetryParam:
    """AC1: Constructor accepts telemetry_service (TC-140, TC-141)."""

    def test_constructor_accepts_telemetry_service(self):
        """TC-140: BaseAgent stores telemetry_service when provided."""
        mock_svc = _make_mock_telemetry()
        agent = _make_agent(telemetry_service=mock_svc)
        assert agent._telemetry_service is mock_svc

    def test_constructor_stores_telemetry_as_private_attr(self):
        """TC-141: telemetry_service stored as _telemetry_service."""
        mock_svc = _make_mock_telemetry()
        agent = _make_agent(telemetry_service=mock_svc)
        assert hasattr(agent, "_telemetry_service")
        assert agent._telemetry_service is mock_svc


class TestBackwardCompatibility:
    """AC2: Backward compatibility preserved (TC-144, REQ-NF02-003)."""

    def test_constructor_without_telemetry_defaults_to_none(self):
        """TC-144: Omitting telemetry_service sets _telemetry_service to None."""
        agent = _make_agent()
        assert agent._telemetry_service is None

    def test_constructor_with_explicit_none_telemetry(self):
        """Explicit None behaves same as omitting."""
        agent = _make_agent(telemetry_service=None)
        assert agent._telemetry_service is None

    def test_existing_params_still_work(self):
        """All existing constructor params continue to work."""
        agent = _make_agent(
            context={"input_fields": ["a"], "output_field": "b"},
        )
        assert agent.name == "test_agent"
        assert agent.context["output_field"] == "b"


class TestRecordLifecycleEvent:
    """AC3: _record_lifecycle_event is error-safe (TC-172)."""

    def test_delegates_to_add_span_event(self):
        """Calls telemetry_service.add_span_event when both span and service present."""
        mock_svc = _make_mock_telemetry()
        mock_span = MagicMock()
        agent = _make_agent(telemetry_service=mock_svc)

        agent._record_lifecycle_event(mock_span, "test_event")

        mock_svc.add_span_event.assert_called_once_with(mock_span, "test_event")

    def test_noop_when_span_is_none(self):
        """Short-circuits when span is None."""
        mock_svc = _make_mock_telemetry()
        agent = _make_agent(telemetry_service=mock_svc)

        agent._record_lifecycle_event(None, "test_event")

        mock_svc.add_span_event.assert_not_called()

    def test_noop_when_telemetry_service_is_none(self):
        """Short-circuits when telemetry_service is None."""
        agent = _make_agent()
        mock_span = MagicMock()

        # Should not raise
        agent._record_lifecycle_event(mock_span, "test_event")

    def test_suppresses_runtime_error(self):
        """Silently catches RuntimeError from add_span_event."""
        mock_svc = _make_mock_telemetry()
        mock_svc.add_span_event.side_effect = RuntimeError("boom")
        mock_span = MagicMock()
        agent = _make_agent(telemetry_service=mock_svc)

        # Should not raise
        agent._record_lifecycle_event(mock_span, "test_event")

    def test_suppresses_any_exception(self):
        """Silently catches any Exception from add_span_event."""
        mock_svc = _make_mock_telemetry()
        mock_svc.add_span_event.side_effect = ValueError("unexpected")
        mock_span = MagicMock()
        agent = _make_agent(telemetry_service=mock_svc)

        # Should not raise
        agent._record_lifecycle_event(mock_span, "test_event")


class TestSetSpanStatusOk:
    """AC4: _set_span_status_ok uses function-level OTEL import (ADR-E02F02-005)."""

    def test_calls_set_status_with_ok(self):
        """Calls span.set_status(StatusCode.OK) when span is present."""
        mock_span = MagicMock()
        agent = _make_agent()

        with patch(
            "agentmap.agents.base_agent.StatusCode", create=True
        ) as mock_status_code:
            mock_status_code.OK = "MOCK_OK"
            # Re-import won't work with function-level import; we need to patch
            # the import mechanism
            pass

        # The real test: just call it and verify span.set_status was called
        agent._set_span_status_ok(mock_span)
        mock_span.set_status.assert_called_once()

    def test_noop_when_span_is_none(self):
        """Short-circuits when span is None."""
        agent = _make_agent()
        # Should not raise
        agent._set_span_status_ok(None)

    def test_suppresses_import_error(self):
        """Suppresses ImportError when opentelemetry not installed."""
        agent = _make_agent()
        mock_span = MagicMock()

        # Patch the import to fail
        with patch.dict(
            "sys.modules", {"opentelemetry": None, "opentelemetry.trace": None}
        ):
            # Should not raise even if import fails
            agent._set_span_status_ok(mock_span)

    def test_suppresses_any_exception(self):
        """Suppresses any exception from set_status call."""
        mock_span = MagicMock()
        mock_span.set_status.side_effect = RuntimeError("boom")
        agent = _make_agent()

        # Should not raise
        agent._set_span_status_ok(mock_span)


class TestRecordSpanException:
    """AC5: _record_span_exception is error-safe (TC-173)."""

    def test_delegates_to_record_exception(self):
        """Calls telemetry_service.record_exception when both span and service present."""
        mock_svc = _make_mock_telemetry()
        mock_span = MagicMock()
        exc = ValueError("test error")
        agent = _make_agent(telemetry_service=mock_svc)

        agent._record_span_exception(mock_span, exc)

        mock_svc.record_exception.assert_called_once_with(mock_span, exc)

    def test_noop_when_span_is_none(self):
        """Short-circuits when span is None."""
        mock_svc = _make_mock_telemetry()
        agent = _make_agent(telemetry_service=mock_svc)

        agent._record_span_exception(None, ValueError("err"))

        mock_svc.record_exception.assert_not_called()

    def test_noop_when_telemetry_service_is_none(self):
        """Short-circuits when telemetry_service is None."""
        agent = _make_agent()
        mock_span = MagicMock()

        # Should not raise
        agent._record_span_exception(mock_span, ValueError("err"))

    def test_suppresses_exceptions(self):
        """Silently catches exceptions from record_exception."""
        mock_svc = _make_mock_telemetry()
        mock_svc.record_exception.side_effect = RuntimeError("service failure")
        mock_span = MagicMock()
        agent = _make_agent(telemetry_service=mock_svc)

        # Should not raise
        agent._record_span_exception(mock_span, ValueError("original"))


class TestCaptureIoAttributes:
    """AC6: _capture_io_attributes respects privacy defaults (TC-150, TC-151)."""

    def test_no_capture_by_default(self):
        """When context has no capture flags, nothing is captured."""
        mock_svc = _make_mock_telemetry()
        mock_span = MagicMock()
        agent = _make_agent(telemetry_service=mock_svc)

        agent._capture_io_attributes(mock_span, inputs={"key": "val"}, output="result")

        mock_svc.set_span_attributes.assert_not_called()

    def test_captures_inputs_when_enabled(self):
        """When capture_agent_inputs=True, inputs are captured."""
        mock_svc = _make_mock_telemetry()
        mock_span = MagicMock()
        agent = _make_agent(
            telemetry_service=mock_svc,
            context={"capture_agent_inputs": True},
        )

        agent._capture_io_attributes(mock_span, inputs={"key": "val"})

        mock_svc.set_span_attributes.assert_called_once()
        attrs = mock_svc.set_span_attributes.call_args[0][1]
        assert "agentmap.agent.inputs" in attrs

    def test_captures_outputs_when_enabled(self):
        """When capture_agent_outputs=True, outputs are captured."""
        mock_svc = _make_mock_telemetry()
        mock_span = MagicMock()
        agent = _make_agent(
            telemetry_service=mock_svc,
            context={"capture_agent_outputs": True},
        )

        agent._capture_io_attributes(mock_span, output="result")

        mock_svc.set_span_attributes.assert_called_once()
        attrs = mock_svc.set_span_attributes.call_args[0][1]
        assert "agentmap.agent.outputs" in attrs

    def test_captures_both_when_both_enabled(self):
        """When both flags True, both inputs and outputs captured."""
        mock_svc = _make_mock_telemetry()
        mock_span = MagicMock()
        agent = _make_agent(
            telemetry_service=mock_svc,
            context={
                "capture_agent_inputs": True,
                "capture_agent_outputs": True,
            },
        )

        agent._capture_io_attributes(mock_span, inputs={"key": "val"}, output="result")

        mock_svc.set_span_attributes.assert_called_once()
        attrs = mock_svc.set_span_attributes.call_args[0][1]
        assert "agentmap.agent.inputs" in attrs
        assert "agentmap.agent.outputs" in attrs

    def test_truncates_to_1024_chars(self):
        """Values longer than 1024 chars are truncated."""
        mock_svc = _make_mock_telemetry()
        mock_span = MagicMock()
        agent = _make_agent(
            telemetry_service=mock_svc,
            context={"capture_agent_inputs": True},
        )

        long_input = {"key": "x" * 2000}
        agent._capture_io_attributes(mock_span, inputs=long_input)

        attrs = mock_svc.set_span_attributes.call_args[0][1]
        assert len(attrs["agentmap.agent.inputs"]) <= 1024

    def test_empty_string_is_captured(self):
        """Edge case 4: Empty string is set as attribute value, not skipped."""
        mock_svc = _make_mock_telemetry()
        mock_span = MagicMock()
        agent = _make_agent(
            telemetry_service=mock_svc,
            context={"capture_agent_outputs": True},
        )

        agent._capture_io_attributes(mock_span, output="")

        mock_svc.set_span_attributes.assert_called_once()
        attrs = mock_svc.set_span_attributes.call_args[0][1]
        assert attrs["agentmap.agent.outputs"] == ""

    def test_noop_when_span_is_none(self):
        """Short-circuits when span is None."""
        mock_svc = _make_mock_telemetry()
        agent = _make_agent(
            telemetry_service=mock_svc,
            context={"capture_agent_inputs": True},
        )

        agent._capture_io_attributes(None, inputs={"key": "val"})

        mock_svc.set_span_attributes.assert_not_called()

    def test_noop_when_telemetry_service_is_none(self):
        """Short-circuits when telemetry_service is None."""
        agent = _make_agent(context={"capture_agent_inputs": True})
        mock_span = MagicMock()

        # Should not raise
        agent._capture_io_attributes(mock_span, inputs={"key": "val"})

    def test_suppresses_exceptions(self):
        """Silently catches exceptions from set_span_attributes."""
        mock_svc = _make_mock_telemetry()
        mock_svc.set_span_attributes.side_effect = RuntimeError("boom")
        mock_span = MagicMock()
        agent = _make_agent(
            telemetry_service=mock_svc,
            context={"capture_agent_inputs": True},
        )

        # Should not raise
        agent._capture_io_attributes(mock_span, inputs={"key": "val"})


class TestNoModuleLevelOtelImports:
    """AC7: No module-level OTEL imports in base_agent.py."""

    def test_no_opentelemetry_module_import(self):
        """Verify base_agent.py has no module-level opentelemetry imports."""
        import inspect

        import agentmap.agents.base_agent as mod

        source = inspect.getsource(mod)
        # Check for module-level imports (not inside functions)
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Skip lines inside functions/methods (indented)
            if stripped.startswith("from opentelemetry") or (
                stripped.startswith("import opentelemetry")
            ):
                # Check if this is at module level (no indentation)
                if not line.startswith(" ") and not line.startswith("\t"):
                    pytest.fail(
                        f"Module-level OTEL import found at line {i+1}: {stripped}"
                    )


class TestGetServiceInfoTelemetry:
    """get_service_info includes telemetry_service_available."""

    def test_service_info_shows_telemetry_available(self):
        """When telemetry_service is provided, service_info reflects it."""
        mock_svc = _make_mock_telemetry()
        agent = _make_agent(telemetry_service=mock_svc)
        info = agent.get_service_info()
        assert info["services"]["telemetry_service_available"] is True

    def test_service_info_shows_telemetry_unavailable(self):
        """When telemetry_service is None, service_info reflects it."""
        agent = _make_agent()
        info = agent.get_service_info()
        assert info["services"]["telemetry_service_available"] is False


class TestAllHelpersIndependent:
    """Edge case 3: No shared failure state between helper calls."""

    def test_failure_in_one_helper_does_not_affect_others(self):
        """Each helper call is independent -- prior failure has no effect."""
        mock_svc = _make_mock_telemetry()
        mock_span = MagicMock()
        agent = _make_agent(telemetry_service=mock_svc)

        # Make lifecycle event fail
        mock_svc.add_span_event.side_effect = RuntimeError("fail1")
        agent._record_lifecycle_event(mock_span, "event1")

        # record_exception should still work
        mock_svc.record_exception.side_effect = None
        agent._record_span_exception(mock_span, ValueError("err"))
        mock_svc.record_exception.assert_called_once()

    def test_both_none_is_pure_noop(self):
        """Edge case 1: telemetry=None AND span=None, all helpers are no-ops."""
        agent = _make_agent()  # No telemetry service
        # All should be pure no-ops, no exceptions
        agent._record_lifecycle_event(None, "event")
        agent._set_span_status_ok(None)
        agent._record_span_exception(None, ValueError("err"))
        agent._capture_io_attributes(None, inputs={}, output="x")
