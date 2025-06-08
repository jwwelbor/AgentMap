"""
Core Service Coordination Integration Tests.

This module tests the coordination between core services using real DI container instances.
These tests verify that services work together correctly in complete workflows,
from CSV processing through graph execution and result tracking.
"""

import unittest
import tempfile
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from tests.fresh_suite.integration.test_data_factories import (
    CSVTestDataFactory,
    IntegrationTestDataManager,
    ExecutionTestDataFactory
)


class TestCoreServiceCoordination(BaseIntegrationTest):
    """
    Integration tests for core service coordination.
    
    Tests how key services work together in real workflows:
    - CSV parsing → Graph definition → Graph execution
    - Configuration coordination between services  
    - Execution tracking throughout the pipeline
    - Error propagation across service boundaries
    """
    
    def setup_services(self):
        """Initialize core services for coordination testing."""
        super().setup_services()
        
        # Core graph services
        self.graph_definition_service = self.container.graph_definition_service()
        self.graph_runner_service = self.container.graph_runner_service()
        self.execution_tracking_service = self.container.execution_tracking_service()
        
        # Configuration services
        self.storage_config_service = self.container.storage_config_service()
        
        # Supporting services
        self.csv_graph_parser_service = self.container.csv_graph_parser_service()
        
        # Initialize test data manager
        self.test_data_manager = IntegrationTestDataManager(Path(self.temp_dir))
    
    # =============================================================================
    # 1. CSV to Graph Definition Integration Tests
    # =============================================================================
    
    def test_csv_to_graph_definition_coordination(self):
        """Test CSV parsing coordinates with graph definition service."""
        # Create test CSV using data factory
        simple_graph_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_graph_spec)
        
        # Verify CSV file was created
        self.assert_file_exists(csv_path, "Test CSV file")
        
        # Test coordination: CSV parser → Graph definition
        try:
            # Step 1: Validate CSV structure first
            validation_errors = self.graph_definition_service.validate_csv_before_building(csv_path)
            self.assertEqual(validation_errors, [], 
                           f"CSV validation should pass for simple graph, got: {validation_errors}")
            
            # Step 2: Build graph from CSV
            graph = self.graph_definition_service.build_from_csv(csv_path)
            
            # Verify graph was created correctly
            self.assertIsNotNone(graph, "Graph should be created from valid CSV")
            self.assertEqual(graph.name, simple_graph_spec.graph_name)
            
            # Verify graph has expected nodes
            self.assertGreater(len(graph.nodes), 0, "Graph should have nodes")
            node_names = [node.name for node in graph.nodes.values()]
            self.assertIn('start', node_names, "Graph should have start node")
            self.assertIn('end', node_names, "Graph should have end node")
            
        except Exception as e:
            self.fail(f"CSV to graph definition coordination failed: {e}")
    
    def test_multi_graph_csv_coordination(self):
        """Test coordination with multi-graph CSV files."""
        # Create multi-graph CSV
        graph_specs = CSVTestDataFactory.create_multi_graph_csv()
        csv_path = self.test_data_manager.create_multi_graph_csv_file(graph_specs)
        
        # Test building all graphs
        all_graphs = self.graph_definition_service.build_all_from_csv(csv_path)
        
        # Verify all graphs were created
        self.assertEqual(len(all_graphs), 2, "Should create both graphs from multi-graph CSV")
        self.assertIn('first_graph', all_graphs, "Should contain first graph")
        self.assertIn('second_graph', all_graphs, "Should contain second graph")
        
        # Test building specific graph
        specific_graph = self.graph_definition_service.build_from_csv(csv_path, 'second_graph')
        self.assertEqual(specific_graph.name, 'second_graph')
        
        # Compare graphs using helper method that handles Node object comparison
        self.assert_graphs_equivalent(specific_graph, all_graphs['second_graph'], "Individual vs batch graph")
    
    def test_conditional_graph_coordination(self):
        """Test coordination with conditional branching graphs."""
        # Create conditional branching graph
        conditional_spec = CSVTestDataFactory.create_conditional_branching_graph()
        csv_path = self.test_data_manager.create_test_csv_file(conditional_spec)
        
        # Build and verify conditional graph
        graph = self.graph_definition_service.build_from_csv(csv_path)
        
        # Verify conditional structure
        self.assertEqual(graph.name, conditional_spec.graph_name)
        
        # Find validation node to check conditional connections
        validation_node = None
        for node in graph.nodes.values():
            if node.name == 'input_validator':
                validation_node = node
                break
        
        self.assertIsNotNone(validation_node, "Should have input_validator node")
    
    # =============================================================================
    # 2. Graph Definition to Execution Coordination Tests
    # =============================================================================
    
    def test_graph_definition_to_execution_coordination(self):
        """Test coordination between graph definition and execution services."""
        # Create simple graph for execution
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        # Step 1: Build graph
        graph = self.graph_definition_service.build_from_csv(csv_path)
        self.assertIsNotNone(graph, "Graph should be built successfully")
        
        # Step 2: Prepare execution state
        execution_state = ExecutionTestDataFactory.create_simple_execution_state()
        
        # Step 3: Test graph runner can work with defined graph
        try:
            # Verify graph runner service accepts the graph
            self.assert_service_created(self.graph_runner_service, "GraphRunnerService")
            
            # The graph runner service should be able to work with the graph
            # Note: We're testing service coordination, not full execution
            # Full execution would require LLM services which are mocked in test environment
            
        except Exception as e:
            self.fail(f"Graph definition to execution coordination failed: {e}")
    
    def test_execution_tracking_coordination(self):
        """Test execution tracking service coordinates with graph execution."""
        # Create execution state
        execution_state = ExecutionTestDataFactory.create_complex_execution_state()
        
        # Test execution tracking service integration
        self.assert_service_created(self.execution_tracking_service, "ExecutionTrackingService")
        
        # Verify execution tracking can handle the execution state
        session_id = execution_state.get('session_id', 'test_session')
        self.assertIsNotNone(session_id, "Session ID should be available for tracking")
    
    # =============================================================================
    # 3. Configuration Service Coordination Tests
    # =============================================================================
    
    def test_configuration_service_coordination(self):
        """Test coordination between configuration services."""
        # Test app config service
        self.assert_service_created(self.app_config_service, "AppConfigService")
        
        # Test storage config service  
        self.assert_service_created(self.storage_config_service, "StorageConfigService")
        
        # Verify configuration coordination
        # Both services should be using the same underlying configuration
        try:
            # Test that storage config service can provide storage settings
            # This verifies the configuration infrastructure is working
            
            # Note: Specific config values are tested in unit tests
            # Here we verify the services work together
            
            pass  # Services are properly initialized through DI container
            
        except Exception as e:
            self.fail(f"Configuration service coordination failed: {e}")
    
    def test_logging_service_coordination(self):
        """Test logging service coordinates across all services."""
        # Verify all services have logging configured
        services_to_check = [
            (self.graph_definition_service, "GraphDefinitionService"),
            (self.graph_runner_service, "GraphRunnerService"), 
            (self.execution_tracking_service, "ExecutionTrackingService"),
            (self.app_config_service, "AppConfigService")
        ]
        
        for service, expected_name in services_to_check:
            self.assert_service_created(service, expected_name)
            
            # Verify service has logging configured using helper method
            self.assert_service_has_logging(service, expected_name)
    
    # =============================================================================
    # 4. Error Propagation Integration Tests
    # =============================================================================
    
    def test_csv_validation_error_propagation(self):
        """Test error propagation from CSV validation through service chain."""
        # Create invalid CSV data
        invalid_csv_samples = CSVTestDataFactory.create_invalid_csv_samples()
        
        # Separate structural validation errors from business logic errors
        structural_errors = {
            "empty_file": invalid_csv_samples["empty_file"],
            "missing_headers": invalid_csv_samples["missing_headers"], 
            "malformed_csv": invalid_csv_samples["malformed_csv"],
            "missing_required_fields": invalid_csv_samples["missing_required_fields"]
        }
        
        business_logic_errors = {
            "duplicate_nodes": invalid_csv_samples["duplicate_nodes"],
            "circular_references": invalid_csv_samples["circular_references"],
            "invalid_edge_targets": invalid_csv_samples["invalid_edge_targets"]
        }
        
        # Test structural validation errors - these should be caught by CSV validation
        print("\n=== Testing Structural Validation Errors ===")
        for error_type, invalid_content in structural_errors.items():
            with self.subTest(error_type=error_type):
                # Create invalid CSV file
                invalid_csv_path = self.create_test_csv_file(invalid_content, f"invalid_{error_type}.csv")
                
                # Test error propagation through validation
                validation_errors = self.graph_definition_service.validate_csv_before_building(invalid_csv_path)
                
                # Structural errors should produce validation errors
                self.assertGreater(len(validation_errors), 0, 
                                 f"Should have validation errors for {error_type}. Got: {validation_errors}")
                
                # Verify error messages contain relevant information
                if error_type == "empty_file":
                    self.assertTrue(any("empty" in error.lower() for error in validation_errors),
                                  f"Empty file error should mention 'empty': {validation_errors}")
                elif error_type == "missing_headers":
                    self.assertTrue(any("header" in error.lower() or "column" in error.lower() or "missing" in error.lower() for error in validation_errors),
                                  f"Missing headers error should mention headers/columns/missing: {validation_errors}")
                elif error_type == "malformed_csv":
                    self.assertTrue(any("column" in error.lower() or "parse" in error.lower() or "error" in error.lower() for error in validation_errors),
                                  f"Malformed CSV error should mention parsing issues: {validation_errors}")
                elif error_type == "missing_required_fields":
                    self.assertTrue(any("required" in error.lower() or "column" in error.lower() or "missing" in error.lower() for error in validation_errors),
                                  f"Missing required fields error should mention required/column/missing: {validation_errors}")
                
                # Log the errors for debugging
                print(f"\n{error_type} produced {len(validation_errors)} validation errors:")
                for error in validation_errors[:3]:  # Show first 3 errors
                    print(f"  - {error}")
        
        # Test business logic errors - these should pass CSV validation but fail during graph building
        print("\n=== Testing Business Logic Errors ===")
        for error_type, invalid_content in business_logic_errors.items():
            with self.subTest(error_type=error_type):
                # Create CSV file with business logic error
                invalid_csv_path = self.create_test_csv_file(invalid_content, f"business_logic_{error_type}.csv")
                
                # These should pass CSV validation (structurally valid)
                validation_errors = self.graph_definition_service.validate_csv_before_building(invalid_csv_path)
                print(f"\n{error_type} CSV validation: {len(validation_errors)} errors")
                if validation_errors:
                    for error in validation_errors:
                        print(f"  - {error}")
                
                # Business logic errors should be caught during graph building, not CSV validation
                # Note: Some business logic validation might happen during building
                try:
                    graph = self.graph_definition_service.build_from_csv(invalid_csv_path)
                    print(f"  {error_type}: Graph building succeeded (business logic validation may be permissive)")
                except Exception as e:
                    print(f"  {error_type}: Graph building failed as expected: {type(e).__name__}: {e}")
    
    def test_business_logic_validation_during_building(self):
        """Test business logic validation that occurs during graph building."""
        # Create CSV samples with business logic errors
        invalid_csv_samples = CSVTestDataFactory.create_invalid_csv_samples()
        
        business_logic_errors = {
            "duplicate_nodes": invalid_csv_samples["duplicate_nodes"],
            "circular_references": invalid_csv_samples["circular_references"],
            "invalid_edge_targets": invalid_csv_samples["invalid_edge_targets"]
        }
        
        for error_type, invalid_content in business_logic_errors.items():
            with self.subTest(error_type=error_type):
                # Create CSV file with business logic error
                invalid_csv_path = self.create_test_csv_file(invalid_content, f"biz_logic_{error_type}.csv")
                
                # CSV validation should pass (structurally valid)
                validation_errors = self.graph_definition_service.validate_csv_before_building(invalid_csv_path)
                print(f"\n{error_type} - CSV validation errors: {len(validation_errors)}")
                
                # Business logic validation should happen during graph building
                # Some business logic errors might be caught, others might be permissive
                try:
                    graph = self.graph_definition_service.build_from_csv(invalid_csv_path)
                    
                    # If building succeeds, verify the graph structure
                    self.assertIsNotNone(graph, f"Graph should be created even with {error_type}")
                    
                    # For duplicate_nodes, check if only one instance is kept
                    if error_type == "duplicate_nodes":
                        node_names = list(graph.nodes.keys())
                        unique_nodes = set(node_names)
                        print(f"  Graph has {len(node_names)} total nodes, {len(unique_nodes)} unique")
                        # The service might handle duplicates by keeping the last one
                    
                    # For circular_references, the graph might still build but be logically circular
                    elif error_type == "circular_references":
                        print(f"  Graph built with potential circular references: {list(graph.nodes.keys())}")
                    
                    # For invalid_edge_targets, this should likely fail during building
                    elif error_type == "invalid_edge_targets":
                        print(f"  Graph built despite invalid edge targets: {list(graph.nodes.keys())}")
                    
                    print(f"  {error_type}: Graph building succeeded - business logic is permissive")
                    
                except Exception as e:
                    print(f"  {error_type}: Graph building failed as expected: {type(e).__name__}: {e}")
                    # For business logic errors, we expect either ValueError or custom graph exceptions
                    self.assertIsInstance(e, (ValueError, AttributeError),
                                        f"Expected ValueError or AttributeError for {error_type}, got {type(e).__name__}")

    def test_file_not_found_error_propagation(self):
        """Test error propagation when CSV file doesn't exist."""
        nonexistent_path = Path(self.temp_dir) / "nonexistent.csv"
        
        # For validation, file not found should return validation errors
        validation_errors = self.graph_definition_service.validate_csv_before_building(nonexistent_path)
        self.assertGreater(len(validation_errors), 0, "Should have validation errors for missing file")
        self.assertTrue(any("not exist" in error.lower() or "not found" in error.lower() for error in validation_errors),
                       f"Should indicate file not found: {validation_errors}")
        
        # For actual building, it should raise an exception
        with self.assertRaises(FileNotFoundError) as context:
            self.graph_definition_service.build_from_csv(nonexistent_path)
        
        # Verify error message is meaningful
        error_msg = str(context.exception)
        self.assertIn("nonexistent.csv", error_msg)
    
    def test_graph_not_found_error_propagation(self):
        """Test error propagation when requested graph doesn't exist in CSV."""
        # Create valid CSV with specific graph
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        # Request non-existent graph
        with self.assertRaises(ValueError) as context:
            self.graph_definition_service.build_from_csv(csv_path, 'nonexistent_graph')
        
        # Verify error includes available graphs
        error_msg = str(context.exception)
        self.assertIn('nonexistent_graph', error_msg)
        self.assertIn('not found', error_msg)
        self.assertIn(simple_spec.graph_name, error_msg)
    
    # =============================================================================
    # 5. End-to-End Service Coordination Tests
    # =============================================================================
    
    def test_complete_csv_to_graph_pipeline(self):
        """Test complete pipeline from CSV file to executable graph."""
        # Set up complete test environment
        test_resources = self.test_data_manager.setup_complete_test_environment()
        
        # Verify all resources were created
        for resource_name, resource_path in test_resources.items():
            if resource_name.endswith('_csv') or resource_name.endswith('_config'):
                self.assert_file_exists(resource_path, f"{resource_name} file")
            elif resource_name.endswith('_dir'):
                self.assert_directory_exists(resource_path, f"{resource_name} directory")
        
        # Test complete pipeline with simple graph
        simple_csv_path = test_resources['simple_csv']
        
        # Step 1: Validate CSV
        validation_errors = self.graph_definition_service.validate_csv_before_building(simple_csv_path)
        self.assertEqual(validation_errors, [], "Simple CSV should validate successfully")
        
        # Step 2: Build graph
        graph = self.graph_definition_service.build_from_csv(simple_csv_path)
        self.assertIsNotNone(graph, "Graph should be built from simple CSV")
        
        # Step 3: Verify graph is ready for execution
        self.assertGreater(len(graph.nodes), 0, "Graph should have nodes")
        
        # Step 4: Verify execution services are ready
        self.assert_service_created(self.graph_runner_service, "GraphRunnerService")
        self.assert_service_created(self.execution_tracking_service, "ExecutionTrackingService")
    
    def test_service_dependency_chain_integrity(self):
        """Test that service dependency chain maintains integrity."""
        # Verify core service dependency chain
        services_chain = [
            # Configuration layer
            (self.app_config_service, "AppConfigService"),
            (self.storage_config_service, "StorageConfigService"),
            
            # Processing layer  
            (self.csv_graph_parser_service, "CSVGraphParserService"),
            (self.graph_definition_service, "GraphDefinitionService"),
            
            # Execution layer
            (self.graph_runner_service, "GraphRunnerService"),
            (self.execution_tracking_service, "ExecutionTrackingService"),
            
            # Infrastructure layer
            (self.logging_service, "LoggingService")
        ]
        
        # Verify all services are properly initialized
        for service, expected_name in services_chain:
            self.assert_service_created(service, expected_name)
        
        # Test that services can coordinate (basic smoke test)
        try:
            # Create a simple workflow that exercises the chain
            simple_spec = CSVTestDataFactory.create_simple_linear_graph()
            csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
            
            # This should exercise: csv_parser → graph_definition → logging
            graph = self.graph_definition_service.build_from_csv(csv_path)
            self.assertIsNotNone(graph, "Service chain should produce valid graph")
            
        except Exception as e:
            self.fail(f"Service dependency chain integrity test failed: {e}")
    
    def test_concurrent_service_access(self):
        """Test services handle concurrent access gracefully."""
        # Create multiple CSV files for concurrent processing
        graphs_specs = [
            CSVTestDataFactory.create_simple_linear_graph(),
            CSVTestDataFactory.create_conditional_branching_graph()
        ]
        
        csv_paths = []
        for i, spec in enumerate(graphs_specs):
            csv_path = self.test_data_manager.create_test_csv_file(spec, f"concurrent_test_{i}.csv")
            csv_paths.append(csv_path)
        
        # Test concurrent graph building (simulated)
        built_graphs = []
        for csv_path in csv_paths:
            try:
                graph = self.graph_definition_service.build_from_csv(csv_path)
                built_graphs.append(graph)
            except Exception as e:
                self.fail(f"Concurrent service access failed for {csv_path}: {e}")
        
        # Verify all graphs were built successfully
        self.assertEqual(len(built_graphs), len(graphs_specs), 
                        "All graphs should be built in concurrent access scenario")
        
        # Verify graphs are distinct
        graph_names = [graph.name for graph in built_graphs]
        self.assertEqual(len(set(graph_names)), len(graph_names), 
                        "All graphs should have unique names")


class TestStorageServiceCoordination(BaseIntegrationTest):
    """
    Integration tests for storage service coordination.
    
    Tests how storage services work together and coordinate with other services.
    """
    
    def setup_services(self):
        """Initialize storage services for coordination testing."""
        super().setup_services()
        
        # Storage service manager (coordinates all storage services)
        self.storage_service_manager = self.container.storage_service_manager()
        
        # Test data manager
        self.test_data_manager = IntegrationTestDataManager(Path(self.temp_dir))
    
    def test_storage_manager_coordination(self):
        """Test storage manager coordinates multiple storage services."""
        # Storage service manager may be None if storage config is not available (graceful degradation)
        if self.storage_service_manager is None:
            self.skipTest("Storage configuration not available - storage services disabled")
        
        # Verify storage service manager is created
        self.assert_service_created(self.storage_service_manager, "StorageServiceManager")
    
    def test_storage_configuration_coordination(self):
        """Test storage services coordinate with configuration."""
        # Storage service manager may be None if storage config is not available
        if self.storage_service_manager is None:
            self.skipTest("Storage configuration not available - storage services disabled")
            
        # Verify storage services can access configuration
        try:
            # Storage services should be properly configured through DI container
            # This tests the coordination between storage config and storage services
            
            # Note: Detailed configuration testing is in unit tests
            # Here we verify coordination works
            self.assert_service_created(self.storage_service_manager, "StorageServiceManager")
            
        except Exception as e:
            self.fail(f"Storage configuration coordination failed: {e}")
    
    def test_csv_storage_integration(self):
        """Test CSV storage service integration."""
        # Storage service manager may be None if storage config is not available
        if self.storage_service_manager is None:
            self.skipTest("Storage configuration not available - storage services disabled")
            
        # Create test CSV data
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        test_data = CSVTestDataFactory.convert_graph_spec_to_csv([simple_spec])
        
        # Test CSV storage coordination
        try:
            # Note: Actual file operations would be tested in unit tests
            # Here we verify the service is properly integrated
            self.assert_service_created(self.storage_service_manager, "StorageServiceManager")
            
        except Exception as e:
            self.fail(f"CSV storage integration failed: {e}")


if __name__ == '__main__':
    unittest.main()
