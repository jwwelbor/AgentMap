"""
Unit tests for AnthropicAgent using pure Mock objects and established testing patterns.

This test suite validates the Anthropic agent's provider-specific configurations
and inheritance from LLMAgent while ensuring protocol compliance.
"""

import unittest
from unittest.mock import Mock

from agentmap.agents.builtins.llm.anthropic_agent import AnthropicAgent
from agentmap.agents.builtins.llm.llm_agent import LLMAgent
from agentmap.services.protocols import LLMCapableAgent, LLMServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory


class TestAnthropicAgent(unittest.TestCase):
    """Unit tests for AnthropicAgent using pure Mock objects."""

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
            "Mock Anthropic response for testing"
        )

        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()

        # Create basic context for testing
        self.test_context = {
            "input_fields": ["prompt", "context"],
            "output_field": "response",
            "description": "Test Anthropic agent",
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 0.5,
            "max_tokens": 2000,
        }

        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(AnthropicAgent)

    def create_anthropic_agent(self, context=None, **kwargs):
        """Helper to create Anthropic agent with common configuration."""
        if context is None:
            context = self.test_context.copy()
        elif isinstance(context, dict):
            full_context = self.test_context.copy()
            full_context.update(context)
            context = full_context

        return AnthropicAgent(
            name="test_anthropic_agent",
            prompt="You are Claude, an AI assistant created by Anthropic.",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            **kwargs,
        )

    # =============================================================================
    # 1. Inheritance and Protocol Compliance Tests
    # =============================================================================

    def test_anthropic_agent_inherits_from_llm_agent(self):
        """Test that AnthropicAgent properly inherits from LLMAgent."""
        agent = self.create_anthropic_agent()

        # Verify inheritance
        self.assertIsInstance(agent, LLMAgent)
        self.assertIsInstance(agent, AnthropicAgent)

        # Verify protocol implementation via inheritance
        self.assertTrue(isinstance(agent, LLMCapableAgent))

        # Verify inherited methods exist
        self.assertTrue(hasattr(agent, "configure_llm_service"))
        self.assertTrue(callable(agent.configure_llm_service))
        self.assertTrue(hasattr(agent, "process"))
        self.assertTrue(callable(agent.process))

    def test_anthropic_agent_protocol_compliance(self):
        """Test that AnthropicAgent correctly implements LLMCapableAgent protocol via inheritance."""
        agent = self.create_anthropic_agent()

        # Verify protocol implementation
        self.assertTrue(isinstance(agent, LLMCapableAgent))

        # Verify service configuration method exists and works
        self.assertTrue(hasattr(agent, "configure_llm_service"))
        self.assertTrue(callable(agent.configure_llm_service))

        # Test service configuration
        agent.configure_llm_service(self.mock_llm_service)

        # Verify service is now accessible
        self.assertEqual(agent.llm_service, self.mock_llm_service)

    # =============================================================================
    # 2. Anthropic-Specific Configuration Tests
    # =============================================================================

    def test_anthropic_agent_initialization_with_forced_provider(self):
        """Test that AnthropicAgent always forces provider to 'anthropic'."""
        # Test with no context
        agent1 = AnthropicAgent(
            name="test_agent1", prompt="Test prompt", logger=self.mock_logger
        )
        self.assertEqual(agent1.provider, "anthropic")

        # Test with empty context
        agent2 = AnthropicAgent(
            name="test_agent2",
            prompt="Test prompt",
            context={},
            logger=self.mock_logger,
        )
        self.assertEqual(agent2.provider, "anthropic")

        # Test with context that tries to override provider
        agent3 = AnthropicAgent(
            name="test_agent3",
            prompt="Test prompt",
            context={"provider": "openai"},  # Should be overridden
            logger=self.mock_logger,
        )
        self.assertEqual(agent3.provider, "anthropic")  # Should still be anthropic

    def test_anthropic_agent_initialization_with_default_model(self):
        """Test AnthropicAgent initialization with no model specified."""
        agent = AnthropicAgent(
            name="test_anthropic",
            prompt="Test prompt",
            context={},  # No model specified
            logger=self.mock_logger,
        )

        # When no model is specified, agent.model is None (LLMService provides default at call time)
        self.assertEqual(agent.provider, "anthropic")
        self.assertIsNone(
            agent.model
        )  # Default model is provided by LLMService at runtime
        self.assertEqual(agent.temperature, 0.7)  # Default temperature

    def test_anthropic_agent_initialization_with_custom_model(self):
        """Test AnthropicAgent initialization with custom Anthropic model."""
        context = {
            "model": "claude-3-opus-20240229",
            "temperature": 0.3,
            "max_tokens": 4000,
        }

        agent = self.create_anthropic_agent(context=context)

        # Should use specified model but keep anthropic provider
        self.assertEqual(agent.provider, "anthropic")
        self.assertEqual(agent.model, "claude-3-opus-20240229")
        self.assertEqual(agent.temperature, 0.3)
        self.assertEqual(agent.max_tokens, 4000)

    def test_anthropic_agent_initialization_with_anthropic_specific_models(self):
        """Test AnthropicAgent with various Anthropic model configurations."""
        anthropic_models = [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-instant-1.2",
        ]

        for model in anthropic_models:
            with self.subTest(model=model):
                context = {"model": model, "temperature": 0.4}
                agent = self.create_anthropic_agent(context=context)

                self.assertEqual(agent.provider, "anthropic")
                self.assertEqual(agent.model, model)
                self.assertEqual(agent.temperature, 0.4)

    def test_anthropic_agent_backward_compatibility_context_preservation(self):
        """Test that AnthropicAgent preserves other context fields while forcing provider."""
        context = {
            "input_fields": ["question", "background"],
            "output_field": "answer",
            "description": "Test Anthropic agent",
            "provider": "openai",  # Should be overridden
            "model": "claude-3-5-sonnet-20241022",
            "temperature": 0.6,
            "routing_enabled": False,
        }

        agent = self.create_anthropic_agent(context=context)

        # Verify provider was forced to anthropic
        self.assertEqual(agent.provider, "anthropic")

        # Verify other context fields were preserved
        self.assertEqual(
            agent.input_fields, ["question", "background", "memory"]
        )  # memory added by LLMAgent
        self.assertEqual(agent.output_field, "answer")
        self.assertEqual(agent.model, "claude-3-5-sonnet-20241022")
        self.assertEqual(agent.temperature, 0.6)
        self.assertFalse(agent.routing_enabled)

    # =============================================================================
    # 3. Integration Tests with Inherited Functionality
    # =============================================================================

    def test_anthropic_agent_process_integration(self):
        """Test AnthropicAgent process method integration via inheritance."""
        agent = self.create_anthropic_agent()
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {"prompt": "What are the key principles of AI safety?"}

        result = agent.process(inputs)

        # Verify LLM service was called via inherited process method
        self.mock_llm_service.call_llm.assert_called_once()
        call_args = self.mock_llm_service.call_llm.call_args

        # Verify call parameters include Anthropic provider
        kwargs = call_args.kwargs
        self.assertEqual(kwargs["provider"], "anthropic")
        self.assertEqual(kwargs["model"], "claude-3-5-sonnet-20241022")
        self.assertEqual(kwargs["temperature"], 0.5)
        self.assertEqual(kwargs["max_tokens"], 2000)

        # Verify messages structure
        messages = kwargs["messages"]
        self.assertIsInstance(messages, list)
        self.assertTrue(len(messages) >= 1)

        # Should have system message with agent prompt
        system_msg = messages[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertIn("Claude", system_msg["content"])
        self.assertIn("Anthropic", system_msg["content"])

        # Should have user message with input (single field = no prefix based on LLMAgent logic)
        user_msg = messages[1]
        self.assertEqual(user_msg["role"], "user")
        self.assertEqual(
            user_msg["content"], "What are the key principles of AI safety?"
        )

        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertEqual(result["output"], "Mock Anthropic response for testing")
        self.assertIn("memory", result)

    def test_anthropic_agent_process_with_multiple_inputs(self):
        """Test AnthropicAgent process with multiple inputs (should use prefixed format)."""
        agent = self.create_anthropic_agent()
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {
            "prompt": "Analyze this situation",
            "context": "A company is considering implementing AI safety measures",
        }

        result = agent.process(inputs)

        # Verify multiple inputs are formatted with prefixes (LLMAgent behavior)
        call_args = self.mock_llm_service.call_llm.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[1]

        expected_content = "prompt: Analyze this situation\ncontext: A company is considering implementing AI safety measures"
        self.assertEqual(user_msg["content"], expected_content)

        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertEqual(result["output"], "Mock Anthropic response for testing")

    def test_anthropic_agent_service_configuration_inheritance(self):
        """Test that AnthropicAgent inherits service configuration from LLMAgent."""
        agent = self.create_anthropic_agent()

        # Initially no LLM service (inherited behavior)
        with self.assertRaises(ValueError) as cm:
            _ = agent.llm_service
        self.assertIn("LLM service not configured", str(cm.exception))

        # Configure LLM service (inherited method)
        agent.configure_llm_service(self.mock_llm_service)

        # Now service should be accessible
        self.assertEqual(agent.llm_service, self.mock_llm_service)

        # Verify logging occurred (inherited logging behavior)
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        llm_configured = any(
            "LLM service configured" in call[1] for call in debug_calls
        )
        self.assertTrue(llm_configured, f"Expected LLM service log, got: {debug_calls}")

    def test_anthropic_agent_error_handling_inheritance(self):
        """Test that AnthropicAgent inherits error handling from LLMAgent."""
        agent = self.create_anthropic_agent()

        # Test without configured service (should raise ValueError via inheritance)
        inputs = {"prompt": "Test prompt"}

        with self.assertRaises(ValueError) as cm:
            agent.process(inputs)

        self.assertIn("LLM service not configured", str(cm.exception))

        # Test with service error (should return error dict via inheritance)
        agent.configure_llm_service(self.mock_llm_service)
        self.mock_llm_service.call_llm.side_effect = Exception("Anthropic API Error")

        result = agent.process(inputs)

        # Should return error result (inherited behavior)
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("Anthropic API Error", result["error"])
        self.assertFalse(result["last_action_success"])

    # =============================================================================
    # 4. Service Information Tests
    # =============================================================================

    def test_anthropic_agent_get_service_info(self):
        """Test service information retrieval for AnthropicAgent."""
        agent = self.create_anthropic_agent()
        agent.configure_llm_service(self.mock_llm_service)

        service_info = agent.get_service_info()

        # Verify basic agent information
        self.assertEqual(service_info["agent_name"], "test_anthropic_agent")
        self.assertEqual(service_info["agent_type"], "AnthropicAgent")

        # Verify service availability (inherited behavior)
        services = service_info["services"]
        self.assertTrue(services["logger_available"])
        self.assertTrue(services["execution_tracker_available"])
        self.assertTrue(services["state_adapter_available"])
        self.assertTrue(services["llm_service_configured"])
        self.assertFalse(services["storage_service_configured"])

        # Verify protocol implementation (inherited behavior)
        protocols = service_info["protocols"]
        self.assertTrue(protocols["implements_llm_capable"])
        self.assertFalse(protocols["implements_storage_capable"])

        # Verify configuration shows Anthropic-specific settings
        config = service_info["configuration"]
        self.assertEqual(config["input_fields"], ["prompt", "context", "memory"])
        self.assertEqual(config["output_field"], "response")
        self.assertEqual(config["description"], "Test Anthropic agent")

        # Verify LLM configuration shows Anthropic provider
        if "llm_configuration" in service_info:
            llm_config = service_info["llm_configuration"]
            self.assertEqual(llm_config["provider_name"], "anthropic")
            self.assertEqual(llm_config["model"], "claude-3-5-sonnet-20241022")

    def test_anthropic_agent_get_service_info_without_llm_service(self):
        """Test service information when LLM service is not configured."""
        agent = self.create_anthropic_agent()

        service_info = agent.get_service_info()

        # Verify service configuration reflects no LLM service
        services = service_info["services"]
        self.assertFalse(services["llm_service_configured"])

        # But should still show Anthropic provider in config
        if "llm_configuration" in service_info:
            llm_config = service_info["llm_configuration"]
            self.assertEqual(llm_config["provider_name"], "anthropic")

    # =============================================================================
    # 5. Integration Tests with Run Method
    # =============================================================================

    def test_anthropic_agent_run_method_integration(self):
        """Test the inherited run method works with AnthropicAgent."""
        agent = self.create_anthropic_agent()
        agent.configure_llm_service(self.mock_llm_service)

        # CRITICAL: Set execution tracker on agent (required by new architecture)
        agent.set_execution_tracker(self.mock_tracker)

        # Configure state adapter behavior
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs

        # The execution tracking service methods are already configured by MockServiceFactory

        # Test state
        test_state = {
            "prompt": "What is constitutional AI?",
            "context": "Anthropic's approach to AI alignment",
            "other_field": "preserved",
        }

        # Execute run method
        result_state = agent.run(test_state)

        # Verify LLM was called with Anthropic provider
        self.mock_llm_service.call_llm.assert_called_once()
        call_args = self.mock_llm_service.call_llm.call_args
        self.assertEqual(call_args.kwargs["provider"], "anthropic")

        # NEW BEHAVIOR: Returns partial state update (output field + memory)
        self.assertIn("response", result_state)
        self.assertEqual(
            result_state["response"], "Mock Anthropic response for testing"
        )

        # Original fields are NOT in result - only output field and memory
        self.assertNotIn("other_field", result_state)
        # LLMAgent returns both output field and memory field via state_updates pattern
        self.assertIn("memory", result_state)
        self.assertEqual(len(result_state), 2)  # Output field + memory field

        # Verify tracking calls (inherited behavior via execution tracking service)
        self.mock_execution_tracking_service.record_node_start.assert_called_once()
        self.mock_execution_tracking_service.record_node_result.assert_called_once()

    # =============================================================================
    # 6. Anthropic-Specific Edge Cases
    # =============================================================================

    def test_anthropic_agent_with_routing_disabled(self):
        """Test AnthropicAgent with routing explicitly disabled (legacy mode)."""
        context = {
            "routing_enabled": False,
            "provider": "openai",  # Should be overridden
            "model": "claude-3-5-sonnet-20241022",
        }

        agent = self.create_anthropic_agent(context=context)

        # Should force Anthropic provider regardless of routing settings
        self.assertEqual(agent.provider, "anthropic")
        self.assertFalse(agent.routing_enabled)
        self.assertEqual(agent.model, "claude-3-5-sonnet-20241022")

    def test_anthropic_agent_minimal_initialization(self):
        """Test AnthropicAgent with minimal configuration."""
        minimal_agent = AnthropicAgent(
            name="minimal_anthropic", prompt="I am Claude.", logger=self.mock_logger
        )

        # Should have Anthropic defaults
        self.assertEqual(minimal_agent.name, "minimal_anthropic")
        self.assertEqual(minimal_agent.prompt, "I am Claude.")
        self.assertEqual(minimal_agent.provider, "anthropic")
        self.assertIsNone(
            minimal_agent.model
        )  # Default model provided by LLMService at runtime
        self.assertEqual(minimal_agent.temperature, 0.7)
        self.assertIsNone(minimal_agent.max_tokens)

    def test_anthropic_agent_context_override_behavior(self):
        """Test how AnthropicAgent handles context field overrides."""
        original_context = {
            "provider": "openai",  # Should be overridden
            "model": "gpt-4",  # Should be preserved
            "temperature": 0.8,  # Should be preserved
            "custom_field": "preserved",  # Should be preserved
        }

        agent = AnthropicAgent(
            name="test_override",
            prompt="Test",
            context=original_context,
            logger=self.mock_logger,
        )

        # Verify provider override but other fields preserved
        self.assertEqual(agent.provider, "anthropic")
        self.assertEqual(agent.model, "gpt-4")  # Non-Anthropic model preserved
        self.assertEqual(agent.temperature, 0.8)
        self.assertEqual(agent.context.get("custom_field"), "preserved")

    # =============================================================================
    # 7. Logging Integration Tests
    # =============================================================================

    def test_anthropic_agent_logging_integration(self):
        """Test that AnthropicAgent properly logs operations via inheritance."""
        agent = self.create_anthropic_agent()
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {"prompt": "Explain constitutional AI"}

        # Execute process to generate log calls
        agent.process(inputs)

        # Verify logger was called (inherited behavior)
        logger_calls = self.mock_logger.calls

        # Should have info calls for processing (inherited from LLMAgent)
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(len(info_calls) > 0)

        # Verify relevant information is logged
        log_messages = [call[1] for call in info_calls]
        prompt_logged = any("Explain constitutional AI" in msg for msg in log_messages)
        self.assertTrue(prompt_logged, f"Expected prompt logged, got: {log_messages}")

    def test_anthropic_agent_debug_logging_provider_info(self):
        """Test that AnthropicAgent logs provider-specific debug information."""
        agent = self.create_anthropic_agent()
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {"prompt": "Test prompt"}
        agent.process(inputs)

        # Check for provider-specific debug logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        debug_messages = [call[1] for call in debug_calls]

        # Should have debug info about using anthropic provider
        provider_logged = any("anthropic" in msg.lower() for msg in debug_messages)
        self.assertTrue(
            provider_logged,
            f"Expected Anthropic provider logged, got: {debug_messages}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
