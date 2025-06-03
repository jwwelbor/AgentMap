"""
Unit tests for GraphScaffoldService.

Tests the scaffolding service with comprehensive coverage of all functionality
including service-aware scaffolding, template management, and error handling.
"""

import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

from agentmap.services.graph_scaffold_service import (
    GraphScaffoldService,
    ServiceRequirementParser,
    ScaffoldOptions,
    ScaffoldResult,
    ServiceAttribute,
    ServiceRequirements
)


class TestServiceRequirementParser:
    """Test the ServiceRequirementParser component."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ServiceRequirementParser()
    
    def test_initialization(self):
        """Test parser initialization and service mapping."""
        assert self.parser.service_protocol_map is not None
        assert "llm" in self.parser.service_protocol_map
        assert "csv" in self.parser.service_protocol_map
        assert len(self.parser.service_protocol_map) == 8  # Expected service count
    
    def test_parse_services_empty_context(self):
        """Test parsing with empty or None context."""
        result = self.parser.parse_services(None)
        assert result.services == []
        assert result.protocols == []
        assert result.imports == []
        assert result.attributes == []
        assert result.usage_examples == {}
        
        result = self.parser.parse_services("")
        assert result.services == []
    
    def test_parse_services_dict_context(self):
        """Test parsing services from dictionary context."""
        context = {"services": ["llm", "csv"]}
        result = self.parser.parse_services(context)
        
        assert "llm" in result.services
        assert "csv" in result.services
        assert "LLMServiceUser" in result.protocols
        assert "CSVServiceUser" in result.protocols
        assert len(result.attributes) == 2
        assert "llm" in result.usage_examples
        assert "csv" in result.usage_examples
    
    def test_parse_services_json_string_context(self):
        """Test parsing services from JSON string context."""
        context = '{"services": ["vector", "memory"]}'
        result = self.parser.parse_services(context)
        
        assert "vector" in result.services
        assert "memory" in result.services
        assert "VectorServiceUser" in result.protocols
        assert "MemoryServiceUser" in result.protocols
    
    def test_parse_services_key_value_string_context(self):
        """Test parsing services from key:value string format."""
        context = "services: llm|json|file"
        result = self.parser.parse_services(context)
        
        assert "llm" in result.services
        assert "json" in result.services
        assert "file" in result.services
        assert len(result.services) == 3
    
    def test_parse_services_invalid_service(self):
        """Test error handling for invalid service names."""
        context = {"services": ["llm", "invalid_service"]}
        
        with pytest.raises(ValueError) as exc_info:
            self.parser.parse_services(context)
        
        assert "Unknown services: ['invalid_service']" in str(exc_info.value)
    
    def test_service_attribute_creation(self):
        """Test creation of service attributes."""
        context = {"services": ["node_registry"]}
        result = self.parser.parse_services(context)
        
        assert len(result.attributes) == 1
        attr = result.attributes[0]
        assert attr.name == "node_registry"
        assert attr.type_hint == "Dict[str, Dict[str, Any]]"
        assert "Node registry" in attr.documentation
    
    def test_usage_examples_generation(self):
        """Test generation of usage examples for services."""
        context = {"services": ["storage"]}
        result = self.parser.parse_services(context)
        
        assert "storage" in result.usage_examples
        example = result.usage_examples["storage"]
        assert "storage_service" in example
        assert "read" in example
        assert "write" in example


class TestScaffoldDataClasses:
    """Test the scaffold data classes."""
    
    def test_scaffold_options_defaults(self):
        """Test ScaffoldOptions default values."""
        options = ScaffoldOptions()
        assert options.graph_name is None
        assert options.output_path is None
        assert options.function_path is None
        assert options.overwrite_existing is False
    
    def test_scaffold_options_with_values(self):
        """Test ScaffoldOptions with specified values."""
        output_path = Path("/test/agents")
        func_path = Path("/test/functions")
        
        options = ScaffoldOptions(
            graph_name="test_graph",
            output_path=output_path,
            function_path=func_path,
            overwrite_existing=True
        )
        
        assert options.graph_name == "test_graph"
        assert options.output_path == output_path
        assert options.function_path == func_path
        assert options.overwrite_existing is True
    
    def test_scaffold_result_defaults(self):
        """Test ScaffoldResult default values."""
        result = ScaffoldResult(scaffolded_count=5)
        assert result.scaffolded_count == 5
        assert result.created_files == []
        assert result.skipped_files == []
        assert result.service_stats == {}
        assert result.errors == []
    
    def test_service_requirements_tuple(self):
        """Test ServiceRequirements named tuple."""
        reqs = ServiceRequirements(
            services=["llm"],
            protocols=["LLMServiceUser"],
            imports=["from agentmap.services import LLMServiceUser"],
            attributes=[ServiceAttribute("llm_service", "'LLMService'", "LLM service")],
            usage_examples={"llm": "example code"}
        )
        
        assert reqs.services == ["llm"]
        assert reqs.protocols == ["LLMServiceUser"]
        assert len(reqs.imports) == 1
        assert len(reqs.attributes) == 1
        assert "llm" in reqs.usage_examples


class TestGraphScaffoldService:
    """Test the main GraphScaffoldService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock dependencies
        self.mock_app_config = Mock()
        self.mock_logging_service = Mock()
        self.mock_logger = Mock()
        self.mock_prompt_manager = Mock()
        
        # Configure mocks
        self.mock_logging_service.get_class_logger.return_value = self.mock_logger
        self.mock_app_config.custom_agents_path = Path("/test/agents")
        self.mock_app_config.functions_path = Path("/test/functions")
        self.mock_app_config.csv_path = Path("/test/graph.csv")
        
        # Create service instance
        self.service = GraphScaffoldService(
            self.mock_app_config,
            self.mock_logging_service,
            self.mock_prompt_manager
        )
    
    def test_service_initialization(self):
        """Test service initialization."""
        assert self.service.config == self.mock_app_config
        assert self.service.logger == self.mock_logger
        assert self.service.prompt_manager == self.mock_prompt_manager
        assert isinstance(self.service.service_parser, ServiceRequirementParser)
        
        # Verify logging calls
        self.mock_logging_service.get_class_logger.assert_called_once()
        self.mock_logger.info.assert_called_with("[GraphScaffoldService] Initialized")
    
    def test_get_scaffold_paths(self):
        """Test getting scaffold paths from config."""
        paths = self.service.get_scaffold_paths()
        
        assert "agents_path" in paths
        assert "functions_path" in paths
        assert "csv_path" in paths
        assert paths["agents_path"] == Path("/test/agents")
        assert paths["functions_path"] == Path("/test/functions")
        assert paths["csv_path"] == Path("/test/graph.csv")
    
    def test_get_service_info(self):
        """Test getting service information."""
        info = self.service.get_service_info()
        
        assert info["service"] == "GraphScaffoldService"
        assert info["config_available"] is True
        assert info["prompt_manager_available"] is True
        assert "custom_agents_path" in info
        assert "functions_path" in info
        assert "csv_path" in info
        assert "supported_services" in info
        assert len(info["supported_services"]) == 8
        assert "template_files" in info
    
    @patch('agentmap.services.graph_scaffold_service.Path.mkdir')
    @patch('agentmap.services.graph_scaffold_service.open', new_callable=mock_open)
    def test_collect_agent_info(self, mock_file, mock_mkdir):
        """Test collecting agent information from CSV."""
        # Mock CSV content
        csv_content = """GraphName,Node,AgentType,Context,Prompt,Input_Fields,Output_Field,Description
test_graph,node1,TestAgent,{"services": ["llm"]},test prompt,input1|input2,output,Test agent description
test_graph,node2,ExistingAgent,no services,prompt2,input3,output2,Existing agent
other_graph,node3,OtherAgent,other context,prompt3,input4,output3,Other graph agent"""
        
        mock_file.return_value.read.return_value = csv_content
        mock_file.return_value.__iter__.return_value = csv_content.splitlines()
        
        # Mock get_agent_class to return None for TestAgent (needs scaffolding)
        # and return a class for ExistingAgent (already exists)
        with patch('agentmap.agents.get_agent_class') as mock_get_agent:
            def mock_agent_lookup(agent_type):
                if agent_type == "TestAgent":
                    return None  # Needs scaffolding
                elif agent_type == "ExistingAgent":
                    return Mock()  # Already exists
                elif agent_type == "OtherAgent":
                    return None  # Needs scaffolding but wrong graph
                return None
            
            mock_get_agent.side_effect = mock_agent_lookup
            
            # Test with graph filter
            agent_info = self.service._collect_agent_info(Path("/test/graph.csv"), "test_graph")
            
            # Should only include TestAgent (ExistingAgent already exists, OtherAgent wrong graph)
            assert "TestAgent" in agent_info
            assert "ExistingAgent" not in agent_info  # Already exists
            assert "OtherAgent" not in agent_info  # Wrong graph
            
            test_agent = agent_info["TestAgent"]
            assert test_agent["agent_type"] == "TestAgent"
            assert test_agent["node_name"] == "node1"
            assert test_agent["context"] == '{"services": ["llm"]}'
            assert test_agent["prompt"] == "test prompt"
            assert test_agent["input_fields"] == ["input1", "input2"]
            assert test_agent["output_field"] == "output"
            assert test_agent["description"] == "Test agent description"
    
    @patch('agentmap.services.graph_scaffold_service.Path.mkdir')
    @patch('agentmap.services.graph_scaffold_service.open', new_callable=mock_open)
    def test_collect_function_info(self, mock_file, mock_mkdir):
        """Test collecting function information from CSV."""
        # Mock CSV content with edge functions
        csv_content = """GraphName,Node,Edge,Success_Next,Failure_Next,Input_Fields,Output_Field,Description,Context
test_graph,node1,func:test_func,node2,node3,input1|input2,output,Test function,function context
test_graph,node2,simple_edge,node3,END,input3,output2,Simple edge,no context
other_graph,node4,func:other_func,node5,END,input4,output3,Other function,other context"""
        
        mock_file.return_value.read.return_value = csv_content
        mock_file.return_value.__iter__.return_value = csv_content.splitlines()
        
        # Mock extract_func_ref to return function names for func: references
        with patch('agentmap.utils.common.extract_func_ref') as mock_extract:
            def mock_func_extraction(value):
                if value == "func:test_func":
                    return "test_func"
                elif value == "func:other_func":
                    return "other_func"
                return None
            
            mock_extract.side_effect = mock_func_extraction
            
            # Test with graph filter
            func_info = self.service._collect_function_info(Path("/test/graph.csv"), "test_graph")
            
            # Should only include test_func (other_func is in wrong graph)
            assert "test_func" in func_info
            assert "other_func" not in func_info  # Wrong graph
            
            test_func = func_info["test_func"]
            assert test_func["node_name"] == "node1"
            assert test_func["context"] == "function context"
            assert test_func["input_fields"] == ["input1", "input2"]
            assert test_func["output_field"] == "output"
            assert test_func["success_next"] == "node2"
            assert test_func["failure_next"] == "node3"
            assert test_func["description"] == "Test function"
    
    @patch('agentmap.services.graph_scaffold_service.Path.mkdir')
    @patch('agentmap.services.graph_scaffold_service.Path.open', new_callable=mock_open)
    @patch('agentmap.services.graph_scaffold_service.Path.exists')
    def test_scaffold_agent_with_services(self, mock_exists, mock_file, mock_mkdir):
        """Test scaffolding an agent with service requirements."""
        mock_exists.return_value = False  # File doesn't exist
        
        # Mock template formatting
        formatted_template = "# Generated agent code with services"
        self.mock_prompt_manager.format_prompt.return_value = formatted_template
        
        # Agent info with services
        agent_info = {
            "agent_type": "TestAgent",
            "node_name": "test_node",
            "context": '{"services": ["llm", "csv"]}',
            "prompt": "test prompt",
            "input_fields": ["input1", "input2"],
            "output_field": "output",
            "description": "Test agent with services"
        }
        
        # Execute scaffolding
        result_path = self.service._scaffold_agent(
            "TestAgent", 
            agent_info, 
            Path("/test/agents"),
            overwrite=False
        )
        
        # Verify results
        assert result_path == Path("/test/agents/testagent_agent.py")
        mock_file.assert_called_once()
        
        # Verify template was called with correct variables
        self.mock_prompt_manager.format_prompt.assert_called_once()
        call_args = self.mock_prompt_manager.format_prompt.call_args
        
        assert call_args[0][0] == "file:scaffold/agent_template.txt"
        template_vars = call_args[0][1]
        
        assert template_vars["agent_type"] == "TestAgent"
        assert template_vars["class_name"] == "TestAgentAgent"
        assert "LLMServiceUser" in template_vars["class_definition"]
        assert "CSVServiceUser" in template_vars["class_definition"]
        assert "with llm, csv capabilities" in template_vars["service_description"]
    
    @patch('agentmap.services.graph_scaffold_service.Path.mkdir')
    @patch('agentmap.services.graph_scaffold_service.Path.open', new_callable=mock_open)
    @patch('agentmap.services.graph_scaffold_service.Path.exists')
    def test_scaffold_agent_file_exists(self, mock_exists, mock_file, mock_mkdir):
        """Test scaffolding when file already exists."""
        mock_exists.return_value = True  # File exists
        
        agent_info = {"agent_type": "TestAgent", "node_name": "test_node"}
        
        # Execute scaffolding without overwrite
        result_path = self.service._scaffold_agent(
            "TestAgent", 
            agent_info, 
            Path("/test/agents"),
            overwrite=False
        )
        
        # Should return None when file exists and overwrite=False
        assert result_path is None
        mock_file.assert_not_called()
        self.mock_prompt_manager.format_prompt.assert_not_called()
    
    def test_template_variable_preparation(self):
        """Test preparation of template variables."""
        agent_info = {
            "agent_type": "TestAgent",
            "node_name": "test_node",
            "context": '{"services": ["llm"]}',
            "prompt": "test prompt",
            "input_fields": ["input1", "input2"],
            "output_field": "output",
            "description": "Test agent"
        }
        
        # Parse service requirements
        service_reqs = self.service.service_parser.parse_services(agent_info["context"])
        
        # Prepare template variables
        template_vars = self.service._prepare_agent_template_variables(
            "TestAgent", agent_info, service_reqs
        )
        
        # Verify key template variables
        assert template_vars["agent_type"] == "TestAgent"
        assert template_vars["class_name"] == "TestAgentAgent"
        assert "LLMServiceUser" in template_vars["class_definition"]
        assert "with llm capabilities" in template_vars["service_description"]
        assert "from agentmap.services import LLMServiceUser" in template_vars["imports"]
        assert "self.llm_service" in template_vars["service_attributes"]
        assert "input1 = processed_inputs.get(\"input1\")" in template_vars["input_field_access"]
        assert "LLM SERVICE:" in template_vars["service_usage_examples"]
    
    @patch('agentmap.services.graph_scaffold_service.Path.mkdir')
    @patch('agentmap.services.graph_scaffold_service.Path.open', new_callable=mock_open)
    @patch('agentmap.services.graph_scaffold_service.Path.exists')
    def test_scaffold_function(self, mock_exists, mock_file, mock_mkdir):
        """Test scaffolding an edge function."""
        mock_exists.return_value = False  # File doesn't exist
        
        # Mock template formatting
        formatted_template = "# Generated function code"
        self.mock_prompt_manager.format_prompt.return_value = formatted_template
        
        # Function info
        func_info = {
            "node_name": "test_node",
            "context": "function context",
            "input_fields": ["input1", "input2"],
            "output_field": "output",
            "success_next": "success_node",
            "failure_next": "failure_node",
            "description": "Test function"
        }
        
        # Execute scaffolding
        result_path = self.service._scaffold_function(
            "test_func",
            func_info,
            Path("/test/functions"),
            overwrite=False
        )
        
        # Verify results
        assert result_path == Path("/test/functions/test_func.py")
        mock_file.assert_called_once()
        
        # Verify template was called
        self.mock_prompt_manager.format_prompt.assert_called_once()
        call_args = self.mock_prompt_manager.format_prompt.call_args
        
        assert call_args[0][0] == "file:scaffold/function_template.txt"
        template_vars = call_args[0][1]
        
        assert template_vars["func_name"] == "test_func"
        assert template_vars["context"] == "function context"
        assert template_vars["success_node"] == "success_node"
        assert template_vars["failure_node"] == "failure_node"
    
    def test_generate_context_fields(self):
        """Test generation of context field documentation."""
        # Test with input and output fields
        result = self.service._generate_context_fields(
            ["input1", "input2"], "output"
        )
        
        expected_lines = [
            "    - input1: Input from previous node",
            "    - input2: Input from previous node", 
            "    - output: Expected output to generate"
        ]
        
        for line in expected_lines:
            assert line in result
        
        # Test with no fields
        result = self.service._generate_context_fields([], "")
        assert "No specific fields defined" in result
    
    @patch.object(GraphScaffoldService, '_collect_agent_info')
    @patch.object(GraphScaffoldService, '_collect_function_info')
    @patch.object(GraphScaffoldService, '_scaffold_agent')
    @patch.object(GraphScaffoldService, '_scaffold_function')
    @patch('agentmap.services.graph_scaffold_service.Path.mkdir')
    def test_scaffold_agents_from_csv_success(self, mock_mkdir, mock_scaffold_func, 
                                            mock_scaffold_agent, mock_collect_func, 
                                            mock_collect_agent):
        """Test complete CSV scaffolding workflow."""
        # Mock data collection
        mock_collect_agent.return_value = {
            "TestAgent": {
                "agent_type": "TestAgent",
                "context": '{"services": ["llm"]}',
                "node_name": "test_node"
            }
        }
        mock_collect_func.return_value = {
            "test_func": {"node_name": "test_node", "context": "func context"}
        }
        
        # Mock scaffolding results
        mock_scaffold_agent.return_value = Path("/test/agents/testagent_agent.py")
        mock_scaffold_func.return_value = Path("/test/functions/test_func.py")
        
        # Execute scaffolding
        options = ScaffoldOptions(graph_name="test_graph")
        result = self.service.scaffold_agents_from_csv(Path("/test/graph.csv"), options)
        
        # Verify results
        assert result.scaffolded_count == 2
        assert len(result.created_files) == 2
        assert len(result.errors) == 0
        assert result.service_stats["with_services"] == 1
        assert result.service_stats["without_services"] == 0
        
        # Verify method calls
        mock_collect_agent.assert_called_once_with(Path("/test/graph.csv"), "test_graph")
        mock_collect_func.assert_called_once_with(Path("/test/graph.csv"), "test_graph")
        mock_scaffold_agent.assert_called_once()
        mock_scaffold_func.assert_called_once()
    
    @patch.object(GraphScaffoldService, '_collect_agent_info')
    @patch.object(GraphScaffoldService, '_collect_function_info')
    @patch('agentmap.services.graph_scaffold_service.Path.mkdir')
    def test_scaffold_agents_from_csv_with_errors(self, mock_mkdir, mock_collect_func, 
                                                 mock_collect_agent):
        """Test CSV scaffolding with error handling."""
        # Mock data collection
        mock_collect_agent.return_value = {
            "TestAgent": {"agent_type": "TestAgent", "context": "test context"}
        }
        mock_collect_func.return_value = {}
        
        # Mock scaffolding to raise exception
        with patch.object(self.service, '_scaffold_agent') as mock_scaffold:
            mock_scaffold.side_effect = Exception("Scaffolding failed")
            
            # Execute scaffolding
            result = self.service.scaffold_agents_from_csv(Path("/test/graph.csv"))
            
            # Verify error handling
            assert result.scaffolded_count == 0
            assert len(result.errors) == 1
            assert "Failed to scaffold agent TestAgent" in result.errors[0]
    
    def test_scaffold_individual_methods(self):
        """Test individual scaffolding methods."""
        agent_info = {"agent_type": "TestAgent", "context": "test context"}
        func_info = {"node_name": "test_node", "context": "func context"}
        
        # Test scaffold_agent_class
        with patch.object(self.service, '_scaffold_agent') as mock_scaffold:
            mock_scaffold.return_value = Path("/test/agent.py")
            
            result = self.service.scaffold_agent_class("TestAgent", agent_info)
            assert result == Path("/test/agent.py")
            mock_scaffold.assert_called_once_with(
                "TestAgent", agent_info, self.mock_app_config.custom_agents_path, overwrite=False
            )
        
        # Test scaffold_edge_function
        with patch.object(self.service, '_scaffold_function') as mock_scaffold:
            mock_scaffold.return_value = Path("/test/function.py")
            
            result = self.service.scaffold_edge_function("test_func", func_info)
            assert result == Path("/test/function.py")
            mock_scaffold.assert_called_once_with(
                "test_func", func_info, self.mock_app_config.functions_path, overwrite=False
            )
