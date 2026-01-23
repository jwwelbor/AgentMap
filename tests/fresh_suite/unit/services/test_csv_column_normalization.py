import os
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

# Add the project root to the path so we can import tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from agentmap.services.csv_graph_parser_service import CSVGraphParserService
from agentmap.services.validation.csv_validation_service import CSVValidationService

# Import from tests which is at the project root level
from tests.utils.mock_service_factory import MockServiceFactory


class TestCSVColumnNormalization(unittest.TestCase):
    """Test CSV column name normalization with case-insensitive matching."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

        # Create mock services
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()

        # Create a simple mock for FunctionResolutionService
        from unittest.mock import Mock

        self.mock_function_resolution_service = Mock()
        self.mock_function_resolution_service.extract_func_ref.return_value = None

        self.mock_agent_registry_service = (
            MockServiceFactory.create_mock_agent_registry_service()
        )

        # Create services with mocked dependencies
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
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_case_insensitive_normalization(self):
        """Test that column names are normalized case-insensitively."""
        # Create CSV with mixed case column names
        csv_content = """graph_name,NODE,agent_Type,PROMPT,description
TestGraph,Start,Default,Hello,Starting node
TestGraph,End,Echo,Done,Ending node"""

        csv_path = Path(self.temp_dir) / "test_case.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        # Parse CSV
        graph_spec = self.csv_parser.parse_csv_to_graph_spec(csv_path)

        # Verify nodes were parsed correctly
        self.assertEqual(len(graph_spec.graphs), 1)
        self.assertIn("TestGraph", graph_spec.graphs)
        self.assertEqual(len(graph_spec.graphs["TestGraph"]), 2)

        # Verify node specs have correct data
        nodes = graph_spec.graphs["TestGraph"]
        start_node = next(n for n in nodes if n.name == "Start")
        self.assertEqual(start_node.agent_type, "Default")
        self.assertEqual(start_node.prompt, "Hello")
        self.assertEqual(start_node.description, "Starting node")

    def test_alias_normalization(self):
        """Test that column aliases are normalized correctly."""
        # Create CSV with various aliases
        csv_content = """workflow_name,node_name,Type,Instructions,desc,input_fields,output,next_on_success,next_on_failure
MyWorkflow,Step1,LLM,Process data,First step,input|context,result,Step2,ErrorHandler
MyWorkflow,Step2,Echo,Display result,Second step,result,output,,
MyWorkflow,ErrorHandler,Echo,Show error,Error handler,error,error_msg,,"""

        csv_path = Path(self.temp_dir) / "test_aliases.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        # Parse CSV
        graph_spec = self.csv_parser.parse_csv_to_graph_spec(csv_path)

        # Verify nodes were parsed correctly
        self.assertEqual(len(graph_spec.graphs), 1)
        self.assertIn("MyWorkflow", graph_spec.graphs)
        self.assertEqual(len(graph_spec.graphs["MyWorkflow"]), 3)

        # Verify node specs have correct data
        nodes = graph_spec.graphs["MyWorkflow"]
        step1 = next(n for n in nodes if n.name == "Step1")
        self.assertEqual(step1.agent_type, "LLM")
        self.assertEqual(step1.prompt, "Process data")
        self.assertEqual(step1.description, "First step")
        self.assertEqual(step1.input_fields, ["input", "context"])
        self.assertEqual(step1.output_field, "result")
        self.assertEqual(step1.success_next, "Step2")
        self.assertEqual(step1.failure_next, "ErrorHandler")

    def test_edge_vs_next_node_aliases(self):
        """Test that Edge and next_node aliases work correctly."""
        # Create CSV with next_node alias
        csv_content = """GraphName,Node,next_node,AgentType
LinearGraph,Start,Middle,Default
LinearGraph,Middle,End,Default  
LinearGraph,End,,Echo"""

        csv_path = Path(self.temp_dir) / "test_next_node.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        # Parse CSV
        graph_spec = self.csv_parser.parse_csv_to_graph_spec(csv_path)

        # Verify edges were parsed correctly
        nodes = graph_spec.graphs["LinearGraph"]
        start_node = next(n for n in nodes if n.name == "Start")
        middle_node = next(n for n in nodes if n.name == "Middle")

        # next_node should be mapped to Edge
        self.assertEqual(start_node.edge, "Middle")
        self.assertEqual(middle_node.edge, "End")

    def test_validation_with_normalized_columns(self):
        """Test that validation works with normalized column names."""
        # Create CSV with mixed aliases
        csv_content = """workflow,name,Type,prompt_template,Config
TestFlow,Init,input,Enter name:,"{'timeout': 30}"
TestFlow,Process,Default,Hello {name},"{'memory': True}"
TestFlow,End,Echo,Complete,{}"""

        csv_path = Path(self.temp_dir) / "test_validation.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        # Validate CSV
        validation_result = self.csv_validator.validate_file(csv_path)

        # Should be valid after normalization
        self.assertTrue(validation_result.is_valid)
        self.assertFalse(validation_result.has_errors)

    def test_mixed_case_and_aliases(self):
        """Test combination of case differences and aliases."""
        # Create CSV with complex column naming
        csv_content = """WORKFLOW_NAME,node_NAME,agent,INSTRUCTIONS,on_success,ON_FAILURE
TestWorkflow,START,Default,Begin process,PROCESS,ERROR_HANDLER
TestWorkflow,PROCESS,LLM,Analyze input,END,ERROR_HANDLER
TestWorkflow,ERROR_HANDLER,Echo,Handle error,END,
TestWorkflow,END,Echo,Done,,"""

        csv_path = Path(self.temp_dir) / "test_mixed.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        # Parse CSV
        graph_spec = self.csv_parser.parse_csv_to_graph_spec(csv_path)

        # Verify all nodes were parsed
        self.assertEqual(len(graph_spec.graphs["TestWorkflow"]), 4)

        # Verify routing was parsed correctly
        nodes = graph_spec.graphs["TestWorkflow"]
        start_node = next(n for n in nodes if n.name == "START")
        self.assertEqual(start_node.success_next, "PROCESS")
        self.assertEqual(start_node.failure_next, "ERROR_HANDLER")

    def test_unexpected_columns_still_warned(self):
        """Test that unexpected columns still generate warnings."""
        # Create CSV with unexpected columns
        csv_content = """GraphName,Node,AgentType,UnknownColumn,AnotherBadColumn
TestGraph,Node1,Default,Value1,Value2"""

        csv_path = Path(self.temp_dir) / "test_unexpected.csv"
        with open(csv_path, "w") as f:
            f.write(csv_content)

        # Validate CSV
        validation_result = self.csv_validator.validate_file(csv_path)

        # Should have warnings about unexpected columns
        warnings = validation_result.warnings
        self.assertTrue(any("UnknownColumn" in w.message for w in warnings))
        self.assertTrue(any("AnotherBadColumn" in w.message for w in warnings))


if __name__ == "__main__":
    unittest.main()
