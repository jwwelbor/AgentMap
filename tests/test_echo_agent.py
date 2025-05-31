# tests/test_echo_agent.py
"""Tests for EchoAgent functionality."""

import pytest
from agentmap.agents.builtins.echo_agent import EchoAgent
from tests.conftest import create_test_agent


def test_echo_agent_with_single_input(test_logger, test_execution_tracker):
    """Test that EchoAgent correctly echoes a single input field."""
    agent = create_test_agent(
        EchoAgent,
        name="Echo",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="",
        context={
            "input_fields": ["message"],
            "output_field": "response"
        }
    )
    
    # Create state with a message
    state = {"message": "Hello, world!"}
    
    # Run the agent
    result = agent.run(state)
    
    # Check that the output contains the input
    assert "response" in result
    assert result["response"] == {"message": "Hello, world!"}
    assert result["last_action_success"] is True


def test_echo_agent_with_multiple_inputs(test_logger, test_execution_tracker):
    """Test that EchoAgent correctly echoes multiple input fields."""
    agent = create_test_agent(
        EchoAgent,
        name="Echo",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="",
        context={
            "input_fields": ["message", "sender"],
            "output_field": "response"
        }
    )
    
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


def test_echo_agent_with_no_inputs(test_logger, test_execution_tracker):
    """Test that EchoAgent handles empty input gracefully."""
    agent = create_test_agent(
        EchoAgent,
        name="Echo",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="",
        context={
            "output_field": "response"
        }
    )
    
    # Run the agent with empty state
    result = agent.run({})
    
    # Check the default response
    assert "response" in result
    assert result["response"] == "No input provided to echo"
    assert result["last_action_success"] is True


def test_echo_agent_with_missing_input_fields(test_logger, test_execution_tracker):
    """Test that EchoAgent handles missing input fields correctly."""
    agent = create_test_agent(
        EchoAgent,
        name="Echo",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="",
        context={
            "input_fields": ["message", "nonexistent"],
            "output_field": "response"
        }
    )
    
    # Create state with only one of the expected fields
    state = {"message": "Hello!"}
    
    # Run the agent
    result = agent.run(state)
    
    # Should only echo the fields that exist
    assert "response" in result
    assert result["response"] == {"message": "Hello!"}
    assert result["last_action_success"] is True


def test_echo_agent_initialization(test_logger, test_execution_tracker):
    """Test that EchoAgent initializes correctly with proper dependencies."""
    agent = create_test_agent(
        EchoAgent,
        name="TestEcho",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={
            "input_fields": ["test_input"],
            "output_field": "test_output"
        }
    )
    
    assert agent.name == "TestEcho"
    assert agent.prompt == "Test prompt"
    assert agent.input_fields == ["test_input"]
    assert agent.output_field == "test_output"
    assert agent._logger is not None
    assert agent._execution_tracker is not None
