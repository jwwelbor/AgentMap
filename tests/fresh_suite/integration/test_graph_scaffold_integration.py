"""
Additional integration tests for GraphScaffoldService.

These tests complement the existing unit tests by focusing on:
1. Real CSV file processing
2. Actual template file integration  
3. File system operations
4. Service dependency verification
5. CLI workflow integration

Note: These tests follow established patterns from TESTING_PATTERNS.md
"""

import unittest
import tempfile
import shutil
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from typing import Dict, Any
import csv
import json

from agentmap.services.graph_scaffold_service import (
    GraphScaffoldService, 
    ScaffoldOptions,
    ScaffoldResult
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphScaffoldServiceIntegration(unittest.TestCase):
    """Integration tests for GraphScaffoldService with real file operations."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies and temp directories."""
        # Create temporary directories for test files
        self.temp_dir = Path(tempfile.mkdtemp())
        self.agents_dir = self.temp_dir / "custom_agents"
        self.functions_dir = self.temp_dir / "custom_functions"
        self.csv_dir = self.temp_dir / "graphs"
        
        # Create directories
        self.agents_dir.mkdir(parents=True)
        self.functions_dir.mkdir(parents=True)
        self.csv_dir.mkdir(parents=True)
        
        # Create mock services using MockServiceFactory
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "custom_agents_path": str(self.agents_dir),
            "functions_path": str(self.functions_dir),
            "csv_path": str(self.csv_dir / "test.csv")
        })
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Create mock agent registry service
        self.mock_agent_registry_service = MockServiceFactory.create_mock_agent_registry_service()
        
        # Use REAL PromptManagerService for integration testing
        from agentmap.services.prompt_manager_service import PromptManagerService
        self.prompt_manager_service = PromptManagerService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service
        )
        
        self.mock_function_resolution_service = Mock()
        
        # Configure path methods for integration tests
        self.mock_app_config_service.get_custom_agents_path.return_value = self.agents_dir
        self.mock_app_config_service.get_functions_path.return_value = self.functions_dir
        
        # Configure path properties
        self.mock_app_config_service.custom_agents_path = self.agents_dir
        self.mock_app_config_service.functions_path = self.functions_dir
        self.mock_app_config_service.csv_path = self.csv_dir / "test.csv"
        
        # Initialize service
        self.service = GraphScaffoldService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            prompt_manager=self.prompt_manager_service,  # Use real PromptManagerService
            function_resolution_service=self.mock_function_resolution_service,
            agent_registry_service=self.mock_agent_registry_service
        )
        
        self.mock_logger = self.service.logger
    
    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    # =============================================================================
    # 1. Real CSV Processing Integration Tests
    # =============================================================================
    
    def test_scaffold_from_real_gm_orchestration_csv(self):
        """Test scaffolding using GM orchestration CSV structure."""
        # Create realistic CSV content matching gm_orchestration_2.csv structure
        csv_content = [
            {
                "GraphName": "gm_orchestration",
                "Node": "UserInput",
                "AgentType": "input",
                "Input_Fields": "input",
                "Output_Field": "input",
                "Edge": "Orchestrator",
                "Success_Next": "",
                "Prompt": "What do you want to do?",
                "Description": "This is to simulate user input",
                "Context": "",
                "Failure_Next": ""
            },
            {
                "GraphName": "gm_orchestration", 
                "Node": "Orchestrator",
                "AgentType": "orchestrator",
                "Input_Fields": "input",
                "Output_Field": "orchestrator_result",
                "Edge": "",
                "Success_Next": "",
                "Prompt": "",
                "Description": "This is the main orchestration node that routes the player's input",
                "Context": '{"services": ["llm", "node_registry"]}',
                "Failure_Next": "ErrorHandler"
            },
            {
                "GraphName": "gm_orchestration",
                "Node": "CombatTurn", 
                "AgentType": "combat_router",
                "Input_Fields": "input",
                "Output_Field": "combat_result",
                "Edge": "UserInput",
                "Success_Next": "",
                "Prompt": "##NOLLM Route input to the combat resolution graph",
                "Description": "Triggered when player initiates combat",
                "Context": '{"services": ["csv", "memory"]}',
                "Failure_Next": ""
            }
        ]
        
        # Write CSV to temp file
        csv_file = self.csv_dir / "gm_orchestration.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_content[0].keys())
            writer.writeheader()
            writer.writerows(csv_content)
        
        # Configure function resolution (no functions in this CSV)
        self.mock_function_resolution_service.extract_func_ref.return_value = None
        
        # Configure realistic template responses
        def create_agent_template(agent_type, services):
            return f"""# Auto-generated agent class for {agent_type}
from typing import Dict, Any, Optional
from agentmap.agents.base_agent import BaseAgent

class {agent_type.title()}Agent(BaseAgent):
    \"\"\"Agent for {agent_type} with {services} capabilities.\"\"\"
    
    def __init__(self):
        super().__init__()
        # Services will be injected during graph building
        
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Implement {agent_type} logic here
        return {{"processed": True, "agent_type": "{agent_type}"}}
"""
        
        def mock_format_prompt(template_path, variables):
            agent_type = variables.get("agent_type", "unknown")
            services = ", ".join(variables.get("service_description", "").split(" with ")[1:] if " with " in variables.get("service_description", "") else [])
            return create_agent_template(agent_type, services)
        
        self.prompt_manager_service.format_prompt = Mock(side_effect=mock_format_prompt)
        
        # Test scaffolding
        options = ScaffoldOptions(graph_name="gm_orchestration")
        result = self.service.scaffold_agents_from_csv(csv_file, options)
        
        # Verify result - Only custom agents should be scaffolded
        # input and orchestrator are builtin agents and should be skipped
        self.assertIsInstance(result, ScaffoldResult)
        self.assertEqual(result.scaffolded_count, 1)  # Only combat_router (custom agent)
        self.assertEqual(len(result.errors), 0)
        
        # Verify service statistics
        self.assertEqual(result.service_stats["with_services"], 1)  # combat_router
        self.assertEqual(result.service_stats["without_services"], 0)  # no agents without services
        
        # Verify only custom agent file was created
        expected_files = [
            self.agents_dir / "combat_router_agent.py"  # Only custom agent
        ]
        
        # Verify builtin agents were NOT scaffolded
        builtin_files = [
            self.agents_dir / "input_agent.py",
            self.agents_dir / "orchestrator_agent.py"
        ]
        
        for file_path in expected_files:
            self.assertTrue(file_path.exists(), f"Expected file not created: {file_path}")
            
            # Verify file has content
            content = file_path.read_text()
            self.assertIn("class", content)
            self.assertIn("Agent", content)
            self.assertIn("def run", content)
        
        # Verify builtin agent files were NOT created
        for file_path in builtin_files:
            self.assertFalse(file_path.exists(), f"Builtin agent file should not be created: {file_path}")
    
    def test_scaffold_with_edge_functions_from_csv(self):
        """Test scaffolding that creates both agents and edge functions."""
        # Create CSV with function references
        csv_content = [
            {
                "GraphName": "test_workflow",
                "Node": "ProcessNode",
                "AgentType": "processor",
                "Input_Fields": "data",
                "Output_Field": "processed_data",
                "Edge": "func:validate_data",
                "Success_Next": "NextNode",
                "Prompt": "Process the data",
                "Description": "Data processing node",
                "Context": '{"services": ["json", "file"]}',
                "Failure_Next": "func:handle_error"
            }
        ]
        
        csv_file = self.csv_dir / "workflow.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_content[0].keys())
            writer.writeheader()
            writer.writerows(csv_content)
        
        # Configure function resolution to extract function names
        def mock_extract_func_ref(value):
            if value and "func:" in value:
                return value.replace("func:", "")
            return None
        
        self.mock_function_resolution_service.extract_func_ref.side_effect = mock_extract_func_ref
        
        # Configure template responses for both agents and functions
        def mock_format_prompt(template_path, variables):
            if "agent_template" in template_path:
                agent_type = variables.get("agent_type", "unknown")
                return f"""# Agent class for {agent_type}
class {agent_type.title()}Agent(BaseAgent):
    def run(self, state): return {{"processed": True}}
"""
            elif "function_template" in template_path:
                func_name = variables.get("func_name", "unknown")
                return f"""# Edge function for {func_name}
def {func_name}(state):
    return "success" if not state.get("error") else "failure"
"""
            return "# Unknown template"
        
        self.prompt_manager_service.format_prompt = Mock(side_effect=mock_format_prompt)
        
        # Test scaffolding
        result = self.service.scaffold_agents_from_csv(csv_file)
        
        # Verify both agents and functions were created
        self.assertEqual(result.scaffolded_count, 3)  # 1 agent + 2 functions
        self.assertEqual(len(result.errors), 0)
        
        # Verify agent file
        agent_file = self.agents_dir / "processor_agent.py"
        self.assertTrue(agent_file.exists())
        content = agent_file.read_text()
        self.assertIn("ProcessorAgent", content)
        
        # Verify function files
        validate_func = self.functions_dir / "validate_data.py"
        error_func = self.functions_dir / "handle_error.py"
        
        self.assertTrue(validate_func.exists())
        self.assertTrue(error_func.exists())
        
        validate_content = validate_func.read_text()
        self.assertIn("def validate_data", validate_content)
        
        error_content = error_func.read_text()
        self.assertIn("def handle_error", error_content)
    
    # =============================================================================
    # 2. Template Integration and Service Dependency Tests
    # =============================================================================
    
    def test_agent_template_service_dependency_injection(self):
        """Test that generated agents have correct service dependencies configured."""
        # Create agent info with multiple services
        agent_type = "ServiceAgent"
        info = {
            "agent_type": "ServiceAgent",
            "node_name": "service_node",
            "context": '{"services": ["llm", "csv", "vector", "memory"]}',
            "prompt": "Multi-service agent prompt",
            "input_fields": ["user_input", "context_data"],
            "output_field": "processed_result",
            "description": "Agent that uses multiple services"
        }
        
        # Configure realistic template with service variables
        template_content = """# Auto-generated agent class for {agent_type}
from typing import Dict, Any, Optional{imports}
from agentmap.agents.base_agent import BaseAgent

{class_definition}
    \"\"\"
    {description}{service_description}
    
    Node: {node_name}
    Input Fields: {input_fields}
    Output Field: {output_field}{services_doc}
    \"\"\"
    
    def __init__(self):
        super().__init__(){service_attributes}
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            processed_inputs = self.process_inputs(state)
            
{input_field_access}
            
{service_usage_examples}
            
            result = {{
                "processed": True,
                "agent_type": "{agent_type}",
                "node": "{node_name}"
            }}
            
            if "{output_field}":
                result["{output_field}"] = "processed_value"
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in {class_name}: {{e}}")
            return {{"error": str(e)}}
"""
        
        self.prompt_manager_service.format_prompt = Mock(return_value=template_content)
        
        # Test agent scaffolding with real file creation (no mocking needed for integration test)
        result_path = self.service.scaffold_agent_class(agent_type, info, self.agents_dir)
        
        # Verify file was created
        self.assertIsNotNone(result_path)
        self.assertTrue(result_path.exists())
        
        # Verify template was called with correct service variables
        call_args = self.prompt_manager_service.format_prompt.call_args
        template_vars = call_args[0][1]
        
        # Verify service-related variables are present
        self.assertIn("LLMServiceUser", template_vars["class_definition"])
        self.assertIn("CSVServiceUser", template_vars["class_definition"])
        self.assertIn("VectorServiceUser", template_vars["class_definition"])
        self.assertIn("MemoryServiceUser", template_vars["class_definition"])
        
        # Verify service imports
        self.assertIn("from agentmap.services import LLMServiceUser", template_vars["imports"])
        self.assertIn("from agentmap.services import CSVServiceUser", template_vars["imports"])
        
        # Verify service attributes
        self.assertIn("llm_service", template_vars["service_attributes"])
        self.assertIn("csv_service", template_vars["service_attributes"])
        self.assertIn("vector_service", template_vars["service_attributes"])
        self.assertIn("memory_service", template_vars["service_attributes"])
        
        # Verify usage examples
        self.assertIn("LLM SERVICE:", template_vars["service_usage_examples"])
        self.assertIn("CSV SERVICE:", template_vars["service_usage_examples"])
        self.assertIn("call_llm", template_vars["service_usage_examples"])
        self.assertIn("csv_service.read", template_vars["service_usage_examples"])
    
    def test_template_variable_comprehensive_substitution(self):
        """Test that all template variables are properly substituted."""
        agent_type = "CompleteAgent"
        info = {
            "agent_type": "CompleteAgent",
            "node_name": "complete_node",
            "context": '{"services": ["llm", "json"]}',
            "prompt": "Complete processing prompt with details",
            "input_fields": ["field_a", "field_b", "field_c"],
            "output_field": "complete_result",
            "description": "Comprehensive agent for testing all template variables"
        }
        
        # Use a template that includes all possible variables
        comprehensive_template = """# Generated: {agent_type}
# Description: {description}
# Node: {node_name}
# Inputs: {input_fields}
# Output: {output_field}
# Context: {context}
# Service Description: {service_description}
# Class Definition: {class_definition}
# Imports: {imports}
# Service Attributes: {service_attributes}
# Input Access: {input_field_access}
# Service Usage: {service_usage_examples}
# Services Doc: {services_doc}
# Prompt Doc: {prompt_doc}
# Usage Examples Section: {usage_examples_section}
"""
        
        # Mock format_prompt to actually format the template
        def mock_format_prompt(template_path, variables):
            try:
                return comprehensive_template.format(**variables)
            except KeyError as e:
                # Handle missing variables gracefully for testing
                import string
                safe_template = string.Template(comprehensive_template.replace('{', '${').replace('}', '}'))
                return safe_template.safe_substitute(**variables)
        
        self.prompt_manager_service.format_prompt = Mock(side_effect=mock_format_prompt)
        
        # Test agent scaffolding with real file creation (no mocking needed for integration test)
        result_path = self.service.scaffold_agent_class(agent_type, info, self.agents_dir)
        
        # Read the generated file content
        self.assertTrue(result_path.exists())
        content = result_path.read_text()
        
        # Verify all variables were substituted (no {variable} patterns remain)
        import re
        unsubstituted_vars = re.findall(r'\{([^}]+)\}', content)
        
        # Filter out legitimate braces (like in f-strings)
        actual_unsubstituted = [var for var in unsubstituted_vars 
                              if not var.startswith(('e}', '"', "'"))]
        
        self.assertEqual(len(actual_unsubstituted), 0, 
                       f"Template variables not substituted: {actual_unsubstituted}")
        
        # Verify specific content is present
        self.assertIn("CompleteAgent", content)
        self.assertIn("complete_node", content)
        self.assertIn("field_a, field_b, field_c", content)
        self.assertIn("complete_result", content)
        self.assertIn("Comprehensive agent for testing", content)
    
    # =============================================================================
    # 3. File System Integration and Directory Management Tests
    # =============================================================================
    
    def test_scaffold_creates_directory_structure(self):
        """Test that scaffolding creates proper directory structure."""
        # Remove directories to test creation
        shutil.rmtree(self.agents_dir)
        shutil.rmtree(self.functions_dir)
        
        # Create CSV with both agents and functions
        csv_content = [
            {
                "GraphName": "structure_test",
                "Node": "TestNode",
                "AgentType": "test",
                "Input_Fields": "input",
                "Output_Field": "output",
                "Edge": "func:test_function",
                "Success_Next": "NextNode",
                "Prompt": "Test",
                "Description": "Test agent",
                "Context": "",
                "Failure_Next": ""
            }
        ]
        
        csv_file = self.csv_dir / "structure_test.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_content[0].keys())
            writer.writeheader()
            writer.writerows(csv_content)
        
        # Configure mocks
        self.mock_function_resolution_service.extract_func_ref.side_effect = lambda x: "test_function" if "func:" in x else None
        self.prompt_manager_service.format_prompt = Mock(return_value="# Generated content")
        
        # Test scaffolding
        result = self.service.scaffold_agents_from_csv(csv_file)
        
        # Verify directories were created
        self.assertTrue(self.agents_dir.exists())
        self.assertTrue(self.functions_dir.exists())
        self.assertTrue(self.agents_dir.is_dir())
        self.assertTrue(self.functions_dir.is_dir())
        
        # Verify files were created in correct directories
        agent_file = self.agents_dir / "test_agent.py"
        function_file = self.functions_dir / "test_function.py"
        
        self.assertTrue(agent_file.exists())
        self.assertTrue(function_file.exists())
        
        # Verify file permissions are readable/writable
        self.assertTrue(agent_file.is_file())
        self.assertTrue(function_file.is_file())
        
        # Verify content can be read
        agent_content = agent_file.read_text()
        function_content = function_file.read_text()
        
        self.assertIsInstance(agent_content, str)
        self.assertIsInstance(function_content, str)
        self.assertGreater(len(agent_content), 0)
        self.assertGreater(len(function_content), 0)
    
    def test_scaffold_handles_existing_files_correctly(self):
        """Test scaffolding behavior with existing files."""
        # Create existing agent file
        existing_agent = self.agents_dir / "existing_agent.py"
        existing_content = "# Existing agent content"
        existing_agent.write_text(existing_content)
        
        # Configure agent info
        agent_type = "existing"
        info = {
            "agent_type": "existing",
            "node_name": "test_node",
            "context": "",
            "prompt": "Test",
            "input_fields": [],
            "output_field": "result",
            "description": "Test existing agent"
        }
        
        # Test scaffolding with overwrite=False (default)
        result_path = self.service.scaffold_agent_class(agent_type, info, self.agents_dir)
        
        # Should return None (file not created)
        self.assertIsNone(result_path)
        
        # Original content should be preserved
        self.assertEqual(existing_agent.read_text(), existing_content)
        
        # Test with custom options and overwrite=True
        options = ScaffoldOptions(output_path=self.agents_dir, overwrite_existing=True)
        
        # Create CSV content
        csv_content = [
            {
                "GraphName": "overwrite_test",
                "Node": "ExistingNode",
                "AgentType": "existing",
                "Input_Fields": "input",
                "Output_Field": "output",
                "Edge": "",
                "Success_Next": "",
                "Prompt": "Overwrite test",
                "Description": "Test overwrite",
                "Context": "",
                "Failure_Next": ""
            }
        ]
        
        csv_file = self.csv_dir / "overwrite.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_content[0].keys())
            writer.writeheader()
            writer.writerows(csv_content)
        
        self.mock_function_resolution_service.extract_func_ref.return_value = None
        self.prompt_manager_service.format_prompt = Mock(return_value="# New generated content")
        
        result = self.service.scaffold_agents_from_csv(csv_file, options)
        
        # Should have overwritten the file
        self.assertEqual(result.scaffolded_count, 1)
        self.assertEqual(len(result.skipped_files), 0)
        
        # Content should be updated
        new_content = existing_agent.read_text()
        self.assertNotEqual(new_content, existing_content)
        self.assertIn("New generated content", new_content)
    
    # =============================================================================
    # 4. Error Handling and Recovery Integration Tests
    # =============================================================================
    
    def test_scaffold_partial_failure_recovery(self):
        """Test scaffolding continues after partial failures."""
        # Create CSV with multiple agents, one will fail
        csv_content = [
            {
                "GraphName": "recovery_test",
                "Node": "GoodNode",
                "AgentType": "good",
                "Input_Fields": "input",
                "Output_Field": "output",
                "Edge": "",
                "Success_Next": "",
                "Prompt": "Good agent",
                "Description": "This agent will succeed",
                "Context": "",
                "Failure_Next": ""
            },
            {
                "GraphName": "recovery_test",
                "Node": "BadNode", 
                "AgentType": "bad",
                "Input_Fields": "input",
                "Output_Field": "output",
                "Edge": "",
                "Success_Next": "",
                "Prompt": "Bad agent",
                "Description": "This agent will fail",
                "Context": '{"services": ["invalid_service"]}',  # This will cause failure
                "Failure_Next": ""
            },
            {
                "GraphName": "recovery_test",
                "Node": "AnotherGoodNode",
                "AgentType": "good2", 
                "Input_Fields": "input",
                "Output_Field": "output",
                "Edge": "",
                "Success_Next": "",
                "Prompt": "Another good agent",
                "Description": "This agent will also succeed",
                "Context": "",
                "Failure_Next": ""
            }
        ]
        
        csv_file = self.csv_dir / "recovery_test.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_content[0].keys())
            writer.writeheader()
            writer.writerows(csv_content)
        
        # Configure function resolution
        self.mock_function_resolution_service.extract_func_ref.return_value = None
        
        # Configure template response
        self.prompt_manager_service.format_prompt = Mock(return_value="# Generated agent")
        
        # Test scaffolding
        result = self.service.scaffold_agents_from_csv(csv_file)
        
        # Should have partial success
        self.assertEqual(result.scaffolded_count, 2)  # good and good2 agents
        self.assertEqual(len(result.errors), 1)  # bad agent failed
        
        # Verify error message contains information about the failure
        error_msg = result.errors[0]
        self.assertIn("bad", error_msg.lower())
        self.assertIn("invalid_service", error_msg)
        
        # Verify successful files were created
        good_agent = self.agents_dir / "good_agent.py"
        good2_agent = self.agents_dir / "good2_agent.py"
        bad_agent = self.agents_dir / "bad_agent.py"
        
        self.assertTrue(good_agent.exists())
        self.assertTrue(good2_agent.exists())
        self.assertFalse(bad_agent.exists())  # Failed agent should not create file


if __name__ == '__main__':
    unittest.main()
