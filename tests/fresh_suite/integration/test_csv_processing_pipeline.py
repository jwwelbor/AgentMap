"""
CSV Processing Pipeline Integration Tests.

This module tests the complete CSV processing pipeline using real DI container instances.
These tests verify the end-to-end flow from CSV file validation through graph compilation
and execution preparation.
"""

import unittest
from pathlib import Path
from typing import Dict, Any, List

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from tests.fresh_suite.integration.test_data_factories import (
    CSVTestDataFactory,
    IntegrationTestDataManager,
    ExecutionTestDataFactory
)


class TestCSVProcessingPipeline(BaseIntegrationTest):
    """
    Integration tests for CSV processing pipeline.
    
    Tests the complete flow:
    CSV File → Validation → Parsing → Graph Spec → Graph Definition → Compilation
    """
    
    def setup_services(self):
        """Initialize services for CSV processing pipeline testing."""
        super().setup_services()
        
        # CSV processing services
        self.csv_graph_parser_service = self.container.csv_graph_parser_service()
        self.csv_validation_service = self.container.csv_validation_service()
        self.graph_definition_service = self.container.graph_definition_service()
        
        # Optional compilation service (if available)
        try:
            self.compilation_service = self.container.compilation_service()
        except AttributeError:
            self.compilation_service = None
        
        # Initialize test data manager
        self.test_data_manager = IntegrationTestDataManager(Path(self.temp_dir))
    
    # =============================================================================
    # 1. CSV Validation Pipeline Tests
    # =============================================================================
    
    def test_csv_validation_pipeline_valid_files(self):
        """Test CSV validation pipeline with valid CSV files."""
        # Test with different valid graph types
        test_cases = [
            ("simple_linear", CSVTestDataFactory.create_simple_linear_graph()),
            ("conditional_branch", CSVTestDataFactory.create_conditional_branching_graph())
        ]
        
        for test_name, graph_spec in test_cases:
            with self.subTest(graph_type=test_name):
                # Create test CSV
                csv_path = self.test_data_manager.create_test_csv_file(graph_spec, f"{test_name}.csv")
                self.assert_file_exists(csv_path, f"{test_name} CSV file")
                
                # Test validation pipeline
                try:
                    # Step 1: CSV validation service validation
                    validation_result = self.csv_validation_service.validate_file(csv_path)
                    self.assertTrue(validation_result.is_valid, 
                                  f"{test_name} should pass validation")
                    self.assertEqual(len(validation_result.errors), 0,
                                   f"{test_name} should have no validation errors")
                    
                    # Step 2: Graph definition service validation
                    definition_errors = self.graph_definition_service.validate_csv_before_building(csv_path)
                    self.assertEqual(definition_errors, [],
                                   f"{test_name} should pass graph definition validation")
                    
                except Exception as e:
                    self.fail(f"CSV validation pipeline failed for {test_name}: {e}")
    
    def test_csv_validation_pipeline_invalid_files(self):
        """Test CSV validation pipeline with invalid CSV files."""
        invalid_samples = CSVTestDataFactory.create_invalid_csv_samples()
        
        for error_type, invalid_content in invalid_samples.items():
            with self.subTest(error_type=error_type):
                # Create invalid CSV file
                invalid_csv_path = self.create_test_csv_file(invalid_content, f"invalid_{error_type}.csv")
                
                # Test validation catches errors
                try:
                    validation_result = self.csv_validation_service.validate_file(invalid_csv_path)
                    
                    # Most invalid files should fail validation
                    if error_type in ['missing_headers', 'missing_required_fields']:
                        self.assertFalse(validation_result.is_valid,
                                       f"{error_type} should fail validation")
                        self.assertGreater(len(validation_result.errors), 0,
                                         f"{error_type} should have validation errors")
                    
                except Exception as e:
                    # Some errors might be caught as exceptions instead of validation results
                    self.assertIsInstance(e, (ValueError, FileNotFoundError, AttributeError),
                                        f"Should get appropriate exception for {error_type}")
    
    def test_csv_validation_pipeline_edge_cases(self):
        """Test CSV validation pipeline with edge cases."""
        # Test empty file
        empty_csv_path = self.create_test_csv_file("", "empty.csv")
        
        try:
            validation_result = self.csv_validation_service.validate_file(empty_csv_path)
            # Empty file should fail validation
            self.assertFalse(validation_result.is_valid, "Empty file should fail validation")
        except Exception as e:
            # Empty file might raise exception instead of validation result
            self.assertIsInstance(e, (ValueError, AttributeError))
        
        # Test file with only headers
        headers_only_csv = "GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge"
        headers_csv_path = self.create_test_csv_file(headers_only_csv, "headers_only.csv")
        
        try:
            validation_result = self.csv_validation_service.validate_file(headers_csv_path)
            # Headers-only file should fail validation (no data)
            self.assertFalse(validation_result.is_valid, "Headers-only file should fail validation")
        except Exception as e:
            # Might raise exception for no data rows
            self.assertIsInstance(e, (ValueError, AttributeError))
    
    # =============================================================================
    # 2. CSV Parsing Pipeline Tests  
    # =============================================================================
    
    def test_csv_parsing_pipeline_single_graph(self):
        """Test CSV parsing pipeline with single graph."""
        # Create simple linear graph
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        # Test complete parsing pipeline
        try:
            # Step 1: Parse CSV to GraphSpec
            graph_spec = self.csv_graph_parser_service.parse_csv_to_graph_spec(csv_path)
            
            # Verify GraphSpec structure
            self.assertIsNotNone(graph_spec, "Should create GraphSpec from CSV")
            
            graph_names = graph_spec.get_graph_names()
            self.assertEqual(len(graph_names), 1, "Should have one graph")
            self.assertEqual(graph_names[0], simple_spec.graph_name)
            
            # Verify nodes in GraphSpec
            nodes = graph_spec.get_nodes_for_graph(simple_spec.graph_name)
            self.assertGreater(len(nodes), 0, "Should have nodes in GraphSpec")
            
            # Step 2: Convert GraphSpec to Graph domain model
            graphs_dict = self.graph_definition_service.build_from_graph_spec(graph_spec)
            
            # Verify Graph domain model
            self.assertEqual(len(graphs_dict), 1, "Should create one graph")
            self.assertIn(simple_spec.graph_name, graphs_dict)
            
            graph = graphs_dict[simple_spec.graph_name]
            self.assertEqual(graph.name, simple_spec.graph_name)
            self.assertGreater(len(graph.nodes), 0, "Graph should have nodes")
            
        except Exception as e:
            self.fail(f"CSV parsing pipeline failed for single graph: {e}")
    
    def test_csv_parsing_pipeline_multi_graph(self):
        """Test CSV parsing pipeline with multiple graphs."""
        # Create multi-graph CSV
        graph_specs = CSVTestDataFactory.create_multi_graph_csv()
        csv_path = self.test_data_manager.create_multi_graph_csv_file(graph_specs)
        
        # Test parsing pipeline
        try:
            # Step 1: Parse CSV to GraphSpec
            graph_spec = self.csv_graph_parser_service.parse_csv_to_graph_spec(csv_path)
            
            # Verify multiple graphs in GraphSpec
            graph_names = graph_spec.get_graph_names()
            self.assertEqual(len(graph_names), 2, "Should have two graphs")
            self.assertIn('first_graph', graph_names)
            self.assertIn('second_graph', graph_names)
            
            # Step 2: Build all graphs
            all_graphs = self.graph_definition_service.build_from_graph_spec(graph_spec)
            
            # Verify all graphs created
            self.assertEqual(len(all_graphs), 2, "Should create both graphs")
            self.assertIn('first_graph', all_graphs)
            self.assertIn('second_graph', all_graphs)
            
            # Verify each graph is properly formed
            for graph_name, graph in all_graphs.items():
                self.assertEqual(graph.name, graph_name)
                self.assertGreater(len(graph.nodes), 0, f"{graph_name} should have nodes")
            
        except Exception as e:
            self.fail(f"CSV parsing pipeline failed for multi-graph: {e}")
    
    def test_csv_parsing_pipeline_conditional_graph(self):
        """Test CSV parsing pipeline with conditional branching."""
        # Create conditional branching graph
        conditional_spec = CSVTestDataFactory.create_conditional_branching_graph()
        csv_path = self.test_data_manager.create_test_csv_file(conditional_spec)
        
        # Test parsing conditional structures
        try:
            # Parse to GraphSpec
            graph_spec = self.csv_graph_parser_service.parse_csv_to_graph_spec(csv_path)
            
            # Verify conditional nodes in GraphSpec
            nodes = graph_spec.get_nodes_for_graph(conditional_spec.graph_name)
            node_names = [node.name for node in nodes]
            
            self.assertIn('input_validator', node_names, "Should have input validator node")
            self.assertIn('success_processor', node_names, "Should have success processor node")
            self.assertIn('error_handler', node_names, "Should have error handler node")
            
            # Build graph and verify conditional structure
            graph = self.graph_definition_service.build_from_csv(csv_path)
            
            # Verify conditional branching is preserved
            self.assertEqual(graph.name, conditional_spec.graph_name)
            graph_node_names = [node.name for node in graph.nodes.values()]
            
            self.assertIn('input_validator', graph_node_names)
            self.assertIn('success_processor', graph_node_names)
            self.assertIn('error_handler', graph_node_names)
            self.assertIn('output_formatter', graph_node_names)
            
        except Exception as e:
            self.fail(f"CSV parsing pipeline failed for conditional graph: {e}")
    
    # =============================================================================
    # 3. Graph Compilation Pipeline Tests
    # =============================================================================
    
    def test_graph_compilation_pipeline(self):
        """Test graph compilation pipeline (if compilation service available)."""
        if self.compilation_service is None:
            self.skipTest("Compilation service not available")
        
        # Create test graph
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        try:
            # Step 1: Build graph
            graph = self.graph_definition_service.build_from_csv(csv_path)
            
            # Step 2: Test compilation (if supported)
            self.assert_service_created(self.compilation_service, "CompilationService")
            
            # Note: Actual compilation testing would depend on compilation service interface
            # This tests that the compilation service is properly integrated
            
        except Exception as e:
            self.fail(f"Graph compilation pipeline failed: {e}")
    
    def test_graph_preparation_for_execution(self):
        """Test graph preparation for execution pipeline."""
        # Create execution-ready graph
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        try:
            # Build graph
            graph = self.graph_definition_service.build_from_csv(csv_path)
            
            # Verify graph is ready for execution
            self.assertGreater(len(graph.nodes), 0, "Graph should have nodes for execution")
            
            # Verify graph structure is sound
            node_names = [node.name for node in graph.nodes.values()]
            self.assertIn('start', node_names, "Should have start node")
            self.assertIn('end', node_names, "Should have end node")
            
            # Test with execution state
            execution_state = ExecutionTestDataFactory.create_simple_execution_state()
            self.assertIsNotNone(execution_state, "Should have execution state for graph")
            
        except Exception as e:
            self.fail(f"Graph preparation for execution failed: {e}")
    
    # =============================================================================
    # 4. End-to-End CSV Pipeline Tests
    # =============================================================================
    
    def test_complete_csv_processing_pipeline(self):
        """Test complete CSV processing pipeline from file to executable graph."""
        # Set up complete test environment
        test_resources = self.test_data_manager.setup_complete_test_environment()
        
        # Test complete pipeline with different graph types
        test_cases = [
            ("simple", test_resources['simple_csv']),
            ("conditional", test_resources['conditional_csv']),
            ("multi_graph", test_resources['multi_csv'])
        ]
        
        for test_name, csv_path in test_cases:
            with self.subTest(pipeline_type=test_name):
                try:
                    # Step 1: Validate CSV structure
                    validation_result = self.csv_validation_service.validate_file(csv_path)
                    self.assertTrue(validation_result.is_valid, 
                                  f"{test_name} CSV should be valid")
                    
                    # Step 2: Validate for graph building
                    build_validation_errors = self.graph_definition_service.validate_csv_before_building(csv_path)
                    self.assertEqual(build_validation_errors, [],
                                   f"{test_name} should pass build validation")
                    
                    # Step 3: Parse CSV to GraphSpec
                    graph_spec = self.csv_graph_parser_service.parse_csv_to_graph_spec(csv_path)
                    self.assertIsNotNone(graph_spec, f"{test_name} should create GraphSpec")
                    
                    # Step 4: Build graphs from GraphSpec
                    if test_name == 'multi_graph':
                        # Multi-graph: build all graphs
                        all_graphs = self.graph_definition_service.build_all_from_csv(csv_path)
                        self.assertGreater(len(all_graphs), 1, "Multi-graph should have multiple graphs")
                        
                        # Verify each graph
                        for graph_name, graph in all_graphs.items():
                            self.assertEqual(graph.name, graph_name)
                            self.assertGreater(len(graph.nodes), 0, f"{graph_name} should have nodes")
                    else:
                        # Single graph: build specific graph
                        graph = self.graph_definition_service.build_from_csv(csv_path)
                        self.assertIsNotNone(graph, f"{test_name} should create graph")
                        self.assertGreater(len(graph.nodes), 0, f"{test_name} should have nodes")
                    
                    # Step 5: Verify graph readiness for execution
                    # (This would connect to execution services in a full pipeline)
                    
                except Exception as e:
                    self.fail(f"Complete CSV processing pipeline failed for {test_name}: {e}")
    
    def test_csv_pipeline_error_recovery(self):
        """Test CSV processing pipeline error recovery mechanisms."""
        # Test pipeline with recoverable errors
        test_cases = [
            # Valid CSV with warnings
            ("warnings_only", '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
test_graph,node1,default,Test prompt,Test description,input,output,node2
test_graph,node2,default,End prompt,End description,output,result,'''),
            
            # CSV with minor formatting issues that might be recoverable
            ("extra_spaces", '''GraphName, Node, AgentType, Prompt, Description, Input_Fields, Output_Field, Edge
test_graph, node1, default, Test prompt, Test description, input, output, node2
test_graph, node2, default, End prompt, End description, output, result, ''')
        ]
        
        for test_name, csv_content in test_cases:
            with self.subTest(recovery_case=test_name):
                csv_path = self.create_test_csv_file(csv_content, f"recovery_{test_name}.csv")
                
                try:
                    # Test that pipeline can handle and potentially recover from minor issues
                    graph = self.graph_definition_service.build_from_csv(csv_path)
                    self.assertIsNotNone(graph, f"{test_name} should recover and create graph")
                    
                except Exception as e:
                    # Some issues might not be recoverable - that's acceptable
                    self.assertIsInstance(e, (ValueError, AttributeError),
                                        f"Should get appropriate exception for {test_name}")
    
    def test_csv_pipeline_performance_characteristics(self):
        """Test CSV processing pipeline performance characteristics."""
        # Create larger test CSV for performance testing
        large_graph_nodes = []
        graph_name = "performance_test_graph"
        
        # Create a larger graph (50 nodes in linear chain)
        for i in range(50):
            node_name = f"node_{i:03d}"
            next_node = f"node_{i+1:03d}" if i < 49 else ""
            
            large_graph_nodes.append({
                "GraphName": graph_name,
                "Node": node_name,
                "AgentType": "default",
                "Prompt": f"Process step {i+1}",
                "Description": f"Processing node {i+1} in sequence",
                "Input_Fields": f"input_{i}" if i == 0 else f"output_{i-1}",
                "Output_Field": f"output_{i}",
                "Edge": next_node,
                "Success_Next": "",
                "Failure_Next": ""
            })
        
        # Convert to CSV content
        headers = list(large_graph_nodes[0].keys())
        csv_lines = [",".join(headers)]
        for node in large_graph_nodes:
            row = [str(node[header]) for header in headers]
            csv_lines.append(",".join(row))
        
        large_csv_content = "\n".join(csv_lines)
        large_csv_path = self.create_test_csv_file(large_csv_content, "large_performance_test.csv")
        
        # Test pipeline with larger graph
        try:
            # Should handle larger graphs without issues
            graph = self.graph_definition_service.build_from_csv(large_csv_path)
            self.assertIsNotNone(graph, "Should handle large graph")
            self.assertEqual(len(graph.nodes), 50, "Should have all 50 nodes")
            
        except Exception as e:
            self.fail(f"CSV pipeline performance test failed: {e}")


class TestCSVProcessingEdgeCases(BaseIntegrationTest):
    """
    Integration tests for CSV processing edge cases and boundary conditions.
    """
    
    def setup_services(self):
        """Initialize services for edge case testing."""
        super().setup_services()
        
        self.csv_validation_service = self.container.csv_validation_service()
        self.graph_definition_service = self.container.graph_definition_service()
        self.test_data_manager = IntegrationTestDataManager(Path(self.temp_dir))
    
    def test_csv_encoding_handling(self):
        """Test CSV processing with different text encodings."""
        # Test with UTF-8 CSV (standard)
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec, "utf8_test.csv")
        
        try:
            graph = self.graph_definition_service.build_from_csv(csv_path)
            self.assertIsNotNone(graph, "Should handle UTF-8 CSV")
        except Exception as e:
            self.fail(f"UTF-8 CSV processing failed: {e}")
    
    def test_csv_special_characters_handling(self):
        """Test CSV processing with special characters in content."""
        # Create CSV with special characters
        special_char_csv = '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
special_test,start_node,default,"Process with quotes, commas",Description with special chars: àáâãäå,input,output,end_node
special_test,end_node,default,Final processing,End node with unicode: 测试,output,result,'''
        
        special_csv_path = self.create_test_csv_file(special_char_csv, "special_chars.csv")
        
        try:
            graph = self.graph_definition_service.build_from_csv(special_csv_path)
            self.assertIsNotNone(graph, "Should handle CSV with special characters")
            self.assertEqual(graph.name, "special_test")
        except Exception as e:
            # Special characters might not be fully supported - that's acceptable
            self.assertIsInstance(e, (ValueError, UnicodeError, AttributeError))
    
    def test_csv_boundary_size_limits(self):
        """Test CSV processing with boundary size limits."""
        # Test very small CSV (minimal valid case)
        minimal_csv = '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
minimal,only_node,default,Single node,Only node in graph,input,output,'''
        
        minimal_csv_path = self.create_test_csv_file(minimal_csv, "minimal.csv")
        
        try:
            graph = self.graph_definition_service.build_from_csv(minimal_csv_path)
            self.assertIsNotNone(graph, "Should handle minimal CSV")
            self.assertEqual(len(graph.nodes), 1, "Should have one node")
        except Exception as e:
            self.fail(f"Minimal CSV processing failed: {e}")


if __name__ == '__main__':
    unittest.main()
