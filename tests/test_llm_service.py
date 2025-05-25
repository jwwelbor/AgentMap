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


@patch('agentmap.services.llm_service.ChatOpenAI')
def test_openai_client_creation(mock_chat_openai):
    """Test OpenAI client creation."""
    config_mock = Mock()
    config_mock.get_llm_config.return_value = {
        "model": "gpt-4",
        "temperature": 0.5,
        "api_key": "test-openai-key"
    }
    
    logging_mock = Mock()
    logging_mock.get_class_logger.return_value = Mock()
    
    service = LLMService(config_mock, logging_mock)
    
    # Mock successful client creation
    mock_client = Mock()
    mock_chat_openai.return_value = mock_client
    
    client = service._create_openai_client("test-key", "gpt-4", 0.5)
    
    # Verify client creation was called correctly
    mock_chat_openai.assert_called_once_with(
        model_name="gpt-4",
        temperature=0.5,
        openai_api_key="test-key"
    )
    
    assert client == mock_client


def test_configuration_error_handling():
    """Test configuration error handling."""
    config_mock = Mock()
    config_mock.get_llm_config.return_value = {}  # Empty config
    
    logging_mock = Mock()
    logging_mock.get_class_logger.return_value = Mock()
    
    service = LLMService(config_mock, logging_mock)
    
    with pytest.raises(LLMConfigurationError):
        service._get_provider_config("nonexistent")


@patch('agentmap.services.llm_service.ChatOpenAI')
def test_call_llm_success(mock_chat_openai):
    """Test successful LLM call."""
    config_mock = Mock()
    config_mock.get_llm_config.return_value = {
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "api_key": "test-key"
    }
    
    logging_mock = Mock()
    logger_mock = Mock()
    logging_mock.get_class_logger.return_value = logger_mock
    
    service = LLMService(config_mock, logging_mock)
    
    # Mock the client and response
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = "Test response"
    mock_client.invoke.return_value = mock_response
    mock_chat_openai.return_value = mock_client
    
    messages = [{"role": "user", "content": "Hello"}]
    result = service.call_llm("openai", messages)
    
    assert result == "Test response"
    mock_client.invoke.assert_called_once_with(messages)


def test_summary_agent_integration():
    """Test that SummaryAgent can use LLMService."""
    from agentmap.agents.builtins.summary_agent import SummaryAgent
    
    # Create agent with LLM mode
    agent = SummaryAgent(
        name="test_summary",
        prompt="Summarize this content",
        context={"llm": "openai"}
    )
    
    # Mock the LLM service
    mock_service = Mock()
    mock_service.call_llm.return_value = "This is a test summary"
    agent.llm_service = mock_service
    
    # Test inputs
    inputs = {
        "field1": "Some content",
        "field2": "More content"
    }
    
    result = agent.process(inputs)
    
    # Verify service was called
    mock_service.call_llm.assert_called_once()
    call_args = mock_service.call_llm.call_args
    assert call_args[1]["provider"] == "openai"
    assert len(call_args[1]["messages"]) == 2
    
    assert result == "This is a test summary"


def test_orchestrator_agent_integration():
    """Test that OrchestratorAgent can use LLMService."""
    from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
    
    # Create agent
    agent = OrchestratorAgent(
        name="test_orchestrator", 
        prompt="Select the best node",
        context={"llm_type": "anthropic", "matching_strategy": "llm"}
    )
    
    # Mock the LLM service
    mock_service = Mock()
    mock_service.call_llm.return_value = "Selected: node2"
    agent.llm_service = mock_service
    
    # Test inputs
    inputs = {
        "available_nodes": {
            "node1": {"description": "First node"},
            "node2": {"description": "Second node"}
        },
        "input": "I need the second option"
    }
    
    result = agent.process(inputs)
    
    # Verify service was called
    mock_service.call_llm.assert_called_once()
    call_args = mock_service.call_llm.call_args
    assert call_args[1]["provider"] == "anthropic"
    
    assert result == "node2"


if __name__ == "__main__":
    # Run basic tests
    test_llm_service_creation()
    test_provider_normalization()
    test_provider_defaults()
    print("✅ Basic LLMService tests passed!")