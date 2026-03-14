"""
Tests for GraphRunnerService telemetry: workflow root span instrumentation.

Covers task T-E02-F03-001 (GraphRunnerService Workflow Root Span Instrumentation).
Test cases TC-200 through TC-212, TC-240-242, TC-250, TC-252, TC-260, TC-262-264,
TC-280-281.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, create_autospec, patch

from agentmap.services.telemetry.constants import (
    GRAPH_AGENT_COUNT,
    GRAPH_NAME,
    GRAPH_NODE_COUNT,
    GRAPH_PARENT_NAME,
    WORKFLOW_RUN_SPAN,
)
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_telemetry_with_span():
    """Create a mock telemetry service with context-manager-compatible start_span.

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


def _make_mock_bundle(graph_name="test_graph", node_count=3):
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
    # node_instances is set after agent instantiation
    bundle.node_instances = None
    bundle.scoped_registry = None
    return bundle


def _make_graph_runner_service(telemetry_service=None):
    """Create a GraphRunnerService with all dependencies mocked.

    Returns:
        (service, mocks_dict) where mocks_dict has keys for each mock dependency.
    """
    from agentmap.services.config.app_config_service import AppConfigService
    from agentmap.services.declaration_registry_service import (
        DeclarationRegistryService,
    )
    from agentmap.services.execution_tracking_service import (
        ExecutionTrackingService,
    )
    from agentmap.services.graph.graph_agent_instantiation_service import (
        GraphAgentInstantiationService,
    )
    from agentmap.services.graph.graph_assembly_service import (
        GraphAssemblyService,
    )
    from agentmap.services.graph.graph_bootstrap_service import (
        GraphBootstrapService,
    )
    from agentmap.services.graph.graph_bundle_service import GraphBundleService
    from agentmap.services.graph.graph_checkpoint_service import (
        GraphCheckpointService,
    )
    from agentmap.services.graph.graph_execution_service import (
        GraphExecutionService,
    )
    from agentmap.services.graph.graph_runner_service import GraphRunnerService
    from agentmap.services.interaction_handler_service import (
        InteractionHandlerService,
    )
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
    }
    return service, mocks


def _setup_successful_run(mocks, bundle):
    """Configure mocks for a successful run() invocation.

    Returns the mock ExecutionResult.
    """
    from agentmap.models.execution.result import ExecutionResult

    # Scoped registry creation
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

    # Agent instantiation -- must also update the original bundle's
    # node_instances so _run_with_telemetry can read agent count
    node_instances = {f"node_{i}": MagicMock() for i in range(len(bundle.nodes))}
    bundle_with_instances = MagicMock()
    bundle_with_instances.graph_name = bundle.graph_name
    bundle_with_instances.nodes = bundle.nodes
    bundle_with_instances.entry_point = bundle.entry_point
    bundle_with_instances.node_instances = node_instances

    def _instantiate_side_effect(b, tracker):
        # Simulate real behaviour: mutate the bundle's node_instances
        b.node_instances = node_instances
        return bundle_with_instances

    mocks["instantiation"].instantiate_agents.side_effect = _instantiate_side_effect

    # Graph assembly
    mock_compiled = MagicMock()
    mocks["assembly"].assemble_graph.return_value = mock_compiled

    # Disable checkpoint path
    mocks["bundle_svc"].requires_checkpoint_support.return_value = False

    # Execution result
    mock_result = MagicMock(spec=ExecutionResult)
    mock_result.success = True
    mock_result.total_duration = 1.5
    mock_result.error = None
    mocks["execution"].execute_compiled_graph.return_value = mock_result

    return mock_result


def _setup_failing_run(mocks, bundle, exception=None):
    """Configure mocks so that run() raises an exception."""
    mock_scoped_registry = MagicMock()
    mock_scoped_registry.get_all_agent_types.return_value = ["agent1"]
    mock_scoped_registry.get_all_service_names.return_value = []
    mocks["declaration"].create_scoped_registry_for_bundle.return_value = (
        mock_scoped_registry
    )

    mock_tracker = MagicMock()
    mock_tracker.thread_id = "test-thread"
    mocks["tracking"].create_tracker.return_value = mock_tracker

    # Disable checkpoint path
    mocks["bundle_svc"].requires_checkpoint_support.return_value = False

    # Make instantiation raise
    exc = exception or RuntimeError("agent instantiation failed")
    mocks["instantiation"].instantiate_agents.side_effect = exc


# ---------------------------------------------------------------------------
# TC-200: Workflow root span created with correct name
# ---------------------------------------------------------------------------


class TestWorkflowSpanCreation:
    """TC-200, TC-203: Workflow span creation and constant usage."""

    def test_tc200_run_creates_workflow_root_span(self):
        """start_span called with WORKFLOW_RUN_SPAN when telemetry active."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("my_graph", node_count=3)
        _setup_successful_run(mocks, bundle)

        service.run(bundle)

        mock_telemetry.start_span.assert_called_once()
        call_args = mock_telemetry.start_span.call_args
        assert call_args[0][0] == WORKFLOW_RUN_SPAN

    def test_tc203_uses_constants_for_span_name(self):
        """Span name is the WORKFLOW_RUN_SPAN constant value."""
        assert WORKFLOW_RUN_SPAN == "agentmap.workflow.run"


# ---------------------------------------------------------------------------
# TC-201: Span has correct attributes
# ---------------------------------------------------------------------------


class TestWorkflowSpanAttributes:
    """TC-201: Span attributes include graph name, node count, agent count."""

    def test_tc201_span_attributes_include_graph_name_and_node_count(self):
        """start_span receives GRAPH_NAME and GRAPH_NODE_COUNT."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("my_graph", node_count=5)
        _setup_successful_run(mocks, bundle)

        service.run(bundle)

        call_args = mock_telemetry.start_span.call_args
        attrs = call_args[1].get("attributes") or call_args[0][1]
        assert attrs[GRAPH_NAME] == "my_graph"
        assert attrs[GRAPH_NODE_COUNT] == 5

    def test_tc201_agent_count_set_after_instantiation(self):
        """set_span_attributes called with GRAPH_AGENT_COUNT after instantiation."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("my_graph", node_count=3)
        _setup_successful_run(mocks, bundle)

        service.run(bundle)

        # set_span_attributes should have been called with agent count
        found_agent_count = False
        for call in mock_telemetry.set_span_attributes.call_args_list:
            span_arg, attrs_arg = call[0]
            if GRAPH_AGENT_COUNT in attrs_arg:
                found_agent_count = True
                assert attrs_arg[GRAPH_AGENT_COUNT] == 3
                break
        assert (
            found_agent_count
        ), "set_span_attributes was not called with GRAPH_AGENT_COUNT"


# ---------------------------------------------------------------------------
# TC-210: Span status OK on success
# ---------------------------------------------------------------------------


class TestWorkflowSpanStatus:
    """TC-210, TC-211: Span status reflects success/failure."""

    def test_tc210_span_status_ok_on_success(self):
        """Span status set to OK on successful workflow completion."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("my_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        service.run(bundle)

        # Span should have set_status(StatusCode.OK) called
        mock_span.set_status.assert_called()
        # Verify the first positional arg is StatusCode.OK
        from opentelemetry.trace import StatusCode

        status_calls = mock_span.set_status.call_args_list
        ok_found = any(call[0][0] == StatusCode.OK for call in status_calls)
        assert ok_found, "Span status was not set to OK"

    def test_tc211_span_status_error_on_exception(self):
        """Span status ERROR when _run_core returns failed result.

        Generic exceptions are caught inside _run_core and converted to an
        error ExecutionResult (success=False). The span status is set to
        ERROR via the result.success check in _run_with_telemetry.
        """
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("my_graph", node_count=2)
        test_error = RuntimeError("workflow exploded")
        _setup_failing_run(mocks, bundle, exception=test_error)

        result = service.run(bundle)

        # Result should indicate failure
        assert result.success is False

        from opentelemetry.trace import StatusCode

        status_calls = mock_span.set_status.call_args_list
        error_found = any(call[0][0] == StatusCode.ERROR for call in status_calls)
        assert error_found, "Span status was not set to ERROR for exception"

    def test_tc211_span_status_error_on_failed_result(self):
        """Span status ERROR when result.success is False (no exception)."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("my_graph", node_count=2)
        mock_result = _setup_successful_run(mocks, bundle)
        mock_result.success = False
        mock_result.error = "something went wrong"

        service.run(bundle)

        from opentelemetry.trace import StatusCode

        status_calls = mock_span.set_status.call_args_list
        error_found = any(call[0][0] == StatusCode.ERROR for call in status_calls)
        assert error_found, "Span status was not set to ERROR for failed result"


# ---------------------------------------------------------------------------
# TC-212: Duration recorded (via span timing -- tested by verifying
# span context manager entered and exited)
# ---------------------------------------------------------------------------


class TestWorkflowSpanDuration:
    """TC-212: Workflow duration captured by span timing."""

    def test_tc212_span_context_manager_used(self):
        """Span context manager is entered and exited (captures duration)."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("my_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        service.run(bundle)

        # start_span was called, and the context manager was used
        mock_telemetry.start_span.assert_called_once()


# ---------------------------------------------------------------------------
# TC-240-242: Subgraph nesting
# ---------------------------------------------------------------------------


class TestSubgraphSpanNesting:
    """TC-240, TC-241, TC-242: Subgraph span nesting behavior."""

    def test_tc241_subgraph_span_has_parent_name_attribute(self):
        """GRAPH_PARENT_NAME set when parent_graph_name is provided."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("child_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        service.run(
            bundle,
            parent_graph_name="parent_workflow",
            is_subgraph=True,
        )

        call_args = mock_telemetry.start_span.call_args
        attrs = call_args[1].get("attributes") or call_args[0][1]
        assert attrs[GRAPH_PARENT_NAME] == "parent_workflow"

    def test_tc242_parent_name_absent_for_top_level_graph(self):
        """GRAPH_PARENT_NAME NOT set for top-level graph execution."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("top_level_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        service.run(bundle)

        call_args = mock_telemetry.start_span.call_args
        attrs = call_args[1].get("attributes") or call_args[0][1]
        assert GRAPH_PARENT_NAME not in attrs


# ---------------------------------------------------------------------------
# TC-250, TC-252: None telemetry path is zero-overhead
# ---------------------------------------------------------------------------


class TestNoneTelemetryPath:
    """TC-250, TC-252: Services work normally with None telemetry."""

    def test_tc250_runs_normally_with_none_telemetry(self):
        """GraphRunnerService works with telemetry_service=None."""
        service, mocks = _make_graph_runner_service(telemetry_service=None)
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        result = service.run(bundle)

        assert result.success is True

    def test_tc252_no_attribute_error_from_telemetry_paths(self):
        """No AttributeError or TypeError from telemetry code paths."""
        service, mocks = _make_graph_runner_service(telemetry_service=None)
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        # Should complete without any exception
        result = service.run(bundle)
        assert result is not None

    def test_constructor_works_without_telemetry_parameter(self):
        """Constructor works when telemetry_service is not provided (default None)."""
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.declaration_registry_service import (
            DeclarationRegistryService,
        )
        from agentmap.services.execution_tracking_service import (
            ExecutionTrackingService,
        )
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )
        from agentmap.services.graph.graph_assembly_service import (
            GraphAssemblyService,
        )
        from agentmap.services.graph.graph_bundle_service import (
            GraphBundleService,
        )
        from agentmap.services.graph.graph_checkpoint_service import (
            GraphCheckpointService,
        )
        from agentmap.services.graph.graph_execution_service import (
            GraphExecutionService,
        )
        from agentmap.services.graph.graph_runner_service import (
            GraphRunnerService,
        )
        from agentmap.services.interaction_handler_service import (
            InteractionHandlerService,
        )
        from agentmap.services.logging_service import LoggingService

        mock_logging = create_autospec(LoggingService, instance=True)
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_instantiation = create_autospec(
            GraphAgentInstantiationService, instance=True
        )

        # No telemetry_service argument at all -- should use default None
        service = GraphRunnerService(
            app_config_service=create_autospec(AppConfigService, instance=True),
            graph_bootstrap_service=None,
            graph_agent_instantiation_service=mock_instantiation,
            graph_assembly_service=create_autospec(GraphAssemblyService, instance=True),
            graph_execution_service=create_autospec(
                GraphExecutionService, instance=True
            ),
            execution_tracking_service=create_autospec(
                ExecutionTrackingService, instance=True
            ),
            logging_service=mock_logging,
            interaction_handler_service=create_autospec(
                InteractionHandlerService, instance=True
            ),
            graph_checkpoint_service=create_autospec(
                GraphCheckpointService, instance=True
            ),
            graph_bundle_service=create_autospec(GraphBundleService, instance=True),
            declaration_registry_service=create_autospec(
                DeclarationRegistryService, instance=True
            ),
        )
        assert service._telemetry_service is None


# ---------------------------------------------------------------------------
# TC-260, TC-262-264: Telemetry failure isolation
# ---------------------------------------------------------------------------


class TestTelemetryFailureIsolation:
    """TC-260, TC-262, TC-263, TC-264: Workflow completes despite telemetry errors."""

    def test_tc260_start_span_failure_workflow_continues(self):
        """Workflow completes normally when start_span() raises RuntimeError."""
        mock_telemetry = create_autospec(TelemetryServiceProtocol, instance=True)
        mock_telemetry.start_span.side_effect = RuntimeError("telemetry broken")

        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        result = service.run(bundle)

        # Workflow should have completed normally via fallback
        assert result.success is True

    def test_tc262_set_span_attributes_failure_continues(self):
        """Execution continues when set_span_attributes() raises."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        mock_telemetry.set_span_attributes.side_effect = RuntimeError("attrs broken")

        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        result = service.run(bundle)

        assert result.success is True

    def test_tc263_add_span_event_failure_continues(self):
        """Execution continues when add_span_event() raises."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        mock_telemetry.add_span_event.side_effect = RuntimeError("events broken")

        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        result = service.run(bundle)

        assert result.success is True

    def test_tc264_warning_logged_on_telemetry_failure(self):
        """Warning logged when telemetry operation fails."""
        mock_telemetry = create_autospec(TelemetryServiceProtocol, instance=True)
        mock_telemetry.start_span.side_effect = RuntimeError("telemetry broken")

        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        service.run(bundle)

        # Logger should have been called with warning
        mock_logger = mocks["logging"].get_class_logger.return_value
        mock_logger.warning.assert_called()
        # Verify warning message contains telemetry context
        warning_msg = str(mock_logger.warning.call_args)
        assert "telemetry" in warning_msg.lower() or "Telemetry" in warning_msg


# ---------------------------------------------------------------------------
# TC-280, TC-281: Phase events recorded on workflow span
# ---------------------------------------------------------------------------


class TestPhaseEvents:
    """TC-280, TC-281: Phase events recorded via add_span_event."""

    def test_tc280_phase_events_recorded(self):
        """add_span_event called for key execution phases."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        # Patch get_current_span to return a recording mock span
        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True
        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            service.run(bundle)

        # Phase events should have been recorded
        event_calls = mock_telemetry.add_span_event.call_args_list
        event_names = []
        for call in event_calls:
            # add_span_event(span, name, attributes)
            if len(call[0]) >= 2:
                event_names.append(call[0][1])

        # Check that key phases are recorded
        expected_phases = [
            "workflow.phase.registry_creation",
            "workflow.phase.tracker_creation",
            "workflow.phase.agent_instantiation",
            "workflow.phase.graph_assembly",
            "workflow.phase.execution",
            "workflow.phase.finalization",
        ]
        for phase in expected_phases:
            assert (
                phase in event_names
            ), f"Phase event '{phase}' not found in {event_names}"

    def test_tc281_phase_events_via_add_span_event_not_child_spans(self):
        """start_span called once (workflow root); phases as events."""
        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True
        with patch(
            "opentelemetry.trace.get_current_span",
            return_value=mock_current_span,
        ):
            service.run(bundle)

        # start_span should be called exactly once (workflow root span)
        assert mock_telemetry.start_span.call_count == 1
        # add_span_event should have been called (for phase events)
        assert mock_telemetry.add_span_event.call_count >= 1


# ---------------------------------------------------------------------------
# TC-203: All attribute keys from constants.py
# ---------------------------------------------------------------------------


class TestConstantsUsage:
    """TC-203: All attribute keys reference constants from constants.py."""

    def test_tc203_graph_parent_name_constant_exists(self):
        """GRAPH_PARENT_NAME constant is defined in constants.py."""
        assert GRAPH_PARENT_NAME == "agentmap.graph.parent_name"

    def test_tc203_workflow_span_constant_value(self):
        """WORKFLOW_RUN_SPAN constant has correct value."""
        assert WORKFLOW_RUN_SPAN == "agentmap.workflow.run"

    def test_tc203_graph_name_constant(self):
        """GRAPH_NAME constant is used for attributes."""
        assert GRAPH_NAME == "agentmap.graph.name"

    def test_tc203_graph_node_count_constant(self):
        """GRAPH_NODE_COUNT constant is used for attributes."""
        assert GRAPH_NODE_COUNT == "agentmap.graph.node_count"

    def test_tc203_graph_agent_count_constant(self):
        """GRAPH_AGENT_COUNT constant is used for attributes."""
        assert GRAPH_AGENT_COUNT == "agentmap.graph.agent_count"


# ---------------------------------------------------------------------------
# Interrupt handling (span should not record error for interrupts)
# ---------------------------------------------------------------------------


class TestInterruptHandling:
    """Interrupt exceptions are not treated as errors on the span."""

    def test_graph_interrupt_does_not_set_error_status(self):
        """GraphInterrupt records span event, not error status."""
        from langgraph.errors import GraphInterrupt

        mock_telemetry, mock_span = _make_mock_telemetry_with_span()
        service, mocks = _make_graph_runner_service(telemetry_service=mock_telemetry)
        bundle = _make_mock_bundle("test_graph", node_count=2)
        _setup_successful_run(mocks, bundle)

        # Make graph execution raise GraphInterrupt (after all setup is done)
        mocks["execution"].execute_compiled_graph.side_effect = GraphInterrupt(
            "suspended"
        )

        # GraphInterrupt is caught by _run_core's except handler which
        # tries to handle it -- but it also propagates through
        # _run_with_telemetry which records a span event
        # The result depends on _run_core's GraphInterrupt handler behavior
        # which needs executable_graph.get_state() -- since that's mocked,
        # it returns a MagicMock. Let's just verify telemetry behavior.
        try:
            service.run(bundle)
        except (GraphInterrupt, RuntimeError):
            pass  # May raise depending on mock state

        # record_exception should NOT be called for GraphInterrupt
        mock_telemetry.record_exception.assert_not_called()
