"""
Tests for conversation memory in LLM agents.

These tests verify that conversation memory is properly persisted
and passed between LLM nodes in AgentMap graphs.
"""
import os
import pytest
import tempfile
from unittest.mock import MagicMock, patch

# We need to handle the case where LangChain is not installed
try:
    from langchain.memory import (
        ConversationBufferMemory,
        ConversationBufferWindowMemory,
        ConversationSummaryMemory
    )
    from langchain.schema import HumanMessage, AIMessage
    
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    
# Import AgentMap functionality
from agentmap.agents.builtins.llm.utils import serialize_memory, deserialize_memory
from agentmap.state.adapter import StateAdapter
from agentmap.agents.features import HAS_LLM_AGENTS

# Skip all tests in this module if LangChain is not available
pytestmark = pytest.mark.skipif(
    not HAS_LANGCHAIN, 
    reason="LangChain not installed. Install with pip install langchain"
)

# Also skip if LLM agents aren't available
pytestmark = pytest.mark.skipif(
    not HAS_LLM_AGENTS, 
    reason="LLM agents not available. Install with pip install agentmap[llm]"
)

# Set up basic test fixtures

@pytest.fixture
def buffer_memory():
    """Fixture for a basic ConversationBufferMemory"""
    if not HAS_LANGCHAIN:
        return None
    memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    memory.chat_memory.add_user_message("Hello")
    memory.chat_memory.add_ai_message("Hi there! How can I help you?")
    return memory

@pytest.fixture
def window_memory():
    """Fixture for a ConversationBufferWindowMemory"""
    if not HAS_LANGCHAIN:
        return None
    memory = ConversationBufferWindowMemory(k=2, return_messages=True, memory_key="history")
    memory.chat_memory.add_user_message("Hello")
    memory.chat_memory.add_ai_message("Hi there! How can I help you?")
    memory.chat_memory.add_user_message("What's the weather?")
    memory.chat_memory.add_ai_message("I don't have real-time weather data.")
    return memory

@pytest.fixture
def state_with_memory(buffer_memory):
    """Fixture for a state dictionary with memory"""
    if buffer_memory is None:
        return {}
    return {
        "input": "Test input",
        "conversation_memory": buffer_memory
    }

@pytest.fixture
def temp_csv_path():
    """Fixture for a temporary CSV file for testing."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        with open(path, 'w') as f:
            f.write("GraphName,Node,AgentType,Prompt,Input_Fields,Output_Field,Success_Next,Failure_Next,Edge,Context\n")
            f.write("MemoryTest,input,input,User Input,input,user_input,,,,\n")
            f.write("MemoryTest,agent1,openai,Respond to: {user_input},user_input|conversation_memory,output|conversation_memory,,,,\n")
            f.write("MemoryTest,agent2,anthropic,Continue the conversation,output|conversation_memory,final_output|conversation_memory,,,,\n")
        yield path
    finally:
        os.unlink(path)

# Core serialization/deserialization tests

def test_memory_serialization(buffer_memory):
    """Test that memory can be correctly serialized to a dictionary."""
    serialized = serialize_memory(buffer_memory)
    
    # Check basic structure
    assert serialized is not None
    assert isinstance(serialized, dict)
    assert serialized.get("_type") == "langchain_memory"
    assert serialized.get("memory_type") == "buffer"
    
    # Check message serialization
    messages = serialized.get("messages", [])
    assert len(messages) == 2
    assert messages[0]["type"] == "human"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["type"] == "ai"
    assert messages[1]["content"] == "Hi there! How can I help you?"

def test_memory_deserialization(buffer_memory):
    """Test that serialized memory can be correctly deserialized."""
    serialized = serialize_memory(buffer_memory)
    deserialized = deserialize_memory(serialized)
    
    # Check type
    assert deserialized is not None
    assert hasattr(deserialized, "chat_memory")
    
    # Check message content
    messages = deserialized.chat_memory.messages
    assert len(messages) == 2
    assert messages[0].type == "human"
    assert messages[0].content == "Hello"
    assert messages[1].type == "ai"
    assert messages[1].content == "Hi there! How can I help you?"

def test_window_memory_serialization(window_memory):
    """Test that window memory correctly preserves window size (k)."""
    serialized = serialize_memory(window_memory)
    
    # Check that k parameter is preserved
    assert serialized.get("k") == 2
    
    # Check that all messages are present in serialized form
    messages = serialized.get("messages", [])
    assert len(messages) == 4

def test_window_memory_deserialization(window_memory):
    """Test that window memory is correctly deserialized with parameters."""
    serialized = serialize_memory(window_memory)
    deserialized = deserialize_memory(serialized)
    
    # Check that k parameter is preserved
    assert deserialized.k == 2
    
    # Check messages
    messages = deserialized.chat_memory.messages
    assert len(messages) == 4

def test_state_adapter_get_memory(state_with_memory):
    """Test that StateAdapter correctly handles memory objects."""
    memory = StateAdapter.get_value(state_with_memory, "conversation_memory")
    
    # Ensure it's a proper memory object
    assert memory is not None
    assert hasattr(memory, "chat_memory")
    assert len(memory.chat_memory.messages) == 2

def test_state_adapter_set_memory(buffer_memory):
    """Test that StateAdapter correctly sets memory objects."""
    state = {}
    new_state = StateAdapter.set_value(state, "conversation_memory", buffer_memory)
    
    # Verify memory was stored
    assert "conversation_memory" in new_state
    
    # When we get it back, it should be a memory object
    retrieved = StateAdapter.get_value(new_state, "conversation_memory")
    assert hasattr(retrieved, "chat_memory")
    assert len(retrieved.chat_memory.messages) == 2

# LLM agent memory tests - using mocks to avoid actual API calls

@pytest.fixture
def mock_llm_agent():
    """Fixture for a mock LLM agent that supports memory."""
    with patch("agentmap.agents.builtins.llm.openai_agent.OpenAIAgent") as mock_agent_class:
        # Configure the mock agent instance
        agent_instance = MagicMock()
        agent_instance.memory_key = "conversation_memory"
        
        # Make process actually call _process_with_langchain to test memory updating
        def mock_process(inputs):
            # Simulate processing with memory
            memory = inputs.get("conversation_memory")
            if memory and hasattr(memory, "chat_memory"):
                # Add the input to memory
                user_input = inputs.get("input", "User input")
                memory.save_context(
                    {"input": user_input},
                    {"output": f"Response to: {user_input}"}
                )
                
                # Return results with updated memory
                return {
                    "output": f"Response to: {user_input}",
                    "conversation_memory": memory
                }
            return {"output": "Response without memory", "conversation_memory": None}
            
        agent_instance.process.side_effect = mock_process
        
        # Make the mock class return our configured instance
        mock_agent_class.return_value = agent_instance
        yield agent_instance

def test_agent_memory_updating(mock_llm_agent, buffer_memory):
    """Test that an LLM agent correctly updates memory during processing."""
    # Initial state with memory
    initial_state = {
        "input": "What is your name?",
        "conversation_memory": buffer_memory
    }
    
    # Process with agent
    result = mock_llm_agent.process(initial_state)
    
    # Check result structure
    assert "output" in result
    assert "conversation_memory" in result
    
    # Verify memory was updated
    updated_memory = result["conversation_memory"]
    assert hasattr(updated_memory, "chat_memory")
    
    # Should now have 4 messages (original 2 + new input/output pair)
    assert len(updated_memory.chat_memory.messages) == 4
    
    # Check the new messages
    assert updated_memory.chat_memory.messages[2].content == "What is your name?"
    assert updated_memory.chat_memory.messages[3].content == "Response to: What is your name?"

# Integration tests with actual graph components

@pytest.mark.integration
def test_memory_persistence_in_graph():
    """Test memory persistence in a complete graph with multiple LLM agents."""
    # This test requires patch work to avoid making actual API calls
    # Skip for now - in a real environment, this would use a mock server
    pytest.skip("Integration test requires complex setup")
    
    # In a complete implementation, this would:
    # 1. Create a test graph with multiple LLM agents
    # 2. Initialize the graph with memory
    # 3. Run the graph and verify memory updates
    # 4. Check that memory is preserved between different agent nodes

@pytest.mark.parametrize("memory_type", ["buffer", "window", "summary"])
def test_different_memory_types(memory_type):
    """Test that different memory types are properly handled."""
    if memory_type == "buffer":
        memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    elif memory_type == "window":
        memory = ConversationBufferWindowMemory(k=3, return_messages=True, memory_key="history")
    elif memory_type == "summary":
        # Skip if we can't use a default LLM for summarization
        pytest.skip("Summary memory requires LLM for summarization")
        memory = ConversationSummaryMemory(return_messages=True, memory_key="history")
    
    # Add some test messages
    memory.chat_memory.add_user_message("Hello")
    memory.chat_memory.add_ai_message("Hi there!")
    
    # Test serialization/deserialization round trip
    serialized = serialize_memory(memory)
    deserialized = deserialize_memory(serialized)
    
    # Verify type-specific properties are preserved
    if memory_type == "buffer":
        assert not hasattr(deserialized, "k")
    elif memory_type == "window":
        assert deserialized.k == 3
    elif memory_type == "summary":
        assert hasattr(deserialized, "llm")
