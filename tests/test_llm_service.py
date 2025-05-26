"""
Simple integration test for LLMService.

This test verifies that the LLMService can be created and used correctly
with the existing system.
"""
import os
from unittest.mock import Mock, patch
import pytest

from agentmap.services.llm_service import LLMService
from agentmap.exceptions import LLMConfigurationError, LLMDependencyError


def test_llm_service_creation():
    """Test that LLMService can be created."""
    # Mock the dependencies
    config_mock = Mock()
    config_mock.get_llm_config.return_value = {
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "api_key": "test-key"
    }
    
    logging_mock = Mock()
    logging_mock.get_class_logger.return_value = Mock()
    
    service = LLMService(config_mock, logging_mock)
    assert service is not None


def test_provider_normalization():
    """Test provider name normalization and aliases."""
    config_mock = Mock()
    logging_mock = Mock()
    logging_mock.get_class_logger.return_value = Mock()
    
    service = LLMService(config_mock, logging_mock)
    
    # Test aliases
    assert service._normalize_provider("gpt") == "openai"
    assert service._normalize_provider("claude") == "anthropic" 
    assert service._normalize_provider("gemini") == "google"
    
    # Test direct names
    assert service._normalize_provider("openai") == "openai"
    assert service._normalize_provider("anthropic") == "anthropic"


def test_provider_defaults():
    """Test provider default configurations."""
    config_mock = Mock()
    logging_mock = Mock()
    logging_mock.get_class_logger.return_value = Mock()
    
    service = LLMService(config_mock, logging_mock)
    
    openai_defaults = service._get_provider_defaults("openai")
    assert "model" in openai_defaults
    assert "temperature" in openai_defaults
    assert openai_defaults["model"] == "gpt-3.5-turbo"
    
    anthropic_defaults = service._get_provider_defaults("anthropic")
    assert anthropic_defaults["model"] == "claude-3-sonnet-20240229"


def test_configuration_error_handling():
    """Test configuration error handling."""
    config_mock = Mock()
    config_mock.get_llm_config.return_value = {}  # Empty config
    
    logging_mock = Mock()
    logging_mock.get_class_logger.return_value = Mock()
    
    service = LLMService(config_mock, logging_mock)
    
    with pytest.raises(LLMConfigurationError):
        service._get_provider_config("nonexistent")

if __name__ == "__main__":
    # Run basic tests
    test_llm_service_creation()
    test_provider_normalization()
    test_provider_defaults()
    print("✅ Basic LLMService tests passed!")