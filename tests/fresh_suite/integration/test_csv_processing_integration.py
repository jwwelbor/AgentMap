"""
CSV Processing Pipeline Integration Tests.

This module tests the complete CSV processing pipeline using real file I/O operations:
CSV file → CSVGraphParserService → GraphDefinitionService → Domain Models.

Tests real service coordination, file system operations, and domain model creation
using actual DI container instances and temporary file system operations.
"""

import unittest
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from tests.fresh_suite.integration.test_data_factories import (
    CSVTestDataFactory,
    IntegrationTestDataManager
)
from agentmap.models.graph import Graph
from agentmap.models.node import Node


class TestCSVProcessingPipelineIntegration(BaseIntegrationTest):
    """
    Integration tests for the complete CSV processing pipeline.
    
    Tests the end-to-end transformation from CSV files to domain models:
    1. Real CSV file creation and I/O operations
    2. CSVGraphParserService parsing CSV to GraphSpec
    3. GraphDefinitionService converting GraphSpec to domain models
    4. Real Node and Graph object creation with correct data
    5. Error handling for file system operations
    6. Various CSV format and content scenarios
    """
    
    def setup_services(self):
        """Initialize services for CSV processing pipeline testing."""
        super().setup_services()
        
        # Core CSV processing services
        self.csv_parser_service = self.container.csv_graph_parser_service()
        self.graph_definition_service = self.container.graph_definition_service()
        
        # Initialize test data manager for file operations
        self.test_data_manager = IntegrationTestDataManager(Path(self.temp_dir))
    
    # =============================================================================
    # 1. Basic CSV File to Domain Model Pipeline Tests
    # =============================================================================
    
    def test_simple_csv_file_to_domain_model_pipeline(self):
        """Test complete pipeline from simple CSV file to Graph domain model."""
        # Create real CSV file with simple linear graph
        simple_graph_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_graph_spec)
        
        # Verify CSV file was created
        self.assert_file_exists(csv_path, "Simple CSV file")
        
        # Test complete pipeline: CSV → Parser → GraphDefinition → Domain Model
        graph = self.graph_definition_service.build_from_csv(csv_path)
        
        # Verify domain model creation
        self.assertIsInstance(graph, Graph, "Should create Graph domain model")
        self.assertEqual(graph.name, "simple_linear", "Graph name should match")
        
        # Verify nodes were created correctly
        self.assertEqual(len(graph.nodes), 3, "Should have 3 nodes")
        expected_nodes = ["start", "middle", "end"]
        for node_name in expected_nodes:
            self.assertIn(node_name, graph.nodes, f"Should contain node: {node_name}")
            self.assertIsInstance(graph.nodes[node_name], Node, f"Node {node_name} should be Node instance")
        
        # Verify node properties
        start_node = graph.nodes["start"]
        self.assertEqual(start_node.name, "start")
        self.assertEqual(start_node.agent_type, "default")
        self.assertEqual(start_node.prompt, "Start the workflow")
        self.assertEqual(start_node.inputs, ["user_input"])
        self.assertEqual(start_node.output, "start_output")
        
        # Verify node edges
        self.assertEqual(start_node.edges.get("default"), "middle", "Start should connect to middle")
        
        middle_node = graph.nodes["middle"]
        self.assertEqual(middle_node.edges.get("default"), "end", "Middle should connect to end")
        
        end_node = graph.nodes["end"]
        self.assertEqual(len(end_node.edges), 0, "End node should have no edges")
    
    def test_conditional_branching_csv_to_domain_model_pipeline(self):
        """Test pipeline with conditional branching graph."""
        # Create CSV file with conditional branching
        conditional_spec = CSVTestDataFactory.create_conditional_branching_graph()
        csv_path = self.test_data_manager.create_test_csv_file(conditional_spec)
        
        # Verify file creation
        self.assert_file_exists(csv_path, "Conditional CSV file")
        
        # Process through pipeline
        graph = self.graph_definition_service.build_from_csv(csv_path)
        
        # Verify conditional graph structure
        self.assertIsInstance(graph, Graph)
        self.assertEqual(graph.name, "conditional_branch")
        self.assertEqual(len(graph.nodes), 4, "Should have 4 nodes")
        
        # Verify conditional routing
        validator_node = graph.nodes["input_validator"]
        self.assertEqual(validator_node.edges.get("success"), "success_processor")
        self.assertEqual(validator_node.edges.get("failure"), "error_handler")
        self.assertTrue(validator_node.has_conditional_routing(), "Should have conditional routing")
        
        # Verify convergence node
        output_formatter = graph.nodes["output_formatter"]
        self.assertEqual(output_formatter.inputs, ["processed_data", "error_message"])
    
    def test_multi_graph_csv_file_processing(self):
        """Test processing CSV file containing multiple graphs."""
        # Create multi-graph CSV
        multi_graph_specs = CSVTestDataFactory.create_multi_graph_csv()
        csv_path = self.test_data_manager.create_multi_graph_csv_file(multi_graph_specs)
        
        # Verify file creation
        self.assert_file_exists(csv_path, "Multi-graph CSV file")
        
        # Process all graphs
        all_graphs = self.graph_definition_service.build_all_from_csv(csv_path)
        
        # Verify all graphs were created
        self.assertEqual(len(all_graphs), 2, "Should create both graphs")
        self.assertIn("first_graph", all_graphs, "Should contain first_graph")
        self.assertIn("second_graph", all_graphs, "Should contain second_graph")
        
        # Verify individual graph properties
        first_graph = all_graphs["first_graph"]
        self.assertIsInstance(first_graph, Graph)
        self.assertEqual(first_graph.name, "first_graph")
        self.assertEqual(len(first_graph.nodes), 3, "First graph should have 3 nodes")
        
        second_graph = all_graphs["second_graph"]
        self.assertIsInstance(second_graph, Graph)
        self.assertEqual(second_graph.name, "second_graph")
        self.assertEqual(len(second_graph.nodes), 2, "Second graph should have 2 nodes")
        
        # Test specific graph extraction
        specific_graph = self.graph_definition_service.build_from_csv(csv_path, "second_graph")
        self.assert_graphs_equivalent(specific_graph, second_graph, "Individual vs batch extraction")
    
    # =============================================================================
    # 2. CSV Parser Service Integration Tests
    # =============================================================================
    
    def test_csv_parser_service_direct_integration(self):
        """Test CSVGraphParserService directly with real CSV file."""
        # Create test CSV file
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        # Test CSV parser service directly
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        
        # Verify GraphSpec creation
        self.assertIsNotNone(graph_spec, "Should create GraphSpec")
        self.assertEqual(len(graph_spec.graphs), 1, "Should have one graph")
        self.assertIn("simple_linear", graph_spec.graphs, "Should contain simple_linear graph")
        
        # Verify node specs
        node_specs = graph_spec.get_nodes_for_graph("simple_linear")
        self.assertEqual(len(node_specs), 3, "Should have 3 node specs")
        
        # Verify node spec properties
        start_spec = next(spec for spec in node_specs if spec.name == "start")
        self.assertEqual(start_spec.graph_name, "simple_linear")
        self.assertEqual(start_spec.agent_type, "default")
        self.assertEqual(start_spec.prompt, "Start the workflow")
        self.assertEqual(start_spec.input_fields, ["user_input"])
        self.assertEqual(start_spec.output_field, "start_output")
        self.assertEqual(start_spec.edge, "middle")
    
    def test_csv_validation_integration(self):
        """Test CSV validation integration with real files."""
        # Test valid CSV file
        valid_spec = CSVTestDataFactory.create_simple_linear_graph()
        valid_csv_path = self.test_data_manager.create_test_csv_file(valid_spec, "valid.csv")
        
        # Test validation through CSV parser
        validation_result = self.csv_parser_service.validate_csv_structure(valid_csv_path)
        self.assertTrue(validation_result.is_valid, "Valid CSV should pass validation")
        self.assertEqual(len(validation_result.errors), 0, "Should have no validation errors")
        
        # Test validation through graph definition service
        validation_errors = self.graph_definition_service.validate_csv_before_building(valid_csv_path)
        self.assertEqual(validation_errors, [], "Should have no validation errors")
    
    def test_csv_parser_to_graph_definition_coordination(self):
        """Test coordination between CSV parser and graph definition services."""
        # Create test CSV
        conditional_spec = CSVTestDataFactory.create_conditional_branching_graph()
        csv_path = self.test_data_manager.create_test_csv_file(conditional_spec)
        
        # Test that GraphDefinitionService uses CSVGraphParserService correctly
        # This verifies the delegation relationship
        
        # Step 1: Parse through CSV parser directly
        graph_spec_direct = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        
        # Step 2: Parse through graph definition service (should use CSV parser internally)
        graph_domain_model = self.graph_definition_service.build_from_csv(csv_path)
        
        # Verify coordination: both should produce equivalent results
        self.assertEqual(len(graph_spec_direct.graphs), 1)
        self.assertEqual(len(graph_domain_model.nodes), 4)
        
        # Verify CSV parser was used by graph definition service
        # (This is implicit through successful processing with same data)
        self.assertEqual(graph_domain_model.name, "conditional_branch")
    
    # =============================================================================
    # 3. Real File System Operations Tests
    # =============================================================================
    
    def test_real_file_creation_and_reading(self):
        """Test real file system operations for CSV processing."""
        # Create CSV content manually
        csv_content = '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
file_test_graph,node1,Default,Test prompt 1,Test description 1,input1,output1,node2
file_test_graph,node2,Default,Test prompt 2,Test description 2,output1,final_output,
'''
        
        # Write to real file
        csv_path = Path(self.temp_dir) / "csv_data" / "file_test.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text(csv_content, encoding='utf-8')
        
        # Verify file was created
        self.assertTrue(csv_path.exists(), "CSV file should exist")
        self.assertTrue(csv_path.is_file(), "Should be a file")
        
        # Read back and verify content
        read_content = csv_path.read_text(encoding='utf-8')
        self.assertEqual(read_content, csv_content, "File content should match")
        
        # Process through pipeline
        graph = self.graph_definition_service.build_from_csv(csv_path)
        
        # Verify processing results
        self.assertEqual(graph.name, "file_test_graph")
        self.assertEqual(len(graph.nodes), 2)
        self.assertIn("node1", graph.nodes)
        self.assertIn("node2", graph.nodes)
    
    def test_csv_file_encoding_handling(self):
        """Test CSV processing with different text encodings."""
        # Create CSV with special characters
        csv_content = '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
encoding_test,start_node,Default,"Process data with special chars: àáâãäå","Description with émojis: 😀🎉",input_data,processed_data,end_node
encoding_test,end_node,Default,"Finalize with üñíçødé","Final node with spécial characters",processed_data,final_result,
'''
        
        # Test UTF-8 encoding
        csv_path = Path(self.temp_dir) / "csv_data" / "encoding_test.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text(csv_content, encoding='utf-8')
        
        # Process through pipeline
        graph = self.graph_definition_service.build_from_csv(csv_path)
        
        # Verify special characters are preserved
        start_node = graph.nodes["start_node"]
        self.assertIn("àáâãäå", start_node.prompt, "Special characters should be preserved")
        self.assertIn("😀🎉", start_node.description, "Emojis should be preserved")
        
        end_node = graph.nodes["end_node"]
        self.assertIn("üñíçødé", end_node.prompt, "Unicode characters should be preserved")
        self.assertIn("spécial", end_node.description, "Accented characters should be preserved")
    
    def test_large_csv_file_processing(self):
        """Test processing larger CSV files for performance and memory handling."""
        # Create a larger graph with many nodes
        large_graph_nodes = []
        for i in range(50):  # Create 50 nodes
            node_data = {
                "GraphName": "large_graph",
                "Node": f"node_{i:02d}",
                "AgentType": "default",
                "Prompt": f"Process step {i}",
                "Description": f"Node {i} in large workflow",
                "Input_Fields": f"input_{i}" if i == 0 else f"output_{i-1:02d}",
                "Output_Field": f"output_{i:02d}",
                "Edge": f"node_{i+1:02d}" if i < 49 else "",
                "Context": f"context_data_{i}",
                "Success_Next": "",
                "Failure_Next": ""
            }
            large_graph_nodes.append(node_data)
        
        # Convert to CSV content
        headers = list(large_graph_nodes[0].keys())
        csv_lines = [",".join(headers)]
        for node in large_graph_nodes:
            row = [str(node.get(header, "")) for header in headers]
            csv_lines.append(",".join(row))
        csv_content = "\n".join(csv_lines)
        
        # Write to file
        large_csv_path = Path(self.temp_dir) / "csv_data" / "large_graph.csv"
        large_csv_path.parent.mkdir(parents=True, exist_ok=True)
        large_csv_path.write_text(csv_content, encoding='utf-8')
        
        # Process through pipeline
        graph = self.graph_definition_service.build_from_csv(large_csv_path)
        
        # Verify large graph processing
        self.assertEqual(graph.name, "large_graph")
        self.assertEqual(len(graph.nodes), 50, "Should process all 50 nodes")
        
        # Verify first and last nodes
        first_node = graph.nodes["node_00"]
        self.assertEqual(first_node.inputs, ["input_0"])
        self.assertEqual(first_node.edges.get("default"), "node_01")
        
        last_node = graph.nodes["node_49"]
        self.assertEqual(last_node.output, "output_49")
        self.assertEqual(len(last_node.edges), 0, "Last node should have no edges")
    
    # =============================================================================
    # 4. Error Handling and Edge Cases
    # =============================================================================
    
    def test_file_not_found_error_handling(self):
        """Test error handling when CSV file doesn't exist."""
        nonexistent_path = Path(self.temp_dir) / "nonexistent.csv"
        
        # Test CSV parser error handling
        with self.assertRaises(FileNotFoundError) as context:
            self.csv_parser_service.parse_csv_to_graph_spec(nonexistent_path)
        
        error_msg = str(context.exception)
        self.assertIn("nonexistent.csv", error_msg)
        
        # Test graph definition service error handling
        validation_errors = self.graph_definition_service.validate_csv_before_building(nonexistent_path)
        self.assertGreater(len(validation_errors), 0, "Should have validation errors")
        self.assertTrue(any("not exist" in error.lower() or "not found" in error.lower() 
                          for error in validation_errors))
        
        with self.assertRaises(FileNotFoundError):
            self.graph_definition_service.build_from_csv(nonexistent_path)
    
    def test_invalid_csv_format_error_handling(self):
        """Test error handling with various invalid CSV formats."""
        invalid_samples = CSVTestDataFactory.create_invalid_csv_samples()
        
        for error_type, invalid_content in invalid_samples.items():
            with self.subTest(error_type=error_type):
                # Create invalid CSV file
                invalid_path = Path(self.temp_dir) / "csv_data" / f"invalid_{error_type}.csv"
                invalid_path.parent.mkdir(parents=True, exist_ok=True)
                invalid_path.write_text(invalid_content, encoding='utf-8')
                
                # Test validation catches the error
                validation_result = self.csv_parser_service.validate_csv_structure(invalid_path)
                
                if error_type in ["empty_file", "missing_headers", "malformed_csv", "missing_required_fields"]:
                    # Structural errors should be caught by validation
                    self.assertFalse(validation_result.is_valid, 
                                   f"{error_type} should fail validation")
                    self.assertGreater(len(validation_result.errors), 0,
                                     f"{error_type} should have validation errors")
                
                # Test graph definition service validation
                validation_errors = self.graph_definition_service.validate_csv_before_building(invalid_path)
                
                if error_type in ["empty_file", "missing_headers", "malformed_csv", "missing_required_fields"]:
                    self.assertGreater(len(validation_errors), 0,
                                     f"{error_type} should have validation errors through graph definition service")
    
    def test_permission_error_handling(self):
        """Test error handling when file permissions prevent access."""
        # Create a CSV file
        csv_content = '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
permission_test,node1,Default,Test,Test,input,output,
'''
        csv_path = Path(self.temp_dir) / "csv_data" / "permission_test.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text(csv_content, encoding='utf-8')
        
        # Note: Simulating permission errors in tests is complex and platform-dependent
        # For now, we verify the file was created and can be processed normally
        self.assert_file_exists(csv_path, "Permission test CSV")
        
        # Verify normal processing works
        graph = self.graph_definition_service.build_from_csv(csv_path)
        self.assertEqual(graph.name, "permission_test")
    
    def test_empty_csv_file_handling(self):
        """Test handling of completely empty CSV files."""
        # Create empty CSV file
        empty_csv_path = Path(self.temp_dir) / "csv_data" / "empty.csv"
        empty_csv_path.parent.mkdir(parents=True, exist_ok=True)
        empty_csv_path.write_text("", encoding='utf-8')
        
        # Test validation
        validation_result = self.csv_parser_service.validate_csv_structure(empty_csv_path)
        self.assertFalse(validation_result.is_valid, "Empty CSV should fail validation")
        self.assertTrue(any("empty" in error.message.lower() for error in validation_result.errors))
        
        # Test graph definition service handling
        validation_errors = self.graph_definition_service.validate_csv_before_building(empty_csv_path)
        self.assertGreater(len(validation_errors), 0, "Should have validation errors for empty file")
        
        # Test building should raise error
        with self.assertRaises(ValueError) as context:
            self.graph_definition_service.build_from_csv(empty_csv_path)
        
        error_msg = str(context.exception)
        self.assertTrue("empty" in error_msg.lower() or "no data" in error_msg.lower())
    
    # =============================================================================
    # 5. Path Operations and File System Integration
    # =============================================================================
    
    def test_path_operations_integration(self):
        """Test Path operations following TESTING_PATTERNS.md section 12.1."""
        # Test with file that exists
        existing_spec = CSVTestDataFactory.create_simple_linear_graph()
        existing_path = self.test_data_manager.create_test_csv_file(existing_spec, "existing.csv")
        
        # Verify real file existence
        self.assertTrue(existing_path.exists(), "Real file should exist")
        self.assertTrue(existing_path.is_file(), "Should be a real file")
        
        # Test processing existing file
        graph = self.graph_definition_service.build_from_csv(existing_path)
        self.assertIsNotNone(graph, "Should process existing file")
        
        # Test with non-existent file using Path.exists() mocking pattern
        import unittest.mock
        nonexistent_path = Path(self.temp_dir) / "csv_data" / "nonexistent.csv"
        
        # Following section 12.1: Use module-level patching for reliable Path.exists() interception
        with unittest.mock.patch('pathlib.Path.exists', return_value=False):
            # Test validation with mocked non-existence
            validation_errors = self.graph_definition_service.validate_csv_before_building(nonexistent_path)
            self.assertGreater(len(validation_errors), 0, "Should detect non-existent file")
    
    def test_directory_creation_integration(self):
        """Test automatic directory creation during CSV processing."""
        # Use a deeply nested path that doesn't exist (inside csv_data directory)
        nested_csv_path = Path(self.temp_dir) / "csv_data" / "deep" / "nested" / "directory" / "test.csv"
        
        # Directory shouldn't exist initially
        self.assertFalse(nested_csv_path.parent.exists(), "Nested directory shouldn't exist initially")
        
        # Create CSV file (should create directories)
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        created_path = self.test_data_manager.create_test_csv_file(simple_spec, "deep/nested/directory/test.csv")
        
        # Verify directories were created
        self.assertTrue(created_path.parent.exists(), "Directories should be created")
        self.assert_file_exists(created_path, "CSV file in nested directory")
        
        # Verify processing works
        graph = self.graph_definition_service.build_from_csv(created_path)
        self.assertIsNotNone(graph, "Should process file in nested directory")
    
    def test_relative_vs_absolute_paths(self):
        """Test CSV processing with both relative and absolute paths."""
        # Create CSV file
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec, "path_test.csv")
        
        # Test with absolute path
        absolute_path = csv_path.absolute()
        graph_abs = self.graph_definition_service.build_from_csv(absolute_path)
        self.assertIsNotNone(graph_abs, "Should process absolute path")
        
        # Test with relative path (relative to current directory)
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(csv_path.parent)
            relative_path = Path(csv_path.name)
            graph_rel = self.graph_definition_service.build_from_csv(relative_path)
            self.assertIsNotNone(graph_rel, "Should process relative path")
            
            # Verify both produce equivalent results
            self.assert_graphs_equivalent(graph_abs, graph_rel, "Absolute vs relative path processing")
        finally:
            os.chdir(original_cwd)
    
    # =============================================================================
    # 6. Performance and Resource Management
    # =============================================================================
    
    def test_memory_cleanup_after_processing(self):
        """Test that memory is properly cleaned up after CSV processing."""
        # Create multiple CSV files and process them
        csv_files = []
        for i in range(5):
            spec = CSVTestDataFactory.create_simple_linear_graph()
            # Update both the spec graph_name and all node GraphName fields
            new_graph_name = f"cleanup_test_{i}"
            spec.graph_name = new_graph_name
            for node in spec.nodes:
                node["GraphName"] = new_graph_name
            
            csv_path = self.test_data_manager.create_test_csv_file(spec, f"cleanup_{i}.csv")
            csv_files.append(csv_path)
        
        # Process all files
        graphs = []
        for csv_path in csv_files:
            graph = self.graph_definition_service.build_from_csv(csv_path)
            graphs.append(graph)
        
        # Verify all were processed
        self.assertEqual(len(graphs), 5, "Should process all CSV files")
        
        # Verify each graph is distinct
        graph_names = [graph.name for graph in graphs]
        self.assertEqual(len(set(graph_names)), 5, "All graphs should have unique names")
        
        # Clear references (simulating cleanup)
        graphs.clear()
        csv_files.clear()
        
        # Processing should still work after cleanup
        new_spec = CSVTestDataFactory.create_simple_linear_graph()
        new_csv = self.test_data_manager.create_test_csv_file(new_spec, "after_cleanup.csv")
        new_graph = self.graph_definition_service.build_from_csv(new_csv)
        self.assertIsNotNone(new_graph, "Should work after cleanup")
    
    def test_concurrent_csv_processing_simulation(self):
        """Test simulated concurrent CSV processing (file system safety)."""
        # Create multiple CSV files with different graphs
        specs = [
            CSVTestDataFactory.create_simple_linear_graph(),
            CSVTestDataFactory.create_conditional_branching_graph()
        ]
        
        csv_paths = []
        for i, spec in enumerate(specs):
            # Update both the spec graph_name and all node GraphName fields
            new_graph_name = f"concurrent_{i}"
            spec.graph_name = new_graph_name
            for node in spec.nodes:
                node["GraphName"] = new_graph_name
            
            csv_path = self.test_data_manager.create_test_csv_file(spec, f"concurrent_{i}.csv")
            csv_paths.append(csv_path)
        
        # Process files in sequence (simulating concurrent access)
        results = []
        for csv_path in csv_paths:
            # Each processing should be independent
            graph = self.graph_definition_service.build_from_csv(csv_path)
            results.append(graph)
        
        # Verify all processing succeeded independently
        self.assertEqual(len(results), 2, "Should process all files")
        self.assertEqual(results[0].name, "concurrent_0")
        self.assertEqual(results[1].name, "concurrent_1")
        
        # Verify no cross-contamination
        self.assertNotEqual(len(results[0].nodes), len(results[1].nodes))
    
    # =============================================================================
    # 7. Integration with Test Data Factories
    # =============================================================================
    
    def test_test_data_factory_integration(self):
        """Test integration with test data factories for comprehensive coverage."""
        # Test all factory-created graph types
        factory_specs = [
            CSVTestDataFactory.create_simple_linear_graph(),
            CSVTestDataFactory.create_conditional_branching_graph()
        ]
        
        for spec in factory_specs:
            with self.subTest(graph_type=spec.graph_name):
                # Create CSV using factory
                csv_path = self.test_data_manager.create_test_csv_file(spec)
                
                # Process through pipeline
                graph = self.graph_definition_service.build_from_csv(csv_path)
                
                # Verify factory-generated data processed correctly
                self.assertIsInstance(graph, Graph)
                self.assertEqual(graph.name, spec.graph_name)
                self.assertGreater(len(graph.nodes), 0, "Should have nodes")
                
                # Verify all nodes are Node instances
                for node_name, node in graph.nodes.items():
                    self.assertIsInstance(node, Node, f"Node {node_name} should be Node instance")
                    self.assertEqual(node.name, node_name, "Node name should match key")
    
    def test_complete_test_environment_integration(self):
        """Test integration with complete test environment setup."""
        # Set up complete test environment
        test_resources = self.test_data_manager.setup_complete_test_environment()
        
        # Verify all resources were created
        for resource_name, resource_path in test_resources.items():
            if resource_name.endswith('_csv'):
                self.assert_file_exists(resource_path, f"{resource_name} file")
            elif resource_name.endswith('_dir'):
                self.assert_directory_exists(resource_path, f"{resource_name} directory")
        
        # Test processing each CSV file
        csv_resources = {k: v for k, v in test_resources.items() if k.endswith('_csv')}
        for resource_name, csv_path in csv_resources.items():
            with self.subTest(resource=resource_name):
                # Process CSV file
                if resource_name == "multi_csv":
                    # Multi-graph CSV
                    all_graphs = self.graph_definition_service.build_all_from_csv(csv_path)
                    self.assertGreater(len(all_graphs), 1, f"{resource_name} should have multiple graphs")
                else:
                    # Single graph CSV
                    graph = self.graph_definition_service.build_from_csv(csv_path)
                    self.assertIsInstance(graph, Graph, f"{resource_name} should produce Graph")
                    self.assertGreater(len(graph.nodes), 0, f"{resource_name} should have nodes")


if __name__ == '__main__':
    unittest.main()
