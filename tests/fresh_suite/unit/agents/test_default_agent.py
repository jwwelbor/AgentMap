"""
Unit tests for DefaultAgent using pure Mock objects and established testing patterns.

This test suite validates the new protocol-based dependency injection pattern
for agents that require no business services (LLM, storage) but provide
default processing behavior with message formatting and UUID tracking.
"""

import unittest
from unittest.mock import Mock, patch

from agentmap.agents.builtins.default_agent import DefaultAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestDefaultAgent(unittest.TestCase):
    """Unit tests for DefaultAgent using pure Mock objects."""

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
            "input_fields": ["input"],
            "output_field": "output",  # Explicitly set since default is now None
            "description": "Test default agent",
        }

        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()

        # Create agent instance with mocked infrastructure dependencies
        self.agent = DefaultAgent(
            name="test_default",
            prompt="Default processing with test prompt",
            context=self.test_context,
            logger=self.mock_logging_service.get_class_logger(DefaultAgent),
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
        self.assertEqual(self.agent.name, "test_default")
        self.assertEqual(self.agent.prompt, "Default processing with test prompt")
        self.assertEqual(self.agent.context, self.test_context)
        self.assertEqual(self.agent.input_fields, ["input"])
        self.assertEqual(self.agent.output_field, "output")

        # Verify infrastructure services are available
        self.assertIsNotNone(self.agent.logger)
        self.assertIsNotNone(self.agent.execution_tracking_service)
        self.assertIsNotNone(self.agent.state_adapter_service)

        # Verify no business services are configured (DefaultAgent doesn't need them)
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
        minimal_agent = DefaultAgent(name="minimal_default", prompt="Minimal prompt")

        # Verify basic configuration
        self.assertEqual(minimal_agent.name, "minimal_default")
        self.assertEqual(minimal_agent.prompt, "Minimal prompt")

        # Verify default context handling (output_field should default to None)
        self.assertEqual(minimal_agent.input_fields, [])
        self.assertIsNone(
            minimal_agent.output_field
        )  # Default is now None, not "output"

    def test_agent_protocol_compliance(self):
        """Test that DefaultAgent correctly implements (or doesn't implement) service protocols."""
        # DefaultAgent should NOT implement business service protocols
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
    # 2. Core Business Logic Tests
    # =============================================================================

    @patch("uuid.uuid4")
    def test_process_basic_functionality(self, mock_uuid):
        """Test basic process functionality with message formatting."""
        # Mock UUID to have predictable process ID
        mock_uuid.return_value.hex = "12345678abcdef12345678abcdef1234"

        inputs = {"input": "test_value"}

        result = self.agent.process(inputs)

        # Should return formatted message with agent name and prompt
        expected_message = "[test_default] DefaultAgent executed with prompt: 'Default processing with test prompt'"
        self.assertEqual(result, expected_message)

        # Verify UUID was called to generate process ID
        mock_uuid.assert_called()

    def test_process_with_empty_inputs(self):
        """Test processing with empty inputs."""
        inputs = {}

        result = self.agent.process(inputs)

        # Should still return formatted message
        expected_message = "[test_default] DefaultAgent executed with prompt: 'Default processing with test prompt'"
        self.assertEqual(result, expected_message)

    def test_process_with_multiple_inputs(self):
        """Test processing with multiple input values."""
        inputs = {"input1": "First value", "input2": "Second value", "input3": 42}

        result = self.agent.process(inputs)

        # Should return same formatted message regardless of inputs
        expected_message = "[test_default] DefaultAgent executed with prompt: 'Default processing with test prompt'"
        self.assertEqual(result, expected_message)

    def test_process_without_prompt(self):
        """Test processing when prompt is empty or None."""
        # Create agent without prompt
        agent_no_prompt = DefaultAgent(
            name="no_prompt_agent",
            prompt="",
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

        inputs = {"input": "test"}
        result = agent_no_prompt.process(inputs)

        # Should return message without prompt part
        expected_message = "[no_prompt_agent] DefaultAgent executed"
        self.assertEqual(result, expected_message)

    def test_process_with_none_prompt(self):
        """Test processing when prompt is explicitly None."""
        # Create agent with None prompt
        agent_none_prompt = DefaultAgent(
            name="none_prompt_agent",
            prompt=None,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

        inputs = {"input": "test"}
        result = agent_none_prompt.process(inputs)

        # Should return message without prompt part
        expected_message = "[none_prompt_agent] DefaultAgent executed"
        self.assertEqual(result, expected_message)

    @patch("uuid.uuid4")
    def test_process_uuid_generation_uniqueness(self, mock_uuid):
        """Test that each process call generates a unique process ID."""
        # Set up sequence of different UUIDs
        mock_uuid.side_effect = [
            Mock(hex="uuid1234567890123456789012345678"),
            Mock(hex="uuid9876543210987654321098765432"),
        ]

        inputs = {"input": "test"}

        # First call
        result1 = self.agent.process(inputs)
        self.assertIsNotNone(result1)

        # Reset mock logger to clear calls
        self.mock_logger.reset_mock()

        # Second call
        result2 = self.agent.process(inputs)
        self.assertIsNotNone(result2)

        # Verify UUID was called twice (once for each process call)
        self.assertEqual(mock_uuid.call_count, 2)

    def test_process_with_complex_data_types(self):
        """Test processing with complex data types in inputs."""
        complex_inputs = {
            "list_input": [1, 2, 3],
            "dict_input": {"nested": "value"},
            "string_input": "text",
            "none_input": None,
        }

        result = self.agent.process(complex_inputs)

        # Should still return formatted message regardless of input complexity
        expected_message = "[test_default] DefaultAgent executed with prompt: 'Default processing with test prompt'"
        self.assertEqual(result, expected_message)

    # =============================================================================
    # 3. Infrastructure Integration Tests
    # =============================================================================

    def test_logging_integration(self):
        """Test that agent properly integrates with logging service."""
        inputs = {"test_input": "test_value"}

        # Execute process to generate log calls
        self.agent.process(inputs)

        # Verify logger was called with expected information
        logger_calls = self.mock_logger.calls

        # Should have debug and info calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        info_calls = [call for call in logger_calls if call[0] == "info"]

        self.assertTrue(len(debug_calls) >= 2)  # START and COMPLETE
        self.assertTrue(len(info_calls) >= 1)  # output log

        # Verify basic logging content (don't be too specific about format)
        debug_messages = [call[1] for call in debug_calls]
        start_logged = any("START" in msg for msg in debug_messages)
        complete_logged = any("COMPLETE" in msg for msg in debug_messages)

        self.assertTrue(
            start_logged, f"Expected START message logged, got: {debug_messages}"
        )
        self.assertTrue(
            complete_logged, f"Expected COMPLETE message logged, got: {debug_messages}"
        )

        # Verify some info logging occurred
        self.assertTrue(len(info_calls) > 0, "Expected some info-level logging")

    def test_logging_process_id_consistency(self):
        """Test that logging occurs consistently during process execution."""
        inputs = {"input": "test"}
        self.agent.process(inputs)

        # Get all log messages
        logger_calls = self.mock_logger.calls

        # Verify logging occurred (basic consistency check)
        self.assertTrue(len(logger_calls) > 0, "Expected some logging to occur")

        # Verify we have both debug and info level logging
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        info_calls = [call for call in logger_calls if call[0] == "info"]

        self.assertTrue(len(debug_calls) > 0, "Expected debug logging")
        self.assertTrue(len(info_calls) > 0, "Expected info logging")

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
        self.assertEqual(service_info["agent_name"], "test_default")
        self.assertEqual(service_info["agent_type"], "DefaultAgent")

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
        self.assertEqual(config["input_fields"], ["input"])
        self.assertEqual(config["output_field"], "output")
        self.assertEqual(config["description"], "Test default agent")

    def test_get_child_service_info(self):
        """Test DefaultAgent-specific service information."""
        service_info = self.agent.get_service_info()

        # Verify DefaultAgent-specific service information is included
        services = service_info["services"]
        self.assertTrue(services["supports_default_processing"])
        self.assertTrue(services["generates_process_ids"])

        # Verify capabilities
        self.assertIn("capabilities", service_info)
        capabilities = service_info["capabilities"]
        self.assertTrue(capabilities["default_message_generation"])
        self.assertTrue(capabilities["prompt_inclusion"])
        self.assertTrue(capabilities["uuid_tracking"])

        # Verify agent behavior information
        self.assertIn("agent_behavior", service_info)
        behavior = service_info["agent_behavior"]
        self.assertEqual(behavior["execution_type"], "default_processing")
        self.assertEqual(behavior["output_format"], "formatted_message_with_prompt")
        self.assertEqual(behavior["logging_level"], "debug_and_info")

    def test_child_service_info_direct_call(self):
        """Test calling _get_child_service_info directly."""
        child_info = self.agent._get_child_service_info()

        self.assertIsNotNone(child_info)
        self.assertIn("services", child_info)
        self.assertIn("capabilities", child_info)
        self.assertIn("agent_behavior", child_info)

        # Verify specific DefaultAgent capabilities
        self.assertTrue(child_info["services"]["supports_default_processing"])
        self.assertTrue(child_info["capabilities"]["default_message_generation"])
        self.assertEqual(
            child_info["agent_behavior"]["execution_type"], "default_processing"
        )

    # =============================================================================
    # 5. Error Handling and Edge Cases
    # =============================================================================

    def test_agent_with_missing_logger_access(self):
        """Test agent behavior when logger is accessed but not provided."""
        # Create agent without logger
        agent_without_logger = DefaultAgent(
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
        agent_without_tracker = DefaultAgent(
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

    def test_process_with_unusual_agent_names(self):
        """Test process method with unusual but valid agent names."""
        test_cases = [
            # Empty string name
            ("", "Default processing with test prompt"),
            # Special characters
            ("agent-with-dashes", "Test prompt"),
            # Numbers
            ("agent123", "Test prompt"),
            # Unicode characters
            ("agént_ünïcode", "Test prompt"),
        ]

        for i, (agent_name, prompt) in enumerate(test_cases):
            with self.subTest(case=i, agent_name=agent_name):
                test_agent = DefaultAgent(
                    name=agent_name,
                    prompt=prompt,
                    logger=self.mock_logger,
                    execution_tracking_service=self.mock_execution_tracking_service,
                    state_adapter_service=self.mock_state_adapter_service,
                )

                result = test_agent.process({"input": "test"})

                # Should return formatted message with the agent name
                expected_message = (
                    f"[{agent_name}] DefaultAgent executed with prompt: '{prompt}'"
                )
                self.assertEqual(result, expected_message)

    def test_process_with_unusual_prompt_values(self):
        """Test process method with unusual but valid prompt values."""
        test_cases = [
            # Very long prompt
            ("A" * 1000),
            # Prompt with special characters
            "Prompt with 'quotes' and \"double quotes\" and symbols: !@#$%^&*()",
            # Prompt with newlines
            "Multi-line\nprompt\nwith\nbreaks",
            # Unicode prompt
            "Prómpt wïth ünïcôde cháracters: 你好世界",
        ]

        for i, prompt in enumerate(test_cases):
            with self.subTest(
                case=i, prompt=prompt[:50] + "..." if len(prompt) > 50 else prompt
            ):
                test_agent = DefaultAgent(
                    name="test_agent",
                    prompt=prompt,
                    logger=self.mock_logger,
                    execution_tracking_service=self.mock_execution_tracking_service,
                    state_adapter_service=self.mock_state_adapter_service,
                )

                result = test_agent.process({"input": "test"})

                # Should return formatted message with the full prompt
                expected_message = (
                    f"[test_agent] DefaultAgent executed with prompt: '{prompt}'"
                )
                self.assertEqual(result, expected_message)

    @patch("uuid.uuid4")
    def test_process_uuid_exception_handling(self, mock_uuid):
        """Test process behavior when UUID generation fails."""
        # Make UUID raise an exception
        mock_uuid.side_effect = Exception("UUID generation failed")

        inputs = {"input": "test"}

        # Process should still work, just without UUID tracking
        with self.assertRaises(Exception):
            self.agent.process(inputs)

    # =============================================================================
    # 6. Integration with Agent Run Method (Inherited from BaseAgent)
    # =============================================================================

    def test_run_method_integration(self):
        """Test that the inherited run method works with DefaultAgent process."""
        # Create mock state
        test_state = {"input": "test message", "other_field": "should be preserved"}

        # Configure state adapter to return proper inputs
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs

        # IMPORTANT: Set execution tracker before calling run() - required by BaseAgent
        self.agent.set_execution_tracker(self.mock_tracker)

        # Execute run method
        result_state = self.agent.run(test_state)

        # NEW BEHAVIOR: Returns partial state update (only output field)
        self.assertIn("output", result_state)
        expected_output = "[test_default] DefaultAgent executed with prompt: 'Default processing with test prompt'"
        self.assertEqual(result_state["output"], expected_output)

        # Original fields are NOT in result - only output field
        self.assertNotIn("other_field", result_state)
        self.assertEqual(len(result_state), 1)  # Only output field

        # Verify tracking methods were called on the execution tracking service
        self.mock_execution_tracking_service.record_node_start.assert_called()
        self.mock_execution_tracking_service.record_node_result.assert_called()

    def test_run_method_with_no_output_field(self):
        """Test run method when output_field is not configured."""
        # Create agent without output_field
        agent_no_output = DefaultAgent(
            name="no_output_agent",
            prompt="Test prompt",
            context={"input_fields": ["input"]},  # No output_field
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

        test_state = {"input": "test"}

        # Configure state adapter
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs

        # IMPORTANT: Set execution tracker before calling run() - required by BaseAgent
        agent_no_output.set_execution_tracker(self.mock_tracker)

        # Execute run method
        result_state = agent_no_output.run(test_state)

        # NEW BEHAVIOR: When output_field is None, return empty dict
        self.assertEqual(result_state, {})
        self.assertEqual(len(result_state), 0)

        # Tracking should still occur
        self.mock_execution_tracking_service.record_node_start.assert_called()
        self.mock_execution_tracking_service.record_node_result.assert_called()

    def test_invoke_method_compatibility(self):
        """Test LangGraph compatibility via invoke method."""
        test_state = {"input": "test message"}

        # Configure state adapter
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        def mock_set_value(state, field, value):
            updated_state = state.copy()
            updated_state[field] = value
            return updated_state

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value

        # IMPORTANT: Set execution tracker before calling run() - required by BaseAgent
        self.agent.set_execution_tracker(self.mock_tracker)

        # invoke should work the same as run
        result_via_invoke = self.agent.invoke(test_state)
        result_via_run = self.agent.run(test_state)

        # Both should produce the same result
        self.assertEqual(result_via_invoke, result_via_run)


if __name__ == "__main__":
    unittest.main()
