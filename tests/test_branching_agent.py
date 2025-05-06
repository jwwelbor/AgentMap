# tests/test_branching_agent.py
import pytest

from agentmap.agents.builtins.branching_agent import BranchingAgent


# success values - ['true', 'yes', 'success', 'succeed', '1', 't', 'y']
def test_branching_agent_initialization():
    """Test that the BranchingAgent initializes correctly."""
    agent = BranchingAgent(name="TestBranch", prompt="Test branching", context={
        "input_fields": ["input", "success"],
        "output_field": "output"
    })
    
    assert agent.name == "TestBranch"
    assert agent.prompt == "Test branching"
    assert "input" in agent.input_fields
    assert "success" in agent.input_fields
    assert agent.output_field == "output"

def test_branching_agent_success_detection():
    """Test that the BranchingAgent correctly detects success indicators."""
    agent = BranchingAgent(name="TestBranch", prompt="Test", context={
        "output_field": "output"
    })
    
    # Test with boolean values
    assert agent._determine_success({"success": True}) is True
    assert agent._determine_success({"success": False}) is False
    
    # Test with string values
    assert agent._determine_success({"success": "true"}) is True
    assert agent._determine_success({"success": "false"}) is False
    assert agent._determine_success({"success": "yes"}) is True
    assert agent._determine_success({"success": "no"}) is False
    
    # Test with numeric values
    assert agent._determine_success({"success": 1}) is True
    assert agent._determine_success({"success": 0}) is False
    
    # Test alternative field names
    assert agent._determine_success({"should_succeed": True}) is True
    assert agent._determine_success({"succeed": "yes"}) is True
    assert agent._determine_success({"branch": "true"}) is True
    
    # Test default behavior (should default to True)
    assert agent._determine_success({}) is True

def test_branching_agent_run_success():
    """Test that the BranchingAgent correctly sets last_action_success to True."""
    agent = BranchingAgent(name="TestBranch", prompt="Test", context={
        "input_fields": ["input"],
        "output_field": "output"
    })
    
    # Run with success=True
    result = agent.run({
        "input": "1"
    })
    
    assert result["last_action_success"] is True
    assert "output" in result
    assert "SUCCEED" in result["output"]
    assert "BRANCH: TestBranch will SUCCEED" in result["output"]

def test_branching_agent_run_failure():
    """Test that the BranchingAgent correctly sets last_action_success to False."""
    agent = BranchingAgent(name="TestBranch", prompt="Test", context={
        "input_fields": ["input"],
        "output_field": "output"
    })
    
    # Run with success=False
    result = agent.run({
        "input": 0,
        "success": False
    })
    
    assert result["last_action_success"] is False
    assert "output" in result
    assert "FAIL" in result["output"]
    assert "BRANCH: TestBranch will FAIL" in result["output"]

        # Run with success=False
    result = agent.run({
        "input": "no",
        "success": False
    })
    
    assert result["last_action_success"] is False
    assert "output" in result
    assert "FAIL" in result["output"]
    assert "BRANCH: TestBranch will FAIL" in result["output"]

def test_branching_agent_includes_inputs_in_output():
    """Test that the BranchingAgent includes inputs in its output."""
    agent = BranchingAgent(name="TestBranch", prompt="Test prompt", context={
        "input_fields": ["input", "success", "extra"],
        "output_field": "output"
    })
    
    # Run with multiple inputs
    result = agent.run({
        "input": "Test input",
        "success": True,
        "extra": "Extra info"
    })
    
    assert "inputs:" in result["output"]
    assert "input=Test input" in result["output"]
    assert "success=True" in result["output"]
    assert "extra=Extra info" in result["output"]
    assert "prompt: 'Test prompt'" in result["output"]