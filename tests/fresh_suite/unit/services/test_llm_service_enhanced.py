"""
Business Logic Tests for LLMService.

These tests focus on business logic and actual functionality rather than
implementation details. They validate what the service does, not how it does it.
"""

import os
import unittest
from unittest.mock import Mock, patch

from agentmap.services.llm_service import LLMService
from tests.utils.mock_service_factory import MockServiceFactory


class TestLLMServiceEnhanced(unittest.TestCase):
    """Enhanced unit tests for LLMService focusing on business logic."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = (
            MockServiceFactory.create_mock_app_config_service()
        )
        self.mock_routing_service = Mock()
        self.mock_llm_models_config_service = (
            MockServiceFactory.create_mock_llm_models_config_service()
        )

        self.service = LLMService(
            configuration=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            routing_service=self.mock_routing_service,
            llm_models_config_service=self.mock_llm_models_config_service,
        )

        self.mock_logger = self.service._logger

    # =============================================================================
    # Business Logic: Successful LLM Operations
    # =============================================================================

    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_can_make_successful_llm_call_with_text_response(self):
        """Test that LLM service can make successful calls and return text responses."""
        # Configure working provider
        self.mock_app_config_service.get_llm_config.return_value = {
            "api_key": "valid_key",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
        }

        # Mock successful LLM call chain
        with (
            patch.object(self.service, "_get_or_create_client") as mock_client,
            patch.object(
                self.service, "_convert_messages_to_langchain"
            ) as mock_convert,
        ):

            # Mock successful response
            mock_llm_client = Mock()
            mock_response = Mock()
            mock_response.content = "Hello! I'm Claude, an AI assistant."
            mock_llm_client.invoke.return_value = mock_response
            mock_client.return_value = mock_llm_client
            mock_convert.return_value = [Mock()]

            # Business Logic Test: Can we get a response?
            result = self.service.call_llm(
                provider="anthropic", messages=[{"role": "user", "content": "Hello!"}]
            )

            # Verify business outcome
            self.assertEqual(result, "Hello! I'm Claude, an AI assistant.")
            self.assertIsInstance(result, str)

    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_can_handle_different_providers_correctly(self):
        """Test that service correctly handles calls to different providers."""

        # Configure configs for different providers
        def mock_get_config(provider):
            configs = {
                "openai": {"api_key": "openai_key", "model": "gpt-4"},
                "anthropic": {
                    "api_key": "claude_key",
                    "model": "claude-3-7-sonnet-20250219",
                },
                "google": {"api_key": "google_key", "model": "gemini-pro"},
            }
            return configs.get(provider)

        self.mock_app_config_service.get_llm_config.side_effect = mock_get_config

        with (
            patch.object(self.service, "_get_or_create_client") as mock_client,
            patch.object(self.service, "_convert_messages_to_langchain"),
        ):

            # Mock different responses per provider
            def mock_client_response(provider, config):
                mock_llm_client = Mock()
                mock_response = Mock()

                if provider == "openai":
                    mock_response.content = "OpenAI response"
                elif provider == "anthropic":
                    mock_response.content = "Claude response"
                elif provider == "google":
                    mock_response.content = "Gemini response"

                mock_llm_client.invoke.return_value = mock_response
                return mock_llm_client

            mock_client.side_effect = mock_client_response

            # Test different providers
            test_cases = [
                ("openai", "OpenAI response"),
                ("anthropic", "Claude response"),
                ("google", "Gemini response"),
            ]

            for provider, expected_response in test_cases:
                result = self.service.call_llm(
                    provider=provider, messages=[{"role": "user", "content": "Test"}]
                )
                self.assertEqual(result, expected_response)

    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_can_override_model_and_temperature_per_call(self):
        """Test that service allows per-call overrides of model and temperature."""
        # Base config
        self.mock_app_config_service.get_llm_config.return_value = {
            "api_key": "test_key",
            "model": "base-model",
            "temperature": 0.7,
        }

        with (
            patch.object(self.service, "_get_or_create_client") as mock_client,
            patch.object(self.service, "_convert_messages_to_langchain"),
        ):

            mock_llm_client = Mock()
            mock_response = Mock()
            mock_response.content = "Override test"
            mock_llm_client.invoke.return_value = mock_response
            mock_client.return_value = mock_llm_client

            # Make call with overrides
            result = self.service.call_llm(
                provider="openai",
                messages=[{"role": "user", "content": "test"}],
                model="gpt-4-turbo",
                temperature=0.3,
            )

            # Verify override was applied (check what config was passed to client creation)
            call_args = mock_client.call_args[0]
            provider_arg, config_arg = call_args

            self.assertEqual(config_arg["model"], "gpt-4-turbo")  # Overridden
            self.assertEqual(config_arg["temperature"], 0.3)  # Overridden
            self.assertEqual(config_arg["api_key"], "test_key")  # From base config
            self.assertEqual(result, "Override test")

    def test_can_use_simple_ask_interface(self):
        """Test that ask() provides a simple interface for basic use cases."""
        with patch.object(self.service, "call_llm") as mock_call_llm:
            mock_call_llm.return_value = "Generated: The answer is 42."

            # Simple interface test
            result = self.service.ask("What is the answer to everything?")

            # Verify it converts to proper message format
            expected_messages = [
                {"role": "user", "content": "What is the answer to everything?"}
            ]
            mock_call_llm.assert_called_once_with(
                provider="anthropic", messages=expected_messages  # default
            )

            self.assertEqual(result, "Generated: The answer is 42.")

    # =============================================================================
    # Business Logic: Configuration Management
    # =============================================================================

    def test_properly_normalizes_provider_names(self):
        """Test that service normalizes provider names correctly for business use."""
        # Test business-relevant normalizations
        test_cases = [
            ("OpenAI", "openai"),
            ("ANTHROPIC", "anthropic"),
            ("GPT", "openai"),  # Business alias
            ("Claude", "anthropic"),  # Business alias
            ("Gemini", "google"),  # Business alias
            ("custom-provider", "custom-provider"),  # Passthrough
        ]

        for input_name, expected_normalized in test_cases:
            result = self.service._normalize_provider(input_name)
            self.assertEqual(
                result,
                expected_normalized,
                f"Failed to normalize {input_name} to {expected_normalized}",
            )

    def test_merges_configuration_with_environment_variables(self):
        """Test that service properly merges config with environment variables."""
        # Partial config missing API key
        self.mock_app_config_service.get_llm_config.return_value = {
            "model": "gpt-4",
            "temperature": 0.5,
            # Missing api_key
        }

        # Set environment variable
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env_api_key"}):
            config = self.service._get_provider_config("openai")

            # Should merge environment variable
            self.assertEqual(config["api_key"], "env_api_key")
            self.assertEqual(config["model"], "gpt-4")  # From config
            self.assertEqual(config["temperature"], 0.5)  # From config

    def test_applies_sensible_defaults_for_missing_config(self):
        """Test that service applies sensible defaults when configuration is incomplete."""
        # Minimal config
        self.mock_app_config_service.get_llm_config.return_value = {
            "api_key": "test_key"
            # Missing model and temperature
        }

        # Clear side_effect and set return_value to test merging logic
        self.mock_llm_models_config_service.get_default_model.side_effect = None
        self.mock_llm_models_config_service.get_default_model.return_value = (
            "test-default-model"
        )

        config = self.service._get_provider_config("openai")

        # Should apply defaults from llm_models_config_service
        self.mock_llm_models_config_service.get_default_model.assert_called_with(
            "openai"
        )
        self.assertEqual(
            config["model"], "test-default-model"
        )  # From llm_models_config
        self.assertEqual(config["temperature"], 0.7)  # Standard default
        self.assertEqual(config["api_key"], "test_key")  # From config

    def test_identifies_available_providers_based_on_api_keys(self):
        """Test that service correctly identifies which providers are available."""

        # Mock different availability scenarios
        def mock_get_config(provider):
            return {
                "openai": {"api_key": "openai_key"},
                "anthropic": {"api_key": "anthropic_key"},
                "google": None,  # Not configured
            }.get(provider)

        self.mock_app_config_service.get_llm_config.side_effect = mock_get_config

        providers = self.service._get_available_providers()

        # Should find configured providers
        self.assertIn("openai", providers)
        self.assertIn("anthropic", providers)
        # Should not find unconfigured provider
        self.assertNotIn("google", providers)

    # =============================================================================
    # Business Logic: Routing Integration
    # =============================================================================

    def test_uses_routing_when_enabled_and_available(self):
        """Test that service uses routing when requested and available."""
        # Configure routing request
        routing_context = {
            "routing_enabled": True,
            "task_type": "analysis",
            "complexity_override": "high",
        }

        # Mock routing decision
        mock_decision = Mock()
        mock_decision.provider = "anthropic"
        mock_decision.model = "claude-opus-4-20250514"
        mock_decision.complexity = "high"
        mock_decision.confidence = 0.9

        self.mock_routing_service.route_request.return_value = mock_decision

        with (
            patch.object(
                self.service,
                "_get_available_providers",
                return_value=["openai", "anthropic"],
            ),
            patch.object(self.service, "_call_llm_direct") as mock_direct,
        ):

            mock_direct.return_value = "Routed high-quality response"

            # Make call with routing
            result = self.service.call_llm(
                provider="openai",  # Should be overridden
                messages=[{"role": "user", "content": "Analyze this data"}],
                routing_context=routing_context,
            )

            # Verify routing was used
            self.mock_routing_service.route_request.assert_called_once()

            # Verify routed provider was used
            mock_direct.assert_called_once_with(
                provider="anthropic",  # From routing decision
                messages=[{"role": "user", "content": "Analyze this data"}],
                model="claude-opus-4-20250514",  # From routing decision
                temperature=None,
            )

            self.assertEqual(result, "Routed high-quality response")

    def test_falls_back_gracefully_when_routing_fails(self):
        """Test that service falls back to direct calls when routing fails."""
        routing_context = {"routing_enabled": True, "fallback_provider": "openai"}

        # Make routing fail
        self.mock_routing_service.route_request.side_effect = Exception(
            "Routing service down"
        )

        with patch.object(self.service, "_call_llm_direct") as mock_direct:
            mock_direct.return_value = "Fallback response"

            result = self.service.call_llm(
                provider="anthropic",
                messages=[{"role": "user", "content": "test"}],
                routing_context=routing_context,
            )

            # Should fall back to configured fallback provider
            mock_direct.assert_called_with(
                provider="openai",  # fallback_provider
                messages=[{"role": "user", "content": "test"}],
                model=None,
                temperature=None,
            )

            self.assertEqual(result, "Fallback response")

    def test_routing_stats_available_when_routing_enabled(self):
        """Test that routing statistics are available when routing is enabled."""
        mock_stats = {
            "total_requests": 150,
            "successful_routes": 140,
            "fallback_count": 10,
            "average_confidence": 0.85,
        }
        self.mock_routing_service.get_routing_stats.return_value = mock_stats

        stats = self.service.get_routing_stats()

        # Routing stats are included alongside circuit_breaker section
        for key in mock_stats:
            self.assertEqual(stats[key], mock_stats[key])
        self.assertIn("circuit_breaker", stats)
        self.mock_routing_service.get_routing_stats.assert_called_once()

    # =============================================================================
    # Business Logic: Error Handling
    # =============================================================================

    def test_handles_missing_api_key_configuration_error(self):
        """Test that service properly handles missing API key scenarios."""
        from agentmap.exceptions import LLMConfigurationError

        # Config without API key
        self.mock_app_config_service.get_llm_config.return_value = {
            "model": "gpt-4",
            "temperature": 0.7,
            # No api_key
        }

        # No environment variable either
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LLMConfigurationError) as context:
                self.service.call_llm(
                    messages=[{"role": "user", "content": "test"}], provider="openai"
                )

            # Should provide clear business error
            self.assertIn("No API key found", str(context.exception))

    def test_handles_provider_not_configured_error(self):
        """Test that service handles requests for unconfigured providers."""
        from agentmap.exceptions import LLMConfigurationError

        # No configuration for provider
        self.mock_app_config_service.get_llm_config.return_value = None

        with self.assertRaises(LLMConfigurationError) as context:
            self.service.call_llm(
                messages=[{"role": "user", "content": "test"}], provider="nonexistent"
            )

        self.assertIn("No configuration found for provider", str(context.exception))

    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_handles_llm_provider_errors_gracefully(self):
        """Test that service handles provider-specific errors gracefully."""
        from agentmap.exceptions import LLMProviderError

        # Valid config
        self.mock_app_config_service.get_llm_config.return_value = {
            "api_key": "valid_key",
            "model": "gpt-4",
            "temperature": 0.7,
        }

        with (
            patch.object(self.service, "_get_or_create_client") as mock_client,
            patch.object(self.service, "_convert_messages_to_langchain"),
        ):

            # Mock provider error (rate limit, network, etc.)
            mock_llm_client = Mock()
            mock_llm_client.invoke.side_effect = Exception("Rate limit exceeded")
            mock_client.return_value = mock_llm_client

            with self.assertRaises(LLMProviderError) as context:
                self.service.call_llm(
                    messages=[{"role": "user", "content": "test"}], provider="openai"
                )

            # Should provide clear business error
            self.assertIn("Rate limit exceeded", str(context.exception))

    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_handles_authentication_errors_clearly(self):
        """Test that service provides clear errors for authentication failures."""
        from agentmap.exceptions import LLMConfigurationError

        # Valid config structure but bad key
        self.mock_app_config_service.get_llm_config.return_value = {
            "api_key": "invalid_key",
            "model": "gpt-4",
            "temperature": 0.7,
        }

        with (
            patch.object(self.service, "_get_or_create_client") as mock_client,
            patch.object(self.service, "_convert_messages_to_langchain"),
        ):

            # Mock authentication error
            mock_llm_client = Mock()
            mock_llm_client.invoke.side_effect = Exception("Invalid API key provided")
            mock_client.return_value = mock_llm_client

            with self.assertRaises(LLMConfigurationError) as context:
                self.service.call_llm(
                    messages=[{"role": "user", "content": "test"}], provider="openai"
                )

            # Should identify as configuration issue
            self.assertIn("Invalid API key", str(context.exception))

    # =============================================================================
    # Business Logic: Caching and Performance
    # =============================================================================

    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_caches_clients_for_performance(self):
        """Test that service caches clients to avoid recreation overhead."""
        config = {"api_key": "test_key", "model": "gpt-4", "temperature": 0.7}

        with patch.object(self.service, "_create_langchain_client") as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client

            # Multiple calls with same config
            client1 = self.service._get_or_create_client("openai", config)
            client2 = self.service._get_or_create_client("openai", config)
            client3 = self.service._get_or_create_client("openai", config)

            # Should return same client instance
            self.assertEqual(client1, client2)
            self.assertEqual(client2, client3)

            # Should only create once for performance
            mock_create.assert_called_once()

    def test_cache_can_be_cleared_when_needed(self):
        """Test that cache can be cleared for configuration changes."""
        # Add client to cache
        self.service._clients["test_key"] = Mock()
        self.assertEqual(len(self.service._clients), 1)

        # Clear cache
        self.service.clear_cache()

        # Should be empty
        self.assertEqual(len(self.service._clients), 0)

    @unittest.skip("MANUAL: Test calls real OpenAI API - needs proper mocking")
    def test_handles_large_message_payloads(self):
        """Test that service can handle large message payloads without issues."""
        # Valid config
        self.mock_app_config_service.get_llm_config.return_value = {
            "api_key": "test_key",
            "model": "gpt-4",
            "temperature": 0.7,
        }

        # Create large messages (business scenario: long documents)
        large_content = "x" * 50000  # 50KB content
        large_messages = [
            {"role": "system", "content": "You analyze documents."},
            {
                "role": "user",
                "content": f"Please analyze this document: {large_content}",
            },
        ]

        with (
            patch.object(self.service, "_get_or_create_client") as mock_client,
            patch.object(
                self.service, "_convert_messages_to_langchain"
            ) as mock_convert,
        ):

            mock_llm_client = Mock()
            mock_response = Mock()
            mock_response.content = "Document analysis complete."
            mock_llm_client.invoke.return_value = mock_response
            mock_client.return_value = mock_llm_client
            mock_convert.return_value = [Mock()]

            # Should handle large payloads
            result = self.service.call_llm(messages=large_messages, provider="openai")

            self.assertEqual(result, "Document analysis complete.")
            # Verify large messages were processed
            mock_convert.assert_called_once_with(large_messages)


if __name__ == "__main__":
    unittest.main()
