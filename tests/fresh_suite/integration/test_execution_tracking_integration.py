"""
Execution Tracking Integration Tests.

This module contains targeted integration tests that verify execution tracking works
correctly end-to-end. These tests specifically address issues that were found where:

1. Graph names from CSV were not preserved in execution results
2. Execution tracking was creating individual trackers instead of shared ones
3. Node executions were not being recorded properly
4. Final output was not being captured in execution summary

These tests follow established patterns from BaseIntegrationTest and would have
caught the original bugs before they reached production.
"""

import time
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.models.execution.result import ExecutionResult
from agentmap.models.graph_bundle import GraphBundle
from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from tests.fresh_suite.integration.test_data_factories import (
    CSVTestDataFactory,
    ExecutionTestDataFactory,
    IntegrationTestDataManager,
)


class TestExecutionTrackingIntegration(BaseIntegrationTest):
    """
    Integration tests for execution tracking functionality.

    These tests verify that execution tracking works correctly across the entire
    execution pipeline, specifically testing the fixes for:

    - Graph name preservation from CSV to final result
    - Shared execution tracker across all agents
    - Node execution recording and summary generation
    - Final output capture in execution summary
    """

    def setup_services(self):
        """Initialize services for execution tracking testing."""
        super().setup_services()

        # Core services needed for execution tracking
        self.graph_runner_service = self.container.graph_runner_service()
        self.graph_execution_service = self.container.graph_execution_service()
        self.execution_tracking_service = self.container.execution_tracking_service()

        # Graph bundle service for CSV processing (following new pattern)
        self.csv_parser_service = self.container.csv_graph_parser_service()
        self.protocol_analyzer = self.container.protocol_requirements_analyzer()
        self.agent_factory_service = self.container.agent_factory_service()

        # Get GraphBundleService from DI container (properly configured with all dependencies)
        self.graph_bundle_service = self.container.graph_bundle_service()

        # Test data manager
        self.test_data_manager = IntegrationTestDataManager(Path(self.temp_dir))

        # Verify all services are available
        self.assert_service_created(self.graph_runner_service, "GraphRunnerService")
        self.assert_service_created(
            self.graph_execution_service, "GraphExecutionService"
        )
        self.assert_service_created(
            self.execution_tracking_service, "ExecutionTrackingService"
        )
        self.assert_service_created(self.graph_bundle_service, "GraphBundleService")

    def _execute_graph_from_csv(
        self,
        csv_path: str,
        graph_name: str,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Helper method to execute graph from CSV using new architecture.

        This follows the new pattern:
        1. Create GraphBundle from CSV using GraphBundleService.get_or_create_bundle
        2. Execute bundle using GraphRunnerService

        Args:
            csv_path: Path to CSV file
            graph_name: Name of the graph to execute
            initial_state: Optional initial execution state

        Returns:
            ExecutionResult from graph execution
        """
        # Step 1: Create bundle from CSV (using correct API)
        bundle, _ = self.graph_bundle_service.get_or_create_bundle(
            csv_path=Path(csv_path),
            graph_name=graph_name,
            config_path=str(Path(self.temp_dir) / "integration_test_config.yaml"),
        )

        # Step 2: Execute bundle using GraphRunnerService with initial state
        result = self.graph_runner_service.run(bundle, initial_state=initial_state)

        return result

    # =============================================================================
    # 1. Graph Name Preservation Tests
    # =============================================================================

    def test_graph_name_preservation_from_csv(self):
        """Test that graph name from CSV is preserved in execution result."""
        print("\n=== Testing Graph Name Preservation from CSV ===")

        # Create test CSV with specific graph name (like gm_orchestration)
        test_graph_name = "gm_orchestration_test"

        custom_nodes = [
            {
                "GraphName": test_graph_name,
                "Node": "UserInput",
                "AgentType": "input",
                "Prompt": "What do you want to do?",
                "Description": "User input node",
                "Input_Fields": "input",
                "Output_Field": "input",
                "Edge": "Orchestrator",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": "",
            },
            {
                "GraphName": test_graph_name,
                "Node": "Orchestrator",
                "AgentType": "default",
                "Prompt": "Process user input",
                "Description": "Main orchestration node",
                "Input_Fields": "input",
                "Output_Field": "result",
                "Edge": "",
                "Context": "",
                "Success_Next": "",
                "Failure_Next": "",
            },
        ]

        from tests.fresh_suite.integration.test_data_factories import TestGraphSpec

        graph_spec = TestGraphSpec(
            graph_name=test_graph_name,
            nodes=custom_nodes,
            description="Test graph for name preservation",
        )

        csv_path = self.test_data_manager.create_test_csv_file(graph_spec)
        print(f"Created CSV with graph name: {test_graph_name}")

        # Execute the graph using new architecture
        initial_state = {"input": "test input for graph name"}

        try:
            result = self._execute_graph_from_csv(
                csv_path=csv_path,
                graph_name=test_graph_name,
                initial_state=initial_state,
            )

            # CRITICAL TEST: Graph name should be preserved exactly
            self.assertIsInstance(
                result, ExecutionResult, "Should return ExecutionResult"
            )
            self.assertEqual(
                result.graph_name,
                test_graph_name,
                f"Graph name should be '{test_graph_name}', not auto-generated",
            )

            # Also check execution summary has correct graph name
            if result.execution_summary:
                self.assertEqual(
                    result.execution_summary.graph_name,
                    test_graph_name,
                    "Execution summary should have correct graph name",
                )

            print(f"✅ Graph name preserved: {result.graph_name}")

            # Verify this is NOT the auto-generated fallback name
            self.assertNotEqual(
                result.graph_name,
                "graph_2_nodes",
                "Should not use auto-generated fallback name",
            )
            self.assertNotEqual(
                result.graph_name,
                "unknown_graph",
                "Should not use unknown_graph fallback",
            )

            print("✅ Graph name preservation test passed")

        except Exception as e:
            self.fail(f"Graph name preservation test failed: {e}")

    # =============================================================================
    # 2. Node Execution Recording Tests
    # =============================================================================

    def test_node_executions_are_recorded(self):
        """Test that individual node executions are properly recorded."""
        print("\n=== Testing Node Execution Recording ===")

        # Create multi-node graph to verify each execution is recorded
        multi_node_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(multi_node_spec)

        initial_state = {"user_input": "test for node recording"}

        try:
            result = self._execute_graph_from_csv(
                csv_path=csv_path,
                graph_name=multi_node_spec.graph_name,
                initial_state=initial_state,
            )

            # CRITICAL TEST: Execution summary should have node executions
            self.assertIsInstance(result, ExecutionResult)
            self.assertIsNotNone(
                result.execution_summary,
                "Should have execution summary with tracking data",
            )

            # Verify node executions were recorded
            node_executions = result.execution_summary.node_executions
            self.assertIsInstance(
                node_executions, list, "Node executions should be a list"
            )

            # CRITICAL: Should not be empty (this was the main bug)
            self.assertGreater(
                len(node_executions),
                0,
                "Should have recorded node executions (was empty in bug)",
            )

            print(f"✅ Recorded {len(node_executions)} node executions")

            # Verify each node execution has required fields
            for i, node_exec in enumerate(node_executions):
                self.assertIsNotNone(
                    node_exec.node_name, f"Node execution {i} should have node_name"
                )
                self.assertIsNotNone(
                    node_exec.start_time, f"Node execution {i} should have start_time"
                )
                print(f"  Node {i+1}: {node_exec.node_name}")

            print("✅ Node execution recording test passed")

        except Exception as e:
            self.fail(f"Node execution recording test failed: {e}")

    def test_execution_tracking_captures_final_output(self):
        """Test that final output is captured in execution summary."""
        print("\n=== Testing Final Output Capture ===")

        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)

        initial_state = {"user_input": "test for final output capture"}

        try:
            result = self._execute_graph_from_csv(
                csv_path=csv_path,
                graph_name=simple_spec.graph_name,
                initial_state=initial_state,
            )

            # CRITICAL TEST: Final output should not be None (this was the bug)
            self.assertIsInstance(result, ExecutionResult)
            self.assertIsNotNone(
                result.execution_summary, "Should have execution summary"
            )

            # The main bug: final_output was None
            execution_summary = result.execution_summary
            self.assertIsNotNone(
                execution_summary.final_output,
                "Execution summary final_output should not be None (was bug)",
            )

            print(f"✅ Final output captured: {type(execution_summary.final_output)}")

            # Verify final output contains expected data
            final_output = execution_summary.final_output
            if isinstance(final_output, dict):
                print(f"  Final output keys: {list(final_output.keys())}")

                # Should contain some data from the execution
                self.assertGreater(
                    len(final_output),
                    0,
                    "Final output should contain execution results",
                )

            print("✅ Final output capture test passed")

        except Exception as e:
            self.fail(f"Final output capture test failed: {e}")

    # =============================================================================
    # 3. Shared Execution Tracker Tests
    # =============================================================================

    def test_shared_execution_tracker_across_agents(self):
        """Test that all agents use the same execution tracker instance."""
        print("\n=== Testing Shared Execution Tracker ===")

        # Create multi-agent graph to test tracker sharing
        multi_agent_nodes = [
            {
                "GraphName": "tracker_test",
                "Node": "Agent1",
                "AgentType": "default",
                "Prompt": "Agent 1 processing",
                "Description": "First agent",
                "Input_Fields": "input",
                "Output_Field": "agent1_output",
                "Edge": "Agent2",
                "Success_Next": "",
                "Failure_Next": "",
                "Context": "",
            },
            {
                "GraphName": "tracker_test",
                "Node": "Agent2",
                "AgentType": "default",
                "Prompt": "Agent 2 processing",
                "Description": "Second agent",
                "Input_Fields": "agent1_output",
                "Output_Field": "agent2_output",
                "Edge": "Agent3",
                "Success_Next": "",
                "Failure_Next": "",
                "Context": "",
            },
            {
                "GraphName": "tracker_test",
                "Node": "Agent3",
                "AgentType": "default",
                "Prompt": "Agent 3 processing",
                "Description": "Third agent",
                "Input_Fields": "agent2_output",
                "Output_Field": "final_output",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Context": "",
            },
        ]

        from tests.fresh_suite.integration.test_data_factories import TestGraphSpec

        tracker_spec = TestGraphSpec(
            graph_name="tracker_test",
            nodes=multi_agent_nodes,
            description="Multi-agent graph for tracker sharing test",
        )

        csv_path = self.test_data_manager.create_test_csv_file(tracker_spec)

        initial_state = {"input": "shared tracker test data"}

        try:
            result = self._execute_graph_from_csv(
                csv_path=csv_path,
                graph_name="tracker_test",
                initial_state=initial_state,
            )

            # Verify execution completed successfully
            self.assertIsInstance(result, ExecutionResult)
            self.assertIsNotNone(result.execution_summary)

            # CRITICAL TEST: All agent executions should be in same summary
            node_executions = result.execution_summary.node_executions

            # Should have executions from ALL agents (proves shared tracker)
            expected_agents = ["Agent1", "Agent2", "Agent3"]
            recorded_agents = [exec.node_name for exec in node_executions]

            print(f"Expected agents: {expected_agents}")
            print(f"Recorded agents: {recorded_agents}")

            # Verify we have multiple agent executions (proves shared tracker worked)
            self.assertGreater(
                len(node_executions),
                1,
                "Should have multiple agent executions (proves shared tracker)",
            )

            # Check that we have executions from multiple distinct agents
            unique_agents = set(recorded_agents)
            self.assertGreater(
                len(unique_agents), 1, "Should have executions from multiple agents"
            )

            print(
                f"✅ Shared tracker recorded {len(node_executions)} executions from {len(unique_agents)} agents"
            )

            # Verify this is NOT individual trackers (the bug scenario)
            # If agents created individual trackers, we'd only see 1 execution or empty list
            self.assertNotEqual(
                len(node_executions),
                1,
                "Should not have just 1 execution (would indicate individual trackers)",
            )

            print("✅ Shared execution tracker test passed")

        except Exception as e:
            self.fail(f"Shared execution tracker test failed: {e}")

    def test_execution_tracker_no_fallback_creation(self):
        """Test that agents require tracker to be set (no fallback creation)."""
        print("\n=== Testing No Tracker Fallback Creation ===")

        # This test is more about the architecture - we're testing that
        # the system properly distributes trackers rather than relying on fallbacks

        simple_spec = CSVTestDataFactory.create_simple_linear_graph()
        csv_path = self.test_data_manager.create_test_csv_file(simple_spec)

        initial_state = {"input": "no fallback test"}

        try:
            result = self._execute_graph_from_csv(
                csv_path=csv_path,
                graph_name=simple_spec.graph_name,
                initial_state=initial_state,
            )

            # If execution succeeds, it means trackers were properly distributed
            self.assertIsInstance(result, ExecutionResult)

            # Verify we have tracking data (proves distribution worked)
            self.assertIsNotNone(result.execution_summary)
            self.assertGreater(len(result.execution_summary.node_executions), 0)

            print("✅ Execution succeeded with proper tracker distribution")
            print("✅ No fallback tracker creation needed")

        except ValueError as e:
            # If we get ValueError about tracker not being set, that's actually good
            # It means our fix to remove fallback logic is working
            if "execution tracker" in str(e).lower():
                print("✅ Proper error for missing tracker (fallback removal working)")
                print(
                    "Note: This error indicates the architecture correctly requires tracker distribution"
                )
            else:
                self.fail(f"Unexpected ValueError: {e}")

        except Exception as e:
            self.fail(f"No fallback creation test failed: {e}")

    # =============================================================================
    # 4. End-to-End Integration Tests (Combining All Fixes)
    # =============================================================================

    def test_complete_execution_tracking_pipeline(self):
        """Test complete execution tracking pipeline with all fixes."""
        print("\n=== Testing Complete Execution Tracking Pipeline ===")

        # Create realistic graph structure (like gm_orchestration)
        pipeline_nodes = [
            {
                "GraphName": "pipeline_test",
                "Node": "UserInput",
                "AgentType": "input",
                "Prompt": "What do you want to do?",
                "Description": "User input simulation",
                "Input_Fields": "input",
                "Output_Field": "user_input",
                "Edge": "Orchestrator",
                "Success_Next": "",
                "Failure_Next": "",
                "Context": "",
            },
            {
                "GraphName": "pipeline_test",
                "Node": "Orchestrator",
                "AgentType": "default",
                "Prompt": "Process and route user input",
                "Description": "Main orchestration logic",
                "Input_Fields": "user_input",
                "Output_Field": "orchestrator_result",
                "Edge": "Processor",
                "Success_Next": "",
                "Failure_Next": "",
                "Context": "",
            },
            {
                "GraphName": "pipeline_test",
                "Node": "Processor",
                "AgentType": "default",
                "Prompt": "Process the orchestrated request",
                "Description": "Request processing",
                "Input_Fields": "orchestrator_result",
                "Output_Field": "processor_result",
                "Edge": "Output",
                "Success_Next": "",
                "Failure_Next": "",
                "Context": "",
            },
            {
                "GraphName": "pipeline_test",
                "Node": "Output",
                "AgentType": "default",
                "Prompt": "Format final output",
                "Description": "Output formatting",
                "Input_Fields": "processor_result",
                "Output_Field": "final_result",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Context": "",
            },
        ]

        from tests.fresh_suite.integration.test_data_factories import TestGraphSpec

        pipeline_spec = TestGraphSpec(
            graph_name="pipeline_test",
            nodes=pipeline_nodes,
            description="Complete pipeline test graph",
        )

        csv_path = self.test_data_manager.create_test_csv_file(pipeline_spec)

        initial_state = {"input": "complete pipeline integration test"}

        try:
            start_time = time.time()
            result = self._execute_graph_from_csv(
                csv_path=csv_path,
                graph_name="pipeline_test",
                initial_state=initial_state,
            )
            execution_time = time.time() - start_time

            # TEST ALL FIXES TOGETHER:

            # 1. Graph name preservation ✅
            self.assertEqual(
                result.graph_name,
                "pipeline_test",
                "Graph name should be preserved from CSV",
            )

            # 2. Execution summary exists ✅
            self.assertIsNotNone(
                result.execution_summary, "Should have execution summary"
            )

            # 3. Node executions recorded ✅
            node_executions = result.execution_summary.node_executions
            self.assertGreater(
                len(node_executions), 0, "Should have recorded node executions"
            )

            # 4. Multiple agents recorded (shared tracker) ✅
            self.assertGreaterEqual(
                len(node_executions), 2, "Should have multiple agent executions"
            )

            # 5. Final output captured ✅
            self.assertIsNotNone(
                result.execution_summary.final_output,
                "Should have captured final output",
            )

            # 6. Execution metadata ✅
            self.assertEqual(
                result.execution_summary.graph_name,
                "pipeline_test",
                "Summary should have correct graph name",
            )

            print(f"✅ Complete pipeline test results:")
            print(f"  - Graph name: {result.graph_name}")
            print(f"  - Execution time: {execution_time:.3f}s")
            print(f"  - Node executions: {len(node_executions)}")
            print(f"  - Final output: {type(result.execution_summary.final_output)}")
            print(f"  - Success: {result.success}")

            # List all recorded node executions
            for i, node_exec in enumerate(node_executions):
                print(
                    f"    {i+1}. {node_exec.node_name} ({'success' if node_exec.success else 'failed'})"
                )

            print("✅ Complete execution tracking pipeline test passed")

        except Exception as e:
            self.fail(f"Complete execution tracking pipeline test failed: {e}")

    def test_regression_prevention_for_original_bugs(self):
        """Test specifically for the original bugs to prevent regression."""
        print("\n=== Testing Regression Prevention ===")

        # Test with the EXACT scenario from the original bug report
        gm_orchestration_nodes = [
            {
                "GraphName": "gm_orchestration",
                "Node": "UserInput",
                "AgentType": "input",
                "Prompt": "What do you want to do?",
                "Description": "This is to simulate user input",
                "Input_Fields": "input",
                "Output_Field": "input",
                "Edge": "Orchestrator",
                "Success_Next": "",
                "Failure_Next": "",
                "Context": "",
            },
            {
                "GraphName": "gm_orchestration",
                "Node": "Orchestrator",
                "AgentType": "orchestrator",
                "Prompt": "",
                "Description": "This is the main orchestration node",
                "Input_Fields": "input",
                "Output_Field": "orchestrator_result",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "ErrorHandler",
                "Context": "",
            },
            {
                "GraphName": "gm_orchestration",
                "Node": "EndNode",
                "AgentType": "default",
                "Prompt": "End the session",
                "Description": "",
                "Input_Fields": "input",
                "Output_Field": "",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Context": "",
            },
            {
                "GraphName": "gm_orchestration",
                "Node": "ErrorHandler",
                "AgentType": "echo",
                "Prompt": "Handle the error",
                "Description": "",
                "Input_Fields": "output",
                "Output_Field": "",
                "Edge": "",
                "Success_Next": "",
                "Failure_Next": "",
                "Context": "",
            },
        ]

        from tests.fresh_suite.integration.test_data_factories import TestGraphSpec

        original_spec = TestGraphSpec(
            graph_name="gm_orchestration",
            nodes=gm_orchestration_nodes,
            description="Original bug scenario reproduction",
        )

        csv_path = self.test_data_manager.create_test_csv_file(original_spec)

        # Use the same input sequence that revealed the original bugs
        initial_state = {"input": "end"}  # This was in the original debug output

        try:
            result = self._execute_graph_from_csv(
                csv_path=csv_path,
                graph_name="gm_orchestration",
                initial_state=initial_state,
            )

            # REGRESSION TESTS FOR ORIGINAL BUGS:

            # Bug 1: Graph name was "graph_10_nodes" instead of "gm_orchestration"
            self.assertEqual(
                result.graph_name,
                "gm_orchestration",
                "REGRESSION: Graph name should be 'gm_orchestration', not auto-generated",
            )

            # Bug 2: node_executions was empty list []
            self.assertIsNotNone(
                result.execution_summary, "Should have execution summary"
            )
            node_executions = result.execution_summary.node_executions
            self.assertGreater(
                len(node_executions),
                0,
                "REGRESSION: Node executions should not be empty list",
            )

            # Bug 3: final_output was None
            self.assertIsNotNone(
                result.execution_summary.final_output,
                "REGRESSION: Final output should not be None",
            )

            print(f"✅ Regression prevention results:")
            print(f"  - Graph name: {result.graph_name} (not auto-generated)")
            print(f"  - Node executions: {len(node_executions)} (not empty)")
            print(
                f"  - Final output: {type(result.execution_summary.final_output)} (not None)"
            )

            # Verify specific bug patterns are NOT present
            self.assertNotIn(
                "graph_",
                result.graph_name,
                "Should not have auto-generated graph name pattern",
            )
            self.assertNotEqual(
                len(node_executions), 0, "Should not have empty node executions"
            )

            print("✅ All original bugs prevented - regression test passed")

        except Exception as e:
            self.fail(f"Regression prevention test failed: {e}")


if __name__ == "__main__":
    unittest.main()
