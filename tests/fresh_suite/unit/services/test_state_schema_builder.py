"""
Unit tests for StateSchemaBuilder mapped binding support (T-E01-F06-001).

Tests validate that StateSchemaBuilder correctly extracts state keys from
mapped field syntax (state_key:param_name) and raises validation errors
for malformed mappings at build time.
"""

import logging
import unittest
from unittest.mock import create_autospec

from agentmap.models.graph import Graph
from agentmap.models.node import Node
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.graph.state_schema_builder import StateSchemaBuilder
from agentmap.services.logging_service import LoggingService


class TestStateSchemaBuilderMappedBindings(unittest.TestCase):
    """Tests for StateSchemaBuilder mapped field handling."""

    def setUp(self) -> None:
        """Set up test fixtures with autospec mocks."""
        self.mock_config = create_autospec(AppConfigService, instance=True)
        self.mock_logging = create_autospec(LoggingService, instance=True)
        self.mock_logging.get_class_logger.return_value = create_autospec(
            logging.Logger
        )
        self.builder = StateSchemaBuilder(self.mock_config, self.mock_logging)

    def _make_graph(self, node_name: str, inputs: list) -> Graph:
        """Helper to create a minimal Graph with a single node."""
        graph = Graph(name="test_graph")
        node = Node(name=node_name, inputs=inputs, output="result")
        graph.nodes[node_name] = node
        return graph

    # =========================================================================
    # _extract_state_key() tests
    # =========================================================================

    def test_extract_state_key_direct_field(self) -> None:
        """Direct field (no colon) returns the field unchanged."""
        result = self.builder._extract_state_key("damage_roll", "TestNode")
        self.assertEqual(result, "damage_roll")

    def test_extract_state_key_mapped_field(self) -> None:
        """AC-8: Mapped field returns only the state-side key (left of colon)."""
        result = self.builder._extract_state_key("damage_roll:addend_a", "TestNode")
        self.assertEqual(result, "damage_roll")

    def test_extract_state_key_empty_param_name_raises(self) -> None:
        """AC-5: Empty param_name ('damage_roll:') raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.builder._extract_state_key("damage_roll:", "TestNode")
        self.assertIn("damage_roll:", str(ctx.exception))
        self.assertIn("TestNode", str(ctx.exception))

    def test_extract_state_key_empty_state_key_raises(self) -> None:
        """AC-6: Empty state_key (':addend_a') raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.builder._extract_state_key(":addend_a", "TestNode")
        self.assertIn(":addend_a", str(ctx.exception))
        self.assertIn("TestNode", str(ctx.exception))

    def test_extract_state_key_bare_colon_raises(self) -> None:
        """Edge case E1: Bare colon ':' raises ValueError."""
        with self.assertRaises(ValueError):
            self.builder._extract_state_key(":", "TestNode")

    def test_extract_state_key_whitespace_stripped(self) -> None:
        """Edge case E3: Whitespace around colon is stripped before validation."""
        result = self.builder._extract_state_key(" damage_roll : addend_a ", "TestNode")
        self.assertEqual(result, "damage_roll")

    def test_extract_state_key_multi_colon(self) -> None:
        """AC-7: Multiple colons -- only first colon splits."""
        result = self.builder._extract_state_key("namespace:key:param_name", "TestNode")
        self.assertEqual(result, "namespace")

    # =========================================================================
    # create_dynamic_state_schema() tests
    # =========================================================================

    def test_create_dynamic_state_schema_mapped_fields(self) -> None:
        """AC-8: Schema registers state_key, not param_name."""
        graph = self._make_graph("TestNode", ["damage_roll:addend_a", "raw_value"])
        schema = self.builder.create_dynamic_state_schema(graph)

        # Get the field names from the TypedDict annotations
        field_names = set(schema.__annotations__.keys())

        # Should contain the state_key "damage_roll" and direct field "raw_value"
        self.assertIn("damage_roll", field_names)
        self.assertIn("raw_value", field_names)
        # Should NOT contain the param_name "addend_a"
        self.assertNotIn("addend_a", field_names)

    def test_create_dynamic_state_schema_malformed_field_raises(self) -> None:
        """AC-5: Malformed mapped field raises ValueError during schema creation."""
        graph = self._make_graph("BadNode", ["bad_field:"])
        with self.assertRaises(ValueError) as ctx:
            self.builder.create_dynamic_state_schema(graph)
        self.assertIn("bad_field:", str(ctx.exception))
        self.assertIn("BadNode", str(ctx.exception))

    def test_create_dynamic_state_schema_empty_state_key_raises(self) -> None:
        """AC-6: Empty state_key raises ValueError during schema creation."""
        graph = self._make_graph("BadNode", [":param"])
        with self.assertRaises(ValueError) as ctx:
            self.builder.create_dynamic_state_schema(graph)
        self.assertIn(":param", str(ctx.exception))

    def test_create_dynamic_state_schema_direct_fields_unchanged(self) -> None:
        """AC-9: Direct fields (no colon) still registered correctly."""
        graph = self._make_graph("TestNode", ["x", "y"])
        schema = self.builder.create_dynamic_state_schema(graph)
        field_names = set(schema.__annotations__.keys())
        self.assertIn("x", field_names)
        self.assertIn("y", field_names)


if __name__ == "__main__":
    unittest.main()
