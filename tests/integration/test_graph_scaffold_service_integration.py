"""
Integration tests for GraphScaffoldService.

Tests the scaffolding service with real dependencies and file system operations
to validate end-to-end functionality and integration with other services.
"""

import csv
import tempfile
from pathlib import Path

import pytest

from agentmap.di import initialize_di
from agentmap.services.graph_scaffold_service import ScaffoldOptions, GraphScaffoldService


class TestGraphScaffoldServiceIntegration:
    """Integration tests for GraphScaffoldService with real dependencies."""
    
    def setup_method(self):
        """Set up test fixtures with real DI container."""
        # Initialize DI container for integration testing
        self.container = initialize_di()
        
        # Create temporary directories for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.agents_dir = self.temp_dir / "agents"
        self.functions_dir = self.temp_dir / "functions"
        self.csv_file = self.temp_dir / "test_graph.csv"
        
        self.agents_dir.mkdir(parents=True)
        self.functions_dir.mkdir(parents=True)
        
        # Get real services from DI container
        self.app_config_service = self.container.app_config_service()
        self.logging_service = self.container.logging_service()
        self.prompt_manager = self.container.prompt_manager_service()
        
        # Override paths for testing
        self.original_agents_path = self.app_config_service.custom_agents_path
        self.original_functions_path = self.app_config_service.functions_path
        self.app_config_service.custom_agents_path = self.agents_dir
        self.app_config_service.functions_path = self.functions_dir
        
        # Create service instance
        self.service = GraphScaffoldService(
            self.app_config_service,
            self.logging_service,
            self.prompt_manager
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Restore original paths
        self.app_config_service.custom_agents_path = self.original_agents_path
        self.app_config_service.functions_path = self.original_functions_path
        
        # Clean up temporary directory
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def create_test_csv(self, csv_content):
        """Create a test CSV file with the given content."""
        with open(self.csv_file, 'w', newline='') as f:
            f.write(csv_content)
    
    def test_service_initialization_with_real_dependencies(self):
        """Test service initialization with real DI container services."""
        assert self.service.config is not None
        assert self.service.logger is not None
        assert self.service.prompt_manager is not None
        assert self.service.service_parser is not None
        
        # Test service info
        info = self.service.get_service_info()
        assert info["service"] == "GraphScaffoldService"
        assert info["config_available"] is True
        assert info["prompt_manager_available"] is True
        assert len(info["supported_services"]) == 8
    
    def test_scaffold_agents_with_services_integration(self):
        """Test scaffolding agents with service integration using real templates."""
        # Create CSV with service-aware agents
        csv_content = """GraphName,Node,AgentType,Context,Prompt,Input_Fields,Output_Field,Description
test_graph,data_processor,DataProcessorAgent,"{""services"": [""llm"", ""csv""]}",Process the data,input_data|file_path,processed_data,Agent that processes data using LLM and CSV services
test_graph,analyzer,AnalyzerAgent,"{""services"": [""vector"", ""memory""]}",Analyze results,analysis_input,analysis_output,Agent that analyzes using vector search and memory
test_graph,simple_agent,SimpleAgent,,Simple processing,simple_input,simple_output,Basic agent without services"""
        
        self.create_test_csv(csv_content)
        
        # Execute scaffolding
        options = ScaffoldOptions(graph_name="test_graph")
        result = self.service.scaffold_agents_from_csv(self.csv_file, options)
        
        # Verify scaffolding results
        assert result.scaffolded_count == 3
        assert len(result.created_files) == 3
        assert len(result.errors) == 0
        assert result.service_stats["with_services"] == 2
        assert result.service_stats["without_services"] == 1
        
        # Verify files were created
        data_processor_file = self.agents_dir / "dataprocessoragent_agent.py"
        analyzer_file = self.agents_dir / "analyzeragent_agent.py"
        simple_file = self.agents_dir / "simpleagent_agent.py"
        
        assert data_processor_file.exists()
        assert analyzer_file.exists()
        assert simple_file.exists()
        
        # Verify content of service-aware agent
        data_processor_content = data_processor_file.read_text()
        assert "class DataProcessorAgentAgent(BaseAgent, LLMServiceUser, CSVServiceUser):" in data_processor_content
        assert "self.llm_service: 'LLMService' = None" in data_processor_content
        assert "self.csv_service: 'CSVStorageService' = None" in data_processor_content
        assert "LLM SERVICE:" in data_processor_content
        assert "CSV SERVICE:" in data_processor_content
        
        # Verify content of vector/memory agent
        analyzer_content = analyzer_file.read_text()
        assert "VectorServiceUser" in analyzer_content
        assert "MemoryServiceUser" in analyzer_content
        assert "self.vector_service" in analyzer_content
        assert "self.memory_service" in analyzer_content
        
        # Verify content of simple agent (no services)
        simple_content = simple_file.read_text()
        assert "class SimpleAgentAgent(BaseAgent):" in simple_content
        assert "ServiceUser" not in simple_content
        assert "No services configured" in simple_content
    
    def test_scaffold_edge_functions_integration(self):
        """Test scaffolding edge functions using real templates."""
        # Create CSV with edge functions
        csv_content = """GraphName,Node,Edge,Success_Next,Failure_Next,Input_Fields,Output_Field,Description,Context
test_graph,validator,func:validate_data,processor,error_handler,data|validation_rules,is_valid,Validates input data,Validation context
test_graph,transformer,func:transform_output,final_node,error_handler,raw_output|format_spec,formatted_output,Transforms output format,Transform context"""
        
        self.create_test_csv(csv_content)
        
        # Mock extract_func_ref to return function names
        import agentmap.utils.common
        original_extract_func_ref = agentmap.utils.common.extract_func_ref
        
        def mock_extract_func_ref(value):
            if value == "func:validate_data":
                return "validate_data"
            elif value == "func:transform_output":
                return "transform_output"
            return original_extract_func_ref(value)
        
        agentmap.utils.common.extract_func_ref = mock_extract_func_ref
        
        try:
            # Execute scaffolding
            options = ScaffoldOptions(graph_name="test_graph")
            result = self.service.scaffold_agents_from_csv(self.csv_file, options)
            
            # Verify scaffolding results
            assert result.scaffolded_count == 2
            assert len(result.created_files) == 2
            assert len(result.errors) == 0
            
            # Verify files were created
            validate_file = self.functions_dir / "validate_data.py"
            transform_file = self.functions_dir / "transform_output.py"
            
            assert validate_file.exists()
            assert transform_file.exists()
            
            # Verify function content
            validate_content = validate_file.read_text()
            assert "def validate_data(state: Dict[str, Any]) -> str:" in validate_content
            assert "data: Input from previous node" in validate_content
            assert "validation_rules: Input from previous node" in validate_content
            assert "is_valid: Expected output to generate" in validate_content
            assert "processor" in validate_content
            assert "error_handler" in validate_content
            
            transform_content = transform_file.read_text()
            assert "def transform_output(state: Dict[str, Any]) -> str:" in transform_content
            assert "raw_output: Input from previous node" in transform_content
            assert "formatted_output: Expected output to generate" in transform_content
            
        finally:
            # Restore original function
            agentmap.utils.common.extract_func_ref = original_extract_func_ref
    
    def test_scaffold_with_graph_filter_integration(self):
        """Test scaffolding with graph name filtering."""
        # Create CSV with multiple graphs
        csv_content = """GraphName,Node,AgentType,Context,Prompt,Input_Fields,Output_Field,Description
target_graph,node1,TargetAgent,,Target prompt,input1,output1,Target graph agent
other_graph,node2,OtherAgent,,Other prompt,input2,output2,Other graph agent
target_graph,node3,AnotherTargetAgent,,Another prompt,input3,output3,Another target agent"""
        
        self.create_test_csv(csv_content)
        
        # Execute scaffolding with graph filter
        options = ScaffoldOptions(graph_name="target_graph")
        result = self.service.scaffold_agents_from_csv(self.csv_file, options)
        
        # Should only scaffold agents from target_graph
        assert result.scaffolded_count == 2
        
        target_file = self.agents_dir / "targetagent_agent.py"
        another_target_file = self.agents_dir / "anothertargetagent_agent.py"
        other_file = self.agents_dir / "otheragent_agent.py"
        
        assert target_file.exists()
        assert another_target_file.exists()
        assert not other_file.exists()
    
    def test_scaffold_overwrite_behavior_integration(self):
        """Test file overwrite behavior."""
        # Create CSV
        csv_content = """GraphName,Node,AgentType,Context,Prompt,Input_Fields,Output_Field,Description
test_graph,node1,TestAgent,,Test prompt,input1,output1,Test agent"""
        
        self.create_test_csv(csv_content)
        
        # First scaffolding - should create file
        options = ScaffoldOptions(graph_name="test_graph", overwrite_existing=False)
        result1 = self.service.scaffold_agents_from_csv(self.csv_file, options)
        
        assert result1.scaffolded_count == 1
        assert len(result1.created_files) == 1
        
        test_file = self.agents_dir / "testagent_agent.py"
        assert test_file.exists()
        
        # Second scaffolding without overwrite - should skip existing file
        result2 = self.service.scaffold_agents_from_csv(self.csv_file, options)
        
        assert result2.scaffolded_count == 0
        assert len(result2.skipped_files) == 1
        
        # Third scaffolding with overwrite - should recreate file
        options.overwrite_existing = True
        result3 = self.service.scaffold_agents_from_csv(self.csv_file, options)
        
        assert result3.scaffolded_count == 1
        assert len(result3.created_files) == 1
    
    def test_scaffold_error_handling_integration(self):
        """Test error handling during scaffolding operations."""
        # Create CSV with invalid content
        csv_content = """GraphName,Node,AgentType,Context,Prompt,Input_Fields,Output_Field,Description
test_graph,node1,TestAgent,"{""services"": [""invalid_service""]}",Test prompt,input1,output1,Test agent with invalid service"""
        
        self.create_test_csv(csv_content)
        
        # Execute scaffolding - should handle errors gracefully
        options = ScaffoldOptions(graph_name="test_graph")
        result = self.service.scaffold_agents_from_csv(self.csv_file, options)
        
        # Should have errors but not crash
        assert result.scaffolded_count == 0
        assert len(result.errors) > 0
        assert "Failed to scaffold agent TestAgent" in result.errors[0]
        assert "Unknown services" in result.errors[0]
    
    def test_individual_scaffolding_methods_integration(self):
        """Test individual scaffolding methods with real dependencies."""
        # Test agent scaffolding
        agent_info = {
            "agent_type": "IndividualAgent",
            "node_name": "individual_node",
            "context": '{"services": ["llm"]}',
            "prompt": "individual prompt",
            "input_fields": ["input1"],
            "output_field": "output1",
            "description": "Individual test agent"
        }
        
        result_path = self.service.scaffold_agent_class("IndividualAgent", agent_info)
        assert result_path is not None
        assert result_path.exists()
        
        # Verify content
        content = result_path.read_text()
        assert "class IndividualAgentAgent(BaseAgent, LLMServiceUser):" in content
        
        # Test function scaffolding
        func_info = {
            "node_name": "individual_node",
            "context": "individual function context",
            "input_fields": ["func_input"],
            "output_field": "func_output",
            "success_next": "success_node",
            "failure_next": "failure_node",
            "description": "Individual test function"
        }
        
        result_path = self.service.scaffold_edge_function("individual_func", func_info)
        assert result_path is not None
        assert result_path.exists()
        
        # Verify content
        content = result_path.read_text()
        assert "def individual_func(state: Dict[str, Any]) -> str:" in content
        assert "func_input: Input from previous node" in content
    
    def test_get_scaffold_paths_integration(self):
        """Test scaffold path retrieval with real config."""
        paths = self.service.get_scaffold_paths()
        
        assert paths["agents_path"] == self.agents_dir
        assert paths["functions_path"] == self.functions_dir
        assert "csv_path" in paths
        
        # Test with graph name (should be same paths)
        paths_with_graph = self.service.get_scaffold_paths("test_graph")
        assert paths_with_graph == paths
    
    def test_prompt_manager_integration(self):
        """Test integration with PromptManagerService for template loading."""
        # This test verifies that the service can load real templates
        # through the PromptManagerService
        
        agent_info = {
            "agent_type": "TemplateTestAgent",
            "node_name": "template_node",
            "context": "",
            "prompt": "template prompt",
            "input_fields": ["template_input"],
            "output_field": "template_output",
            "description": "Template test agent"
        }
        
        # This should work with real templates
        result_path = self.service.scaffold_agent_class("TemplateTestAgent", agent_info)
        assert result_path is not None
        assert result_path.exists()
        
        # Verify that template was properly formatted
        content = result_path.read_text()
        assert "class TemplateTestAgentAgent(BaseAgent):" in content
        assert "def run(self, state: Dict[str, Any]) -> Dict[str, Any]:" in content
        assert "Template test agent" in content  # Description should be included
        
        # Test function template
        func_info = {
            "node_name": "template_node",
            "context": "template function context",
            "input_fields": ["template_func_input"],
            "output_field": "template_func_output",
            "success_next": "template_success",
            "failure_next": "template_failure",
            "description": "Template test function"
        }
        
        result_path = self.service.scaffold_edge_function("template_test_func", func_info)
        assert result_path is not None
        assert result_path.exists()
        
        content = result_path.read_text()
        assert "def template_test_func(state: Dict[str, Any]) -> str:" in content
        assert "template_func_input: Input from previous node" in content
