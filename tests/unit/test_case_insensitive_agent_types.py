"""
Test case to verify the fix for case-insensitive agent type handling.

This test checks that agent types like "Default" (capital D) are properly
normalized to lowercase when creating GraphBundles.
"""

import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, r"C:\Users\jwwel\Documents\code\AgentMap\src")

from agentmap.models.node import Node  # noqa: E402
from agentmap.services.static_bundle_analyzer import StaticBundleAnalyzer  # noqa: E402


class TestCaseInsensitiveAgentTypes(unittest.TestCase):
    """Test that agent types are handled case-insensitively."""

    def setUp(self):
        """Set up mocks for testing."""
        # Mock dependencies
        self.mock_declaration_registry = Mock()
        self.mock_custom_agent_manager = Mock()
        self.mock_csv_parser = Mock()
        self.mock_logging_service = Mock()

        # Mock logger
        mock_logger = Mock()
        self.mock_logging_service.get_class_logger.return_value = mock_logger

        # Create analyzer instance
        self.analyzer = StaticBundleAnalyzer(
            self.mock_declaration_registry,
            self.mock_custom_agent_manager,
            self.mock_csv_parser,
            self.mock_logging_service,
        )

    def test_extract_agent_types_normalizes_to_lowercase(self):
        """Test that _extract_agent_types normalizes agent types to lowercase."""
        # Create nodes with different case agent types
        nodes = [
            self._create_node("Node1", "Default"),
            self._create_node("Node2", "OPENAI"),
            self._create_node("Node3", "AnThRoPiC"),
            self._create_node("Node4", "default"),  # Already lowercase
        ]

        # Extract agent types
        agent_types = self.analyzer._extract_agent_types(nodes)

        # Verify all are lowercase
        self.assertEqual(agent_types, {"default", "openai", "anthropic"})

        # Verify no duplicates (Default and default should be same)
        self.assertEqual(len(agent_types), 3)

    def test_validate_declarations_works_with_lowercase(self):
        """Test that _validate_declarations works with lowercase agent types."""
        # Setup mock declarations
        self.mock_declaration_registry.get_agent_declaration.side_effect = lambda x: (
            True if x in ["default", "openai"] else None
        )
        self.mock_custom_agent_manager.get_agent_declaration.side_effect = lambda x: (
            {"class_path": f"custom.{x}"} if x == "anthropic" else None
        )

        # Test with lowercase agent types (as they would come from _extract_agent_types)
        agent_types = {"default", "openai", "anthropic", "missing"}

        valid, missing = self.analyzer._validate_declarations(agent_types)

        # Verify results
        self.assertEqual(valid, {"default", "openai", "anthropic"})
        self.assertEqual(missing, {"missing"})

    def test_end_node_with_capital_default(self):
        """Test that an End node with 'Default' agent type works correctly."""
        # Create an End node with capital D Default
        end_node = self._create_node("End", "Default")

        # Extract agent types
        agent_types = self.analyzer._extract_agent_types([end_node])

        # Should be normalized to lowercase
        self.assertEqual(agent_types, {"default"})
        self.assertNotIn("Default", agent_types)

    def _create_node(self, name, agent_type):
        """Helper to create a node with specified agent type."""
        node = Node(name=name)
        node.agent_type = agent_type
        return node


if __name__ == "__main__":
    # Run the tests
    unittest.main(verbosity=2)
