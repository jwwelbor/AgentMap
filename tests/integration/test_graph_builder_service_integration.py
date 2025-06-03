"""
Integration tests for GraphBuilderService.

These tests use real dependencies and real CSV files to verify the service
works correctly in realistic scenarios, following existing integration test patterns.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from agentmap.services.graph_builder_service import GraphBuilderService
from agentmap.models.graph import Graph
from agentmap.models.node import Node


class TestGraphBuilderServiceIntegration(unittest.TestCase):
    """Integration tests for GraphBuilderService with real dependencies."""
    
    def setUp(self):
        """Set up test fixtures with real dependencies."""
        # Create real but minimal dependencies for integration testing
        self.logging_service = Mock()
        self.logger = Mock()
        self.logging_service.get_class_logger.return_value = self.logger
        
        self.config_service = Mock()
        
        # Create service instance
        self.service = GraphBuilderService(
            logging_service=self.logging_service,
            app_config_service=self.config_service
        )
    
    def create_test_csv_file(self, content: str) -> Path:
        """Helper method to create temporary CSV file with content."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_file.write(content)
        temp_file.close()
        return Path(temp_file.name)
    
    def test_real_csv_parsing_simple_workflow(self):
        """Test parsing a real simple workflow CSV."""
        csv_content = """GraphName,Node,AgentType,Input_Fields,Output_Field,Prompt,Description,Edge,Success_Next,Failure_Next
SimpleWorkflow,DataInput,Input,user_data,processed_data,Collect user input,Input collection node,DataProcessor,,
SimpleWorkflow,DataProcessor,LLM,processed_data,analysis_result,Analyze the data,Data processing node,,Success,Failure
SimpleWorkflow,Success,Output,analysis_result,final_output,Return successful result,Success output node,,,
SimpleWorkflow,Failure,Output,analysis_result,error_output,Return error result,Failure output node,,,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            # Test building all graphs
            result = self.service.build_all_from_csv(csv_path)
            
            # Verify basic structure
            self.assertEqual(len(result), 1)
            self.assertIn("SimpleWorkflow", result)
            
            workflow = result["SimpleWorkflow"]
            self.assertIsInstance(workflow, Graph)
            self.assertEqual(workflow.name, "SimpleWorkflow")
            self.assertEqual(len(workflow.nodes), 4)
            
            # Verify nodes exist
            expected_nodes = ["DataInput", "DataProcessor", "Success", "Failure"]
            for node_name in expected_nodes:
                self.assertIn(node_name, workflow.nodes)
                self.assertIsInstance(workflow.nodes[node_name], Node)
            
            # Verify entry point detection
            self.assertEqual(workflow.entry_point, "DataInput")
            
            # Verify node properties
            data_input = workflow.nodes["DataInput"]
            self.assertEqual(data_input.agent_type, "Input")
            self.assertEqual(data_input.inputs, ["user_data"])
            self.assertEqual(data_input.output, "processed_data")
            self.assertEqual(data_input.description, "Input collection node")
            
            # Verify edges
            self.assertEqual(data_input.edges["default"], "DataProcessor")
            
            data_processor = workflow.nodes["DataProcessor"]
            self.assertEqual(data_processor.edges["success"], "Success")
            self.assertEqual(data_processor.edges["failure"], "Failure")
            self.assertTrue(data_processor.has_conditional_routing())
            
        finally:
            csv_path.unlink()
    
    def test_real_csv_parsing_multiple_graphs(self):
        """Test parsing CSV with multiple distinct graphs."""
        csv_content = """GraphName,Node,AgentType,Edge,Success_Next,Failure_Next
UserRegistration,ValidateInput,Validation,ProcessInput,,
UserRegistration,ProcessInput,LLM,,Success,Failure
UserRegistration,Success,Output,,,
UserRegistration,Failure,Output,,,
DataAnalysis,LoadData,Input,AnalyzeData,,
DataAnalysis,AnalyzeData,LLM,GenerateReport,,
DataAnalysis,GenerateReport,Output,,,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            result = self.service.build_all_from_csv(csv_path)
            
            # Verify multiple graphs
            self.assertEqual(len(result), 2)
            self.assertIn("UserRegistration", result)
            self.assertIn("DataAnalysis", result)
            
            # Verify UserRegistration graph
            user_reg = result["UserRegistration"]
            self.assertEqual(len(user_reg.nodes), 4)
            self.assertEqual(user_reg.entry_point, "ValidateInput")
            
            # Verify DataAnalysis graph
            data_analysis = result["DataAnalysis"]
            self.assertEqual(len(data_analysis.nodes), 3)
            self.assertEqual(data_analysis.entry_point, "LoadData")
            
            # Verify graphs are independent
            self.assertNotEqual(user_reg.nodes, data_analysis.nodes)
            
        finally:
            csv_path.unlink()
    
    def test_build_specific_graph_from_multi_graph_csv(self):
        """Test building a specific graph from CSV containing multiple graphs."""
        csv_content = """GraphName,Node,AgentType,Edge
Graph1,Start1,LLM,End1
Graph1,End1,Output,
Graph2,Start2,Input,End2
Graph2,End2,LLM,
Graph3,Start3,Validation,End3
Graph3,End3,Output,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            # Test building specific graph
            result = self.service.build_from_csv(csv_path, graph_name="Graph2")
            
            self.assertIsInstance(result, Graph)
            self.assertEqual(result.name, "Graph2")
            self.assertEqual(len(result.nodes), 2)
            self.assertIn("Start2", result.nodes)
            self.assertIn("End2", result.nodes)
            self.assertEqual(result.entry_point, "Start2")
            
        finally:
            csv_path.unlink()
    
    """
    ComplexWorkflow
    Start → Router
    Router → PathA/PathB (conditional)
    PathA → SubA1/SubA2 (conditional)
    SubA1, SubA2, PathB → MergePoint
    MergePoint → Success/Failure (conditional)
    """   
    def test_complex_routing_scenarios(self):
        """Test complex routing scenarios with mixed edge types."""
        csv_content = """GraphName,Node,AgentType,Edge,Success_Next,Failure_Next,Input_Fields,Output_Field
ComplexWorkflow,Start,Input,Router,,,input,initial_data
ComplexWorkflow,Router,LLM,,PathA,PathB,initial_data,routing_decision
ComplexWorkflow,PathA,Processing,,SubA1,SubA2,routing_decision,path_a_result
ComplexWorkflow,SubA1,LLM,MergePoint,,,path_a_result,sub_a1_output
ComplexWorkflow,SubA2,LLM,MergePoint,,,path_a_result,sub_a2_output
ComplexWorkflow,PathB,Processing,MergePoint,,,routing_decision,path_b_result
ComplexWorkflow,MergePoint,LLM,,Success,Failure,final_input,final_result
ComplexWorkflow,Success,Output,,,,final_result,success_output
ComplexWorkflow,Failure,Output,,,,final_result,failure_output
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            result = self.service.build_all_from_csv(csv_path)
            workflow = result["ComplexWorkflow"]
            
            # Verify complex structure
            self.assertEqual(len(workflow.nodes), 9)
            self.assertEqual(workflow.entry_point, "Start")
            
            # Verify different routing types
            router = workflow.nodes["Router"]
            self.assertEqual(router.edges["success"], "PathA")
            self.assertEqual(router.edges["failure"], "PathB")
            
            path_a = workflow.nodes["PathA"]
            self.assertEqual(path_a.edges["success"], "SubA1")
            self.assertEqual(path_a.edges["failure"], "SubA2")
            
            # Verify convergence point
            sub_a1 = workflow.nodes["SubA1"]
            path_b = workflow.nodes["PathB"]
            self.assertEqual(sub_a1.edges["default"], "MergePoint")
            self.assertEqual(path_b.edges["default"], "MergePoint")
            
        finally:
            csv_path.unlink()
    
    def test_validation_integration_with_real_errors(self):
        """Test validation integration with real error scenarios."""
        # Test missing required fields
        invalid_csv = """GraphName,Node,WrongColumn
TestGraph,Node1,Value1
"""
        
        csv_path = self.create_test_csv_file(invalid_csv)
        
        try:
            errors = self.service.validate_csv_before_building(csv_path)
            self.assertTrue(len(errors) > 0)
            self.assertTrue(any("Missing required columns" in error for error in errors))
            
        finally:
            csv_path.unlink()
    
    def test_edge_case_empty_fields(self):
        """Test handling of empty and missing fields in real CSV."""
        csv_content = """GraphName,Node,AgentType,Input_Fields,Output_Field,Prompt,Description,Edge
TestGraph,Start,,,"",Test prompt,"",End
TestGraph,End,Default,,,,,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            result = self.service.build_all_from_csv(csv_path)
            graph = result["TestGraph"]
            
            start_node = graph.nodes["Start"]
            
            # Verify empty fields are handled correctly
            self.assertEqual(start_node.agent_type, "Default")  # Should use default
            self.assertEqual(start_node.inputs, [])  # Empty list for empty input fields
            self.assertEqual(start_node.output, "")  # Empty string preserved
            self.assertEqual(start_node.prompt, "Test prompt")  # Non-empty preserved
            self.assertEqual(start_node.description, "")  # Empty string preserved
            
        finally:
            csv_path.unlink()
    
    def test_context_field_integration(self):
        """Test integration of context field parsing."""
        csv_content = """GraphName,Node,Context,AgentType
TestGraph,WithContext,This is context data,LLM
TestGraph,WithoutContext,,Default
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            result = self.service.build_all_from_csv(csv_path)
            graph = result["TestGraph"]
            
            # Verify context handling
            with_context = graph.nodes["WithContext"]
            self.assertEqual(with_context.context, {"context": "This is context data"})
            
            without_context = graph.nodes["WithoutContext"]
            self.assertIsNone(without_context.context)
            
        finally:
            csv_path.unlink()
    
    def test_input_fields_parsing_integration(self):
        """Test parsing of pipe-separated input fields."""
        csv_content = """GraphName,Node,Input_Fields
TestGraph,SingleInput,single_field
TestGraph,MultipleInputs,field1|field2|field3
TestGraph,EmptyInputs,
TestGraph,SpacedInputs," field1 | field2 | field3 "
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            result = self.service.build_all_from_csv(csv_path)
            graph = result["TestGraph"]
            
            # Verify input field parsing
            single = graph.nodes["SingleInput"]
            self.assertEqual(single.inputs, ["single_field"])
            
            multiple = graph.nodes["MultipleInputs"]
            self.assertEqual(multiple.inputs, ["field1", "field2", "field3"])
            
            empty = graph.nodes["EmptyInputs"]
            self.assertEqual(empty.inputs, [])
            
            spaced = graph.nodes["SpacedInputs"]
            self.assertEqual(spaced.inputs, ["field1", "field2", "field3"])
            
        finally:
            csv_path.unlink()
    
    def test_logging_integration(self):
        """Test that logging integration works correctly."""
        csv_content = """GraphName,Node,AgentType
TestGraph,Node1,LLM
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            # Reset mock to verify calls
            self.logger.reset_mock()
            
            result = self.service.build_all_from_csv(csv_path)
            
            # Verify logging calls were made
            self.logger.info.assert_called()
            self.logger.debug.assert_called()
            
            # Verify specific important log messages
            info_calls = [call[0][0] for call in self.logger.info.call_args_list]
            self.assertTrue(any("Building all graphs from" in msg for msg in info_calls))
            self.assertTrue(any("Successfully built" in msg for msg in info_calls))
            
        finally:
            csv_path.unlink()
    
    def test_error_handling_integration(self):
        """Test error handling with real error scenarios."""
        # Test with invalid edge target
        csv_content = """GraphName,Node,Edge
TestGraph,Start,NonExistentTarget
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            with self.assertRaises(ValueError) as context:
                self.service.build_all_from_csv(csv_path)
            
            # Verify error message contains useful information
            error_msg = str(context.exception)
            self.assertIn("NonExistentTarget", error_msg)
            self.assertIn("not defined as a node", error_msg)
            self.assertIn("TestGraph", error_msg)
            
            # Verify error was logged
            self.logger.error.assert_called()
            
        finally:
            csv_path.unlink()


if __name__ == '__main__':
    unittest.main()
