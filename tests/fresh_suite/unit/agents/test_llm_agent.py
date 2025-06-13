"""
Unit tests for LLMAgent using pure Mock objects and established testing patterns.

This test suite validates the LLM agent's core functionality including protocol
compliance, service integration, and business logic.
"""
import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any

from agentmap.agents.builtins.llm.llm_agent import LLMAgent
from agentmap.services.protocols import LLMCapableAgent, LLMServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory


class TestLLMAgent(unittest.TestCase):
    """Unit tests for LLMAgent using pure Mock objects."""
    
    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Create LLM service mock
        self.mock_llm_service = Mock(spec=LLMServiceProtocol)
        self.mock_llm_service.call_llm.return_value = "Mock LLM response for testing"
        
        # Create execution tracker mock
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()
        
        # Create basic context for testing
        self.test_context = {
            "input_fields": ["prompt", "context"],
            "output_field": "response",
            "description": "Test LLM agent",
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(LLMAgent)
        
        # Create agent instance with mocked infrastructure dependencies
        self.agent = LLMAgent(
            name="test_llm_agent",
            prompt="You are a helpful AI assistant.",
            context=self.test_context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
    
    # =============================================================================
    # 1. Agent Initialization and Protocol Compliance Tests
    # =============================================================================
    
    def test_agent_initialization_with_llm_configuration(self):
        """Test that LLMAgent initializes correctly with LLM configuration."""
        # Verify all infrastructure dependencies are stored
        self.assertEqual(self.agent.name, "test_llm_agent")
        self.assertEqual(self.agent.prompt, "You are a helpful AI assistant.")
        self.assertEqual(self.agent.context, self.test_context)
        self.assertEqual(self.agent.input_fields, ["prompt", "context", "memory"])
        self.assertEqual(self.agent.output_field, "response")
        
        # Verify LLM-specific configuration
        self.assertEqual(self.agent.provider, "openai")
        self.assertEqual(self.agent.model, "gpt-4")
        self.assertEqual(self.agent.temperature, 0.7)
        self.assertEqual(self.agent.max_tokens, 1000)
        
        # Verify infrastructure services are available
        self.assertIsNotNone(self.agent.logger)
        self.assertIsNotNone(self.agent.execution_tracking_service)
        self.assertIsNotNone(self.agent.state_adapter_service)
        
        # Verify LLM service is not configured by default
        with self.assertRaises(ValueError):
            _ = self.agent.llm_service
    
    def test_agent_protocol_implementation(self):
        """Test that LLMAgent correctly implements LLMCapableAgent protocol."""
        # Verify protocol implementation
        self.assertTrue(isinstance(self.agent, LLMCapableAgent))
        
        # Verify service configuration method exists
        self.assertTrue(hasattr(self.agent, 'configure_llm_service'))
        self.assertTrue(callable(self.agent.configure_llm_service))
        
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
        
        # Verify service is now accessible
        self.assertEqual(self.agent.llm_service, self.mock_llm_service)
    
    def test_agent_initialization_with_minimal_context(self):
        """Test LLMAgent with minimal configuration."""
        minimal_agent = LLMAgent(
            name="minimal_llm",
            prompt="Simple prompt"
        )
        
        # Verify defaults are applied
        self.assertEqual(minimal_agent.name, "minimal_llm")
        self.assertEqual(minimal_agent.prompt, "Simple prompt")
        self.assertEqual(minimal_agent.provider, "anthropic")  # Default provider
        self.assertEqual(minimal_agent.model, "claude-3-sonnet-20240229")  # Default model
        self.assertEqual(minimal_agent.temperature, 0.7)  # Default temperature
        self.assertIsNone(minimal_agent.max_tokens)  # Default max_tokens
    
    def test_agent_initialization_with_different_providers(self):
        """Test LLMAgent with different LLM providers."""
        providers_config = [
            ("anthropic", "claude-3-sonnet-20240229", 0.5),
            ("google", "gemini-1.0-pro", 0.3),
            ("openai", "gpt-4-turbo", 0.8)
        ]
        
        for provider, model, temp in providers_config:
            with self.subTest(provider=provider, model=model, temp=temp):
                context = {
                    "provider": provider,
                    "model": model,
                    "temperature": temp,
                    "input_fields": ["input"],
                    "output_field": "output"
                }
                
                agent = LLMAgent(
                    name=f"test_{provider}",
                    prompt="Test prompt",
                    context=context,
                    logger=self.mock_logger
                )
                
                self.assertEqual(agent.provider, provider)
                self.assertEqual(agent.model, model)
                self.assertEqual(agent.temperature, temp)
    
    # =============================================================================
    # 2. Service Configuration and Error Handling Tests
    # =============================================================================
    
    def test_llm_service_configuration(self):
        """Test LLM service configuration via protocol."""
        # Initially no LLM service
        with self.assertRaises(ValueError) as cm:
            _ = self.agent.llm_service
        self.assertIn("LLM service not configured", str(cm.exception))
        self.assertIn("test_llm_agent", str(cm.exception))
        
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
        
        # Now service should be accessible
        self.assertEqual(self.agent.llm_service, self.mock_llm_service)
        
        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        llm_configured = any("LLM service configured" in call[1] for call in debug_calls)
        self.assertTrue(llm_configured, f"Expected LLM service log, got: {debug_calls}")
    
    def test_llm_service_error_when_not_configured(self):
        """Test clear error when LLM service is accessed but not configured."""
        unconfigured_agent = LLMAgent(
            name="unconfigured",
            prompt="Test prompt",
            logger=self.mock_logger
        )
        
        with self.assertRaises(ValueError) as cm:
            _ = unconfigured_agent.llm_service
        
        error_msg = str(cm.exception)
        self.assertIn("LLM service not configured", error_msg)
        self.assertIn("unconfigured", error_msg)
    
    # =============================================================================
    # 3. Core Business Logic Tests
    # =============================================================================
    
    def test_process_with_simple_prompt(self):
        """Test processing with a simple prompt."""
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {"prompt": "What is the capital of France?"}
        
        result = self.agent.process(inputs)
        
        # Verify LLM service was called
        self.mock_llm_service.call_llm.assert_called_once()
        call_args = self.mock_llm_service.call_llm.call_args
        
        # Verify call parameters
        kwargs = call_args.kwargs
        self.assertEqual(kwargs["provider"], "openai")
        self.assertEqual(kwargs["model"], "gpt-4")
        self.assertEqual(kwargs["temperature"], 0.7)
        self.assertEqual(kwargs["max_tokens"], 1000)
        
        # Verify messages structure
        messages = kwargs["messages"]
        self.assertIsInstance(messages, list)
        self.assertTrue(len(messages) >= 1)
        
        # Should have system message with agent prompt
        system_msg = messages[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertIn("helpful AI assistant", system_msg["content"])
        
        # Should have user message with input prompt (single field = no prefix)
        user_msg = messages[1]
        self.assertEqual(user_msg["role"], "user")
        self.assertEqual(user_msg["content"], "What is the capital of France?")  # Single field, no prefix
        
        # Verify result (now returns a dictionary with output and memory)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["output"], "Mock LLM response for testing")
        self.assertIn("memory", result)
    
    def test_process_with_context_and_prompt(self):
        """Test processing with both context and prompt."""
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {
            "prompt": "Summarize this information",
            "context": "The weather today is sunny with 75°F temperature."
        }
        
        result = self.agent.process(inputs)
        
        # Verify LLM service was called
        self.mock_llm_service.call_llm.assert_called_once()
        call_args = self.mock_llm_service.call_llm.call_args
        
        # Verify messages include both context and prompt (multiple fields = prefixed format)
        messages = call_args.kwargs["messages"]
        user_msg = messages[1]  # User message
        
        # Should include both fields with prefixes since we have multiple fields
        expected_content = "prompt: Summarize this information\ncontext: The weather today is sunny with 75°F temperature."
        self.assertEqual(user_msg["content"], expected_content)
        
        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertEqual(result["output"], "Mock LLM response for testing")
        self.assertIn("memory", result)
    
    def test_process_with_multiple_inputs(self):
        """Test processing with multiple input fields."""
        # Create agent with more input fields
        context = {
            "input_fields": ["task", "data", "format"],
            "output_field": "result",
            "provider": "openai"
        }
        
        agent = LLMAgent(
            name="multi_input",
            prompt="Process the given task",
            context=context,
            logger=self.mock_logger
        )
        
        agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {
            "task": "Analyze sentiment",
            "data": "I love this product!",
            "format": "JSON"
        }
        
        result = agent.process(inputs)
        
        # Verify all inputs are included in the message (multiple fields = prefixed format)
        call_args = self.mock_llm_service.call_llm.call_args
        messages = call_args.kwargs["messages"]
        user_msg = messages[1]
        
        # Should include all fields with prefixes since we have multiple fields
        expected_content = "task: Analyze sentiment\ndata: I love this product!\nformat: JSON"
        self.assertEqual(user_msg["content"], expected_content)
        
        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertEqual(result["output"], "Mock LLM response for testing")
        self.assertIn("memory", result)
    
    def test_process_with_empty_inputs(self):
        """Test processing with empty inputs."""
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {}
        
        result = self.agent.process(inputs)
        
        # Should still call LLM with system message only
        self.mock_llm_service.call_llm.assert_called_once()
        call_args = self.mock_llm_service.call_llm.call_args
        messages = call_args.kwargs["messages"]
        
        # Should have system message
        self.assertTrue(len(messages) >= 1)
        self.assertEqual(messages[0]["role"], "system")
        
        # May have a user message indicating no input
        if len(messages) > 1:
            self.assertEqual(messages[1]["role"], "user")
        
        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertEqual(result["output"], "Mock LLM response for testing")
        self.assertIn("memory", result)
    
    # =============================================================================
    # 4. Error Handling Tests
    # =============================================================================
    
    def test_process_without_configured_service(self):
        """Test process method fails gracefully when LLM service not configured."""
        unconfigured_agent = LLMAgent(
            name="unconfigured",
            prompt="Test",
            logger=self.mock_logger
        )
        
        inputs = {"prompt": "Test prompt"}
        
        with self.assertRaises(ValueError) as cm:
            unconfigured_agent.process(inputs)
        
        self.assertIn("LLM service not configured", str(cm.exception))
    
    def test_process_with_llm_service_error(self):
        """Test process handles LLM service errors gracefully."""
        # Configure LLM service to raise an error
        self.mock_llm_service.call_llm.side_effect = Exception("LLM API Error")
        self.agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {"prompt": "Test prompt"}
        
        # Should return error in the result (LLMAgent catches and returns error dict)
        result = self.agent.process(inputs)
        
        # Verify error result structure
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("LLM API Error", result["error"])
        self.assertFalse(result["last_action_success"])
    
    # =============================================================================
    # 5. Message Construction Tests
    # =============================================================================
    
    def test_build_messages_with_system_prompt(self):
        """Test message building with system prompt."""
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {"prompt": "Hello"}
        self.agent.process(inputs)
        
        call_args = self.mock_llm_service.call_llm.call_args
        messages = call_args.kwargs["messages"]
        
        # Verify system message
        system_msg = messages[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertEqual(system_msg["content"], "You are a helpful AI assistant.")
    
    def test_build_messages_with_no_system_prompt(self):
        """Test message building when no system prompt provided."""
        agent = LLMAgent(
            name="no_system",
            prompt="",  # Empty prompt
            context={"input_fields": ["input"], "provider": "openai"},
            logger=self.mock_logger
        )
        
        agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {"input": "Test input"}
        agent.process(inputs)
        
        call_args = self.mock_llm_service.call_llm.call_args
        messages = call_args.kwargs["messages"]
        
        # With empty prompt, should only have user message (no system message)
        self.assertEqual(len(messages), 1)
        
        # Should have user message only
        user_msg = messages[0]
        self.assertEqual(user_msg["role"], "user")
        self.assertEqual(user_msg["content"], "Test input")  # Single field, no prefix
    
    def test_build_user_message_formatting(self):
        """Test user message formatting with conditional prefix logic."""
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
        
        test_cases = [
            # Single field: no prefix
            ({"prompt": "Hello"}, "Hello"),
            # Multiple fields: prefixed format
            ({"prompt": "Question", "context": "Background"}, "prompt: Question\ncontext: Background"),
            # With None values (only non-None field, so no prefix)
            ({"prompt": "Test", "context": None}, "Test"),
        ]
        
        for inputs, expected_content in test_cases:
            with self.subTest(inputs=inputs):
                self.mock_llm_service.reset_mock()
                self.agent.process(inputs)
                
                call_args = self.mock_llm_service.call_llm.call_args
                messages = call_args.kwargs["messages"]
                user_msg = messages[1]  # Second message should be user
                
                self.assertEqual(user_msg["content"], expected_content)
    
    # =============================================================================
    # 6. Integration Tests
    # =============================================================================
    
    def test_run_method_integration(self):
        """Test the inherited run method works with LLMAgent."""
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
        
        # Configure state adapter behavior
        def mock_get_inputs(state, input_fields):
            return {field: state.get(field) for field in input_fields if field in state}
        
        def mock_set_value(state, field, value):
            updated_state = state.copy()
            updated_state[field] = value
            return updated_state
        
        self.mock_state_adapter_service.get_inputs.side_effect = mock_get_inputs
        self.mock_state_adapter_service.set_value.side_effect = mock_set_value
        
        # CRITICAL: Set execution tracker on agent (required by new architecture)
        self.agent.set_execution_tracker(self.mock_tracker)
        
        # The execution tracking service methods are already configured by MockServiceFactory
        
        # Test state
        test_state = {
            "prompt": "What is AI?",
            "context": "Machine learning context",
            "other_field": "preserved"
        }
        
        # Execute run method
        result_state = self.agent.run(test_state)
        
        # Verify LLM was called
        self.mock_llm_service.call_llm.assert_called_once()
        
        # Verify state was updated with response
        self.assertIn("response", result_state)
        self.assertEqual(result_state["response"], "Mock LLM response for testing")
        
        # Verify original fields are preserved
        self.assertEqual(result_state["other_field"], "preserved")
        
        # Verify tracking calls (inherited behavior via execution tracking service)
        self.mock_execution_tracking_service.record_node_start.assert_called_once()
        self.mock_execution_tracking_service.record_node_result.assert_called_once()
    
    # =============================================================================
    # 7. Service Information Tests
    # =============================================================================
    
    def test_get_service_info(self):
        """Test service information retrieval."""
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
        
        service_info = self.agent.get_service_info()
        
        # Verify basic agent information
        self.assertEqual(service_info["agent_name"], "test_llm_agent")
        self.assertEqual(service_info["agent_type"], "LLMAgent")
        
        # Verify service availability
        services = service_info["services"]
        self.assertTrue(services["logger_available"])
        self.assertTrue(services["execution_tracker_available"])
        self.assertTrue(services["state_adapter_available"])
        self.assertTrue(services["llm_service_configured"])
        self.assertFalse(services["storage_service_configured"])
        
        # Verify protocol implementation
        protocols = service_info["protocols"]
        self.assertTrue(protocols["implements_llm_capable"])
        self.assertFalse(protocols["implements_storage_capable"])
        
        # Verify configuration
        config = service_info["configuration"]
        self.assertEqual(config["input_fields"], ["prompt", "context", "memory"])
        self.assertEqual(config["output_field"], "response")
        self.assertEqual(config["description"], "Test LLM agent")
    
    # =============================================================================
    # 8. Logging Integration Tests
    # =============================================================================
    
    def test_logging_integration(self):
        """Test that agent properly logs LLM operations."""
        # Configure LLM service
        self.agent.configure_llm_service(self.mock_llm_service)
        
        inputs = {"prompt": "Test logging"}
        
        # Execute process to generate log calls
        self.agent.process(inputs)
        
        # Verify logger was called
        logger_calls = self.mock_logger.calls
        
        # Should have info calls for processing
        info_calls = [call for call in logger_calls if call[0] == "info"]
        self.assertTrue(len(info_calls) > 0)
        
        # Verify relevant information is logged
        log_messages = [call[1] for call in info_calls]
        prompt_logged = any("Test logging" in msg for msg in log_messages)
        self.assertTrue(prompt_logged, f"Expected prompt logged, got: {log_messages}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
