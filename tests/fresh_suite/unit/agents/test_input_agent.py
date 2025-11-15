"""
Unit tests for InputAgent using pure Mock objects and established testing patterns.

This test suite validates the new protocol-based dependency injection pattern
for agents that require no business services (LLM, storage) but handle user input.
"""
import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any

from agentmap.agents.builtins.input_agent import InputAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestInputAgent(unittest.TestCase):
    """Unit tests for InputAgent using pure Mock objects."""
    
    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Create basic context for testing (explicitly specify output_field)
        self.test_context = {
            "input_fields": ["user_data"],
            "output_field": "user_input",
            "description": "Test input agent"
        }
        
        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()
        
        # Create agent instance with mocked infrastructure dependencies
        self.agent = InputAgent(
            name="test_input",
            prompt="Please enter your data: ",
            context=self.test_context,
            logger=self.mock_logging_service.get_class_logger(InputAgent),
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.agent.logger
    
    # =============================================================================
    # 1. Agent Initialization Tests
    # =============================================================================
    
    def test_agent_initialization_with_infrastructure_services(self):
        """Test that agent initializes correctly with infrastructure services."""
        # Verify all infrastructure dependencies are stored
        self.assertEqual(self.agent.name, "test_input")
        self.assertEqual(self.agent.prompt, "Please enter your data: ")
        self.assertEqual(self.agent.context, self.test_context)
        self.assertEqual(self.agent.input_fields, ["user_data"])
        self.assertEqual(self.agent.output_field, "user_input")
        
        # Verify infrastructure services are available
        self.assertIsNotNone(self.agent.logger)
        self.assertIsNotNone(self.agent.execution_tracking_service)
        self.assertIsNotNone(self.agent.state_adapter_service)
        
        # Verify no business services are configured (InputAgent doesn't need them)
        self.assertFalse(hasattr(self.agent, '_llm_service') and self.agent._llm_service is not None)
        self.assertFalse(hasattr(self.agent, '_storage_service') and self.agent._storage_service is not None)
    
    def test_agent_initialization_with_minimal_dependencies(self):
        """Test agent initialization with minimal required dependencies."""
        # Create agent with only required parameters
        minimal_agent = InputAgent(
            name="minimal_input",
            prompt="Enter something: "
        )
        
        # Verify basic configuration
        self.assertEqual(minimal_agent.name, "minimal_input")
        self.assertEqual(minimal_agent.prompt, "Enter something: ")
        
        # Verify default context handling (output_field should default to None)
        self.assertEqual(minimal_agent.input_fields, [])
        self.assertIsNone(minimal_agent.output_field)
    
    def test_agent_protocol_compliance(self):
        """Test that InputAgent correctly implements (or doesn't implement) service protocols."""
        # InputAgent should NOT implement business service protocols
        self.assertFalse(isinstance(self.agent, LLMCapableAgent))
        self.assertFalse(isinstance(self.agent, StorageCapableAgent))
        
        # Verify service access raises appropriate errors for unconfigured services
        with self.assertRaises(ValueError) as cm:
            _ = self.agent.llm_service
        self.assertIn("LLM service not configured", str(cm.exception))
        
        with self.assertRaises(ValueError) as cm:
            _ = self.agent.storage_service
        self.assertIn("Storage service not configured", str(cm.exception))
    
    # =============================================================================
    # 2. Core Business Logic Tests (Input Prompting)
    # =============================================================================
    
    @patch('builtins.input', return_value='user_typed_input')
    def test_process_with_custom_prompt(self, mock_input):
        """Test processing with custom prompt and mocked user input."""
        inputs = {"user_data": "some_data"}
        
        result = self.agent.process(inputs)
        
        # Should return the mocked user input
        self.assertEqual(result, 'user_typed_input')
        
        # Verify input() was called with the correct prompt
        mock_input.assert_called_once_with("Please enter your data: ")
        
        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(len(info_calls) > 0)
        self.assertTrue(any("prompting for user input" in call[1] for call in info_calls))
    
    @patch('builtins.input', return_value='default_input')
    def test_process_with_default_prompt(self, mock_input):
        """Test processing when no custom prompt is provided."""
        # Create agent with None prompt
        agent_no_prompt = InputAgent(
            name="no_prompt",
            prompt=None,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        inputs = {}
        result = agent_no_prompt.process(inputs)
        
        # Should return the mocked user input
        self.assertEqual(result, 'default_input')
        
        # Verify input() was called with default prompt
        mock_input.assert_called_once_with("Please provide input: ")
    
    @patch('builtins.input', return_value='empty_string_prompt')
    def test_process_with_empty_prompt(self, mock_input):
        """Test processing when prompt is empty string."""
        # Create agent with empty prompt
        agent_empty_prompt = InputAgent(
            name="empty_prompt",
            prompt="",
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        inputs = {}
        result = agent_empty_prompt.process(inputs)
        
        # Should return the mocked user input
        self.assertEqual(result, 'empty_string_prompt')
        
        # Verify input() was called with default prompt (empty string is falsy)
        mock_input.assert_called_once_with("Please provide input: ")
    
    def test_process_with_different_input_scenarios(self):
        """Test process method with various input scenarios using subTest."""
        test_cases = [
            {
                'name': 'simple_text',
                'user_input': 'Hello World',
                'expected': 'Hello World'
            },
            {
                'name': 'empty_input',
                'user_input': '',
                'expected': ''
            },
            {
                'name': 'numeric_input',
                'user_input': '42',
                'expected': '42'
            },
            {
                'name': 'multiline_input',
                'user_input': 'Line 1\nLine 2',
                'expected': 'Line 1\nLine 2'
            },
            {
                'name': 'special_characters',
                'user_input': '!@#$%^&*()',
                'expected': '!@#$%^&*()'
            }
        ]
        
        for case in test_cases:
            with self.subTest(case=case['name']):
                with patch('builtins.input', return_value=case['user_input']) as mock_input:
                    inputs = {"test_field": "test_value"}
                    result = self.agent.process(inputs)
                    
                    self.assertEqual(result, case['expected'])
                    mock_input.assert_called_once_with("Please enter your data: ")
    
    # =============================================================================
    # 3. Infrastructure Integration Tests
    # =============================================================================
    
    @patch('builtins.input', return_value='test_input')
    def test_logging_integration(self, mock_input):
        """Test that agent properly integrates with logging service."""
        inputs = {"test_field": "test_value"}
        
        # Execute process to generate log calls
        self.agent.process(inputs)
        
        # Verify logger was called with expected information
        logger_calls = self.mock_logger.calls
        
        # Should have at least one info call
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(len(info_calls) > 0)
        
        # Verify log message contains agent name and input prompting info
        log_messages = [call[1] for call in info_calls]
        prompt_logged = any("test_input" in msg and "prompting for user input" in msg for msg in log_messages)
        self.assertTrue(prompt_logged, f"Expected prompting logged, got: {log_messages}")
    
    def test_execution_tracker_integration(self):
        """Test that agent properly integrates with execution tracker."""
        # Verify execution tracker is accessible
        tracker = self.agent.execution_tracking_service
        self.assertEqual(tracker, self.mock_execution_tracking_service)
        
        # Verify tracker has expected properties
        self.assertTrue(hasattr(tracker, 'track_inputs'))
        self.assertTrue(hasattr(tracker, 'track_outputs'))
    
    def test_state_adapter_integration(self):
        """Test that agent properly integrates with state adapter."""
        # Verify state adapter is accessible
        adapter = self.agent.state_adapter_service
        self.assertEqual(adapter, self.mock_state_adapter_service)
        
        # Verify adapter has expected methods
        self.assertTrue(hasattr(adapter, 'get_value'))
        self.assertTrue(hasattr(adapter, 'set_value'))
    
    # =============================================================================
    # 4. Service Information and Debugging Tests
    # =============================================================================
    
    def test_get_service_info(self):
        """Test service information retrieval for debugging."""
        service_info = self.agent.get_service_info()
        
        # Verify basic agent information
        self.assertEqual(service_info["agent_name"], "test_input")
        self.assertEqual(service_info["agent_type"], "InputAgent")
        
        # Verify infrastructure service availability
        services = service_info["services"]
        self.assertTrue(services["logger_available"])
        self.assertTrue(services["execution_tracker_available"])
        self.assertTrue(services["state_adapter_available"])
        
        # Verify business services are not configured
        self.assertFalse(services["llm_service_configured"])
        self.assertFalse(services["storage_service_configured"])
        
        # Verify protocol implementation status
        protocols = service_info["protocols"]
        self.assertFalse(protocols["implements_llm_capable"])
        self.assertFalse(protocols["implements_storage_capable"])
        
        # Verify configuration
        config = service_info["configuration"]
        self.assertEqual(config["input_fields"], ["user_data"])
        self.assertEqual(config["output_field"], "user_input")
        self.assertEqual(config["description"], "Test input agent")
    
    def test_get_child_service_info(self):
        """Test InputAgent-specific service information from _get_child_service_info."""
        child_info = self.agent._get_child_service_info()
        
        # Verify InputAgent-specific service information
        self.assertIn("services", child_info)
        services = child_info["services"]
        self.assertTrue(services["supports_user_input_prompting"])
        self.assertTrue(services["handles_console_input"])
        
        # Verify capabilities
        self.assertIn("capabilities", child_info)
        capabilities = child_info["capabilities"]
        self.assertTrue(capabilities["interactive_user_input"])
        self.assertTrue(capabilities["custom_prompt_support"])
        self.assertTrue(capabilities["real_time_input_capture"])
        
        # Verify agent behavior
        self.assertIn("agent_behavior", child_info)
        behavior = child_info["agent_behavior"]
        self.assertEqual(behavior["execution_type"], "interactive_input")
        self.assertEqual(behavior["input_method"], "console_prompt")
        self.assertEqual(behavior["prompt_customization"], "supports_custom_prompts")
    
    # =============================================================================
    # 5. Error Handling and Edge Cases
    # =============================================================================
    
    def test_agent_with_missing_logger_access(self):
        """Test agent behavior when logger is accessed but not provided."""
        # Create agent without logger
        agent_without_logger = InputAgent(
            name="no_logger",
            prompt="Test prompt",
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Accessing logger should raise clear error
        with self.assertRaises(ValueError) as cm:
            _ = agent_without_logger.logger
        
        self.assertIn("Logger not provided", str(cm.exception))
        self.assertIn("no_logger", str(cm.exception))
    
    def test_agent_with_missing_execution_tracker_access(self):
        """Test agent behavior when execution tracker is accessed but not provided."""
        # Create agent without execution tracker
        agent_without_tracker = InputAgent(
            name="no_tracker",
            prompt="Test prompt",
            logger=self.mock_logger,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Accessing execution tracker should raise clear error
        with self.assertRaises(ValueError) as cm:
            _ = agent_without_tracker.execution_tracking_service
        
        self.assertIn("ExecutionTrackingService not provided", str(cm.exception))
        self.assertIn("no_tracker", str(cm.exception))
    
    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_process_with_keyboard_interrupt(self, mock_input):
        """Test process method handling of KeyboardInterrupt (Ctrl+C)."""
        inputs = {"test": "data"}
        
        # Should raise KeyboardInterrupt and not catch it
        with self.assertRaises(KeyboardInterrupt):
            self.agent.process(inputs)
    
    @patch('builtins.input', side_effect=EOFError)
    def test_process_with_eof_error(self, mock_input):
        """Test process method handling of EOFError (Ctrl+D)."""
        inputs = {"test": "data"}
        
        # Should raise EOFError and not catch it
        with self.assertRaises(EOFError):
            self.agent.process(inputs)
    
    # =============================================================================
    # 6. Integration with Agent Run Method (Inherited from BaseAgent)
    # =============================================================================
    
    @patch('builtins.input', return_value='integration_test_input')
    def test_run_method_integration(self, mock_input):
        """Test that the inherited run method works with InputAgent process."""
        # Create mock state
        test_state = {
            "user_data": "initial_data",
            "other_field": "should be preserved"
        }
        
        # Configure state adapter to return proper inputs
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}
        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        
        # CRITICAL: Set execution tracker on agent (required by new architecture)
        self.agent.set_execution_tracker(self.mock_tracker)
        
        # Execute run method
        result_state = self.agent.run(test_state)
        
        # Verify state was updated with user input
        self.assertIn("user_input", result_state)
        self.assertEqual(result_state["user_input"], "integration_test_input")
        
        # Original fields are NOT in result - only output field
        self.assertNotIn("other_field", result_state)
        self.assertEqual(len(result_state), 1)  # Only output field
        
        # Verify input() was called with correct prompt
        mock_input.assert_called_once_with("Please enter your data: ")
        
        # Verify tracking methods were called on the execution tracking service
        self.mock_execution_tracking_service.record_node_start.assert_called_once()
        self.mock_execution_tracking_service.record_node_result.assert_called_once()


if __name__ == '__main__':
    unittest.main()
