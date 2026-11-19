"""Boundary tests for dynamically loaded LLM provider configuration."""

from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm_provider_utils import LLMProviderUtils


def test_non_mapping_provider_config_raises_configuration_error():
    app_config = Mock()
    app_config.get_llm_config.return_value = ["invalid"]
    logging_service = Mock()
    logging_service.get_class_logger.return_value = Mock()

    provider_utils = LLMProviderUtils(app_config, Mock(), logging_service)

    with pytest.raises(LLMConfigurationError, match="No configuration found"):
        provider_utils.get_provider_config("openai")
