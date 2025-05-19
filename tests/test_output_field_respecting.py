# tests/test_output_field_respecting.py
import pytest

from agentmap.agents import BranchingAgent, DefaultAgent, SuccessAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)

def test_default_agent_respects_output_field():
    """Test that agents correctly use the output_field from context."""
    # Create an agent with a specific output field
    agent = DefaultAgent(name="TestAgent", prompt="Test", context={
        "output_field": "custom_output"
    })
    
    # Run the agent
    result = agent.run({})
    
    # Verify that the output is in the correct field
    assert "custom_output" in result
    assert "[TestAgent] DefaultAgent executed with prompt: 'Test'" == result["custom_output"]
    assert "last_action_success" in result
    assert result["last_action_success"] is True

def test_branching_agent_respects_output_field():
    """Test that agents correctly use the output_field from context."""
    # Create an agent with a specific output field
    agent = BranchingAgent(name="TestAgent", prompt="Test", context={
        "input_fields": ["input"],
        "output_field": "custom_output"
    })
    
    # Run the agent
    result = agent.run({input: "1"})
    
    # Verify that the output is in the correct field
    assert "custom_output" in result
    assert "BRANCH: TestAgent will SUCCEED based on inputs: [input=None] with prompt: 'Test' (Will trigger SUCCESS branch)" == result["custom_output"]
    logger.info(f"result: {result}")
    assert "last_action_success" in result
    assert result["last_action_success"] is True


def test_success_agent_respects_output_field():
    """Test that agents correctly use the output_field from context."""
    # Create an agent with a specific output field
    agent = SuccessAgent(name="Success-Agent", prompt="Testing output", context={
        "input_fields": ["input"],
        "output_field": "custom_output"
    })
    
    # Run the agent
    result = agent.run({input: "1"})
    
    # Verify that the output is in the correct field
    assert "custom_output" in result
    assert "SUCCESS: Success-Agent executed with inputs: input=None with prompt: 'Testing output'" == result["custom_output"]
    logger.info(f"result: {result}")
    assert "last_action_success" in result
    assert result["last_action_success"] is True