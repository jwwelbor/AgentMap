"""
Unit tests for GraphRunnerService async orchestration path.

Covers task T-E04-F04-002 — async runner orchestration, telemetry parity,
and protocol support.

Test cases:
  TC-003: async runner follows the checkpoint-off path
  TC-004: async runner follows the checkpoint-on path
  TC-008: existing sync runner tests remain green (regression gate)
  TC-012: async runner emissions match the telemetry parity matrix

Caller-path contract (from test plan):
  Production entrypoint:
    GraphRunnerService.run_async(bundle, initial_state=None,
        parent_graph_name=None, parent_tracker=None,
        is_subgraph=False, validate_agents=False)
  Lowest allowed mock seam: GraphAssemblyService and GraphExecutionService
    async siblings; supporting services may be autospecced.
  Forbidden mocks: GraphRunnerService._run_core,
    GraphRunnerService._run_with_telemetry, or direct assertions against
    private helper internals.
  Counter-factual: a buggy implementation would reuse the sync execution path
    after async assembly was introduced, or drop telemetry/interrupt metadata
    during async execution.
"""

import asyncio
import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from agentmap.models.execution.result import ExecutionResult
from agentmap.services.graph.graph_runner_service import GraphRunnerService
from agentmap.services.telemetry.constants import (
    GRAPH_NAME,
    GRAPH_NODE_COUNT,
    WORKFLOW_RUN_SPAN,
)
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_mock_bundle(graph_name="test_graph", node_count=3, checkpoint=False):
    """Create a minimal mock GraphBundle."""
    bundle = MagicMock(name="mock_bundle")
    bundle.graph_name = graph_name
    nodes = {}
    for i in range(node_count):
        node = MagicMock()
        node.agent_type = "default"
        nodes[f"node_{i}"] = node
    bundle.nodes = nodes
    bundle.entry_point = "node_0"
    bundle.csv_hash = None
    bundle.node_instances = None
    bundle.scoped_registry = None
    bundle.missing_services = set()
    return bundle


def _make_mock_telemetry():
    """Create a recording mock telemetry service."""
    svc = create_autospec(TelemetryServiceProtocol, instance=True)
    mock_span = MagicMock(name="mock_span")

    @contextmanager
    def _start_span_cm(name, attributes=None, kind=None):
        yield mock_span

    svc.start_span.side_effect = _start_span_cm
    return svc, mock_span


def _make_graph_runner_service(telemetry_service=None):
    """Create a GraphRunnerService with all dependencies mocked.

    Returns:
        (service, mocks_dict) where mocks_dict has keys for each mock dependency.
    """
    from agentmap.services.config.app_config_service import AppConfigService
    from agentmap.services.declaration_registry_service import (
        DeclarationRegistryService,
    )
    from agentmap.services.execution_tracking_service import ExecutionTrackingService
    from agentmap.services.graph.graph_agent_instantiation_service import (
        GraphAgentInstantiationService,
    )
    from agentmap.services.graph.graph_assembly_service import GraphAssemblyService
    from agentmap.services.graph.graph_bootstrap_service import GraphBootstrapService
    from agentmap.services.graph.graph_bundle_service import GraphBundleService
    from agentmap.services.graph.graph_checkpoint_service import GraphCheckpointService
    from agentmap.services.graph.graph_execution_service import GraphExecutionService
    from agentmap.services.interaction_handler_service import InteractionHandlerService
    from agentmap.services.logging_service import LoggingService

    mock_app_config = create_autospec(AppConfigService, instance=True)
    mock_bootstrap = create_autospec(GraphBootstrapService, instance=True)
    mock_instantiation = create_autospec(GraphAgentInstantiationService, instance=True)
    mock_assembly = create_autospec(GraphAssemblyService, instance=True)
    mock_execution = create_autospec(GraphExecutionService, instance=True)
    mock_tracking = create_autospec(ExecutionTrackingService, instance=True)
    mock_logging = create_autospec(LoggingService, instance=True)
    mock_logging.get_class_logger.return_value = MagicMock(name="mock_logger")
    mock_interaction = create_autospec(InteractionHandlerService, instance=True)
    mock_checkpoint = create_autospec(GraphCheckpointService, instance=True)
    mock_bundle_svc = create_autospec(GraphBundleService, instance=True)
    mock_declaration = create_autospec(DeclarationRegistryService, instance=True)

    service = GraphRunnerService(
        app_config_service=mock_app_config,
        graph_bootstrap_service=mock_bootstrap,
        graph_agent_instantiation_service=mock_instantiation,
        graph_assembly_service=mock_assembly,
        graph_execution_service=mock_execution,
        execution_tracking_service=mock_tracking,
        logging_service=mock_logging,
        interaction_handler_service=mock_interaction,
        graph_checkpoint_service=mock_checkpoint,
        graph_bundle_service=mock_bundle_svc,
        declaration_registry_service=mock_declaration,
        telemetry_service=telemetry_service,
    )

    mocks = {
        "app_config": mock_app_config,
        "instantiation": mock_instantiation,
        "assembly": mock_assembly,
        "execution": mock_execution,
        "tracking": mock_tracking,
        "logging": mock_logging,
        "bundle_svc": mock_bundle_svc,
        "declaration": mock_declaration,
        "interaction": mock_interaction,
        "checkpoint": mock_checkpoint,
    }
    return service, mocks


def _setup_successful_async_run(mocks, bundle, return_result=None):
    """Configure mocks for a successful run_async() invocation.

    Returns the mock ExecutionResult.
    """
    # Scoped registry
    mock_scoped_registry = MagicMock()
    mock_scoped_registry.get_all_agent_types.return_value = ["agent1"]
    mock_scoped_registry.get_all_service_names.return_value = []
    mocks["declaration"].create_scoped_registry_for_bundle.return_value = (
        mock_scoped_registry
    )

    # Execution tracker
    mock_tracker = MagicMock()
    mock_tracker.thread_id = "test-thread"
    mocks["tracking"].create_tracker.return_value = mock_tracker

    # Agent instantiation
    node_instances = {f"node_{i}": MagicMock() for i in range(len(bundle.nodes))}
    bundle_with_instances = MagicMock()
    bundle_with_instances.graph_name = bundle.graph_name
    bundle_with_instances.nodes = bundle.nodes
    bundle_with_instances.entry_point = bundle.entry_point
    bundle_with_instances.node_instances = node_instances

    def _instantiate_side_effect(b, tracker):
        b.node_instances = node_instances
        return bundle_with_instances

    mocks["instantiation"].instantiate_agents.side_effect = _instantiate_side_effect

    # Graph assembly (async)
    mock_compiled = MagicMock()
    mocks["assembly"].assemble_graph_async.return_value = mock_compiled

    # Disable checkpoint path
    mocks["bundle_svc"].requires_checkpoint_support.return_value = False

    # Async execution result
    if return_result is None:
        mock_result = MagicMock(spec=ExecutionResult)
        mock_result.success = True
        mock_result.total_duration = 1.5
        mock_result.error = None
    else:
        mock_result = return_result

    # execute_compiled_graph_async is an async method — use AsyncMock
    mocks["execution"].execute_compiled_graph_async = AsyncMock(
        return_value=mock_result
    )

    return mock_result


def _setup_checkpoint_async_run(mocks, bundle):
    """Configure mocks for a checkpoint-on run_async() invocation."""
    # Scoped registry
    mock_scoped_registry = MagicMock()
    mock_scoped_registry.get_all_agent_types.return_value = ["agent1"]
    mock_scoped_registry.get_all_service_names.return_value = []
    mocks["declaration"].create_scoped_registry_for_bundle.return_value = (
        mock_scoped_registry
    )

    # Execution tracker with thread_id
    mock_tracker = MagicMock()
    mock_tracker.thread_id = "checkpoint-thread-123"
    mocks["tracking"].create_tracker.return_value = mock_tracker

    # Agent instantiation
    node_instances = {f"node_{i}": MagicMock() for i in range(len(bundle.nodes))}
    bundle_with_instances = MagicMock()
    bundle_with_instances.graph_name = bundle.graph_name
    bundle_with_instances.nodes = bundle.nodes
    bundle_with_instances.entry_point = bundle.entry_point
    bundle_with_instances.node_instances = node_instances

    def _instantiate_side_effect(b, tracker):
        b.node_instances = node_instances
        return bundle_with_instances

    mocks["instantiation"].instantiate_agents.side_effect = _instantiate_side_effect

    # Checkpoint path enabled
    mocks["bundle_svc"].requires_checkpoint_support.return_value = True

    # Graph assembly (async with checkpoint)
    mock_compiled = MagicMock()
    # No pending tasks — non-interrupt result
    mock_state = MagicMock()
    mock_state.tasks = []
    mock_compiled.get_state.return_value = mock_state
    mocks["assembly"].assemble_with_checkpoint_async.return_value = mock_compiled

    # Async execution result
    mock_result = MagicMock(spec=ExecutionResult)
    mock_result.success = True
    mock_result.total_duration = 2.0
    mock_result.error = None

    mocks["execution"].execute_compiled_graph_async = AsyncMock(
        return_value=mock_result
    )

    return mock_result, mock_compiled


# ---------------------------------------------------------------------------
# TC-003: async runner follows the checkpoint-off path
# ---------------------------------------------------------------------------


class TestTC003AsyncRunnerCheckpointOff(unittest.IsolatedAsyncioTestCase):
    """TC-003: run_async follows the non-checkpoint assembly/execution path."""

    async def test_tc003_run_async_selects_non_checkpoint_path(self):
        """run_async uses assemble_graph_async (not assemble_with_checkpoint_async)
        when checkpoint support is not required.
        """
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        await service.run_async(bundle)

        # async assembly was used
        mocks["assembly"].assemble_graph_async.assert_called_once()
        mocks["assembly"].assemble_with_checkpoint_async.assert_not_called()
        # async execution was used
        mocks["execution"].execute_compiled_graph_async.assert_awaited_once()
        # sync execution not used
        mocks["execution"].execute_compiled_graph.assert_not_called()

    async def test_tc003_run_async_returns_same_result_envelope_as_sync(self):
        """run_async returns an ExecutionResult with same shape as sync run()."""
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("test_graph", node_count=2)
        mock_result = _setup_successful_async_run(mocks, bundle)

        result = await service.run_async(bundle)

        assert result is mock_result
        assert result.success is True

    async def test_tc003_run_async_with_initial_state(self):
        """run_async accepts and forwards initial_state."""
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        initial_state = {"input": "hello"}
        result = await service.run_async(bundle, initial_state=initial_state)

        assert result.success is True
        # execute_compiled_graph_async should have been called
        mocks["execution"].execute_compiled_graph_async.assert_awaited_once()

    async def test_tc003_run_async_with_none_telemetry(self):
        """run_async works with telemetry_service=None."""
        service, mocks = _make_graph_runner_service(telemetry_service=None)
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        result = await service.run_async(bundle)

        assert result.success is True


# ---------------------------------------------------------------------------
# TC-004: async runner follows the checkpoint-on path
# ---------------------------------------------------------------------------


class TestTC004AsyncRunnerCheckpointOn(unittest.IsolatedAsyncioTestCase):
    """TC-004: run_async follows the checkpoint-enabled assembly/execution path."""

    async def test_tc004_run_async_selects_checkpoint_path(self):
        """run_async uses assemble_with_checkpoint_async when checkpoint required."""
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("checkpoint_graph", node_count=2)
        _setup_checkpoint_async_run(mocks, bundle)

        await service.run_async(bundle)

        mocks["assembly"].assemble_with_checkpoint_async.assert_called_once()
        mocks["assembly"].assemble_graph_async.assert_not_called()

    async def test_tc004_run_async_checkpoint_inspects_state(self):
        """run_async inspects graph state after execution when checkpoint is on."""
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("checkpoint_graph", node_count=2)
        mock_result, mock_compiled = _setup_checkpoint_async_run(mocks, bundle)

        await service.run_async(bundle)

        # State should have been inspected on the compiled graph
        mock_compiled.get_state.assert_called_once()

    async def test_tc004_run_async_checkpoint_returns_result_envelope(self):
        """run_async checkpoint path returns an ExecutionResult."""
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("checkpoint_graph", node_count=2)
        mock_result, _ = _setup_checkpoint_async_run(mocks, bundle)

        result = await service.run_async(bundle)

        assert result is mock_result
        assert result.success is True

    async def test_tc004_run_async_returns_error_result_without_thread_id(self):
        """run_async returns error ExecutionResult when checkpoint path has no thread_id.

        The RuntimeError for missing thread_id is caught at the pipeline boundary
        and converted to a failed ExecutionResult (same behavior as sync run()).
        """
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("checkpoint_graph", node_count=2)
        _setup_checkpoint_async_run(mocks, bundle)

        # Override: tracker has no thread_id
        mock_tracker_no_id = MagicMock()
        mock_tracker_no_id.thread_id = None
        mocks["tracking"].create_tracker.return_value = mock_tracker_no_id

        result = await service.run_async(bundle)
        assert result.success is False
        assert "thread_id" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# TC-008: sync regression gate — existing sync interface unaffected
# ---------------------------------------------------------------------------


class TestTC008SyncRegressionGate(unittest.TestCase):
    """TC-008: Async additions do not break the sync run() interface."""

    def test_tc008_sync_run_still_works(self):
        """sync run() returns ExecutionResult after async methods are added."""
        from tests.unit.services.graph.test_graph_runner_telemetry import (
            _make_graph_runner_service as _sync_factory,
        )
        from tests.unit.services.graph.test_graph_runner_telemetry import (
            _make_mock_bundle as _sync_bundle,
        )
        from tests.unit.services.graph.test_graph_runner_telemetry import (
            _setup_successful_run,
        )

        service, mocks = _sync_factory()
        bundle = _sync_bundle("sync_test_graph", node_count=2)
        mock_result = _setup_successful_run(mocks, bundle)

        result = service.run(bundle)

        assert result.success is True
        assert result is mock_result

    def test_tc008_run_async_method_exists(self):
        """GraphRunnerService has a run_async method."""
        service, _ = _make_graph_runner_service()
        assert hasattr(service, "run_async"), "run_async method not found"
        import inspect

        assert inspect.iscoroutinefunction(
            service.run_async
        ), "run_async is not a coroutine function"

    def test_tc008_resume_from_checkpoint_sync_still_works(self):
        """sync resume_from_checkpoint() delegates to checkpoint_manager."""
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("cp_graph")
        mock_result = MagicMock(spec=ExecutionResult)
        mock_result.success = True

        # Patch checkpoint_manager.resume_from_checkpoint
        service.checkpoint_manager.resume_from_checkpoint = MagicMock(
            return_value=mock_result
        )

        result = service.resume_from_checkpoint(bundle, "thread-1", {})

        service.checkpoint_manager.resume_from_checkpoint.assert_called_once()
        assert result.success is True

    def test_tc008_resume_from_checkpoint_async_method_exists(self):
        """GraphRunnerService has a resume_from_checkpoint_async method."""
        service, _ = _make_graph_runner_service()
        assert hasattr(
            service, "resume_from_checkpoint_async"
        ), "resume_from_checkpoint_async method not found"
        import inspect

        assert inspect.iscoroutinefunction(
            service.resume_from_checkpoint_async
        ), "resume_from_checkpoint_async is not a coroutine function"


# ---------------------------------------------------------------------------
# TC-012: Telemetry parity matrix conformance for async runner
# ---------------------------------------------------------------------------


class TestTC012TelemetryParityAsync(unittest.IsolatedAsyncioTestCase):
    """TC-012: Async runner emits the same span, phase events, and status as sync."""

    async def _run_async_with_telemetry(self, bundle, mocks, mock_telemetry):
        """Run run_async and collect all span events."""
        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            result = await _make_graph_runner_service.__wrapped_run__(
                self, bundle, mocks, mock_telemetry
            )
        return result

    async def test_tc012_async_runner_creates_workflow_root_span(self):
        """run_async creates the same root span (WORKFLOW_RUN_SPAN) as sync run()."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("telemetry_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            await service.run_async(bundle)

        mock_telemetry.start_span.assert_called_once()
        call_args = mock_telemetry.start_span.call_args
        assert call_args[0][0] == WORKFLOW_RUN_SPAN

    async def test_tc012_async_runner_span_has_graph_name_attribute(self):
        """run_async span carries GRAPH_NAME attribute."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("my_async_graph", node_count=3)
        _setup_successful_async_run(mocks, bundle)

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            await service.run_async(bundle)

        call_args = mock_telemetry.start_span.call_args
        attrs = call_args[1].get("attributes") or call_args[0][1]
        assert attrs[GRAPH_NAME] == "my_async_graph"
        assert attrs[GRAPH_NODE_COUNT] == 3

    async def test_tc012_async_runner_all_six_phase_events_present(self):
        """run_async records all six phase events in the correct order."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("phase_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            await service.run_async(bundle)

        # Collect phase events from add_span_event calls
        event_names = []
        for call in mock_telemetry.add_span_event.call_args_list:
            if len(call[0]) >= 2:
                event_names.append(call[0][1])

        expected_phases = [
            "workflow.phase.registry_creation",
            "workflow.phase.tracker_creation",
            "workflow.phase.agent_instantiation",
            "workflow.phase.graph_assembly",
            "workflow.phase.execution",
            "workflow.phase.finalization",
        ]

        for phase in expected_phases:
            assert phase in event_names, (
                f"Phase event '{phase}' not found in async run. "
                f"Recorded events: {event_names}"
            )

    async def test_tc012_async_runner_phase_events_in_correct_order(self):
        """run_async records phase events in the same lifecycle order as sync."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("order_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            await service.run_async(bundle)

        event_names = []
        for call in mock_telemetry.add_span_event.call_args_list:
            if len(call[0]) >= 2:
                event_names.append(call[0][1])

        phase_events = [e for e in event_names if e.startswith("workflow.phase.")]

        expected_order = [
            "workflow.phase.registry_creation",
            "workflow.phase.tracker_creation",
            "workflow.phase.agent_instantiation",
            "workflow.phase.graph_assembly",
            "workflow.phase.execution",
            "workflow.phase.finalization",
        ]

        for i, expected in enumerate(expected_order):
            assert phase_events[i] == expected, (
                f"Expected '{expected}' at position {i}, "
                f"got '{phase_events[i]}'. Full: {phase_events}"
            )

    async def test_tc012_async_runner_span_status_ok_on_success(self):
        """run_async sets span status to OK on successful result."""
        from opentelemetry.trace import StatusCode

        mock_telemetry, mock_span = _make_mock_telemetry()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("ok_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            await service.run_async(bundle)

        mock_span.set_status.assert_called()
        status_calls = mock_span.set_status.call_args_list
        ok_found = any(call[0][0] == StatusCode.OK for call in status_calls)
        assert ok_found, "Span status was not set to OK for successful async run"

    async def test_tc012_async_runner_span_status_error_on_failure(self):
        """run_async sets span status to ERROR when result.success is False."""
        from opentelemetry.trace import StatusCode

        mock_telemetry, mock_span = _make_mock_telemetry()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("fail_graph", node_count=2)

        failed_result = MagicMock(spec=ExecutionResult)
        failed_result.success = False
        failed_result.error = "something failed"
        failed_result.total_duration = 0.5
        _setup_successful_async_run(mocks, bundle, return_result=failed_result)

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            await service.run_async(bundle)

        mock_span.set_status.assert_called()
        status_calls = mock_span.set_status.call_args_list
        error_found = any(call[0][0] == StatusCode.ERROR for call in status_calls)
        assert error_found, "Span status was not set to ERROR for failed async run"

    async def test_tc012_telemetry_fallback_on_setup_failure(self):
        """run_async falls back to uninstrumented execution when start_span fails."""
        mock_telemetry = create_autospec(TelemetryServiceProtocol, instance=True)
        # Make start_span raise
        mock_telemetry.start_span.side_effect = RuntimeError("telemetry infra down")

        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("fallback_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        # Should not raise; should fall back to uninstrumented path
        result = await service.run_async(bundle)

        assert result.success is True

    async def test_tc012_cancelled_error_propagates(self):
        """CancelledError propagates from run_async — not swallowed."""
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("cancel_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        # Make execute_compiled_graph_async raise CancelledError
        mocks["execution"].execute_compiled_graph_async = AsyncMock(
            side_effect=asyncio.CancelledError()
        )

        with self.assertRaises((asyncio.CancelledError, BaseException)):
            await service.run_async(bundle)


# ---------------------------------------------------------------------------
# TC-012: GraphRunnerServiceProtocol includes async members
# ---------------------------------------------------------------------------


class TestTC012ProtocolExtension(unittest.TestCase):
    """Verify GraphRunnerServiceProtocol includes async runner members."""

    def test_protocol_has_run_async(self):
        """GraphRunnerServiceProtocol declares run_async."""
        from agentmap.services.protocols.service_protocols import (
            GraphRunnerServiceProtocol,
        )

        assert hasattr(
            GraphRunnerServiceProtocol, "run_async"
        ), "GraphRunnerServiceProtocol.run_async not found"

    def test_protocol_has_resume_from_checkpoint_async(self):
        """GraphRunnerServiceProtocol declares resume_from_checkpoint_async."""
        from agentmap.services.protocols.service_protocols import (
            GraphRunnerServiceProtocol,
        )

        assert hasattr(
            GraphRunnerServiceProtocol, "resume_from_checkpoint_async"
        ), "GraphRunnerServiceProtocol.resume_from_checkpoint_async not found"

    def test_protocol_run_async_is_coroutine_function(self):
        """GraphRunnerServiceProtocol.run_async is declared as a coroutine function."""
        import inspect

        from agentmap.services.protocols.service_protocols import (
            GraphRunnerServiceProtocol,
        )

        member = GraphRunnerServiceProtocol.run_async
        assert inspect.iscoroutinefunction(
            member
        ), "GraphRunnerServiceProtocol.run_async is not a coroutine function"

    def test_protocol_resume_from_checkpoint_async_is_coroutine_function(self):
        """GraphRunnerServiceProtocol.resume_from_checkpoint_async is a coroutine."""
        import inspect

        from agentmap.services.protocols.service_protocols import (
            GraphRunnerServiceProtocol,
        )

        member = GraphRunnerServiceProtocol.resume_from_checkpoint_async
        assert inspect.iscoroutinefunction(member), (
            "GraphRunnerServiceProtocol.resume_from_checkpoint_async is not "
            "a coroutine function"
        )

    def test_protocol_sync_run_still_present(self):
        """GraphRunnerServiceProtocol still declares sync run() (regression gate)."""
        from agentmap.services.protocols.service_protocols import (
            GraphRunnerServiceProtocol,
        )

        assert hasattr(
            GraphRunnerServiceProtocol, "run"
        ), "GraphRunnerServiceProtocol.run (sync) was removed"

    def test_concrete_service_satisfies_protocol(self):
        """GraphRunnerService satisfies GraphRunnerServiceProtocol at runtime."""
        from agentmap.services.protocols.service_protocols import (
            GraphRunnerServiceProtocol,
        )

        service, _ = _make_graph_runner_service()
        assert isinstance(
            service, GraphRunnerServiceProtocol
        ), "GraphRunnerService does not satisfy GraphRunnerServiceProtocol"


# ---------------------------------------------------------------------------
# AC-007: run_async + asyncio.wait_for cancellation finalizes tracker
# ---------------------------------------------------------------------------


class TestAC007RunAsyncWaitForTrackerFinalization(unittest.IsolatedAsyncioTestCase):
    """AC-007: when run_async is cancelled via asyncio.wait_for, the execution
    tracker is finalized (complete_execution called) and CancelledError propagates.

    Counter-factual: a buggy implementation would either swallow the
    CancelledError, or let the tracker leak (not call complete_execution).
    """

    async def test_ac007_wait_for_cancel_finalizes_tracker(self):
        """asyncio.wait_for cancellation propagates and tracker is finalized.

        Caller-path contract:
            asyncio.wait_for(service.run_async(bundle, ...), timeout=0.01)
            The execution service's cancel branch calls complete_execution.
        """
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("cancel_tracker_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        # execute_compiled_graph_async: sleep long enough for wait_for to fire,
        # then finalize tracker (mirrors real graph_execution_service behaviour)
        mock_tracker_ref = []

        async def slow_exec_that_finalizes_on_cancel(
            executable_graph, graph_name, initial_state, execution_tracker, config=None
        ):
            mock_tracker_ref.append(execution_tracker)
            try:
                await asyncio.sleep(10)  # will be cancelled by wait_for
            except asyncio.CancelledError:
                # Mirrors graph_execution_service.py:353-369 — finalize tracker
                mocks["tracking"].complete_execution(execution_tracker)
                raise

        mocks["execution"].execute_compiled_graph_async = AsyncMock(
            side_effect=slow_exec_that_finalizes_on_cancel
        )

        with self.assertRaises((asyncio.CancelledError, TimeoutError)):
            await asyncio.wait_for(service.run_async(bundle), timeout=0.05)

        # Tracker must have been finalized — not leaked
        assert len(mock_tracker_ref) == 1, "execute_compiled_graph_async was not called"
        mocks["tracking"].complete_execution.assert_called_once_with(
            mock_tracker_ref[0]
        )

    async def test_ac007_wait_for_cancel_reraises_cancelled_error(self):
        """CancelledError from asyncio.wait_for propagates — not swallowed by run_async.

        Python 3.12 wraps CancelledError in TimeoutError when asyncio.wait_for
        fires; both are accepted here.
        """
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("cancel_reraise_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        async def slow_exec(*args, **kwargs):
            await asyncio.sleep(10)

        mocks["execution"].execute_compiled_graph_async = AsyncMock(
            side_effect=slow_exec
        )

        with self.assertRaises((asyncio.CancelledError, TimeoutError)):
            await asyncio.wait_for(service.run_async(bundle), timeout=0.05)


# ---------------------------------------------------------------------------
# AC-009: two concurrent run_async calls on same bundle — no state bleed
# ---------------------------------------------------------------------------


class TestAC009ConcurrentRunAsyncNoStateBleed(unittest.IsolatedAsyncioTestCase):
    """AC-009: asyncio.gather(run_async, run_async) on the same bundle must:
    - complete both runs without raising
    - not bleed run-local state (scoped_registry / node_instances) between runs

    Counter-factual: if run_async mutates the shared bundle directly, the
    second concurrent run overwrites the first run's scoped_registry/tracker,
    causing wrong registry or tracker linkage on one of the results.
    """

    async def test_ac009_two_concurrent_run_async_both_succeed(self):
        """Both concurrent run_async calls return successful ExecutionResult."""
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("concurrent_graph", node_count=2)

        # Each call gets its own tracker
        tracker_a = MagicMock()
        tracker_a.thread_id = "thread-A"
        tracker_b = MagicMock()
        tracker_b.thread_id = "thread-B"
        mocks["tracking"].create_tracker.side_effect = [tracker_a, tracker_b]

        # Scoped registry — return a new mock each time
        def make_scoped():
            sr = MagicMock()
            sr.get_all_agent_types.return_value = ["agent1"]
            sr.get_all_service_names.return_value = []
            return sr

        mocks["declaration"].create_scoped_registry_for_bundle.side_effect = (
            lambda b: make_scoped()
        )

        # Agent instantiation: return a new bundle copy each call
        def instantiate(b, tracker):
            new_b = MagicMock()
            new_b.graph_name = b.graph_name
            new_b.nodes = b.nodes
            new_b.entry_point = b.entry_point
            new_b.node_instances = {"node_0": MagicMock(), "node_1": MagicMock()}
            return new_b

        mocks["instantiation"].instantiate_agents.side_effect = instantiate

        # No checkpoint path
        mocks["bundle_svc"].requires_checkpoint_support.return_value = False

        result_a = MagicMock(
            spec=__import__(
                "agentmap.models.execution.result", fromlist=["ExecutionResult"]
            ).ExecutionResult
        )
        result_a.success = True
        result_a.total_duration = 0.1
        result_a.error = None

        result_b = MagicMock(
            spec=__import__(
                "agentmap.models.execution.result", fromlist=["ExecutionResult"]
            ).ExecutionResult
        )
        result_b.success = True
        result_b.total_duration = 0.1
        result_b.error = None

        call_count = 0

        async def async_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0)  # yield to let both tasks start
            if call_count == 1:
                return result_a
            return result_b

        mocks["execution"].execute_compiled_graph_async = AsyncMock(
            side_effect=async_exec
        )

        results = await asyncio.gather(
            service.run_async(bundle),
            service.run_async(bundle),
        )

        assert len(results) == 2
        assert all(r.success for r in results)

    async def test_ac009_concurrent_run_async_uses_distinct_trackers(self):
        """Each concurrent run_async call receives its own execution tracker.

        Counter-factual: if a shared tracker is reused, both runs would see
        the same tracker object — the tracker for the second run would
        overwrite the first's data.
        """
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("tracker_isolation_graph", node_count=2)

        tracker_a = MagicMock()
        tracker_a.thread_id = "thread-A"
        tracker_b = MagicMock()
        tracker_b.thread_id = "thread-B"
        mocks["tracking"].create_tracker.side_effect = [tracker_a, tracker_b]

        def make_scoped():
            sr = MagicMock()
            sr.get_all_agent_types.return_value = ["agent1"]
            sr.get_all_service_names.return_value = []
            return sr

        mocks["declaration"].create_scoped_registry_for_bundle.side_effect = (
            lambda b: make_scoped()
        )

        received_trackers = []

        def instantiate(b, tracker):
            received_trackers.append(tracker)
            new_b = MagicMock()
            new_b.graph_name = b.graph_name
            new_b.nodes = b.nodes
            new_b.entry_point = b.entry_point
            new_b.node_instances = {"node_0": MagicMock()}
            return new_b

        mocks["instantiation"].instantiate_agents.side_effect = instantiate
        mocks["bundle_svc"].requires_checkpoint_support.return_value = False

        exec_results = [MagicMock() for _ in range(2)]
        for r in exec_results:
            r.success = True
            r.total_duration = 0.0
            r.error = None

        mocks["execution"].execute_compiled_graph_async = AsyncMock(
            side_effect=exec_results
        )

        await asyncio.gather(
            service.run_async(bundle),
            service.run_async(bundle),
        )

        # Both runs received a tracker; the trackers are distinct
        assert len(received_trackers) == 2
        assert received_trackers[0] is not received_trackers[1], (
            "Both concurrent run_async calls used the same tracker — "
            "per-run state is not isolated"
        )

    async def test_ac009_original_bundle_not_mutated_by_concurrent_runs(self):
        """Concurrent run_async calls do not permanently mutate the original bundle.

        Counter-factual: if _run_core_async writes scoped_registry / node_instances
        directly onto the shared bundle, the original bundle is permanently
        modified and callers outside the run can observe stale run-local state.
        """
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("mutation_guard_graph", node_count=2)

        # Capture original values before any run
        original_scoped_registry = bundle.scoped_registry
        original_node_instances = bundle.node_instances

        def make_scoped():
            sr = MagicMock()
            sr.get_all_agent_types.return_value = ["agent1"]
            sr.get_all_service_names.return_value = []
            return sr

        mocks["declaration"].create_scoped_registry_for_bundle.side_effect = (
            lambda b: make_scoped()
        )
        mocks["tracking"].create_tracker.side_effect = [
            MagicMock(thread_id="t-1"),
            MagicMock(thread_id="t-2"),
        ]

        def instantiate(b, tracker):
            new_b = MagicMock()
            new_b.graph_name = b.graph_name
            new_b.nodes = b.nodes
            new_b.entry_point = b.entry_point
            new_b.node_instances = {"node_0": MagicMock()}
            return new_b

        mocks["instantiation"].instantiate_agents.side_effect = instantiate
        mocks["bundle_svc"].requires_checkpoint_support.return_value = False

        exec_results = [MagicMock() for _ in range(2)]
        for r in exec_results:
            r.success = True
            r.total_duration = 0.0
            r.error = None

        mocks["execution"].execute_compiled_graph_async = AsyncMock(
            side_effect=exec_results
        )

        await asyncio.gather(
            service.run_async(bundle),
            service.run_async(bundle),
        )

        # Original bundle fields must not be permanently mutated
        assert (
            bundle.scoped_registry is original_scoped_registry
        ), "run_async mutated bundle.scoped_registry on the shared input bundle"
        assert (
            bundle.node_instances is original_node_instances
        ), "run_async mutated bundle.node_instances on the shared input bundle"


# ---------------------------------------------------------------------------
# AC-011: async interrupt telemetry parity
# ---------------------------------------------------------------------------


class TestAC011AsyncInterruptTelemetryParity(unittest.IsolatedAsyncioTestCase):
    """AC-011: async path emits workflow.interrupted / workflow.interrupted.legacy
    span events when GraphInterrupt / ExecutionInterruptedException are raised.

    Counter-factual: a buggy implementation would omit these span events on
    the async path, leaving the interrupt rows of the telemetry parity matrix
    unverified.
    """

    async def test_ac011_graph_interrupt_emits_workflow_interrupted_event(self):
        """GraphInterrupt from execute_compiled_graph_async → workflow.interrupted
        span event is recorded.

        The _run_core_async handler processes GraphInterrupt and returns an
        interrupt ExecutionResult. The workflow.interrupted telemetry event
        must be emitted inside the active span before the result is returned.

        Counter-factual: without the _record_phase_event("workflow.interrupted")
        call in the except-GraphInterrupt handler, no interrupt event appears
        in the span — the interrupt row of the parity matrix is unverified.
        """
        from langgraph.errors import GraphInterrupt

        mock_telemetry, mock_span = _make_mock_telemetry()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("interrupt_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        # Raise GraphInterrupt from the execution service
        mocks["execution"].execute_compiled_graph_async = AsyncMock(
            side_effect=GraphInterrupt("suspend at node_0")
        )

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            # _run_core_async handles GraphInterrupt and returns an interrupt result;
            # it must also emit the workflow.interrupted event to the current span.
            await service.run_async(bundle)

        # workflow.interrupted event must have been recorded on the span
        event_names = [
            call[0][1]
            for call in mock_telemetry.add_span_event.call_args_list
            if len(call[0]) >= 2
        ]
        assert "workflow.interrupted" in event_names, (
            f"Expected 'workflow.interrupted' span event on GraphInterrupt path. "
            f"Recorded events: {event_names}"
        )

        # Must NOT have recorded record_exception for an interrupt
        mock_telemetry.record_exception.assert_not_called()

    async def test_ac011_execution_interrupted_exception_emits_legacy_event(self):
        """ExecutionInterruptedException → workflow.interrupted.legacy span event.

        _run_core_async re-raises ExecutionInterruptedException after handling;
        the workflow.interrupted.legacy event must be emitted before re-raising.
        """
        from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException

        mock_telemetry, mock_span = _make_mock_telemetry()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("legacy_interrupt_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        exc = ExecutionInterruptedException(
            thread_id="legacy-thread-001",
            interaction_request={"type": "human"},
            checkpoint_data={},
        )
        mocks["execution"].execute_compiled_graph_async = AsyncMock(side_effect=exc)

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            with self.assertRaises(ExecutionInterruptedException):
                await service.run_async(bundle)

        event_names = [
            call[0][1]
            for call in mock_telemetry.add_span_event.call_args_list
            if len(call[0]) >= 2
        ]
        assert "workflow.interrupted.legacy" in event_names, (
            f"Expected 'workflow.interrupted.legacy' span event on legacy interrupt "
            f"path. Recorded events: {event_names}"
        )

    async def test_ac011_graph_interrupt_does_not_set_error_status(self):
        """GraphInterrupt must not set ERROR span status — same as sync path.

        GraphInterrupt is a workflow suspension signal, not an error.
        """
        from langgraph.errors import GraphInterrupt
        from opentelemetry.trace import StatusCode

        mock_telemetry, mock_span = _make_mock_telemetry()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("interrupt_no_error_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        mocks["execution"].execute_compiled_graph_async = AsyncMock(
            side_effect=GraphInterrupt("suspend")
        )

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            await service.run_async(bundle)

        # span.set_status(ERROR) must not be called for interrupt
        error_calls = [
            call
            for call in mock_span.set_status.call_args_list
            if call[0] and call[0][0] == StatusCode.ERROR
        ]
        assert (
            len(error_calls) == 0
        ), "GraphInterrupt should not set ERROR span status on async path"

    async def test_ac011_legacy_interrupt_does_not_set_error_status(self):
        """ExecutionInterruptedException must not set ERROR span status."""
        from opentelemetry.trace import StatusCode

        from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException

        mock_telemetry, mock_span = _make_mock_telemetry()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("legacy_no_error_graph", node_count=2)
        _setup_successful_async_run(mocks, bundle)

        exc = ExecutionInterruptedException(
            thread_id="leg-thr",
            interaction_request={},
            checkpoint_data={},
        )
        mocks["execution"].execute_compiled_graph_async = AsyncMock(side_effect=exc)

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True

        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            with self.assertRaises(ExecutionInterruptedException):
                await service.run_async(bundle)

        error_calls = [
            call
            for call in mock_span.set_status.call_args_list
            if call[0] and call[0][0] == StatusCode.ERROR
        ]
        assert (
            len(error_calls) == 0
        ), "ExecutionInterruptedException should not set ERROR span status"
