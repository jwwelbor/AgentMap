"""
Unit tests for CSVRowParser with multi-output field parsing.

Tests comprehensive CSV parsing functionality including:
- Single output field parsing (backward compatibility)
- Multi-output field parsing (pipe-separated values)
- Empty output field handling
- Whitespace trimming in multi-output
- Edge cases (trailing pipes, multiple pipes, etc.)

Follows project testing patterns using unittest.TestCase and MockServiceFactory.
"""

import unittest
from unittest.mock import Mock

import pandas as pd

from agentmap.services.csv_graph_parser.column_config import CSVColumnConfig
from agentmap.services.csv_graph_parser.parsers import CSVRowParser
from tests.utils.mock_service_factory import MockServiceFactory


class TestCSVRowParserOutputField(unittest.TestCase):
    """Test CSVRowParser output field parsing functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.column_config = CSVColumnConfig()
        self.parser = CSVRowParser(
            column_config=self.column_config, logger=self.mock_logging
        )

    def _create_test_row(self, output_field: str = None) -> pd.Series:
        """
        Create a test pandas Series with standard fields.

        Args:
            output_field: Value for Output_Field column

        Returns:
            pd.Series representing a CSV row
        """
        data = {
            "GraphName": "TestGraph",
            "Node": "TestNode",
            "AgentType": "TestAgent",
            "Prompt": "Test prompt",
            "Description": "Test description",
            "Context": "Test context",
            "Input_Fields": "",
            "Output_Field": output_field if output_field is not None else "",
            "Edge": "",
            "Success_Next": "",
            "Failure_Next": "",
            "Tool_Source": "",
            "Available_Tools": "",
        }
        return pd.Series(data)

    def test_single_output_field_parsing(self):
        """Test backward compatibility: single output field parsing."""
        # Arrange
        row = self._create_test_row(output_field="result")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "result")

    def test_single_output_field_with_whitespace(self):
        """Test single output field with surrounding whitespace."""
        # Arrange
        row = self._create_test_row(output_field="  result  ")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "result")

    def test_multi_output_field_parsing_two_fields(self):
        """Test multi-output parsing with two pipe-separated fields."""
        # Arrange
        row = self._create_test_row(output_field="result|status")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "result|status")

    def test_multi_output_field_parsing_three_fields(self):
        """Test multi-output parsing with three pipe-separated fields."""
        # Arrange
        row = self._create_test_row(output_field="result|status|count")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "result|status|count")

    def test_multi_output_with_internal_whitespace(self):
        """Test multi-output with whitespace around pipes."""
        # Arrange
        row = self._create_test_row(output_field="result | status | count")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        # The output_field should preserve the original pipe-separated format
        # Whitespace handling is expected to be preserved as-is
        self.assertEqual(node_spec.output_field, "result | status | count")

    def test_multi_output_with_leading_trailing_whitespace(self):
        """Test multi-output with leading/trailing whitespace."""
        # Arrange
        row = self._create_test_row(output_field="  result|status|count  ")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        # After .strip() on the entire field
        self.assertEqual(node_spec.output_field, "result|status|count")

    def test_empty_output_field(self):
        """Test empty output field handling."""
        # Arrange
        row = self._create_test_row(output_field="")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertIsNone(node_spec.output_field)

    def test_whitespace_only_output_field(self):
        """Test whitespace-only output field (should be treated as empty)."""
        # Arrange
        row = self._create_test_row(output_field="   ")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertIsNone(node_spec.output_field)

    def test_output_field_with_trailing_pipe(self):
        """Test multi-output with trailing pipe."""
        # Arrange
        row = self._create_test_row(output_field="result|status|")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        # The parser should preserve the input as-is
        self.assertEqual(node_spec.output_field, "result|status|")

    def test_output_field_with_leading_pipe(self):
        """Test multi-output with leading pipe."""
        # Arrange
        row = self._create_test_row(output_field="|result|status")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "|result|status")

    def test_output_field_with_consecutive_pipes(self):
        """Test multi-output with consecutive pipes."""
        # Arrange
        row = self._create_test_row(output_field="result||status")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "result||status")

    def test_output_field_with_only_pipes(self):
        """Test output field containing only pipes (converted to None after strip)."""
        # Arrange
        row = self._create_test_row(output_field="|||")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        # Pipes only become empty string after strip, which converts to None via `or None`
        self.assertIsNone(node_spec.output_field)

    def test_output_field_with_special_characters(self):
        """Test multi-output with special characters in field names."""
        # Arrange
        row = self._create_test_row(output_field="result_data|status-code|count.value")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(
            node_spec.output_field, "result_data|status-code|count.value"
        )

    def test_output_field_nan_handling(self):
        """Test NaN value handling for output field."""
        # Arrange
        row = self._create_test_row()
        row["Output_Field"] = float("nan")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertIsNone(node_spec.output_field)

    def test_output_field_none_handling(self):
        """Test None value handling for output field."""
        # Arrange
        row = self._create_test_row()
        row["Output_Field"] = None

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertIsNone(node_spec.output_field)

    def test_output_field_long_field_names(self):
        """Test multi-output with long field names."""
        # Arrange
        long_field = "very_long_result_field_name|another_very_long_status_field|long_count"
        row = self._create_test_row(output_field=long_field)

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, long_field)

    def test_output_field_many_fields(self):
        """Test multi-output with many pipe-separated fields."""
        # Arrange
        many_fields = "|".join([f"field{i}" for i in range(10)])
        row = self._create_test_row(output_field=many_fields)

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, many_fields)

    def test_output_field_with_numbers(self):
        """Test multi-output with numeric field names."""
        # Arrange
        row = self._create_test_row(output_field="field1|field2|field3")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "field1|field2|field3")

    def test_output_field_with_uppercase(self):
        """Test multi-output with uppercase field names."""
        # Arrange
        row = self._create_test_row(output_field="RESULT|STATUS|COUNT")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "RESULT|STATUS|COUNT")

    def test_output_field_with_mixed_case(self):
        """Test multi-output with mixed case field names."""
        # Arrange
        row = self._create_test_row(output_field="Result|Status|Count")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "Result|Status|Count")


class TestCSVRowParserInputFieldsParsing(unittest.TestCase):
    """Test CSVRowParser input fields parsing (pipe-separated format)."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.column_config = CSVColumnConfig()
        self.parser = CSVRowParser(
            column_config=self.column_config, logger=self.mock_logging
        )

    def _create_test_row(self, input_fields: str = None) -> pd.Series:
        """
        Create a test pandas Series with standard fields.

        Args:
            input_fields: Value for Input_Fields column

        Returns:
            pd.Series representing a CSV row
        """
        data = {
            "GraphName": "TestGraph",
            "Node": "TestNode",
            "AgentType": "TestAgent",
            "Prompt": "Test prompt",
            "Description": "Test description",
            "Context": "Test context",
            "Input_Fields": input_fields if input_fields is not None else "",
            "Output_Field": "",
            "Edge": "",
            "Success_Next": "",
            "Failure_Next": "",
            "Tool_Source": "",
            "Available_Tools": "",
        }
        return pd.Series(data)

    def test_single_input_field(self):
        """Test parsing single input field."""
        # Arrange
        row = self._create_test_row(input_fields="input_data")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.input_fields, ["input_data"])

    def test_multiple_input_fields(self):
        """Test parsing multiple pipe-separated input fields."""
        # Arrange
        row = self._create_test_row(input_fields="input1|input2|input3")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.input_fields, ["input1", "input2", "input3"])

    def test_input_fields_with_whitespace(self):
        """Test input fields with whitespace trimming."""
        # Arrange
        row = self._create_test_row(input_fields="  input1  |  input2  ")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.input_fields, ["input1", "input2"])

    def test_empty_input_fields(self):
        """Test empty input fields."""
        # Arrange
        row = self._create_test_row(input_fields="")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.input_fields, [])


class TestCSVRowParserEdgeTargets(unittest.TestCase):
    """Test CSVRowParser edge target parsing functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.column_config = CSVColumnConfig()
        self.parser = CSVRowParser(
            column_config=self.column_config, logger=self.mock_logging
        )

    def test_parse_edge_targets_single_target(self):
        """Test parsing single edge target."""
        # Act
        result = self.parser.parse_edge_targets("NextNode")

        # Assert
        self.assertEqual(result, "NextNode")

    def test_parse_edge_targets_multiple_targets(self):
        """Test parsing multiple pipe-separated edge targets."""
        # Act
        result = self.parser.parse_edge_targets("NodeA|NodeB|NodeC")

        # Assert
        self.assertEqual(result, ["NodeA", "NodeB", "NodeC"])

    def test_parse_edge_targets_with_whitespace(self):
        """Test parsing edge targets with whitespace."""
        # Act
        result = self.parser.parse_edge_targets("Node A | Node B")

        # Assert
        self.assertEqual(result, ["Node A", "Node B"])

    def test_parse_edge_targets_empty(self):
        """Test parsing empty edge target."""
        # Act
        result = self.parser.parse_edge_targets("")

        # Assert
        self.assertIsNone(result)

    def test_parse_edge_targets_whitespace_only(self):
        """Test parsing whitespace-only edge target."""
        # Act
        result = self.parser.parse_edge_targets("   ")

        # Assert
        self.assertIsNone(result)

    def test_parse_edge_targets_trailing_pipe(self):
        """Test parsing edge target with trailing pipe."""
        # Act
        result = self.parser.parse_edge_targets("NodeA|")

        # Assert
        self.assertEqual(result, "NodeA")

    def test_parse_edge_targets_leading_pipe(self):
        """Test parsing edge target with leading pipe."""
        # Act
        result = self.parser.parse_edge_targets("|NodeA")

        # Assert
        self.assertEqual(result, "NodeA")

    def test_parse_edge_targets_consecutive_pipes(self):
        """Test parsing edge targets with consecutive pipes."""
        # Act
        result = self.parser.parse_edge_targets("NodeA||NodeB")

        # Assert
        self.assertEqual(result, ["NodeA", "NodeB"])


class TestCSVRowParserNodeSpecParsing(unittest.TestCase):
    """Test CSVRowParser node spec parsing with output fields."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.column_config = CSVColumnConfig()
        self.parser = CSVRowParser(
            column_config=self.column_config, logger=self.mock_logging
        )

    def _create_test_row(
        self,
        graph_name: str = "TestGraph",
        node_name: str = "TestNode",
        output_field: str = None,
        edge: str = None,
    ) -> pd.Series:
        """
        Create a test pandas Series with standard fields.

        Args:
            graph_name: GraphName value
            node_name: Node value
            output_field: Output_Field value
            edge: Edge value

        Returns:
            pd.Series representing a CSV row
        """
        data = {
            "GraphName": graph_name,
            "Node": node_name,
            "AgentType": "TestAgent",
            "Prompt": "Test prompt",
            "Description": "Test description",
            "Context": "Test context",
            "Input_Fields": "",
            "Output_Field": output_field if output_field is not None else "",
            "Edge": edge if edge is not None else "",
            "Success_Next": "",
            "Failure_Next": "",
            "Tool_Source": "",
            "Available_Tools": "",
        }
        return pd.Series(data)

    def test_node_spec_with_single_output_and_edge(self):
        """Test parsing NodeSpec with single output and edge target."""
        # Arrange
        row = self._create_test_row(
            output_field="result", edge="NextNode"
        )

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "result")
        self.assertEqual(node_spec.edge, "NextNode")

    def test_node_spec_with_multi_output_and_parallel_edges(self):
        """Test parsing NodeSpec with multi-output and parallel edge targets."""
        # Arrange
        row = self._create_test_row(
            output_field="result|status",
            edge="NodeA|NodeB"
        )

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.output_field, "result|status")
        self.assertEqual(node_spec.edge, ["NodeA", "NodeB"])

    def test_node_spec_missing_graph_name(self):
        """Test that NodeSpec parsing returns None when GraphName is missing."""
        # Arrange
        row = self._create_test_row(graph_name="", output_field="result")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNone(node_spec)

    def test_node_spec_missing_node_name(self):
        """Test that NodeSpec parsing returns None when Node is missing."""
        # Arrange
        row = self._create_test_row(node_name="", output_field="result")

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNone(node_spec)

    def test_node_spec_complete_with_all_fields(self):
        """Test parsing complete NodeSpec with all fields including multi-output."""
        # Arrange
        data = {
            "GraphName": "CompleteGraph",
            "Node": "CompleteNode",
            "AgentType": "LLMAgent",
            "Prompt": "You are a helpful assistant",
            "Description": "Test node",
            "Context": "Test context data",
            "Input_Fields": "user_input|previous_output",
            "Output_Field": "response|confidence|metadata",
            "Edge": "NextNode",
            "Success_Next": "OnSuccessNode",
            "Failure_Next": "OnFailureNode|OnTimeoutNode",
            "Tool_Source": "tools.py",
            "Available_Tools": "tool1|tool2|tool3",
        }
        row = pd.Series(data)

        # Act
        node_spec = self.parser.parse_row_to_node_spec(row, line_number=2)

        # Assert
        self.assertIsNotNone(node_spec)
        self.assertEqual(node_spec.graph_name, "CompleteGraph")
        self.assertEqual(node_spec.name, "CompleteNode")
        self.assertEqual(node_spec.agent_type, "LLMAgent")
        self.assertEqual(node_spec.input_fields, ["user_input", "previous_output"])
        self.assertEqual(node_spec.output_field, "response|confidence|metadata")
        self.assertEqual(node_spec.edge, "NextNode")
        self.assertEqual(node_spec.success_next, "OnSuccessNode")
        self.assertEqual(node_spec.failure_next, ["OnFailureNode", "OnTimeoutNode"])
        self.assertEqual(node_spec.available_tools, ["tool1", "tool2", "tool3"])


if __name__ == "__main__":
    unittest.main()
