"""
Tests for NodeSpec output_fields feature.

Tests the new output_fields list field and is_multi_output() method,
ensuring backward compatibility with existing output_field string.
"""

import unittest
from agentmap.models.graph_spec import NodeSpec


class TestNodeSpecOutputFields(unittest.TestCase):
    """Test cases for NodeSpec output_fields list and is_multi_output method."""

    def test_output_fields_default_empty_list(self):
        """Test that output_fields defaults to empty list."""
        node = NodeSpec(name="test_node", graph_name="test_graph")
        self.assertEqual(node.output_fields, [])

    def test_output_fields_can_be_initialized(self):
        """Test that output_fields can be initialized with values."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_fields=["field1", "field2"],
        )
        self.assertEqual(node.output_fields, ["field1", "field2"])

    def test_output_fields_single_item_list(self):
        """Test output_fields with single item."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_fields=["single_field"],
        )
        self.assertEqual(node.output_fields, ["single_field"])

    def test_output_fields_multiple_items_list(self):
        """Test output_fields with multiple items."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_fields=["field1", "field2", "field3"],
        )
        self.assertEqual(node.output_fields, ["field1", "field2", "field3"])

    def test_is_multi_output_false_with_empty_list(self):
        """Test is_multi_output returns False for empty output_fields."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_fields=[],
        )
        self.assertFalse(node.is_multi_output())

    def test_is_multi_output_false_with_single_field(self):
        """Test is_multi_output returns False for single field."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_fields=["single_field"],
        )
        self.assertFalse(node.is_multi_output())

    def test_is_multi_output_true_with_two_fields(self):
        """Test is_multi_output returns True for two fields."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_fields=["field1", "field2"],
        )
        self.assertTrue(node.is_multi_output())

    def test_is_multi_output_true_with_multiple_fields(self):
        """Test is_multi_output returns True for multiple fields."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_fields=["field1", "field2", "field3", "field4"],
        )
        self.assertTrue(node.is_multi_output())

    def test_backward_compatibility_output_field_string(self):
        """Test that existing output_field string still works."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_field="legacy_output",
        )
        self.assertEqual(node.output_field, "legacy_output")
        self.assertEqual(node.output_fields, [])

    def test_both_output_field_and_output_fields_can_coexist(self):
        """Test that both output_field and output_fields can be set simultaneously."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_field="legacy_output",
            output_fields=["new_field1", "new_field2"],
        )
        self.assertEqual(node.output_field, "legacy_output")
        self.assertEqual(node.output_fields, ["new_field1", "new_field2"])
        self.assertTrue(node.is_multi_output())

    def test_is_multi_output_ignores_output_field_string(self):
        """Test that is_multi_output only checks output_fields list."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_field="some_legacy_field",
            output_fields=[],
        )
        self.assertFalse(node.is_multi_output())

    def test_output_fields_with_complex_field_names(self):
        """Test output_fields with complex field names (underscores, numbers, etc)."""
        node = NodeSpec(
            name="test_node",
            graph_name="test_graph",
            output_fields=["output_field_1", "output_field_2", "final_result_v2"],
        )
        self.assertEqual(len(node.output_fields), 3)
        self.assertTrue(node.is_multi_output())


if __name__ == "__main__":
    unittest.main()
