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
