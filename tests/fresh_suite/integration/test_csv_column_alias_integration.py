"""
Integration test for CSV column alias support.

This test verifies that CSV files with alternative column names
can be successfully parsed and validated through the actual system.
"""

import os
import shutil

# Add the project root to the path so we can import tests
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from agentmap.services.csv_graph_parser_service import (  # noqa: E402
    CSVGraphParserService,
)
from agentmap.services.validation.csv_validation_service import (  # noqa: E402
    CSVValidationService,
)
from tests.utils.mock_service_factory import MockServiceFactory  # noqa: E402


class TestCSVColumnAliasIntegration(unittest.TestCase):
    """Integration test for CSV column alias functionality."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

        # Create minimal mocks
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = (
            MockServiceFactory.create_mock_app_config_service()
        )
        self.mock_agent_registry_service = (
            MockServiceFactory.create_mock_agent_registry_service()
        )
        self.mock_graph_factory_service = (
            MockServiceFactory.create_mock_graph_factory_service()
        )

        # Create simple mock for FunctionResolutionService
        from unittest.mock import Mock

        self.mock_function_resolution_service = Mock()
        self.mock_function_resolution_service.extract_func_ref.return_value = None

        # Create services
        self.csv_parser = CSVGraphParserService(
            logging_service=self.mock_logging_service
        )

        self.csv_validator = CSVValidationService(
            logging_service=self.mock_logging_service,
            function_resolution_service=self.mock_function_resolution_service,
            agent_registry_service=self.mock_agent_registry_service,
        )

    def tearDown(self):
        """Clean up temporary files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mixed_case_columns(self):
        """Test that mixed case column names work correctly."""
        csv_content = """WORKFLOW,node_NAME,AGENT_type,Prompt_Template,NEXT_on_success,failure_NEXT
TestFlow,START,INPUT,Get user input,PROCESS,ERROR
TestFlow,PROCESS,default,Process the data,END,ERROR
TestFlow,ERROR,echo,Show error,END,
TestFlow,END,echo,Complete,,"""

        csv_path = Path(self.temp_dir) / "mixed_case.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        # Should validate successfully
        validation_result = self.csv_validator.validate_file(csv_path)
        self.assertTrue(validation_result.is_valid)

        # Should parse successfully
        graph_spec = self.csv_parser.parse_csv_to_graph_spec(csv_path)
        self.assertEqual(len(graph_spec.graphs["TestFlow"]), 4)

    def test_legacy_format_still_works(self):
        """Ensure original column names continue to work."""
        csv_content = """GraphName,Node,AgentType,Prompt,Success_Next,Failure_Next,Input_Fields,Output_Field
LegacyFlow,Input,input,Enter value:,Process,Error,,user_value
LegacyFlow,Process,default,Transform value,Output,Error,user_value,result
LegacyFlow,Output,echo,Show result:,,,result,
LegacyFlow,Error,echo,Error occurred,,,error,"""

        csv_path = Path(self.temp_dir) / "legacy.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        # Should work exactly as before
        validation_result = self.csv_validator.validate_file(csv_path)
        self.assertTrue(validation_result.is_valid)

        graph_spec = self.csv_parser.parse_csv_to_graph_spec(csv_path)
        nodes = graph_spec.graphs["LegacyFlow"]
        self.assertEqual(len(nodes), 4)

        # Verify exact field names are preserved
        input_node = next(n for n in nodes if n.name == "Input")
        self.assertEqual(input_node.success_next, "Process")
        self.assertEqual(input_node.failure_next, "Error")

    def test_partial_aliases(self):
        """Test using some aliases mixed with standard names."""
        csv_content = """GraphName,node_name,AgentType,instructions,Success_Next,on_failure
MixedFlow,Start,input,Get input,Process,HandleError
MixedFlow,Process,default,Do work,End,HandleError
MixedFlow,HandleError,echo,Show error,End,
MixedFlow,End,echo,Done,,"""

        csv_path = Path(self.temp_dir) / "partial_aliases.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        # Should work with mixed naming
        validation_result = self.csv_validator.validate_file(csv_path)
        self.assertTrue(validation_result.is_valid)

        graph_spec = self.csv_parser.parse_csv_to_graph_spec(csv_path)
        nodes = graph_spec.graphs["MixedFlow"]

        # Verify both aliased and standard names work
        start_node = next(n for n in nodes if n.name == "Start")
        self.assertEqual(start_node.prompt, "Get input")  # From 'instructions' alias
        self.assertEqual(
            start_node.failure_next, "HandleError"
        )  # From 'on_failure' alias


if __name__ == "__main__":
    unittest.main()
