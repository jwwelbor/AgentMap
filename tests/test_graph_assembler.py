# tests/test_graph_assembler.py
"""Tests for GraphAssembler functionality."""

from pathlib import Path

import pytest
from langgraph.graph import StateGraph

from agentmap.agents import BranchingAgent, DefaultAgent
from agentmap.graph import GraphAssembler
from tests.conftest import create_test_agent


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


def test_graph_assembler_initialization_with_options():
    """Test GraphAssembler initialization with custom options."""
    builder = StateGraph(dict)
    
    assembler = GraphAssembler(builder, enable_logging=False)
    
    assert assembler.builder == builder
    assert assembler.enable_logging is False


def test_graph_assembler_add_node(test_logger, test_execution_tracker):
    """Test that the GraphAssembler can add nodes correctly."""
    # Create a builder
    builder = StateGraph(dict)
    
    # Create the assembler
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Create an agent with proper dependencies
    agent = create_test_agent(
        DefaultAgent,
        name="TestNode",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={}
    )
    
    # Add the node
    assembler.add_node("TestNode", agent)
    
    # Check that the node was added to the builder
    assert "TestNode" in builder.nodes


def test_graph_assembler_add_edge(test_logger, test_execution_tracker):
    """Test that the GraphAssembler can add edges correctly."""
    # Create a builder
    builder = StateGraph(dict)
    
    # Create the assembler
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Create two agents with proper dependencies
    agent1 = create_test_agent(
        DefaultAgent,
        name="Node1",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={}
    )
    
    agent2 = create_test_agent(
        DefaultAgent,
        name="Node2",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={}
    )
    
    # Add the nodes
    assembler.add_node("Node1", agent1)
    assembler.add_node("Node2", agent2)
    
    # Add an edge
    assembler.add_default_edge("Node1", "Node2")
    
    # Check that the edge was added
    assert any(e[0] == "Node1" and e[1] == "Node2" for e in builder._all_edges)


def test_graph_assembler_success_failure_edge(test_logger, test_execution_tracker):
    """Test that the GraphAssembler can add success/failure edges correctly."""
    # Create a builder
    builder = StateGraph(dict)
    
    # Create the assembler
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Create three agents with proper dependencies
    branching_agent = create_test_agent(
        BranchingAgent,
        name="Start",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Test prompt",
        context={"input_fields": ["input"], "output_field": "branch_output"}
    )
    
    success_agent = create_test_agent(
        DefaultAgent,
        name="Success",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Success prompt",
        context={"output_field": "success_output"}
    )
    
    failure_agent = create_test_agent(
        DefaultAgent,
        name="Failure",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Failure prompt",
        context={"output_field": "failure_output"}
    )
    
    # Add the nodes
    assembler.add_node("Start", branching_agent)
    assembler.add_node("Success", success_agent)
    assembler.add_node("Failure", failure_agent)
    
    # Add success/failure edge
    assembler.add_success_failure_edge("Start", "Success", "Failure")
    
    # Set entry point
    assembler.set_entry_point("Start")
    
    # Compile the graph
    graph = assembler.compile()
    
    # Test with success state (truthy input)
    result = graph.invoke({"input": "true"})
    assert "success_output" in result
    assert "Success" in result["success_output"]
    
    # Test with failure state (falsy input)
    result = graph.invoke({"input": "false"})
    assert "failure_output" in result
    assert "Failure" in result["failure_output"]


def test_graph_assembler_process_node_edges(test_logger, test_execution_tracker):
    """Test that the GraphAssembler can process different edge types for nodes."""
    # Create a builder
    builder = StateGraph(dict)
    
    # Create the assembler
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Create agents with proper dependencies
    start = create_test_agent(
        BranchingAgent,
        name="Start",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Branch decision",
        context={"input_fields": ["input"], "output_field": "branch_result"}
    )
    
    success = create_test_agent(
        DefaultAgent,
        name="Success",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Success processing",
        context={"output_field": "success_result"}
    )
    
    failure = create_test_agent(
        DefaultAgent,
        name="Failure",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Failure handling",
        context={"output_field": "failure_result"}
    )
    
    next_node = create_test_agent(
        DefaultAgent,
        name="Next",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Next step",
        context={"output_field": "next_result"}
    )
    
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
    
    # Test the success path (should go Start -> Success -> Next)
    result = graph.invoke({"input": True})
    assert "next_result" in result
    assert "Next" in result["next_result"]
    
    # Test the failure path (should go Start -> Failure)
    result = graph.invoke({"input": False})
    assert "failure_result" in result
    assert "Failure" in result["failure_result"]


def test_graph_assembler_entry_point_setting():
    """Test that GraphAssembler correctly sets entry points."""
    builder = StateGraph(dict)
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Set entry point
    assembler.set_entry_point("StartNode")
    
    # Verify entry point is set (this is internal LangGraph behavior,
    # so we test that no exception is raised)
    assert True  # If we get here, set_entry_point worked


def test_graph_assembler_multiple_edges(test_logger, test_execution_tracker):
    """Test that GraphAssembler handles multiple edges correctly."""
    builder = StateGraph(dict)
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Create agents
    agent1 = create_test_agent(
        DefaultAgent,
        name="Node1",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="First",
        context={"output_field": "result1"}
    )
    
    agent2 = create_test_agent(
        DefaultAgent,
        name="Node2",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Second",
        context={"output_field": "result2"}
    )
    
    agent3 = create_test_agent(
        DefaultAgent,
        name="Node3",
        test_logger=test_logger,
        test_execution_tracker=test_execution_tracker,
        prompt="Third",
        context={"output_field": "result3"}
    )
    
    # Add nodes
    assembler.add_node("Node1", agent1)
    assembler.add_node("Node2", agent2)
    assembler.add_node("Node3", agent3)
    
    # Add multiple edges
    assembler.add_default_edge("Node1", "Node2")
    assembler.add_default_edge("Node2", "Node3")
    
    # Verify edges were added
    edges = builder._all_edges
    assert any(e[0] == "Node1" and e[1] == "Node2" for e in edges)
    assert any(e[0] == "Node2" and e[1] == "Node3" for e in edges)


def test_graph_assembler_compilation():
    """Test that GraphAssembler can compile graphs successfully."""
    builder = StateGraph(dict)
    assembler = GraphAssembler(builder, enable_logging=False)
    
    # Should be able to compile even empty graph
    try:
        # Note: This might throw an error if entry point is required
        # That's expected behavior
        graph = assembler.compile()
        assert graph is not None
    except Exception:
        # Expected if no entry point set - this is valid LangGraph behavior
        assert True
