"""
Test that execution tracking works properly with complex state objects.

This test uses actual AgentMap graph code to verify that the graph_success field
is correctly set regardless of what fields are in the state.
"""
import pytest
from unittest.mock import patch

# Skip tests if required dependencies aren't available
try:
    from langchain.memory import ConversationBufferMemory
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

from langgraph.graph import StateGraph

from agentmap.state.adapter import StateAdapter
from agentmap.agents.base_agent import BaseAgent
from agentmap.graph.assembler import GraphAssembler

# Simple test agents

class SimpleAgent(BaseAgent):
    """Simple agent that passes through its inputs."""
    
    def process(self, inputs):
        """Return inputs unchanged."""
        return inputs

class FailingAgent(BaseAgent):
    """Agent that always fails."""
    
    def process(self, inputs):
        """Always raise an error."""
        raise ValueError("Intentional test failure")

# Test helpers

def create_success_graph():
    """Create a graph with agents that all succeed."""
    # Create StateGraph builder
    builder = StateGraph(dict)
    
    # Create graph assembler
    assembler = GraphAssembler(builder)
    
    # Add nodes
    agent1 = SimpleAgent("agent1", "", {"input_fields": ["input"], "output_field": "output"})
    agent2 = SimpleAgent("agent2", "", {"input_fields": ["input"], "output_field": "output"})
    
    assembler.add_node("agent1", agent1)
    assembler.add_node("agent2", agent2)
    
    # Set entry point
    assembler.set_entry_point("agent1")
    
    # Add edge
    assembler.add_default_edge("agent1", "agent2")
    
    # Compile and return
    return assembler.compile()

def create_failure_graph():
    """Create a graph with an agent that fails."""
    # Create StateGraph builder
    builder = StateGraph(dict)
    
    # Create graph assembler
    assembler = GraphAssembler(builder)
    
    # Add nodes
    agent1 = SimpleAgent("agent1", "", {"input_fields": ["input"], "output_field": "output"})
    agent2 = FailingAgent("agent2", "", {"input_fields": ["input"], "output_field": "output"})
    
    assembler.add_node("agent1", agent1)
    assembler.add_node("agent2", agent2)
    
    # Set entry point
    assembler.set_entry_point("agent1")
    
    # Add edge
    assembler.add_default_edge("agent1", "agent2")
    
    # Compile and return
    return assembler.compile()

# Tests

def test_tracking_with_various_state_fields():
    """Test that tracking works with various fields in state."""
    # Create various objects to include in state
    if HAS_LANGCHAIN:
        memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    else:
        memory = {"mock": "memory"}
        
    # Create state with various field types
    state = {
        "string_field": "text value",
        "int_field": 42,
        "list_field": [1, 2, 3],
        "dict_field": {"nested": "value"},
        "complex_field": memory,
        "input": "test"
    }
    
    # Create graph
    graph = create_success_graph()
    
    # Run with complex state
    result = graph.invoke(state)
    
    # Verify tracking was initialized and works
    assert "graph_success" in result
    assert result["graph_success"] is True
    
    # Verify all fields preserved
    assert "string_field" in result
    assert "int_field" in result
    assert "list_field" in result
    assert "dict_field" in result
    assert "complex_field" in result
    
    # Verify execution summary
    assert "__execution_tracker" in result
    summary = result["__execution_tracker"]
    assert len(summary["execution_path"]) == 2
    assert summary["graph_success"] is True

def test_tracking_with_failing_agent():
    """Test that tracking works when an agent fails."""
    # Create state with complex object
    if HAS_LANGCHAIN:
        memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    else:
        memory = {"mock": "memory"}
        
    state = {
        "complex_field": memory,
        "input": "test"
    }
    
    # Create graph
    graph = create_failure_graph()
    
    # Run with complex state
    result = graph.invoke(state)
    
    # Verify tracking shows failure
    assert "graph_success" in result
    assert result["graph_success"] is False
    
    # Verify fields still preserved
    assert "complex_field" in result
    
    # Verify execution summary
    assert "__execution_summary" in result
    summary = result["__execution_summary"]
    assert "agent1" in summary["execution_path"]
    assert "agent2" in summary["execution_path"]
    assert summary["graph_success"] is False

def test_policy_evaluation():
    """Test that policy evaluation works correctly."""
    # Create state with complex object
    if HAS_LANGCHAIN:
        memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    else:
        memory = {"mock": "memory"}
        
    state = {
        "complex_field": memory,
        "input": "test"
    }
    
    # Create graph
    graph = create_failure_graph()
    
    # Test with policy always returning True
    with patch("agentmap.logging.tracking.policy.evaluate_success_policy", return_value=True):
        result = graph.invoke(state)
        
        # Should be True despite agent failure
        assert result["graph_success"] is True
        
        # Fields should still be preserved
        assert "complex_field" in result
    
    # Test with policy always returning False
    with patch("agentmap.logging.tracking.policy.evaluate_success_policy", return_value=False):
        result = graph.invoke(state)
        
        # Should be False
        assert result["graph_success"] is False
        
        # Fields should still be preserved
        assert "complex_field" in result
