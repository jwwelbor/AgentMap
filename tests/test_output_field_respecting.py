# tests/test_output_field_respecting.py
"""Tests for agents respecting output_field configuration."""

import pytest

from agentmap.agents import BranchingAgent, DefaultAgent, SuccessAgent
from tests.conftest import create_test_agent


def test_default_agent_respects_output_field(test_logger, test_execution_tracker):
    """Test that DefaultAgent correctly uses the output_field from context."""
    agent = create_test_agent(
        DefaultAgent,
        name="TestAgent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "output_field": "custom_output"
        }
    )
    
    # Run the agent
    result = agent.run({})
    
    # Verify that the output is in the correct field
    assert "custom_output" in result
    assert "last_action_success" in result
    assert result["last_action_success"] is True
    # Verify the output contains expected content
    assert "TestAgent" in result["custom_output"]
    assert "DefaultAgent executed" in result["custom_output"]


def test_branching_agent_respects_output_field(test_logger, test_execution_tracker):
    """Test that BranchingAgent correctly uses the output_field from context."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestAgent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["input"],
            "output_field": "custom_output"
        }
    )
    
    # Run the agent with success input
    result = agent.run({"input": "1"})
    
    # Verify that the output is in the correct field
    assert "custom_output" in result
    assert "last_action_success" in result
    assert result["last_action_success"] is True
    # Verify the output contains expected branching content
    assert "BRANCH: TestAgent will SUCCEED" in result["custom_output"]


def test_success_agent_respects_output_field(test_logger, test_execution_tracker):
    """Test that SuccessAgent correctly uses the output_field from context."""
    agent = create_test_agent(
        SuccessAgent,
        name="Success-Agent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Testing output",
        context={
            "input_fields": ["input"],
            "output_field": "custom_output"
        }
    )
    
    # Run the agent
    result = agent.run({"input": "test_value"})
    
    # Verify that the output is in the correct field
    assert "custom_output" in result
    assert "last_action_success" in result
    assert result["last_action_success"] is True
    # Verify the output contains expected success content
    assert "SUCCESS: Success-Agent executed" in result["custom_output"]


def test_multiple_agents_different_output_fields(test_logger, test_execution_tracker):
    """Test that different agents can use different output fields."""
    # Create agents with different output fields
    default_agent = create_test_agent(
        DefaultAgent,
        name="Agent1",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test 1",
        context={"output_field": "result_a"}
    )
    
    success_agent = create_test_agent(
        SuccessAgent,
        name="Agent2",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test 2",
        context={"output_field": "result_b"}
    )
    
    # Run both agents
    result1 = default_agent.run({})
    result2 = success_agent.run({})
    
    # Verify each agent uses its specific output field
    assert "result_a" in result1
    assert "result_b" in result2
    assert "result_b" not in result1
    assert "result_a" not in result2


def test_agent_without_output_field_uses_default(test_logger, test_execution_tracker):
    """Test that agents without output_field use the default 'output' field."""
    agent = create_test_agent(
        DefaultAgent,
        name="TestAgent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test"
        # No context with output_field specified
    )
    
    # Run the agent
    result = agent.run({})
    
    # Should use default "output" field
    assert "output" in result
    assert result["last_action_success"] is True


def test_branching_agent_output_field_with_failure(test_logger, test_execution_tracker):
    """Test that BranchingAgent respects output_field even on failure."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestAgent",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["input"],
            "output_field": "branch_result"
        }
    )
    
    # Run the agent with failure input
    result = agent.run({"input": "0"})  # Should trigger failure
    
    # Verify output field is respected even for failure
    assert "branch_result" in result
    assert "last_action_success" in result
    assert result["last_action_success"] is False
    assert "BRANCH: TestAgent will FAIL" in result["branch_result"]


def test_output_field_initialization(test_logger, test_execution_tracker):
    """Test that agents correctly initialize output_field from context."""
    # Test with custom output field
    agent1 = create_test_agent(
        DefaultAgent,
        name="Agent1",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={"output_field": "my_custom_field"}
    )
    
    # Test without output field (should default to "output")
    agent2 = create_test_agent(
        DefaultAgent,
        name="Agent2",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test"
    )
    
    assert agent1.output_field == "my_custom_field"
    assert agent2.output_field == "output"  # Default value
