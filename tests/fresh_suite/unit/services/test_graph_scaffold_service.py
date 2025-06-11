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
    ServiceRequirementParser
)
from agentmap.models.scaffold_types import (
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
        self.mock_function_resolution_service = Mock()
        self.mock_agent_registry_service = MockServiceFactory.create_mock_agent_registry_service()
        self.mock_template_composer = Mock()
        
        # Configure template composer mock to return formatted templates
        self.mock_template_composer.compose_template.return_value = "# Generated Agent Class\nclass TestAgent(BaseAgent):\n    def __init__(self, **kwargs):\n        super().__init__(**kwargs)\n    \n    def run(self, **kwargs):\n        return {}\n"
        self.mock_template_composer.compose_function_template.return_value = "# Generated Function\ndef test_function(state):\n    return state\n"
        
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
        
        # Initialize GraphScaffoldService with mocked dependencies (no longer needs prompt_manager)
        self.service = GraphScaffoldService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            function_resolution_service=self.mock_function_resolution_service,
            agent_registry_service=self.mock_agent_registry_service,
            template_composer=self.mock_template_composer
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
        self.assertEqual(self.service.function_service, self.mock_function_resolution_service)
        self.assertEqual(self.service.agent_registry, self.mock_agent_registry_service)
        self.assertEqual(self.service.template_composer, self.mock_template_composer)
        
        # Verify logger is configured
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, "GraphScaffoldService")
        
        # Verify service parser is initialized
        self.assertIsNotNone(self.service.service_parser)
        self.assertIsInstance(self.service.service_parser, ServiceRequirementParser)
        
        # Verify initialization log message includes unified template composer reference
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("unified IndentedTemplateComposer" in call[1]
                          for call in logger_calls if call[0] == "info"))
    
    def test_get_service_info(self):
        """Test get_service_info() debug method."""
        # Act
        service_info = self.service.get_service_info()
        
        # Assert basic structure
        self.assertIsInstance(service_info, dict)
        self.assertEqual(service_info["service"], "GraphScaffoldService")
        self.assertTrue(service_info["config_available"])
        self.assertTrue(service_info["template_composer_available"])
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
        
        # Verify template composer handles both agent and function templates
        template_composer_handles = service_info["template_composer_handles"]
        self.assertIn("agent_templates", template_composer_handles)
        self.assertIn("function_templates", template_composer_handles)
    
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
        
        # Verify service protocol maps exist
        self.assertIsInstance(parser.separate_service_map, dict)
        self.assertIsInstance(parser.unified_service_map, dict)
        
        # Verify all expected services are mapped in separate_service_map
        expected_services = [
            "llm", "csv", "json", "file", "vector", "memory", 
            "node_registry", "storage"
        ]
        for service in expected_services:
            self.assertIn(service, parser.separate_service_map)
            
            # Verify each service has required keys
            service_info = parser.separate_service_map[service]
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
        self.assertEqual(llm_attr.type_hint, "LLMServiceProtocol")
        self.assertIn("LLM service", llm_attr.documentation)
        
        # Verify CSV service mapping
        csv_attr = next(attr for attr in result.attributes if attr.name == "csv_service")
        self.assertEqual(csv_attr.type_hint, "Any  # CSV storage service")
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
        self.assertEqual(vector_attr.type_hint, "Any  # Vector storage service")
    
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
        llm_example = parser._get_usage_example("llm", parser.separate_service_map)
        self.assertIn("llm_service", llm_example)
        self.assertIn("call_llm", llm_example)
        self.assertIn("provider", llm_example)
        
        # Test CSV usage example
        csv_example = parser._get_usage_example("csv", parser.separate_service_map)
        self.assertIn("csv_service", csv_example)
        self.assertIn("read", csv_example)
        self.assertIn("write", csv_example)
        
        # Test vector usage example
        vector_example = parser._get_usage_example("vector", parser.separate_service_map)
        self.assertIn("vector_service", vector_example)
        self.assertIn("collection", vector_example)
        self.assertIn("similar", vector_example)
        
        # Test node_registry usage example
        node_registry_example = parser._get_usage_example("node_registry", parser.separate_service_map)
        self.assertIn("node_registry", node_registry_example)
        self.assertIn("available_nodes", node_registry_example)
        self.assertIn("routing", node_registry_example)
        
        # Test unknown service
        unknown_example = parser._get_usage_example("unknown", parser.separate_service_map)
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
        # Configure template composer to return specific formatted template
        formatted_template = """# Generated Agent Class
class TestAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def run(self, **kwargs):
        return {}
"""
        self.mock_template_composer.compose_template.return_value = formatted_template
        
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
            
            # Verify template composer was called instead of prompt manager
            self.mock_template_composer.compose_template.assert_called_once()
            call_args = self.mock_template_composer.compose_template.call_args
            
            # Verify template composer was called with correct arguments
            self.assertEqual(call_args[0][0], "TestAgent")  # agent_type
            self.assertEqual(call_args[0][1], info)  # info dict
            # Third argument is service_reqs - we'll verify it's a ServiceRequirements object
            service_reqs = call_args[0][2]
            self.assertEqual(service_reqs.services, ["llm"])
    
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
            
            # Template composer should not be called
            self.mock_template_composer.compose_template.assert_not_called()
    
    def test_scaffold_agent_with_services(self):
        """Test scaffolding agent with service dependencies."""
        # Configure template composer formatting
        self.mock_template_composer.compose_template.return_value = "# Mock template with services"
        
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
            
            # Verify template composer was called with service requirements
            self.mock_template_composer.compose_template.assert_called_once()
            call_args = self.mock_template_composer.compose_template.call_args
            
            # Verify template composer received correct arguments
            self.assertEqual(call_args[0][0], "ServiceAgent")  # agent_type
            self.assertEqual(call_args[0][1], info)  # info dict
            
            # Verify service requirements were parsed correctly
            service_reqs = call_args[0][2]
            self.assertEqual(service_reqs.services, ["llm", "csv", "vector"])
            self.assertIn("LLMCapableAgent", service_reqs.protocols)
            self.assertIn("CSVCapableAgent", service_reqs.protocols)
            self.assertIn("VectorCapableAgent", service_reqs.protocols)
    
    # =============================================================================
    # 5. Function Scaffolding Tests
    # =============================================================================
    
    def test_scaffold_edge_function_success(self):
        """Test scaffold_edge_function() creates function file successfully."""
        # Configure template composer formatting
        formatted_template = """# Generated Edge Function
def test_function(state):
    \"\"\"Test function description.\"\"\"
    return state
"""
        self.mock_template_composer.compose_function_template.return_value = formatted_template
        
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
            
            # Verify template composer was called for function template
            self.mock_template_composer.compose_function_template.assert_called_once()
            call_args = self.mock_template_composer.compose_function_template.call_args
            self.assertEqual(call_args[0][0], "test_function")  # func_name
            self.assertEqual(call_args[0][1], info)  # info dict
    
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
            
            # Template composer should not be called
            self.mock_template_composer.compose_function_template.assert_not_called()
    
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
        
        # Configure template composer formatting
        self.mock_template_composer.compose_template.return_value = "# Mock agent template"
        self.mock_template_composer.compose_function_template.return_value = "# Mock function template"
        
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
            
            # Verify both agent and function templates were composed
            self.mock_template_composer.compose_template.assert_called_once()
            self.mock_template_composer.compose_function_template.assert_called_once()
    
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
        
        # Configure template composer to raise exception
        self.mock_template_composer.compose_template.side_effect = Exception("Template error")
        
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
        # Configure template composer to raise exception
        self.mock_template_composer.compose_template.side_effect = Exception("Template formatting failed")
        
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
        # Configure template composer to raise exception
        self.mock_template_composer.compose_function_template.side_effect = Exception("Function template error")
        
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
            # Missing template_composer should raise TypeError
            GraphScaffoldService(
                app_config_service=self.mock_app_config_service,
                logging_service=self.mock_logging_service,
                function_resolution_service=self.mock_function_resolution_service,
                agent_registry_service=self.mock_agent_registry_service
                # Missing template_composer
            )
    
    def test_template_composer_integration(self):
        """Test integration with IndentedTemplateComposer for both agents and functions."""
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
            
            # Test agent scaffolding - should use template composer
            self.service.scaffold_agent_class(agent_type, info)
            
            # Verify template composer was called for agent
            self.mock_template_composer.compose_template.assert_called_once()
            call_args = self.mock_template_composer.compose_template.call_args
            self.assertEqual(call_args[0][0], "TemplateAgent")
            
            # Reset for function test
            self.mock_template_composer.reset_mock()
            
            # Test function scaffolding - should use template composer for functions too
            func_info = {"node_name": "test", "context": "test", "input_fields": [], "output_field": "", "success_next": "", "failure_next": "", "description": ""}
            self.service.scaffold_edge_function("test_func", func_info)
            
            # Verify template composer was called for function
            self.mock_template_composer.compose_function_template.assert_called_once()
            call_args = self.mock_template_composer.compose_function_template.call_args
            self.assertEqual(call_args[0][0], "test_func")


if __name__ == '__main__':
    unittest.main()
