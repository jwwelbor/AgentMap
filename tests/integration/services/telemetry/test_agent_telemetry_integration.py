"""Integration tests for agent telemetry with real OTEL SDK components.

These tests verify end-to-end span creation using real TracerProvider and
InMemorySpanExporter.  They complement the unit tests in T-E02-F02-004 by
validating what mocks cannot: actual exported span names, attribute values,
event objects, status codes, and exception recordings.

Test IDs: INT-100 through INT-151 (task T-E02-F02-005).

Requires ``opentelemetry-sdk`` to be installed.  The entire module is
skipped automatically when the SDK is unavailable (AC11).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from unittest.mock import MagicMock, create_autospec

import pytest

# ---------------------------------------------------------------------------
# Graceful skip when OTEL SDK is not installed (AC11)
# ---------------------------------------------------------------------------
try:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from opentelemetry.trace import StatusCode

    _sdk_available = True
except ImportError:
    _sdk_available = False

pytestmark = pytest.mark.skipif(
    not _sdk_available,
    reason="opentelemetry-sdk not installed -- skipping OTEL integration tests",
)

from agentmap.agents.base_agent import BaseAgent  # noqa: E402
from agentmap.services.execution_tracking_service import ExecutionTrackingService  # noqa: E402
from agentmap.services.state_adapter_service import StateAdapterService  # noqa: E402
from agentmap.services.telemetry.constants import (  # noqa: E402
    AGENT_NAME,
    AGENT_RUN_SPAN,
    AGENT_TYPE,
    GRAPH_NAME,
    NODE_NAME,
)
from agentmap.services.telemetry.noop_telemetry_service import NoOpTelemetryService  # noqa: E402
from agentmap.services.telemetry.otel_telemetry_service import OTELTelemetryService  # noqa: E402
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _otel_provider():
    """Create a per-test TracerProvider + InMemorySpanExporter pair."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter, provider


@pytest.fixture()
def otel_exporter(_otel_provider):
    """Per-test InMemorySpanExporter.

    Uses a local TracerProvider (not the global one) to avoid conflicts
    with other test modules.
    """
    exporter, _ = _otel_provider
    return exporter


@pytest.fixture()
def telemetry_service(_otel_provider):
    """Create a real OTELTelemetryService with tracer from the test provider."""
    _, provider = _otel_provider
    svc = OTELTelemetryService()
    # Override the tracer to use the test-local provider instead of the global one
    svc._tracer = provider.get_tracer("agentmap")
    return svc


@pytest.fixture()
def mock_tracking_service():
    """Autospec-based mock for ExecutionTrackingService."""
    svc = create_autospec(ExecutionTrackingService, instance=True)
    svc.update_graph_success.return_value = False
    return svc


@pytest.fixture()
def mock_state_adapter():
    """Autospec-based mock for StateAdapterService."""
    svc = create_autospec(StateAdapterService, instance=True)
    svc.get_inputs.return_value = {"input": "hello"}
    return svc


@pytest.fixture()
def mock_tracker():
    """Simple execution tracker object (mock)."""
    return MagicMock(name="execution_tracker")


# ---------------------------------------------------------------------------
# Concrete test agent subclasses
# ---------------------------------------------------------------------------


class _SuccessAgent(BaseAgent):
    """Agent that succeeds and returns its input."""

    def process(self, inputs: Dict[str, Any]) -> Any:
        return inputs.get("input", "default")


class _FailingAgent(BaseAgent):
    """Agent whose process() raises ValueError."""

    def process(self, inputs: Dict[str, Any]) -> Any:
        raise ValueError("something went wrong")


class _SuspendingAgent(BaseAgent):
    """Agent whose process() raises GraphInterrupt."""

    def process(self, inputs: Dict[str, Any]) -> Any:
        from langgraph.errors import GraphInterrupt

        raise GraphInterrupt("checkpoint")


class _CustomAgent(BaseAgent):
    """Custom agent subclass with no telemetry code -- only overrides process()."""

    def process(self, inputs: Dict[str, Any]) -> Any:
        return f"custom: {inputs.get('input', '')}"


def _make_agent(
    cls,
    *,
    name: str = "test_node",
    prompt: str = "test prompt",
    graph_name: str = "test_graph",
    output_field: str = "result",
    telemetry_service=None,
    tracking_service=None,
    state_adapter=None,
):
    """Helper to construct a test agent with required services."""
    context = {
        "input_fields": ["input"],
        "output_field": output_field,
        "graph_name": graph_name,
    }
    agent = cls(
        name=name,
        prompt=prompt,
        context=context,
        logger=logging.getLogger(f"test.{cls.__name__}"),
        execution_tracking_service=tracking_service,
        state_adapter_service=state_adapter,
        telemetry_service=telemetry_service,
    )
    return agent


# ---------------------------------------------------------------------------
# INT-100: Real span export with correct identity (AC1)
# ---------------------------------------------------------------------------


class TestRealSpanExport:
    """INT-100: Verify real exported spans have correct identity and attributes."""

    def test_span_name_and_attributes(
        self,
        otel_exporter,
        telemetry_service,
        mock_tracking_service,
        mock_state_adapter,
        mock_tracker,
    ) -> None:
        """INT-100: run() produces exactly one span with correct name and attributes."""
        agent = _make_agent(
            _SuccessAgent,
            name="my_node",
            graph_name="my_graph",
            telemetry_service=telemetry_service,
            tracking_service=mock_tracking_service,
            state_adapter=mock_state_adapter,
        )
        agent.set_execution_tracker(mock_tracker)

        result = agent.run({"input": "hello"})

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1, f"Expected 1 span, got {len(spans)}"

        span = spans[0]
        assert span.name == AGENT_RUN_SPAN
        assert span.status.status_code == StatusCode.OK
        assert span.attributes[AGENT_NAME] == "my_node"
        assert span.attributes[AGENT_TYPE] == "_SuccessAgent"
        assert span.attributes[NODE_NAME] == "my_node"
        assert span.attributes[GRAPH_NAME] == "my_graph"

        # Verify non-zero duration
        assert span.end_time is not None
        assert span.start_time is not None
        assert span.end_time >= span.start_time

        # Verify result is correct
        assert result == {"result": "hello"}


# ---------------------------------------------------------------------------
# INT-101: Lifecycle events on real span (AC2)
# ---------------------------------------------------------------------------


class TestLifecycleEvents:
    """INT-101: Verify lifecycle events appear in correct order."""

    def test_lifecycle_events_present_and_ordered(
        self,
        otel_exporter,
        telemetry_service,
        mock_tracking_service,
        mock_state_adapter,
        mock_tracker,
    ) -> None:
        """INT-101: Exported span has 4 lifecycle events in ascending timestamp order."""
        agent = _make_agent(
            _SuccessAgent,
            telemetry_service=telemetry_service,
            tracking_service=mock_tracking_service,
            state_adapter=mock_state_adapter,
        )
        agent.set_execution_tracker(mock_tracker)
        agent.run({"input": "test"})

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1
        events = spans[0].events

        expected_names = [
            "pre_process.start",
            "process.start",
            "post_process.start",
            "agent.complete",
        ]
        event_names = [e.name for e in events]
        assert (
            event_names == expected_names
        ), f"Expected events {expected_names}, got {event_names}"

        # Verify timestamps are in ascending order
        timestamps = [e.timestamp for e in events]
        for i in range(len(timestamps) - 1):
            assert (
                timestamps[i] <= timestamps[i + 1]
            ), f"Event timestamps not in order: {timestamps}"


# ---------------------------------------------------------------------------
# INT-102: Exception recorded on real span (AC3)
# ---------------------------------------------------------------------------


class TestExceptionOnSpan:
    """INT-102: Verify exception recording on span."""

    def test_error_span_with_exception(
        self,
        otel_exporter,
        telemetry_service,
        mock_tracking_service,
        mock_state_adapter,
        mock_tracker,
    ) -> None:
        """INT-102: Failing agent produces ERROR span with exception event."""
        agent = _make_agent(
            _FailingAgent,
            telemetry_service=telemetry_service,
            tracking_service=mock_tracking_service,
            state_adapter=mock_state_adapter,
        )
        agent.set_execution_tracker(mock_tracker)

        # run() catches exceptions and returns error dict (does not re-raise)
        result = agent.run({"input": "test"})

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.status.status_code == StatusCode.ERROR

        # Check that pre_process.start and process.start events are present
        event_names = [e.name for e in span.events]
        assert "pre_process.start" in event_names
        assert "process.start" in event_names

        # Check for exception event (OTEL records exceptions as events with name "exception")
        exception_events = [e for e in span.events if e.name == "exception"]
        assert (
            len(exception_events) >= 1
        ), f"Expected exception event, got events: {event_names}"

        # Verify exception details
        exc_event = exception_events[0]
        exc_attrs = dict(exc_event.attributes)
        assert "ValueError" in exc_attrs.get("exception.type", "")
        assert "something went wrong" in exc_attrs.get("exception.message", "")

        # Verify result is an error dict
        assert result.get("last_action_success") is False


# ---------------------------------------------------------------------------
# INT-103: GraphInterrupt does not produce ERROR span (AC4)
# ---------------------------------------------------------------------------


class TestGraphInterruptSpan:
    """INT-103: Verify GraphInterrupt produces UNSET span, not ERROR."""

    def test_graph_interrupt_unset_status(
        self,
        otel_exporter,
        telemetry_service,
        mock_tracking_service,
        mock_state_adapter,
        mock_tracker,
    ) -> None:
        """INT-103: GraphInterrupt results in UNSET status with agent.suspended event."""
        from langgraph.errors import GraphInterrupt

        agent = _make_agent(
            _SuspendingAgent,
            telemetry_service=telemetry_service,
            tracking_service=mock_tracking_service,
            state_adapter=mock_state_adapter,
        )
        agent.set_execution_tracker(mock_tracker)

        with pytest.raises(GraphInterrupt):
            agent.run({"input": "test"})

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        # GraphInterrupt should NOT set ERROR status
        assert span.status.status_code == StatusCode.UNSET

        event_names = [e.name for e in span.events]
        assert "agent.suspended" in event_names

        # No exception event should be recorded for GraphInterrupt
        exception_events = [e for e in span.events if e.name == "exception"]
        assert len(exception_events) == 0, (
            f"GraphInterrupt should not record exception events, "
            f"but found: {exception_events}"
        )


# ---------------------------------------------------------------------------
# INT-110: FileWriterAgent span via super().run() (AC5)
# ---------------------------------------------------------------------------


class TestFileWriterAgentSpan:
    """INT-110: FileWriterAgent gets telemetry via super().run()."""

    def test_file_writer_agent_span(
        self,
        otel_exporter,
        telemetry_service,
        mock_tracking_service,
        mock_state_adapter,
        mock_tracker,
    ) -> None:
        """INT-110: FileWriterAgent produces span with correct agent type."""
        from agentmap.agents.builtins.storage.file.writer import FileWriterAgent

        context = {
            "input_fields": ["data"],
            "output_field": "result",
            "graph_name": "test_graph",
        }

        agent = FileWriterAgent(
            name="file_writer_node",
            prompt="/tmp/test.txt",
            context=context,
            logger=logging.getLogger("test.FileWriterAgent"),
            execution_tracking_service=mock_tracking_service,
            state_adapter_service=mock_state_adapter,
        )
        # Inject telemetry_service directly (FileWriterAgent constructor
        # does not forward **kwargs, so we set it on the instance)
        agent._telemetry_service = telemetry_service
        agent.set_execution_tracker(mock_tracker)

        # Mock the file service to avoid actual I/O
        mock_file_service = MagicMock()
        mock_file_service.write.return_value = MagicMock(
            success=True, file_path="/tmp/test.txt", error=None
        )
        agent.configure_file_service(mock_file_service)

        # Configure state adapter to return data input
        mock_state_adapter.get_inputs.return_value = {
            "data": "test content",
            "mode": "write",
            "collection": "/tmp/test.txt",
        }

        agent.run({"data": "test content"})

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.attributes[AGENT_TYPE] == "FileWriterAgent"
        assert span.name == AGENT_RUN_SPAN

        # Verify lifecycle events are present
        event_names = [e.name for e in span.events]
        assert "pre_process.start" in event_names
        assert "process.start" in event_names


# ---------------------------------------------------------------------------
# INT-120: Custom agent automatic span creation (AC6)
# ---------------------------------------------------------------------------


class TestCustomAgentSpan:
    """INT-120: Custom agent subclass gets automatic telemetry."""

    def test_custom_agent_automatic_span(
        self,
        otel_exporter,
        telemetry_service,
        mock_tracking_service,
        mock_state_adapter,
        mock_tracker,
    ) -> None:
        """INT-120: Custom agent with only process() override gets full span."""
        agent = _make_agent(
            _CustomAgent,
            telemetry_service=telemetry_service,
            tracking_service=mock_tracking_service,
            state_adapter=mock_state_adapter,
        )
        agent.set_execution_tracker(mock_tracker)
        result = agent.run({"input": "world"})

        spans = otel_exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        assert span.attributes[AGENT_TYPE] == "_CustomAgent"
        assert span.status.status_code == StatusCode.OK

        # All lifecycle events should be present
        event_names = [e.name for e in span.events]
        assert event_names == [
            "pre_process.start",
            "process.start",
            "post_process.start",
            "agent.complete",
        ]

        # mock_state_adapter returns {"input": "hello"} regardless of actual state
        assert result == {"result": "custom: hello"}


# ---------------------------------------------------------------------------
# INT-130: DI container wires telemetry to agent pipeline (AC7)
# ---------------------------------------------------------------------------


class TestDIContainerWiring:
    """INT-130: DI container wires telemetry_service to graph agent instantiation."""

    def test_graph_agent_instantiation_service_has_telemetry(self) -> None:
        """INT-130: graph_agent_instantiation_service holds telemetry singleton."""
        from unittest.mock import MagicMock

        from agentmap.di.container_parts.graph_agent import GraphAgentContainer
        from agentmap.di.container_parts.telemetry import TelemetryContainer

        # Create telemetry container
        mock_ls = MagicMock()
        mock_ls.get_logger.return_value = MagicMock()
        telemetry_container = TelemetryContainer(logging_service=mock_ls)
        telemetry_svc = telemetry_container.telemetry_service()

        # Create graph agent container with all required dependencies
        graph_agent_container = GraphAgentContainer(
            features_registry_service=MagicMock(),
            logging_service=mock_ls,
            custom_agent_loader=MagicMock(),
            app_config_service=MagicMock(),
            llm_service=MagicMock(),
            storage_service_manager=MagicMock(),
            host_protocol_configuration_service=MagicMock(),
            prompt_manager_service=MagicMock(),
            graph_checkpoint_service=MagicMock(),
            blob_storage_service=MagicMock(),
            execution_tracking_service=MagicMock(),
            state_adapter_service=MagicMock(),
            graph_bundle_service=MagicMock(),
            orchestrator_service=MagicMock(),
            declaration_registry_service=MagicMock(),
            telemetry_service=telemetry_svc,
        )

        instantiation_svc = graph_agent_container.graph_agent_instantiation_service()

        # Verify telemetry_service is not None
        assert instantiation_svc.telemetry_service is not None

        # Verify it is the same singleton instance
        assert instantiation_svc.telemetry_service is telemetry_svc

        # Verify it satisfies the protocol
        assert isinstance(instantiation_svc.telemetry_service, TelemetryServiceProtocol)


# ---------------------------------------------------------------------------
# INT-140: E02-F01 protocol and constants compatibility (AC8)
# ---------------------------------------------------------------------------


class TestCrossFeatureCompatibility:
    """INT-140: E02-F01 deliverables are importable and compatible."""

    def test_constants_importable_and_nonempty(self) -> None:
        """INT-140a: Required constants are importable and non-empty strings."""
        from agentmap.services.telemetry.constants import (
            AGENT_NAME,
            AGENT_RUN_SPAN,
            AGENT_TYPE,
            GRAPH_NAME,
            NODE_NAME,
        )

        for name, val in [
            ("AGENT_RUN_SPAN", AGENT_RUN_SPAN),
            ("AGENT_NAME", AGENT_NAME),
            ("AGENT_TYPE", AGENT_TYPE),
            ("NODE_NAME", NODE_NAME),
            ("GRAPH_NAME", GRAPH_NAME),
        ]:
            assert isinstance(val, str), f"{name} is not a string"
            assert len(val) > 0, f"{name} is empty"

    def test_protocol_defines_required_methods(self) -> None:
        """INT-140b: TelemetryServiceProtocol defines required methods."""
        import inspect

        methods = {
            name
            for name, _ in inspect.getmembers(
                TelemetryServiceProtocol, predicate=inspect.isfunction
            )
        }
        required = {
            "start_span",
            "add_span_event",
            "record_exception",
            "set_span_attributes",
        }
        missing = required - methods
        assert not missing, f"Protocol missing methods: {missing}"

    def test_otel_service_satisfies_protocol(self) -> None:
        """INT-140c: OTELTelemetryService satisfies TelemetryServiceProtocol."""
        svc = OTELTelemetryService()
        assert isinstance(svc, TelemetryServiceProtocol)

    def test_noop_service_satisfies_protocol(self) -> None:
        """INT-140d: NoOpTelemetryService satisfies TelemetryServiceProtocol."""
        svc = NoOpTelemetryService()
        assert isinstance(svc, TelemetryServiceProtocol)


# ---------------------------------------------------------------------------
# INT-150: Existing agent test suite passes unchanged (AC9)
# ---------------------------------------------------------------------------
# This acceptance criterion is validated by running:
#   uv run pytest tests/unit/agents/ tests/fresh_suite/unit/agents/
# without any modifications to existing test files.
# It is not encoded as a test in this file -- it is a CI gate.


# ---------------------------------------------------------------------------
# INT-151: NoOp telemetry matches pre-instrumentation behavior (AC10)
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """INT-151: Agent with None telemetry produces identical results."""

    def test_none_telemetry_same_result(
        self,
        mock_tracking_service,
        mock_state_adapter,
        mock_tracker,
    ) -> None:
        """INT-151: Agent with telemetry_service=None produces same state dict."""
        # Run WITH telemetry
        agent_with = _make_agent(
            _SuccessAgent,
            telemetry_service=NoOpTelemetryService(),
            tracking_service=mock_tracking_service,
            state_adapter=mock_state_adapter,
        )
        agent_with.set_execution_tracker(mock_tracker)
        result_with = agent_with.run({"input": "hello"})

        # Reset mock call counts
        mock_tracking_service.reset_mock()

        # Run WITHOUT telemetry
        agent_without = _make_agent(
            _SuccessAgent,
            telemetry_service=None,
            tracking_service=mock_tracking_service,
            state_adapter=mock_state_adapter,
        )
        agent_without.set_execution_tracker(mock_tracker)
        result_without = agent_without.run({"input": "hello"})

        # State dicts must be identical
        assert (
            result_with == result_without
        ), f"Results differ: with={result_with}, without={result_without}"

    def test_none_telemetry_same_tracking_calls(
        self,
        mock_state_adapter,
        mock_tracker,
    ) -> None:
        """INT-151: Same execution tracking calls with and without telemetry."""
        # Run with NoOp telemetry
        tracking_with = create_autospec(ExecutionTrackingService, instance=True)
        tracking_with.update_graph_success.return_value = False
        agent_with = _make_agent(
            _SuccessAgent,
            telemetry_service=NoOpTelemetryService(),
            tracking_service=tracking_with,
            state_adapter=mock_state_adapter,
        )
        agent_with.set_execution_tracker(mock_tracker)
        agent_with.run({"input": "hello"})

        # Run without telemetry
        tracking_without = create_autospec(ExecutionTrackingService, instance=True)
        tracking_without.update_graph_success.return_value = False
        agent_without = _make_agent(
            _SuccessAgent,
            telemetry_service=None,
            tracking_service=tracking_without,
            state_adapter=mock_state_adapter,
        )
        agent_without.set_execution_tracker(mock_tracker)
        agent_without.run({"input": "hello"})

        # Same tracking methods called with same args
        assert tracking_with.record_node_start.call_count == (
            tracking_without.record_node_start.call_count
        )
        assert tracking_with.record_node_result.call_count == (
            tracking_without.record_node_result.call_count
        )

        # Verify call arguments match
        with_start_args = tracking_with.record_node_start.call_args
        without_start_args = tracking_without.record_node_start.call_args
        assert with_start_args == without_start_args

    def test_none_telemetry_error_path_same_result(
        self,
        mock_state_adapter,
        mock_tracker,
    ) -> None:
        """INT-151: Error path produces same result with and without telemetry."""
        tracking_with = create_autospec(ExecutionTrackingService, instance=True)
        tracking_with.update_graph_success.return_value = False
        agent_with = _make_agent(
            _FailingAgent,
            telemetry_service=NoOpTelemetryService(),
            tracking_service=tracking_with,
            state_adapter=mock_state_adapter,
        )
        agent_with.set_execution_tracker(mock_tracker)
        result_with = agent_with.run({"input": "hello"})

        tracking_without = create_autospec(ExecutionTrackingService, instance=True)
        tracking_without.update_graph_success.return_value = False
        agent_without = _make_agent(
            _FailingAgent,
            telemetry_service=None,
            tracking_service=tracking_without,
            state_adapter=mock_state_adapter,
        )
        agent_without.set_execution_tracker(mock_tracker)
        result_without = agent_without.run({"input": "hello"})

        # Both should return error dicts with same structure
        assert result_with.get("last_action_success") == result_without.get(
            "last_action_success"
        )
        assert result_with.get("graph_success") == result_without.get("graph_success")
        assert "errors" in result_with
        assert "errors" in result_without
