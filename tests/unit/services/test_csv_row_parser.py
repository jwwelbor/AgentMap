"""
Unit tests for CSVRowParser, focusing on output field parsing.

Tests parsing of pipe-delimited Output_Field values into lists,
whitespace trimming, and backward compatibility with single values.
"""

import unittest
from unittest.mock import Mock

import pandas as pd

from agentmap.services.csv_graph_parser.column_config import CSVColumnConfig
from agentmap.services.csv_graph_parser.parsers import CSVRowParser
from tests.utils.mock_service_factory import MockServiceFactory


class TestCSVRowParserOutputFieldParsing(unittest.TestCase):
    """Test CSVRowParser output field parsing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.column_config = CSVColumnConfig()
        self.parser = CSVRowParser(self.column_config, self.mock_logging)

    def test_parse_single_output_field(self):
        """Test parsing single output field (backward compatibility)."""
        row = pd.Series(
            {
                "GraphName": "TestGraph",
                "Node": "TestNode",
                "Output_Field": "result",
                "Input_Fields": "",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Tool_Source": "",
                "Available_Tools": "",
            }
        )

        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Single field should be stored as-is (backward compatible)
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "result")

    def test_parse_pipe_delimited_output_fields(self):
        """Test parsing pipe-delimited output fields."""
        row = pd.Series(
            {
                "GraphName": "TestGraph",
                "Node": "TestNode",
                "Output_Field": "field1|field2|field3",
                "Input_Fields": "",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Tool_Source": "",
                "Available_Tools": "",
            }
        )

        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Multiple fields should be parsed into list
        self.assertIsNotNone(node_spec)
        self.assertIsInstance(node_spec.output_fields, list)
        self.assertEqual(node_spec.output_fields, ["field1", "field2", "field3"])

    def test_parse_output_fields_with_whitespace(self):
        """Test parsing output fields with whitespace around pipes."""
        row = pd.Series(
            {
                "GraphName": "TestGraph",
                "Node": "TestNode",
                "Output_Field": "field1 | field2 | field3",
                "Input_Fields": "",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Tool_Source": "",
                "Available_Tools": "",
            }
        )

        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Whitespace should be trimmed from each field
        self.assertIsNotNone(node_spec)
        self.assertIsInstance(node_spec.output_fields, list)
        self.assertEqual(node_spec.output_fields, ["field1", "field2", "field3"])

    def test_parse_output_fields_with_empty_pipes(self):
        """Test parsing output fields with empty values (should be filtered)."""
        row = pd.Series(
            {
                "GraphName": "TestGraph",
                "Node": "TestNode",
                "Output_Field": "field1||field2||field3",
                "Input_Fields": "",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Tool_Source": "",
                "Available_Tools": "",
            }
        )

        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Empty values should be filtered out
        self.assertIsNotNone(node_spec)
        self.assertIsInstance(node_spec.output_fields, list)
        self.assertEqual(node_spec.output_fields, ["field1", "field2", "field3"])

    def test_parse_empty_output_field(self):
        """Test parsing empty output field."""
        row = pd.Series(
            {
                "GraphName": "TestGraph",
                "Node": "TestNode",
                "Output_Field": "",
                "Input_Fields": "",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Tool_Source": "",
                "Available_Tools": "",
            }
        )

        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Empty output field should result in None
        self.assertIsNotNone(node_spec)
        self.assertIsNone(node_spec.output_field)
        self.assertEqual(node_spec.output_fields, [])

    def test_parse_whitespace_only_output_field(self):
        """Test parsing output field with only whitespace."""
        row = pd.Series(
            {
                "GraphName": "TestGraph",
                "Node": "TestNode",
                "Output_Field": "   ",
                "Input_Fields": "",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Tool_Source": "",
                "Available_Tools": "",
            }
        )

        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Whitespace-only should be treated as empty
        self.assertIsNotNone(node_spec)
        self.assertIsNone(node_spec.output_field)
        self.assertEqual(node_spec.output_fields, [])

    def test_parse_output_fields_consistency_with_input_fields(self):
        """Test that output field parsing follows same pattern as input_fields."""
        row = pd.Series(
            {
                "GraphName": "TestGraph",
                "Node": "TestNode",
                "Output_Field": "out1|out2|out3",
                "Input_Fields": "in1|in2|in3",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Tool_Source": "",
                "Available_Tools": "",
            }
        )

        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Both should be parsed into lists following same pattern
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.input_fields, ["in1", "in2", "in3"])
        self.assertIsInstance(node_spec.output_fields, list)
        self.assertEqual(node_spec.output_fields, ["out1", "out2", "out3"])

    def test_single_field_backward_compatibility_check(self):
        """Test backward compatibility: single field maintains string in output_field."""
        row = pd.Series(
            {
                "GraphName": "TestGraph",
                "Node": "TestNode",
                "Output_Field": "single_result",
                "Input_Fields": "",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Tool_Source": "",
                "Available_Tools": "",
            }
        )

        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # For backward compatibility, single output_field should stay as string
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "single_result")
        # output_fields should be a list with one element
        self.assertEqual(node_spec.output_fields, ["single_result"])

    def test_parse_output_fields_with_special_characters(self):
        """Test parsing output fields with valid special characters in field names."""
        row = pd.Series(
            {
                "GraphName": "TestGraph",
                "Node": "TestNode",
                "Output_Field": "result_1|result-2|result.3",
                "Input_Fields": "",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Tool_Source": "",
                "Available_Tools": "",
            }
        )

        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Special characters in field names should be preserved
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_fields, ["result_1", "result-2", "result.3"])


if __name__ == "__main__":
    unittest.main()
