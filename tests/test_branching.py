# Add to tests/test_branching.py
import os
from pathlib import Path

import pandas as pd
import pytest

from agentmap.runner import run_graph


def test_success_agents():
    """Test that the SuccessAgent and FailureAgent work correctly."""
    # Create a temporary CSV file with success and failure agents
    csv_content = """GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
TestBranching,Start,,Start Node,Success,SuccessPath,FailurePath,input,startOutput,Start prompt
TestBranching,SuccessPath,,Success Path,Default,,,startOutput,finalOutput,Success reached
TestBranching,FailurePath,,Failure Path,Default,,,startOutput,finalOutput,Failure reached
"""
    # Write the CSV to a temporary file
    temp_csv = Path("temp_test_branching.csv")
    with open(temp_csv, "w") as f:
        f.write(csv_content)

    from agentmap.di import initialize_di    
    initialize_di();

    try:
        # Test with a success agent
        result = run_graph(
            graph_name="TestBranching",
            initial_state={"input": "Test input"},
            csv_path=str(temp_csv),
            autocompile_override=False
        )
        
        assert isinstance(result, dict)
        assert result.get("last_action_success") is True
        assert "finalOutput" in result
        assert "[SuccessPath] DefaultAgent executed with prompt: 'Success reached'" in result["finalOutput"]
        assert "Success reached" in result["finalOutput"]
    finally:
        # Clean up the temporary file
        if temp_csv.exists():
            os.remove(temp_csv)        

def test_failure_agents():
    """Test that the SuccessAgent and FailureAgent work correctly."""
    
    # Create a different CSV with failure in the first node
    csv_content_2 = """GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
TestBranching,Start,,Start Node,Failure,SuccessPath,FailurePath,input,startOutput,Start prompt
TestBranching,SuccessPath,,Success Path,Default,,,startOutput,finalOutput,Success reached
TestBranching,FailurePath,,Failure Path,Default,,,startOutput,finalOutput,Failure reached
"""
    temp_csv = Path("temp_test_branching.csv")
    with open(temp_csv, "w") as f:
        f.write(csv_content_2)

    from agentmap.di import initialize_di    
    initialize_di();

    try:
        # Write the second CSV to a temporary file
        with open(temp_csv, "w") as f:
            f.write(csv_content_2)
            
        # Test with a failure agent
        result = run_graph(
            graph_name="TestBranching",
            initial_state={"input": "Test input"},
            csv_path=str(temp_csv),
            autocompile_override=False
        )

        assert isinstance(result, dict)
        assert result.get("last_action_success") is True
        assert "finalOutput" in result
        assert "[FailurePath] DefaultAgent executed with prompt: 'Failure reached'" in result["finalOutput"]
        assert "Failure reached" in result["finalOutput"]

        
    finally:
        # Clean up the temporary file
        if temp_csv.exists():
            os.remove(temp_csv)