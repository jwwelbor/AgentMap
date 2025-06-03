"""
Unit tests for ExecutionPolicyService.

These tests mock all dependencies and focus on testing the service logic
in isolation, following the existing test patterns in AgentMap.
"""

import unittest
from unittest.mock import Mock, patch

from agentmap.services.execution_policy_service import ExecutionPolicyService
from agentmap.migration_utils import (
    MockLoggingService,
    MockAppConfigService
)


class TestExecutionPolicyService(unittest.TestCase):
    """Unit tests for ExecutionPolicyService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use migration-safe mock implementations
        self.mock_logging_service = MockLoggingService()
        self.mock_config_service = MockAppConfigService()
        
        # Create service instance with mocked dependencies
        self.service = ExecutionPolicyService(
            app_config_service=self.mock_config_service,
            logging_service=self.mock_logging_service
        )
    
    def test_service_initialization(self):
        """Test that service initializes correctly with dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.logger.name, "ExecutionPolicyService")
        self.assertEqual(self.service.config, self.mock_config_service)
        
        # Verify initialization log message
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "[ExecutionPolicyService] Initialized" 
                          for call in logger_calls if call[0] == "info"))
    
    @patch('agentmap.services.execution_policy_service.evaluate_success_policy')
    def test_evaluate_success_policy_all_nodes_success(self, mock_evaluate):
        """Test successful policy evaluation with all_nodes policy."""
        # Setup mock execution config
        execution_config = {
            "success_policy": {
                "type": "all_nodes"
            }
        }
        
        # Mock config service to return execution config
        with patch.object(self.mock_config_service, 'get_execution_config', return_value=execution_config):
            # Mock policy evaluation to return success
            mock_evaluate.return_value = True
            
            # Create test summary
            test_summary = {
                "overall_success": True,
                "execution_path": [
                    {"node_name": "Node1", "success": True},
                    {"node_name": "Node2", "success": True}
                ]
            }
            
            # Test policy evaluation
            result = self.service.evaluate_success_policy(test_summary)
            
            # Verify result
            self.assertTrue(result)
            
            # Verify policy function was called with correct parameters
            mock_evaluate.assert_called_once_with(
                test_summary, 
                execution_config, 
                self.service.logger
            )
            
            # Verify debug logging
            logger_calls = self.service.logger.calls
            self.assertTrue(any(call[1] == "[ExecutionPolicyService] Evaluating success policy" 
                              for call in logger_calls if call[0] == "debug"))
    
    @patch('agentmap.services.execution_policy_service.evaluate_success_policy')
    def test_evaluate_success_policy_final_node_success(self, mock_evaluate):
        """Test successful policy evaluation with final_node policy."""
        execution_config = {
            "success_policy": {
                "type": "final_node"
            }
        }
        
        with patch.object(self.mock_config_service, 'get_execution_config', return_value=execution_config):
            mock_evaluate.return_value = True
            
            test_summary = {
                "overall_success": False,  # Overall failed but final node succeeded
                "execution_path": [
                    {"node_name": "Node1", "success": False},
                    {"node_name": "FinalNode", "success": True}
                ]
            }
            
            result = self.service.evaluate_success_policy(test_summary)
            
            self.assertTrue(result)
            mock_evaluate.assert_called_once()
    
    @patch('agentmap.services.execution_policy_service.evaluate_success_policy')
    def test_evaluate_success_policy_critical_nodes_success(self, mock_evaluate):
        """Test successful policy evaluation with critical_nodes policy."""
        execution_config = {
            "success_policy": {
                "type": "critical_nodes",
                "critical_nodes": ["ImportantNode1", "ImportantNode2"]
            }
        }
        
        with patch.object(self.mock_config_service, 'get_execution_config', return_value=execution_config):
            mock_evaluate.return_value = True
            
            test_summary = {
                "overall_success": False,
                "execution_path": [
                    {"node_name": "ImportantNode1", "success": True},
                    {"node_name": "NonCriticalNode", "success": False},
                    {"node_name": "ImportantNode2", "success": True}
                ]
            }
            
            result = self.service.evaluate_success_policy(test_summary)
            
            self.assertTrue(result)
    
    @patch('agentmap.services.execution_policy_service.evaluate_success_policy')
    def test_evaluate_success_policy_custom_policy(self, mock_evaluate):
        """Test policy evaluation with custom policy."""
        execution_config = {
            "success_policy": {
                "type": "custom",
                "custom_function": "mymodule.custom_evaluator"
            }
        }
        
        with patch.object(self.mock_config_service, 'get_execution_config', return_value=execution_config):
            mock_evaluate.return_value = True
            
            test_summary = {"custom": "summary"}
            result = self.service.evaluate_success_policy(test_summary)
            
            self.assertTrue(result)
    
    @patch('agentmap.services.execution_policy_service.evaluate_success_policy')
    def test_evaluate_success_policy_failure(self, mock_evaluate):
        """Test policy evaluation returning failure."""
        execution_config = {
            "success_policy": {
                "type": "all_nodes"
            }
        }
        
        with patch.object(self.mock_config_service, 'get_execution_config', return_value=execution_config):
            mock_evaluate.return_value = False
            
            test_summary = {
                "overall_success": False,
                "execution_path": [
                    {"node_name": "Node1", "success": True},
                    {"node_name": "Node2", "success": False}
                ]
            }
            
            result = self.service.evaluate_success_policy(test_summary)
            
            self.assertFalse(result)
    
    @patch('agentmap.services.execution_policy_service.evaluate_success_policy')
    def test_evaluate_success_policy_error_handling(self, mock_evaluate):
        """Test error handling in policy evaluation."""
        # Mock config service to raise exception
        with patch.object(self.mock_config_service, 'get_execution_config', side_effect=Exception("Config error")):
            
            test_summary = {"test": "data"}
            result = self.service.evaluate_success_policy(test_summary)
            
            # Should return conservative failure result
            self.assertFalse(result)
            
            # Verify error was logged
            logger_calls = self.service.logger.calls
            self.assertTrue(any("Error evaluating policy" in call[1] 
                              for call in logger_calls if call[0] == "error"))
    
    @patch('agentmap.services.execution_policy_service.evaluate_success_policy')
    def test_evaluate_success_policy_evaluation_error(self, mock_evaluate):
        """Test error handling when policy evaluation function fails."""
        execution_config = {"success_policy": {"type": "all_nodes"}}
        
        with patch.object(self.mock_config_service, 'get_execution_config', return_value=execution_config):
            # Mock evaluation function to raise exception
            mock_evaluate.side_effect = Exception("Policy evaluation error")
            
            result = self.service.evaluate_success_policy({"test": "summary"})
            
            # Should return conservative failure result
            self.assertFalse(result)
            
            # Verify error was logged
            logger_calls = self.service.logger.calls
            self.assertTrue(any("Error evaluating policy" in call[1] 
                              for call in logger_calls if call[0] == "error"))
    
    def test_get_available_policies(self):
        """Test getting list of available policies."""
        policies = self.service.get_available_policies()
        
        expected_policies = ["all_nodes", "final_node", "critical_nodes", "custom"]
        self.assertEqual(policies, expected_policies)
    
    def test_validate_policy_config_valid_all_nodes(self):
        """Test validation of valid all_nodes policy config."""
        config = {"type": "all_nodes"}
        errors = self.service.validate_policy_config(config)
        
        self.assertEqual(len(errors), 0)
    
    def test_validate_policy_config_valid_final_node(self):
        """Test validation of valid final_node policy config."""
        config = {"type": "final_node"}
        errors = self.service.validate_policy_config(config)
        
        self.assertEqual(len(errors), 0)
    
    def test_validate_policy_config_valid_critical_nodes(self):
        """Test validation of valid critical_nodes policy config."""
        config = {
            "type": "critical_nodes",
            "critical_nodes": ["Node1", "Node2"]
        }
        errors = self.service.validate_policy_config(config)
        
        self.assertEqual(len(errors), 0)
    
    def test_validate_policy_config_valid_custom(self):
        """Test validation of valid custom policy config."""
        config = {
            "type": "custom",
            "custom_function": "mymodule.path.my_function"
        }
        errors = self.service.validate_policy_config(config)
        
        self.assertEqual(len(errors), 0)
    
    def test_validate_policy_config_invalid_type(self):
        """Test validation with invalid policy type."""
        config = {"type": "invalid_policy_type"}
        errors = self.service.validate_policy_config(config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid policy type: invalid_policy_type", errors[0])
    
    def test_validate_policy_config_critical_nodes_empty_list(self):
        """Test validation of critical_nodes policy with empty list."""
        config = {
            "type": "critical_nodes",
            "critical_nodes": []
        }
        errors = self.service.validate_policy_config(config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("requires at least one critical node", errors[0])
    
    def test_validate_policy_config_critical_nodes_not_list(self):
        """Test validation of critical_nodes policy with non-list value."""
        config = {
            "type": "critical_nodes",
            "critical_nodes": "not_a_list"
        }
        errors = self.service.validate_policy_config(config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("critical_nodes must be a list", errors[0])
    
    def test_validate_policy_config_custom_no_function(self):
        """Test validation of custom policy without function."""
        config = {"type": "custom"}
        errors = self.service.validate_policy_config(config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("custom policy requires custom_function", errors[0])
    
    def test_validate_policy_config_custom_invalid_function_format(self):
        """Test validation of custom policy with invalid function format."""
        config = {
            "type": "custom",
            "custom_function": "invalid_format"
        }
        errors = self.service.validate_policy_config(config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("must be in format 'module.path.function_name'", errors[0])
    
    def test_validate_policy_config_custom_non_string_function(self):
        """Test validation of custom policy with non-string function."""
        config = {
            "type": "custom",
            "custom_function": 123
        }
        errors = self.service.validate_policy_config(config)
        
        self.assertEqual(len(errors), 1)
        self.assertIn("custom_function must be a string", errors[0])
    
    def test_get_policy_description(self):
        """Test getting policy descriptions."""
        # Test all valid policy types
        all_nodes_desc = self.service.get_policy_description("all_nodes")
        self.assertIn("All nodes must succeed", all_nodes_desc)
        
        final_node_desc = self.service.get_policy_description("final_node")
        self.assertIn("Only the final node must succeed", final_node_desc)
        
        critical_nodes_desc = self.service.get_policy_description("critical_nodes")
        self.assertIn("All specified critical nodes must succeed", critical_nodes_desc)
        
        custom_desc = self.service.get_policy_description("custom")
        self.assertIn("Uses a custom function", custom_desc)
        
        # Test unknown policy type
        unknown_desc = self.service.get_policy_description("unknown")
        self.assertIn("Unknown policy type: unknown", unknown_desc)
    
    def test_get_service_info_success(self):
        """Test getting service information successfully."""
        execution_config = {
            "success_policy": {
                "type": "all_nodes"
            }
        }
        
        with patch.object(self.mock_config_service, 'get_execution_config', return_value=execution_config):
            info = self.service.get_service_info()
            
            # Verify service information
            self.assertEqual(info["service"], "ExecutionPolicyService")
            self.assertTrue(info["config_available"])
            self.assertEqual(info["available_policies"], ["all_nodes", "final_node", "critical_nodes", "custom"])
            self.assertEqual(info["current_policy"], execution_config["success_policy"])
            
            # Verify capabilities
            capabilities = info["capabilities"]
            self.assertTrue(capabilities["policy_evaluation"])
            self.assertTrue(capabilities["policy_validation"])
            self.assertTrue(capabilities["configuration_integration"])
            self.assertTrue(capabilities["error_handling"])
            
            # Verify wrapped functions
            wrapped_functions = info["wrapped_functions"]
            self.assertIn("evaluate_success_policy", wrapped_functions)
    
    def test_get_service_info_config_error(self):
        """Test getting service information when config fails."""
        with patch.object(self.mock_config_service, 'get_execution_config', side_effect=Exception("Config error")):
            info = self.service.get_service_info()
            
            # Should still return service info with error indication
            self.assertEqual(info["service"], "ExecutionPolicyService")
            self.assertTrue(info["config_available"])
            self.assertIn("error", info["current_policy"])


if __name__ == '__main__':
    unittest.main()
