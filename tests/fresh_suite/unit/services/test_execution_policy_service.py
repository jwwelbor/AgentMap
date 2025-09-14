"""
Unit tests for ExecutionPolicyService.

These tests validate the ExecutionPolicyService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
from typing import Dict, Any, List

from agentmap.services.execution_policy_service import ExecutionPolicyService
from agentmap.models.execution.summary import ExecutionSummary, NodeExecution
from tests.utils.mock_service_factory import MockServiceFactory


class TestExecutionPolicyService(unittest.TestCase):
    """Unit tests for ExecutionPolicyService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        
        # Initialize ExecutionPolicyService with mocked dependencies
        self.service = ExecutionPolicyService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.config, self.mock_app_config_service)
        self.assertIsNotNone(self.service.logger)
        
        # Verify logger is configured correctly
        self.assertEqual(self.service.logger.name, 'ExecutionPolicyService')
        
        # Verify get_class_logger was called during initialization
        self.mock_logging_service.get_class_logger.assert_called_once_with(self.service)
        
        # Verify initialization log message
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[1] == '[ExecutionPolicyService] Initialized' 
                          for call in logger_calls if call[0] == 'info'))
    
    def test_service_logs_status(self):
        """Test that service status logging works correctly."""
        # Verify initialization logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == 'info']
        self.assertTrue(any('[ExecutionPolicyService] Initialized' in call[1] 
                          for call in info_calls))
    
    # =============================================================================
    # Helper Methods
    # =============================================================================
    
    def create_mock_execution_summary(
        self,
        graph_name: str = "test_graph",
        node_executions: List[Dict[str, Any]] = None
    ) -> ExecutionSummary:
        """Create mock ExecutionSummary with realistic NodeExecution objects."""
        if node_executions is None:
            node_executions = [
                {"node_name": "node1", "success": True},
                {"node_name": "node2", "success": True}
            ]
        
        # Create NodeExecution objects
        node_exec_objects = []
        for i, node_data in enumerate(node_executions):
            start_time = datetime.now()
            end_time = datetime.now()
            
            node_execution = NodeExecution(
                node_name=node_data["node_name"],
                success=node_data["success"],
                start_time=start_time,
                end_time=end_time,
                duration=1.0,
                output=node_data.get("output", f"output_{i}"),
                error=node_data.get("error", None)
            )
            node_exec_objects.append(node_execution)
        
        # Create ExecutionSummary
        summary = ExecutionSummary(
            graph_name=graph_name,
            start_time=datetime.now(),
            end_time=datetime.now(),
            node_executions=node_exec_objects,
            final_output="final_result",
            status="completed"
        )
        
        return summary
    
    def configure_execution_config(self, policy_config: Dict[str, Any]) -> None:
        """Configure mock app config service with execution config."""
        execution_config = {
            "success_policy": policy_config,
            "tracking": {"enabled": True}
        }
        self.mock_app_config_service.get_execution_config.return_value = execution_config
    
    # =============================================================================
    # 2. Policy Evaluation Tests
    # =============================================================================
    
    def test_evaluate_success_policy_all_nodes_success(self):
        """Test all_nodes policy with all nodes successful."""
        # Configure policy
        self.configure_execution_config({"type": "all_nodes"})
        
        # Create summary with all successful nodes
        summary = self.create_mock_execution_summary(
            "test_graph",
            [
                {"node_name": "node1", "success": True},
                {"node_name": "node2", "success": True},
                {"node_name": "node3", "success": True}
            ]
        )
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result
        self.assertTrue(result)
        
        # Verify configuration was accessed
        self.mock_app_config_service.get_execution_config.assert_called_once()
        
        # Verify debug logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == 'debug']
        self.assertTrue(any('Evaluating success policy' in call[1] for call in debug_calls))
        self.assertTrue(any('Policy evaluation complete' in call[1] and 'Result: True' in call[1] 
                          for call in debug_calls))
    
    def test_evaluate_success_policy_all_nodes_failure(self):
        """Test all_nodes policy with one node failed."""
        # Configure policy
        self.configure_execution_config({"type": "all_nodes"})
        
        # Create summary with one failed node
        summary = self.create_mock_execution_summary(
            "test_graph",
            [
                {"node_name": "node1", "success": True},
                {"node_name": "node2", "success": False, "error": "Processing failed"},
                {"node_name": "node3", "success": True}
            ]
        )
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result
        self.assertFalse(result)
        
        # Verify debug logging shows failure
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == 'debug']
        self.assertTrue(any('Result: False' in call[1] for call in debug_calls))
    
    def test_evaluate_success_policy_final_node_success(self):
        """Test final_node policy with last node successful."""
        # Configure policy
        self.configure_execution_config({"type": "final_node"})
        
        # Create summary with mixed results but final node successful
        summary = self.create_mock_execution_summary(
            "test_graph",
            [
                {"node_name": "node1", "success": False, "error": "Early failure"},
                {"node_name": "node2", "success": False, "error": "Middle failure"},
                {"node_name": "node3", "success": True}  # Final node succeeds
            ]
        )
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should be True because final node succeeded
        self.assertTrue(result)
        
        # Verify policy type logged
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == 'debug']
        self.assertTrue(any('Type: final_node' in call[1] for call in debug_calls))
    
    def test_evaluate_success_policy_final_node_failure(self):
        """Test final_node policy with last node failed."""
        # Configure policy
        self.configure_execution_config({"type": "final_node"})
        
        # Create summary with final node failed
        summary = self.create_mock_execution_summary(
            "test_graph",
            [
                {"node_name": "node1", "success": True},
                {"node_name": "node2", "success": True},
                {"node_name": "node3", "success": False, "error": "Final failure"}
            ]
        )
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result
        self.assertFalse(result)
    
    def test_evaluate_success_policy_final_node_empty_executions(self):
        """Test final_node policy with no node executions."""
        # Configure policy
        self.configure_execution_config({"type": "final_node"})
        
        # Create summary with no executions
        summary = self.create_mock_execution_summary("test_graph", [])
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should be False for empty executions
        self.assertFalse(result)
    
    def test_evaluate_success_policy_critical_nodes_success(self):
        """Test critical_nodes policy with all critical nodes successful."""
        # Configure policy with critical nodes
        self.configure_execution_config({
            "type": "critical_nodes",
            "critical_nodes": ["node1", "node3"]
        })
        
        # Create summary with critical nodes successful
        summary = self.create_mock_execution_summary(
            "test_graph",
            [
                {"node_name": "node1", "success": True},   # Critical
                {"node_name": "node2", "success": False},  # Non-critical failure OK
                {"node_name": "node3", "success": True},   # Critical
                {"node_name": "node4", "success": True}
            ]
        )
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should be True because critical nodes succeeded
        self.assertTrue(result)
    
    def test_evaluate_success_policy_critical_nodes_failure(self):
        """Test critical_nodes policy with critical node failed."""
        # Configure policy with critical nodes
        self.configure_execution_config({
            "type": "critical_nodes",
            "critical_nodes": ["node1", "node3"]
        })
        
        # Create summary with one critical node failed
        summary = self.create_mock_execution_summary(
            "test_graph",
            [
                {"node_name": "node1", "success": True},   # Critical - OK
                {"node_name": "node2", "success": True},   # Non-critical
                {"node_name": "node3", "success": False, "error": "Critical failure"},  # Critical - FAILED
                {"node_name": "node4", "success": True}
            ]
        )
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should be False because critical node failed
        self.assertFalse(result)
    
    def test_evaluate_success_policy_critical_nodes_empty_list(self):
        """Test critical_nodes policy with empty critical nodes list."""
        # Configure policy with empty critical nodes
        self.configure_execution_config({
            "type": "critical_nodes",
            "critical_nodes": []
        })
        
        # Create summary with mixed results
        summary = self.create_mock_execution_summary(
            "test_graph",
            [
                {"node_name": "node1", "success": False},
                {"node_name": "node2", "success": True}
            ]
        )
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should be True because no critical nodes to check
        self.assertTrue(result)
    
    def test_evaluate_success_policy_critical_nodes_missing_node(self):
        """Test critical_nodes policy with critical node not executed."""
        # Configure policy with critical node not in execution
        self.configure_execution_config({
            "type": "critical_nodes",
            "critical_nodes": ["node1", "missing_node"]
        })
        
        # Create summary without the critical node
        summary = self.create_mock_execution_summary(
            "test_graph",
            [
                {"node_name": "node1", "success": True},   # Critical - OK
                {"node_name": "node2", "success": True}    # missing_node not executed
            ]
        )
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should be False because critical node missing
        self.assertFalse(result)
    
    def test_evaluate_success_policy_custom_success(self):
        """Test custom policy with successful custom function."""
        # Configure policy with custom function
        self.configure_execution_config({
            "type": "custom",
            "custom_function": "test.module.custom_policy_success"
        })
        
        # Create summary
        summary = self.create_mock_execution_summary("test_graph")
        
        # Mock the custom function import and execution
        mock_module = Mock()
        mock_custom_function = Mock(return_value=True)
        mock_module.custom_policy_success = mock_custom_function
        
        with patch('importlib.import_module', return_value=mock_module):
            # Execute test
            result = self.service.evaluate_success_policy(summary)
        
        # Verify result
        self.assertTrue(result)
        
        # Verify custom function was called with summary
        mock_custom_function.assert_called_once_with(summary)
    
    def test_evaluate_success_policy_custom_failure(self):
        """Test custom policy with failed custom function."""
        # Configure policy with custom function
        self.configure_execution_config({
            "type": "custom",
            "custom_function": "test.module.custom_policy_failure"
        })
        
        # Create summary
        summary = self.create_mock_execution_summary("test_graph")
        
        # Mock the custom function import and execution
        mock_module = Mock()
        mock_custom_function = Mock(return_value=False)
        mock_module.custom_policy_failure = mock_custom_function
        
        with patch('importlib.import_module', return_value=mock_module):
            # Execute test
            result = self.service.evaluate_success_policy(summary)
        
        # Verify result
        self.assertFalse(result)
    
    def test_evaluate_success_policy_custom_missing_function(self):
        """Test custom policy with missing custom function configuration."""
        # Configure policy without custom_function
        self.configure_execution_config({
            "type": "custom",
            # Missing custom_function
        })
        
        # Create summary
        summary = self.create_mock_execution_summary("test_graph")
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should fall back to all_nodes policy
        self.assertTrue(result)  # All nodes in mock summary are successful
        
        # Verify warning was logged
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == 'warning']
        self.assertTrue(any('Custom policy selected but no function specified' in call[1] 
                          for call in warning_calls))
    
    def test_evaluate_success_policy_unknown_type_fallback(self):
        """Test policy evaluation with unknown policy type falls back to all_nodes."""
        # Configure policy with unknown type
        self.configure_execution_config({
            "type": "unknown_policy_type"
        })
        
        # Create summary with all successful nodes
        summary = self.create_mock_execution_summary("test_graph")
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should fall back to all_nodes policy
        self.assertTrue(result)
        
        # Verify warning was logged
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == 'warning']
        self.assertTrue(any('Unknown success policy type: unknown_policy_type' in call[1] 
                          for call in warning_calls))
    
    # =============================================================================
    # 3. Configuration Integration Tests
    # =============================================================================
    
    def test_evaluate_success_policy_default_configuration(self):
        """Test policy evaluation with default configuration."""
        # Don't configure explicit policy - should use defaults
        execution_config = {
            "tracking": {"enabled": True}
            # No success_policy section - should use defaults
        }
        self.mock_app_config_service.get_execution_config.return_value = execution_config
        
        # Create summary
        summary = self.create_mock_execution_summary("test_graph")
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should default to all_nodes policy
        self.assertTrue(result)
        
        # Verify debug logging shows default policy type
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == 'debug']
        self.assertTrue(any('Type: all_nodes' in call[1] for call in debug_calls))
    
    def test_evaluate_success_policy_configuration_access_error(self):
        """Test policy evaluation handles configuration access errors."""
        # Configure mock to raise exception
        self.mock_app_config_service.get_execution_config.side_effect = Exception("Config error")
        
        # Create summary
        summary = self.create_mock_execution_summary("test_graph")
        
        # Execute test
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should return False due to error
        self.assertFalse(result)
        
        # Verify error was logged
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == 'error']
        self.assertTrue(any('Error evaluating policy' in call[1] for call in error_calls))
    
    # =============================================================================
    # 4. Validation Tests
    # =============================================================================
    
    def test_validate_policy_config_all_nodes_valid(self):
        """Test validate_policy_config with valid all_nodes configuration."""
        policy_config = {"type": "all_nodes"}
        
        errors = self.service.validate_policy_config(policy_config)
        
        self.assertEqual(errors, [])
    
    def test_validate_policy_config_final_node_valid(self):
        """Test validate_policy_config with valid final_node configuration."""
        policy_config = {"type": "final_node"}
        
        errors = self.service.validate_policy_config(policy_config)
        
        self.assertEqual(errors, [])
    
    def test_validate_policy_config_critical_nodes_valid(self):
        """Test validate_policy_config with valid critical_nodes configuration."""
        policy_config = {
            "type": "critical_nodes",
            "critical_nodes": ["node1", "node2", "node3"]
        }
        
        errors = self.service.validate_policy_config(policy_config)
        
        self.assertEqual(errors, [])
    
    def test_validate_policy_config_custom_valid(self):
        """Test validate_policy_config with valid custom configuration."""
        policy_config = {
            "type": "custom",
            "custom_function": "my.module.policy_function"
        }
        
        errors = self.service.validate_policy_config(policy_config)
        
        self.assertEqual(errors, [])
    
    def test_validate_policy_config_invalid_type(self):
        """Test validate_policy_config with invalid policy type."""
        policy_config = {"type": "invalid_policy"}
        
        errors = self.service.validate_policy_config(policy_config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid policy type: invalid_policy", errors[0])
    
    def test_validate_policy_config_critical_nodes_not_list(self):
        """Test validate_policy_config with critical_nodes not a list."""
        policy_config = {
            "type": "critical_nodes",
            "critical_nodes": "not_a_list"
        }
        
        errors = self.service.validate_policy_config(policy_config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("critical_nodes must be a list", errors[0])
    
    def test_validate_policy_config_critical_nodes_empty(self):
        """Test validate_policy_config with empty critical_nodes list."""
        policy_config = {
            "type": "critical_nodes",
            "critical_nodes": []
        }
        
        errors = self.service.validate_policy_config(policy_config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("critical_nodes policy requires at least one critical node", errors[0])
    
    def test_validate_policy_config_custom_missing_function(self):
        """Test validate_policy_config with custom policy missing function."""
        policy_config = {
            "type": "custom"
            # Missing custom_function
        }
        
        errors = self.service.validate_policy_config(policy_config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("custom policy requires custom_function to be specified", errors[0])
    
    def test_validate_policy_config_custom_function_not_string(self):
        """Test validate_policy_config with custom_function not a string."""
        policy_config = {
            "type": "custom",
            "custom_function": 123  # Not a string
        }
        
        errors = self.service.validate_policy_config(policy_config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("custom_function must be a string", errors[0])
    
    def test_validate_policy_config_custom_function_invalid_format(self):
        """Test validate_policy_config with custom_function in wrong format."""
        policy_config = {
            "type": "custom",
            "custom_function": "invalid_format"  # Missing module path
        }
        
        errors = self.service.validate_policy_config(policy_config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("custom_function must be in format 'module.path.function_name'", errors[0])
    
    def test_validate_policy_config_multiple_errors(self):
        """Test validate_policy_config returns multiple errors."""
        policy_config = {
            "type": "critical_nodes",
            "critical_nodes": "not_a_list"  # Error 1: not a list
        }
        
        errors = self.service.validate_policy_config(policy_config)
        
        # Should have error about not being a list
        self.assertTrue(len(errors) >= 1)
        self.assertTrue(any("critical_nodes must be a list" in error for error in errors))
    
    # =============================================================================
    # 5. Utility Methods Tests
    # =============================================================================
    
    def test_get_available_policies(self):
        """Test get_available_policies returns all supported policy types."""
        policies = self.service.get_available_policies()
        
        expected_policies = ["all_nodes", "final_node", "critical_nodes", "custom"]
        self.assertEqual(policies, expected_policies)
    
    def test_get_policy_description_all_policies(self):
        """Test get_policy_description for all supported policy types."""
        # Test all known policy types
        descriptions = {
            "all_nodes": self.service.get_policy_description("all_nodes"),
            "final_node": self.service.get_policy_description("final_node"),
            "critical_nodes": self.service.get_policy_description("critical_nodes"),
            "custom": self.service.get_policy_description("custom")
        }
        
        # Verify all descriptions are meaningful
        for policy_type, description in descriptions.items():
            self.assertIsInstance(description, str)
            self.assertTrue(len(description) > 10)  # Should be meaningful description
            self.assertIn(policy_type.replace("_", " "), description.lower())  # Should mention policy type
    
    def test_get_policy_description_unknown_policy(self):
        """Test get_policy_description with unknown policy type."""
        description = self.service.get_policy_description("unknown_policy")
        
        self.assertIn("Unknown policy type: unknown_policy", description)
    
    def test_get_service_info(self):
        """Test get_service_info returns comprehensive service information."""
        info = self.service.get_service_info()
        
        # Verify structure
        self.assertIsInstance(info, dict)
        self.assertEqual(info["service"], "ExecutionPolicyService")
        self.assertTrue(info["config_available"])
        
        # Verify available policies
        self.assertEqual(info["available_policies"], ["all_nodes", "final_node", "critical_nodes", "custom"])
        
        # Verify current policy information
        self.assertIn("current_policy", info)
        self.assertIsInstance(info["current_policy"], dict)
        
        # Verify capabilities
        capabilities = info["capabilities"]
        self.assertTrue(capabilities["policy_evaluation"])
        self.assertTrue(capabilities["policy_validation"])
        self.assertTrue(capabilities["configuration_integration"])
        self.assertTrue(capabilities["error_handling"])
        
        # Verify wrapped functions
        expected_functions = [
            "evaluate_success_policy",
            "_evaluate_all_nodes_policy",
            "_evaluate_final_node_policy",
            "_evaluate_critical_nodes_policy",
            "_evaluate_custom_policy"
        ]
        self.assertEqual(info["wrapped_functions"], expected_functions)
    
    def test_get_service_info_config_error(self):
        """Test get_service_info handles configuration errors gracefully."""
        # Configure mock to raise exception for config access
        self.mock_app_config_service.get_execution_config.side_effect = Exception("Config error")
        
        info = self.service.get_service_info()
        
        # Should still return info but with error in current_policy
        self.assertIsInstance(info, dict)
        self.assertEqual(info["service"], "ExecutionPolicyService")
        self.assertIn("error", info["current_policy"])
        self.assertIn("Unable to load policy configuration", info["current_policy"]["error"])
    
    # =============================================================================
    # 6. Error Handling Tests
    # =============================================================================
    
    def test_evaluate_custom_policy_import_error(self):
        """Test custom policy evaluation handles import errors."""
        # Configure policy with custom function
        self.configure_execution_config({
            "type": "custom",
            "custom_function": "nonexistent.module.function"
        })
        
        # Create summary
        summary = self.create_mock_execution_summary("test_graph")
        
        # Mock import to raise ImportError
        with patch('importlib.import_module', side_effect=ImportError("Module not found")):
            # Execute test
            result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should return False due to import error
        self.assertFalse(result)
        
        # Verify error was logged
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == 'error']
        self.assertTrue(any('Error loading custom policy function' in call[1] 
                          for call in error_calls))
    
    def test_evaluate_custom_policy_attribute_error(self):
        """Test custom policy evaluation handles attribute errors."""
        # Configure policy with custom function
        self.configure_execution_config({
            "type": "custom",
            "custom_function": "test.module.nonexistent_function"
        })
        
        # Create summary
        summary = self.create_mock_execution_summary("test_graph")
        
        # Mock module without the function - this will cause getattr to raise AttributeError
        mock_module = Mock(spec=[])  # Empty spec means no attributes
        
        with patch('importlib.import_module', return_value=mock_module):
            # Execute test - getattr will naturally raise AttributeError
            result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should return False due to attribute error
        self.assertFalse(result)
        
        # Verify error was logged
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == 'error']
        self.assertTrue(any('Error loading custom policy function' in call[1] 
                          for call in error_calls))
    
    def test_evaluate_custom_policy_execution_error(self):
        """Test custom policy evaluation handles function execution errors."""
        # Configure policy with custom function
        self.configure_execution_config({
            "type": "custom",
            "custom_function": "test.module.failing_function"
        })
        
        # Create summary
        summary = self.create_mock_execution_summary("test_graph")
        
        # Mock the custom function to raise exception
        mock_module = Mock()
        mock_failing_function = Mock(side_effect=RuntimeError("Function execution failed"))
        mock_module.failing_function = mock_failing_function
        
        with patch('importlib.import_module', return_value=mock_module):
            # Execute test
            result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should return False due to execution error
        self.assertFalse(result)
        
        # Verify error was logged
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == 'error']
        self.assertTrue(any('Error executing custom policy function' in call[1] 
                          for call in error_calls))
    
    def test_evaluate_custom_policy_value_error(self):
        """Test custom policy evaluation handles value errors in function path."""
        # Configure policy with malformed function path
        self.configure_execution_config({
            "type": "custom",
            "custom_function": "invalid_format"  # Missing module.function format
        })
        
        # Create summary
        summary = self.create_mock_execution_summary("test_graph")
        
        # Execute test - rsplit(".", 1) on "invalid_format" will raise ValueError
        # because there's no "." to split on, so it can't unpack into 2 values
        result = self.service.evaluate_success_policy(summary)
        
        # Verify result - should return False due to value error
        self.assertFalse(result)
        
        # Verify error was logged
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == 'error']
        self.assertTrue(any('Error loading custom policy function' in call[1] 
                          for call in error_calls))
    
    def test_evaluate_success_policy_exception_during_evaluation(self):
        """Test evaluate_success_policy handles unexpected exceptions."""
        # Configure policy
        self.configure_execution_config({"type": "all_nodes"})
        
        # Create malformed summary that will cause exception
        malformed_summary = Mock()
        malformed_summary.node_executions = None  # This should cause TypeError
        
        # Execute test
        result = self.service.evaluate_success_policy(malformed_summary)
        
        # Verify result - should return False due to exception
        self.assertFalse(result)
        
        # Verify error was logged
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == 'error']
        self.assertTrue(any('Error evaluating policy' in call[1] for call in error_calls))
    
    def test_service_initialization_with_missing_dependencies(self):
        """Test service handles missing dependencies gracefully."""
        # Test missing logging service - should fail during initialization
        with self.assertRaises(AttributeError):
            ExecutionPolicyService(
                app_config_service=self.mock_app_config_service,
                logging_service=None
            )
        
        # Test missing config service - initialization succeeds but methods handle errors gracefully
        service_with_none_config = ExecutionPolicyService(
            app_config_service=None,
            logging_service=self.mock_logging_service
        )
        
        # Verify service was created but config is None
        self.assertIsNone(service_with_none_config.config)
        self.assertIsNotNone(service_with_none_config.logger)
        
        # Test that evaluate_success_policy handles None config gracefully
        summary = self.create_mock_execution_summary("test_graph")
        result = service_with_none_config.evaluate_success_policy(summary)
        
        # Should return False due to error, not raise exception
        self.assertFalse(result)
        
        # Verify error was logged
        logger = service_with_none_config.logger
        logger_calls = logger.calls
        error_calls = [call for call in logger_calls if call[0] == 'error']
        self.assertTrue(any('Error evaluating policy' in call[1] for call in error_calls))


if __name__ == '__main__':
    unittest.main()
