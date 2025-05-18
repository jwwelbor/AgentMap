from pathlib import Path

import pytest

from agentmap.graph.builder import GraphBuilder


def test_can_load_graphs():
    # Use an example CSV that definitely exists
    csv_path = Path("../examples/LinearGraph.csv")
    assert csv_path.exists(), f"Test CSV file not found at {csv_path}"
    
    gb = GraphBuilder(csv_path)
    graphs = gb.build()
    
    assert isinstance(graphs, dict)
    assert len(graphs) > 0
    
    # Verify the LinearGraph was loaded
    assert "LinearGraph" in graphs
    
    # Verify nodes were created
    graph = graphs["LinearGraph"]
    assert "Start" in graph
    assert "Next" in graph
    assert "Ender" in graph

def test_node_has_required_attributes():
    csv_path = Path("../examples/SingleNodeGraph.csv")
    assert csv_path.exists(), f"Test CSV file not found at {csv_path}"
    
    gb = GraphBuilder(csv_path)
    graphs = gb.build()
    
    graph = graphs["SingleNodeGraph"]
    node = graph["Start"]
    
    # Verify node has required attributes
    assert node.name == "Start"
    assert hasattr(node, "agent_type")
    assert hasattr(node, "edges")