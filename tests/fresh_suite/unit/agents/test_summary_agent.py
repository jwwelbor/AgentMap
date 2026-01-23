"""
Unit tests for SummaryAgent using pure Mock objects and established testing patterns.

This test suite validates the summary agent's dual-mode operation (LLM vs basic),
prompt resolution capabilities, and flexible input handling.
"""

import unittest
from typing import Any, Dict
from unittest.mock import Mock

from agentmap.agents.builtins.summary_agent import SummaryAgent
from agentmap.services.protocols import LLMCapableAgent, LLMServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory


class TestSummaryAgent(unittest.TestCase):
    """Unit tests for SummaryAgent using pure Mock objects."""

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

        # Create LLM service mock
        self.mock_llm_service = Mock(spec=LLMServiceProtocol)
        self.mock_llm_service.call_llm.return_value = (
            "LLM-generated summary of the content"
        )

        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()

        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(SummaryAgent)

    def create_summary_agent(self, use_llm=False, **context_overrides):
        """Helper to create summary agent with common configuration."""
        context = {
            "input_fields": ["content1", "content2", "content3"],
            "output_field": "summary",
            "description": "Test summary agent",
            "format": "{key}: {value}",
            "separator": "\n\n",
            "include_keys": True,
            **context_overrides,
        }

        if use_llm:
            context["llm"] = "openai"
            context["model"] = "gpt-4"
            context["temperature"] = 0.3

        agent = SummaryAgent(
            name="test_summary",
            prompt="Please summarize the following information concisely",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,  # Service, not tracker
            state_adapter_service=self.mock_state_adapter_service,
        )

        # Set the execution tracker instance on the agent
        agent.set_execution_tracker(self.mock_tracker)

        return agent

    # =============================================================================
    # 1. Agent Initialization and Mode Detection Tests
    # =============================================================================

    def test_agent_initialization_basic_mode(self):
        """Test summary agent initialization in basic concatenation mode."""
        agent = self.create_summary_agent(use_llm=False)

        # Verify basic configuration
        self.assertEqual(agent.name, "test_summary")
        self.assertEqual(
            agent.prompt, "Please summarize the following information concisely"
        )
        self.assertFalse(agent.use_llm)
        self.assertIsNone(agent.llm_type)

        # Verify formatting configuration
        self.assertEqual(agent.format_template, "{key}: {value}")
        self.assertEqual(agent.separator, "\n\n")
        self.assertTrue(agent.include_keys)

        # Verify infrastructure services
        self.assertIsNotNone(agent.logger)
        self.assertIsNotNone(agent.execution_tracking_service)
        self.assertIsNotNone(agent.state_adapter_service)

    def test_agent_initialization_llm_mode(self):
        """Test summary agent initialization in LLM mode."""
        agent = self.create_summary_agent(use_llm=True)

        # Verify LLM configuration
        self.assertTrue(agent.use_llm)
        self.assertEqual(agent.llm_type, "openai")

        # Verify protocol implementation
        self.assertTrue(isinstance(agent, LLMCapableAgent))

        # LLM service should not be configured by default
        with self.assertRaises(ValueError):
            _ = agent.llm_service

    def test_agent_initialization_with_minimal_context(self):
        """Test summary agent with minimal configuration."""
        # Even minimal tests need required infrastructure dependencies
        minimal_agent = SummaryAgent(
            name="minimal_summary",
            prompt="Summarize this",
            logger=self.mock_logger,  # Required dependency
        )

        # Verify defaults
        self.assertEqual(minimal_agent.name, "minimal_summary")
        self.assertFalse(minimal_agent.use_llm)  # Default to basic mode
        self.assertEqual(minimal_agent.format_template, "{key}: {value}")
        self.assertEqual(minimal_agent.separator, "\n\n")
        self.assertTrue(minimal_agent.include_keys)

    def test_agent_initialization_with_llm_mode_but_no_service_configured(self):
        """Test agent initialization in LLM mode without service configured."""
        # Create agent with LLM mode enabled
        agent = self.create_summary_agent(use_llm=True)

        # Agent should be in LLM mode
        self.assertTrue(agent.use_llm)
        self.assertEqual(agent.llm_type, "openai")

        # But should raise error when trying to access LLM service
        with self.assertRaises(ValueError) as cm:
            _ = agent.llm_service
        self.assertIn("LLM service not configured", str(cm.exception))

        # Should log initialization in LLM mode
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        llm_mode_logged = any("using LLM mode" in call[1] for call in debug_calls)
        self.assertTrue(
            llm_mode_logged, f"Expected LLM mode logged, got: {debug_calls}"
        )

    # =============================================================================
    # 2. Service Configuration Tests
    # =============================================================================

    def test_llm_service_configuration(self):
        """Test LLM service configuration for LLM mode."""
        agent = self.create_summary_agent(use_llm=True)

        # Initially no LLM service
        with self.assertRaises(ValueError) as cm:
            _ = agent.llm_service
        self.assertIn("LLM service not configured", str(cm.exception))

        # Configure LLM service
        agent.configure_llm_service(self.mock_llm_service)

        # Now service should be accessible
        self.assertEqual(agent.llm_service, self.mock_llm_service)

        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        llm_configured = any(
            "LLM service configured" in call[1] for call in debug_calls
        )
        self.assertTrue(llm_configured, f"Expected LLM service log, got: {debug_calls}")

    def test_llm_service_not_required_for_basic_mode(self):
        """Test that basic mode doesn't require LLM service."""
        agent = self.create_summary_agent(use_llm=False)

        # Should be able to process without LLM service
        inputs = {
            "content1": "First piece of information",
            "content2": "Second piece of information",
        }

        result = agent.process(inputs)
        self.assertIsNotNone(result)
        self.assertIn("First piece", result)
        self.assertIn("Second piece", result)

    # =============================================================================
    # 3. Basic Concatenation Mode Tests
    # =============================================================================

    def test_basic_concatenation_with_default_formatting(self):
        """Test basic concatenation with default key-value formatting."""
        agent = self.create_summary_agent(use_llm=False)

        inputs = {
            "content1": "User completed registration",
            "content2": "Payment processed successfully",
            "content3": "Welcome email sent",
        }

        result = agent.process(inputs)

        # Should format with keys
        self.assertIn("content1: User completed registration", result)
        self.assertIn("content2: Payment processed successfully", result)
        self.assertIn("content3: Welcome email sent", result)

        # Should use separator
        self.assertIn("\n\n", result)

    def test_basic_concatenation_without_keys(self):
        """Test basic concatenation without including keys."""
        agent = self.create_summary_agent(use_llm=False, include_keys=False)

        inputs = {"content1": "First item", "content2": "Second item"}

        result = agent.process(inputs)

        # Should not include keys
        self.assertNotIn("content1:", result)
        self.assertNotIn("content2:", result)

        # Should include values
        self.assertIn("First item", result)
        self.assertIn("Second item", result)

    def test_basic_concatenation_with_custom_formatting(self):
        """Test basic concatenation with custom format template and separator."""
        agent = self.create_summary_agent(
            use_llm=False, format="- {key}: {value}", separator=" | ", include_keys=True
        )

        inputs = {"item1": "Value one", "item2": "Value two"}

        result = agent.process(inputs)

        # Should use custom format
        self.assertIn("- item1: Value one", result)
        self.assertIn("- item2: Value two", result)

        # Should use custom separator
        self.assertIn(" | ", result)

    def test_basic_concatenation_with_none_values(self):
        """Test basic concatenation skips None values."""
        agent = self.create_summary_agent(use_llm=False)

        inputs = {
            "content1": "Valid content",
            "content2": None,
            "content3": "More valid content",
        }

        result = agent.process(inputs)

        # Should include valid content
        self.assertIn("Valid content", result)
        self.assertIn("More valid content", result)

        # Should not include None value
        self.assertNotIn("content2", result)
        self.assertNotIn("None", result)

    def test_basic_concatenation_with_empty_inputs(self):
        """Test basic concatenation with empty inputs."""
        agent = self.create_summary_agent(use_llm=False)

        inputs = {}

        result = agent.process(inputs)

        # Should return empty string
        self.assertEqual(result, "")

    def test_basic_concatenation_with_complex_data_types(self):
        """Test basic concatenation with complex data types."""
        agent = self.create_summary_agent(use_llm=False)

        inputs = {
            "list_data": [1, 2, 3],
            "dict_data": {"nested": "value"},
            "string_data": "simple text",
        }

        result = agent.process(inputs)

        # Should convert complex types to strings
        self.assertIn("[1, 2, 3]", result)
        self.assertIn("nested", result)
        self.assertIn("simple text", result)

    def test_basic_concatenation_with_formatting_error(self):
        """Test basic concatenation handles formatting errors gracefully."""
        agent = self.create_summary_agent(
            use_llm=False, format="{invalid_placeholder}"  # Invalid format template
        )

        inputs = {"content": "test value"}

        result = agent.process(inputs)

        # Should fall back to simple key: value format
        self.assertIn("content: test value", result)

        # Should log warning about formatting error
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]
        self.assertTrue(any("Error formatting" in call[1] for call in warning_calls))

    # =============================================================================
    # 4. LLM Mode Tests
    # =============================================================================

    def test_llm_mode_with_service_configured(self):
        """Test LLM mode with properly configured service."""
        agent = self.create_summary_agent(use_llm=True)
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {
            "content1": "User registered successfully",
            "content2": "Payment of $99.99 processed",
            "content3": "Confirmation email sent to user@example.com",
        }

        result = agent.process(inputs)

        # Verify LLM service was called
        self.mock_llm_service.call_llm.assert_called_once()
        call_args = self.mock_llm_service.call_llm.call_args

        # Verify call parameters
        kwargs = call_args.kwargs
        self.assertEqual(kwargs["provider"], "openai")
        self.assertEqual(kwargs["model"], "gpt-4")
        self.assertEqual(kwargs["temperature"], 0.3)

        # Verify messages structure
        messages = kwargs["messages"]
        self.assertTrue(len(messages) >= 2)

        # Check system message contains agent prompt
        system_msg = messages[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertIn("summarize the following information", system_msg["content"])

        # Check user message contains concatenated content
        user_msg = messages[1]
        self.assertEqual(user_msg["role"], "user")
        self.assertIn("User registered", user_msg["content"])
        self.assertIn("Payment of $99.99", user_msg["content"])
        self.assertIn("Confirmation email", user_msg["content"])

        # Verify result is from LLM
        self.assertEqual(result, "LLM-generated summary of the content")

    def test_llm_mode_without_service_configured(self):
        """Test LLM mode fails when service not configured."""
        agent = self.create_summary_agent(use_llm=True)

        inputs = {"content": "test content"}

        with self.assertRaises(ValueError) as cm:
            agent.process(inputs)

        self.assertIn("LLM service not configured", str(cm.exception))

    def test_llm_mode_with_llm_service_error(self):
        """Test LLM mode handles LLM service errors with fallback."""
        agent = self.create_summary_agent(use_llm=True)

        # Configure LLM service to raise an error
        self.mock_llm_service.call_llm.side_effect = Exception("LLM API Error")
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {"content1": "First content", "content2": "Second content"}

        result = agent.process(inputs)

        # Should fall back to basic concatenation
        self.assertIn("ERROR in summarization", result)
        self.assertIn("LLM API Error", result)
        self.assertIn("First content", result)  # Original content included
        self.assertIn("Second content", result)

        # Should log error
        logger_calls = self.mock_logger.calls
        error_calls = [call for call in logger_calls if call[0] == "error"]
        self.assertTrue(
            any("Error in LLM summarization" in call[1] for call in error_calls)
        )

    # =============================================================================
    # 5. Prompt Resolution Tests (PromptResolutionMixin)
    # =============================================================================

    def test_prompt_resolution_with_template_variables(self):
        """Test prompt resolution using PromptManagerService."""
        agent = self.create_summary_agent(use_llm=True)
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {"content1": "Data point one", "content2": "Data point two"}

        # Call process to trigger prompt resolution
        agent.process(inputs)

        # Verify LLM was called with resolved prompt
        call_args = self.mock_llm_service.call_llm.call_args
        messages = call_args.kwargs["messages"]
        system_msg = messages[0]

        # System message should contain resolved prompt
        self.assertIn("summarize the following information", system_msg["content"])

        # User message should contain the concatenated content
        user_msg = messages[1]
        self.assertIn("Data point one", user_msg["content"])
        self.assertIn("Data point two", user_msg["content"])

    # =============================================================================
    # 6. Integration Tests
    # =============================================================================

    def test_run_method_integration_basic_mode(self):
        """Test the inherited run method works with basic mode."""
        agent = self.create_summary_agent(use_llm=False)

        # Configure state adapter behavior
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs

        # Note: BaseAgent calls the service methods, not the tracker methods directly

        # Test state
        test_state = {
            "content1": "First piece of info",
            "content2": "Second piece of info",
            "other_field": "preserved",
        }

        # Execute run method
        result_state = agent.run(test_state)

        # Verify state was updated with summary
        self.assertIn("summary", result_state)
        summary = result_state["summary"]
        self.assertIn("First piece", summary)
        self.assertIn("Second piece", summary)

        # Original fields are NOT in result - only output field
        self.assertNotIn("other_field", result_state)
        self.assertEqual(len(result_state), 1)  # Only output field

        # Verify tracking service methods were called
        self.mock_execution_tracking_service.record_node_start.assert_called_once()
        self.mock_execution_tracking_service.record_node_result.assert_called_once()

    def test_run_method_integration_llm_mode(self):
        """Test the inherited run method works with LLM mode."""
        agent = self.create_summary_agent(use_llm=True)
        agent.configure_llm_service(self.mock_llm_service)

        # Configure state adapter and tracker (same setup as above)
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        # Note: BaseAgent calls the service methods, not the tracker methods directly

        test_state = {
            "content1": "User activity log",
            "content2": "System performance metrics",
            "content3": "Error reports",
        }

        result_state = agent.run(test_state)

        # Verify LLM was called
        self.mock_llm_service.call_llm.assert_called_once()

        # Verify state was updated with LLM summary
        self.assertIn("summary", result_state)
        self.assertEqual(
            result_state["summary"], "LLM-generated summary of the content"
        )

    # =============================================================================
    # 7. Service Information and Logging Tests
    # =============================================================================

    def test_get_service_info_basic_mode(self):
        """Test service information for basic mode."""
        agent = self.create_summary_agent(use_llm=False)

        service_info = agent.get_service_info()

        # Verify basic agent information
        self.assertEqual(service_info["agent_name"], "test_summary")
        self.assertEqual(service_info["agent_type"], "SummaryAgent")

        # Verify service configuration for basic mode
        services = service_info["services"]
        self.assertFalse(services["llm_service_configured"])

        # Still implements protocol even if not using LLM
        protocols = service_info["protocols"]
        self.assertTrue(protocols["implements_llm_capable"])

    def test_get_service_info_llm_mode(self):
        """Test service information for LLM mode."""
        agent = self.create_summary_agent(use_llm=True)
        agent.configure_llm_service(self.mock_llm_service)

        service_info = agent.get_service_info()

        # Verify service configuration for LLM mode
        services = service_info["services"]
        self.assertTrue(services["llm_service_configured"])

    def test_logging_integration_basic_mode(self):
        """Test logging for basic concatenation mode."""
        agent = self.create_summary_agent(use_llm=False)

        inputs = {"content1": "test content", "content2": "more content"}
        agent.process(inputs)

        # Verify mode is logged
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        basic_mode_logged = any(
            "using basic concatenation mode" in call[1] for call in debug_calls
        )
        self.assertTrue(
            basic_mode_logged, f"Expected basic mode logged, got: {debug_calls}"
        )

    def test_logging_integration_llm_mode(self):
        """Test logging for LLM mode."""
        agent = self.create_summary_agent(use_llm=True)
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {"content1": "test content"}
        agent.process(inputs)

        # Verify LLM mode is logged
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        llm_mode_logged = any("using LLM mode" in call[1] for call in debug_calls)
        self.assertTrue(
            llm_mode_logged, f"Expected LLM mode logged, got: {debug_calls}"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
