# tests/test_input_agent.py
from unittest.mock import patch

import pytest

from agentmap.agents.builtins.input_agent import InputAgent


def test_input_agent_process():
    # Create the agent
    agent = InputAgent(name="UserInput", prompt="Enter data: ", context={
        "output_field": "user_response"
    })
    
    # Mock the input function to return a predefined value
    with patch('builtins.input', return_value="test input"):
        # Process with empty inputs
        result = agent.process({})
        
        # Check that the result matches our mocked input
        assert result == "test input"

def test_input_agent_run():
    # Create the agent
    agent = InputAgent(name="UserInput", prompt="Enter data: ", context={
        "output_field": "user_response"
    })
    
    # Mock the input function
    with patch('builtins.input', return_value="test input"):
        # Run with an initial state
        initial_state = {"some_field": "initial value"}
        result = agent.run(initial_state)
        
        # Check that the state was updated correctly
        assert result["user_response"] == "test input"
        assert result["last_action_success"] is True
        assert result["some_field"] == "initial value"  # Original fields preserved