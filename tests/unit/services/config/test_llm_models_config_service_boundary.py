"""Tests for validating dynamic LLM model configuration values."""

from unittest.mock import Mock

from agentmap.services.config.llm_models_config_service import LLMModelsConfigService


def test_non_string_fallback_model_uses_anthropic_default():
    config = Mock()
    config.get_value.side_effect = lambda path: (
        ["not-a-model-name"] if path == "routing.fallback.default_model" else None
    )

    service = LLMModelsConfigService(config)

    assert service.get_fallback_model() == "claude-sonnet-4-6"
