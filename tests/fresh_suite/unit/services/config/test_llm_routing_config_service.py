"""
Test suite for LlmRoutingConfigService - LLM routing configuration testing.

This module tests the LlmRoutingConfigService which handles LLM provider
routing configuration, provider selection, and routing logic.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

from agentmap.services.logging_service import LoggingService
from src.agentmap.services.config.app_config_service import AppConfigService
from src.agentmap.services.config.llm_routing_config_service import (
    LLMRoutingConfigService,
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestLlmRoutingConfigService(unittest.TestCase):
    """Test suite for LlmRoutingConfigService - LLM routing configuration."""

    def setUp(self):
        """Set up test fixtures with mock service factory."""
        self.mock_factory = MockServiceFactory()
        # Create mock services
        self.mock_app_config_service = Mock(spec=AppConfigService)
        self.mock_logging_service = self.mock_factory.create_mock_logging_service()
        self.mock_llm_models_config_service = (
            self.mock_factory.create_mock_llm_models_config_service()
        )

        # Set up routing configuration
        self.routing_config = {
            "enabled": True,
            "routing_matrix": {
                "anthropic": {
                    "low": "claude-3-haiku-20240307",
                    "medium": "claude-3-5-sonnet-20241022",
                    "high": "claude-3-opus-20240229",
                    "critical": "claude-3-opus-20240229",
                },
                "openai": {
                    "low": "gpt-3.5-turbo",
                    "medium": "gpt-4",
                    "high": "gpt-4",
                    "critical": "gpt-4-turbo",
                },
            },
            "task_types": {
                "general": {
                    "description": "General purpose tasks",
                    "provider_preference": ["anthropic", "openai"],
                    "default_complexity": "medium",
                    "complexity_keywords": {
                        "low": ["simple", "basic"],
                        "high": ["complex", "detailed"],
                    },
                },
                "analysis": {
                    "description": "Analysis tasks",
                    "provider_preference": ["openai", "anthropic"],
                    "default_complexity": "high",
                },
            },
            "complexity_analysis": {
                "prompt_length_thresholds": {"low": 100, "medium": 300, "high": 800}
            },
            "cost_optimization": {"enabled": True, "max_cost_tier": "high"},
            "fallback": {
                "default_provider": "anthropic",
                "default_model": "claude-3-haiku-20240307",
            },
            "performance": {"enable_routing_cache": True, "cache_ttl": 300},
        }

        self.mock_app_config_service.get_routing_config.return_value = (
            self.routing_config
        )

        self.llm_routing_service = LLMRoutingConfigService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            llm_models_config_service=self.mock_llm_models_config_service,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        pass

    def test_initialization_success(self):
        """Test successful initialization with valid config."""
        self.assertIsNotNone(self.llm_routing_service)
        self.assertTrue(self.llm_routing_service.enabled)
        self.assertIsInstance(self.llm_routing_service.routing_matrix, dict)
        self.assertIsInstance(self.llm_routing_service.task_types, dict)

    def test_get_model_for_complexity(self):
        """Test getting model for specific provider and complexity."""
        # Test valid provider and complexity
        result = self.llm_routing_service.get_model_for_complexity(
            "anthropic", "medium"
        )
        self.assertEqual(result, "claude-3-5-sonnet-20241022")

        result = self.llm_routing_service.get_model_for_complexity("openai", "high")
        self.assertEqual(result, "gpt-4")

        # Test case insensitive
        result = self.llm_routing_service.get_model_for_complexity("ANTHROPIC", "LOW")
        self.assertEqual(result, "claude-3-haiku-20240307")

        # Test non-existing provider
        result = self.llm_routing_service.get_model_for_complexity("missing", "medium")
        self.assertIsNone(result)

        # Test non-existing complexity
        result = self.llm_routing_service.get_model_for_complexity(
            "anthropic", "unknown"
        )
        self.assertIsNone(result)

    def test_get_task_type_config(self):
        """Test getting task type configuration."""
        # Test existing task type
        result = self.llm_routing_service.get_task_type_config("general")
        expected = {
            "description": "General purpose tasks",
            "provider_preference": ["anthropic", "openai"],
            "default_complexity": "medium",
            "complexity_keywords": {
                "low": ["simple", "basic"],
                "high": ["complex", "detailed"],
            },
        }
        self.assertEqual(result, expected)

        # Test non-existing task type (should return general)
        result = self.llm_routing_service.get_task_type_config("missing")
        self.assertEqual(result, self.llm_routing_service.task_types["general"])

    def test_get_provider_preference(self):
        """Test getting provider preference for task type."""
        result = self.llm_routing_service.get_provider_preference("general")
        self.assertEqual(result, ["anthropic", "openai"])

        result = self.llm_routing_service.get_provider_preference("analysis")
        self.assertEqual(result, ["openai", "anthropic"])

        # Test non-existing task type
        result = self.llm_routing_service.get_provider_preference("missing")
        self.assertEqual(result, ["anthropic", "openai"])  # Falls back to general

    def test_get_default_complexity(self):
        """Test getting default complexity for task type."""
        result = self.llm_routing_service.get_default_complexity("general")
        self.assertEqual(result, "medium")

        result = self.llm_routing_service.get_default_complexity("analysis")
        self.assertEqual(result, "high")

        # Test non-existing task type
        result = self.llm_routing_service.get_default_complexity("missing")
        self.assertEqual(result, "medium")  # Falls back to general

    def test_get_complexity_keywords(self):
        """Test getting complexity keywords for task type."""
        result = self.llm_routing_service.get_complexity_keywords("general")
        expected = {"low": ["simple", "basic"], "high": ["complex", "detailed"]}
        self.assertEqual(result, expected)

        # Test task type without keywords
        result = self.llm_routing_service.get_complexity_keywords("analysis")
        self.assertEqual(result, {})

    def test_get_available_providers(self):
        """Test getting list of available providers."""
        result = self.llm_routing_service.get_available_providers()
        self.assertEqual(set(result), {"anthropic", "openai"})

    def test_get_available_task_types(self):
        """Test getting list of available task types."""
        result = self.llm_routing_service.get_available_task_types()
        self.assertEqual(set(result), {"general", "analysis"})

    def test_is_provider_available(self):
        """Test checking if provider is available."""
        self.assertTrue(self.llm_routing_service.is_provider_available("anthropic"))
        self.assertTrue(self.llm_routing_service.is_provider_available("openai"))
        self.assertTrue(
            self.llm_routing_service.is_provider_available("ANTHROPIC")
        )  # Case insensitive

        self.assertFalse(self.llm_routing_service.is_provider_available("missing"))

    def test_get_fallback_provider(self):
        """Test getting fallback provider."""
        result = self.llm_routing_service.get_fallback_provider()
        self.assertEqual(result, "anthropic")

    def test_get_fallback_model(self):
        """Test getting fallback model."""
        result = self.llm_routing_service.get_fallback_model()
        self.assertEqual(result, "claude-3-haiku-20240307")

    def test_is_cost_optimization_enabled(self):
        """Test checking if cost optimization is enabled."""
        result = self.llm_routing_service.is_cost_optimization_enabled()
        self.assertTrue(result)

    def test_get_max_cost_tier(self):
        """Test getting maximum cost tier."""
        result = self.llm_routing_service.get_max_cost_tier()
        self.assertEqual(result, "high")

    def test_is_routing_cache_enabled(self):
        """Test checking if routing cache is enabled."""
        result = self.llm_routing_service.is_routing_cache_enabled()
        self.assertTrue(result)

    def test_get_cache_ttl(self):
        """Test getting cache TTL."""
        result = self.llm_routing_service.get_cache_ttl()
        self.assertEqual(result, 300)

    def test_validate_config_success(self):
        """Test configuration validation with valid config."""
        errors = self.llm_routing_service.validate_AppConfigService()
        self.assertEqual(errors, [])

    def test_validate_config_empty_routing_matrix(self):
        """Test validation with empty routing matrix."""
        # Set up config with empty routing matrix
        self.routing_config["routing_matrix"] = {}
        self.mock_app_config_service.get_routing_config.return_value = (
            self.routing_config
        )

        service = LLMRoutingConfigService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            llm_models_config_service=self.mock_llm_models_config_service,
        )

        errors = service.validate_AppConfigService()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("Routing matrix is empty" in error for error in errors))

    def test_validate_config_missing_complexity_levels(self):
        """Test validation with missing complexity levels."""
        # Set up config with incomplete routing matrix
        self.routing_config["routing_matrix"] = {
            "anthropic": {
                "low": "claude-3-haiku-20240307"
                # Missing medium, high, critical
            }
        }
        self.mock_app_config_service.get_routing_config.return_value = (
            self.routing_config
        )

        service = LLMRoutingConfigService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            llm_models_config_service=self.mock_llm_models_config_service,
        )

        errors = service.validate_AppConfigService()
        self.assertGreater(len(errors), 0)
        self.assertTrue(
            any("missing model for complexity" in error for error in errors)
        )

    def test_validate_config_invalid_complexity_level(self):
        """Test validation with invalid complexity levels."""
        # Set up config with invalid complexity level
        self.routing_config["routing_matrix"] = {
            "anthropic": {"invalid_level": "claude-3-haiku-20240307"}
        }
        self.mock_app_config_service.get_routing_config.return_value = (
            self.routing_config
        )

        service = LLMRoutingConfigService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            llm_models_config_service=self.mock_llm_models_config_service,
        )

        errors = service.validate_AppConfigService()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("invalid complexity level" in error for error in errors))

    def test_validate_config_unknown_provider_reference(self):
        """Test validation with task type referencing unknown provider."""
        # Set up config with task type referencing unknown provider
        self.routing_config["task_types"]["general"]["provider_preference"] = [
            "unknown_provider"
        ]
        self.mock_app_config_service.get_routing_config.return_value = (
            self.routing_config
        )

        service = LLMRoutingConfigService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            llm_models_config_service=self.mock_llm_models_config_service,
        )

        errors = service.validate_AppConfigService()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("references unknown provider" in error for error in errors))

    def test_validate_config_missing_prompt_thresholds(self):
        """Test validation with missing prompt length thresholds."""
        # Set up config with incomplete thresholds
        self.routing_config["complexity_analysis"]["prompt_length_thresholds"] = {
            "low": 100
            # Missing medium, high
        }
        self.mock_app_config_service.get_routing_config.return_value = (
            self.routing_config
        )

        service = LLMRoutingConfigService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            llm_models_config_service=self.mock_llm_models_config_service,
        )

        errors = service.validate_AppConfigService()
        self.assertGreater(len(errors), 0)
        self.assertTrue(
            any("Missing prompt length threshold" in error for error in errors)
        )

    def test_routing_matrix_normalization(self):
        """Test that routing matrix keys are normalized to lowercase."""
        # Set up config with mixed case
        config_with_mixed_case = {
            "enabled": True,
            "routing_matrix": {
                "ANTHROPIC": {
                    "LOW": "claude-3-haiku-20240307",
                    "MEDIUM": "claude-3-5-sonnet-20241022",
                }
            },
            "task_types": {},
            "complexity_analysis": {},
            "fallback": {},
        }

        self.mock_app_config_service.get_routing_config.return_value = (
            config_with_mixed_case
        )

        service = LLMRoutingConfigService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            llm_models_config_service=self.mock_llm_models_config_service,
        )

        # Keys should be normalized to lowercase
        self.assertIn("anthropic", service.routing_matrix)
        self.assertIn("low", service.routing_matrix["anthropic"])
        self.assertIn("medium", service.routing_matrix["anthropic"])

    def test_task_type_validation(self):
        """Test task type configuration validation."""
        # Test with invalid task type (missing required fields)
        invalid_config = self.routing_config.copy()
        invalid_config["task_types"]["invalid"] = {
            "description": "Invalid task type"
            # Missing required fields: provider_preference, default_complexity
        }

        self.mock_app_config_service.get_routing_config.return_value = invalid_config

        service = LLMRoutingConfigService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            llm_models_config_service=self.mock_llm_models_config_service,
        )

        # Invalid task type should be filtered out
        self.assertNotIn("invalid", service.task_types)


if __name__ == "__main__":
    unittest.main()
