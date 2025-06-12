"""
Unit tests for FailureAgent using pure Mock objects and established testing patterns.

This test suite validates the new protocol-based dependency injection pattern
for agents that simulate failure behavior with post-processing state modification.
"""
import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any

from agentmap.agents.builtins.failure_agent import FailureAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent
from agentmap.services.state_adapter_service import StateAdapterService
from tests.utils.mock_service_factory import MockServiceFactory


class TestFailureAgent(unittest.TestCase):
    """Unit tests for FailureAgent using pure Mock objects."""
    
    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Create basic context for testing (explicitly specify output_field)
        self.test_context = {
            "input_fields": ["operation", "target"],
            "output_field": "failure_result",
            "description": "Test failure agent"
        }
        
        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()
        
        # Create agent instance with mocked infrastructure dependencies
        self.agent = FailureAgent(
            name="test_failure",
            prompt="Execute operation that will fail",
            context=self.test_context,
            logger=self.mock_logging_service.get_class_logger(FailureAgent),
            execution_tracker_service=self.mock_tracker,
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
        self.assertEqual(self.agent.name, "test_failure")
        self.assertEqual(self.agent.prompt, "Execute operation that will fail")
        self.assertEqual(self.agent.context, self.test_context)
        self.assertEqual(self.agent.input_fields, ["operation", "target"])
        self.assertEqual(self.agent.output_field, "failure_result")
        
        # Verify infrastructure services are available
        self.assertIsNotNone(self.agent.logger)
        self.assertIsNotNone(self.agent.execution_tracker_service)
        self.assertIsNotNone(self.agent.state_adapter_service)
        
        # Verify no business services are configured (FailureAgent doesn't need them)
        self.assertFalse(hasattr(self.agent, '_llm_service') and self.agent._llm_service is not None)
        self.assertFalse(hasattr(self.agent, '_storage_service') and self.agent._storage_service is not None)
    
    def test_agent_initialization_with_minimal_dependencies(self):
        """Test agent initialization with minimal required dependencies."""
        # Create agent with only required parameters
        minimal_agent = FailureAgent(
            name="minimal_failure",
            prompt="Minimal failure prompt"
        )
        
        # Verify basic configuration
        self.assertEqual(minimal_agent.name, "minimal_failure")
        self.assertEqual(minimal_agent.prompt, "Minimal failure prompt")
        
        # Verify default context handling (output_field should default to None)
        self.assertEqual(minimal_agent.input_fields, [])
        self.assertIsNone(minimal_agent.output_field)
    
    def test_agent_protocol_compliance(self):
        """Test that FailureAgent correctly implements (or doesn't implement) service protocols."""
        # FailureAgent should NOT implement business service protocols
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
    # 2. Core Business Logic Tests (Failure Message Generation)
    # =============================================================================
    
    def test_process_with_no_inputs(self):
        """Test processing with no inputs returns basic failure message."""
        inputs = {}
        
        result = self.agent.process(inputs)
        
        # Should return basic failure message with agent name and prompt
        expected = "test_failure executed (will set last_action_success=False) with prompt: 'Execute operation that will fail'"
        self.assertEqual(result, expected)
    
    def test_process_with_single_input(self):
        """Test processing with single input includes input in message."""
        inputs = {"operation": "delete_file"}
        
        result = self.agent.process(inputs)
        
        # Should include input in failure message
        expected = "test_failure executed (will set last_action_success=False) with inputs: operation with prompt: 'Execute operation that will fail'"
        self.assertEqual(result, expected)
    
    def test_process_with_multiple_inputs(self):
        """Test processing with multiple inputs includes all inputs in message."""
        inputs = {
            "operation": "backup_data",
            "target": "database",
            "format": "sql"
        }
        
        result = self.agent.process(inputs)
        
        # Should include all input keys (not values) in failure message
        self.assertIn("test_failure executed (will set last_action_success=False)", result)
        self.assertIn("with inputs: operation, target, format", result)
        self.assertIn("with prompt: 'Execute operation that will fail'", result)
    
    def test_process_without_prompt(self):
        """Test processing when no prompt is provided."""
        # Create agent with None prompt
        agent_no_prompt = FailureAgent(
            name="no_prompt_failure",
            prompt=None,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_tracker,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        inputs = {"test": "data"}
        result = agent_no_prompt.process(inputs)
        
        # Should not include prompt in message when prompt is None
        expected = "no_prompt_failure executed (will set last_action_success=False) with inputs: test"
        self.assertEqual(result, expected)
    
    def test_process_with_empty_prompt(self):
        """Test processing when prompt is empty string."""
        # Create agent with empty prompt
        agent_empty_prompt = FailureAgent(
            name="empty_prompt_failure",
            prompt="",
            logger=self.mock_logger,
            execution_tracker_service=self.mock_tracker,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        inputs = {"test": "data"}
        result = agent_empty_prompt.process(inputs)
        
        # Should not include prompt in message when prompt is empty (falsy)
        expected = "empty_prompt_failure executed (will set last_action_success=False) with inputs: test"
        self.assertEqual(result, expected)
    
    def test_process_with_various_scenarios(self):
        """Test process method with various input/prompt combinations using subTest."""
        test_cases = [
            {
                'name': 'no_inputs_no_prompt',
                'inputs': {},
                'prompt': None,
                'expected_parts': ['test_agent executed (will set last_action_success=False)']
            },
            {
                'name': 'inputs_no_prompt',
                'inputs': {'key': 'value'},
                'prompt': None,
                'expected_parts': ['test_agent executed (will set last_action_success=False)', 'with inputs: key']
            },
            {
                'name': 'no_inputs_with_prompt',
                'inputs': {},
                'prompt': 'Test prompt',
                'expected_parts': ['test_agent executed (will set last_action_success=False)', "with prompt: 'Test prompt'"]
            },
            {
                'name': 'inputs_and_prompt',
                'inputs': {'action': 'test'},
                'prompt': 'Test prompt',
                'expected_parts': ['test_agent executed (will set last_action_success=False)', 'with inputs: action', "with prompt: 'Test prompt'"]
            }
        ]
        
        for case in test_cases:
            with self.subTest(case=case['name']):
                # Create agent for this test case
                test_agent = FailureAgent(
                    name="test_agent",
                    prompt=case['prompt'],
                    logger=self.mock_logger,
                    execution_tracker_service=self.mock_tracker,
                    state_adapter_service=self.mock_state_adapter_service
                )
                
                result = test_agent.process(case['inputs'])
                
                # Verify all expected parts are in the result
                for expected_part in case['expected_parts']:
                    self.assertIn(expected_part, result)
    
    # =============================================================================
    # 3. Post-Processing Behavior Tests (Unique to FailureAgent)
    # =============================================================================
    
    @patch.object(StateAdapterService, 'set_value')
    def test_post_process_sets_failure_flag(self, mock_set_value):
        """Test that _post_process method sets last_action_success=False."""
        # Mock set_value to return modified state
        def mock_set_value_impl(state, key, value):
            updated_state = state.copy() if isinstance(state, dict) else state
            if isinstance(updated_state, dict):
                updated_state[key] = value
            return updated_state
        
        mock_set_value.side_effect = mock_set_value_impl
        
        # Setup test data
        test_state = {"current_step": "processing", "last_action_success": True}
        test_inputs = {"operation": "test_op"}
        original_output = "Original output message"
        
        # Call _post_process directly
        result_state, result_output = self.agent._post_process(test_state, test_inputs, original_output)
        
        # Verify StateAdapterService.set_value was called with failure flag
        mock_set_value.assert_called_once_with(test_state, "last_action_success", False)
        
        # Verify output was modified to indicate failure branch
        expected_output = "Original output message (Will force FAILURE branch)"
        self.assertEqual(result_output, expected_output)
        
        # Verify state was returned (possibly modified)
        self.assertIsNotNone(result_state)
    
    @patch.object(StateAdapterService, 'set_value')
    def test_post_process_with_none_output(self, mock_set_value):
        """Test _post_process behavior when output is None."""
        mock_set_value.return_value = {"last_action_success": False}
        
        test_state = {"current_step": "processing"}
        test_inputs = {"operation": "test_op"}
        original_output = None
        
        # Call _post_process with None output
        result_state, result_output = self.agent._post_process(test_state, test_inputs, original_output)
        
        # Verify StateAdapterService.set_value was still called
        mock_set_value.assert_called_once_with(test_state, "last_action_success", False)
        
        # Verify output remains None when original output is None
        self.assertIsNone(result_output)
    
    @patch.object(StateAdapterService, 'set_value')
    def test_post_process_with_empty_output(self, mock_set_value):
        """Test _post_process behavior when output is empty string."""
        mock_set_value.return_value = {"last_action_success": False}
        
        test_state = {"current_step": "processing"}
        test_inputs = {"operation": "test_op"}
        original_output = ""
        
        # Call _post_process with empty output
        result_state, result_output = self.agent._post_process(test_state, test_inputs, original_output)
        
        # Verify StateAdapterService.set_value was called
        mock_set_value.assert_called_once_with(test_state, "last_action_success", False)
        
        # Verify empty output is not modified (falsy check)
        self.assertEqual(result_output, "")
    
    def test_post_process_output_modification(self):
        """Test that _post_process correctly modifies output message."""
        test_cases = [
            {
                'original': 'Simple message',
                'expected': 'Simple message (Will force FAILURE branch)'
            },
            {
                'original': 'Complex message with details',
                'expected': 'Complex message with details (Will force FAILURE branch)'
            },
            {
                'original': 'Message with special chars !@#$%',
                'expected': 'Message with special chars !@#$% (Will force FAILURE branch)'
            }
        ]
        
        with patch.object(StateAdapterService, 'set_value') as mock_set_value:
            mock_set_value.return_value = {"last_action_success": False}
            
            for case in test_cases:
                with self.subTest(original=case['original']):
                    test_state = {}
                    test_inputs = {}
                    
                    result_state, result_output = self.agent._post_process(
                        test_state, test_inputs, case['original']
                    )
                    
                    self.assertEqual(result_output, case['expected'])
    
    # =============================================================================
    # 4. Infrastructure Integration Tests
    # =============================================================================
    
    def test_execution_tracker_integration(self):
        """Test that agent properly integrates with execution tracker."""
        # Verify execution tracker is accessible
        tracker = self.agent.execution_tracker_service
        self.assertEqual(tracker, self.mock_tracker)
        
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
    # 5. Service Information and Debugging Tests
    # =============================================================================
    
    def test_get_service_info(self):
        """Test service information retrieval for debugging."""
        service_info = self.agent.get_service_info()
        
        # Verify basic agent information
        self.assertEqual(service_info["agent_name"], "test_failure")
        self.assertEqual(service_info["agent_type"], "FailureAgent")
        
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
        self.assertEqual(config["input_fields"], ["operation", "target"])
        self.assertEqual(config["output_field"], "failure_result")
        self.assertEqual(config["description"], "Test failure agent")
    
    def test_get_child_service_info(self):
        """Test FailureAgent-specific service information from _get_child_service_info."""
        child_info = self.agent._get_child_service_info()
        
        # Verify FailureAgent-specific service information
        self.assertIn("services", child_info)
        services = child_info["services"]
        self.assertTrue(services["supports_failure_simulation"])
        self.assertTrue(services["manipulates_success_flags"])
        self.assertTrue(services["modifies_post_processing"])
        
        # Verify capabilities
        self.assertIn("capabilities", child_info)
        capabilities = child_info["capabilities"]
        self.assertTrue(capabilities["failure_path_testing"])
        self.assertTrue(capabilities["state_modification"])
        self.assertTrue(capabilities["success_flag_override"])
        self.assertTrue(capabilities["output_message_modification"])
        
        # Verify agent behavior
        self.assertIn("agent_behavior", child_info)
        behavior = child_info["agent_behavior"]
        self.assertEqual(behavior["execution_type"], "failure_simulation")
        self.assertEqual(behavior["post_process_behavior"], "sets_last_action_success_false")
        self.assertEqual(behavior["testing_purpose"], "validates_failure_branches")
        self.assertEqual(behavior["state_manipulation"], "forces_failure_state")
    
    # =============================================================================
    # 6. Error Handling and Edge Cases
    # =============================================================================
    
    def test_agent_with_missing_logger_access(self):
        """Test agent behavior when logger is accessed but not provided."""
        # Create agent without logger
        agent_without_logger = FailureAgent(
            name="no_logger",
            prompt="Test prompt",
            execution_tracker_service=self.mock_tracker,
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
        agent_without_tracker = FailureAgent(
            name="no_tracker",
            prompt="Test prompt",
            logger=self.mock_logger,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Accessing execution tracker should raise clear error
        with self.assertRaises(ValueError) as cm:
            _ = agent_without_tracker.execution_tracker_service
        
        self.assertIn("ExecutionTracker not provided", str(cm.exception))
        self.assertIn("no_tracker", str(cm.exception))
    
    def test_process_with_complex_input_types(self):
        """Test processing with complex data types in inputs."""
        inputs = {
            "list_data": [1, 2, 3],
            "dict_data": {"nested": "value"},
            "number": 42
        }
        
        result = self.agent.process(inputs)
        
        # Should handle complex types and include all input keys
        self.assertIn("test_failure executed (will set last_action_success=False)", result)
        self.assertIn("with inputs: list_data, dict_data, number", result)
    
    # =============================================================================
    # 7. Integration with Agent Run Method (Inherited from BaseAgent)
    # =============================================================================
    
    def test_run_method_integration_with_failure_simulation(self):
        """Test that the inherited run method works with FailureAgent post-processing."""
        # Create mock state
        test_state = {
            "operation": "test_operation",
            "target": "sample_target",
            "other_field": "should be preserved",
            "last_action_success": True  # Will be overridden by FailureAgent
        }
        
        # Configure state adapter to return proper inputs
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}
        
        def mock_set_value(state, field, value):
            updated_state = state.copy()
            updated_state[field] = value
            return updated_state
        
        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        # Mock the StateAdapterService.set_value static method for post-processing
        with patch.object(StateAdapterService, 'set_value', side_effect=mock_set_value):
            # Execute run method
            result_state = self.agent.run(test_state)
        
        # Verify state was updated with failure message
        self.assertIn("failure_result", result_state)
        failure_message = result_state["failure_result"]
        self.assertIn("test_failure executed (will set last_action_success=False)", failure_message)
        self.assertIn("(Will force FAILURE branch)", failure_message)
        
        # Verify failure flag was set by post-processing
        self.assertEqual(result_state["last_action_success"], False)
        
        # Verify original fields are preserved
        self.assertEqual(result_state["other_field"], "should be preserved")
        
        # Verify tracking methods were called on the tracker instance
        self.mock_tracker.record_node_start.assert_called()
        self.mock_tracker.record_node_result.assert_called()


if __name__ == '__main__':
    unittest.main()
