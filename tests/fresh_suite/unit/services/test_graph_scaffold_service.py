"""
Unit tests for GraphScaffoldService.

These tests validate the GraphScaffoldService using pure Mock objects
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from typing import Dict, Any
import json

from agentmap.services.graph_scaffold_service import (
    GraphScaffoldService, 
    ServiceRequirementParser,
    ScaffoldOptions,
    ScaffoldResult,
    ServiceRequirements,
    ServiceAttribute
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphScaffoldService(unittest.TestCase):
    """Unit tests for GraphScaffoldService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create all mock services using MockServiceFactory
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "custom_agents_path": "agentmap/custom_agents",
            "functions_path": "agentmap/custom_functions",
            "csv_path": "graphs/test.csv"
        })
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_prompt_manager_service = Mock()
        self.mock_function_resolution_service = Mock()
        self.mock_agent_registry_service = MockServiceFactory.create_mock_agent_registry_service()
        
        # Configure prompt manager mock
        self.mock_prompt_manager_service.format_prompt.return_value = "# Mock formatted template\nclass MockAgent:\n    pass"
        
        # Configure function resolution service mock
        self.mock_function_resolution_service.extract_func_ref.return_value = "test_function"
        
        # Configure agent registry service mock (assume all agents need scaffolding)
        self.mock_agent_registry_service.has_agent.return_value = False
        
        # Configure additional path methods that get_service_info() uses
        self.mock_app_config_service.get_custom_agents_path.return_value = Path("agentmap/custom_agents")
        self.mock_app_config_service.get_functions_path.return_value = Path("agentmap/custom_functions")
        
        # Configure path properties that get_service_info() accesses directly
        self.mock_app_config_service.custom_agents_path = Path("agentmap/custom_agents")
        self.mock_app_config_service.functions_path = Path("agentmap/custom_functions")
        self.mock_app_config_service.csv_path = Path("graphs/test.csv")
        
        # Initialize GraphScaffoldService with mocked dependencies
        self.service = GraphScaffoldService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            prompt_manager=self.mock_prompt_manager_service,
            function_resolution_service=self.mock_function_resolution_service,
            agent_registry_service=self.mock_agent_registry_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.config, self.mock_app_config_service)
        self.assertEqual(self.service.prompt_manager, self.mock_prompt_manager_service)
        self.assertEqual(self.service.function_service, self.mock_function_resolution_service)
        self.assertEqual(self.service.agent_registry, self.mock_agent_registry_service)
        
        # Verify logger is configured
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, "GraphScaffoldService")
        
        # Verify service parser is initialized
        self.assertIsNotNone(self.service.service_parser)
        self.assertIsInstance(self.service.service_parser, ServiceRequirementParser)
        
        # Verify initialization log message
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[1] == "[GraphScaffoldService] Initialized" 
                          for call in logger_calls if call[0] == "info"))
    
    def test_get_service_info(self):
        """Test get_service_info() debug method."""
        # Act
        service_info = self.service.get_service_info()
        
        # Assert basic structure
        self.assertIsInstance(service_info, dict)
        self.assertEqual(service_info["service"], "GraphScaffoldService")
        self.assertTrue(service_info["config_available"])
        self.assertTrue(service_info["prompt_manager_available"])
        self.assertTrue(service_info["service_parser_available"])
        
        # Verify paths are properly configured (normalize for cross-platform compatibility)
        self.assertEqual(Path(service_info["custom_agents_path"]), Path("agentmap/custom_agents"))
        self.assertEqual(Path(service_info["functions_path"]), Path("agentmap/custom_functions"))
        self.assertEqual(Path(service_info["csv_path"]), Path("graphs/test.csv"))
        
        # Verify supported services list
        supported_services = service_info["supported_services"]
        expected_services = [
            "llm", "csv", "json", "file", "vector", "memory", 
            "node_registry", "storage"
        ]
        for service in expected_services:
            self.assertIn(service, supported_services)
        
        # Verify template files
        template_files = service_info["template_files"]
        self.assertIn("scaffold/agent_template.txt", template_files)
        self.assertIn("scaffold/function_template.txt", template_files)
    
    def test_get_scaffold_paths(self):
        """Test get_scaffold_paths() method."""
        # Act
        paths = self.service.get_scaffold_paths()
        
        # Assert
        self.assertIsInstance(paths, dict)
        self.assertEqual(paths["agents_path"], Path("agentmap/custom_agents"))
        self.assertEqual(paths["functions_path"], Path("agentmap/custom_functions"))
        self.assertEqual(paths["csv_path"], Path("graphs/test.csv"))
        
        # Test with graph name parameter (should be ignored)
        paths_with_graph = self.service.get_scaffold_paths("test_graph")
        self.assertEqual(paths, paths_with_graph)
    
    # =============================================================================
    # 2. Service Requirement Parser Tests
    # =============================================================================
    
    def test_service_requirement_parser_initialization(self):
        """Test ServiceRequirementParser initializes with correct mappings."""
        parser = ServiceRequirementParser()
        
        # Verify service protocol map exists
        self.assertIsInstance(parser.service_protocol_map, dict)
        
        # Verify all expected services are mapped
        expected_services = [
            "llm", "csv", "json", "file", "vector", "memory", 
            "node_registry", "storage"
        ]
        for service in expected_services:
            self.assertIn(service, parser.service_protocol_map)
            
            # Verify each service has required keys
            service_info = parser.service_protocol_map[service]
            required_keys = ["protocol", "import", "attribute", "type_hint", "doc"]
            for key in required_keys:
                self.assertIn(key, service_info)
    
    def test_parse_services_with_dict_context(self):
        """Test parse_services() with dictionary context."""
        parser = ServiceRequirementParser()
        
        # Test with dictionary containing services
        context = {"services": ["llm", "csv"]}
        result = parser.parse_services(context)
        
        # Verify result structure
        self.assertIsInstance(result, ServiceRequirements)
        self.assertEqual(result.services, ["llm", "csv"])
        self.assertEqual(len(result.protocols), 2)
        self.assertEqual(len(result.attributes), 2)
        
        # Verify LLM service mapping
        llm_attr = next(attr for attr in result.attributes if attr.name == "llm_service")
        self.assertEqual(llm_attr.type_hint, "'LLMService'")
        self.assertIn("LLM service", llm_attr.documentation)
        
        # Verify CSV service mapping
        csv_attr = next(attr for attr in result.attributes if attr.name == "csv_service")
        self.assertEqual(csv_attr.type_hint, "'CSVStorageService'")
        self.assertIn("CSV storage service", csv_attr.documentation)
    
    def test_parse_services_with_json_string_context(self):
        """Test parse_services() with JSON string context."""
        parser = ServiceRequirementParser()
        
        # Test with JSON string
        context = '{"services": ["vector", "memory"]}'
        result = parser.parse_services(context)
        
        # Verify parsing
        self.assertEqual(result.services, ["vector", "memory"])
        self.assertEqual(len(result.protocols), 2)
        
        # Verify vector service mapping
        vector_attr = next(attr for attr in result.attributes if attr.name == "vector_service")
        self.assertEqual(vector_attr.type_hint, "'VectorStorageService'")
    
    def test_parse_services_with_key_value_string_context(self):
        """Test parse_services() with key:value string format."""
        parser = ServiceRequirementParser()
        
        # Test with key:value format
        context = "services: llm|json|file"
        result = parser.parse_services(context)
        
        # Verify parsing
        self.assertEqual(result.services, ["llm", "json", "file"])
        self.assertEqual(len(result.protocols), 3)
        self.assertEqual(len(result.attributes), 3)
    
    def test_parse_services_with_empty_context(self):
        """Test parse_services() with empty or None context."""
        parser = ServiceRequirementParser()
        
        # Test with None
        result = parser.parse_services(None)
        self.assertEqual(result.services, [])
        self.assertEqual(result.protocols, [])
        self.assertEqual(result.attributes, [])
        
        # Test with empty string
        result = parser.parse_services("")
        self.assertEqual(result.services, [])
        
        # Test with empty dict
        result = parser.parse_services({})
        self.assertEqual(result.services, [])
    
    def test_parse_services_with_invalid_service(self):
        """Test parse_services() with invalid service names."""
        parser = ServiceRequirementParser()
        
        # Test with invalid service
        context = {"services": ["llm", "invalid_service", "csv"]}
        
        with self.assertRaises(ValueError) as cm:
            parser.parse_services(context)
        
        self.assertIn("Unknown services: ['invalid_service']", str(cm.exception))
        self.assertIn("Available:", str(cm.exception))
    
    def test_service_usage_examples(self):
        """Test that usage examples are generated correctly."""
        parser = ServiceRequirementParser()
        
        # Test LLM usage example
        llm_example = parser._get_usage_example("llm")
        self.assertIn("llm_service", llm_example)
        self.assertIn("call_llm", llm_example)
        self.assertIn("provider", llm_example)
        
        # Test CSV usage example
        csv_example = parser._get_usage_example("csv")
        self.assertIn("csv_service", csv_example)
        self.assertIn("read", csv_example)
        self.assertIn("write", csv_example)
        
        # Test vector usage example
        vector_example = parser._get_usage_example("vector")
        self.assertIn("vector_service", vector_example)
        self.assertIn("collection", vector_example)
        self.assertIn("similar", vector_example)
        
        # Test unknown service
        unknown_example = parser._get_usage_example("unknown")
        self.assertIn("unknown service", unknown_example.lower())
        self.assertIn("TODO", unknown_example)
    
    # =============================================================================
    # 3. CSV Collection and Processing Tests
    # =============================================================================
    
    def test_collect_agent_info_from_csv(self):
        """Test _collect_agent_info() method."""
        # Create mock CSV content
        csv_content = [
            {
                "GraphName": "test_graph",
                "Node": "node1", 
                "AgentType": "TestAgent",
                "Context": '{"services": ["llm"]}',
                "Prompt": "Test prompt",
                "Input_Fields": "input1|input2",
                "Output_Field": "output1",
                "Description": "Test agent description"
            },
            {
                "GraphName": "test_graph",
                "Node": "node2",
                "AgentType": "AnotherAgent", 
                "Context": "",
                "Prompt": "Another prompt",
                "Input_Fields": "input3",
                "Output_Field": "output2",
                "Description": "Another agent description"
            }
        ]
        
        # Mock CSV reading
        with patch('csv.DictReader', return_value=csv_content), \
             patch('builtins.open', mock_open()):
            
            # Configure agent registry to indicate these agents need scaffolding
            self.mock_agent_registry_service.has_agent.return_value = False
                
            # Test method
            csv_path = Path("test.csv")
            agent_info = self.service._collect_agent_info(csv_path, "test_graph")
                
            # Verify results
            self.assertEqual(len(agent_info), 2)
            
            # Verify TestAgent info
            test_agent = agent_info["TestAgent"]
            self.assertEqual(test_agent["agent_type"], "TestAgent")
            self.assertEqual(test_agent["node_name"], "node1")
            self.assertEqual(test_agent["context"], '{"services": ["llm"]}')
            self.assertEqual(test_agent["prompt"], "Test prompt")
            self.assertEqual(test_agent["input_fields"], ["input1", "input2"])
            self.assertEqual(test_agent["output_field"], "output1")
            self.assertEqual(test_agent["description"], "Test agent description")
            
            # Verify AnotherAgent info
            another_agent = agent_info["AnotherAgent"]
            self.assertEqual(another_agent["agent_type"], "AnotherAgent")
            self.assertEqual(another_agent["input_fields"], ["input3"])
    
    def test_collect_agent_info_with_graph_filter(self):
        """Test _collect_agent_info() with graph name filtering."""
        # Create mock CSV content with multiple graphs
        csv_content = [
            {
                "GraphName": "graph1",
                "Node": "node1",
                "AgentType": "Agent1",
                "Context": "",
                "Prompt": "Prompt 1",
                "Input_Fields": "input1",
                "Output_Field": "output1",
                "Description": "Agent 1"
            },
            {
                "GraphName": "graph2", 
                "Node": "node2",
                "AgentType": "Agent2",
                "Context": "",
                "Prompt": "Prompt 2",
                "Input_Fields": "input2",
                "Output_Field": "output2", 
                "Description": "Agent 2"
            }
        ]
        
        with patch('csv.DictReader', return_value=csv_content), \
             patch('builtins.open', mock_open()):
            
            # Configure agent registry to indicate these agents need scaffolding
            self.mock_agent_registry_service.has_agent.return_value = False
            
            # Test filtering for graph1
            csv_path = Path("test.csv")
            agent_info = self.service._collect_agent_info(csv_path, "graph1")
            
            # Should only contain Agent1
            self.assertEqual(len(agent_info), 1)
            self.assertIn("Agent1", agent_info)
            self.assertNotIn("Agent2", agent_info)
    
    def test_collect_function_info_from_csv(self):
        """Test _collect_function_info() method."""
        # Configure function resolution service to return function names
        def mock_extract_func_ref(value):
            if "func:" in value:
                return value.replace("func:", "")
            return None
        
        self.mock_function_resolution_service.extract_func_ref.side_effect = mock_extract_func_ref
        
        # Create mock CSV content
        csv_content = [
            {
                "GraphName": "test_graph",
                "Node": "node1",
                "Edge": "func:process_data",
                "Success_Next": "node2",
                "Failure_Next": "func:handle_error",
                "Context": '{"services": ["csv"]}',
                "Input_Fields": "input1|input2",
                "Output_Field": "result",
                "Description": "Processing node"
            }
        ]
        
        with patch('csv.DictReader', return_value=csv_content), \
             patch('builtins.open', mock_open()):
            
            # Test method
            csv_path = Path("test.csv")
            func_info = self.service._collect_function_info(csv_path, "test_graph")
            
            # Verify results
            self.assertEqual(len(func_info), 2)  # process_data and handle_error
            
            # Verify process_data function info
            self.assertIn("process_data", func_info)
            process_info = func_info["process_data"]
            self.assertEqual(process_info["node_name"], "node1")
            self.assertEqual(process_info["context"], '{"services": ["csv"]}')
            self.assertEqual(process_info["input_fields"], ["input1", "input2"])
            self.assertEqual(process_info["output_field"], "result")
            self.assertEqual(process_info["success_next"], "node2")
            self.assertEqual(process_info["failure_next"], "func:handle_error")
            
            # Verify handle_error function info
            self.assertIn("handle_error", func_info)
    
    # =============================================================================
    # 4. Agent Scaffolding Tests
    # =============================================================================
    
    def test_scaffold_agent_class_success(self):
        """Test scaffold_agent_class() creates agent file successfully."""
        # Configure template formatting
        formatted_template = """# Generated Agent Class
class TestAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def run(self, **kwargs):
        return {}
"""
        self.mock_prompt_manager_service.format_prompt.return_value = formatted_template
        
        # Test data
        agent_type = "TestAgent"
        info = {
            "agent_type": "TestAgent",
            "node_name": "test_node",
            "context": '{"services": ["llm"]}',
            "prompt": "Test prompt",
            "input_fields": ["input1"],
            "output_field": "output1",
            "description": "Test agent"
        }
        
        # Mock file operations
        with patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.open', mock_open()) as mock_file:
            
            # Test method
            output_path = Path("custom/agents")
            result_path = self.service.scaffold_agent_class(agent_type, info, output_path)
            
            # Verify result
            expected_path = output_path / "testagent_agent.py"
            self.assertEqual(result_path, expected_path)
            
            # Verify file was written
            mock_file.assert_called_once()
            handle = mock_file.return_value.__enter__.return_value
            handle.write.assert_called_once_with(formatted_template)
            
            # Verify prompt manager was called with correct template
            self.mock_prompt_manager_service.format_prompt.assert_called_once()
            call_args = self.mock_prompt_manager_service.format_prompt.call_args
            self.assertEqual(call_args[0][0], "file:scaffold/agent_template.txt")
            
            # Verify template variables
            template_vars = call_args[0][1]
            self.assertEqual(template_vars["agent_type"], "TestAgent")
            self.assertEqual(template_vars["class_name"], "TestAgentAgent")
            self.assertIn("TestAgent", template_vars["class_definition"])
    
    def test_scaffold_agent_class_file_exists(self):
        """Test scaffold_agent_class() when file already exists."""
        # Mock file exists
        with patch('pathlib.Path.exists', return_value=True):
            
            # Test method
            agent_type = "ExistingAgent"
            info = {"agent_type": "ExistingAgent"}
            result_path = self.service.scaffold_agent_class(agent_type, info)
            
            # Should return None when file exists and overwrite=False
            self.assertIsNone(result_path)
            
            # Prompt manager should not be called
            self.mock_prompt_manager_service.format_prompt.assert_not_called()
    
    def test_scaffold_agent_with_services(self):
        """Test scaffolding agent with service dependencies."""
        # Configure template formatting
        self.mock_prompt_manager_service.format_prompt.return_value = "# Mock template with services"
        
        # Test data with services
        agent_type = "ServiceAgent"
        info = {
            "agent_type": "ServiceAgent",
            "node_name": "service_node",
            "context": '{"services": ["llm", "csv", "vector"]}',
            "prompt": "Service-enabled prompt",
            "input_fields": ["data"],
            "output_field": "processed_data",
            "description": "Agent with service dependencies"
        }
        
        with patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.open', mock_open()):
            
            # Test method
            result_path = self.service.scaffold_agent_class(agent_type, info)
            
            # Verify template variables included service information
            call_args = self.mock_prompt_manager_service.format_prompt.call_args
            template_vars = call_args[0][1]
            
            # Verify service-related variables
            self.assertIn("LLMServiceUser", template_vars["class_definition"])
            self.assertIn("CSVServiceUser", template_vars["class_definition"])
            self.assertIn("VectorServiceUser", template_vars["class_definition"])
            self.assertIn("llm, csv, vector", template_vars["service_description"])
            self.assertIn("llm_service", template_vars["service_attributes"])
            self.assertIn("csv_service", template_vars["service_attributes"])
            self.assertIn("vector_service", template_vars["service_attributes"])
    
    def test_scaffold_agent_template_variable_preparation(self):
        """Test _prepare_agent_template_variables() comprehensive variable preparation."""
        # Test data
        agent_type = "ComplexAgent"
        info = {
            "agent_type": "ComplexAgent",
            "node_name": "complex_node",
            "context": '{"services": ["llm", "json"]}',
            "prompt": "Complex processing prompt",
            "input_fields": ["input_a", "input_b", "input_c"],
            "output_field": "final_result",
            "description": "Complex agent with multiple inputs"
        }
        
        # Parse service requirements
        service_reqs = self.service.service_parser.parse_services(info.get("context"))
        
        # Test method
        template_vars = self.service._prepare_agent_template_variables(agent_type, info, service_reqs)
        
        # Verify basic variables
        self.assertEqual(template_vars["agent_type"], "ComplexAgent")
        self.assertEqual(template_vars["class_name"], "ComplexAgentAgent")
        self.assertEqual(template_vars["node_name"], "complex_node")
        self.assertEqual(template_vars["description"], "Complex agent with multiple inputs")
        
        # Verify service-related variables
        self.assertIn("LLMServiceUser", template_vars["class_definition"])
        self.assertIn("JSONServiceUser", template_vars["class_definition"])
        self.assertIn("llm, json", template_vars["service_description"])
        
        # Verify input field processing
        self.assertEqual(template_vars["input_fields"], "input_a, input_b, input_c")
        self.assertIn("input_a = processed_inputs.get", template_vars["input_field_access"])
        self.assertIn("input_b = processed_inputs.get", template_vars["input_field_access"])
        self.assertIn("input_c = processed_inputs.get", template_vars["input_field_access"])
        
        # Verify service usage examples
        self.assertIn("LLM SERVICE:", template_vars["service_usage_examples"])
        self.assertIn("JSON SERVICE:", template_vars["service_usage_examples"])
    
    # =============================================================================
    # 5. Function Scaffolding Tests
    # =============================================================================
    
    def test_scaffold_edge_function_success(self):
        """Test scaffold_edge_function() creates function file successfully."""
        # Configure template formatting
        formatted_template = """# Generated Edge Function
def test_function(state):
    \"\"\"Test function description.\"\"\"
    return state
"""
        self.mock_prompt_manager_service.format_prompt.return_value = formatted_template
        
        # Test data
        func_name = "test_function"
        info = {
            "node_name": "test_node",
            "context": "Process test data",
            "input_fields": ["input1", "input2"],
            "output_field": "result",
            "success_next": "next_node",
            "failure_next": "error_node",
            "description": "Test function description"
        }
        
        # Mock file operations
        with patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.open', mock_open()) as mock_file:
            
            # Test method
            func_path = Path("custom/functions")
            result_path = self.service.scaffold_edge_function(func_name, info, func_path)
            
            # Verify result
            expected_path = func_path / "test_function.py"
            self.assertEqual(result_path, expected_path)
            
            # Verify file was written
            mock_file.assert_called_once()
            handle = mock_file.return_value.__enter__.return_value
            handle.write.assert_called_once_with(formatted_template)
            
            # Verify template variables
            call_args = self.mock_prompt_manager_service.format_prompt.call_args
            self.assertEqual(call_args[0][0], "file:scaffold/function_template.txt")
            
            template_vars = call_args[0][1]
            self.assertEqual(template_vars["func_name"], "test_function")
            self.assertEqual(template_vars["context"], "Process test data")
            self.assertEqual(template_vars["success_node"], "next_node")
            self.assertEqual(template_vars["failure_node"], "error_node")
            self.assertEqual(template_vars["node_name"], "test_node")
            self.assertEqual(template_vars["description"], "Test function description")
    
    def test_scaffold_edge_function_file_exists(self):
        """Test scaffold_edge_function() when file already exists."""
        # Mock file exists
        with patch('pathlib.Path.exists', return_value=True):
            
            # Test method
            func_name = "existing_function"
            info = {"node_name": "test"}
            result_path = self.service.scaffold_edge_function(func_name, info)
            
            # Should return None when file exists and overwrite=False
            self.assertIsNone(result_path)
            
            # Prompt manager should not be called
            self.mock_prompt_manager_service.format_prompt.assert_not_called()
    
    def test_generate_context_fields(self):
        """Test _generate_context_fields() method."""
        # Test with input and output fields
        input_fields = ["field1", "field2", "field3"]
        output_field = "result"
        
        context_fields = self.service._generate_context_fields(input_fields, output_field)
        
        # Verify format
        lines = context_fields.split('\n')
        self.assertEqual(len(lines), 4)  # 3 inputs + 1 output
        self.assertIn("field1: Input from previous node", lines[0])
        self.assertIn("field2: Input from previous node", lines[1])
        self.assertIn("field3: Input from previous node", lines[2])
        self.assertIn("result: Expected output to generate", lines[3])
        
        # Test with no fields
        empty_context = self.service._generate_context_fields([], "")
        self.assertIn("No specific fields defined", empty_context)
        
        # Test with only input fields
        input_only = self.service._generate_context_fields(["input1"], "")
        lines = input_only.split('\n')
        self.assertEqual(len(lines), 1)
        self.assertIn("input1: Input from previous node", lines[0])
    
    # =============================================================================
    # 6. Full CSV Scaffolding Tests
    # =============================================================================
    
    def test_scaffold_agents_from_csv_success(self):
        """Test scaffold_agents_from_csv() full workflow success."""
        # Mock CSV content
        csv_content = [
            {
                "GraphName": "test_graph",
                "Node": "node1",
                "AgentType": "TestAgent",
                "Context": '{"services": ["llm"]}',
                "Prompt": "Test prompt",
                "Input_Fields": "input1",
                "Output_Field": "output1",
                "Description": "Test agent",
                "Edge": "func:process_data",
                "Success_Next": "node2",
                "Failure_Next": "error_node"
            }
        ]
        
        # Configure function resolution
        def mock_extract_func_ref(value):
            if "func:" in value:
                return value.replace("func:", "")
            return None
        
        self.mock_function_resolution_service.extract_func_ref.side_effect = mock_extract_func_ref
        
        # Configure template formatting
        self.mock_prompt_manager_service.format_prompt.return_value = "# Mock template"
        
        # Configure app config paths
        self.mock_app_config_service.get_custom_agents_path.return_value = Path("custom/agents")
        self.mock_app_config_service.get_functions_path.return_value = Path("custom/functions")
        
        with patch('csv.DictReader', return_value=csv_content), \
             patch('builtins.open', mock_open()), \
             patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.open', mock_open()):
            
            # Configure agent registry to indicate this agent needs scaffolding
            self.mock_agent_registry_service.has_agent.return_value = False
            
            # Test method
            csv_path = Path("test.csv")
            options = ScaffoldOptions(graph_name="test_graph")
            result = self.service.scaffold_agents_from_csv(csv_path, options)
            
            # Verify result
            self.assertIsInstance(result, ScaffoldResult)
            self.assertEqual(result.scaffolded_count, 2)  # 1 agent + 1 function
            self.assertEqual(len(result.created_files), 2)
            self.assertEqual(len(result.errors), 0)
            
            # Verify service statistics
            self.assertEqual(result.service_stats["with_services"], 1)
            self.assertEqual(result.service_stats["without_services"], 0)
            
            # Verify directories were created
            self.mock_app_config_service.get_custom_agents_path.assert_called_once()
            self.mock_app_config_service.get_functions_path.assert_called_once()
    
    def test_scaffold_agents_from_csv_with_defaults(self):
        """Test scaffold_agents_from_csv() with default options."""
        # Mock empty CSV (no agents/functions to scaffold)
        csv_content = []
        
        with patch('csv.DictReader', return_value=csv_content), \
             patch('builtins.open', mock_open()), \
             patch('pathlib.Path.mkdir'):
            
            # Test with None options
            csv_path = Path("empty.csv")
            result = self.service.scaffold_agents_from_csv(csv_path, options=None)
            
            # Verify default options were used
            self.assertIsInstance(result, ScaffoldResult)
            self.assertEqual(result.scaffolded_count, 0)
            self.assertEqual(len(result.errors), 0)
    
    def test_scaffold_agents_from_csv_with_errors(self):
        """Test scaffold_agents_from_csv() handles errors gracefully."""
        # Mock CSV content that will cause an error
        csv_content = [
            {
                "GraphName": "test_graph",
                "Node": "node1",
                "AgentType": "ProblematicAgent",
                "Context": "",
                "Prompt": "Test prompt",
                "Input_Fields": "",
                "Output_Field": "",
                "Description": "",
                "Edge": "",  # Explicitly add empty function fields
                "Success_Next": "",
                "Failure_Next": ""
            }
        ]
        
        # Configure function resolution to return None for empty strings
        def mock_extract_func_ref(value):
            if value and "func:" in value:
                return value.replace("func:", "")
            return None  # Return None for empty or non-function values
        
        self.mock_function_resolution_service.extract_func_ref.side_effect = mock_extract_func_ref
        
        # Configure prompt manager to raise exception
        self.mock_prompt_manager_service.format_prompt.side_effect = Exception("Template error")
        
        with patch('csv.DictReader', return_value=csv_content), \
             patch('builtins.open', mock_open()), \
             patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.mkdir'):
            
            # Configure agent registry to indicate this agent needs scaffolding
            self.mock_agent_registry_service.has_agent.return_value = False
            
            # Test method
            csv_path = Path("problematic.csv")
            result = self.service.scaffold_agents_from_csv(csv_path)
            
            # Verify errors were captured - should only be 1 error from agent scaffolding
            self.assertEqual(result.scaffolded_count, 0)
            self.assertEqual(len(result.errors), 1)
            self.assertIn("Template error", result.errors[0])
            
            # Verify error logging
            logger_calls = self.mock_logger.calls
            error_calls = [call for call in logger_calls if call[0] == "error"]
            self.assertTrue(len(error_calls) > 0)
    
    def test_scaffold_agents_from_csv_file_exception(self):
        """Test scaffold_agents_from_csv() handles file access exceptions."""
        # Mock file access error
        with patch('builtins.open', side_effect=FileNotFoundError("CSV file not found")):
            
            # Test method
            csv_path = Path("missing.csv")
            result = self.service.scaffold_agents_from_csv(csv_path)
            
            # Verify error result
            self.assertEqual(result.scaffolded_count, 0)
            self.assertEqual(len(result.errors), 1)
            self.assertIn("CSV file not found", result.errors[0])
    
    # =============================================================================
    # 7. Error Handling and Edge Cases
    # =============================================================================
    
    def test_scaffold_agent_template_exception(self):
        """Test agent scaffolding handles template exceptions gracefully."""
        # Configure prompt manager to raise exception
        self.mock_prompt_manager_service.format_prompt.side_effect = Exception("Template formatting failed")
        
        with patch('pathlib.Path.exists', return_value=False):
            
            # Test method with complete info to avoid early exceptions
            agent_type = "ErrorAgent"
            info = {
                "agent_type": "ErrorAgent",
                "node_name": "error_node", 
                "context": "",
                "prompt": "Error prompt",
                "input_fields": ["input1"],
                "output_field": "output1",
                "description": "Error test agent"
            }
            
            with self.assertRaises(Exception) as cm:
                self.service.scaffold_agent_class(agent_type, info)
            
            self.assertIn("Template formatting failed", str(cm.exception))
    
    def test_scaffold_function_template_exception(self):
        """Test function scaffolding handles template exceptions gracefully."""
        # Configure prompt manager to raise exception
        self.mock_prompt_manager_service.format_prompt.side_effect = Exception("Function template error")
        
        with patch('pathlib.Path.exists', return_value=False):
            
            # Test method with complete info to avoid early exceptions
            func_name = "error_function"
            info = {
                "node_name": "error_node",
                "context": "Error context",
                "input_fields": ["input1"],
                "output_field": "output1",
                "success_next": "next_node",
                "failure_next": "error_node",
                "description": "Error test function"
            }
            
            with self.assertRaises(Exception) as cm:
                self.service.scaffold_edge_function(func_name, info)
            
            self.assertIn("Function template error", str(cm.exception))
    
    def test_service_requirement_parser_malformed_json(self):
        """Test ServiceRequirementParser handles malformed JSON gracefully."""
        parser = ServiceRequirementParser()
        
        # Test with malformed JSON
        malformed_context = '{"services": ["llm",}'  # Missing closing bracket
        result = parser.parse_services(malformed_context)
        
        # Should fall back to empty services
        self.assertEqual(result.services, [])
    
    def test_service_requirement_parser_edge_cases(self):
        """Test ServiceRequirementParser handles various edge cases."""
        parser = ServiceRequirementParser()
        
        # Test with integer context
        result = parser.parse_services(123)
        self.assertEqual(result.services, [])
        
        # Test with list context (not dict)
        result = parser.parse_services(["not", "a", "dict"])
        self.assertEqual(result.services, [])
        
        # Test with complex nested dict without services key
        complex_context = {
            "metadata": {"version": 1},
            "configuration": {"enabled": True}
        }
        result = parser.parse_services(complex_context)
        self.assertEqual(result.services, [])
    
    # =============================================================================
    # 8. Configuration Integration Tests
    # =============================================================================
    
    def test_scaffold_uses_config_paths(self):
        """Test that scaffolding uses paths from app config service."""
        # Configure custom paths
        custom_agents_path = Path("project/custom_agents")
        custom_functions_path = Path("project/functions")
        
        # Update both methods and properties since different parts of the service use different approaches
        self.mock_app_config_service.get_custom_agents_path.return_value = custom_agents_path
        self.mock_app_config_service.get_functions_path.return_value = custom_functions_path
        
        # get_scaffold_paths() accesses properties directly, so update those too
        self.mock_app_config_service.custom_agents_path = custom_agents_path
        self.mock_app_config_service.functions_path = custom_functions_path
        
        # Test get_scaffold_paths
        paths = self.service.get_scaffold_paths()
        
        self.assertEqual(paths["agents_path"], custom_agents_path)
        self.assertEqual(paths["functions_path"], custom_functions_path)
        
        # Verify that the service correctly uses config paths (focus on behavior, not implementation)
        # The CSV path should come from the config as well
        self.assertEqual(paths["csv_path"], Path("graphs/test.csv"))
    
    def test_service_initialization_with_missing_dependencies(self):
        """Test service handles missing dependencies gracefully."""
        # This test verifies that all dependencies are actually required
        with self.assertRaises(TypeError):
            # Missing agent_registry_service should raise TypeError
            GraphScaffoldService(
                app_config_service=self.mock_app_config_service,
                logging_service=self.mock_logging_service,
                prompt_manager=self.mock_prompt_manager_service,
                function_resolution_service=self.mock_function_resolution_service
                # Missing agent_registry_service
            )
    
    def test_template_prompt_manager_integration(self):
        """Test integration with PromptManagerService for template loading."""
        # Test data
        agent_type = "TemplateAgent"
        info = {
            "agent_type": "TemplateAgent",
            "node_name": "template_node",
            "context": "",
            "prompt": "Template test",
            "input_fields": [],
            "output_field": "result",
            "description": "Template integration test"
        }
        
        with patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.open', mock_open()):
            
            # Test agent scaffolding
            self.service.scaffold_agent_class(agent_type, info)
            
            # Verify prompt manager was called with correct template path
            self.mock_prompt_manager_service.format_prompt.assert_called_once()
            call_args = self.mock_prompt_manager_service.format_prompt.call_args
            self.assertEqual(call_args[0][0], "file:scaffold/agent_template.txt")
            
            # Reset for function test
            self.mock_prompt_manager_service.reset_mock()
            
            # Test function scaffolding
            func_info = {"node_name": "test", "context": "test", "input_fields": [], "output_field": "", "success_next": "", "failure_next": "", "description": ""}
            self.service.scaffold_edge_function("test_func", func_info)
            
            # Verify function template path
            call_args = self.mock_prompt_manager_service.format_prompt.call_args
            self.assertEqual(call_args[0][0], "file:scaffold/function_template.txt")


if __name__ == '__main__':
    unittest.main()
