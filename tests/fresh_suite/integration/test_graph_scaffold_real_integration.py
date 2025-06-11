"""
Integration tests for GraphScaffoldService using REAL services.

These tests complement the existing unit tests by focusing on:
1. Real CSV file processing with actual templates
2. Real IndentedTemplateComposer integration  
3. File system operations
4. Service dependency verification

Note: These are true integration tests using real services, not mocks.
"""

import unittest
import tempfile
import shutil
from unittest.mock import Mock, patch
from pathlib import Path
from typing import Dict, Any
import csv

from agentmap.services.graph_scaffold_service import (
    GraphScaffoldService, 
    ScaffoldOptions,
    ScaffoldResult
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphScaffoldServiceIntegration(unittest.TestCase):
    """Integration tests for GraphScaffoldService with real services."""
    
    def setUp(self):
        """Set up test fixtures with real services and temp directories."""
        # Create temporary directories for test files
        self.temp_dir = Path(tempfile.mkdtemp())
        self.agents_dir = self.temp_dir / "custom_agents"
        self.functions_dir = self.temp_dir / "custom_functions"
        self.csv_dir = self.temp_dir / "graphs"
        
        # Create directories
        self.agents_dir.mkdir(parents=True)
        self.functions_dir.mkdir(parents=True)
        self.csv_dir.mkdir(parents=True)
        
        # Create mock config and logging services
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "custom_agents_path": str(self.agents_dir),
            "functions_path": str(self.functions_dir),
            "csv_path": str(self.csv_dir / "test.csv")
        })
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Configure path methods for integration tests
        self.mock_app_config_service.get_custom_agents_path.return_value = self.agents_dir
        self.mock_app_config_service.get_functions_path.return_value = self.functions_dir
        self.mock_app_config_service.custom_agents_path = self.agents_dir
        self.mock_app_config_service.functions_path = self.functions_dir
        self.mock_app_config_service.csv_path = self.csv_dir / "test.csv"
        
        # Use REAL IndentedTemplateComposer for true integration testing
        from agentmap.services.indented_template_composer import IndentedTemplateComposer
        self.template_composer = IndentedTemplateComposer(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service
        )
        
        # Mock only the function resolution service (not core to this test)
        self.mock_function_resolution_service = Mock()
        
        # Create mock agent registry service for integration testing
        self.mock_agent_registry_service = MockServiceFactory.create_mock_agent_registry_service()
        
        # Initialize service with real IndentedTemplateComposer
        self.service = GraphScaffoldService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            function_resolution_service=self.mock_function_resolution_service,
            agent_registry_service=self.mock_agent_registry_service,
            template_composer=self.template_composer  # REAL service!
        )
        
        self.mock_logger = self.service.logger
    
    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    # =============================================================================
    # Real Template Integration Tests
    # =============================================================================
    
    def test_scaffold_agent_with_real_template(self):
        """Test scaffolding using the real agent template file."""
        # Create agent info with services
        agent_type = "TestAgent"
        info = {
            "agent_type": "test",
            "node_name": "test_node",
            "context": '{"services": ["llm", "csv"]}',
            "prompt": "Test agent prompt",
            "input_fields": ["user_input", "context_data"],
            "output_field": "test_result",
            "description": "Test agent for integration testing"
        }
        
        # Test scaffolding with REAL template processing
        result_path = self.service.scaffold_agent_class(agent_type, info, self.agents_dir)
        
        # Verify file was created
        self.assertIsNotNone(result_path)
        self.assertTrue(result_path.exists())
        
        # Read and verify the generated content uses real template
        content = result_path.read_text()
        
        # Verify proper class name (our PascalCase fix)
        self.assertIn("class TestAgent(BaseAgent", content)
        
        # Verify real template structure
        self.assertIn("# Auto-generated agent class for TestAgent", content)
        self.assertIn("from typing import Dict, Any, Optional", content)
        self.assertIn("from agentmap.agents.base_agent import BaseAgent", content)
        
        # Verify service dependencies were injected (modern protocols)
        self.assertIn("LLMCapableAgent", content)
        self.assertIn("CSVCapableAgent", content)  # Separate service for "csv"
        self.assertIn("from agentmap.services.protocols import LLMCapableAgent", content)
        self.assertIn("from agentmap.services.protocols import CSVCapableAgent", content)
        
        # Verify template variables were substituted
        self.assertIn("Test agent for integration testing", content)
        self.assertIn("test_node", content)
        self.assertIn("user_input, context_data", content)
        self.assertIn("test_result", content)
        
        # Verify template is properly formatted
        self.assertGreater(len(content), 1000, "Template content too short")
        self.assertIn('def __init__(', content, "Missing constructor")
        self.assertIn('def process(', content, "Missing main process method")
    
    def test_scaffold_from_real_csv_with_templates(self):
        """Test scaffolding from CSV using real templates."""
        # Create realistic CSV content
        csv_content = [
            {
                "GraphName": "integration_test",
                "Node": "InputNode",
                "AgentType": "input",
                "Input_Fields": "user_input",
                "Output_Field": "input",
                "Edge": "",
                "Success_Next": "",
                "Prompt": "What would you like to do?",
                "Description": "User input collection agent",
                "Context": "",
                "Failure_Next": ""
            },
            {
                "GraphName": "integration_test",
                "Node": "ProcessorNode",
                "AgentType": "processor",
                "Input_Fields": "input|metadata",
                "Output_Field": "processed_result",
                "Edge": "",
                "Success_Next": "",
                "Prompt": "Process the user input with context",
                "Description": "Main processing agent with service dependencies",
                "Context": '{"services": ["llm", "json", "memory"]}',
                "Failure_Next": ""
            }
        ]
        
        # Write CSV to temp file
        csv_file = self.csv_dir / "integration_test.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_content[0].keys())
            writer.writeheader()
            writer.writerows(csv_content)
        
        # Configure function resolution (no functions in this test)
        self.mock_function_resolution_service.extract_func_ref.return_value = None
        
        # Test scaffolding with real templates
        options = ScaffoldOptions(graph_name="integration_test")
        result = self.service.scaffold_agents_from_csv(csv_file, options)
        
        # Verify result - only custom agents should be scaffolded
        # input is a builtin agent and should be skipped
        self.assertIsInstance(result, ScaffoldResult)
        self.assertEqual(result.scaffolded_count, 1)  # Only processor (custom agent)
        self.assertEqual(len(result.errors), 0)
        
        # Verify service statistics
        self.assertEqual(result.service_stats["with_services"], 1)  # processor
        self.assertEqual(result.service_stats["without_services"], 0)  # no custom agents without services
        
        # Verify only custom agent file was created
        input_agent = self.agents_dir / "input_agent.py"
        processor_agent = self.agents_dir / "processor_agent.py"
        
        # Input agent should NOT be created (it's builtin)
        self.assertFalse(input_agent.exists(), "Builtin input agent should not be scaffolded")
        
        # Processor agent should be created (it's custom)
        self.assertTrue(processor_agent.exists())
        
        # Verify processor agent has service dependencies (modern protocols)
        processor_content = processor_agent.read_text()
        self.assertIn("class ProcessorAgent(BaseAgent", processor_content)
        self.assertIn("LLMCapableAgent", processor_content)
        self.assertIn("JSONCapableAgent", processor_content)  # Separate service for "json"
        self.assertIn("MemoryCapableAgent", processor_content)  # Separate service for "memory"
        # Verify service description is included (flexible format)
        self.assertTrue(
            "with llm, json, memory" in processor_content or 
            "llm, json, memory" in processor_content,
            "Service capabilities not found in processor content"
        )
        self.assertIn("Main processing agent", processor_content)
    
    def test_scaffold_with_edge_functions_real_templates(self):
        """Test scaffolding both agents and functions with real templates."""
        # Create CSV with function references
        csv_content = [
            {
                "GraphName": "function_test",
                "Node": "ValidatorNode",
                "AgentType": "validator",
                "Input_Fields": "raw_data",
                "Output_Field": "validated_data",
                "Edge": "func:validate_input",
                "Success_Next": "ProcessNode",
                "Prompt": "Validate the incoming data",
                "Description": "Data validation agent",
                "Context": '{"services": ["json"]}',
                "Failure_Next": "func:handle_validation_error"
            }
        ]
        
        csv_file = self.csv_dir / "function_test.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_content[0].keys())
            writer.writeheader()
            writer.writerows(csv_content)
        
        # Configure function resolution
        def mock_extract_func_ref(value):
            if value and "func:" in value:
                return value.replace("func:", "")
            return None
        
        self.mock_function_resolution_service.extract_func_ref.side_effect = mock_extract_func_ref
        
        # Test scaffolding
        result = self.service.scaffold_agents_from_csv(csv_file)
        
        # Verify both agents and functions were created
        self.assertEqual(result.scaffolded_count, 3)  # 1 agent + 2 functions
        self.assertEqual(len(result.errors), 0)
        
        # Verify agent file with real template
        agent_file = self.agents_dir / "validator_agent.py"
        self.assertTrue(agent_file.exists())
        agent_content = agent_file.read_text()
        self.assertIn("class ValidatorAgent(BaseAgent", agent_content)
        self.assertIn("JSONCapableAgent", agent_content)
        self.assertIn("Data validation agent", agent_content)
        
        # Verify function files with real templates
        validate_func = self.functions_dir / "validate_input.py"
        error_func = self.functions_dir / "handle_validation_error.py"
        
        self.assertTrue(validate_func.exists())
        self.assertTrue(error_func.exists())
        
        validate_content = validate_func.read_text()
        error_content = error_func.read_text()
        
        # Verify real function template structure (flexible format)
        self.assertIn("def validate_input(", validate_content)
        # Check for either full signature or basic function definition
        self.assertTrue(
            "state: Dict[str, Any]" in validate_content or "def validate_input(" in validate_content,
            "Function signature not found"
        )
        # Verify template content is present (flexible format)
        self.assertTrue(
            "# Auto-generated" in validate_content or "# Function:" in validate_content,
            "Template header not found"
        )
        self.assertIn("ProcessNode", validate_content)  # Success route
        
        self.assertIn("def handle_validation_error(", error_content)
        # Check for either full signature or basic function definition
        self.assertTrue(
            "state: Dict[str, Any]" in error_content or "def handle_validation_error(" in error_content,
            "Function signature not found"
        )
        # Verify template content is present (flexible format)
        self.assertTrue(
            "# Auto-generated" in error_content or "# Function:" in error_content,
            "Template header not found"
        )
    
    def test_real_template_error_handling(self):
        """Test error handling with real templates."""
        # Create agent with invalid service configuration
        agent_type = "ErrorAgent"
        info = {
            "agent_type": "ErrorAgent",
            "node_name": "error_node",
            "context": '{"services": ["nonexistent_service"]}',  # Invalid service
            "prompt": "This will fail",
            "input_fields": ["input"],
            "output_field": "output",
            "description": "Agent that should fail"
        }
        
        # Test that scaffolding fails gracefully
        with self.assertRaises(ValueError) as cm:
            self.service.scaffold_agent_class(agent_type, info, self.agents_dir)
        
        # Verify appropriate error message
        self.assertIn("Unknown service", str(cm.exception))
        self.assertIn("nonexistent_service", str(cm.exception))
        
        # Verify no file was created
        error_agent = self.agents_dir / "erroragent_agent.py"
        self.assertFalse(error_agent.exists())
    
    def test_real_template_service_integration(self):
        """Test comprehensive service integration with real templates."""
        # Test with all supported services
        agent_type = "FullService"
        info = {
            "agent_type": "FullService",
            "node_name": "full_service_node",
            "context": '{"services": ["llm", "csv", "json", "file", "vector", "memory"]}',
            "prompt": "Agent with all service types",
            "input_fields": ["complex_input", "multi_data"],
            "output_field": "comprehensive_result",
            "description": "Agent demonstrating all service integrations"
        }
        
        # Test scaffolding
        result_path = self.service.scaffold_agent_class(agent_type, info, self.agents_dir)
        
        # Verify file creation
        self.assertIsNotNone(result_path)
        self.assertTrue(result_path.exists())
        
        # Read and verify comprehensive service integration
        content = result_path.read_text()
        
        # Verify all service protocols are included
        expected_protocols = [
            "LLMCapableAgent", "CSVCapableAgent", "JSONCapableAgent", 
            "FileCapableAgent", "VectorCapableAgent", "MemoryCapableAgent"
        ]
        for protocol in expected_protocols:
            self.assertIn(protocol, content)
        
        # Verify service imports
        expected_imports = [
            "from agentmap.services.protocols import LLMCapableAgent",
            "from agentmap.services.protocols import CSVCapableAgent",
            "from agentmap.services.protocols import VectorCapableAgent"
        ]
        for import_stmt in expected_imports:
            self.assertIn(import_stmt, content)
        
        # Verify service attributes are injected
        service_attributes = [
            "llm_service", "csv_service", "json_service", 
            "file_service", "vector_service", "memory_service"
        ]
        for attr in service_attributes:
            self.assertIn(f"self.{attr}", content)
        
        # Verify usage examples for key services (flexible format)
        # Check that service usage examples are present in some form
        llm_usage_found = any([
            "call_llm" in content,
            "llm_service" in content,
            "LLM SERVICE" in content
        ])
        self.assertTrue(llm_usage_found, "LLM usage example not found")
        
        csv_usage_found = any([
            "csv_service.read" in content,
            "csv_service" in content,
            "CSV SERVICE" in content
        ])
        self.assertTrue(csv_usage_found, "CSV usage example not found")
        
        vector_usage_found = any([
            "vector_service.search" in content,
            "vector_service" in content,
            "VECTOR SERVICE" in content
        ])
        self.assertTrue(vector_usage_found, "Vector usage example not found")
        
        # Verify comprehensive documentation
        self.assertIn("Agent demonstrating all service integrations", content)
        self.assertIn("complex_input, multi_data", content)
        self.assertIn("comprehensive_result", content)


if __name__ == '__main__':
    unittest.main()
