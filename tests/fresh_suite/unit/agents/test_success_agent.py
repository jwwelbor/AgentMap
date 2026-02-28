"""
Unit tests for SuccessAgent using pure Mock objects and established testing patterns.

This test suite validates the new protocol-based dependency injection pattern
for agents that generate success messages with detailed context information.
"""

import unittest

from agentmap.agents.builtins.success_agent import SuccessAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestSuccessAgent(unittest.TestCase):
    """Unit tests for SuccessAgent using pure Mock objects."""

    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )

        # Create basic context for testing (explicitly specify output_field)
        self.test_context = {
            "input_fields": ["action", "data"],
            "output_field": "success_message",
            "description": "Test success agent",
        }

        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()

        # Create agent instance with mocked infrastructure dependencies
        self.agent = SuccessAgent(
            name="test_success",
            prompt="Execute successful operation",
            context=self.test_context,
            logger=self.mock_logging_service.get_class_logger(SuccessAgent),
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

        # Get the mock logger for verification
        self.mock_logger = self.agent.logger

    # =============================================================================
    # 1. Agent Initialization Tests
    # =============================================================================

    def test_agent_initialization_with_infrastructure_services(self):
        """Test that agent initializes correctly with infrastructure services."""
        # Verify all infrastructure dependencies are stored
        self.assertEqual(self.agent.name, "test_success")
        self.assertEqual(self.agent.prompt, "Execute successful operation")
        self.assertEqual(self.agent.context, self.test_context)
        self.assertEqual(self.agent.input_fields, ["action", "data"])
        self.assertEqual(self.agent.output_field, "success_message")

        # Verify infrastructure services are available
        self.assertIsNotNone(self.agent.logger)
        self.assertIsNotNone(self.agent.execution_tracking_service)
        self.assertIsNotNone(self.agent.state_adapter_service)

        # Verify no business services are configured (SuccessAgent doesn't need them)
        self.assertFalse(
            hasattr(self.agent, "_llm_service") and self.agent._llm_service is not None
        )
        self.assertFalse(
            hasattr(self.agent, "_storage_service")
            and self.agent._storage_service is not None
        )

    def test_agent_initialization_with_minimal_dependencies(self):
        """Test agent initialization with minimal required dependencies."""
        # Create agent with only required parameters
        minimal_agent = SuccessAgent(
            name="minimal_success", prompt="Minimal success prompt"
        )

        # Verify basic configuration
        self.assertEqual(minimal_agent.name, "minimal_success")
        self.assertEqual(minimal_agent.prompt, "Minimal success prompt")

        # Verify default context handling (output_field should default to None)
        self.assertEqual(minimal_agent.input_fields, [])
        self.assertIsNone(minimal_agent.output_field)

    def test_agent_protocol_compliance(self):
        """Test that SuccessAgent correctly implements (or doesn't implement) service protocols."""
        # SuccessAgent should NOT implement business service protocols
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
    # 2. Core Business Logic Tests (Success Message Generation)
    # =============================================================================

    def test_process_with_no_inputs(self):
        """Test processing with no inputs returns basic success message."""
        inputs = {}

        result = self.agent.process(inputs)

        # Should return basic success message with agent name and prompt
        expected = (
            "SUCCESS: test_success executed with prompt: 'Execute successful operation'"
        )
        self.assertEqual(result, expected)

        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(len(info_calls) > 0)
        self.assertTrue(any("executed with success" in call[1] for call in info_calls))

    def test_process_with_single_input(self):
        """Test processing with single input includes input in message."""
        inputs = {"action": "create_file"}

        result = self.agent.process(inputs)

        # Should include input in success message
        expected = "SUCCESS: test_success executed with inputs: action=create_file with prompt: 'Execute successful operation'"
        self.assertEqual(result, expected)

        # Verify debug logging with full output
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(
            any(
                "Full output:" in call[1] and "create_file" in call[1]
                for call in debug_calls
            )
        )

    def test_process_with_multiple_inputs(self):
        """Test processing with multiple inputs includes all inputs in message."""
        inputs = {"action": "process_data", "data": "user_info", "format": "json"}

        result = self.agent.process(inputs)

        # Should include all inputs in success message
        self.assertIn("SUCCESS: test_success executed with inputs:", result)
        self.assertIn("action=process_data", result)
        self.assertIn("data=user_info", result)
        self.assertIn("format=json", result)
        self.assertIn("with prompt: 'Execute successful operation'", result)

        # Verify all inputs are logged in debug
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        full_output_logs = [
            call[1] for call in debug_calls if "Full output:" in call[1]
        ]
        self.assertTrue(len(full_output_logs) > 0)
        self.assertTrue(
            any(
                "process_data" in log and "user_info" in log for log in full_output_logs
            )
        )

    def test_process_with_complex_input_types(self):
        """Test processing with complex data types in inputs."""
        inputs = {
            "list_data": [1, 2, 3],
            "dict_data": {"nested": "value"},
            "number": 42,
            "boolean": True,
        }

        result = self.agent.process(inputs)

        # Should handle complex types in message
        self.assertIn("SUCCESS: test_success executed with inputs:", result)
        self.assertIn("list_data=[1, 2, 3]", result)
        self.assertIn("dict_data={'nested': 'value'}", result)
        self.assertIn("number=42", result)
        self.assertIn("boolean=True", result)

    def test_process_without_prompt(self):
        """Test processing when no prompt is provided."""
        # Create agent with None prompt
        agent_no_prompt = SuccessAgent(
            name="no_prompt_success",
            prompt=None,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

        inputs = {"test": "data"}
        result = agent_no_prompt.process(inputs)

        # Should not include prompt in message when prompt is None
        expected = "SUCCESS: no_prompt_success executed with inputs: test=data"
        self.assertEqual(result, expected)

    def test_process_with_empty_prompt(self):
        """Test processing when prompt is empty string."""
        # Create agent with empty prompt
        agent_empty_prompt = SuccessAgent(
            name="empty_prompt_success",
            prompt="",
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

        inputs = {"test": "data"}
        result = agent_empty_prompt.process(inputs)

        # Should not include prompt in message when prompt is empty (falsy)
        expected = "SUCCESS: empty_prompt_success executed with inputs: test=data"
        self.assertEqual(result, expected)

    def test_process_with_various_scenarios(self):
        """Test process method with various input/prompt combinations using subTest."""
        test_cases = [
            {
                "name": "no_inputs_no_prompt",
                "inputs": {},
                "prompt": None,
                "expected_parts": ["SUCCESS: test_agent executed"],
            },
            {
                "name": "inputs_no_prompt",
                "inputs": {"key": "value"},
                "prompt": None,
                "expected_parts": [
                    "SUCCESS: test_agent executed",
                    "with inputs: key=value",
                ],
            },
            {
                "name": "no_inputs_with_prompt",
                "inputs": {},
                "prompt": "Test prompt",
                "expected_parts": [
                    "SUCCESS: test_agent executed",
                    "with prompt: 'Test prompt'",
                ],
            },
            {
                "name": "inputs_and_prompt",
                "inputs": {"action": "test"},
                "prompt": "Test prompt",
                "expected_parts": [
                    "SUCCESS: test_agent executed",
                    "with inputs: action=test",
                    "with prompt: 'Test prompt'",
                ],
            },
        ]

        for case in test_cases:
            with self.subTest(case=case["name"]):
                # Create agent for this test case
                test_agent = SuccessAgent(
                    name="test_agent",
                    prompt=case["prompt"],
                    logger=self.mock_logger,
                    execution_tracking_service=self.mock_execution_tracking_service,
                    state_adapter_service=self.mock_state_adapter_service,
                )

                result = test_agent.process(case["inputs"])

                # Verify all expected parts are in the result
                for expected_part in case["expected_parts"]:
                    self.assertIn(expected_part, result)

    # =============================================================================
    # 3. Infrastructure Integration Tests
    # =============================================================================

    def test_logging_integration(self):
        """Test that agent properly integrates with logging service."""
        inputs = {"action": "test_action", "data": "test_data"}

        # Execute process to generate log calls
        self.agent.process(inputs)

        # Verify logger was called with expected information
        logger_calls = self.mock_logger.calls

        # Should have info level logs
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(len(info_calls) > 0)
        success_logged = any("executed with success" in call[1] for call in info_calls)
        self.assertTrue(
            success_logged,
            f"Expected success execution logged, got: {[call[1] for call in info_calls]}",
        )

        # Should have debug level logs with detailed information
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        self.assertTrue(
            len(debug_calls) >= 3
        )  # Full output, Input fields, Output field

        # Verify specific debug information
        debug_messages = [call[1] for call in debug_calls]
        self.assertTrue(any("Full output:" in msg for msg in debug_messages))
        self.assertTrue(any("Input fields:" in msg for msg in debug_messages))
        self.assertTrue(any("Output field:" in msg for msg in debug_messages))

    def test_execution_tracker_integration(self):
        """Test that agent properly integrates with execution tracker."""
        # Verify execution tracker is accessible
        tracker = self.agent.execution_tracking_service
        self.assertEqual(tracker, self.mock_execution_tracking_service)

        # Verify tracker has expected properties
        self.assertTrue(hasattr(tracker, "track_inputs"))
        self.assertTrue(hasattr(tracker, "track_outputs"))

    def test_state_adapter_integration(self):
        """Test that agent properly integrates with state adapter."""
        # Verify state adapter is accessible
        adapter = self.agent.state_adapter_service
        self.assertEqual(adapter, self.mock_state_adapter_service)

        # Verify adapter has expected methods
        self.assertTrue(hasattr(adapter, "get_value"))
        self.assertTrue(hasattr(adapter, "set_value"))

    # =============================================================================
    # 4. Service Information and Debugging Tests
    # =============================================================================

    def test_get_service_info(self):
        """Test service information retrieval for debugging."""
        service_info = self.agent.get_service_info()

        # Verify basic agent information
        self.assertEqual(service_info["agent_name"], "test_success")
        self.assertEqual(service_info["agent_type"], "SuccessAgent")

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
        self.assertEqual(config["input_fields"], ["action", "data"])
        self.assertEqual(config["output_field"], "success_message")
        self.assertEqual(config["description"], "Test success agent")

    def test_get_child_service_info(self):
        """Test SuccessAgent-specific service information from _get_child_service_info."""
        child_info = self.agent._get_child_service_info()

        # Verify SuccessAgent-specific service information
        self.assertIn("services", child_info)
        services = child_info["services"]
        self.assertTrue(services["supports_success_simulation"])
        self.assertTrue(services["generates_success_messages"])

        # Verify capabilities
        self.assertIn("capabilities", child_info)
        capabilities = child_info["capabilities"]
        self.assertTrue(capabilities["success_path_testing"])
        self.assertTrue(capabilities["detailed_success_reporting"])
        self.assertTrue(capabilities["input_context_inclusion"])
        self.assertTrue(capabilities["prompt_context_inclusion"])

        # Verify agent behavior
        self.assertIn("agent_behavior", child_info)
        behavior = child_info["agent_behavior"]
        self.assertEqual(behavior["execution_type"], "success_simulation")
        self.assertEqual(behavior["output_format"], "success_message_with_context")
        self.assertEqual(behavior["testing_purpose"], "validates_success_branches")

    # =============================================================================
    # 5. Error Handling and Edge Cases
    # =============================================================================

    def test_agent_with_missing_logger_access(self):
        """Test agent behavior when logger is accessed but not provided."""
        # Create agent without logger
        agent_without_logger = SuccessAgent(
            name="no_logger",
            prompt="Test prompt",
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

        # Accessing logger should raise clear error
        with self.assertRaises(ValueError) as cm:
            _ = agent_without_logger.logger

        self.assertIn("Logger not provided", str(cm.exception))
        self.assertIn("no_logger", str(cm.exception))

    def test_agent_with_missing_execution_tracker_access(self):
        """Test agent behavior when execution tracker is accessed but not provided."""
        # Create agent without execution tracker
        agent_without_tracker = SuccessAgent(
            name="no_tracker",
            prompt="Test prompt",
            logger=self.mock_logger,
            state_adapter_service=self.mock_state_adapter_service,
        )

        # Accessing execution tracker should raise clear error
        with self.assertRaises(ValueError) as cm:
            _ = agent_without_tracker.execution_tracking_service

        self.assertIn("ExecutionTrackingService not provided", str(cm.exception))
        self.assertIn("no_tracker", str(cm.exception))

    def test_process_with_none_values_in_inputs(self):
        """Test processing with None values in inputs."""
        inputs = {"action": None, "data": "valid_data", "empty": None}

        result = self.agent.process(inputs)

        # Should handle None values gracefully in message
        self.assertIn("SUCCESS: test_success executed with inputs:", result)
        self.assertIn("action=None", result)
        self.assertIn("data=valid_data", result)
        self.assertIn("empty=None", result)

    def test_process_with_special_characters_in_inputs(self):
        """Test processing with special characters in input values."""
        inputs = {
            "text": "Hello, World! @#$%^&*()",
            "path": "/path/to/file with spaces",
            "quotes": "Text with \"quotes\" and 'apostrophes'",
        }

        result = self.agent.process(inputs)

        # Should handle special characters properly
        self.assertIn("SUCCESS: test_success executed with inputs:", result)
        # The exact format may vary based on string representation,
        # but the message should be generated without errors
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    # =============================================================================
    # 6. Integration with Agent Run Method (Inherited from BaseAgent)
    # =============================================================================

    def test_run_method_integration(self):
        """Test that the inherited run method works with SuccessAgent process."""
        # Create mock state
        test_state = {
            "action": "test_operation",
            "data": "sample_data",
            "other_field": "should be preserved",
        }

        # Configure state adapter to return proper inputs
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs

        # IMPORTANT: Set execution tracker before calling run() - required by BaseAgent
        self.agent.set_execution_tracker(self.mock_tracker)

        # Execute run method
        result_state = self.agent.run(test_state)

        # Verify state was updated with success message
        self.assertIn("success_message", result_state)
        success_message = result_state["success_message"]
        self.assertIn("SUCCESS: test_success executed", success_message)
        self.assertIn("action=test_operation", success_message)
        self.assertIn("data=sample_data", success_message)

        # Original fields are NOT in result - only output field
        self.assertNotIn("other_field", result_state)
        self.assertEqual(len(result_state), 1)  # Only output field

        # Verify tracking methods were called on the execution tracking service
        self.mock_execution_tracking_service.record_node_start.assert_called()
        self.mock_execution_tracking_service.record_node_result.assert_called()


if __name__ == "__main__":
    unittest.main()
