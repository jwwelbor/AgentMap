# test_workflow_integration.py
from pathlib import Path

import pytest

from agentmap.runner import run_graph


def test_linear_workflow_execution():
    """Test that a simple linear workflow executes properly."""
    # Use the LinearGraph example which has Start -> Next -> End
    result = run_graph(
        graph_name="LinearGraph",
        initial_state={"input": "Test message"}, 
        csv_path="examples/LinearGraph.csv",
        autocompile_override=False
    )
    
    assert isinstance(result, dict)
    assert "response" in result
    assert result.get("last_action_success") is True

def test_single_node_workflow():
    """Test a single node workflow."""
    result = run_graph(
        graph_name="SingleNodeGraph",
        initial_state={"input": "Test message"}, 
        csv_path="examples/SingleNodeGraph.csv",
        autocompile_override=False
    )
    
    assert isinstance(result, dict)
    assert "response" in result
    assert result.get("last_action_success") is True

# Add to tests/test_workflow_integration.py
def test_branching_workflow():
    """Test that a branching workflow correctly follows success and failure paths."""
    # First test the success path
    result = run_graph(
        graph_name="BranchingGraph",
        initial_state={"input": "true", "last_action_success": None}, 
        csv_path="examples/BranchingGraph.csv",
        autocompile_override=False
    )
    
    assert isinstance(result, dict)
    assert result.get("last_action_success") is True
    # Verify we ended up in the SuccessPath node
    assert "finalResponse" in result
    assert "DefaultAgent 'SuccessPath' executed with prompt: 'Success path reached!'" in str(result.get("finalResponse", ""))
    
    # Next test the failure path
    result = run_graph(
        graph_name="BranchingGraph",
        initial_state={"input": "0", "last_action_success": None}, 
        csv_path="examples/BranchingGraph.csv",
        autocompile_override=False
    )
    
    assert isinstance(result, dict)
    assert result.get("last_action_success") is True  # The node itself succeeded
    # Verify we ended up in the FailurePath node
    assert "finalResponse" in result
    assert "DefaultAgent 'FailurePath' executed with prompt: 'Failure path reached!'" in str(result.get("finalResponse", ""))