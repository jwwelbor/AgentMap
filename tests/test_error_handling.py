# test_error_handling.py
import tempfile
from pathlib import Path

import pytest

from agentmap.exceptions.graph_exceptions import InvalidEdgeDefinitionError
from agentmap.graph.builder import GraphBuilder


def test_graph_builder_nonexistent_file():
    """Test that GraphBuilder raises an error for non-existent files."""
    with pytest.raises(FileNotFoundError):
        gb = GraphBuilder(Path("nonexistent_file.csv"))
        gb.build()

def test_graph_builder_invalid_edge():
    """Test that GraphBuilder raises an error for invalid edge definitions."""
    # Create a temporary CSV with an invalid edge definition
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.csv', delete=False) as temp:
        temp.write("GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Prompt\n")
        temp.write("Test,Node1,Next,context,default,Success,Failure,prompt\n")  # Both Edge and Success/Failure
        temp_path = Path(temp.name)
    
    try:
        with pytest.raises(InvalidEdgeDefinitionError):
            gb = GraphBuilder(temp_path)
            gb.build()
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()