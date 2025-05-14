"""
Test for the GraphAssembler class.
"""
from pathlib import Path

import pytest
from langgraph.graph import StateGraph

from agentmap.agents import BranchingAgent, DefaultAgent
from agentmap.graph import GraphAssembler


def test_graph_assembler_initialization():
    """Test that the GraphAssembler initializes correctly."""
    # Create a builder
    builder = StateGraph(dict)
    
    # Create the assembler
    assembler = GraphAssembler(builder)
    
    # Check that the assembler was created correctly
    assert assembler.builder == builder
    assert assembler.enable_logging is True
    assert isinstance(assembler.functions_dir, Path)

def test_graph_assembler_add_node():
    """Test that the GraphAssembler can add nodes correctly."""
    # Create a builder
    builder = StateGraph(dict)
    
    # Create the assembler
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Create an agent
    agent = DefaultAgent(name="TestNode", prompt="Test prompt", context={})
    
    # Add the node
    assembler.add_node("TestNode", agent)
    
    # Check that the node was added to the builder
    assert "TestNode" in builder.nodes

def test_graph_assembler_add_edge():
    """Test that the GraphAssembler can add edges correctly."""
    # Create a builder
    builder = StateGraph(dict)
    
    # Create the assembler
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Create two agents
    agent1 = DefaultAgent(name="Node1", prompt="Test prompt", context={})
    agent2 = DefaultAgent(name="Node2", prompt="Test prompt", context={})
    
    # Add the nodes
    assembler.add_node("Node1", agent1)
    assembler.add_node("Node2", agent2)
    
    # Add an edge
    assembler.add_default_edge("Node1", "Node2")
    
    # Check that the edge was added
    assert any(e[0] == "Node1" and e[1] == "Node2" for e in builder._all_edges)

def test_graph_assembler_success_failure_edge():
    """Test that the GraphAssembler can add success/failure edges correctly."""
    # Create a builder
    builder = StateGraph(dict)
    
    # Create the assembler
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Create three agents
    agent1 = BranchingAgent(name="Start", prompt="Test prompt", context={"input_fields": ["input"]})
    agent2 = DefaultAgent(name="Success", prompt="Test prompt", context={})
    agent3 = DefaultAgent(name="Failure", prompt="Test prompt", context={})
    
    # Add the nodes
    assembler.add_node("Start", agent1)
    assembler.add_node("Success", agent2)
    assembler.add_node("Failure", agent3)
    
    # Add success/failure edge
    assembler.add_success_failure_edge("Start", "Success", "Failure")
    
    # Set entry point
    assembler.set_entry_point("Start")
    
    # Compile the graph
    graph = assembler.compile()
    
    # Test with success state
    result = graph.invoke({"input": "true"})
    output = result.get("output", [])
    assert output == "DefaultAgent 'Success' executed with prompt: 'Test prompt'"
        
    # Test with failure state
    result = graph.invoke({"input": "false"})
    output = result.get("output", [])
    assert output == "DefaultAgent 'Failure' executed with prompt: 'Test prompt'"
     
def test_graph_assembler_process_node_edges():
    """Test that the GraphAssembler can process all edge types for a node."""
    # Create a builder
    builder = StateGraph(dict)
    
    # Create the assembler
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Create agents
    start = BranchingAgent(name="Start", prompt="", context={"input_fields": ["input"]})
    success = DefaultAgent(name="Success", prompt="", context={})
    failure = DefaultAgent(name="Failure", prompt="", context={})
    next_node = DefaultAgent(name="Next", prompt="", context={})
    
    # Add nodes
    assembler.add_node("Start", start)
    assembler.add_node("Success", success)
    assembler.add_node("Failure", failure)
    assembler.add_node("Next", next_node)
    
    # Process edges for a node with success/failure routes
    assembler.process_node_edges("Start", {
        "success": "Success",
        "failure": "Failure"
    })
    
    # Process edges for a node with a default route
    assembler.process_node_edges("Success", {
        "default": "Next"
    })
    
    # Set entry point
    assembler.set_entry_point("Start")
    
    # Compile the graph
    graph = assembler.compile()
    
    # Test the success path
    result = graph.invoke({"input": True})
    output = result.get("output", [])
    assert output == "DefaultAgent 'Next' executed"
    
    # Test the failure path
    result = graph.invoke({"input": False})
    output = result.get("output", [])
    assert output == "DefaultAgent 'Failure' executed"

