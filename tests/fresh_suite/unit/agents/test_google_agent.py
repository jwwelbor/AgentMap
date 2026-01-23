"""
Unit tests for GoogleAgent using pure Mock objects and established testing patterns.

This test suite validates the Google/Gemini agent's provider-specific configurations
and inheritance from LLMAgent while ensuring protocol compliance.
"""

import unittest
from typing import Any, Dict
from unittest.mock import Mock

from agentmap.agents.builtins.llm.google_agent import GoogleAgent
from agentmap.agents.builtins.llm.llm_agent import LLMAgent
from agentmap.services.protocols import LLMCapableAgent, LLMServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory


class TestGoogleAgent(unittest.TestCase):
    """Unit tests for GoogleAgent using pure Mock objects."""

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
            "Mock Google/Gemini response for testing"
        )

        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()

        # Create basic context for testing
        self.test_context = {
            "input_fields": ["prompt", "context"],
            "output_field": "response",
            "description": "Test Google agent",
            "model": "gemini-1.0-pro",
            "temperature": 0.3,
            "max_tokens": 1500,
        }

        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(GoogleAgent)

    def create_google_agent(self, context=None, **kwargs):
        """Helper to create Google agent with common configuration."""
        if context is None:
            context = self.test_context.copy()
        elif isinstance(context, dict):
            full_context = self.test_context.copy()
            full_context.update(context)
            context = full_context

        return GoogleAgent(
            name="test_google_agent",
            prompt="You are Gemini, a helpful AI assistant created by Google.",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            **kwargs,
        )

    # =============================================================================
    # 1. Inheritance and Protocol Compliance Tests
    # =============================================================================

    def test_google_agent_inherits_from_llm_agent(self):
        """Test that GoogleAgent properly inherits from LLMAgent."""
        agent = self.create_google_agent()

        # Verify inheritance
        self.assertIsInstance(agent, LLMAgent)
        self.assertIsInstance(agent, GoogleAgent)

        # Verify protocol implementation via inheritance
        self.assertTrue(isinstance(agent, LLMCapableAgent))

        # Verify inherited methods exist
        self.assertTrue(hasattr(agent, "configure_llm_service"))
        self.assertTrue(callable(agent.configure_llm_service))
        self.assertTrue(hasattr(agent, "process"))
        self.assertTrue(callable(agent.process))

    def test_google_agent_protocol_compliance(self):
        """Test that GoogleAgent correctly implements LLMCapableAgent protocol via inheritance."""
        agent = self.create_google_agent()

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
    # 2. Google-Specific Configuration Tests
    # =============================================================================

    def test_google_agent_initialization_with_forced_provider(self):
        """Test that GoogleAgent always forces provider to 'google'."""
        # Test with no context
        agent1 = GoogleAgent(
            name="test_agent1", prompt="Test prompt", logger=self.mock_logger
        )
        self.assertEqual(agent1.provider, "google")

        # Test with empty context
        agent2 = GoogleAgent(
            name="test_agent2",
            prompt="Test prompt",
            context={},
            logger=self.mock_logger,
        )
        self.assertEqual(agent2.provider, "google")

        # Test with context that tries to override provider
        agent3 = GoogleAgent(
            name="test_agent3",
            prompt="Test prompt",
            context={"provider": "anthropic"},  # Should be overridden
            logger=self.mock_logger,
        )
        self.assertEqual(agent3.provider, "google")  # Should still be google

    def test_google_agent_initialization_with_default_model(self):
        """Test GoogleAgent initialization with no model specified."""
        agent = GoogleAgent(
            name="test_google",
            prompt="Test prompt",
            context={},  # No model specified
            logger=self.mock_logger,
        )

        # When no model is specified, agent.model is None (LLMService provides default at call time)
        self.assertEqual(agent.provider, "google")
        self.assertIsNone(
            agent.model
        )  # Default model is provided by LLMService at runtime
        self.assertEqual(agent.temperature, 0.7)  # Default temperature

    def test_google_agent_initialization_with_custom_gemini_model(self):
        """Test GoogleAgent initialization with custom Gemini model."""
        context = {"model": "gemini-pro", "temperature": 0.1, "max_tokens": 2048}

        agent = self.create_google_agent(context=context)

        # Should use specified model but keep google provider
        self.assertEqual(agent.provider, "google")
        self.assertEqual(agent.model, "gemini-pro")
        self.assertEqual(agent.temperature, 0.1)
        self.assertEqual(agent.max_tokens, 2048)

    def test_google_agent_initialization_with_gemini_model_variants(self):
        """Test GoogleAgent with various Gemini model configurations."""
        gemini_models = [
            "gemini-1.0-pro",
            "gemini-pro",
            "gemini-pro-vision",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]

        for model in gemini_models:
            with self.subTest(model=model):
                context = {"model": model, "temperature": 0.2}
                agent = self.create_google_agent(context=context)

                self.assertEqual(agent.provider, "google")
                self.assertEqual(agent.model, model)
                self.assertEqual(agent.temperature, 0.2)

    def test_google_agent_backward_compatibility_context_preservation(self):
        """Test that GoogleAgent preserves other context fields while forcing provider."""
        context = {
            "provider": "openai",  # Should be overridden
            "model": "gemini-pro",  # Should be preserved
            "temperature": 0.9,  # Should be preserved
            "routing_enabled": True,  # Should be preserved
            "custom_field": "preserved",  # Should be preserved
        }

        agent = self.create_google_agent(context=context)

        # Verify provider was forced to google
        self.assertEqual(agent.provider, "google")

        # Verify other context fields were preserved
        self.assertEqual(
            agent.input_fields, ["prompt", "context", "memory"]
        )  # memory added by LLMAgent
        self.assertEqual(agent.output_field, "response")
        self.assertEqual(agent.model, "gemini-pro")
        self.assertEqual(agent.temperature, 0.9)
        self.assertTrue(agent.routing_enabled)
        self.assertEqual(agent.context.get("custom_field"), "preserved")

    # =============================================================================
    # 3. Integration Tests with Inherited Functionality
    # =============================================================================

    def test_google_agent_process_integration(self):
        """Test GoogleAgent process method integration via inheritance."""
        agent = self.create_google_agent()
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {"prompt": "What are the latest advances in AI research?"}

        result = agent.process(inputs)

        # Verify LLM service was called via inherited process method
        self.mock_llm_service.call_llm.assert_called_once()
        call_args = self.mock_llm_service.call_llm.call_args

        # Verify call parameters include Google provider
        kwargs = call_args.kwargs
        self.assertEqual(kwargs["provider"], "google")
        self.assertEqual(kwargs["model"], "gemini-1.0-pro")
        self.assertEqual(kwargs["temperature"], 0.3)
        self.assertEqual(kwargs["max_tokens"], 1500)

        # Verify messages structure
        messages = kwargs["messages"]
        self.assertIsInstance(messages, list)
        self.assertTrue(len(messages) >= 1)

        # Should have system message with agent prompt
        system_msg = messages[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertIn("Gemini", system_msg["content"])
        self.assertIn("Google", system_msg["content"])

        # Should have user message with input (single field = no prefix based on LLMAgent logic)
        user_msg = messages[1]
        self.assertEqual(user_msg["role"], "user")
        self.assertEqual(
            user_msg["content"], "What are the latest advances in AI research?"
        )

        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertEqual(result["output"], "Mock Google/Gemini response for testing")
        self.assertIn("memory", result)

    def test_google_agent_process_with_multiple_inputs(self):
        """Test GoogleAgent process with multiple inputs (should use prefixed format)."""
        agent = self.create_google_agent()
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {
            "prompt": "Summarize this research",
            "context": "Recent breakthroughs in quantum computing and AI alignment",
        }

        result = agent.process(inputs)

        # Verify multiple inputs are formatted with prefixes (LLMAgent behavior)
        call_args = self.mock_llm_service.call_llm.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[1]

        expected_content = "prompt: Summarize this research\ncontext: Recent breakthroughs in quantum computing and AI alignment"
        self.assertEqual(user_msg["content"], expected_content)

        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertEqual(result["output"], "Mock Google/Gemini response for testing")

    def test_google_agent_service_configuration_inheritance(self):
        """Test that GoogleAgent inherits service configuration from LLMAgent."""
        agent = self.create_google_agent()

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

    def test_google_agent_error_handling_inheritance(self):
        """Test that GoogleAgent inherits error handling from LLMAgent."""
        agent = self.create_google_agent()

        # Test without configured service (should raise ValueError via inheritance)
        inputs = {"prompt": "Test prompt"}

        with self.assertRaises(ValueError) as cm:
            agent.process(inputs)

        self.assertIn("LLM service not configured", str(cm.exception))

        # Test with service error (should return error dict via inheritance)
        agent.configure_llm_service(self.mock_llm_service)
        self.mock_llm_service.call_llm.side_effect = Exception("Google API Error")

        result = agent.process(inputs)

        # Should return error result (inherited behavior)
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("Google API Error", result["error"])
        self.assertFalse(result["last_action_success"])

    # =============================================================================
    # 4. Service Information Tests
    # =============================================================================

    def test_google_agent_get_service_info(self):
        """Test service information retrieval for GoogleAgent."""
        agent = self.create_google_agent()
        agent.configure_llm_service(self.mock_llm_service)

        service_info = agent.get_service_info()

        # Verify basic agent information
        self.assertEqual(service_info["agent_name"], "test_google_agent")
        self.assertEqual(service_info["agent_type"], "GoogleAgent")

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

        # Verify configuration shows Google-specific settings
        config = service_info["configuration"]
        self.assertEqual(config["input_fields"], ["prompt", "context", "memory"])
        self.assertEqual(config["output_field"], "response")
        self.assertEqual(config["description"], "Test Google agent")

        # Verify LLM configuration shows Google provider
        if "llm_configuration" in service_info:
            llm_config = service_info["llm_configuration"]
            self.assertEqual(llm_config["provider_name"], "google")
            self.assertEqual(llm_config["model"], "gemini-1.0-pro")

    def test_google_agent_get_service_info_without_llm_service(self):
        """Test service information when LLM service is not configured."""
        agent = self.create_google_agent()

        service_info = agent.get_service_info()

        # Verify service configuration reflects no LLM service
        services = service_info["services"]
        self.assertFalse(services["llm_service_configured"])

        # But should still show Google provider in config
        if "llm_configuration" in service_info:
            llm_config = service_info["llm_configuration"]
            self.assertEqual(llm_config["provider_name"], "google")

    # =============================================================================
    # 5. Integration Tests with Run Method
    # =============================================================================

    def test_google_agent_run_method_integration(self):
        """Test the inherited run method works with GoogleAgent."""
        agent = self.create_google_agent()
        agent.configure_llm_service(self.mock_llm_service)

        # Configure state adapter behavior
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}

        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs

        # CRITICAL: Set execution tracker on agent (required by new architecture)
        agent.set_execution_tracker(self.mock_tracker)

        # The execution tracking service methods are already configured by MockServiceFactory

        # Test state
        test_state = {
            "prompt": "What is multimodal AI?",
            "context": "Google's approach to combining text, image, and audio processing",
            "other_field": "preserved",
        }

        # Execute run method
        result_state = agent.run(test_state)

        # Verify LLM was called with Google provider
        self.mock_llm_service.call_llm.assert_called_once()
        call_args = self.mock_llm_service.call_llm.call_args
        self.assertEqual(call_args.kwargs["provider"], "google")

        # Verify state was updated with response
        self.assertIn("response", result_state)
        self.assertEqual(
            result_state["response"], "Mock Google/Gemini response for testing"
        )

        # Original fields are NOT in result - only output field
        self.assertNotIn("other_field", result_state)
        self.assertEqual(len(result_state), 1)  # Only output field

        # Verify tracking calls (inherited behavior via execution tracking service)
        self.mock_execution_tracking_service.record_node_start.assert_called_once()
        self.mock_execution_tracking_service.record_node_result.assert_called_once()

    # =============================================================================
    # 6. Google-Specific Edge Cases
    # =============================================================================

    def test_google_agent_with_routing_enabled(self):
        """Test GoogleAgent with routing enabled (should still force Google provider)."""
        context = {
            "routing_enabled": True,
            "provider": "anthropic",  # Should be overridden
            "model": "gemini-pro",
        }

        agent = self.create_google_agent(context=context)

        # Should force Google provider regardless of routing settings
        self.assertEqual(agent.provider, "google")
        self.assertTrue(agent.routing_enabled)
        self.assertEqual(agent.model, "gemini-pro")

    def test_google_agent_minimal_initialization(self):
        """Test GoogleAgent with minimal configuration."""
        minimal_agent = GoogleAgent(
            name="minimal_google", prompt="I am Gemini.", logger=self.mock_logger
        )

        # Should have Google defaults
        self.assertEqual(minimal_agent.name, "minimal_google")
        self.assertEqual(minimal_agent.prompt, "I am Gemini.")
        self.assertEqual(minimal_agent.provider, "google")
        self.assertIsNone(
            minimal_agent.model
        )  # Default model provided by LLMService at runtime
        self.assertEqual(minimal_agent.temperature, 0.7)
        self.assertIsNone(minimal_agent.max_tokens)

    def test_google_agent_context_override_behavior(self):
        """Test how GoogleAgent handles context field overrides."""
        original_context = {
            "provider": "anthropic",  # Should be overridden
            "model": "claude-3-5-sonnet-20241022",  # Should be preserved
            "temperature": 0.1,  # Should be preserved
            "custom_field": "preserved",  # Should be preserved
            "routing_enabled": False,
        }

        agent = GoogleAgent(
            name="test_override",
            prompt="Test",
            context=original_context,
            logger=self.mock_logger,
        )

        # Verify provider override but other fields preserved
        self.assertEqual(agent.provider, "google")
        self.assertEqual(
            agent.model, "claude-3-5-sonnet-20241022"
        )  # Non-Google model preserved
        self.assertEqual(agent.temperature, 0.1)
        self.assertEqual(agent.context.get("custom_field"), "preserved")
        self.assertFalse(agent.routing_enabled)

    def test_google_agent_with_vision_model(self):
        """Test GoogleAgent with Gemini vision model configuration."""
        context = {"model": "gemini-pro-vision", "temperature": 0.0, "max_tokens": 1024}

        agent = self.create_google_agent(context=context)

        # Should properly configure vision model
        self.assertEqual(agent.provider, "google")
        self.assertEqual(agent.model, "gemini-pro-vision")
        self.assertEqual(agent.temperature, 0.0)
        self.assertEqual(agent.max_tokens, 1024)

    # =============================================================================
    # 7. Logging Integration Tests
    # =============================================================================

    def test_google_agent_logging_integration(self):
        """Test that GoogleAgent properly logs operations via inheritance."""
        agent = self.create_google_agent()
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {"prompt": "Explain Gemini's multimodal capabilities"}

        # Execute process to generate log calls
        agent.process(inputs)

        # Verify logger was called (inherited behavior)
        logger_calls = self.mock_logger.calls

        # Should have info calls for processing (inherited from LLMAgent)
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(len(info_calls) > 0)

        # Verify relevant information is logged
        log_messages = [call[1] for call in info_calls]
        prompt_logged = any("multimodal capabilities" in msg for msg in log_messages)
        self.assertTrue(prompt_logged, f"Expected prompt logged, got: {log_messages}")

    def test_google_agent_debug_logging_provider_info(self):
        """Test that GoogleAgent logs provider-specific debug information."""
        agent = self.create_google_agent()
        agent.configure_llm_service(self.mock_llm_service)

        inputs = {"prompt": "Test prompt"}
        agent.process(inputs)

        # Check for provider-specific debug logging
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        debug_messages = [call[1] for call in debug_calls]

        # Should have debug info about using google provider
        provider_logged = any("google" in msg.lower() for msg in debug_messages)
        self.assertTrue(
            provider_logged, f"Expected Google provider logged, got: {debug_messages}"
        )

    # =============================================================================
    # 8. Gemini-Specific Model Parameter Tests
    # =============================================================================

    def test_google_agent_with_gemini_specific_parameters(self):
        """Test GoogleAgent with Gemini-specific model parameters."""
        context = {
            "model": "gemini-1.5-pro",
            "temperature": 0.4,
            "max_tokens": 8192,
            "top_p": 0.8,
            "top_k": 40,
        }

        agent = self.create_google_agent(context=context)

        # Verify Google provider and Gemini model
        self.assertEqual(agent.provider, "google")
        self.assertEqual(agent.model, "gemini-1.5-pro")
        self.assertEqual(agent.temperature, 0.4)
        self.assertEqual(agent.max_tokens, 8192)

        # Verify additional parameters are preserved in context
        self.assertEqual(agent.context.get("top_p"), 0.8)
        self.assertEqual(agent.context.get("top_k"), 40)

    def test_google_agent_default_model_consistency(self):
        """Test that GoogleAgent uses consistent initialization when no model specified."""
        # Test multiple agents to ensure consistent defaults
        agents = []
        for i in range(3):
            agent = GoogleAgent(
                name=f"test_agent_{i}", prompt="Test", logger=self.mock_logger
            )
            agents.append(agent)

        # All should have consistent initialization (model=None, LLMService provides default at runtime)
        for agent in agents:
            self.assertEqual(agent.provider, "google")
            self.assertIsNone(
                agent.model
            )  # Default model provided by LLMService at runtime
            self.assertEqual(agent.temperature, 0.7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
