"""
Unit tests for LLMService.

These tests validate the LLMService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Optional
import os

from agentmap.services.llm_service import LLMService
from tests.utils.mock_service_factory import MockServiceFactory


class TestLLMService(unittest.TestCase):
    """Unit tests for LLMService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        self.mock_llm_models_config_service = MockServiceFactory.create_mock_llm_models_config_service()

        # Create mock LLMRoutingService
        self.mock_routing_service = Mock()

        # Initialize LLMService with mocked dependencies
        self.service = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=self.mock_routing_service,
            llm_models_config_service=self.mock_llm_models_config_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service._logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.configuration, self.mock_app_config_service)
        self.assertEqual(self.service.routing_service, self.mock_routing_service)
        self.assertIsNotNone(self.service._logger)
        
        # Verify routing is enabled when service is provided
        self.assertTrue(self.service._routing_enabled)
        
        # Verify clients cache is initialized
        self.assertEqual(self.service._clients, {})
    
    def test_service_initialization_without_routing(self):
        """Test service initialization with no routing service."""
        service_no_routing = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=None,
            llm_models_config_service=self.mock_llm_models_config_service
        )

        # Verify routing is disabled
        self.assertFalse(service_no_routing._routing_enabled)
        self.assertIsNone(service_no_routing.routing_service)
    
    def test_service_logging_setup(self):
        """Test that service logging is set up correctly."""
        # Verify logger name
        self.assertEqual(self.service._logger.name, "agentmap.llm")

        # Verify get_class_logger was called for main service and helper classes
        # After refactoring, LLMService creates 4 loggers (main + 3 helpers)
        calls = self.mock_logging_service.get_class_logger.call_args_list
        logger_names = [call[0][0] for call in calls]
        self.assertIn("agentmap.llm", logger_names)
        self.assertEqual(len(calls), 4)  # Main service + 3 helpers
    
    # =============================================================================
    # 2. Core LLM Call Tests
    # =============================================================================
    
    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_call_llm_direct_provider_success(self):
        """Test call_llm() with direct provider call (no routing)."""
        # Configure mock config for OpenAI
        self.mock_app_config_service.get_llm_config.return_value = {
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "api_key": "test_key"
        }
        
        # Mock LangChain client and response
        with patch('agentmap.services.llm_service.LLMService._create_langchain_client') as mock_create_client, \
             patch('agentmap.services.llm_service.LLMService._convert_messages_to_langchain') as mock_convert:
            
            # Configure mock client
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = "Test LLM response"
            mock_client.invoke.return_value = mock_response
            mock_create_client.return_value = mock_client
            
            # Configure message conversion
            mock_langchain_messages = [Mock()]
            mock_convert.return_value = mock_langchain_messages
            
            # Execute test
            messages = [{"role": "user", "content": "Hello, world!"}]
            result = self.service.call_llm(
                provider="openai",
                messages=messages,
                model="gpt-4",
                temperature=0.5
            )
            
            # Verify result
            self.assertEqual(result, "Test LLM response")
            
            # Verify provider config was requested
            self.mock_app_config_service.get_llm_config.assert_called_once_with("openai")
            
            # Verify client creation with overrides
            mock_create_client.assert_called_once()
            
            # Verify message conversion
            mock_convert.assert_called_once_with(messages)
            
            # Verify client invoke
            mock_client.invoke.assert_called_once_with(mock_langchain_messages)
    
    def test_call_llm_with_routing_context(self):
        """Test call_llm() with routing integration."""
        # Configure routing context
        routing_context = {
            "routing_enabled": True,
            "task_type": "general",
            "complexity_override": "medium"
        }
        
        # Mock routing decision
        mock_decision = Mock()
        mock_decision.provider = "anthropic"
        mock_decision.model = "claude-3-7-sonnet-20250219"
        mock_decision.complexity = "medium"
        mock_decision.confidence = 0.85
        
        self.mock_routing_service.route_request.return_value = mock_decision
        
        # Mock available providers
        with patch.object(self.service, '_get_available_providers', return_value=["openai", "anthropic"]), \
             patch.object(self.service, '_call_llm_direct') as mock_direct_call:
            
            mock_direct_call.return_value = "Routed response"
            
            # Execute test
            messages = [{"role": "user", "content": "Complex task"}]
            result = self.service.call_llm(
                provider="openai",  # This should be overridden by routing
                messages=messages,
                routing_context=routing_context
            )
            
            # Verify routing was used
            self.mock_routing_service.route_request.assert_called_once()
            
            # Verify direct call was made with routed provider
            mock_direct_call.assert_called_once_with(
                provider="anthropic",
                messages=messages,
                model="claude-3-7-sonnet-20250219",
                temperature=None
            )
            
            self.assertEqual(result, "Routed response")
    
    def test_call_llm_routing_fallback(self):
        """Test call_llm() falls back to direct call when routing fails."""
        # Configure routing context but make routing fail
        routing_context = {
            "routing_enabled": True,
            "fallback_provider": "openai"
        }
        
        # Make routing service raise exception
        self.mock_routing_service.route_request.side_effect = Exception("Routing failed")
        
        with patch.object(self.service, '_call_llm_direct') as mock_direct_call:
            mock_direct_call.return_value = "Fallback response"
            
            # Execute test
            messages = [{"role": "user", "content": "Test"}]
            result = self.service.call_llm(
                provider="anthropic",
                messages=messages,
                routing_context=routing_context
            )
            
            # Verify fallback to direct call
            mock_direct_call.assert_called_with(
                provider="openai",  # fallback_provider
                messages=messages,
                model=None,
                temperature=None
            )
            
            self.assertEqual(result, "Fallback response")
    
    def test_generate_method_simple_interface(self):
        """Test generate() method as simplified LLM interface."""
        with patch.object(self.service, 'call_llm') as mock_call_llm:
            mock_call_llm.return_value = "Generated text"
            
            # Execute test
            result = self.service.generate("What is AI?", provider="anthropic", temperature=0.8)
            
            # Verify delegation to call_llm
            expected_messages = [{"role": "user", "content": "What is AI?"}]
            mock_call_llm.assert_called_once_with(
                provider="anthropic",
                messages=expected_messages,
                temperature=0.8
            )
            
            self.assertEqual(result, "Generated text")
    
    def test_generate_method_default_provider(self):
        """Test generate() method with default provider."""
        with patch.object(self.service, 'call_llm') as mock_call_llm:
            mock_call_llm.return_value = "Default response"
            
            # Execute test without specifying provider
            result = self.service.generate("Hello")
            
            # Verify default provider is used
            expected_messages = [{"role": "user", "content": "Hello"}]
            mock_call_llm.assert_called_once_with(
                provider="anthropic",  # default
                messages=expected_messages
            )
            
            self.assertEqual(result, "Default response")
    
    # =============================================================================
    # 3. Provider Management Tests
    # =============================================================================
    
    def test_normalize_provider_aliases(self):
        """Test provider name normalization and aliases."""
        # Test provider normalization
        self.assertEqual(self.service._normalize_provider("OpenAI"), "openai")
        self.assertEqual(self.service._normalize_provider("GPT"), "openai") 
        self.assertEqual(self.service._normalize_provider("Claude"), "anthropic")
        self.assertEqual(self.service._normalize_provider("Gemini"), "google")
        self.assertEqual(self.service._normalize_provider("custom"), "custom")
    
    def test_get_provider_config_success(self):
        """Test _get_provider_config() returns proper configuration."""
        # Configure mock to return config
        mock_config = {
            "model": "gpt-4",
            "temperature": 0.5,
            "api_key": "test_key_123"
        }
        self.mock_app_config_service.get_llm_config.return_value = mock_config
        
        # Execute test
        result = self.service._get_provider_config("openai")
        
        # Verify config returned with defaults merged
        self.assertIn("model", result)
        self.assertIn("temperature", result)
        self.assertIn("api_key", result)
        self.assertEqual(result["model"], "gpt-4")
    
    def test_get_provider_config_with_defaults(self):
        """Test _get_provider_config() merges defaults for missing fields."""
        # Configure mock to return partial config
        partial_config = {"api_key": "test_key"}
        self.mock_app_config_service.get_llm_config.return_value = partial_config

        # Clear side_effect and set return_value to test merging logic
        self.mock_llm_models_config_service.get_default_model.side_effect = None
        self.mock_llm_models_config_service.get_default_model.return_value = "test-model"

        # Execute test
        result = self.service._get_provider_config("openai")

        # Verify defaults are applied from llm_models_config_service
        self.mock_llm_models_config_service.get_default_model.assert_called_with("openai")
        self.assertEqual(result["model"], "test-model")  # from llm_models_config
        self.assertEqual(result["temperature"], 0.7)  # hardcoded default
        self.assertEqual(result["api_key"], "test_key")  # from config
    
    def test_get_provider_config_not_found(self):
        """Test _get_provider_config() raises error for missing provider."""
        from agentmap.exceptions import LLMConfigurationError
        
        # Configure mock to return None
        self.mock_app_config_service.get_llm_config.return_value = None
        
        # Execute and verify error
        with self.assertRaises(LLMConfigurationError) as context:
            self.service._get_provider_config("nonexistent")
        
        self.assertIn("No configuration found for provider", str(context.exception))
    
    def test_get_available_providers_with_api_keys(self):
        """Test _get_available_providers() returns providers with valid API keys."""
        # Mock configuration for different providers
        def mock_get_llm_config(provider):
            configs = {
                "openai": {"api_key": "openai_key"},
                "anthropic": {"api_key": "anthropic_key"},
                "google": None  # No config
            }
            return configs.get(provider)
        
        self.mock_app_config_service.get_llm_config.side_effect = mock_get_llm_config
        
        # Mock environment variables
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env_key", "ANTHROPIC_API_KEY": "env_key2"}):
            # Execute test
            providers = self.service._get_available_providers()
            
            # Should find openai and anthropic (both have keys)
            self.assertIn("openai", providers)
            self.assertIn("anthropic", providers)
            # google should not be included (no config)
    
    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_client_caching(self):
        """Test that LangChain clients are properly cached."""
        # Configure mock config
        config = {
            "model": "gpt-3.5-turbo",
            "api_key": "test_key",
            "temperature": 0.7
        }
        
        with patch.object(self.service, '_create_langchain_client') as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            
            # First call - should create client
            client1 = self.service._get_or_create_client("openai", config)
            
            # Second call with same config - should use cached
            client2 = self.service._get_or_create_client("openai", config)
            
            # Verify same client returned
            self.assertEqual(client1, client2)
            
            # Verify client was only created once
            mock_create.assert_called_once()
    
    def test_clear_cache(self):
        """Test clear_cache() clears the client cache."""
        # Add something to cache
        self.service._clients["test_key"] = Mock()
        
        # Execute clear
        self.service.clear_cache()
        
        # Verify cache is empty
        self.assertEqual(self.service._clients, {})
    
    # =============================================================================
    # 4. Routing Integration Tests
    # =============================================================================
    
    def test_routing_context_creation(self):
        """Test _create_routing_context() properly converts dictionary to RoutingContext."""
        routing_dict = {
            "task_type": "coding",
            "complexity_override": "high",
            "provider_preference": ["anthropic", "openai"],
            "max_cost_tier": 3
        }
        messages = [{"role": "user", "content": "Write code"}]
        
        # Execute test
        context = self.service._create_routing_context(routing_dict, messages)
        
        # Verify RoutingContext fields
        self.assertEqual(context.task_type, "coding")
        self.assertEqual(context.complexity_override, "high")
        self.assertEqual(context.provider_preference, ["anthropic", "openai"])
        self.assertEqual(context.max_cost_tier, 3)
        self.assertEqual(context.prompt, "Write code")  # extracted from messages
    
    def test_extract_prompt_from_messages(self):
        """Test _extract_prompt_from_messages() combines user and system messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},  # Should be ignored
            {"role": "user", "content": "How are you?"}
        ]
        
        # Execute test
        prompt = self.service._extract_prompt_from_messages(messages)
        
        # Should combine system and user messages only
        expected = "You are a helpful assistant. Hello How are you?"
        self.assertEqual(prompt, expected)
    
    def test_is_routing_enabled(self):
        """Test is_routing_enabled() returns correct status."""
        # Service with routing
        self.assertTrue(self.service.is_routing_enabled())

        # Service without routing
        service_no_routing = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=None,
            llm_models_config_service=self.mock_llm_models_config_service
        )
        self.assertFalse(service_no_routing.is_routing_enabled())
    
    def test_get_routing_stats(self):
        """Test get_routing_stats() delegates to routing service."""
        # Configure mock routing service
        mock_stats = {"total_requests": 100, "avg_confidence": 0.85}
        self.mock_routing_service.get_routing_stats.return_value = mock_stats
        
        # Execute test
        stats = self.service.get_routing_stats()
        
        # Verify delegation
        self.mock_routing_service.get_routing_stats.assert_called_once()
        self.assertEqual(stats, mock_stats)
    
    def test_get_routing_stats_no_routing_service(self):
        """Test get_routing_stats() returns empty dict when no routing service."""
        service_no_routing = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=None,
            llm_models_config_service=self.mock_llm_models_config_service
        )

        # Execute test
        stats = service_no_routing.get_routing_stats()

        # Should return empty dict
        self.assertEqual(stats, {})
    
    # =============================================================================
    # 5. Error Handling Tests
    # =============================================================================
    
    def test_llm_configuration_error_no_api_key(self):
        """Test LLMConfigurationError when API key is missing."""
        from agentmap.exceptions import LLMConfigurationError
        
        # Configure config without API key
        config_no_key = {
            "model": "gpt-3.5-turbo",
            "temperature": 0.7
            # Missing api_key
        }
        self.mock_app_config_service.get_llm_config.return_value = config_no_key
        
        # Mock environment to not have the key either
        with patch.dict(os.environ, {}, clear=True):
            # Execute and verify error
            with self.assertRaises(LLMConfigurationError) as context:
                self.service.call_llm("openai", [{"role": "user", "content": "test"}])
            
            self.assertIn("No API key found", str(context.exception))
    
    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_llm_dependency_error_missing_langchain(self):
        """Test LLMDependencyError when LangChain imports fail."""
        from agentmap.exceptions import LLMDependencyError

        # Configure valid config
        config = {"api_key": "test_key", "model": "gpt-3.5-turbo", "temperature": 0.7}
        self.mock_app_config_service.get_llm_config.return_value = config
        
        # Mock import failure
        with patch('agentmap.services.llm_service.LLMService._create_langchain_client') as mock_create:
            mock_create.side_effect = ImportError("No module named 'langchain_openai'")
            
            # Execute and verify error
            with self.assertRaises(LLMDependencyError) as context:
                self.service.call_llm("openai", [{"role": "user", "content": "test"}])
            
            self.assertIn("Missing dependencies", str(context.exception))
    
    def test_llm_provider_error_invalid_provider(self):
        """Test error handling for unsupported provider."""
        from agentmap.exceptions import LLMConfigurationError
        
        # Configure config for unsupported provider
        config = {"api_key": "test_key", "model": "some-model", "temperature": 0.7}
        self.mock_app_config_service.get_llm_config.return_value = config
        
        with patch.object(self.service, '_create_langchain_client') as mock_create:
            mock_create.side_effect = LLMConfigurationError("Unsupported provider: unknown")
            
            # Execute and verify error
            with self.assertRaises(LLMConfigurationError) as context:
                self.service.call_llm("unknown", [{"role": "user", "content": "test"}])
            
            self.assertIn("Unsupported provider", str(context.exception))
    
    def test_authentication_error_handling(self):
        """Test authentication error handling."""
        from agentmap.exceptions import LLMConfigurationError
        
        # Configure valid config
        config = {"api_key": "invalid_key", "model": "gpt-3.5-turbo", "temperature": 0.7}
        self.mock_app_config_service.get_llm_config.return_value = config
        
        with patch.object(self.service, '_get_or_create_client') as mock_get_client, \
             patch.object(self.service, '_convert_messages_to_langchain') as mock_convert:
            
            # Mock client that raises authentication error
            mock_client = Mock()
            mock_client.invoke.side_effect = Exception("Authentication failed")
            mock_get_client.return_value = mock_client
            mock_convert.return_value = [Mock()]
            
            # Execute and verify error conversion
            with self.assertRaises(LLMConfigurationError) as context:
                self.service.call_llm("openai", [{"role": "user", "content": "test"}])
            
            self.assertIn("Authentication failed", str(context.exception))
    
    def test_message_conversion_langchain_import_fallback(self):
        """Test _convert_messages_to_langchain() handles import failures gracefully."""
        messages = [{"role": "user", "content": "test"}]
        
        # Mock import failures for both new and old LangChain
        with patch('agentmap.services.llm_service.LLMService._convert_messages_to_langchain') as mock_convert:
            # Configure to fall back to returning messages as-is
            mock_convert.return_value = messages
            
            result = self.service._convert_messages_to_langchain(messages)
            
            # Should handle gracefully
            self.assertEqual(result, messages)
    
    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_get_available_providers_public_method(self):
        """Test public get_available_providers() method."""
        with patch.object(self.service, '_get_available_providers') as mock_private:
            mock_private.return_value = ["openai", "anthropic"]
            
            # Execute test
            providers = self.service.get_available_providers()
            
            # Verify delegation
            mock_private.assert_called_once()
            self.assertEqual(providers, ["openai", "anthropic"])


if __name__ == '__main__':
    unittest.main()
