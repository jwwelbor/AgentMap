"""
Test utilities for memory testing in AgentMap.

This module provides helper functions and fixtures for testing memory
functionality in AgentMap workflows.
"""
import os
import csv
import tempfile
from typing import Dict, Any, Optional, List
from unittest.mock import MagicMock, patch

# Try to import required dependencies
try:
    from langchain.memory import (
        ConversationBufferMemory,
        ConversationBufferWindowMemory,
        ConversationSummaryMemory,
        ConversationTokenBufferMemory
    )
    from langchain.schema import HumanMessage, AIMessage, SystemMessage
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

from agentmap.agents.features import HAS_LLM_AGENTS

# Memory creation helpers

def create_memory(memory_type: str = "buffer", **kwargs) -> Any:
    """
    Create a memory object of the specified type with optional configuration.
    
    Args:
        memory_type: Type of memory to create ('buffer', 'window', 'summary', 'token')
        **kwargs: Additional configuration options
    
    Returns:
        Memory object or None if dependencies not available
    """
    if not HAS_LANGCHAIN:
        return None
        
    if memory_type == "buffer":
        return ConversationBufferMemory(return_messages=True, memory_key="history")
    elif memory_type == "window":
        k = kwargs.get("k", 5)
        return ConversationBufferWindowMemory(k=k, return_messages=True, memory_key="history")
    elif memory_type == "summary":
        return ConversationSummaryMemory(return_messages=True, memory_key="history")
    elif memory_type == "token":
        max_token_limit = kwargs.get("max_token_limit", 2000)
        return ConversationTokenBufferMemory(
            max_token_limit=max_token_limit,
            return_messages=True,
            memory_key="history"
        )
    else:
        raise ValueError(f"Unknown memory type: {memory_type}")

def add_messages_to_memory(memory: Any, messages: List[Dict[str, str]]) -> Any:
    """
    Add messages to a memory object.
    
    Args:
        memory: Memory object
        messages: List of message dictionaries with 'role' and 'content' keys
    
    Returns:
        Updated memory object
    """
    if not memory or not hasattr(memory, "chat_memory"):
        return memory
        
    for msg in messages:
        role = msg.get("role", "").lower()
        content = msg.get("content", "")
        
        if role == "human" or role == "user":
            memory.chat_memory.add_user_message(content)
        elif role == "ai" or role == "assistant":
            memory.chat_memory.add_ai_message(content)
        elif role == "system":
            memory.chat_memory.messages.append(SystemMessage(content=content))
            
    return memory

# Graph creation helpers

def create_memory_graph_csv(
    output_path: Optional[str] = None,
    graph_name: str = "MemoryTest",
    num_agents: int = 2,
    agent_types: Optional[List[str]] = None
) -> str:
    """
    Create a CSV file defining a graph with memory-enabled agents.
    
    Args:
        output_path: Optional output path for the CSV
        graph_name: Name of the graph
        num_agents: Number of agent nodes to create
        agent_types: List of agent types to use (defaults to ['openai', 'anthropic'])
    
    Returns:
        Path to the created CSV file
    """
    if agent_types is None:
        agent_types = ["openai", "anthropic"] * (num_agents // 2 + 1)
    
    # If output_path is None, create a temporary file
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "GraphName", "Node", "AgentType", "Prompt", "Input_Fields", 
            "Output_Field", "Success_Next", "Failure_Next", "Edge", "Context"
        ])
        
        # Add input node
        writer.writerow([
            graph_name, "input", "input", "User Input", "input",
            "user_input", "", "", "agent1", ""
        ])
        
        # Add agent nodes
        for i in range(1, num_agents + 1):
            agent_type = agent_types[(i - 1) % len(agent_types)]
            input_fields = "user_input|conversation_memory" if i == 1 else f"output{i-1}|conversation_memory"
            output_field = f"output{i}|conversation_memory" if i < num_agents else "final_output|conversation_memory"
            edge = f"agent{i+1}" if i < num_agents else ""
            
            prompt = "Respond to: {user_input}" if i == 1 else "Continue the conversation based on previous output"
            
            writer.writerow([
                graph_name, f"agent{i}", agent_type, prompt, input_fields,
                output_field, "", "", edge, ""
            ])
    
    return output_path

# Mock agent creation

def create_mock_llm_agent(
    agent_type: str = "openai",
    name: str = "mock_agent",
    memory_key: str = "conversation_memory"
) -> MagicMock:
    """
    Create a mock LLM agent that simulates memory handling.
    
    Args:
        agent_type: Type of agent to mock
        name: Name for the agent
        memory_key: Memory key to use
    
    Returns:
        MagicMock configured to simulate an LLM agent
    """
    agent = MagicMock()
    agent.name = name
    agent.agent_type = agent_type
    agent.memory_key = memory_key
    
    # Configure run method to handle memory
    def mock_run(state):
        from agentmap.state.adapter import StateAdapter
        
        # Get input and memory
        input_text = StateAdapter.get_value(state, "input") or "Default input"
        memory = StateAdapter.get_value(state, memory_key)
        
        # Create default memory if none exists
        if not memory or not hasattr(memory, "chat_memory"):
            memory = create_memory("buffer")
        
        # Add messages to memory
        memory.chat_memory.add_user_message(input_text)
        memory.chat_memory.add_ai_message(f"Response from {name} to: {input_text}")
        
        # Update state
        state = StateAdapter.set_value(state, "output", f"Response from {name} to: {input_text}")
        state = StateAdapter.set_value(state, memory_key, memory)
        state = StateAdapter.set_value(state, "last_action_success", True)
        
        return state
        
    agent.run.side_effect = mock_run
    
    return agent

# Patch utilities

def patch_llm_agents():
    """
    Create a context manager that patches LLM agents to avoid real API calls.
    
    Returns:
        Context manager for patching
    """
    # Define patchers
    openai_patcher = patch("agentmap.agents.builtins.llm.openai_agent.OpenAIAgent._call_api")
    anthropic_patcher = patch("agentmap.agents.builtins.llm.anthropic_agent.AnthropicAgent._call_api")
    google_patcher = patch("agentmap.agents.builtins.llm.google_agent.GoogleAgent._call_api")
    
    # Start patchers and configure mocks
    mock_openai = openai_patcher.start()
    mock_anthropic = anthropic_patcher.start()
    mock_google = google_patcher.start()
    
    # Configure mocks
    mock_openai.side_effect = lambda prompt: f"OpenAI response to: {prompt[-30:]}"
    mock_anthropic.side_effect = lambda prompt: f"Anthropic response to: {prompt[-30:]}"
    mock_google.side_effect = lambda prompt: f"Google response to: {prompt[-30:]}"
    
    try:
        yield {
            "openai": mock_openai,
            "anthropic": mock_anthropic,
            "google": mock_google
        }
    finally:
        # Stop patchers
        openai_patcher.stop()
        anthropic_patcher.stop()
        google_patcher.stop()

# Integration test utilities

def verify_memory_persistence(state: Dict[str, Any], memory_key: str = "conversation_memory"):
    """
    Verify that memory in a state object is properly persisted.
    
    Args:
        state: State dictionary or object
        memory_key: Key to retrieve memory from state
    
    Returns:
        True if memory is valid, False otherwise
    """
    from agentmap.state.adapter import StateAdapter
    from agentmap.agents.builtins.memory.utils import deserialize_memory
    
    # Get memory from state
    memory = StateAdapter.get_value(state, memory_key)
    
    # Check if memory exists
    if memory is None:
        return False
    
    # Handle serialized memory
    if isinstance(memory, dict) and memory.get("_type") == "langchain_memory":
        memory = deserialize_memory(memory)
    
    # Check if memory has chat_memory attribute
    if not hasattr(memory, "chat_memory"):
        return False
    
    # Check if memory has messages
    if not memory.chat_memory.messages:
        return False
    
    return True

def get_memory_messages(state: Dict[str, Any], memory_key: str = "conversation_memory"):
    """
    Get messages from memory in a state object.
    
    Args:
        state: State dictionary or object
        memory_key: Key to retrieve memory from state
    
    Returns:
        List of message objects or empty list if memory not found
    """
    from agentmap.state.adapter import StateAdapter
    from agentmap.agents.builtins.memory.utils import deserialize_memory
    
    # Get memory from state
    memory = StateAdapter.get_value(state, memory_key)
    
    # Handle serialized memory
    if isinstance(memory, dict) and memory.get("_type") == "langchain_memory":
        memory = deserialize_memory(memory)
    
    # Handle missing or invalid memory
    if not memory or not hasattr(memory, "chat_memory"):
        return []
    
    return memory.chat_memory.messages
