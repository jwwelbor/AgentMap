import pytest
from unittest.mock import patch, MagicMock
import json

from agentmap.agents.builtins.summary_agent import SummaryAgent
from agentmap.agents.builtins.llm.llm_agent import LLMAgent

from agentmap.di import initialize_di

class MockLLMAgent(LLMAgent):
    """Mock LLM agent for testing."""
    
    def __init__(self, name, prompt, context=None):
        super().__init__(name, prompt, context)
        self.process_called = False
        self.last_input = None
        self.mock_response = "This is a summarized version of the content."
    
    def _get_provider_name(self):
        return "mock"
    
    def _get_api_key_env_var(self):
        return "MOCK_API_KEY"
    
    def _get_default_model_name(self):
        return "mock-model"
    
    def _call_api(self, formatted_prompt):
        return self.mock_response
    
    def _create_langchain_client(self):
        return None
    
    def process(self, inputs):
        self.process_called = True
        self.last_input = inputs
        return self.mock_response


class TestSummaryAgent:
    """Test suite for SummaryAgent."""
    
    def test_init_default_params(self):
        """Test initialization with default parameters."""
        agent = SummaryAgent("test_agent", "Test prompt")
        
        assert agent.name == "test_agent"
        assert agent.prompt == "Test prompt"
        assert agent.format_template == "{key}: {value}"
        assert agent.separator == "\n\n"
        assert agent.include_keys is True
        assert agent.use_llm is False
    
    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        context = {
            "format": "Key: {key} | Value: {value}",
            "separator": "\n---\n",
            "include_keys": False
        }
        agent = SummaryAgent("test_agent", "Test prompt", context)
        
        assert agent.format_template == "Key: {key} | Value: {value}"
        assert agent.separator == "\n---\n"
        assert agent.include_keys is False
    
    def test_basic_concatenation_default(self):
        """Test basic concatenation with default configuration."""
        agent = SummaryAgent("test_agent", "Test prompt")
        inputs = {"field1": "value1", "field2": "value2"}
        
        result = agent.process(inputs)
        
        assert "field1: value1" in result
        assert "field2: value2" in result
        assert result.count("\n\n") == 1  # Check separator
    
    def test_basic_concatenation_custom_format(self):
        """Test basic concatenation with custom format."""
        context = {"format": "[{key}] -> {value}"}
        agent = SummaryAgent("test_agent", "Test prompt", context)
        inputs = {"field1": "value1", "field2": "value2"}
        
        result = agent.process(inputs)
        
        assert "[field1] -> value1" in result
        assert "[field2] -> value2" in result
    
    def test_basic_concatenation_custom_separator(self):
        """Test basic concatenation with custom separator."""
        context = {"separator": " | "}
        agent = SummaryAgent("test_agent", "Test prompt", context)
        inputs = {"field1": "value1", "field2": "value2"}
        
        result = agent.process(inputs)
        
        assert " | " in result
        assert result.count(" | ") == 1  # Check separator count
    
    def test_basic_concatenation_without_keys(self):
        """Test basic concatenation without including keys."""
        context = {"include_keys": False}
        agent = SummaryAgent("test_agent", "Test prompt", context)
        inputs = {"field1": "value1", "field2": "value2"}
        
        result = agent.process(inputs)
        
        assert "field1" not in result
        assert "field2" not in result
        assert "value1" in result
        assert "value2" in result
    
    def test_empty_inputs(self):
        """Test with empty inputs."""
        agent = SummaryAgent("test_agent", "Test prompt")
        result = agent.process({})
        
        assert result == ""
    
    def test_none_value(self):
        """Test with None value in inputs."""
        agent = SummaryAgent("test_agent", "Test prompt")
        inputs = {"field1": "value1", "field2": None}
        
        result = agent.process(inputs)
        
        assert "field1: value1" in result
        assert "field2" not in result  # None values should be skipped
    
    def test_formatting_error(self):
        """Test handling of formatting errors."""
        context = {"format": "{key}: {value} {extra}"}  # Extra param will cause error
        agent = SummaryAgent("test_agent", "Test prompt", context)
        inputs = {"field1": "value1"}
        
        # Should fall back to "key: value" format
        result = agent.process(inputs)
        
        assert "field1: value1" in result
    
    @patch("agentmap.agents.HAS_LLM_AGENTS", False)
    def test_llm_mode_dependencies_missing(self):
        """Test LLM mode when dependencies are missing."""
        context = {"llm": "openai"}
        agent = SummaryAgent("test_agent", "Test prompt", context)
        inputs = {"field1": "value1", "field2": "value2"}
        
        # Should fall back to basic concatenation
        result = agent.process(inputs)
        
        assert "field1: value1" in result
        assert "field2: value2" in result
    
if __name__ == "__main__":
    pytest.main(["-xvs", __file__])