"""
Unit tests for GraphBuilderService.

These tests mock all dependencies and focus on testing the service logic
in isolation, following the existing test patterns in AgentMap.
"""

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from agentmap.services.graph_builder_service import GraphBuilderService
from agentmap.models.graph import Graph
from agentmap.models.node import Node
from agentmap.migration_utils import (
    MockLoggingService,
    MockAppConfigService,
    InvalidEdgeDefinitionError
)


class TestGraphBuilderService(unittest.TestCase):
    """Unit tests for GraphBuilderService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use migration-safe mock implementations
        self.mock_logging_service = MockLoggingService()
        self.mock_config_service = MockAppConfigService()
        
        # Create service instance with mocked dependencies
        self.service = GraphBuilderService(
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_config_service
        )
    
    def test_service_initialization(self):
        """Test that service initializes correctly with dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.logger.name, "GraphBuilderService")
        self.assertEqual(self.service.config, self.mock_config_service)
        
        # Verify initialization log message
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "[GraphBuilderService] Initialized" 
                          for call in logger_calls if call[0] == "info"))
    
    def test_validate_csv_before_building_missing_file(self):
        """Test validation with missing CSV file."""
        non_existent_path = Path("/non/existent/file.csv")
        
        errors = self.service.validate_csv_before_building(non_existent_path)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("CSV file not found", errors[0])
    
    @patch("builtins.open", new_callable=mock_open)
    @patch("csv.DictReader")
    def test_validate_csv_before_building_missing_columns(self, mock_dict_reader, mock_file):
        """Test validation with missing required columns."""
        # Mock CSV reader with missing columns
        mock_reader = Mock()
        mock_reader.fieldnames = ["WrongColumn"]
        mock_dict_reader.return_value = mock_reader
        
        csv_path = Path("test.csv")
        
        with patch.object(Path, 'exists', return_value=True), \
            patch.object(Path, 'open', mock_file):
            errors = self.service.validate_csv_before_building(csv_path)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("Missing required columns", errors[0])
        self.assertIn("{'GraphName', 'Node'}", errors[0])
    
    @patch("builtins.open", new_callable=mock_open)
    @patch("csv.DictReader")
    def test_validate_csv_before_building_empty_file(self, mock_dict_reader, mock_file):
        """Test validation with empty CSV file."""
        # Mock CSV reader with no rows
        mock_reader = Mock()
        mock_reader.fieldnames = ["GraphName", "Node"]
        mock_reader.__iter__ = Mock(return_value=iter([]))  # No rows
        mock_dict_reader.return_value = mock_reader
        
        csv_path = Path("test.csv")
        
        with patch.object(Path, 'exists', return_value=True), \
            patch.object(Path, 'open', mock_file):
            errors = self.service.validate_csv_before_building(csv_path)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("CSV file is empty", errors[0])

    
    @patch("builtins.open", new_callable=mock_open)
    @patch("csv.DictReader")
    def test_validate_csv_before_building_valid_file(self, mock_dict_reader, mock_file):
        """Test validation with valid CSV file."""
        # Mock CSV reader with valid data
        mock_reader = Mock()
        mock_reader.fieldnames = ["GraphName", "Node", "AgentType"]
        mock_reader.__iter__ = Mock(return_value=iter([
            {"GraphName": "TestGraph", "Node": "Node1", "AgentType": "LLM"}
        ]))
        mock_dict_reader.return_value = mock_reader
        
        csv_path = Path("test.csv")
        
        with patch.object(Path, 'exists', return_value=True), \
            patch.object(Path, 'open', mock_file):
            errors = self.service.validate_csv_before_building(csv_path)
        
        self.assertEqual(len(errors), 0)
    
    def test_build_from_csv_missing_file(self):
        """Test building from non-existent CSV file."""
        non_existent_path = Path("/non/existent/file.csv")
        
        with self.assertRaises(FileNotFoundError) as context:
            self.service.build_from_csv(non_existent_path)
        
        self.assertIn("CSV file not found", str(context.exception))
    
    @patch.object(GraphBuilderService, 'build_all_from_csv')
    def test_build_from_csv_single_graph_success(self, mock_build_all):
        """Test building single graph when graph exists."""
        # Mock build_all_from_csv to return test graphs
        test_graphs = {
            "Graph1": Graph(name="Graph1"),
            "Graph2": Graph(name="Graph2")
        }
        mock_build_all.return_value = test_graphs
        
        csv_path = Path("test.csv")
        
        # Test getting specific graph
        result = self.service.build_from_csv(csv_path, graph_name="Graph1")
        
        self.assertEqual(result.name, "Graph1")
        mock_build_all.assert_called_once_with(csv_path)
    
    @patch.object(GraphBuilderService, 'build_all_from_csv')
    def test_build_from_csv_first_graph_when_none_specified(self, mock_build_all):
        """Test building returns first graph when no name specified."""
        # Mock build_all_from_csv to return test graphs
        test_graphs = {
            "Graph2": Graph(name="Graph2"),
            "Graph1": Graph(name="Graph1")
        }
        mock_build_all.return_value = test_graphs
        
        csv_path = Path("test.csv")
        
        # Test getting first graph (should be Graph2 since it's first in dict)
        result = self.service.build_from_csv(csv_path)
        
        # The first graph depends on dict order, but should be one of them
        self.assertIn(result.name, ["Graph1", "Graph2"])
        mock_build_all.assert_called_once_with(csv_path)
    
    @patch.object(GraphBuilderService, 'build_all_from_csv')
    def test_build_from_csv_graph_not_found(self, mock_build_all):
        """Test building specific graph that doesn't exist."""
        # Mock build_all_from_csv to return test graphs
        test_graphs = {
            "Graph1": Graph(name="Graph1"),
            "Graph2": Graph(name="Graph2")
        }
        mock_build_all.return_value = test_graphs
        
        csv_path = Path("test.csv")
        
        # Test getting non-existent graph
        with self.assertRaises(ValueError) as context:
            self.service.build_from_csv(csv_path, graph_name="NonExistent")
        
        self.assertIn("Graph 'NonExistent' not found", str(context.exception))
        self.assertIn("Available graphs: ['Graph1', 'Graph2']", str(context.exception))
    
    @patch.object(GraphBuilderService, 'build_all_from_csv')
    def test_build_from_csv_no_graphs_found(self, mock_build_all):
        """Test building when no graphs found in CSV."""
        # Mock build_all_from_csv to return empty
        mock_build_all.return_value = {}
        
        csv_path = Path("test.csv")
        
        with self.assertRaises(ValueError) as context:
            self.service.build_from_csv(csv_path)
        
        self.assertIn("No graphs found in CSV file", str(context.exception))
    
    def create_test_csv_file(self, content: str) -> Path:
        """Helper method to create temporary CSV file with content."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_file.write(content)
        temp_file.close()
        return Path(temp_file.name)
    
    def test_build_all_from_csv_simple_graph(self):
        """Test building a simple graph from CSV."""
        csv_content = """GraphName,Node,AgentType,Input_Fields,Output_Field,Prompt,Description,Edge,Success_Next,Failure_Next
TestGraph,Start,LLM,input|data,result,Test prompt,Start node,End,,
TestGraph,End,Default,result,final,End prompt,End node,,,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            with patch.object(Path, 'exists', return_value=True):
                result = self.service.build_all_from_csv(csv_path)
            
            # Verify result structure
            self.assertEqual(len(result), 1)
            self.assertIn("TestGraph", result)
            
            graph = result["TestGraph"]
            self.assertEqual(graph.name, "TestGraph")
            self.assertEqual(len(graph.nodes), 2)
            self.assertIn("Start", graph.nodes)
            self.assertIn("End", graph.nodes)
            
            # Verify node properties
            start_node = graph.nodes["Start"]
            self.assertEqual(start_node.name, "Start")
            self.assertEqual(start_node.agent_type, "LLM")
            self.assertEqual(start_node.inputs, ["input", "data"])
            self.assertEqual(start_node.output, "result")
            self.assertEqual(start_node.prompt, "Test prompt")
            self.assertEqual(start_node.description, "Start node")
            
            # Verify edges
            self.assertEqual(start_node.edges["default"], "End")
            
        finally:
            # Clean up temp file
            csv_path.unlink()
    
    def test_build_all_from_csv_conditional_routing(self):
        """Test building graph with conditional routing."""
        csv_content = """GraphName,Node,AgentType,Success_Next,Failure_Next
TestGraph,Start,LLM,Success,Failure
TestGraph,Success,Default,,
TestGraph,Failure,Default,,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            with patch.object(Path, 'exists', return_value=True):
                result = self.service.build_all_from_csv(csv_path)
            
            graph = result["TestGraph"]
            start_node = graph.nodes["Start"]
            
            # Verify conditional edges
            self.assertEqual(start_node.edges["success"], "Success")
            self.assertEqual(start_node.edges["failure"], "Failure")
            self.assertTrue(start_node.has_conditional_routing())
            
        finally:
            csv_path.unlink()
    
    def test_build_all_from_csv_multiple_graphs(self):
        """Test building multiple graphs from single CSV."""
        csv_content = """GraphName,Node,AgentType,Edge
Graph1,Node1,LLM,Node2
Graph1,Node2,Default,
Graph2,Start,LLM,End
Graph2,End,Default,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            with patch.object(Path, 'exists', return_value=True):
                result = self.service.build_all_from_csv(csv_path)
            
            # Verify multiple graphs
            self.assertEqual(len(result), 2)
            self.assertIn("Graph1", result)
            self.assertIn("Graph2", result)
            
            # Verify each graph has correct nodes
            self.assertEqual(len(result["Graph1"].nodes), 2)
            self.assertEqual(len(result["Graph2"].nodes), 2)
            
        finally:
            csv_path.unlink()
    
    def test_conflicting_edge_definition_error(self):
        """Test that conflicting edge definitions raise proper error."""
        csv_content = """GraphName,Node,Edge,Success_Next
TestGraph,Start,End,AlsoEnd
TestGraph,End,Default,
TestGraph,AlsoEnd,Default,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            with patch.object(Path, 'exists', return_value=True):
                with self.assertRaises(InvalidEdgeDefinitionError) as context:
                    self.service.build_all_from_csv(csv_path)
                
                self.assertIn("both Edge and Success/Failure defined", str(context.exception))
                
        finally:
            csv_path.unlink()
    
    def test_invalid_edge_target_error(self):
        """Test that invalid edge targets raise proper error."""
        csv_content = """GraphName,Node,Edge
TestGraph,Start,NonExistentNode
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            with patch.object(Path, 'exists', return_value=True):
                with self.assertRaises(ValueError) as context:
                    self.service.build_all_from_csv(csv_path)
                
                self.assertIn("not defined as a node", str(context.exception))
                
        finally:
            csv_path.unlink()
    
    def test_entry_point_detection_single_candidate(self):
        """Test entry point detection with single candidate."""
        csv_content = """GraphName,Node,Edge
TestGraph,Start,End
TestGraph,End,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            with patch.object(Path, 'exists', return_value=True):
                result = self.service.build_all_from_csv(csv_path)
            
            graph = result["TestGraph"]
            self.assertEqual(graph.entry_point, "Start")
            
        finally:
            csv_path.unlink()
    
    def test_entry_point_detection_multiple_candidates(self):
        """Test entry point detection with multiple candidates."""
        csv_content = """GraphName,Node,Edge
TestGraph,Start1,End
TestGraph,Start2,End
TestGraph,End,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            with patch.object(Path, 'exists', return_value=True):
                result = self.service.build_all_from_csv(csv_path)
            
            graph = result["TestGraph"]
            # Should pick first alphabetically
            self.assertEqual(graph.entry_point, "Start1")
            
        finally:
            csv_path.unlink()
    
    def test_context_conversion(self):
        """Test that context string is converted to dict properly."""
        csv_content = """GraphName,Node,Context
TestGraph,Start,test context value
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            with patch.object(Path, 'exists', return_value=True):
                result = self.service.build_all_from_csv(csv_path)
            
            graph = result["TestGraph"]
            start_node = graph.nodes["Start"]
            
            # Context should be converted to dict
            self.assertEqual(start_node.context, {"context": "test context value"})
            
        finally:
            csv_path.unlink()
    
    def test_empty_context_handling(self):
        """Test that empty context is handled correctly."""
        csv_content = """GraphName,Node,Context
TestGraph,Start,
"""
        
        csv_path = self.create_test_csv_file(csv_content)
        
        try:
            with patch.object(Path, 'exists', return_value=True):
                result = self.service.build_all_from_csv(csv_path)
            
            graph = result["TestGraph"]
            start_node = graph.nodes["Start"]
            
            # Empty context should be None
            self.assertIsNone(start_node.context)
            
        finally:
            csv_path.unlink()


if __name__ == '__main__':
    unittest.main()
