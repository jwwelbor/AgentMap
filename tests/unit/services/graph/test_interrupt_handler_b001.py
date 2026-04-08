"""
Regression test for B001: run_workflow -> resume_workflow round-trip broken for human agent.

Root cause: handle_langgraph_interrupt() early-returns without calling
_store_thread_metadata when the fallback execution-tracker path is used
(interrupt_metadata lacks a 'raw' key, so interrupt_value is empty/falsy).
resume_workflow() then raises 'Thread not found in storage'.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.services.graph.runner.interrupt_handler import GraphInterruptHandler
from tests.utils.mock_service_factory import MockServiceFactory

_DISPLAY_PATCH = "agentmap.deployment.cli.display_utils.display_interaction_request"


def _make_handler(interaction_handler=None):
    """Build a GraphInterruptHandler with minimal mocks."""
    logging_service = MockServiceFactory.create_mock_logging_service()
    if interaction_handler is None:
        interaction_handler = Mock()
    return GraphInterruptHandler(
        logging_service=logging_service,
        interaction_handler_service=interaction_handler,
    )


def _make_bundle(node_name="human_node", agent_type="HumanAgent"):
    """Return a minimal GraphBundle-like mock."""
    node = Mock(spec=Node)
    node.agent_type = agent_type
    node.context = {"prompt": "Please review this"}

    bundle = Mock(spec=GraphBundle)
    bundle.graph_name = "test_graph"
    bundle.config_path = None
    bundle.nodes = {node_name: node}
    return bundle


def _make_execution_tracker(node_name="human_node", success=None):
    """Return a minimal execution-tracker with one pending node."""
    node_exec = SimpleNamespace(
        node_name=node_name,
        success=success,
        inputs={"document": "some content"},
    )
    return SimpleNamespace(node_executions=[node_exec])


def _run_handler(state):
    """Run handle_langgraph_interrupt with the given state; return (result, mock handler)."""
    interaction_handler = Mock()
    handler = _make_handler(interaction_handler)
    bundle = _make_bundle(node_name="human_node", agent_type="HumanAgent")
    tracker = _make_execution_tracker(node_name="human_node", success=None)

    with patch(_DISPLAY_PATCH, return_value=None):
        result = handler.handle_langgraph_interrupt(
            state=state,
            bundle=bundle,
            thread_id="thread-b001",
            execution_tracker=tracker,
        )
    return result, interaction_handler


class TestInterruptHandlerB001(unittest.TestCase):
    """
    B001 regression: _store_thread_metadata must be called for human_interaction
    even when interrupt metadata comes from the execution-tracker fallback
    (i.e., there is no 'raw' key in interrupt_metadata).
    """

    def test_store_thread_metadata_called_via_fallback_path(self):
        """
        When LangGraph state has no interrupt tasks (fallback path is used),
        handle_langgraph_interrupt must still call _store_thread_metadata so that
        resume_workflow can load the thread pickle.
        """
        # No LangGraph state tasks — forces the execution-tracker fallback
        state = SimpleNamespace(tasks=[])
        result, interaction_handler = _run_handler(state)

        # _store_thread_metadata MUST have been called — this was the B001 bug
        interaction_handler._store_thread_metadata.assert_called_once()
        interaction_handler._store_interaction_request.assert_called_once()

        self.assertIsNotNone(result)
        self.assertEqual(result.get("type"), "human_interaction")
        self.assertEqual(result.get("thread_id"), "thread-b001")

    def test_store_thread_metadata_called_when_langgraph_provides_minimal_interrupt(
        self,
    ):
        """
        When LangGraph state has a task with a minimal interrupt value (type present
        but no interaction_type/prompt/options fields), handle_langgraph_interrupt must
        still reach _store_thread_metadata using .get() defaults.
        """
        interrupt_obj = SimpleNamespace(
            value={"type": "human_interaction", "node_name": "human_node"}
        )
        task = SimpleNamespace(interrupts=[interrupt_obj])
        state = SimpleNamespace(tasks=[task])
        result, interaction_handler = _run_handler(state)

        interaction_handler._store_thread_metadata.assert_called_once()

        self.assertIsNotNone(result)
        self.assertEqual(result.get("type"), "human_interaction")


if __name__ == "__main__":
    unittest.main()
