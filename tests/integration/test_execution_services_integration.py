"""
Integration tests for ExecutionPolicyService, StateAdapterService, and ExecutionTrackingService.

These tests use real dependencies and verify that the services work correctly
together in realistic scenarios, following existing integration test patterns.
"""

import time
import unittest
from unittest.mock import Mock

from agentmap.services.execution_policy_service import ExecutionPolicyService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.execution_tracking_service import ExecutionTrackingService, ExecutionTracker


class TestExecutionServicesIntegration(unittest.TestCase):
    """Integration tests for execution services with real dependencies."""
    
    def setUp(self):
        """Set up test fixtures with real but minimal dependencies."""
        # Create real but minimal dependencies for integration testing
        self.logging_service = Mock()
        self.logger = Mock()
        self.logging_service.get_class_logger.return_value = self.logger
        
        self.config_service = Mock()
        
        # Create service instances
        self.policy_service = ExecutionPolicyService(
            app_config_service=self.config_service,
            logging_service=self.logging_service
        )
        
        self.state_service = StateAdapterService(
            app_config_service=self.config_service,
            logging_service=self.logging_service
        )
        
        self.tracking_service = ExecutionTrackingService(
            app_config_service=self.config_service,
            logging_service=self.logging_service
        )
    
    def test_policy_service_integration(self):
        """Test ExecutionPolicyService integration with real dependencies."""
        # Mock execution configuration
        execution_config = {
            "success_policy": {
                "type": "all_nodes"
            }
        }
        self.config_service.get_execution_config.return_value = execution_config
        
        # Create test execution summary
        test_summary = {
            "overall_success": True,
            "execution_path": [
                {"node_name": "Node1", "success": True, "duration": 1.0},
                {"node_name": "Node2", "success": True, "duration": 1.5}
            ]
        }
        
        # Test policy evaluation (will use real policy evaluation logic)
        with self.assertLogs() as log_context:
            result = self.policy_service.evaluate_success_policy(test_summary)
        
        # Should return success for all_nodes policy with all successful nodes
        self.assertTrue(result)
        
        # Verify logging occurred
        self.logger.debug.assert_called()
        
        # Test available policies
        policies = self.policy_service.get_available_policies()
        self.assertIn("all_nodes", policies)
        self.assertIn("final_node", policies)
        self.assertIn("critical_nodes", policies)
        self.assertIn("custom", policies)
    
    def test_policy_service_validation_integration(self):
        """Test policy configuration validation integration."""
        # Test valid configurations
        valid_configs = [
            {"type": "all_nodes"},
            {"type": "final_node"},
            {"type": "critical_nodes", "critical_nodes": ["Node1", "Node2"]},
            {"type": "custom", "custom_function": "mymodule.path.function"}
        ]
        
        for config in valid_configs:
            with self.subTest(config=config):
                errors = self.policy_service.validate_policy_config(config)
                self.assertEqual(len(errors), 0, f"Valid config should have no errors: {config}")
        
        # Test invalid configurations
        invalid_configs = [
            {"type": "invalid_type"},
            {"type": "critical_nodes", "critical_nodes": []},
            {"type": "custom", "custom_function": "invalid_format"}
        ]
        
        for config in invalid_configs:
            with self.subTest(config=config):
                errors = self.policy_service.validate_policy_config(config)
                self.assertGreater(len(errors), 0, f"Invalid config should have errors: {config}")
    
    def test_state_service_integration(self):
        """Test StateAdapterService integration with real state manipulation."""
        # Test with dict state
        dict_state = {"key1": "value1", "existing": "data"}
        
        # Use real StateAdapter functionality
        result = self.state_service.set_value(dict_state, "new_key", "new_value")
        
        # Verify state was updated correctly
        self.assertIn("new_key", result)
        self.assertEqual(result["new_key"], "new_value")
        self.assertEqual(result["key1"], "value1")  # Existing data preserved
        self.assertEqual(result["existing"], "data")
        
        # Verify original state is unchanged (immutable update)
        self.assertNotIn("new_key", dict_state)
        
        # Test with object state
        class TestState:
            def __init__(self):
                self.existing_attr = "existing_value"
        
        obj_state = TestState()
        result_obj = self.state_service.set_value(obj_state, "new_attr", "new_value")
        
        # Verify object state update
        self.assertTrue(hasattr(result_obj, "new_attr"))
        self.assertEqual(result_obj.new_attr, "new_value")
        self.assertEqual(result_obj.existing_attr, "existing_value")
        
        # Verify logging occurred
        self.logger.debug.assert_called()
    
    def test_state_service_error_handling_integration(self):
        """Test StateAdapterService error handling integration."""
        # Test forbidden key handling
        test_state = {"key": "value"}
        
        with self.assertRaises(Exception):
            self.state_service.set_value(test_state, "__execution_tracker", "forbidden")
        
        # Verify error was logged
        self.logger.error.assert_called()
    
    def test_tracking_service_integration(self):
        """Test ExecutionTrackingService integration with real tracking."""
        # Mock tracking configuration
        tracking_config = {
            "enabled": True,
            "track_outputs": True,
            "track_inputs": True
        }
        execution_config = {"timeout": 300}
        
        self.config_service.get_tracking_config.return_value = tracking_config
        self.config_service.get_execution_config.return_value = execution_config
        
        # Create tracker through service
        tracker = self.tracking_service.create_tracker()
        
        # Verify tracker was created and initialized
        self.assertIsInstance(tracker, ExecutionTracker)
        self.assertEqual(len(tracker.execution_path), 0)
        self.assertTrue(tracker.overall_success)
        
        # Test tracking configuration
        config = self.tracking_service.get_tracking_config()
        self.assertEqual(config, tracking_config)
        
        # Test tracking enabled check
        self.assertTrue(self.tracking_service.is_tracking_enabled())
    
    def test_execution_tracker_full_workflow_integration(self):
        """Test ExecutionTracker through a complete execution workflow."""
        # Setup configuration
        tracking_config = {
            "enabled": True,
            "track_outputs": True,
            "track_inputs": True
        }
        execution_config = {"timeout": 300}
        
        self.config_service.get_tracking_config.return_value = tracking_config
        self.config_service.get_execution_config.return_value = execution_config
        
        # Create and use tracker
        tracker = self.tracking_service.create_tracker()
        
        # Simulate full execution workflow
        
        # Start first node
        tracker.record_node_start("InputNode", {"user_input": "test data"})
        time.sleep(0.01)  # Small delay for timing
        tracker.record_node_result("InputNode", True, {"processed_input": "processed test data"})
        
        # Start second node
        tracker.record_node_start("ProcessingNode", {"processed_input": "processed test data"})
        time.sleep(0.01)
        tracker.record_node_result("ProcessingNode", True, {"analysis": "data analysis result"})
        
        # Start third node that fails
        tracker.record_node_start("ValidationNode", {"analysis": "data analysis result"})
        time.sleep(0.01)
        tracker.record_node_result("ValidationNode", False, None, "Validation failed")
        
        # Complete execution
        tracker.complete_execution()
        
        # Get summary
        summary = tracker.get_summary()
        
        # Verify summary structure
        self.assertFalse(summary["overall_success"])  # Should be False due to ValidationNode failure
        self.assertEqual(len(summary["execution_path"]), 3)
        self.assertGreater(summary["total_duration"], 0)
        self.assertIsNotNone(summary["start_time"])
        self.assertIsNotNone(summary["end_time"])
        
        # Verify execution path details
        execution_path = summary["execution_path"]
        
        # First node
        input_record = execution_path[0]
        self.assertEqual(input_record["node_name"], "InputNode")
        self.assertTrue(input_record["success"])
        self.assertEqual(input_record["node_execution_number"], 1)
        self.assertIn("inputs", input_record)
        self.assertIn("result", input_record)
        
        # Second node
        processing_record = execution_path[1]
        self.assertEqual(processing_record["node_name"], "ProcessingNode")
        self.assertTrue(processing_record["success"])
        
        # Third node (failed)
        validation_record = execution_path[2]
        self.assertEqual(validation_record["node_name"], "ValidationNode")
        self.assertFalse(validation_record["success"])
        self.assertEqual(validation_record["error"], "Validation failed")
        self.assertIsNone(validation_record["result"])
    
    def test_tracker_subgraph_integration(self):
        """Test ExecutionTracker subgraph recording integration."""
        # Setup configuration
        tracking_config = {"enabled": True, "track_outputs": False, "track_inputs": False}
        execution_config = {"timeout": 300}
        
        self.config_service.get_tracking_config.return_value = tracking_config
        self.config_service.get_execution_config.return_value = execution_config
        
        # Create tracker
        tracker = self.tracking_service.create_tracker()
        
        # Start parent node
        tracker.record_node_start("ParentNode")
        
        # Record subgraph execution
        subgraph_summary = {
            "overall_success": True,
            "nodes": {
                "SubNode1": {"success": True, "duration": 0.5},
                "SubNode2": {"success": True, "duration": 0.3}
            },
            "total_duration": 0.8
        }
        
        tracker.record_subgraph_execution("DataProcessingSubgraph", subgraph_summary)
        
        # Complete parent node
        tracker.record_node_result("ParentNode", True, "parent_result")
        
        # Get summary
        summary = tracker.get_summary()
        
        # Verify subgraph integration
        self.assertEqual(summary["subgraph_executions"], 1)
        self.assertIn("DataProcessingSubgraph", summary["subgraph_details"])
        
        subgraph_details = summary["subgraph_details"]["DataProcessingSubgraph"]
        self.assertEqual(len(subgraph_details), 1)
        self.assertEqual(subgraph_details[0]["parent_node"], "ParentNode")
        self.assertTrue(subgraph_details[0]["success"])
        self.assertEqual(subgraph_details[0]["node_count"], 2)
        
        # Verify subgraph data is in execution path
        parent_record = summary["execution_path"][0]
        self.assertIn("subgraphs", parent_record)
        self.assertIn("DataProcessingSubgraph", parent_record["subgraphs"])
        self.assertEqual(parent_record["subgraphs"]["DataProcessingSubgraph"], subgraph_summary)
    
    def test_cross_service_coordination_integration(self):
        """Test coordination between all three execution services."""
        # Setup all services with real configuration
        execution_config = {
            "success_policy": {"type": "final_node"},
            "timeout": 300
        }
        tracking_config = {"enabled": True, "track_outputs": True, "track_inputs": True}
        
        self.config_service.get_execution_config.return_value = execution_config
        self.config_service.get_tracking_config.return_value = tracking_config
        
        # Create execution scenario
        tracker = self.tracking_service.create_tracker()
        
        # Simulate execution with mixed success/failure
        tracker.record_node_start("StartNode")
        tracker.record_node_result("StartNode", False, None, "Start failed")
        
        tracker.record_node_start("MiddleNode")
        tracker.record_node_result("MiddleNode", False, None, "Middle failed")
        
        tracker.record_node_start("FinalNode")
        tracker.record_node_result("FinalNode", True, "final_success")
        
        tracker.complete_execution()
        
        # Get tracking summary
        execution_summary = tracker.get_summary()
        
        # Verify tracking worked
        self.assertFalse(execution_summary["overall_success"])  # Raw tracking shows failure
        self.assertEqual(len(execution_summary["execution_path"]), 3)
        
        # Use policy service to evaluate success
        policy_result = self.policy_service.evaluate_success_policy(execution_summary)
        
        # Should be True because final_node policy only cares about final node success
        self.assertTrue(policy_result)
        
        # Test state manipulation during this execution
        initial_state = {
            "execution_id": "test_123",
            "status": "running"
        }
        
        # Update state with execution results
        updated_state = self.state_service.set_value(initial_state, "execution_summary", execution_summary)
        final_state = self.state_service.set_value(updated_state, "policy_result", policy_result)
        
        # Verify state coordination
        self.assertEqual(final_state["execution_id"], "test_123")
        self.assertEqual(final_state["status"], "running")
        self.assertEqual(final_state["execution_summary"], execution_summary)
        self.assertTrue(final_state["policy_result"])
        
        # Verify original state unchanged
        self.assertNotIn("execution_summary", initial_state)
        self.assertNotIn("policy_result", initial_state)
    
    def test_service_info_integration(self):
        """Test service info methods work correctly in integration."""
        # Test all service info methods
        policy_info = self.policy_service.get_service_info()
        state_info = self.state_service.get_service_info()
        tracking_info = self.tracking_service.get_service_info()
        
        # Verify policy service info
        self.assertEqual(policy_info["service"], "ExecutionPolicyService")
        self.assertIn("capabilities", policy_info)
        self.assertIn("available_policies", policy_info)
        
        # Verify state service info
        self.assertEqual(state_info["service"], "StateAdapterService")
        self.assertIn("yagni_compliance", state_info)
        self.assertIn("available_state_types", state_info)
        
        # Verify tracking service info
        self.assertEqual(tracking_info["service"], "ExecutionTrackingService")
        self.assertIn("tracker_methods", tracking_info)
        self.assertIn("architecture_note", tracking_info)
        
        # Verify all services report config availability
        self.assertTrue(policy_info["config_available"])
        self.assertTrue(state_info["config_available"])
        self.assertTrue(tracking_info["config_available"])
    
    def test_error_handling_integration(self):
        """Test error handling across all services in integration."""
        # Test policy service error handling
        self.config_service.get_execution_config.side_effect = Exception("Config error")
        
        # Should handle config error gracefully
        result = self.policy_service.evaluate_success_policy({"test": "summary"})
        self.assertFalse(result)  # Conservative failure result
        
        # Reset config service
        self.config_service.get_execution_config.side_effect = None
        self.config_service.get_execution_config.return_value = {"success_policy": {"type": "all_nodes"}}
        
        # Test state service error handling with forbidden key
        test_state = {"key": "value"}
        
        with self.assertRaises(Exception):
            self.state_service.set_value(test_state, "__execution_tracker", "forbidden")
        
        # Test tracking service with disabled tracking
        self.config_service.get_tracking_config.return_value = {"enabled": False}
        
        tracker = self.tracking_service.create_tracker()
        
        # Should still work but in minimal mode
        self.assertTrue(tracker.minimal_mode)
        self.assertFalse(tracker.track_outputs)
        self.assertFalse(tracker.track_inputs)
    
    def test_performance_integration(self):
        """Test performance characteristics in integration scenario."""
        # Setup for performance test
        tracking_config = {"enabled": True, "track_outputs": True, "track_inputs": True}
        execution_config = {"success_policy": {"type": "all_nodes"}}
        
        self.config_service.get_tracking_config.return_value = tracking_config
        self.config_service.get_execution_config.return_value = execution_config
        
        # Test with larger execution scenario
        tracker = self.tracking_service.create_tracker()
        
        # Record many node executions
        num_nodes = 50
        start_time = time.time()
        
        for i in range(num_nodes):
            node_name = f"Node_{i}"
            tracker.record_node_start(node_name, {"input": f"data_{i}"})
            tracker.record_node_result(node_name, True, {"output": f"result_{i}"})
        
        tracker.complete_execution()
        
        # Get summary and evaluate policy
        summary = tracker.get_summary()
        policy_result = self.policy_service.evaluate_success_policy(summary)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify performance is reasonable (should complete quickly)
        self.assertLess(total_time, 1.0, "Integration scenario should complete in under 1 second")
        
        # Verify all data was tracked correctly
        self.assertEqual(len(summary["execution_path"]), num_nodes)
        self.assertTrue(policy_result)
        self.assertTrue(summary["overall_success"])
        
        # Test state manipulation performance
        large_state = {f"key_{i}": f"value_{i}" for i in range(100)}
        
        state_start = time.time()
        result_state = self.state_service.set_value(large_state, "summary", summary)
        state_end = time.time()
        
        state_time = state_end - state_start
        self.assertLess(state_time, 0.1, "State manipulation should be fast")
        
        # Verify state integrity
        self.assertEqual(len(result_state), 101)  # 100 original + 1 new
        self.assertEqual(result_state["summary"], summary)


if __name__ == '__main__':
    unittest.main()
