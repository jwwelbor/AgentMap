"""
Unit tests for CSV tool field validation.

Tests the CSVRowModel validators for AvailableTools and ToolSource fields,
including format validation, cross-field validation, and backward compatibility.
"""

import unittest
import warnings
from pydantic import ValidationError

from agentmap.models.validation.csv_row_model import CSVRowModel


class TestCSVToolValidation(unittest.TestCase):
    """Test CSV tool field validation in CSVRowModel."""

    def test_csv_row_model_with_valid_tool_fields(self):
        """Test CSVRowModel creation with valid tool fields."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="weather_graph",
            Node="weather_node",
            AgentType="tool",
            AvailableTools="get_weather|get_forecast",
            ToolSource="tools/weather_tools.py"
        )

        # Assert
        self.assertEqual(row.GraphName, "weather_graph")
        self.assertEqual(row.Node, "weather_node")
        self.assertEqual(row.AvailableTools, "get_weather|get_forecast")
        self.assertEqual(row.ToolSource, "tools/weather_tools.py")

    def test_available_tools_validator_single_tool(self):
        """Test AvailableTools validator with single tool name."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            AvailableTools="search_tool"
        )

        # Assert
        self.assertEqual(row.AvailableTools, "search_tool")

    def test_available_tools_validator_multiple_tools(self):
        """Test AvailableTools validator with pipe-separated tool names."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            AvailableTools="tool1|tool2|tool3"
        )

        # Assert
        self.assertEqual(row.AvailableTools, "tool1|tool2|tool3")

    def test_available_tools_validator_with_whitespace(self):
        """Test AvailableTools validator strips whitespace."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            AvailableTools="  tool1  |  tool2  |  tool3  "
        )

        # Assert
        self.assertEqual(row.AvailableTools, "tool1|tool2|tool3")

    def test_available_tools_validator_alphanumeric_underscore(self):
        """Test AvailableTools accepts alphanumeric characters and underscores."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            AvailableTools="get_weather_v2|calculate_sum_123"
        )

        # Assert
        self.assertEqual(row.AvailableTools, "get_weather_v2|calculate_sum_123")

    def test_available_tools_validator_invalid_characters(self):
        """Test AvailableTools rejects invalid characters."""
        # Arrange & Act & Assert
        with self.assertRaises(ValidationError) as context:
            CSVRowModel(
                GraphName="test_graph",
                Node="test_node",
                AvailableTools="invalid-tool-name"
            )

        self.assertIn("Invalid tool name", str(context.exception))
        self.assertIn("alphanumeric characters and underscore", str(context.exception))

    def test_available_tools_validator_special_characters(self):
        """Test AvailableTools rejects special characters."""
        # Arrange & Act & Assert
        with self.assertRaises(ValidationError) as context:
            CSVRowModel(
                GraphName="test_graph",
                Node="test_node",
                AvailableTools="tool@name|tool#2"
            )

        self.assertIn("Invalid tool name", str(context.exception))

    def test_available_tools_validator_empty_when_specified(self):
        """Test AvailableTools rejects empty string when specified."""
        # Arrange & Act & Assert
        with self.assertRaises(ValidationError) as context:
            CSVRowModel(
                GraphName="test_graph",
                Node="test_node",
                AvailableTools=""
            )

        self.assertIn("cannot be empty when specified", str(context.exception))

    def test_available_tools_validator_none_is_valid(self):
        """Test AvailableTools accepts None (optional field)."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            AvailableTools=None
        )

        # Assert
        self.assertIsNone(row.AvailableTools)

    def test_tool_source_validator_py_file_path(self):
        """Test ToolSource validator accepts .py file paths."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            ToolSource="tools/my_tools.py"
        )

        # Assert
        self.assertEqual(row.ToolSource, "tools/my_tools.py")

    def test_tool_source_validator_toolnode_keyword(self):
        """Test ToolSource validator accepts 'toolnode' keyword."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            ToolSource="toolnode"
        )

        # Assert
        self.assertEqual(row.ToolSource, "toolnode")

    def test_tool_source_validator_toolnode_case_insensitive(self):
        """Test ToolSource validator accepts 'toolnode' case-insensitively."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            ToolSource="TOOLNODE"
        )

        # Assert
        self.assertEqual(row.ToolSource, "toolnode")

    def test_tool_source_validator_invalid_extension(self):
        """Test ToolSource validator rejects non-.py file paths."""
        # Arrange & Act & Assert
        with self.assertRaises(ValidationError) as context:
            CSVRowModel(
                GraphName="test_graph",
                Node="test_node",
                ToolSource="tools/my_tools.txt"
            )

        self.assertIn("must be either 'toolnode' or a .py file path", str(context.exception))

    def test_tool_source_validator_no_extension(self):
        """Test ToolSource validator rejects paths without .py extension."""
        # Arrange & Act & Assert
        with self.assertRaises(ValidationError) as context:
            CSVRowModel(
                GraphName="test_graph",
                Node="test_node",
                ToolSource="tools/my_tools"
            )

        self.assertIn(".py file path", str(context.exception))

    def test_tool_source_validator_none_is_valid(self):
        """Test ToolSource accepts None (optional field)."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            ToolSource=None
        )

        # Assert
        self.assertIsNone(row.ToolSource)

    def test_cross_field_validation_warning_tools_without_source(self):
        """Test warning when AvailableTools specified without ToolSource."""
        # Arrange & Act
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            row = CSVRowModel(
                GraphName="test_graph",
                Node="test_node",
                AvailableTools="tool1|tool2",
                ToolSource=None
            )

            # Assert
            self.assertEqual(len(w), 1)
            self.assertIn("has AvailableTools but no ToolSource", str(w[0].message))
            self.assertIn("test_node", str(w[0].message))

    def test_cross_field_validation_no_warning_with_both_fields(self):
        """Test no warning when both AvailableTools and ToolSource are specified."""
        # Arrange & Act
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            row = CSVRowModel(
                GraphName="test_graph",
                Node="test_node",
                AvailableTools="tool1",
                ToolSource="tools.py"
            )

            # Assert
            self.assertEqual(len(w), 0)

    def test_cross_field_validation_no_warning_without_tools(self):
        """Test no warning when AvailableTools is None."""
        # Arrange & Act
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            row = CSVRowModel(
                GraphName="test_graph",
                Node="test_node",
                AvailableTools=None,
                ToolSource="tools.py"
            )

            # Assert
            self.assertEqual(len(w), 0)

    def test_backward_compatibility_missing_tool_fields(self):
        """Test backward compatibility when tool fields are not provided."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            AgentType="default",
            Prompt="Test prompt"
        )

        # Assert
        self.assertIsNone(row.AvailableTools)
        self.assertIsNone(row.ToolSource)
        self.assertEqual(row.GraphName, "test_graph")
        self.assertEqual(row.Node, "test_node")

    def test_complex_tool_configuration(self):
        """Test complex tool configuration with multiple tools and py source."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="api_graph",
            Node="api_tools",
            AgentType="tool",
            Prompt="API integration tools",
            AvailableTools="search_api|weather_api|geocode_api",
            ToolSource="integrations/api_tools.py",
            Input_Fields="query|location",
            Output_Field="api_result"
        )

        # Assert
        self.assertEqual(row.GraphName, "api_graph")
        self.assertEqual(row.Node, "api_tools")
        self.assertEqual(row.AvailableTools, "search_api|weather_api|geocode_api")
        self.assertEqual(row.ToolSource, "integrations/api_tools.py")
        self.assertEqual(row.Input_Fields, "query|location")
        self.assertEqual(row.Output_Field, "api_result")

    def test_tool_with_routing_fields(self):
        """Test tool configuration combined with routing fields."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="workflow_graph",
            Node="tool_node",
            AvailableTools="process_data",
            ToolSource="utils/processors.py",
            Success_Next="next_node",
            Failure_Next="error_handler"
        )

        # Assert
        self.assertEqual(row.AvailableTools, "process_data")
        self.assertEqual(row.ToolSource, "utils/processors.py")
        self.assertEqual(row.Success_Next, "next_node")
        self.assertEqual(row.Failure_Next, "error_handler")

    def test_absolute_path_tool_source(self):
        """Test ToolSource with absolute path."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            ToolSource="/absolute/path/to/tools.py"
        )

        # Assert
        self.assertEqual(row.ToolSource, "/absolute/path/to/tools.py")

    def test_relative_path_tool_source(self):
        """Test ToolSource with relative path."""
        # Arrange & Act
        row = CSVRowModel(
            GraphName="test_graph",
            Node="test_node",
            ToolSource="../parent/tools.py"
        )

        # Assert
        self.assertEqual(row.ToolSource, "../parent/tools.py")


if __name__ == "__main__":
    unittest.main()
