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

from agentmap.di import initialize_di

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

