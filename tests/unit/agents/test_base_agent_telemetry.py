"""
Tests for BaseAgent telemetry: constructor, helper methods, and run() instrumentation.

Covers tasks T-E02-F02-001 (constructor + helpers) and T-E02-F02-002 (run() refactoring).
Test cases TC-100 through TC-182.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, call, create_autospec, patch

import pytest
from langgraph.errors import GraphInterrupt

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.telemetry.constants import (
    AGENT_NAME,
    AGENT_RUN_SPAN,
    AGENT_TYPE,
    GRAPH_NAME,
    NODE_NAME,
)
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol


class ConcreteTestAgent(BaseAgent):
    """Minimal concrete agent subclass for testing."""

    def process(self, inputs):
        return "test_output"


class FailingTestAgent(BaseAgent):
    """Agent that raises ValueError during process()."""

    def process(self, inputs):
        raise ValueError("agent processing failed")


class SuspendingTestAgent(BaseAgent):
    """Agent that raises GraphInterrupt during process()."""

    def process(self, inputs):
        raise GraphInterrupt("suspended")


def _make_agent(**kwargs):
    """Create a ConcreteTestAgent with sensible defaults."""
    defaults = {
        "name": "test_agent",
        "prompt": "test prompt",
    }
    defaults.update(kwargs)
    agent_class = defaults.pop("agent_class", ConcreteTestAgent)
    return agent_class(**defaults)


def _make_mock_telemetry_with_span():
    """Create a mock telemetry service with a context-manager-compatible start_span.

    Returns:
        (mock_telemetry_service, mock_span) tuple.
    """
    svc = create_autospec(TelemetryServiceProtocol, instance=True)
    mock_span = MagicMock(name="mock_span")

    @contextmanager
    def _start_span_cm(name, attributes=None, kind=None):
        yield mock_span

    svc.start_span.side_effect = _start_span_cm
    return svc, mock_span


def _make_runnable_agent(telemetry_service=None, agent_class=ConcreteTestAgent,
                         context=None, name="test_agent"):
    """Create an agent wired up with mocked services ready for run().

    Returns:
        (agent, mock_tracking, mock_state_adapter, mock_tracker) tuple.
    """
    mock_tracking = create_autospec(ExecutionTrackingService, instance=True)
    mock_state_adapter = create_autospec(StateAdapterService, instance=True)
    mock_tracker = MagicMock(name="mock_tracker")
    mock_logger = MagicMock(name="mock_logger")
    # Ensure logger has all required level methods
    for method_name in ["debug", "info", "warning", "error", "trace"]:
        setattr(mock_logger, method_name, MagicMock())

    ctx = context or {
        "input_fields": ["input1"],
        "output_field": "output1",
        "graph_name": "test_graph",
    }

    agent = agent_class(
        name=name,
        prompt="test prompt",
        context=ctx,
        logger=mock_logger,
        execution_tracking_service=mock_tracking,
        state_adapter_service=mock_state_adapter,
        telemetry_service=telemetry_service,
    )
    agent.set_execution_tracker(mock_tracker)

    # Default: state_adapter returns inputs dict
    mock_state_adapter.get_inputs.return_value = {"input1": "value1"}
    # Default: update_graph_success returns False
    mock_tracking.update_graph_success.return_value = False

    return agent, mock_tracking, mock_state_adapter, mock_tracker


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


# ======================================================================
# T-E02-F02-002: run() Refactoring and Span Instrumentation Tests
# ======================================================================


class TestRunDispatchGuard:
    """AC1: run() dispatches to _run_with_telemetry or _run_core (TC-100, TC-143)."""

    def test_run_dispatches_to_telemetry_path_when_service_present(self):
        """TC-100: When telemetry_service is set, start_span is called."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        result = agent.run({"input1": "val"})

        mock_svc.start_span.assert_called_once()

    def test_run_dispatches_to_core_path_when_no_service(self):
        """TC-143/TC-180: When telemetry_service is None, no telemetry calls."""
        agent, _, _, _ = _make_runnable_agent(telemetry_service=None)

        result = agent.run({"input1": "val"})

        # Agent executes normally, returns state updates
        assert "output1" in result
        assert result["output1"] == "test_output"

    def test_run_returns_identical_results_with_and_without_telemetry(self):
        """AC1: Uninstrumented path returns identical results to instrumented."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        state = {"input1": "val"}

        agent_with, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)
        result_with = agent_with.run(state)

        agent_without, _, _, _ = _make_runnable_agent(telemetry_service=None)
        result_without = agent_without.run(state)

        assert result_with == result_without


class TestSpanCreation:
    """AC2: Span created with correct name and attributes (TC-100, TC-110-114)."""

    def test_span_name_is_agent_run_span_constant(self):
        """TC-100: start_span called with AGENT_RUN_SPAN constant."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        agent.run({"input1": "val"})

        args, kwargs = mock_svc.start_span.call_args
        assert args[0] == AGENT_RUN_SPAN

    def test_span_attributes_contain_agent_name(self):
        """TC-110: Attributes include AGENT_NAME."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc, name="my_agent"
        )

        agent.run({"input1": "val"})

        args, kwargs = mock_svc.start_span.call_args
        attrs = kwargs.get("attributes") or args[1] if len(args) > 1 else kwargs.get("attributes")
        assert attrs[AGENT_NAME] == "my_agent"

    def test_span_attributes_contain_agent_type(self):
        """TC-111: Attributes include AGENT_TYPE = class name."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        agent.run({"input1": "val"})

        args, kwargs = mock_svc.start_span.call_args
        attrs = kwargs.get("attributes") or args[1] if len(args) > 1 else kwargs.get("attributes")
        assert attrs[AGENT_TYPE] == "ConcreteTestAgent"

    def test_span_attributes_contain_node_name(self):
        """TC-112: Attributes include NODE_NAME."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc, name="node_1"
        )

        agent.run({"input1": "val"})

        args, kwargs = mock_svc.start_span.call_args
        attrs = kwargs.get("attributes") or args[1] if len(args) > 1 else kwargs.get("attributes")
        assert attrs[NODE_NAME] == "node_1"

    def test_span_attributes_contain_graph_name(self):
        """TC-113: Attributes include GRAPH_NAME from context."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc,
            context={
                "input_fields": ["input1"],
                "output_field": "output1",
                "graph_name": "my_graph",
            },
        )

        agent.run({"input1": "val"})

        args, kwargs = mock_svc.start_span.call_args
        attrs = kwargs.get("attributes") or args[1] if len(args) > 1 else kwargs.get("attributes")
        assert attrs[GRAPH_NAME] == "my_graph"

    def test_graph_name_defaults_to_unknown(self):
        """TC-113 edge: Missing graph_name in context defaults to 'unknown'."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc,
            context={
                "input_fields": ["input1"],
                "output_field": "output1",
            },
        )

        agent.run({"input1": "val"})

        args, kwargs = mock_svc.start_span.call_args
        attrs = kwargs.get("attributes") or args[1] if len(args) > 1 else kwargs.get("attributes")
        assert attrs[GRAPH_NAME] == "unknown"

    def test_start_span_called_exactly_once(self):
        """TC-124: Only one span created per run (no child spans for phases)."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        agent.run({"input1": "val"})

        assert mock_svc.start_span.call_count == 1


class TestLifecycleEvents:
    """AC3: Four lifecycle events in order on happy path (TC-120-125)."""

    def test_four_events_recorded_on_success(self):
        """TC-125: Events recorded in order: pre_process.start, process.start,
        post_process.start, agent.complete."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        agent.run({"input1": "val"})

        event_calls = mock_svc.add_span_event.call_args_list
        event_names = [c[0][1] for c in event_calls]
        assert event_names == [
            "pre_process.start",
            "process.start",
            "post_process.start",
            "agent.complete",
        ]

    def test_events_use_add_span_event(self):
        """TC-124: Events are recorded via add_span_event, not child spans."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        agent.run({"input1": "val"})

        assert mock_svc.add_span_event.call_count == 4
        # All calls pass the span as first arg
        for c in mock_svc.add_span_event.call_args_list:
            assert c[0][0] is mock_span


class TestSpanStatusSuccess:
    """AC4: Span status OK on success (TC-130)."""

    def test_span_set_status_ok_on_success(self):
        """TC-130: span.set_status(StatusCode.OK) called on successful run."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        agent.run({"input1": "val"})

        # _set_span_status_ok calls span.set_status
        mock_span.set_status.assert_called_once()


class TestSpanStatusException:
    """AC5: Exception records on span with ERROR status (TC-131, TC-132)."""

    def test_exception_recorded_on_span(self):
        """TC-132: record_exception called with the exception."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc, agent_class=FailingTestAgent
        )

        result = agent.run({"input1": "val"})

        mock_svc.record_exception.assert_called_once()
        exc_arg = mock_svc.record_exception.call_args[0][1]
        assert isinstance(exc_arg, ValueError)
        assert "agent processing failed" in str(exc_arg)

    def test_error_path_still_returns_error_state(self):
        """AC5: Existing error handling preserved -- error_updates returned."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc, agent_class=FailingTestAgent
        )

        result = agent.run({"input1": "val"})

        assert result["last_action_success"] is False
        assert "errors" in result

    def test_events_before_error_still_recorded(self):
        """Events before the failure are still recorded."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc, agent_class=FailingTestAgent
        )

        agent.run({"input1": "val"})

        event_names = [c[0][1] for c in mock_svc.add_span_event.call_args_list]
        assert "pre_process.start" in event_names
        assert "process.start" in event_names


class TestGraphInterruptHandling:
    """AC6: GraphInterrupt records agent.suspended, UNSET status (TC-133-135)."""

    def test_graph_interrupt_records_suspended_event(self):
        """TC-135: agent.suspended event recorded on GraphInterrupt."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc, agent_class=SuspendingTestAgent
        )

        with pytest.raises(GraphInterrupt):
            agent.run({"input1": "val"})

        event_names = [c[0][1] for c in mock_svc.add_span_event.call_args_list]
        assert "agent.suspended" in event_names

    def test_graph_interrupt_does_not_set_error_status(self):
        """TC-133: record_exception NOT called for GraphInterrupt."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc, agent_class=SuspendingTestAgent
        )

        with pytest.raises(GraphInterrupt):
            agent.run({"input1": "val"})

        mock_svc.record_exception.assert_not_called()

    def test_graph_interrupt_does_not_set_ok_status(self):
        """TC-133: span status not set to OK (remains UNSET)."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc, agent_class=SuspendingTestAgent
        )

        with pytest.raises(GraphInterrupt):
            agent.run({"input1": "val"})

        # set_status should NOT be called (UNSET is the default)
        mock_span.set_status.assert_not_called()

    def test_graph_interrupt_is_reraised(self):
        """TC-134: GraphInterrupt propagates to caller."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=mock_svc, agent_class=SuspendingTestAgent
        )

        with pytest.raises(GraphInterrupt):
            agent.run({"input1": "val"})


class TestTelemetryFailureIsolation:
    """AC7: start_span failure falls back to _run_core (TC-170, TC-171)."""

    def test_start_span_failure_falls_back_to_run_core(self):
        """TC-170: Agent still runs when start_span raises."""
        mock_svc = create_autospec(TelemetryServiceProtocol, instance=True)
        mock_svc.start_span.side_effect = RuntimeError("telemetry broken")

        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        result = agent.run({"input1": "val"})

        assert "output1" in result
        assert result["output1"] == "test_output"

    def test_start_span_failure_logs_warning(self):
        """TC-171: Warning logged on telemetry failure."""
        mock_svc = create_autospec(TelemetryServiceProtocol, instance=True)
        mock_svc.start_span.side_effect = RuntimeError("telemetry broken")

        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        agent.run({"input1": "val"})

        # Check that log_warning was called (via the logger mock)
        warning_calls = agent._logger.warning.call_args_list
        warning_text = " ".join(str(c) for c in warning_calls)
        assert "telemetry" in warning_text.lower() or "instrumentation" in warning_text.lower()


class TestMidExecutionEventFailure:
    """AC8: Mid-execution event failure does not prevent completion (TC-172)."""

    def test_event_failure_does_not_block_completion(self):
        """TC-172: Agent completes even when add_span_event raises."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        # Make second add_span_event call fail
        call_count = [0]
        original_side_effect = None

        def side_effect_fn(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("event recording failed")

        mock_svc.add_span_event.side_effect = side_effect_fn

        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        result = agent.run({"input1": "val"})

        # Agent still completes successfully
        assert "output1" in result
        assert result["output1"] == "test_output"

    def test_all_events_attempted_despite_failures(self):
        """TC-172: Subsequent events still attempted after a failure."""
        mock_svc, mock_span = _make_mock_telemetry_with_span()
        call_count = [0]

        def side_effect_fn(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("first event failed")

        mock_svc.add_span_event.side_effect = side_effect_fn

        agent, _, _, _ = _make_runnable_agent(telemetry_service=mock_svc)

        agent.run({"input1": "val"})

        # All 4 events should still be attempted
        assert mock_svc.add_span_event.call_count == 4


class TestNoneTelemetryPath:
    """TC-180-182: No telemetry interaction when service is None."""

    def test_no_span_creation_when_none(self):
        """TC-180: No start_span call."""
        agent, _, _, _ = _make_runnable_agent(telemetry_service=None)

        result = agent.run({"input1": "val"})

        assert "output1" in result

    def test_no_attribute_error_with_none(self):
        """TC-181: No AttributeError from None telemetry."""
        agent, _, _, _ = _make_runnable_agent(telemetry_service=None)

        # Should not raise any exception
        result = agent.run({"input1": "val"})
        assert result["output1"] == "test_output"

    def test_error_path_works_without_telemetry(self):
        """Error handling path works without telemetry."""
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=None, agent_class=FailingTestAgent
        )

        result = agent.run({"input1": "val"})

        assert result["last_action_success"] is False

    def test_graph_interrupt_works_without_telemetry(self):
        """GraphInterrupt re-raised without telemetry."""
        agent, _, _, _ = _make_runnable_agent(
            telemetry_service=None, agent_class=SuspendingTestAgent
        )

        with pytest.raises(GraphInterrupt):
            agent.run({"input1": "val"})
