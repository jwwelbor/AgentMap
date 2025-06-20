"""
Enhanced unit tests for GraphBuilderService.

This file enhances the existing GraphBuilderService tests to achieve 90%+ coverage
by adding comprehensive testing of internal methods, edge cases, and error conditions.
"""

import unittest
from unittest.mock import Mock, mock_open, patch
from pathlib import Path
from typing import Dict, Any, List
import csv
from io import StringIO

from agentmap.services.graph_builder_service import GraphBuilderService
from agentmap.models.graph import Graph
from agentmap.models.node import Node
from agentmap.exceptions.graph_exceptions import InvalidEdgeDefinitionError
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphBuilderServiceEnhanced(unittest.TestCase):
    """Enhanced unit tests for GraphBuilderService with comprehensive coverage."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        
        # Initialize GraphBuilderService with mocked dependencies
        self.service = GraphBuilderService(
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
    
    # =============================================================================
    # 1. Service Initialization Tests (Enhanced)
    # =============================================================================
    
    def test_service_initialization_complete(self):
        """Test comprehensive service initialization verification."""
        # Verify all dependencies are stored correctly
        self.assertEqual(self.service.config, self.mock_app_config_service)
        self.assertIsNotNone(self.service.logger)
        
        # Verify logger configuration
        self.assertEqual(self.service.logger.name, 'GraphBuilderService')
        
        # Verify dependency injection calls
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.service)
        
        # Verify initialization logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == 'info']
        self.assertTrue(any('[GraphBuilderService] Initialized' in call[1] 
                          for call in info_calls))
    
    # =============================================================================
    # 2. CSV Processing Tests (Comprehensive)
    # =============================================================================
    
    def test_create_nodes_from_csv_comprehensive(self):
        """Test _create_nodes_from_csv() with comprehensive CSV data."""
        # Create comprehensive CSV content
        csv_content = '''GraphName,Node,Context,AgentType,Input_Fields,Output_Field,Prompt,Description
test_graph,input_node,input_context,input,field1|field2,output1,"Input prompt","Input description"
test_graph,process_node,process_context,processor,field3,output2,"Process prompt","Process description"
test_graph,output_node,,default,,output3,"Output prompt","Output description"
another_graph,start_node,start_context,starter,start_field,start_output,"Start prompt","Start description"'''
        
        # Mock CSV file operations
        with patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            result = self.service._create_nodes_from_csv(Path('test.csv'))
            
            # Verify multiple graphs were created
            self.assertEqual(len(result), 2)
            self.assertIn('test_graph', result)
            self.assertIn('another_graph', result)
            
            # Verify test_graph nodes
            test_graph = result['test_graph']
            self.assertEqual(len(test_graph), 3)
            
            # Verify input_node details
            input_node = test_graph['input_node']
            self.assertEqual(input_node.name, 'input_node')
            self.assertEqual(input_node.agent_type, 'input')
            self.assertEqual(input_node.inputs, ['field1', 'field2'])
            self.assertEqual(input_node.output, 'output1')
            self.assertEqual(input_node.prompt, 'Input prompt')
            self.assertEqual(input_node.description, 'Input description')
            self.assertEqual(input_node.context, {'context': 'input_context'})
            
            # Verify another_graph was created
            another_graph = result['another_graph']
            self.assertEqual(len(another_graph), 1)
            start_node = another_graph['start_node']
            self.assertEqual(start_node.name, 'start_node')
            self.assertEqual(start_node.agent_type, 'starter')
    
    def test_create_nodes_from_csv_edge_cases(self):
        """Test _create_nodes_from_csv() handles edge cases."""
        # CSV with empty values and special characters
        csv_content = '''GraphName,Node,Context,AgentType,Input_Fields,Output_Field,Prompt,Description
edge_graph,"node with spaces",,,"",,"Prompt with ""quotes""","Description, with commas"
edge_graph,node_minimal,,,,,,"Minimal node"
edge_graph,node_unicode,unicode_context,unicode_agent,unicode_field,unicode_output,"Unicode: ñáéíóú","Unicode description: 中文"'''
        
        with patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            result = self.service._create_nodes_from_csv(Path('edge.csv'))
            
            edge_graph = result['edge_graph']
            
            # Verify node with spaces
            spaced_node = edge_graph['node with spaces']
            self.assertEqual(spaced_node.name, 'node with spaces')
            self.assertEqual(spaced_node.agent_type, 'Default')  # Default when empty
            self.assertEqual(spaced_node.inputs, [])  # Empty when no input fields
            
            # Verify minimal node
            minimal_node = edge_graph['node_minimal']
            self.assertEqual(minimal_node.name, 'node_minimal')
            self.assertIsNone(minimal_node.context)  # None when no context
            
            # Verify unicode handling
            unicode_node = edge_graph['node_unicode']
            self.assertEqual(unicode_node.prompt, 'Unicode: ñáéíóú')
            self.assertEqual(unicode_node.description, 'Unicode description: 中文')
    
    def test_create_nodes_from_csv_logging_verification(self):
        """Test _create_nodes_from_csv() logging behavior."""
        csv_content = '''GraphName,Node,Context,AgentType,Input_Fields,Output_Field,Prompt,Description
log_graph,log_node,log_context,log_agent,log_input,log_output,"Log prompt","Log description"'''
        
        with patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            self.service._create_nodes_from_csv(Path('log.csv'))
            
            # Verify row processing logging
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == 'info']
            debug_calls = [call for call in logger_calls if call[0] == 'debug']
            
            # Should log total rows processed
            self.assertTrue(any('Processed 1 rows' in call[1] for call in info_calls))
            
            # Should log node creation details
            self.assertTrue(any("Processing: Graph='log_graph'" in call[1] for call in debug_calls))
    
    def test_create_nodes_from_csv_missing_required_fields(self):
        """Test _create_nodes_from_csv() handles missing required fields."""
        # CSV with missing required fields
        csv_content = '''GraphName,Node,Context,AgentType,Input_Fields,Output_Field,Prompt,Description
,missing_graph_node,context,agent,input,output,"Prompt","Description"
missing_node_graph,,context,agent,input,output,"Prompt","Description"'''
        
        with patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            result = self.service._create_nodes_from_csv(Path('missing.csv'))
            
            # Should skip rows with missing required fields
            self.assertEqual(len(result), 0)
            
            # Verify warning logging for missing fields
            logger_calls = self.mock_logger.calls
            warning_calls = [call for call in logger_calls if call[0] == 'warning']
            
            self.assertTrue(any('Missing GraphName' in call[1] for call in warning_calls))
            self.assertTrue(any('Missing Node' in call[1] for call in warning_calls))
    
    # =============================================================================
    # 3. Node Creation Tests (Internal Method Coverage)
    # =============================================================================
    
    def test_create_node_comprehensive(self):
        """Test _create_node() method comprehensively."""
        graph = {}
        
        # Test creating a comprehensive node
        result_node = self.service._create_node(
            graph=graph,
            node_name="comprehensive_node",
            context="detailed_context",
            agent_type="comprehensive_agent",
            input_fields=["input1", "input2", "input3"],
            output_field="comprehensive_output",
            prompt="This is a comprehensive prompt for testing purposes",
            description="Comprehensive node description for testing"
        )
        
        # Verify node was created and added to graph
        self.assertIn("comprehensive_node", graph)
        self.assertEqual(result_node, graph["comprehensive_node"])
        
        # Verify all node properties
        node = graph["comprehensive_node"]
        self.assertEqual(node.name, "comprehensive_node")
        self.assertEqual(node.context, {"context": "detailed_context"})
        self.assertEqual(node.agent_type, "comprehensive_agent")
        self.assertEqual(node.inputs, ["input1", "input2", "input3"])
        self.assertEqual(node.output, "comprehensive_output")
        self.assertEqual(node.prompt, "This is a comprehensive prompt for testing purposes")
        self.assertEqual(node.description, "Comprehensive node description for testing")
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        trace_calls = [call for call in logger_calls if call[0] == 'trace']
        debug_calls = [call for call in logger_calls if call[0] == 'debug']
        
        self.assertTrue(any("Creating Node: node_name: comprehensive_node" in call[1] 
                          for call in trace_calls))
        self.assertTrue(any("Created Node: comprehensive_node" in call[1] 
                          for call in debug_calls))
    
    def test_create_node_defaults_and_edge_cases(self):
        """Test _create_node() with defaults and edge cases."""
        graph = {}
        
        # Test with minimal parameters
        minimal_node = self.service._create_node(
            graph=graph,
            node_name="minimal_node",
            context="",  # Empty context
            agent_type="",  # Empty agent type (should default)
            input_fields=[],  # Empty input fields
            output_field="",  # Empty output field
            prompt="",  # Empty prompt
            description=None  # None description
        )
        
        # Verify defaults are applied
        self.assertEqual(minimal_node.agent_type, "Default")  # Should default to "Default"
        self.assertIsNone(minimal_node.context)  # Empty context becomes None
        self.assertEqual(minimal_node.inputs, [])
        self.assertEqual(minimal_node.output, "")
        self.assertEqual(minimal_node.prompt, "")
        self.assertIsNone(minimal_node.description)
    
    def test_create_node_duplicate_handling(self):
        """Test _create_node() duplicate node handling."""
        graph = {}
        
        # Create initial node
        first_node = self.service._create_node(
            graph=graph,
            node_name="duplicate_test",
            context="first_context",
            agent_type="first_agent",
            input_fields=["first_input"],
            output_field="first_output",
            prompt="First prompt",
            description="First description"
        )
        
        # Attempt to create duplicate node
        second_node = self.service._create_node(
            graph=graph,
            node_name="duplicate_test",  # Same name
            context="second_context",
            agent_type="second_agent",
            input_fields=["second_input"],
            output_field="second_output",
            prompt="Second prompt",
            description="Second description"
        )
        
        # Should return the same node (first one created)
        self.assertEqual(first_node, second_node)
        self.assertEqual(len(graph), 1)
        
        # Original node properties should be unchanged
        node = graph["duplicate_test"]
        self.assertEqual(node.context, {"context": "first_context"})
        self.assertEqual(node.agent_type, "first_agent")
        
        # Verify skip logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == 'debug']
        self.assertTrue(any("Node duplicate_test already exists, skipping creation" in call[1] 
                          for call in debug_calls))
    
    # =============================================================================
    # 4. Edge Connection Tests (Internal Methods)
    # =============================================================================
    
    def test_connect_direct_edge_successful(self):
        """Test _connect_direct_edge() successful connection."""
        # Create mock nodes
        source_node = Mock()
        source_node.add_edge = Mock()
        target_node = Mock()
        
        graph = {
            "source": source_node,
            "target": target_node
        }
        
        # Execute edge connection
        self.service._connect_direct_edge(graph, "source", "target", "test_graph")
        
        # Verify edge was added
        source_node.add_edge.assert_called_once_with("default", "target")
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == 'debug']
        self.assertTrue(any("🔗 source --default--> target" in call[1] 
                          for call in debug_calls))
    
    def test_connect_direct_edge_target_not_found(self):
        """Test _connect_direct_edge() with missing target node."""
        source_node = Mock()
        graph = {"source": source_node}
        
        # Should raise ValueError for missing target
        with self.assertRaises(ValueError) as context:
            self.service._connect_direct_edge(graph, "source", "missing_target", "test_graph")
        
        error_msg = str(context.exception)
        self.assertIn("Edge target 'missing_target' is not defined as a node", error_msg)
        self.assertIn("test_graph", error_msg)
        
        # Verify error logging
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == 'error']
        self.assertTrue(any("Edge target 'missing_target' not defined" in call[1] 
                          for call in error_calls))
    
    def test_connect_success_edge_successful(self):
        """Test _connect_success_edge() successful connection."""
        source_node = Mock()
        source_node.add_edge = Mock()
        target_node = Mock()
        
        graph = {
            "source": source_node,
            "success_target": target_node
        }
        
        self.service._connect_success_edge(graph, "source", "success_target", "test_graph")
        
        # Verify success edge was added
        source_node.add_edge.assert_called_once_with("success", "success_target")
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == 'debug']
        self.assertTrue(any("🔗 source --success--> success_target" in call[1] 
                          for call in debug_calls))
    
    def test_connect_failure_edge_successful(self):
        """Test _connect_failure_edge() successful connection."""
        source_node = Mock()
        source_node.add_edge = Mock()
        target_node = Mock()
        
        graph = {
            "source": source_node,
            "failure_target": target_node
        }
        
        self.service._connect_failure_edge(graph, "source", "failure_target", "test_graph")
        
        # Verify failure edge was added
        source_node.add_edge.assert_called_once_with("failure", "failure_target")
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == 'debug']
        self.assertTrue(any("🔗 source --failure--> failure_target" in call[1] 
                          for call in debug_calls))
    
    def test_connect_nodes_with_edges_conflict_detection(self):
        """Test _connect_nodes_with_edges() detects edge conflicts."""
        # Create CSV content with conflicting edge definitions
        csv_content = '''GraphName,Node,Edge,Success_Next,Failure_Next
conflict_graph,conflict_node,direct_target,success_target,failure_target'''
        
        # Create mock graphs to pass to edge connection
        conflict_node = Mock()
        graphs = {
            "conflict_graph": {
                "conflict_node": conflict_node,
                "direct_target": Mock(),
                "success_target": Mock(),
                "failure_target": Mock()
            }
        }
        
        with patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            # Should raise InvalidEdgeDefinitionError
            with self.assertRaises(InvalidEdgeDefinitionError) as context:
                self.service._connect_nodes_with_edges(graphs, Path('conflict.csv'))
            
            error_msg = str(context.exception)
            self.assertIn("conflict_node", error_msg)
            self.assertIn("both Edge and Success/Failure defined", error_msg)
    
    def test_connect_nodes_with_edges_successful_combinations(self):
        """Test _connect_nodes_with_edges() with various valid edge combinations."""
        # CSV with different valid edge combinations
        csv_content = '''GraphName,Node,Edge,Success_Next,Failure_Next
edge_graph,direct_node,target_node,,
edge_graph,success_node,,success_target,
edge_graph,failure_node,,,failure_target
edge_graph,both_conditional_node,,success_target,failure_target
edge_graph,target_node,,,
edge_graph,success_target,,,
edge_graph,failure_target,,,'''
        
        # Create mock nodes
        graphs = {
            "edge_graph": {
                "direct_node": Mock(),
                "success_node": Mock(),
                "failure_node": Mock(),
                "both_conditional_node": Mock(),
                "target_node": Mock(),
                "success_target": Mock(),
                "failure_target": Mock()
            }
        }
        
        # Mock the individual edge connection methods
        with patch.object(self.service, '_connect_direct_edge') as mock_direct, \
             patch.object(self.service, '_connect_success_edge') as mock_success, \
             patch.object(self.service, '_connect_failure_edge') as mock_failure, \
             patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            
            self.service._connect_nodes_with_edges(graphs, Path('edge.csv'))
            
            # Verify appropriate connections were made
            mock_direct.assert_called_once_with(
                graphs["edge_graph"], "direct_node", "target_node", "edge_graph"
            )
            
            # Should have two success edge calls
            success_calls = mock_success.call_args_list
            self.assertEqual(len(success_calls), 2)
            
            # Should have two failure edge calls  
            failure_calls = mock_failure.call_args_list
            self.assertEqual(len(failure_calls), 2)
    
    # =============================================================================
    # 5. Domain Model Conversion Tests
    # =============================================================================
    
    def test_convert_to_domain_models_comprehensive(self):
        """Test _convert_to_domain_models() comprehensive conversion."""
        # Create raw graphs with multiple nodes and relationships
        node1 = Node(name="start", agent_type="starter", inputs=["input"], output="output1")
        node2 = Node(name="middle", agent_type="processor", inputs=["output1"], output="output2")
        node3 = Node(name="end", agent_type="finalizer", inputs=["output2"], output="final")
        
        # Set up edges to test entry point detection
        node1.add_edge("default", "middle")
        node2.add_edge("success", "end")
        
        raw_graphs = {
            "comprehensive_graph": {
                "start": node1,
                "middle": node2,
                "end": node3
            },
            "simple_graph": {
                "single_node": Node(name="single_node", agent_type="simple")
            }
        }
        
        # Execute conversion
        result = self.service._convert_to_domain_models(raw_graphs)
        
        # Verify comprehensive_graph conversion
        self.assertIn("comprehensive_graph", result)
        comp_graph = result["comprehensive_graph"]
        self.assertIsInstance(comp_graph, Graph)
        self.assertEqual(comp_graph.name, "comprehensive_graph")
        self.assertEqual(len(comp_graph.nodes), 3)
        
        # Verify nodes are properly stored
        self.assertIn("start", comp_graph.nodes)
        self.assertIn("middle", comp_graph.nodes)
        self.assertIn("end", comp_graph.nodes)
        
        # Verify entry point detection (start node has no incoming edges)
        self.assertEqual(comp_graph.entry_point, "start")
        
        # Verify simple_graph conversion
        simple_graph = result["simple_graph"]
        self.assertEqual(simple_graph.entry_point, "single_node")
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == 'debug']
        self.assertTrue(any("Converted graph 'comprehensive_graph' with 3 nodes" in call[1] 
                          for call in debug_calls))
    
    def test_detect_entry_point_scenarios(self):
        """Test _detect_entry_point() various scenarios."""
        # Scenario 1: Clear single entry point
        graph1 = Graph(name="clear_entry")
        node1 = Node(name="entry", agent_type="starter")
        node2 = Node(name="middle", agent_type="processor")
        node1.add_edge("default", "middle")
        
        graph1.nodes = {"entry": node1, "middle": node2}
        self.service._detect_entry_point(graph1)
        self.assertEqual(graph1.entry_point, "entry")
        
        # Scenario 2: Multiple entry point candidates (alphabetical selection)
        graph2 = Graph(name="multiple_entries")
        node_z = Node(name="z_node", agent_type="starter")
        node_a = Node(name="a_node", agent_type="starter")
        
        graph2.nodes = {"z_node": node_z, "a_node": node_a}
        self.service._detect_entry_point(graph2)
        self.assertEqual(graph2.entry_point, "a_node")  # Alphabetically first
        
        # Verify warning logging for multiple candidates
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == 'warning']
        self.assertTrue(any("Multiple entry point candidates" in call[1] 
                          for call in warning_calls))
        
        # Scenario 3: Circular references (no clear entry point)
        graph3 = Graph(name="circular")
        node_x = Node(name="x_node", agent_type="circular")
        node_y = Node(name="y_node", agent_type="circular")
        node_x.add_edge("default", "y_node")
        node_y.add_edge("default", "x_node")
        
        graph3.nodes = {"x_node": node_x, "y_node": node_y}
        self.service._detect_entry_point(graph3)
        
        # Should use first node when no clear entry point
        self.assertIn(graph3.entry_point, ["x_node", "y_node"])
        
        # Verify warning logging for circular references
        warning_calls = [call for call in logger_calls if call[0] == 'warning']
        self.assertTrue(any("No clear entry point found" in call[1] 
                          for call in warning_calls))
    
    # =============================================================================
    # 6. CSV Field Handling Tests
    # =============================================================================
    
    def test_safe_get_csv_field_comprehensive(self):
        """Test _safe_get_csv_field() comprehensive field handling."""
        # Test with normal row
        normal_row = {
            "existing_field": "value",
            "empty_field": "",
            "none_field": None
        }
        
        # Test existing field
        result = self.service._safe_get_csv_field(normal_row, "existing_field")
        self.assertEqual(result, "value")
        
        # Test empty field
        result = self.service._safe_get_csv_field(normal_row, "empty_field")
        self.assertEqual(result, "")
        
        # Test None field (should return default)
        result = self.service._safe_get_csv_field(normal_row, "none_field")
        self.assertEqual(result, "")
        
        # Test missing field with default
        result = self.service._safe_get_csv_field(normal_row, "missing_field", "default_value")
        self.assertEqual(result, "default_value")
        
        # Test missing field with no default
        result = self.service._safe_get_csv_field(normal_row, "missing_field")
        self.assertEqual(result, "")
    
    def test_safe_get_csv_field_edge_cases(self):
        """Test _safe_get_csv_field() edge cases."""
        # Test with None row
        result = self.service._safe_get_csv_field({}, "any_field", "fallback")
        self.assertEqual(result, "fallback")
        
        # Test with numeric values (should convert to string)
        numeric_row = {"number_field": 123, "float_field": 45.67}
        result = self.service._safe_get_csv_field(numeric_row, "number_field")
        self.assertEqual(result, 123)  # Should preserve type for non-None values
        
        result = self.service._safe_get_csv_field(numeric_row, "float_field")
        self.assertEqual(result, 45.67)
    
    # =============================================================================
    # 7. Validation Enhancement Tests
    # =============================================================================
    
    def test_validate_csv_before_building_comprehensive_validation(self):
        """Test validate_csv_before_building() comprehensive validation scenarios."""
        # Valid CSV content
        valid_csv = '''GraphName,Node,AgentType,Input_Fields,Output_Field
valid_graph,valid_node,valid_agent,valid_input,valid_output'''
        
        with patch('agentmap.services.graph_builder_service.Path') as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.open.return_value = StringIO(valid_csv)
            mock_path_class.return_value = mock_path
            
            errors = self.service.validate_csv_before_building(Path('valid.csv'))
            
            # Should return no errors for valid CSV
            self.assertEqual(errors, [])
    
    def test_validate_csv_before_building_multiple_validation_errors(self):
        """Test validate_csv_before_building() with multiple validation errors."""
        # Invalid CSV with multiple issues
        invalid_csv = '''WrongColumn,AnotherWrong
,
invalid_graph,'''
        
        with patch('agentmap.services.graph_builder_service.Path') as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.open.return_value = StringIO(invalid_csv)
            mock_path_class.return_value = mock_path
            
            errors = self.service.validate_csv_before_building(Path('invalid.csv'))
            
            # Should detect multiple errors
            self.assertTrue(len(errors) > 0)
            
            # Should detect missing required columns
            self.assertTrue(any("Missing required columns" in error for error in errors))
    
    def test_validate_csv_before_building_file_reading_exceptions(self):
        """Test validate_csv_before_building() handles file reading exceptions."""
        with patch('agentmap.services.graph_builder_service.Path') as mock_path_class:
            mock_path = Mock()
            mock_path.exists.return_value = True
            mock_path.open.side_effect = IOError("File read error")
            mock_path_class.return_value = mock_path
            
            errors = self.service.validate_csv_before_building(Path('error.csv'))
            
            # Should handle exception gracefully
            self.assertTrue(len(errors) > 0)
            self.assertTrue(any("Error reading CSV file" in error for error in errors))
    
    # =============================================================================
    # 8. Integration and End-to-End Tests
    # =============================================================================
    
    def test_build_all_from_csv_complex_integration(self):
        """Test build_all_from_csv() with complex multi-graph CSV."""
        # Complex CSV with multiple graphs and various edge types
        complex_csv = '''GraphName,Node,Context,AgentType,Input_Fields,Output_Field,Prompt,Description,Edge,Success_Next,Failure_Next
workflow_a,start_a,context_a,starter,input_a,output_a,"Start A","Start node for workflow A",,process_a,error_a
workflow_a,process_a,context_proc,processor,output_a,result_a,"Process A","Processing node",,finish_a,error_a
workflow_a,finish_a,context_fin,finalizer,result_a,final_a,"Finish A","Final node",,,
workflow_a,error_a,context_err,error_handler,error_info,error_result,"Error A","Error handling",,,
workflow_b,start_b,context_b,starter,input_b,output_b,"Start B","Start node for workflow B",end_b,,
workflow_b,end_b,context_end,ender,output_b,final_b,"End B","End node",,,'''
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.open', mock_open(read_data=complex_csv)):
            
            result = self.service.build_all_from_csv(Path('complex.csv'))
            
            # Verify multiple graphs were built
            self.assertEqual(len(result), 2)
            self.assertIn('workflow_a', result)
            self.assertIn('workflow_b', result)
            
            # Verify workflow_a structure
            workflow_a = result['workflow_a']
            self.assertEqual(len(workflow_a.nodes), 4)
            
            # Verify complex edge relationships in workflow_a
            start_node = workflow_a.nodes['start_a']
            self.assertIn('success', start_node.edges)
            self.assertIn('failure', start_node.edges)
            self.assertEqual(start_node.edges['success'], 'process_a')
            self.assertEqual(start_node.edges['failure'], 'error_a')
            
            # Verify workflow_b structure with direct edges
            workflow_b = result['workflow_b']
            self.assertEqual(len(workflow_b.nodes), 2)
            start_b_node = workflow_b.nodes['start_b']
            self.assertIn('default', start_b_node.edges)
            self.assertEqual(start_b_node.edges['default'], 'end_b')
            
            # Verify entry point detection
            self.assertEqual(workflow_a.entry_point, 'start_a')
            self.assertEqual(workflow_b.entry_point, 'start_b')
    
    def test_build_from_csv_performance_logging(self):
        """Test build_from_csv() performance and detailed logging."""
        csv_content = '''GraphName,Node,Context,AgentType,Input_Fields,Output_Field,Prompt,Description
perf_graph,perf_node1,context1,agent1,input1,output1,"Prompt 1","Description 1"
perf_graph,perf_node2,context2,agent2,input2,output2,"Prompt 2","Description 2"
perf_graph,perf_node3,context3,agent3,input3,output3,"Prompt 3","Description 3"'''
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.open', mock_open(read_data=csv_content)):
            
            result = self.service.build_from_csv(Path('perf.csv'), 'perf_graph')
            
            # Verify result structure
            self.assertIsInstance(result, Graph)
            self.assertEqual(result.name, 'perf_graph')
            self.assertEqual(len(result.nodes), 3)
            
            # Verify comprehensive logging was performed
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == 'info']
            
            # Should log start of building
            self.assertTrue(any('Building single graph from' in call[1] for call in info_calls))
            
            # Should log successful completion with graph count
            self.assertTrue(any('Successfully built' in call[1] and 'perf_graph' in call[1] 
                              for call in info_calls))
    
    # =============================================================================
    # 9. Error Recovery and Resilience Tests
    # =============================================================================
    
    def test_service_handles_malformed_csv_gracefully(self):
        """Test service handles malformed CSV data gracefully."""
        # Malformed CSV with inconsistent columns
        malformed_csv = '''GraphName,Node,ExtraColumn
graph1,node1,extra1,unexpected_extra
graph1,node2,extra2
graph1'''  # Incomplete row
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.open', mock_open(read_data=malformed_csv)):
            
            # Should handle malformed CSV without crashing
            result = self.service.build_all_from_csv(Path('malformed.csv'))
            
            # Should still process valid rows
            self.assertIsInstance(result, dict)
            
            # May have partial data or empty result depending on CSV parsing behavior
            # The important thing is that it doesn't crash
    
    def test_service_handles_large_graph_efficiently(self):
        """Test service handles large graphs efficiently."""
        # Generate large CSV content programmatically
        large_csv_lines = ['GraphName,Node,Context,AgentType,Input_Fields,Output_Field,Prompt,Description']
        
        # Create 100 nodes for stress testing
        for i in range(100):
            large_csv_lines.append(
                f'large_graph,node_{i:03d},context_{i},agent_{i % 5},input_{i},output_{i},'
                f'"Prompt for node {i}","Description for node {i}"'
            )
        
        large_csv = '\n'.join(large_csv_lines)
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.open', mock_open(read_data=large_csv)):
            
            # Should handle large graph without performance issues
            result = self.service.build_all_from_csv(Path('large.csv'))
            
            # Verify large graph was built correctly
            self.assertIn('large_graph', result)
            large_graph = result['large_graph']
            self.assertEqual(len(large_graph.nodes), 100)
            
            # Verify logging indicates processing completion
            logger_calls = self.mock_logger.calls
            info_calls = [call for call in logger_calls if call[0] == 'info']
            self.assertTrue(any('Successfully built 1 graph(s)' in call[1] for call in info_calls))


if __name__ == '__main__':
    unittest.main()
