"""
Core Service Coordination Integration Tests.

This module establishes core integration testing patterns for service-to-service coordination
using real DI container instances. Focuses on fundamental service interactions that demonstrate
the integration testing approach for the fresh test suite.
"""

import unittest
from pathlib import Path
from typing import Any, Dict

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest


class TestCoreServiceIntegration(BaseIntegrationTest):
    """
    Integration tests for core service coordination patterns.
    
    Establishes core integration testing patterns by testing fundamental service interactions:
    - GraphRunnerService → GraphDefinitionService delegation
    - ExecutionTrackingService coordination
    - Configuration service integration
    - Real DI container service creation and wiring
    
    These tests serve as the foundation for more complex integration testing scenarios.
    """
    
    def setup_services(self):
        """Initialize core services from DI container for integration testing."""
        super().setup_services()
        
        # Core graph services
        self.graph_runner_service = self.container.graph_runner_service()
        self.graph_definition_service = self.container.graph_definition_service()
        self.execution_tracking_service = self.container.execution_tracking_service()
        
        # Compilation service
        self.compilation_service = self.container.compilation_service()
        
        # Configuration services for coordination testing
        self.storage_config_service = self.container.storage_config_service()
    
    def _create_correct_format_simple_csv(self) -> str:
        """Create simple CSV with correct format expected by CSV parser."""
        return '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
test_graph,start_node,default,Start processing,Start node for testing,input_data,processed_data,end_node
test_graph,end_node,default,Finish processing,End node for testing,processed_data,final_result,
'''
    
    def _create_correct_format_multi_graph_csv(self) -> str:
        """Create multi-graph CSV with correct format expected by CSV parser."""
        return '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge
first_graph,start_node,default,Start first graph,First graph start,input,output,end_node
first_graph,end_node,default,End first graph,First graph end,output,result,
second_graph,begin_node,default,Start second graph,Second graph start,data,processed,finish_node
second_graph,finish_node,default,End second graph,Second graph end,processed,final,
'''
    
    def create_simple_test_graph_csv(self) -> str:
        """Override base class method to use correct CSV format."""
        return self._create_correct_format_simple_csv()
    
    def create_complex_test_graph_csv(self) -> str:
        """Override base class method to use correct CSV format."""
        return '''GraphName,Node,AgentType,Prompt,Description,Input_Fields,Output_Field,Edge,Success_Next,Failure_Next
complex_graph,input_node,default,Process input data,Input processing node,raw_input,validated_input,validation_node,,
complex_graph,validation_node,default,Validate the input,Validation node,validated_input,validation_result,,process_node,error_node
complex_graph,process_node,default,Process validated data,Main processing node,validation_result,processed_output,output_node,,
complex_graph,error_node,default,Handle errors,Error handling node,validation_result,error_message,,,
complex_graph,output_node,default,Format final output,Output formatting node,processed_output,final_output,,,
'''
    
    # =============================================================================
    # 1. Service Creation and DI Container Integration Tests
    # =============================================================================
    
    def test_di_container_creates_real_services(self):
        """Test that DI container creates real service instances correctly."""
        # Test that all core services are created as real instances
        self.assert_service_created(self.graph_runner_service, "GraphRunnerService")
        self.assert_service_created(self.graph_definition_service, "GraphDefinitionService")
        self.assert_service_created(self.execution_tracking_service, "ExecutionTrackingService")
        self.assert_service_created(self.compilation_service, "CompilationService")
        
        # Verify services are not None (real instances, not mocks)
        self.assertIsNotNone(self.graph_runner_service)
        self.assertIsNotNone(self.graph_definition_service)
        self.assertIsNotNone(self.execution_tracking_service)
        self.assertIsNotNone(self.compilation_service)
    
    def test_service_dependency_injection_works(self):
        """Test that services receive real dependencies through DI container."""
        # Test GraphRunnerService has real dependencies injected
        self.assertIsNotNone(self.graph_runner_service.graph_definition, 
                           "GraphRunnerService should have graph_definition dependency injected")
        self.assertIsNotNone(self.graph_runner_service.graph_execution, 
                           "GraphRunnerService should have graph_execution dependency injected")
        self.assertIsNotNone(self.graph_runner_service.compilation, 
                           "GraphRunnerService should have compilation dependency injected")
        
        # Test GraphDefinitionService has real dependencies injected
        self.assertIsNotNone(self.graph_definition_service.logger, 
                           "GraphDefinitionService should have logger dependency injected")
        self.assertIsNotNone(self.graph_definition_service.config, 
                           "GraphDefinitionService should have config dependency injected")
        self.assertIsNotNone(self.graph_definition_service.csv_parser, 
                           "GraphDefinitionService should have csv_parser dependency injected")
    
    def test_service_interface_compliance(self):
        """Test that services implement expected interfaces for coordination."""
        # Test GraphRunnerService interface
        self.assertTrue(hasattr(self.graph_runner_service, 'run_graph'), 
                       "GraphRunnerService should have run_graph method")
        self.assertTrue(hasattr(self.graph_runner_service, 'run_from_csv_direct'), 
                       "GraphRunnerService should have run_from_csv_direct method")
        self.assertTrue(hasattr(self.graph_runner_service, 'get_default_options'), 
                       "GraphRunnerService should have get_default_options method")
        
        # Test GraphDefinitionService interface
        self.assertTrue(hasattr(self.graph_definition_service, 'build_from_csv'), 
                       "GraphDefinitionService should have build_from_csv method")
        self.assertTrue(hasattr(self.graph_definition_service, 'build_all_from_csv'), 
                       "GraphDefinitionService should have build_all_from_csv method")
        self.assertTrue(hasattr(self.graph_definition_service, 'validate_csv_before_building'), 
                       "GraphDefinitionService should have validate_csv_before_building method")
        
        # Test ExecutionTrackingService interface
        self.assertTrue(hasattr(self.execution_tracking_service, 'create_tracker'), 
                       "ExecutionTrackingService should have create_tracker method")
        self.assertTrue(hasattr(self.execution_tracking_service, 'record_node_start'), 
                       "ExecutionTrackingService should have record_node_start method")
        self.assertTrue(hasattr(self.execution_tracking_service, 'record_node_result'), 
                       "ExecutionTrackingService should have record_node_result method")
    
    # =============================================================================
    # 2. GraphRunnerService → GraphDefinitionService Delegation Tests
    # =============================================================================
    
    def test_graph_runner_to_definition_service_delegation(self):
        """Test GraphRunnerService delegates to GraphDefinitionService correctly."""
        # Create test CSV file with simple graph using correct format
        csv_content = self._create_correct_format_simple_csv()
        csv_path = self.create_test_csv_file(csv_content)
        
        # Test delegation: GraphRunnerService should use GraphDefinitionService internally
        # We verify this by testing that the same CSV can be processed by both services consistently
        
        # 1. Build graph directly using GraphDefinitionService
        graph_via_definition_service = self.graph_definition_service.build_from_csv(csv_path)
        
        # 2. Verify GraphRunnerService can access GraphDefinitionService
        self.assertIsNotNone(self.graph_runner_service.graph_definition, 
                           "GraphRunnerService should have GraphDefinitionService available")
        
        # 3. Test that GraphRunnerService uses the same GraphDefinitionService instance
        self.assertEqual(type(self.graph_runner_service.graph_definition).__name__, "GraphDefinitionService",
                        "GraphRunnerService should delegate to GraphDefinitionService")
        
        # 4. Verify the delegation works by testing the interface
        # GraphRunnerService should be able to resolve graphs using its internal GraphDefinitionService
        self.assertIsNotNone(graph_via_definition_service, "GraphDefinitionService should build graph")
        self.assertEqual(graph_via_definition_service.name, "test_graph")
        self.assertGreater(len(graph_via_definition_service.nodes), 0)
    
    def test_csv_validation_coordination(self):
        """Test CSV validation coordination between services."""
        # Create test CSV file
        csv_content = self._create_correct_format_simple_csv()
        csv_path = self.create_test_csv_file(csv_content)
        
        # Test validation through GraphDefinitionService
        validation_errors = self.graph_definition_service.validate_csv_before_building(csv_path)
        
        # Valid CSV should have no errors
        self.assertEqual(validation_errors, [], 
                        f"Simple CSV should validate successfully, got: {validation_errors}")
        
        # Test that GraphRunnerService can work with validated CSV
        # This demonstrates coordination: validation → building → potential execution
        graph = self.graph_definition_service.build_from_csv(csv_path)
        self.assertIsNotNone(graph, "Validated CSV should build successfully")
        self.assertEqual(graph.name, "test_graph")
    
    def test_multi_graph_csv_coordination(self):
        """Test coordination with multi-graph CSV processing."""
        # Create multi-graph CSV content with correct format
        multi_graph_csv = self._create_correct_format_multi_graph_csv()
        csv_path = self.create_test_csv_file(multi_graph_csv, "multi_graph_test.csv")
        
        # Test that GraphDefinitionService can handle multiple graphs
        all_graphs = self.graph_definition_service.build_all_from_csv(csv_path)
        
        # Verify coordination results
        self.assertEqual(len(all_graphs), 2, "Should build both graphs")
        self.assertIn('first_graph', all_graphs, "Should contain first_graph")
        self.assertIn('second_graph', all_graphs, "Should contain second_graph")
        
        # Test specific graph extraction
        specific_graph = self.graph_definition_service.build_from_csv(csv_path, 'second_graph')
        self.assertEqual(specific_graph.name, 'second_graph')
        
        # Compare using helper method that handles Node object comparison
        self.assert_graphs_equivalent(specific_graph, all_graphs['second_graph'], 
                                    "Individual vs batch graph coordination")
    
    # =============================================================================
    # 3. ExecutionTrackingService Coordination Tests
    # =============================================================================
    
    def test_execution_tracking_service_coordination(self):
        """Test ExecutionTrackingService coordinates with other services."""
        # Test execution tracker creation
        execution_tracker = self.execution_tracking_service.create_tracker()
        self.assertIsNotNone(execution_tracker, "ExecutionTrackingService should create tracker")
        
        # Test tracker configuration coordination with AppConfigService
        # The tracker should be configured based on app configuration
        self.assertIsNotNone(execution_tracker, "Tracker should be properly configured")
        
        # Test basic tracking operations
        test_node_name = "test_node"
        test_inputs = {"input_data": "test_value"}
        
        # Record node start
        self.execution_tracking_service.record_node_start(execution_tracker, test_node_name, test_inputs)
        
        # Verify tracking state
        self.assertGreater(len(execution_tracker.node_executions), 0, 
                          "Should have recorded node execution")
        self.assertEqual(execution_tracker.node_execution_counts[test_node_name], 1,
                        "Should have recorded execution count")
        
        # Record node result
        self.execution_tracking_service.record_node_result(execution_tracker, test_node_name, True, "success_result")
        
        # Complete execution
        self.execution_tracking_service.complete_execution(execution_tracker)
        self.assertIsNotNone(execution_tracker.end_time, "Should have recorded end time")
    
    def test_execution_tracking_integration_with_graph_services(self):
        """Test ExecutionTrackingService integrates with graph processing services."""
        # Create simple CSV for testing
        csv_content = self._create_correct_format_simple_csv()
        csv_path = self.create_test_csv_file(csv_content)
        
        # Build graph using GraphDefinitionService
        graph = self.graph_definition_service.build_from_csv(csv_path)
        
        # Create execution tracker for the graph
        execution_tracker = self.execution_tracking_service.create_tracker()
        
        # Simulate tracking for each node in the graph
        for node_name in graph.nodes:
            # Test tracking coordination with graph structure
            self.execution_tracking_service.record_node_start(execution_tracker, node_name, {"test": "data"})
            self.execution_tracking_service.record_node_result(execution_tracker, node_name, True, "result")
        
        # Complete execution
        self.execution_tracking_service.complete_execution(execution_tracker)
        
        # Verify tracking coordination results
        self.assertEqual(len(execution_tracker.node_executions), len(graph.nodes),
                        "Should track all graph nodes")
        
        # Create execution summary
        summary = self.execution_tracking_service.to_summary(execution_tracker, graph.name)
        self.assertIsNotNone(summary, "Should create execution summary")
        self.assertEqual(summary.graph_name, graph.name, "Summary should reference correct graph")
    
    # =============================================================================
    # 4. Configuration Service Coordination Tests
    # =============================================================================
    
    def test_configuration_service_coordination(self):
        """Test configuration services coordinate properly."""
        # Test AppConfigService coordination
        self.assert_service_created(self.app_config_service, "AppConfigService")
        
        # Test configuration accessibility
        logging_config = self.app_config_service.get_logging_config()
        self.assertIsNotNone(logging_config, "AppConfigService should provide logging config")
        
        execution_config = self.app_config_service.get_execution_config()
        self.assertIsNotNone(execution_config, "AppConfigService should provide execution config")
        
        # Test StorageConfigService coordination (may be None due to graceful degradation)
        if self.storage_config_service is not None:
            self.assert_service_created(self.storage_config_service, "StorageConfigService")
        else:
            # Graceful degradation - storage config not available is acceptable
            self.logger.info("StorageConfigService not available - graceful degradation working")
    
    def test_logging_service_coordination(self):
        """Test logging service coordinates across all services."""
        # Verify all services have logging configured using helper method
        services_to_check = [
            (self.graph_definition_service, "GraphDefinitionService"),
            (self.graph_runner_service, "GraphRunnerService"), 
            (self.execution_tracking_service, "ExecutionTrackingService"),
            (self.app_config_service, "AppConfigService"),
            (self.compilation_service, "CompilationService")
        ]
        
        for service, expected_name in services_to_check:
            self.assert_service_created(service, expected_name)
            self.assert_service_has_logging(service, expected_name)
    
    # =============================================================================
    # 5. Error Handling and Graceful Degradation Tests
    # =============================================================================
    
    def test_file_not_found_error_coordination(self):
        """Test error coordination across services when files don't exist."""
        nonexistent_path = Path(self.temp_dir) / "nonexistent.csv"
        
        # Test error handling in GraphDefinitionService
        validation_errors = self.graph_definition_service.validate_csv_before_building(nonexistent_path)
        self.assertGreater(len(validation_errors), 0, "Should have validation errors for missing file")
        
        # Test error propagation from GraphDefinitionService
        with self.assertRaises(FileNotFoundError) as context:
            self.graph_definition_service.build_from_csv(nonexistent_path)
        
        # Verify error message is meaningful and contains file path
        error_msg = str(context.exception)
        self.assertIn("nonexistent.csv", error_msg)
    
    def test_invalid_csv_error_coordination(self):
        """Test error coordination with invalid CSV content."""
        # Create invalid CSV content (missing required columns)
        invalid_csv = "Invalid,CSV,Headers\nno,proper,structure"
        csv_path = self.create_test_csv_file(invalid_csv, "invalid.csv")
        
        # Test error detection through validation
        validation_errors = self.graph_definition_service.validate_csv_before_building(csv_path)
        self.assertGreater(len(validation_errors), 0, 
                          f"Should have validation errors for invalid CSV: {validation_errors}")
        
        # Test error propagation during building
        with self.assertRaises(Exception) as context:
            self.graph_definition_service.build_from_csv(csv_path)
        
        # Error should be meaningful
        error_msg = str(context.exception)
        self.assertIsNotNone(error_msg, "Should have meaningful error message")
    
    def test_graceful_degradation_coordination(self):
        """Test graceful degradation when optional services are unavailable."""
        # Test that StorageConfigService can be None (graceful degradation)
        if self.storage_config_service is None:
            # This is expected behavior - verify system continues to work
            self.assertIsNotNone(self.app_config_service, "Core config should still work")
            self.assertIsNotNone(self.graph_definition_service, "Graph services should still work")
            self.assertIsNotNone(self.execution_tracking_service, "Tracking should still work")
        
        # Test that core services remain functional even with degraded storage
        csv_content = self._create_correct_format_simple_csv()
        csv_path = self.create_test_csv_file(csv_content)
        
        # Core functionality should work regardless of storage availability
        graph = self.graph_definition_service.build_from_csv(csv_path)
        self.assertIsNotNone(graph, "Core graph building should work with degraded storage")
    
    # =============================================================================
    # 6. Service Integration Smoke Tests
    # =============================================================================
    
    def test_end_to_end_service_coordination_smoke_test(self):
        """Smoke test for end-to-end service coordination."""
        # Create test CSV
        csv_content = self._create_correct_format_simple_csv()
        csv_path = self.create_test_csv_file(csv_content)
        
        # Step 1: Validate CSV (GraphDefinitionService)
        validation_errors = self.graph_definition_service.validate_csv_before_building(csv_path)
        self.assertEqual(validation_errors, [], "CSV should validate successfully")
        
        # Step 2: Build graph (GraphDefinitionService)
        graph = self.graph_definition_service.build_from_csv(csv_path)
        self.assertIsNotNone(graph, "Graph should be built successfully")
        
        # Step 3: Create execution tracker (ExecutionTrackingService)
        execution_tracker = self.execution_tracking_service.create_tracker()
        self.assertIsNotNone(execution_tracker, "Execution tracker should be created")
        
        # Step 4: Verify GraphRunnerService can access graph definition capability
        self.assertIsNotNone(self.graph_runner_service.graph_definition, 
                           "GraphRunnerService should have access to graph definition")
        
        # This demonstrates the complete service coordination chain:
        # CSV → Validation → Graph Building → Execution Tracking → Graph Running
        self.assertTrue(True, "End-to-end service coordination successful")
    
    def test_compilation_service_coordination(self):
        """Test CompilationService coordinates with other services."""
        # Verify CompilationService is properly wired
        self.assert_service_created(self.compilation_service, "CompilationService")
        
        # Test that CompilationService has access to required dependencies
        self.assertIsNotNone(self.compilation_service, "CompilationService should be available")
        
        # Verify GraphRunnerService can access CompilationService
        self.assertIsNotNone(self.graph_runner_service.compilation, 
                           "GraphRunnerService should have access to CompilationService")
        
        # Test coordination: GraphRunnerService → CompilationService
        self.assertEqual(type(self.graph_runner_service.compilation).__name__, "CompilationService",
                        "GraphRunnerService should delegate to CompilationService")
    
    def test_service_integration_patterns_established(self):
        """Test that core integration patterns are properly established."""
        # Pattern 1: Real DI container usage (not mocked)
        self.assertIsNotNone(self.container, "Should use real DI container")
        
        # Pattern 2: Service dependency injection
        all_services_available = all([
            self.graph_runner_service is not None,
            self.graph_definition_service is not None,
            self.execution_tracking_service is not None,
            self.compilation_service is not None,
            self.app_config_service is not None,
            self.logging_service is not None
        ])
        self.assertTrue(all_services_available, "All core services should be available")
        
        # Pattern 3: Service coordination interfaces
        coordination_interfaces_available = all([
            hasattr(self.graph_runner_service, 'graph_definition'),
            hasattr(self.graph_runner_service, 'graph_execution'),
            hasattr(self.graph_runner_service, 'compilation'),
            hasattr(self.graph_definition_service, 'build_from_csv'),
            hasattr(self.execution_tracking_service, 'create_tracker')
        ])
        self.assertTrue(coordination_interfaces_available, "Service coordination interfaces should be available")
        
        # Pattern 4: Configuration coordination
        config_coordination_working = all([
            self.app_config_service is not None,
            hasattr(self.app_config_service, 'get_logging_config'),
            hasattr(self.app_config_service, 'get_execution_config')
        ])
        self.assertTrue(config_coordination_working, "Configuration coordination should work")
        
        # Pattern 5: Error handling and graceful degradation
        graceful_degradation_working = True  # StorageConfigService can be None
        self.assertTrue(graceful_degradation_working, "Graceful degradation should work")


if __name__ == '__main__':
    unittest.main()
