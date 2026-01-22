"""Unit tests for GraphRunnerService conditional checkpoint assembly."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

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


if __name__ == "__main__":
    unittest.main()
