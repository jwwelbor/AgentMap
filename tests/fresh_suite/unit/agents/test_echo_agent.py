"""
Unit tests for EchoAgent using pure Mock objects and established testing patterns.

This test suite validates the new protocol-based dependency injection pattern
for agents that require no business services (LLM, storage).
"""

import unittest

from agentmap.agents.builtins.echo_agent import EchoAgent
from agentmap.services.protocols import LLMCapableAgent, StorageCapableAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestEchoAgent(unittest.TestCase):
    """Unit tests for EchoAgent using pure Mock objects."""

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
            "description": "Test echo agent",
        }

        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()

        # Create agent instance with mocked infrastructure dependencies
        self.agent = EchoAgent(
            name="test_echo",
            prompt="Echo the input unchanged",
            context=self.test_context,
            logger=self.mock_logging_service.get_class_logger(EchoAgent),
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
        self.assertEqual(self.agent.name, "test_echo")
        self.assertEqual(self.agent.prompt, "Echo the input unchanged")
        self.assertEqual(self.agent.context, self.test_context)
        self.assertEqual(self.agent.input_fields, ["input"])
        self.assertEqual(self.agent.output_field, "output")

        # Verify infrastructure services are available
        self.assertIsNotNone(self.agent.logger)
        self.assertIsNotNone(self.agent.execution_tracking_service)
        self.assertIsNotNone(self.agent.state_adapter_service)

        # Verify no business services are configured (EchoAgent doesn't need them)
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
        minimal_agent = EchoAgent(name="minimal_echo", prompt="Minimal prompt")

        # Verify basic configuration
        self.assertEqual(minimal_agent.name, "minimal_echo")
        self.assertEqual(minimal_agent.prompt, "Minimal prompt")

        # Verify default context handling (output_field should default to None)
        self.assertEqual(minimal_agent.input_fields, [])
        self.assertIsNone(
            minimal_agent.output_field
        )  # Default is now None, not "output"

    def test_agent_protocol_compliance(self):
        """Test that EchoAgent correctly implements (or doesn't implement) service protocols."""
        # EchoAgent should NOT implement business service protocols
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

    def test_process_single_input(self):
        """Test processing with a single input value."""
        inputs = {"input": "Hello World"}

        result = self.agent.process(inputs)

        # Should return the single input value directly
        self.assertEqual(result, "Hello World")

        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(len(info_calls) > 0)
        self.assertTrue(any("received inputs" in call[1] for call in info_calls))

    def test_process_multiple_inputs(self):
        """Test processing with multiple input values."""
        inputs = {"input1": "First value", "input2": "Second value", "input3": 42}

        result = self.agent.process(inputs)

        # Should return all inputs as dictionary for multiple inputs
        self.assertEqual(result, inputs)

        # Verify logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(any("received inputs" in call[1] for call in info_calls))

    def test_process_empty_inputs(self):
        """Test processing with empty inputs."""
        inputs = {}

        result = self.agent.process(inputs)

        # Should return default message for no input
        self.assertEqual(result, "No input provided to echo")

        # Verify logging
        logger_calls = self.mock_logger.calls
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(any("received inputs" in call[1] for call in info_calls))

    def test_process_with_none_values(self):
        """Test processing with None values in inputs."""
        inputs = {"input": None}

        result = self.agent.process(inputs)

        # Should return None value directly
        self.assertIsNone(result)

    def test_process_with_complex_data_types(self):
        """Test processing with complex data types."""
        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "string": "text",
        }
        inputs = {"input": complex_data}

        result = self.agent.process(inputs)

        # Should return the complex data unchanged
        self.assertEqual(result, complex_data)

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

        # Should have at least one info call
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(len(info_calls) > 0)

        # Verify log message contains input information
        log_messages = [call[1] for call in info_calls]
        input_logged = any(
            "test_input" in msg and "test_value" in msg for msg in log_messages
        )
        self.assertTrue(input_logged, f"Expected input logged, got: {log_messages}")

        # Verify prompt is logged
        prompt_logged = any("Echo the input unchanged" in msg for msg in log_messages)
        self.assertTrue(prompt_logged, f"Expected prompt logged, got: {log_messages}")

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
        self.assertEqual(service_info["agent_name"], "test_echo")
        self.assertEqual(service_info["agent_type"], "EchoAgent")

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
        self.assertEqual(config["description"], "Test echo agent")

    # =============================================================================
    # 5. Error Handling and Edge Cases
    # =============================================================================

    def test_agent_with_missing_logger_access(self):
        """Test agent behavior when logger is accessed but not provided."""
        # Create agent without logger
        agent_without_logger = EchoAgent(
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
        agent_without_tracker = EchoAgent(
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

    def test_process_with_unusual_input_structures(self):
        """Test process method with unusual but valid input structures."""
        test_cases = [
            # Empty string
            {"input": ""},
            # Number zero
            {"input": 0},
            # Boolean false
            {"input": False},
            # Complex nested structure
            {"input": {"nested": {"deep": {"value": "test"}}}},
            # List with mixed types
            {"input": [1, "two", {"three": 3}, None]},
        ]

        for i, inputs in enumerate(test_cases):
            with self.subTest(case=i, inputs=inputs):
                result = self.agent.process(inputs)
                # EchoAgent should return the input value unchanged
                self.assertEqual(result, inputs["input"])

    # =============================================================================
    # 6. Integration with Agent Run Method (Inherited from BaseAgent)
    # =============================================================================

    def test_run_method_integration(self):
        """Test that the inherited run method works with EchoAgent process."""
        # Create mock state
        test_state = {"input": "test message", "other_field": "should be ignored"}

        # Configure state adapter to return proper inputs
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs

        # CRITICAL: Set execution tracker on agent (required by new architecture)
        self.agent.set_execution_tracker(self.mock_tracker)

        # Execute run method
        result_state = self.agent.run(test_state)

        # NEW BEHAVIOR: Returns partial state update (only output field)
        self.assertIn("output", result_state)
        self.assertEqual(result_state["output"], "test message")

        # Original fields are NOT in result - only output field
        self.assertNotIn("other_field", result_state)
        self.assertEqual(len(result_state), 1)  # Only output field

        # Verify tracking methods were called on the execution tracking service
        self.mock_execution_tracking_service.record_node_start.assert_called_once()
        self.mock_execution_tracking_service.record_node_result.assert_called_once()


if __name__ == "__main__":
    unittest.main()
