"""
Integration tests for GraphRunnerService.

These tests use real dependencies and real CSV files to verify the service
works correctly in realistic scenarios and preserves all existing functionality
from runner.py.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import time

from agentmap.services.graph_runner_service import GraphRunnerService, RunOptions
from agentmap.services.graph_builder_service import GraphBuilderService
from agentmap.services.compilation_service import CompilationService
from agentmap.models.execution_result import ExecutionResult
from agentmap.models.graph import Graph
from agentmap.models.node import Node


class TestGraphRunnerServiceIntegration(unittest.TestCase):
    """Integration tests for GraphRunnerService with real dependencies."""
    
    def setUp(self):
        """Set up test fixtures with real dependencies."""
        # Create real but minimal dependencies for integration testing
        self.logging_service = Mock()
        self.logger = Mock()
        self.logging_service.get_class_logger.return_value = self.logger
        self.logging_service.get_logger.return_value = self.logger
        
        self.config_service = Mock()
        self.config_service.get_compiled_graphs_path.return_value = Path("/test/compiled")
        self.config_service.get_csv_path.return_value = Path("/test/graph.csv")
        self.config_service.get_custom_agents_path.return_value = Path("/test/agents")
        self.config_service.get_value.return_value = False  # autocompile default
        
        self.node_registry_service = Mock()
        self.node_registry_service.prepare_for_assembly.return_value = {}
        self.node_registry_service.verify_pre_compilation_injection.return_value = {
            "all_injected": True, "has_orchestrators": False, "stats": {}
        }
        
        # Create real GraphBuilderService for testing
        self.graph_builder_service = GraphBuilderService(
            logging_service=self.logging_service,
            app_config_service=self.config_service
        )
        
        # Create real CompilationService for testing
        self.compilation_service = CompilationService(
            graph_builder_service=self.graph_builder_service,
            logging_service=self.logging_service,
            app_config_service=self.config_service,
            node_registry_service=self.node_registry_service
        )
        
        # Mock other services that are more complex to set up
        self.llm_service = Mock()
        self.storage_service_manager = Mock()
        self.execution_tracker = Mock()
        
        # Setup execution tracker mocks
        self.execution_tracker.get_summary.return_value = {
            "graph_success": True,
            "overall_success": True,
            "execution_time": 1.5,
            "nodes_executed": 2,
            "errors": []
        }
        
        # Create service instance with mixed real/mock dependencies
        self.service = GraphRunnerService(
            graph_builder_service=self.graph_builder_service,
            compilation_service=self.compilation_service,
            llm_service=self.llm_service,
            storage_service_manager=self.storage_service_manager,
            node_registry_service=self.node_registry_service,
            logging_service=self.logging_service,
            app_config_service=self.config_service,
            execution_tracker=self.execution_tracker
        )
    
    def create_test_csv_file(self, content: str) -> Path:
        """Helper method to create temporary CSV file with content."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_file.write(content)
        temp_file.close()
        return Path(temp_file.name)
    
def create_simple_workflow_csv(self) -> str:
    """Create a simple workflow CSV for testing."""
    return """GraphName,Node,AgentType,Input_Fields,Output_Field,Prompt,Description,Edge,Success_Next,Failure_Next
SimpleWorkflow,Start,Default,input,processed,Start processing,Start node,Process,,
SimpleWorkflow,Process,LLM,processed,result,Process the data,Processing node,,Success,Failure
SimpleWorkflow,Success,Default,result,output,Success result,Success node,,,
SimpleWorkflow,Failure,Default,result,error,Failure result,Failure node,,,
"""

def create_complex_workflow_csv(self) -> str:
    """Create a more complex workflow CSV for testing."""
    return """GraphName,Node,AgentType,Input_Fields,Output_Field,Prompt,Description,Edge,Success_Next,Failure_Next
ComplexWorkflow,DataInput,Default,user_input,initial_data,Collect input,Input node,Validator,,
ComplexWorkflow,Validator,Default,initial_data,validated_data,Validate input,Validation node,,Router,ErrorHandler
ComplexWorkflow,Router,Default,validated_data,routing_decision,Route data,Routing node,,ProcessorA,ProcessorB
ComplexWorkflow,ProcessorA,LLM,routing_decision,result_a,Process type A,Processor A node,Merger,,
ComplexWorkflow,ProcessorB,LLM,routing_decision,result_b,Process type B,Processor B node,Merger,,
ComplexWorkflow,Merger,Default,results,final_result,Merge results,Merger node,Output,,
ComplexWorkflow,Output,Default,final_result,output,Final output,Output node,,,
ComplexWorkflow,ErrorHandler,Default,error_data,error_output,Handle errors,Error node,,,
"""

