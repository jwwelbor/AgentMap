"""Unit tests for GraphBundleService checkpoint detection."""

import unittest
from unittest.mock import Mock

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphBundleServiceCheckpoint(unittest.TestCase):
    """Verify checkpoint requirements detection logic."""

    def setUp(self):
        logging_service = MockServiceFactory.create_mock_logging_service()
        self.service = GraphBundleService(
            logging_service,
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            Mock(),
        )

    def test_requires_checkpoint_for_human_agent(self):
        """Bundle with HumanAgent should require checkpoint support."""
        bundle = GraphBundle(graph_name="human_flow")
        bundle.nodes = {
            "ask": Node(name="ask", agent_type="human"),
            "next": Node(name="next", agent_type="llm"),
        }
        bundle.required_agents = {"human", "llm"}

        result = self.service.requires_checkpoint_support(bundle)
        self.assertTrue(result)

    def test_requires_checkpoint_for_suspend_agent(self):
        """Bundle with SuspendAgent should require checkpoint support."""
        bundle = GraphBundle(graph_name="suspend_flow")
        bundle.nodes = {
            "wait": Node(name="wait", agent_type="suspend"),
            "cont": Node(name="cont", agent_type="llm"),
        }
        bundle.required_agents = {"suspend", "llm"}

        result = self.service.requires_checkpoint_support(bundle)
        self.assertTrue(result)

    def test_requires_checkpoint_case_insensitive(self):
        """Checkpoint requirement detection should be case-insensitive."""
        bundle = GraphBundle(graph_name="mixed_case")
        bundle.nodes = {
            "pause": Node(name="pause", agent_type="HUMAN"),
        }
        bundle.required_agents = {"HUMAN"}

        result = self.service.requires_checkpoint_support(bundle)
        self.assertTrue(result)

    def test_no_checkpoint_without_interrupt_agents(self):
        """Bundle without interrupt-capable agents should not require checkpoint."""
        bundle = GraphBundle(graph_name="simple_flow")
        bundle.nodes = {
            "start": Node(name="start", agent_type="llm"),
            "finish": Node(name="finish", agent_type="success"),
        }
        bundle.required_agents = {"llm", "success"}

        result = self.service.requires_checkpoint_support(bundle)
        self.assertFalse(result)

    def test_empty_bundle(self):
        """Empty bundle should not request checkpoint support."""
        bundle = GraphBundle(graph_name="empty")
        bundle.nodes = {}
        bundle.required_agents = set()

        result = self.service.requires_checkpoint_support(bundle)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
