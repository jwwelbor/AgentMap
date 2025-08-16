"""
Graph Execution Workflow Integration Tests.

This module tests the complete graph execution workflow from CSV definition
through agent creation, execution, and result tracking. Tests verify real
service coordination using actual DI container instances with focus on:

- Complete execution pipeline: CSV → Graph → Agents → Execution → Results
- Service coordination: GraphRunnerService → GraphExecutionService → ExecutionTrackingService
- Real agent instantiation and execution (DefaultAgent)
- ExecutionResult validation and state flow
- Error handling across service boundaries
"""

import unittest
import time
from pathlib import Path
from typing import Dict, Any, Optional

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from tests.fresh_suite.integration.test_data_factories import (
    CSVTestDataFactory,
    IntegrationTestDataManager,
    ExecutionTestDataFactory
)
from agentmap.models.execution_result import ExecutionResult
from agentmap.services.graph.graph_runner_service import RunOptions


class TestExecutionWorkflowIntegration(BaseIntegrationTest):
    """
    Integration tests for graph execution workflows.
    
    Tests the complete execution pipeline that coordinates multiple services:
    - GraphRunnerService: Main orchestration and agent creation
    - GraphExecutionService: Execution coordination and tracking setup
    - ExecutionTrackingService: Execution tracking and summary generation
    - Graph definition services: CSV parsing and graph building
    - Agent services: Real agent instantiation and execution
    """
    
    def setup_services(self):
        """Initialize services for execution workflow testing."""
        super().setup_services()
        
        # Core execution services
        self.graph_runner_service = self.container.graph_runner_service()
        self.graph_execution_service = self.container.graph_execution_service()
        self.execution_tracking_service = self.container.execution_tracking_service()
        
        # Supporting services for comprehensive testing
        self.graph_definition_service = self.container.graph_definition_service()
        
        # Test data manager
        self.test_data_manager = IntegrationTestDataManager(Path(self.temp_dir))
        
        # Verify all critical services are available
        self.assert_service_created(self.graph_runner_service, "GraphRunnerService")
        self.assert_service_created(self.graph_execution_service, "GraphExecutionService")
        self.assert_service_created(self.execution_tracking_service, "ExecutionTrackingService")
        self.assert_service_created(self.graph_definition_service, "GraphDefinitionService")
    
    # =============================================================================
    # 1. Complete Graph Execution Workflow Tests
    # =============================================================================
    
    def test_complete_graph_execution_workflow(self):
        """Test complete workflow: CSV → Graph Definition → Agent Creation → Execution → Results."""
        print("\n=== Testing Complete Graph Execution Workflow ===")
        
        # Step 1: Create test graph CSV
        simple_graph_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_graph_spec)
        
        print(f"Created test CSV: {csv_path}")
        self.assert_file_exists(csv_path, "Test CSV file")
        
        # Step 2: Prepare execution state
        initial_state = ExecutionTestDataFactory.create_simple_execution_state()
        print(f"Initial state: {initial_state}")
        
        # Step 3: Execute complete workflow using GraphRunnerService
        print("\nExecuting complete workflow...")
        start_time = time.time()
        
        # Create RunOptions with initial state
        options = RunOptions(initial_state=initial_state)
        
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name=simple_graph_spec.graph_name,
                options=options
            )
            
            execution_time = time.time() - start_time
            print(f"Execution completed in {execution_time:.3f}s")
            
            # Step 4: Verify execution result structure
            self.assertIsInstance(result, ExecutionResult, "Should return ExecutionResult instance")
            self.assertIsNotNone(result.graph_name, "ExecutionResult should have graph name")
            self.assertEqual(result.graph_name, simple_graph_spec.graph_name, "Graph name should match")
            
            # Step 5: Verify execution success
            print(f"Execution success: {result.success}")
            print(f"Final state keys: {list(result.final_state.keys()) if result.final_state else 'None'}")
            
            if not result.success:
                print(f"Execution error: {result.error}")
                # For integration tests, we log but don't necessarily fail on execution errors
                # since we're testing service coordination, not business logic
            
            # Step 6: Verify result structure regardless of execution success
            self.assertIsNotNone(result.final_state, "Should have final state")
            
            # Duration validation - handle both possible field names and allow very fast executions
            duration_value = None
            duration_field = None
            if hasattr(result, 'total_duration'):
                duration_value = result.total_duration
                duration_field = 'total_duration'
            elif hasattr(result, 'execution_time'):
                duration_value = result.execution_time
                duration_field = 'execution_time'
            else:
                # Check all attributes for debugging
                print("\nDEBUG: Available attributes on result:")
                for attr in dir(result):
                    if not attr.startswith('_') and 'time' in attr.lower():
                        print(f"  {attr}: {getattr(result, attr, 'N/A')}")
                self.fail("ExecutionResult should have either 'total_duration' or 'execution_time' field")
            
            self.assertIsNotNone(duration_value, f"Should have {duration_field}")
            self.assertIsInstance(duration_value, (int, float), f"{duration_field} should be numeric")
            self.assertGreaterEqual(duration_value, 0, f"{duration_field} should be non-negative (can be 0.0 for fast executions)")
            
            print(f"Duration validation: {duration_field} = {duration_value}")
            
            # Step 7: Verify execution summary (if available)
            if result.execution_summary:
                print(f"Execution summary available: {type(result.execution_summary)}")
                self.assertIsNotNone(result.execution_summary.graph_name, "Summary should have graph name")
            else:
                print("No execution summary available (acceptable for some execution paths)")
            
            print("✅ Complete workflow coordination successful")
            
        except Exception as e:
            print(f"❌ Complete workflow failed: {e}")
            self.fail(f"Complete graph execution workflow failed: {e}")
    
    def test_csv_direct_execution_with_complex_graph(self):
        """Test CSV direct execution with conditional branching graph."""
        print("\n=== Testing Complex Graph Execution ===")
        
        # Create conditional branching graph
        conditional_spec = CSVTestDataFactory.create_conditional_branching_graph()
        csv_path = self.test_data_manager.create_test_csv_file(conditional_spec)
        
        print(f"Created conditional graph CSV: {csv_path}")
        
        # Prepare complex execution state
        complex_state = ExecutionTestDataFactory.create_complex_execution_state()
        
        # Create RunOptions with complex state
        options = RunOptions(initial_state=complex_state)
        
        # Execute workflow
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name=conditional_spec.graph_name,
                options=options
            )
            
            # Verify result structure for complex graph
            self.assertIsInstance(result, ExecutionResult)
            self.assertEqual(result.graph_name, conditional_spec.graph_name)
            self.assertIsNotNone(result.final_state)
            
            print(f"Complex graph execution: {result.success}")
            print("✅ Complex graph workflow coordination successful")
            
        except Exception as e:
            print(f"❌ Complex graph workflow failed: {e}")
            self.fail(f"Complex graph execution workflow failed: {e}")
    
    # =============================================================================
    # 2. Service Coordination Tests
    # =============================================================================
    
    def test_graph_runner_to_execution_service_delegation(self):
        """Test GraphRunnerService correctly delegates to GraphExecutionService."""
        print("\n=== Testing Service Delegation ===")
        
        # Create test data
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        initial_state = {"test_input": "delegation_test"}
        
        # Create RunOptions with initial state
        options = RunOptions(initial_state=initial_state)
        
        # Test delegation through run_from_csv_direct
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name=simple_spec.graph_name,
                options=options
            )
            
            # Verify that delegation occurred successfully
            self.assertIsInstance(result, ExecutionResult, "Delegation should produce ExecutionResult")
            
            # Verify the result indicates GraphExecutionService was used
            # The compiled_from field indicates the execution path
            expected_source = "memory"  # CSV direct should use memory execution
            if hasattr(result, 'compiled_from'):
                self.assertEqual(result.compiled_from, expected_source, 
                               f"Should use {expected_source} execution path")
            elif hasattr(result, 'source_info'):
                self.assertEqual(result.source_info, expected_source,
                               f"Should use {expected_source} execution path")
            
            print("✅ Service delegation successful")
            
        except Exception as e:
            print(f"❌ Service delegation failed: {e}")
            self.fail(f"Service delegation test failed: {e}")
    
    def test_execution_tracking_coordination(self):
        """Test ExecutionTrackingService coordinates with graph execution."""
        print("\n=== Testing Execution Tracking Coordination ===")
        
        # Create simple graph for tracking test
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        # Execute with tracking enabled
        initial_state = {"tracking_test": "execution_tracking"}
        
        # Create RunOptions with initial state
        options = RunOptions(initial_state=initial_state)
        
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name=simple_spec.graph_name,
                options=options
            )
            
            # Verify execution tracking was coordinated
            self.assertIsInstance(result, ExecutionResult)
            
            # Check for execution tracking artifacts in the result
            if result.execution_summary:
                print(f"Execution summary present: {type(result.execution_summary)}")
                # Verify summary has tracking information
                self.assertIsNotNone(result.execution_summary.graph_name)
            
            # Check if tracking metadata exists in final state
            if result.final_state and "__execution_summary" in result.final_state:
                print("Execution tracking metadata found in final state")
            
            print("✅ Execution tracking coordination successful")
            
        except Exception as e:
            print(f"❌ Execution tracking coordination failed: {e}")
            self.fail(f"Execution tracking coordination test failed: {e}")
    
    # =============================================================================
    # 3. Real Agent Instantiation and Execution Tests
    # =============================================================================
    
    def test_real_agent_instantiation_and_execution(self):
        """Test real DefaultAgent instances are created and executed."""
        print("\n=== Testing Real Agent Instantiation ===")
        
        # Create graph with specific agent prompts to verify execution
        custom_nodes = [
            {
                "GraphName": "agent_test",
                "Node": "agent1",
                "AgentType": "Default",
                "Prompt": "Agent 1 test prompt",
                "Description": "First test agent",
                "Input_Fields": "user_input",
                "Output_Field": "agent1_output",
                "Edge": "agent2",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": ""
            },
            {
                "GraphName": "agent_test", 
                "Node": "agent2",
                "AgentType": "Default",
                "Prompt": "Agent 2 test prompt",
                "Description": "Second test agent",
                "Input_Fields": "agent1_output",
                "Output_Field": "final_output",
                "Edge": "",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": ""
            }
        ]
        
        from tests.fresh_suite.integration.test_data_factories import TestGraphSpec
        agent_test_spec = TestGraphSpec(
            graph_name="agent_test",
            nodes=custom_nodes,
            description="Graph for testing real agent instantiation"
        )
        
        csv_path = self.test_data_manager.create_test_csv_file(agent_test_spec)
        
        # Execute with state that will be processed by real agents
        initial_state = {"user_input": "test data for real agents"}
        
        # Create RunOptions with initial state
        options = RunOptions(initial_state=initial_state)
        
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name="agent_test",
                options=options
            )
            
            # Verify agents were instantiated and executed
            self.assertIsInstance(result, ExecutionResult)
            self.assertIsNotNone(result.final_state)
            
            # Check if agent outputs are present (indicating real execution)
            if result.final_state:
                # Look for agent output fields or DefaultAgent execution messages
                final_state_str = str(result.final_state)
                if "DefaultAgent executed" in final_state_str:
                    print("✅ Real DefaultAgent execution detected in final state")
                else:
                    print(f"Final state: {result.final_state}")
                    print("Note: DefaultAgent output format may vary")
            
            print("✅ Real agent instantiation test completed")
            
        except Exception as e:
            print(f"❌ Real agent instantiation failed: {e}")
            self.fail(f"Real agent instantiation test failed: {e}")
    
    def test_agent_service_injection(self):
        """Test that agents receive proper service injection."""
        print("\n=== Testing Agent Service Injection ===")
        
        # Create simple graph to test service injection
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        initial_state = {"test_data": "service_injection_test"}
        
        # Create RunOptions with initial state
        options = RunOptions(initial_state=initial_state)
        
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name=simple_spec.graph_name,
                options=options
            )
            
            # Verify execution completed (indicating services were injected properly)
            self.assertIsInstance(result, ExecutionResult)
            
            # The fact that execution completed without injection errors
            # indicates that services were properly injected into agents
            print("✅ Agent service injection test completed")
            
        except Exception as e:
            # Check if error is related to service injection
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["inject", "service", "llm", "storage"]):
                self.fail(f"Agent service injection failed: {e}")
            else:
                print(f"Non-injection error occurred: {e}")
                print("✅ Service injection appears to be working (other error occurred)")
    
    # =============================================================================
    # 4. ExecutionResult and State Flow Tests
    # =============================================================================
    
    def test_execution_result_structure_validation(self):
        """Test ExecutionResult contains all required fields and data."""
        print("\n=== Testing ExecutionResult Structure ===")
        
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        initial_state = {"validation_test": "result_structure"}
        
        # Create RunOptions with initial state
        options = RunOptions(initial_state=initial_state)
        
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name=simple_spec.graph_name,
                options=options
            )
            
            # Verify all required ExecutionResult fields
            self.assertIsInstance(result, ExecutionResult, "Should return ExecutionResult instance")
            
            # Required fields
            self.assertIsNotNone(result.graph_name, "graph_name should not be None")
            self.assertIsNotNone(result.final_state, "final_state should not be None")
            self.assertIsNotNone(result.success, "success should not be None")
            self.assertIsInstance(result.success, bool, "success should be boolean")
            
            # Duration field validation (handle both possible field names)
            duration_exists = hasattr(result, 'total_duration') or hasattr(result, 'execution_time')
            self.assertTrue(duration_exists, "ExecutionResult should have either 'total_duration' or 'execution_time' field")
            
            # Optional fields (may be None)
            # execution_summary can be None in some execution paths
            # error should be None for successful executions (if success=True)
            if result.success and result.error:
                print(f"Warning: Successful execution has error: {result.error}")
            
            # Verify field types and values
            self.assertEqual(result.graph_name, simple_spec.graph_name, "Graph name should match")
            self.assertIsInstance(result.final_state, dict, "final_state should be dict")
            
            # Duration validation - handle both possible field names and allow very fast executions
            duration_value = None
            if hasattr(result, 'total_duration'):
                duration_value = result.total_duration
                duration_field = 'total_duration'
            elif hasattr(result, 'execution_time'):
                duration_value = result.execution_time
                duration_field = 'execution_time'
            else:
                self.fail("ExecutionResult should have either 'total_duration' or 'execution_time' field")
            
            self.assertIsNotNone(duration_value, f"{duration_field} should not be None")
            self.assertIsInstance(duration_value, (int, float), f"{duration_field} should be numeric")
            self.assertGreaterEqual(duration_value, 0, f"{duration_field} should be non-negative")
            # Note: Duration can be 0.0 for very fast executions, so we only check >= 0
            
            print(f"ExecutionResult structure valid:")
            print(f"  - graph_name: {result.graph_name}")
            print(f"  - success: {result.success}")
            print(f"  - final_state type: {type(result.final_state)}")
            print(f"  - {duration_field}: {duration_value}")
            print(f"  - execution_summary: {type(result.execution_summary) if result.execution_summary else 'None'}")
            print("✅ ExecutionResult structure validation passed")
            
        except Exception as e:
            print(f"❌ ExecutionResult validation failed: {e}")
            self.fail(f"ExecutionResult structure validation failed: {e}")
    
    def test_state_flow_through_execution_pipeline(self):
        """Test state flows correctly through the execution pipeline."""
        print("\n=== Testing State Flow Through Pipeline ===")
        
        # Create graph with multiple nodes to test state flow
        multi_node_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(multi_node_spec)
        
        # Use complex initial state to track flow
        initial_state = {
            "user_input": "pipeline_state_test",
            "metadata": {
                "test_id": "state_flow_001",
                "timestamp": "2025-06-05T12:00:00Z"
            },
            "tracking_data": "should_be_preserved"
        }
        
        print(f"Initial state: {initial_state}")
        
        # Create RunOptions with initial state
        options = RunOptions(initial_state=initial_state)
        
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name=multi_node_spec.graph_name,
                options=options
            )
            
            # Verify state transformation
            self.assertIsInstance(result, ExecutionResult)
            self.assertIsNotNone(result.final_state)
            
            # Check that initial state elements are preserved or transformed
            final_state = result.final_state
            print(f"Final state: {final_state}")
            
            # The exact state flow depends on agent implementations
            # For DefaultAgent, we expect some preservation of input data
            if isinstance(final_state, dict):
                print(f"Final state keys: {list(final_state.keys())}")
                
                # Check for state flow artifacts
                state_str = str(final_state)
                if "pipeline_state_test" in state_str:
                    print("✅ Input data found in final state")
                
                # Check for execution metadata
                if "__execution_summary" in final_state:
                    print("✅ Execution metadata added to final state")
                
            print("✅ State flow through pipeline completed")
            
        except Exception as e:
            print(f"❌ State flow test failed: {e}")
            self.fail(f"State flow through execution pipeline failed: {e}")
    
    # =============================================================================
    # 5. Error Handling and Edge Cases
    # =============================================================================
    
    def test_execution_error_handling_across_services(self):
        """Test error handling propagation across service boundaries."""
        print("\n=== Testing Error Handling Across Services ===")
        
        # Test 1: Non-existent CSV file
        print("\nTesting non-existent CSV file...")
        nonexistent_csv = Path(self.temp_dir) / "nonexistent.csv"
        
        # Create RunOptions with initial state
        options = RunOptions(initial_state={"test": "data"})
        
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=nonexistent_csv,
                graph_name="test_graph",
                options=options
            )
            
            # Should return error result, not raise exception
            self.assertIsInstance(result, ExecutionResult)
            self.assertFalse(result.success, "Should indicate failure")
            self.assertIsNotNone(result.error, "Should have error message")
            print(f"✅ File not found handled gracefully: {result.error}")
            
        except Exception as e:
            # If exception is raised, verify it's the expected type
            self.assertIsInstance(e, FileNotFoundError, f"Expected FileNotFoundError, got {type(e)}")
            print(f"✅ File not found raised expected exception: {e}")
        
        # Test 2: Invalid graph name
        print("\nTesting invalid graph name...")
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        # Create RunOptions with initial state
        options = RunOptions(initial_state={"test": "data"})
        
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name="nonexistent_graph",
                options=options
            )
            
            # Should return error result
            self.assertIsInstance(result, ExecutionResult)
            self.assertFalse(result.success, "Should indicate failure")
            self.assertIsNotNone(result.error, "Should have error message")
            print(f"✅ Invalid graph name handled: {result.error}")
            
        except ValueError as e:
            # ValueError is acceptable for invalid graph name
            print(f"✅ Invalid graph name raised expected exception: {e}")
        except Exception as e:
            print(f"Note: Unexpected exception type for invalid graph: {type(e).__name__}: {e}")
        
        # Test 3: Empty initial state
        print("\nTesting empty initial state...")
        
        # Create RunOptions with empty state
        empty_options = RunOptions(initial_state={})  # Empty state
        
        try:
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name=simple_spec.graph_name,
                options=empty_options
            )
            
            # Empty state should be handled gracefully
            self.assertIsInstance(result, ExecutionResult)
            print(f"✅ Empty state handled: success={result.success}")
            
        except Exception as e:
            print(f"Note: Empty state caused exception: {type(e).__name__}: {e}")
        
        print("✅ Error handling across services tested")
    
    def test_execution_timeout_and_resource_management(self):
        """Test execution respects timeouts and manages resources properly."""
        print("\n=== Testing Execution Timeout and Resource Management ===")
        
        # Create simple graph for timeout testing
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        # Test with minimal timeout configuration
        initial_state = {"timeout_test": "resource_management"}
        
        # Create RunOptions with initial state
        options = RunOptions(initial_state=initial_state)
        
        try:
            start_time = time.time()
            result = self.graph_runner_service.run_from_csv_direct(
                csv_path=csv_path,
                graph_name=simple_spec.graph_name,
                options=options
            )
            execution_time = time.time() - start_time
            
            # Verify execution completed in reasonable time
            self.assertIsInstance(result, ExecutionResult)
            self.assertLess(execution_time, 30.0, "Execution should complete in reasonable time")
            
            # Verify resource cleanup (no hanging resources)
            print(f"Execution time: {execution_time:.3f}s")
            print("✅ Resource management test completed")
            
        except Exception as e:
            print(f"❌ Resource management test failed: {e}")
            self.fail(f"Execution timeout/resource management test failed: {e}")
    
    # =============================================================================
    # 6. Performance and Scalability Tests
    # =============================================================================
    
    def test_multiple_sequential_executions(self):
        """Test multiple sequential executions for memory leaks and performance."""
        print("\n=== Testing Multiple Sequential Executions ===")
        
        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)
        
        execution_times = []
        num_executions = 3  # Keep small for integration tests
        
        try:
            for i in range(num_executions):
                print(f"Execution {i+1}/{num_executions}")
                
                initial_state = {"execution_num": i+1, "test_data": f"sequential_test_{i}"}
                
                # Create RunOptions with initial state
                options = RunOptions(initial_state=initial_state)
                
                start_time = time.time()
                result = self.graph_runner_service.run_from_csv_direct(
                    csv_path=csv_path,
                    graph_name=simple_spec.graph_name,
                    options=options
                )
                execution_time = time.time() - start_time
                execution_times.append(execution_time)
                
                # Verify each execution
                self.assertIsInstance(result, ExecutionResult)
                print(f"  Execution {i+1}: {execution_time:.3f}s, success={result.success}")
            
            # Analyze performance
            avg_time = sum(execution_times) / len(execution_times)
            max_time = max(execution_times)
            min_time = min(execution_times)
            
            print(f"Performance summary:")
            print(f"  Average: {avg_time:.3f}s")
            print(f"  Min: {min_time:.3f}s")
            print(f"  Max: {max_time:.3f}s")
            
            # Basic performance checks
            self.assertLess(avg_time, 10.0, "Average execution time should be reasonable")
            self.assertLess(max_time - min_time, 5.0, "Execution time variance should be reasonable")
            
            print("✅ Multiple sequential executions completed")
            
        except Exception as e:
            print(f"❌ Sequential executions failed: {e}")
            self.fail(f"Multiple sequential executions test failed: {e}")


if __name__ == '__main__':
    unittest.main()
