# tests/test_branching_agent.py
"""Tests for BranchingAgent functionality."""

import pytest
from agentmap.agents.builtins.branching_agent import BranchingAgent
from tests.conftest import create_test_agent


def test_branching_agent_initialization(test_logger, test_execution_tracker):
    """Test that the BranchingAgent initializes correctly with proper dependencies."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test branching",
        context={
            "input_fields": ["input", "success"],
            "output_field": "output"
        }
    )
    
    assert agent.name == "TestBranch"
    assert agent.prompt == "Test branching"
    assert "input" in agent.input_fields
    assert "success" in agent.input_fields
    assert agent.output_field == "output"


def test_branching_agent_success_with_truthy_values(test_logger, test_execution_tracker):
    """Test that BranchingAgent correctly handles truthy success indicators."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["input"],
            "output_field": "output"
        }
    )
    
    # Test with truthy input value (1)
    result = agent.run({"input": "1"})
    
    assert result["last_action_success"] is True
    assert "output" in result
    assert "SUCCEED" in result["output"]
    assert "BRANCH: TestBranch will SUCCEED" in result["output"]


def test_branching_agent_success_with_boolean_true(test_logger, test_execution_tracker):
    """Test that BranchingAgent correctly handles explicit boolean True."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["success"],
            "output_field": "output"
        }
    )
    
    result = agent.run({"success": True})
    
    assert result["last_action_success"] is True
    assert "SUCCEED" in result["output"]


def test_branching_agent_success_with_string_values(test_logger, test_execution_tracker):
    """Test that BranchingAgent correctly handles string success indicators."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["input"],
            "output_field": "output"
        }
    )
    
    # Test various success strings
    for success_value in ["true", "yes", "success", "succeed", "t", "y"]:
        result = agent.run({"input": success_value})
        assert result["last_action_success"] is True, f"Failed for success value: {success_value}"
        assert "SUCCEED" in result["output"]


def test_branching_agent_failure_with_falsy_values(test_logger, test_execution_tracker):
    """Test that BranchingAgent correctly handles falsy failure indicators."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["input"],
            "output_field": "output"
        }
    )
    
    # Test with falsy value (0)
    result = agent.run({"input": 0})
    
    assert result["last_action_success"] is False
    assert "output" in result
    assert "FAIL" in result["output"]
    assert "BRANCH: TestBranch will FAIL" in result["output"]


def test_branching_agent_failure_with_boolean_false(test_logger, test_execution_tracker):
    """Test that BranchingAgent correctly handles explicit boolean False."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["success"],
            "output_field": "output"
        }
    )
    
    result = agent.run({"success": False})
    
    assert result["last_action_success"] is False
    assert "FAIL" in result["output"]


def test_branching_agent_failure_with_string_values(test_logger, test_execution_tracker):
    """Test that BranchingAgent correctly handles string failure indicators."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["input"],
            "output_field": "output"
        }
    )
    
    # Test various failure strings
    for failure_value in ["false", "no", "0", "f", "n"]:
        result = agent.run({"input": failure_value})
        assert result["last_action_success"] is False, f"Failed for failure value: {failure_value}"
        assert "FAIL" in result["output"]


def test_branching_agent_alternative_field_names(test_logger, test_execution_tracker):
    """Test that BranchingAgent works with alternative success field names."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["should_succeed"],
            "output_field": "output"
        }
    )
    
    # Test success with alternative field name
    result = agent.run({"should_succeed": True})
    assert result["last_action_success"] is True
    assert "SUCCEED" in result["output"]
    
    # Test failure with alternative field name
    result = agent.run({"should_succeed": False})
    assert result["last_action_success"] is False
    assert "FAIL" in result["output"]


def test_branching_agent_default_behavior_empty_input(test_logger, test_execution_tracker):
    """Test that BranchingAgent defaults to success when no relevant fields are provided."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["irrelevant"],
            "output_field": "output"
        }
    )
    
    result = agent.run({"irrelevant": "some value"})
    
    # Should default to success when no success indicators found
    assert result["last_action_success"] is True
    assert "SUCCEED" in result["output"]


def test_branching_agent_includes_inputs_in_output(test_logger, test_execution_tracker):
    """Test that BranchingAgent includes input information in its output."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={
            "input_fields": ["input", "success", "extra"],
            "output_field": "output"
        }
    )
    
    result = agent.run({
        "input": "Test input",
        "success": True,
        "extra": "Extra info"
    })
    
    # Verify output contains input information
    output = result["output"]
    assert "input=Test input" in output
    assert "success=True" in output
    assert "extra=Extra info" in output
    assert "prompt: 'Test prompt'" in output
    assert result["last_action_success"] is True


def test_branching_agent_multiple_success_fields(test_logger, test_execution_tracker):
    """Test BranchingAgent behavior when multiple success-related fields are present."""
    agent = create_test_agent(
        BranchingAgent,
        name="TestBranch",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test",
        context={
            "input_fields": ["input", "success", "should_succeed"],
            "output_field": "output"
        }
    )
    
    # When input field comes first and is truthy, should succeed
    result = agent.run({
        "input": "yes",
        "success": False,  # This should be ignored since input is checked first
        "should_succeed": False
    })
    
    assert result["last_action_success"] is True
    assert "SUCCEED" in result["output"]
