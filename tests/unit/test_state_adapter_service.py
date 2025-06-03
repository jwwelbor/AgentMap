"""
Unit tests for StateAdapterService.

These tests mock all dependencies and focus on testing the service logic
in isolation, following the existing test patterns in AgentMap.
"""

import unittest
from unittest.mock import Mock, patch

from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.migration_utils import (
    MockLoggingService,
    MockAppConfigService
)


class TestStateAdapterService(unittest.TestCase):
    """Unit tests for StateAdapterService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use migration-safe mock implementations
        self.mock_logging_service = MockLoggingService()
        self.mock_config_service = MockAppConfigService()
        
        # Create service instance with mocked dependencies
        self.service = StateAdapterService(
            app_config_service=self.mock_config_service,
            logging_service=self.mock_logging_service
        )
    
    def test_service_initialization(self):
        """Test that service initializes correctly with dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.logger.name, "StateAdapterService")
        self.assertEqual(self.service.config, self.mock_config_service)
        
        # Verify initialization log message
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "[StateAdapterService] Initialized" 
                          for call in logger_calls if call[0] == "info"))
    
    @patch('agentmap.services.state_adapter_service.StateAdapter')
    def test_set_value_dict_state_success(self, mock_state_adapter):
        """Test successful state value setting with dict state."""
        # Setup mock StateAdapter
        initial_state = {"key1": "value1", "key2": "value2"}
        updated_state = {"key1": "value1", "key2": "value2", "new_key": "new_value"}
        mock_state_adapter.set_value.return_value = updated_state
        
        # Test setting value
        result = self.service.set_value(initial_state, "new_key", "new_value")
        
        # Verify result
        self.assertEqual(result, updated_state)
        
        # Verify StateAdapter was called correctly
        mock_state_adapter.set_value.assert_called_once_with(
            initial_state, "new_key", "new_value"
        )
        
        # Verify debug logging
        logger_calls = self.service.logger.calls
        self.assertTrue(any(call[1] == "[StateAdapterService] Setting state value: new_key" 
                          for call in logger_calls if call[0] == "debug"))
        self.assertTrue(any("Successfully set state value: new_key" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    @patch('agentmap.services.state_adapter_service.StateAdapter')
    def test_set_value_object_state_success(self, mock_state_adapter):
        """Test successful state value setting with object state."""
        # Create mock object state
        class MockState:
            def __init__(self):
                self.value = "original"
        
        initial_state = MockState()
        updated_state = MockState()
        updated_state.value = "updated"
        
        mock_state_adapter.set_value.return_value = updated_state
        
        # Test setting value
        result = self.service.set_value(initial_state, "value", "updated")
        
        # Verify result
        self.assertEqual(result, updated_state)
        self.assertEqual(result.value, "updated")
        
        # Verify StateAdapter was called correctly
        mock_state_adapter.set_value.assert_called_once_with(
            initial_state, "value", "updated"
        )
    
    @patch('agentmap.services.state_adapter_service.StateAdapter')
    def test_set_value_pydantic_model_success(self, mock_state_adapter):
        """Test successful state value setting with Pydantic model."""
        # Mock Pydantic-like state
        initial_state = {"id": 1, "name": "test"}
        updated_state = {"id": 1, "name": "updated_test"}
        
        mock_state_adapter.set_value.return_value = updated_state
        
        # Test setting value
        result = self.service.set_value(initial_state, "name", "updated_test")
        
        # Verify result
        self.assertEqual(result, updated_state)
        
        # Verify state type was logged
        logger_calls = self.service.logger.calls
        self.assertTrue(any("state type: dict" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    @patch('agentmap.services.state_adapter_service.StateAdapter')
    def test_set_value_execution_tracker_key_error(self, mock_state_adapter):
        """Test error when trying to set __execution_tracker key."""
        mock_state_adapter.set_value.side_effect = Exception("__execution_tracker not allowed in state")
        
        initial_state = {"key": "value"}
        
        # Test setting forbidden key
        with self.assertRaises(Exception) as context:
            self.service.set_value(initial_state, "__execution_tracker", "tracker")
        
        self.assertIn("__execution_tracker not allowed in state", str(context.exception))
        
        # Verify error was logged
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Error setting state value '__execution_tracker'" in call[1] 
                          for call in logger_calls if call[0] == "error"))
    
    @patch('agentmap.services.state_adapter_service.StateAdapter')
    def test_set_value_state_adapter_error(self, mock_state_adapter):
        """Test error handling when StateAdapter fails."""
        mock_state_adapter.set_value.side_effect = Exception("State update failed")
        
        initial_state = {"key": "value"}
        
        # Test with StateAdapter failure
        with self.assertRaises(Exception) as context:
            self.service.set_value(initial_state, "new_key", "new_value")
        
        self.assertIn("State update failed", str(context.exception))
        
        # Verify error was logged
        logger_calls = self.service.logger.calls
        self.assertTrue(any("Error setting state value 'new_key'" in call[1] 
                          for call in logger_calls if call[0] == "error"))
    
    @patch('agentmap.services.state_adapter_service.StateAdapter')
    def test_set_value_complex_types(self, mock_state_adapter):
        """Test setting value with complex data types."""
        initial_state = {"data": [1, 2, 3]}
        complex_value = {"nested": {"deep": {"value": "test"}}, "list": [1, 2, 3]}
        updated_state = {"data": [1, 2, 3], "complex": complex_value}
        
        mock_state_adapter.set_value.return_value = updated_state
        
        # Test setting complex value
        result = self.service.set_value(initial_state, "complex", complex_value)
        
        # Verify result
        self.assertEqual(result, updated_state)
        mock_state_adapter.set_value.assert_called_once_with(
            initial_state, "complex", complex_value
        )
    
    @patch('agentmap.services.state_adapter_service.StateAdapter')
    def test_set_value_none_value(self, mock_state_adapter):
        """Test setting None value."""
        initial_state = {"key": "value"}
        updated_state = {"key": None}
        
        mock_state_adapter.set_value.return_value = updated_state
        
        # Test setting None value
        result = self.service.set_value(initial_state, "key", None)
        
        # Verify result
        self.assertEqual(result, updated_state)
        mock_state_adapter.set_value.assert_called_once_with(
            initial_state, "key", None
        )
    
    @patch('agentmap.services.state_adapter_service.StateAdapter')
    def test_set_value_empty_string_key(self, mock_state_adapter):
        """Test setting value with empty string key."""
        initial_state = {"key": "value"}
        updated_state = {"key": "value", "": "empty_key_value"}
        
        mock_state_adapter.set_value.return_value = updated_state
        
        # Test setting value with empty key
        result = self.service.set_value(initial_state, "", "empty_key_value")
        
        # Verify result
        self.assertEqual(result, updated_state)
        mock_state_adapter.set_value.assert_called_once_with(
            initial_state, "", "empty_key_value"
        )
    
    def test_get_service_info(self):
        """Test getting service information."""
        info = self.service.get_service_info()
        
        # Verify service information
        self.assertEqual(info["service"], "StateAdapterService")
        self.assertTrue(info["config_available"])
        
        # Verify capabilities
        capabilities = info["capabilities"]
        self.assertTrue(capabilities["state_manipulation"])
        self.assertTrue(capabilities["immutable_updates"])
        self.assertTrue(capabilities["multiple_state_types"])
        self.assertTrue(capabilities["error_handling"])
        
        # Verify wrapped methods
        wrapped_methods = info["wrapped_methods"]
        self.assertEqual(wrapped_methods, ["set_value"])
        
        # Verify available state types
        state_types = info["available_state_types"]
        expected_types = ["dict", "pydantic_models", "objects_with_copy_method", "objects_with_attributes"]
        self.assertEqual(state_types, expected_types)
        
        # Verify YAGNI compliance
        yagni_compliance = info["yagni_compliance"]
        self.assertEqual(yagni_compliance["methods_wrapped"], 1)
        self.assertEqual(yagni_compliance["methods_available"], 4)
        self.assertIn("Only set_value method is currently used", yagni_compliance["reason"])
    
    def test_service_yagni_compliance(self):
        """Test that service follows YAGNI principle correctly."""
        # Verify only set_value method is implemented
        self.assertTrue(hasattr(self.service, 'set_value'))
        
        # Verify other StateAdapter methods are not implemented yet
        self.assertFalse(hasattr(self.service, 'get_value'))
        self.assertFalse(hasattr(self.service, 'has_value'))
        self.assertFalse(hasattr(self.service, 'get_inputs'))
        
        # This validates YAGNI compliance - only implement what's needed
    
    @patch('agentmap.services.state_adapter_service.StateAdapter')
    def test_set_value_type_preservation(self, mock_state_adapter):
        """Test that state type information is preserved through adapter."""
        # Test different state types to ensure type information is logged
        
        # Dict state
        dict_state = {"key": "value"}
        mock_state_adapter.set_value.return_value = {"key": "value", "new": "data"}
        
        self.service.set_value(dict_state, "new", "data")
        
        logger_calls = self.service.logger.calls
        self.assertTrue(any("state type: dict" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
        
        # Reset logger for next test
        self.service.logger.calls = []
        
        # Object state
        class TestState:
            pass
        
        obj_state = TestState()
        mock_state_adapter.set_value.return_value = obj_state
        
        self.service.set_value(obj_state, "attr", "value")
        
        logger_calls = self.service.logger.calls
        self.assertTrue(any("state type: TestState" in call[1] 
                          for call in logger_calls if call[0] == "debug"))


if __name__ == '__main__':
    unittest.main()
