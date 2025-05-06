import pytest

from agentmap.agents.builtins.echo_agent import EchoAgent


def test_echo_agent_with_single_input():
    # Create an echo agent
    agent = EchoAgent(name="Echo", prompt="", context={
        "input_fields": ["message"],
        "output_field": "response"
    })
    
    # Create state with a message
    state = {"message": "Hello, world!"}
    
    # Run the agent
    result = agent.run(state)
    
    # Check that the output contains the input
    assert "response" in result
    assert result["response"] == {"message": "Hello, world!"}
    assert result["last_action_success"] is True

def test_echo_agent_with_multiple_inputs():
    # Create an echo agent with multiple input fields
    agent = EchoAgent(name="Echo", prompt="", context={
        "input_fields": ["message", "sender"],
        "output_field": "response"
    })
    
    # Create state with multiple inputs
    state = {
        "message": "Hello, world!",
        "sender": "Test"
    }
    
    # Run the agent
    result = agent.run(state)
    
    # Check that all inputs were included in the output
    assert "response" in result
    assert result["response"] == {
        "message": "Hello, world!",
        "sender": "Test"
    }
    assert result["last_action_success"] is True

def test_echo_agent_with_no_inputs():
    # Create an echo agent with no inputs defined
    agent = EchoAgent(name="Echo", prompt="", context={
        "output_field": "response"
    })
    
    # Run the agent with empty state
    result = agent.run({})
    
    # Check the default response
    assert "response" in result
    assert result["response"] == "No input provided to echo"
    assert result["last_action_success"] is True