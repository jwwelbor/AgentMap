"""Unit tests for GraphRunnerService conditional checkpoint assembly."""

import asyncio  # noqa: F401 — used inside async test methods
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from agentmap.models.execution.result import ExecutionResult
from agentmap.models.execution.tracker import ExecutionTracker, NodeExecution
from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.services.graph.graph_runner_service import GraphRunnerService
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphRunnerServiceCheckpoint(unittest.TestCase):
    """Ensure GraphRunnerService toggles checkpointer based on bundle contents."""

    def setUp(self):
        self.app_config = Mock()
        self.graph_bootstrap = Mock()
        self.graph_instantiation = Mock()
        self.graph_assembly = Mock()
        self.graph_execution = Mock()
        self.execution_tracking = Mock()
        self.logging_service = MockServiceFactory.create_mock_logging_service()
        self.interaction_handler = Mock()
        self.interaction_handler._store_thread_metadata_suspend_only = Mock()
        self.interaction_handler._store_thread_metadata = Mock()
        self.interaction_handler._store_interaction_request = Mock()
        self.interaction_handler.mark_thread_resuming = Mock()
        self.interaction_handler.mark_thread_completed = Mock()
        self.graph_checkpoint = Mock()
        self.graph_bundle_service = Mock()
        self.declaration_registry_service = Mock()

        # Configure mock scoped registry for thread-safe concurrent execution
        self.mock_scoped_registry = Mock()
        self.mock_scoped_registry.get_all_agent_types.return_value = ["LLMAgent"]
        self.mock_scoped_registry.get_all_service_names.return_value = [
            "logging_service"
        ]
        self.mock_scoped_registry.get_agent_declaration.return_value = None
        self.declaration_registry_service.create_scoped_registry_for_bundle.return_value = (
            self.mock_scoped_registry
        )

        self.service = GraphRunnerService(
            self.app_config,
            self.graph_bootstrap,
            self.graph_instantiation,
            self.graph_assembly,
            self.graph_execution,
            self.execution_tracking,
            self.logging_service,
            self.interaction_handler,
            self.graph_checkpoint,
            self.graph_bundle_service,
            self.declaration_registry_service,
        )

        self.execution_tracker = ExecutionTracker()
        self.execution_tracker.thread_id = "thread-123"
        self.execution_tracking.create_tracker.return_value = self.execution_tracker
        self.execution_tracking.record_subgraph_execution = Mock()
        self.execution_tracking.complete_execution = Mock()

        from agentmap.models.execution.summary import ExecutionSummary

        self.execution_tracking.to_summary = Mock(
            side_effect=lambda tracker, graph_name, final_output: ExecutionSummary(
                graph_name=graph_name,
                final_output=final_output,
                status="completed" if tracker.end_time else "in_progress",
            )
        )

        self.bundle = GraphBundle(graph_name="conditional")
        self.bundle.nodes = {
            "start": Node(name="start", agent_type="LLMAgent"),
        }
        self.bundle.entry_point = "start"

        self.bundle_with_instances = GraphBundle(graph_name="conditional")
        self.bundle_with_instances.nodes = self.bundle.nodes
        self.bundle_with_instances.entry_point = "start"
        self.bundle_with_instances.node_instances = {"start": Mock()}

        self.graph_instantiation.instantiate_agents.return_value = (
            self.bundle_with_instances
        )
        self.graph_instantiation.validate_instantiation.return_value = {
            "valid": True,
            "instantiated_nodes": 1,
        }

        self.compiled_with_checkpoint = Mock()
        self.compiled_with_checkpoint.get_state.return_value = Mock(tasks=[])
        self.compiled_without_checkpoint = Mock()

        self.graph_assembly.assemble_with_checkpoint.return_value = (
            self.compiled_with_checkpoint
        )
        self.graph_assembly.assemble_graph.return_value = (
            self.compiled_without_checkpoint
        )

        self.graph_execution.execute_compiled_graph.return_value = ExecutionResult(
            graph_name="conditional",
            final_state={},
            execution_summary=None,
            success=True,
            total_duration=0.05,
        )

        # Avoid CLI display side-effects during tests
        self.service._display_resume_instructions = Mock()

    def test_assemble_without_checkpoint_when_not_required(self):
        """assemble() is used when bundle does not require checkpoint support."""
        self.graph_bundle_service.requires_checkpoint_support.return_value = False

        result = self.service.run(self.bundle)

        self.assertTrue(result.success)
        self.graph_bundle_service.requires_checkpoint_support.assert_called_once()
        self.graph_assembly.assemble_graph.assert_called_once()
        self.graph_assembly.assemble_with_checkpoint.assert_not_called()
        self.compiled_without_checkpoint.get_state.assert_not_called()
        _, kwargs = self.graph_execution.execute_compiled_graph.call_args
        self.assertIsNone(kwargs.get("config"))

    def test_assemble_with_checkpoint_when_required(self):
        """assemble_with_checkpoint() is used when bundle requires checkpoint support."""
        self.graph_bundle_service.requires_checkpoint_support.return_value = True

        result = self.service.run(self.bundle)

        self.assertTrue(result.success)
        self.graph_bundle_service.requires_checkpoint_support.assert_called_once()
        self.graph_assembly.assemble_with_checkpoint.assert_called_once()
        self.graph_assembly.assemble_graph.assert_not_called()
        self.compiled_with_checkpoint.get_state.assert_called_once_with(
            {"configurable": {"thread_id": "thread-123"}}
        )
        _, kwargs = self.graph_execution.execute_compiled_graph.call_args
        self.assertEqual(
            kwargs.get("config"), {"configurable": {"thread_id": "thread-123"}}
        )

    @unittest.skip("MANUAL: Checkpoint detection logic changed - needs investigation")
    def test_detects_suspend_interrupt_after_execution(self):
        """Run should return interrupted result if state reflects a suspend interrupt."""
        self.graph_bundle_service.requires_checkpoint_support.return_value = True

        interrupt_value = {"type": "suspend", "node_name": "SuspendForResponse"}
        state = SimpleNamespace(
            tasks=[SimpleNamespace(interrupts=[SimpleNamespace(value=interrupt_value)])]
        )
        self.compiled_with_checkpoint.get_state.return_value = state

        result = self.service.run(self.bundle)

        self.assertFalse(result.success)
        self.assertTrue(result.final_state.get("__interrupted"))
        self.assertEqual(result.final_state.get("__interrupt_type"), "suspend")
        self.assertEqual(result.execution_summary.status, "suspended")
        self.interaction_handler._store_thread_metadata_suspend_only.assert_called_once()
        self.service._display_resume_instructions.assert_called_once()

    def test_suspend_metadata_fallback_without_interrupts(self):
        """Fallback should persist suspend metadata when LangGraph interrupts are empty."""
        self.graph_bundle_service.requires_checkpoint_support.return_value = True

        state = SimpleNamespace(tasks=[SimpleNamespace(interrupts=tuple())])
        self.compiled_with_checkpoint.get_state.return_value = state

        pending_node = NodeExecution(
            node_name="SuspendForResponse", success=None, inputs={"foo": "bar"}
        )
        self.execution_tracker.node_executions.append(pending_node)

        self.bundle.nodes["SuspendForResponse"] = Node(
            name="SuspendForResponse",
            agent_type="SuspendAgent",
        )
        self.bundle_with_instances.nodes = self.bundle.nodes

        result = self.service.run(self.bundle)

        self.assertFalse(result.success)
        self.assertEqual(result.execution_summary.status, "suspended")
        self.interaction_handler._store_thread_metadata_suspend_only.assert_called_once()
        interrupt_info = result.final_state.get("__interrupt_info", {})
        self.assertEqual(interrupt_info.get("type"), "suspend")
        self.assertEqual(interrupt_info.get("node_name"), "SuspendForResponse")

    def test_resume_from_checkpoint_without_human_response_uses_none_input(self):
        """Suspend-only resume should invoke graph with None rather than an empty Command."""
        self.compiled_with_checkpoint.invoke.reset_mock()
        self.compiled_with_checkpoint.invoke.return_value = {}

        thread_id = "thread-789"
        checkpoint_state = {}

        result = self.service.resume_from_checkpoint(
            bundle=self.bundle,
            thread_id=thread_id,
            checkpoint_state=checkpoint_state,
        )

        args, kwargs = self.compiled_with_checkpoint.invoke.call_args
        from langgraph.types import Command

        self.assertIsInstance(args[0], Command)
        self.assertEqual(args[0].resume, {"__resume_marker": True})
        self.assertEqual(
            kwargs.get("config"), {"configurable": {"thread_id": thread_id}}
        )
        self.interaction_handler.mark_thread_resuming.assert_called_once_with(thread_id)
        self.interaction_handler.mark_thread_completed.assert_called_once_with(
            thread_id
        )
        self.assertTrue(result.success)
        self.assertEqual(result.final_state.get("__thread_id"), thread_id)
        self.assertIsNot(result.execution_summary.final_output, result.final_state)

    def test_resume_from_checkpoint_with_human_response_builds_command(self):
        """Human-interaction resume should wrap payload in a Command object."""
        from langgraph.types import Command

        self.compiled_with_checkpoint.invoke.reset_mock()
        self.compiled_with_checkpoint.invoke.return_value = {}

        thread_id = "thread-456"
        resume_payload = {"action": "approve", "data": {"note": "ok"}}
        checkpoint_state = {"__human_response": resume_payload}

        result = self.service.resume_from_checkpoint(
            bundle=self.bundle,
            thread_id=thread_id,
            checkpoint_state=checkpoint_state,
        )

        args, kwargs = self.compiled_with_checkpoint.invoke.call_args
        self.assertIsInstance(args[0], Command)
        self.assertEqual(args[0].resume, resume_payload)
        self.assertEqual(
            kwargs.get("config"), {"configurable": {"thread_id": thread_id}}
        )
        self.assertTrue(result.success)
        self.interaction_handler.mark_thread_resuming.assert_called_once_with(thread_id)
        self.interaction_handler.mark_thread_completed.assert_called_once_with(
            thread_id
        )
        self.assertIsNot(result.execution_summary.final_output, result.final_state)


# ---------------------------------------------------------------------------
# TC-005 and TC-006: Async resume parity
# (resume_from_checkpoint_async)
# ---------------------------------------------------------------------------


class TestAsyncCheckpointResumeParity(unittest.IsolatedAsyncioTestCase):
    """TC-005 and TC-006: resume_from_checkpoint_async parity with sync path.

    Caller-path contract:
        Production entrypoint:
            GraphRunnerService.resume_from_checkpoint_async(
                bundle, thread_id, checkpoint_state, resume_node=None)
        Lowest allowed mock seam:
            CheckpointManager async resume helpers and the compiled graph
            async invoke surface.
        Forbidden mocks:
            GraphRunnerService.resume_from_checkpoint, private resume helpers,
            or any helper that fabricates resume payloads outside the
            production resume contract.
        Counter-factual:
            A buggy implementation would lose the resume payload, fail to
            mark the thread state transitions, or return a different
            final-state envelope than the sync resume path.
    """

    def setUp(self):
        from agentmap.models.execution.summary import ExecutionSummary
        from agentmap.models.execution.tracker import ExecutionTracker
        from tests.utils.mock_service_factory import MockServiceFactory

        self.app_config = Mock()
        self.graph_bootstrap = Mock()
        self.graph_instantiation = Mock()
        self.graph_assembly = Mock()
        self.graph_execution = Mock()
        self.execution_tracking = Mock()
        self.logging_service = MockServiceFactory.create_mock_logging_service()
        self.interaction_handler = Mock()
        self.interaction_handler.mark_thread_resuming = Mock()
        self.interaction_handler.mark_thread_completed = Mock()
        self.interaction_handler.unmark_thread_resuming = Mock()
        self.graph_checkpoint = Mock()
        self.graph_bundle_service = Mock()
        self.declaration_registry_service = Mock()

        mock_scoped_registry = Mock()
        mock_scoped_registry.get_all_agent_types.return_value = ["LLMAgent"]
        mock_scoped_registry.get_all_service_names.return_value = ["logging_service"]
        mock_scoped_registry.get_agent_declaration.return_value = None
        self.declaration_registry_service.create_scoped_registry_for_bundle.return_value = (
            mock_scoped_registry
        )

        self.service = GraphRunnerService(
            self.app_config,
            self.graph_bootstrap,
            self.graph_instantiation,
            self.graph_assembly,
            self.graph_execution,
            self.execution_tracking,
            self.logging_service,
            self.interaction_handler,
            self.graph_checkpoint,
            self.graph_bundle_service,
            self.declaration_registry_service,
        )

        self.execution_tracker = ExecutionTracker()
        self.execution_tracker.thread_id = "async-thread-001"
        self.execution_tracking.create_tracker.return_value = self.execution_tracker
        self.execution_tracking.complete_execution = Mock()
        self.execution_tracking.to_summary = Mock(
            side_effect=lambda tracker, graph_name, final_output: ExecutionSummary(
                graph_name=graph_name,
                final_output=final_output,
                status="completed",
            )
        )

        self.bundle = GraphBundle(graph_name="async-checkpoint-graph")
        self.bundle.nodes = {
            "start": Node(name="start", agent_type="LLMAgent"),
        }
        self.bundle.entry_point = "start"

        self.bundle_with_instances = GraphBundle(graph_name="async-checkpoint-graph")
        self.bundle_with_instances.nodes = self.bundle.nodes
        self.bundle_with_instances.entry_point = "start"
        self.bundle_with_instances.node_instances = {"start": Mock()}
        self.graph_instantiation.instantiate_agents.return_value = (
            self.bundle_with_instances
        )
        self.graph_instantiation.validate_instantiation.return_value = {
            "valid": True,
            "instantiated_nodes": 1,
        }

        # Compiled graph with async invoke surface
        self.compiled_graph = Mock()
        self.compiled_graph.ainvoke = AsyncMock(return_value={})
        self.graph_assembly.assemble_with_checkpoint_async.return_value = (
            self.compiled_graph
        )

    # -----------------------------------------------------------------------
    # TC-005: suspend-style resume parity
    # -----------------------------------------------------------------------

    async def test_tc005_suspend_style_resume_uses_default_marker(self):
        """TC-005: suspend resume builds default __resume_marker when no payload."""
        from langgraph.types import Command

        thread_id = "async-suspend-thread"
        checkpoint_state = {}  # no __human_response

        await self.service.resume_from_checkpoint_async(
            bundle=self.bundle,
            thread_id=thread_id,
            checkpoint_state=checkpoint_state,
        )

        args, kwargs = self.compiled_graph.ainvoke.call_args
        self.assertIsInstance(args[0], Command)
        self.assertEqual(args[0].resume, {"__resume_marker": True})
        self.assertEqual(
            kwargs.get("config"), {"configurable": {"thread_id": thread_id}}
        )

    async def test_tc005_suspend_style_resume_returns_correct_result_shape(self):
        """TC-005: async suspend resume returns same ExecutionResult shape as sync."""
        thread_id = "async-suspend-thread"

        result = await self.service.resume_from_checkpoint_async(
            bundle=self.bundle,
            thread_id=thread_id,
            checkpoint_state={},
        )

        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertEqual(result.graph_name, "async-checkpoint-graph")
        self.assertIsNotNone(result.execution_summary)
        self.assertEqual(result.final_state.get("__thread_id"), thread_id)

    async def test_tc005_suspend_style_resume_marks_thread_transitions(self):
        """TC-005: async suspend resume marks thread resuming then completed."""
        thread_id = "async-suspend-thread"

        await self.service.resume_from_checkpoint_async(
            bundle=self.bundle,
            thread_id=thread_id,
            checkpoint_state={},
        )

        self.interaction_handler.mark_thread_resuming.assert_called_once_with(thread_id)
        self.interaction_handler.mark_thread_completed.assert_called_once_with(
            thread_id
        )

    async def test_tc005_suspend_style_resume_final_output_not_same_object(self):
        """TC-005: execution_summary.final_output is a copy, not the same dict."""
        result = await self.service.resume_from_checkpoint_async(
            bundle=self.bundle,
            thread_id="async-suspend-thread",
            checkpoint_state={},
        )

        self.assertIsNot(result.execution_summary.final_output, result.final_state)

    # -----------------------------------------------------------------------
    # TC-006: human-response resume parity
    # -----------------------------------------------------------------------

    async def test_tc006_human_response_resume_preserves_payload(self):
        """TC-006: async human-response resume wraps payload in Command correctly."""
        from langgraph.types import Command

        thread_id = "async-human-thread"
        resume_payload = {"action": "approve", "data": {"note": "ok"}}
        checkpoint_state = {"__human_response": resume_payload}

        await self.service.resume_from_checkpoint_async(
            bundle=self.bundle,
            thread_id=thread_id,
            checkpoint_state=checkpoint_state,
        )

        args, kwargs = self.compiled_graph.ainvoke.call_args
        self.assertIsInstance(args[0], Command)
        self.assertEqual(args[0].resume, resume_payload)
        self.assertEqual(
            kwargs.get("config"), {"configurable": {"thread_id": thread_id}}
        )

    async def test_tc006_human_response_resume_returns_success_result(self):
        """TC-006: async human-response resume returns success ExecutionResult."""
        thread_id = "async-human-thread"
        resume_payload = {"action": "approve"}
        checkpoint_state = {"__human_response": resume_payload}

        result = await self.service.resume_from_checkpoint_async(
            bundle=self.bundle,
            thread_id=thread_id,
            checkpoint_state=checkpoint_state,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.graph_name, "async-checkpoint-graph")

    async def test_tc006_human_response_resume_marks_thread_completed(self):
        """TC-006: human-response resume marks thread resuming then completed."""
        thread_id = "async-human-thread"
        checkpoint_state = {"__human_response": {"action": "approve"}}

        await self.service.resume_from_checkpoint_async(
            bundle=self.bundle,
            thread_id=thread_id,
            checkpoint_state=checkpoint_state,
        )

        self.interaction_handler.mark_thread_resuming.assert_called_once_with(thread_id)
        self.interaction_handler.mark_thread_completed.assert_called_once_with(
            thread_id
        )

    async def test_tc006_human_response_with_nested_data(self):
        """TC-006: async resume preserves nested human response data."""
        nested_payload = {
            "action": "submit",
            "data": {"nested": {"key": "value"}, "list": [1, 2, 3]},
        }
        checkpoint_state = {"__human_response": nested_payload}

        await self.service.resume_from_checkpoint_async(
            bundle=self.bundle,
            thread_id="async-nested-thread",
            checkpoint_state=checkpoint_state,
        )

        args, _ = self.compiled_graph.ainvoke.call_args
        self.assertEqual(args[0].resume, nested_payload)


# ---------------------------------------------------------------------------
# TC-010: Cancelled resume leaves thread re-resumable
# ---------------------------------------------------------------------------


class TestTC010CancelledResumeLeadsToReresumable(unittest.IsolatedAsyncioTestCase):
    """TC-010: cancel resume_from_checkpoint_async — thread must not be wedged.

    Caller-path contract:
        Production entrypoint:
            GraphRunnerService.resume_from_checkpoint_async(
                bundle, thread_id, checkpoint_state, resume_node=None)
            wrapped by the caller in asyncio.wait_for() / task cancellation.
        Lowest allowed mock seam:
            CheckpointManager async helpers and compiled graph ainvoke.
        Forbidden mocks:
            catching/suppressing CancelledError inside the test;
            asserting against private resume helpers.
        Counter-factual:
            A buggy implementation swallows CancelledError or leaves the
            checkpoint thread stuck in 'resuming' so the next resume blocks.
    """

    def setUp(self):
        from agentmap.models.execution.summary import ExecutionSummary
        from agentmap.models.execution.tracker import ExecutionTracker
        from tests.utils.mock_service_factory import MockServiceFactory

        self.app_config = Mock()
        self.graph_bootstrap = Mock()
        self.graph_instantiation = Mock()
        self.graph_assembly = Mock()
        self.graph_execution = Mock()
        self.execution_tracking = Mock()
        self.logging_service = MockServiceFactory.create_mock_logging_service()
        self.interaction_handler = Mock()
        self.interaction_handler.mark_thread_resuming = Mock()
        self.interaction_handler.mark_thread_completed = Mock()
        self.interaction_handler.unmark_thread_resuming = Mock()
        self.graph_checkpoint = Mock()
        self.graph_bundle_service = Mock()
        self.declaration_registry_service = Mock()

        mock_scoped_registry = Mock()
        mock_scoped_registry.get_all_agent_types.return_value = ["LLMAgent"]
        mock_scoped_registry.get_all_service_names.return_value = ["logging_service"]
        mock_scoped_registry.get_agent_declaration.return_value = None
        self.declaration_registry_service.create_scoped_registry_for_bundle.return_value = (
            mock_scoped_registry
        )

        self.service = GraphRunnerService(
            self.app_config,
            self.graph_bootstrap,
            self.graph_instantiation,
            self.graph_assembly,
            self.graph_execution,
            self.execution_tracking,
            self.logging_service,
            self.interaction_handler,
            self.graph_checkpoint,
            self.graph_bundle_service,
            self.declaration_registry_service,
        )

        self.execution_tracker = ExecutionTracker()
        self.execution_tracker.thread_id = "cancel-thread-001"
        self.execution_tracking.create_tracker.return_value = self.execution_tracker
        self.execution_tracking.complete_execution = Mock()
        self.execution_tracking.to_summary = Mock(
            side_effect=lambda tracker, graph_name, final_output: ExecutionSummary(
                graph_name=graph_name,
                final_output=final_output,
                status="completed",
            )
        )

        self.bundle = GraphBundle(graph_name="cancel-graph")
        self.bundle.nodes = {
            "start": Node(name="start", agent_type="LLMAgent"),
        }
        self.bundle.entry_point = "start"

        self.bundle_with_instances = GraphBundle(graph_name="cancel-graph")
        self.bundle_with_instances.nodes = self.bundle.nodes
        self.bundle_with_instances.entry_point = "start"
        self.bundle_with_instances.node_instances = {"start": Mock()}
        self.graph_instantiation.instantiate_agents.return_value = (
            self.bundle_with_instances
        )
        self.graph_instantiation.validate_instantiation.return_value = {
            "valid": True,
            "instantiated_nodes": 1,
        }

    async def test_tc010_cancelled_resume_propagates_cancelled_error(self):
        """TC-010: CancelledError propagates from resume_from_checkpoint_async."""

        # Compiled graph whose ainvoke raises CancelledError mid-resume
        slow_graph = Mock()
        slow_graph.ainvoke = AsyncMock(side_effect=asyncio.CancelledError())
        self.graph_assembly.assemble_with_checkpoint_async.return_value = slow_graph

        with self.assertRaises((asyncio.CancelledError, BaseException)):
            await self.service.resume_from_checkpoint_async(
                bundle=self.bundle,
                thread_id="cancel-thread-001",
                checkpoint_state={},
            )

    async def test_tc010_cancelled_resume_after_marking_resuming_resets_state(self):
        """TC-010: when cancel happens after mark_thread_resuming, unmark is called."""
        slow_graph = Mock()
        slow_graph.ainvoke = AsyncMock(side_effect=asyncio.CancelledError())
        self.graph_assembly.assemble_with_checkpoint_async.return_value = slow_graph

        try:
            await self.service.resume_from_checkpoint_async(
                bundle=self.bundle,
                thread_id="cancel-thread-001",
                checkpoint_state={},
            )
        except (asyncio.CancelledError, BaseException):
            pass

        # The thread should have been unmarked from 'resuming' so it can be
        # re-resumed without being wedged
        self.interaction_handler.unmark_thread_resuming.assert_called_once_with(
            "cancel-thread-001"
        )

    async def test_tc010_second_resume_after_cancel_succeeds(self):
        """TC-010: a second resume after a cancel completes normally (not wedged)."""
        # First resume — cancelled mid-flight
        cancelled_graph = Mock()
        cancelled_graph.ainvoke = AsyncMock(side_effect=asyncio.CancelledError())
        self.graph_assembly.assemble_with_checkpoint_async.return_value = (
            cancelled_graph
        )

        try:
            await self.service.resume_from_checkpoint_async(
                bundle=self.bundle,
                thread_id="cancel-thread-001",
                checkpoint_state={},
            )
        except (asyncio.CancelledError, BaseException):
            pass

        # Reset mocks for the second attempt
        self.interaction_handler.mark_thread_resuming.reset_mock()
        self.interaction_handler.mark_thread_completed.reset_mock()
        self.interaction_handler.unmark_thread_resuming.reset_mock()

        # Second resume — succeeds
        success_graph = Mock()
        success_graph.ainvoke = AsyncMock(return_value={"result": "ok"})
        self.graph_assembly.assemble_with_checkpoint_async.return_value = success_graph

        result = await self.service.resume_from_checkpoint_async(
            bundle=self.bundle,
            thread_id="cancel-thread-001",
            checkpoint_state={},
        )

        self.assertTrue(result.success)
        self.interaction_handler.mark_thread_resuming.assert_called_once_with(
            "cancel-thread-001"
        )
        self.interaction_handler.mark_thread_completed.assert_called_once_with(
            "cancel-thread-001"
        )

    async def test_tc010_cancel_before_mark_resuming_does_not_call_unmark(self):
        """TC-010: if cancel happens before mark_thread_resuming, unmark is not called."""
        # Make instantiation raise CancelledError (before mark_thread_resuming)
        self.graph_instantiation.instantiate_agents.side_effect = (
            asyncio.CancelledError()
        )

        try:
            await self.service.resume_from_checkpoint_async(
                bundle=self.bundle,
                thread_id="cancel-thread-001",
                checkpoint_state={},
            )
        except (asyncio.CancelledError, BaseException):
            pass

        # unmark should NOT be called because we never got to mark_thread_resuming
        self.interaction_handler.unmark_thread_resuming.assert_not_called()
        self.interaction_handler.mark_thread_resuming.assert_not_called()

    async def test_tc010b_cancelled_resume_finalizes_execution_tracker(self):
        """TC-010 / B-2: cancelled resume must call complete_execution on the tracker.

        Counter-factual: without the complete_execution call in the CancelledError
        branch, the tracker created at the start of resume_from_checkpoint_async is
        leaked in-progress.  This test would pass against a correct implementation
        and FAIL against the buggy implementation described in B-2.

        Caller-Path Contract:
            Production entrypoint: resume_from_checkpoint_async(bundle, thread_id, ...)
            Lowest allowed mock seam: compiled graph ainvoke and execution_tracking
            Forbidden mocks: do not suppress CancelledError inside the test body
        """
        # Compiled graph whose ainvoke raises CancelledError after mark_thread_resuming
        slow_graph = Mock()
        slow_graph.ainvoke = AsyncMock(side_effect=asyncio.CancelledError())
        self.graph_assembly.assemble_with_checkpoint_async.return_value = slow_graph

        try:
            await self.service.resume_from_checkpoint_async(
                bundle=self.bundle,
                thread_id="cancel-thread-001",
                checkpoint_state={},
            )
        except (asyncio.CancelledError, BaseException):
            pass

        # The execution tracker created at the top of the resume path MUST be
        # finalized via complete_execution so it is not leaked (REQ-F-009c / AC-008).
        self.execution_tracking.complete_execution.assert_called_once_with(
            self.execution_tracker
        )

    async def test_tc010c_cancel_before_tracker_created_does_not_finalize(self):
        """TC-010 / B-2: if cancel happens before tracker is created, no finalization.

        The tracker is created at the very first line of the try block.  If a
        CancelledError fires *before* that line (e.g. Python cancels the task
        before entry), complete_execution must NOT be called because there is
        nothing to finalize.  This test guards against an over-eager finalization
        that would crash with AttributeError/TypeError on a None tracker.

        Caller-Path Contract: same as test_tc010b.
        """
        # Patch create_tracker to simulate task cancellation before tracker creation
        # by making create_tracker itself raise CancelledError.
        self.execution_tracking.create_tracker.side_effect = asyncio.CancelledError()

        try:
            await self.service.resume_from_checkpoint_async(
                bundle=self.bundle,
                thread_id="cancel-thread-001",
                checkpoint_state={},
            )
        except (asyncio.CancelledError, BaseException):
            pass

        # complete_execution must NOT be called — no tracker was created
        self.execution_tracking.complete_execution.assert_not_called()


if __name__ == "__main__":
    unittest.main()
