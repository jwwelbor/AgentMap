# tests/test_input_agent.py
"""Tests for InputAgent functionality."""

import pytest
from unittest.mock import patch

from agentmap.agents.builtins.input_agent import InputAgent
from tests.conftest import create_test_agent


def test_input_agent_basic_functionality(test_logger, test_execution_tracker):
    """Test that InputAgent correctly prompts for and returns user input."""
    agent = create_test_agent(
        InputAgent,
        name="UserInput",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Enter data: ",
        context={
            "output_field": "user_response"
        }
    )
    
    # Mock the input function to return a predefined value
    with patch('builtins.input', return_value="test input"):
        result = agent.run({})
        
        # Check that the agent returns the mocked input
        assert "user_response" in result
        assert result["user_response"] == "test input"
        assert result["last_action_success"] is True


def test_input_agent_with_custom_prompt(test_logger, test_execution_tracker):
    """Test that InputAgent uses the provided prompt correctly."""
    custom_prompt = "Please enter your name: "
    
    agent = create_test_agent(
        InputAgent,
        name="NameInput",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt=custom_prompt,
        context={
            "output_field": "user_name"
        }
    )
    
    # Mock the input function and verify prompt is used
    with patch('builtins.input', return_value="John Doe") as mock_input:
        result = agent.run({})
        
        # Verify the prompt was passed to input()
        mock_input.assert_called_once_with(custom_prompt)
        
        # Check the result
        assert result["user_name"] == "John Doe"
        assert result["last_action_success"] is True


def test_input_agent_empty_input(test_logger, test_execution_tracker):
    """Test that InputAgent handles empty input correctly."""
    agent = create_test_agent(
        InputAgent,
        name="UserInput",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Enter something: ",
        context={
            "output_field": "user_response"
        }
    )
    
    # Mock empty input
    with patch('builtins.input', return_value=""):
        result = agent.run({})
        
        # Should handle empty input gracefully
        assert result["user_response"] == ""
        assert result["last_action_success"] is True


def test_input_agent_ignores_existing_state(test_logger, test_execution_tracker):
    """Test that InputAgent ignores existing state and always prompts."""
    agent = create_test_agent(
        InputAgent,
        name="UserInput",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Enter data: ",
        context={
            "output_field": "user_response"
        }
    )
    
    # Mock input with existing state data
    with patch('builtins.input', return_value="new input"):
        result = agent.run({"existing_data": "should be ignored"})
        
        # Should return new input, not existing data
        assert result["user_response"] == "new input"
        assert result["last_action_success"] is True


def test_input_agent_initialization(test_logger, test_execution_tracker):
    """Test that InputAgent initializes correctly with proper dependencies."""
    agent = create_test_agent(
        InputAgent,
        name="TestInput",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt: ",
        context={
            "output_field": "test_output"
        }
    )
    
    assert agent.name == "TestInput"
    assert agent.prompt == "Test prompt: "
    assert agent.output_field == "test_output"
    assert agent._logger is not None
    assert agent._execution_tracker is not None
