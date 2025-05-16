"""
Tests for the LLMAgent class focusing on memory handling.

These tests verify that LLMAgent correctly manages memory during
processing and integrates with LangChain memory objects.
"""
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

try:
    from langchain.memory import (
        ConversationBufferMemory,
        ConversationBufferWindowMemory
    )
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

from agentmap.agents.features import HAS_LLM_AGENTS
from agentmap.state.adapter import StateAdapter
from agentmap.agents.builtins.memory.utils import serialize_memory, deserialize_memory

# Skip tests if dependencies aren't available
pytestmark = pytest.mark.skipif(
    not (HAS_LANGCHAIN and HAS_LLM_AGENTS),
    reason="LangChain and/or LLM agents not available. Install with: pip install agentmap[llm]"
)

# Fixture and helper functions

@pytest.fixture
def mock_langchain_client():
    """Create a mock LangChain client."""
    client = MagicMock()
    client.return_value = "Mock LangChain response"
    
    # Configure generate method for chat messages
    client.generate.return_value = MagicMock(
        generations=[[MagicMock(text="Mock generated response")]]
    )
    
    return client

@pytest.fixture
def mock_openai_agent():
    """Create a mock OpenAI agent with patched methods."""
    try:
        from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent
    except ImportError:
        pytest.skip("OpenAIAgent not available")
    
    with patch("agentmap.agents.builtins.llm.openai_agent.OpenAIAgent._call_api") as mock_call_api:
        # Configure the mock API response
        mock_call_api.return_value = "Mock API response"
        
        # Create the agent instance
        agent = OpenAIAgent(
            name="test_agent",
            prompt="Test prompt: {input}",
            context={
                "input_fields": ["input", "conversation_memory"],
                "output_field": "output",
                "memory_key": "conversation_memory"
            }
        )
        
        # Patch the LangChain client creation
        with patch.object(agent, "_create_langchain_client") as mock_create_client:
            mock_create_client.return_value = MagicMock()
            yield agent

def create_basic_memory():
    """Create a simple memory object with some messages."""
    memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    memory.chat_memory.add_user_message("Hello")
    memory.chat_memory.add_ai_message("Hi there! How can I help?")
    return memory

# Test LLMAgent with memory

def test_llm_agent_with_memory(mock_openai_agent):
    """Test that LLMAgent correctly processes inputs with memory."""
    # Create initial state with memory
    memory = create_basic_memory()
    initial_state = {
        "input": "What is Python?",
        "conversation_memory": memory
    }
    
    # Run the agent
    result = mock_openai_agent.run(initial_state)
    
    # Verify the result has conversation_memory
    assert "conversation_memory" in result
    
    # Get memory from result
    result_memory = StateAdapter.get_value(result, "conversation_memory")
    
    # Verify memory structure
    assert result_memory is not None
    assert hasattr(result_memory, "chat_memory")
    
    # Should have the original 2 messages plus the new exchange
    messages = result_memory.chat_memory.messages
    assert len(messages) >= 4
    
    # Verify content
    assert messages[0].content == "Hello"
    assert messages[1].content == "Hi there! How can I help?"
    assert "What is Python?" in messages[2].content  # User message
    
    # Verify output was set properly
    assert StateAdapter.get_value(result, "output") is not None
    assert StateAdapter.get_value(result, "last_action_success") is True

def test_llm_agent_create_memory_if_none(mock_openai_agent):
    """Test that LLMAgent creates memory if none is provided."""
    # Set up the agent to create memory
    mock_openai_agent.memory = None  # Ensure no memory is pre-initialized
    
    # Create initial state without memory
    initial_state = {
        "input": "Tell me about machine learning"
    }
    
    # Run the agent
    result = mock_openai_agent.run(initial_state)
    
    # Verify memory was created
    assert "conversation_memory" in result
    
    # Get memory from result
    result_memory = StateAdapter.get_value(result, "conversation_memory")
    
    # Verify memory structure
    assert result_memory is not None
    assert hasattr(result_memory, "chat_memory")
    
    # Should have the new exchange
    messages = result_memory.chat_memory.messages
    assert len(messages) >= 2
    
    # Verify content contains our query
    assert any("machine learning" in msg.content for msg in messages)

def test_llm_agent_with_memory_config(mock_openai_agent):
    """Test that LLMAgent correctly applies memory configuration."""
    # Patch the agent creation to use a real memory
    with patch("agentmap.agents.builtins.llm.llm_agent.LLMAgent._create_memory") as mock_create_memory:
        # Configure the memory creation
        window_memory = ConversationBufferWindowMemory(
            k=3, return_messages=True, memory_key="history"
        )
        mock_create_memory.return_value = window_memory
        
        # Reset the agent's memory
        mock_openai_agent.memory = None
        
        # Create a new memory configuration
        mock_openai_agent.context["memory"] = {
            "type": "buffer_window",
            "k": 3
        }
        
        # Initialize the agent (normally this would happen in __init__)
        mock_openai_agent.memory = mock_openai_agent._create_memory(mock_openai_agent.context["memory"])
        
        # Create initial state without memory
        initial_state = {
            "input": "What is your name?"
        }
        
        # Run the agent
        result = mock_openai_agent.run(initial_state)
        
        # Verify memory was created with the right configuration
        memory = StateAdapter.get_value(result, "conversation_memory")
        assert memory is not None
        assert hasattr(memory, "k")
        assert memory.k == 3

def test_llm_agent_process_with_langchain(mock_openai_agent, mock_langchain_client):
    """Test that LLMAgent can process with LangChain integration."""
    # Create memory with existing conversation
    memory = create_basic_memory()
    
    # Configure the agent to use LangChain
    mock_openai_agent._create_langchain_client = MagicMock(return_value=mock_langchain_client)
    
    # Create inputs with memory
    inputs = {
        "input": "What is artificial intelligence?",
        "conversation_memory": memory
    }
    
    # Process the inputs
    result = mock_openai_agent.process(inputs)
    
    # Verify the result contains memory
    assert "conversation_memory" in result
    
    # Get and verify memory
    result_memory = result["conversation_memory"]
    assert result_memory is not None
    
    # If it's a serialized dict, deserialize it
    if isinstance(result_memory, dict) and result_memory.get("_type") == "langchain_memory":
        result_memory = deserialize_memory(result_memory)
    
    # Verify memory structure
    assert hasattr(result_memory, "chat_memory")
    
    # Should have the original 2 messages plus the new exchange
    messages = result_memory.chat_memory.messages
    assert len(messages) >= 4
    
    # Verify content
    assert messages[0].content == "Hello"
    assert messages[1].content == "Hi there! How can I help?"
    assert "artificial intelligence" in messages[2].content  # User message

def test_llm_agent_with_error_handling(mock_openai_agent):
    """Test that LLMAgent properly handles errors during processing."""
    # Create a state with memory
    memory = create_basic_memory()
    initial_state = {
        "input": "Test input",
        "conversation_memory": memory
    }
    
    # Make the API call fail
    mock_openai_agent._call_api = MagicMock(side_effect=RuntimeError("API error"))
    
    # Run the agent
    result = mock_openai_agent.run(initial_state)
    
    # Verify error handling
    assert StateAdapter.get_value(result, "last_action_success") is False
    assert "error" in result
    assert "API error" in StateAdapter.get_value(result, "error")
    
    # Memory should still be preserved
    memory_after = StateAdapter.get_value(result, "conversation_memory")
    assert memory_after is not None
    assert hasattr(memory_after, "chat_memory")
    assert len(memory_after.chat_memory.messages) == 2  # Original messages

def test_llm_agent_with_multiple_turns(mock_openai_agent):
    """Test memory persistence across multiple turns with the same agent."""
    # First turn
    memory = create_basic_memory()
    state1 = {
        "input": "What is AI?",
        "conversation_memory": memory
    }
    
    result1 = mock_openai_agent.run(state1)
    memory1 = StateAdapter.get_value(result1, "conversation_memory")
    
    # Second turn
    state2 = {
        "input": "How does machine learning relate to AI?",
        "conversation_memory": memory1
    }
    
    result2 = mock_openai_agent.run(state2)
    memory2 = StateAdapter.get_value(result2, "conversation_memory")
    
    # Verify memory accumulation
    assert memory2 is not None
    assert hasattr(memory2, "chat_memory")
    
    # Should have all the messages from both turns
    messages = memory2.chat_memory.messages
    assert len(messages) >= 6  # 2 original + 2 from first turn + 2 from second turn
    
    # Verify content
    message_contents = [msg.content for msg in messages]
    assert "Hello" in message_contents[0]
    assert "What is AI?" in message_contents[2]
    assert "How does machine learning relate to AI?" in message_contents[4]

def test_memory_serialization_compatibility(mock_openai_agent):
    """Test compatibility between memory serialization and LLMAgent."""
    # Create and serialize memory
    memory = create_basic_memory()
    serialized = serialize_memory(memory)
    
    # Process with serialized memory
    state = {
        "input": "Test with serialized memory",
        "conversation_memory": serialized
    }
    
    result = mock_openai_agent.run(state)
    
    # Verify memory was properly handled
    result_memory = StateAdapter.get_value(result, "conversation_memory")
    assert result_memory is not None
    assert hasattr(result_memory, "chat_memory")
    
    # Should have the original 2 messages plus the new exchange
    assert len(result_memory.chat_memory.messages) >= 4
    
    # Verify the result can be re-serialized
    re_serialized = serialize_memory(result_memory)
    assert re_serialized is not None
    assert re_serialized["_type"] == "langchain_memory"
    assert len(re_serialized["messages"]) >= 4

# Test specific LLM agent implementations

@pytest.mark.parametrize("agent_type", ["openai", "anthropic", "google"])
def test_specific_llm_agent_types(agent_type):
    """Test memory handling in specific LLM agent implementations."""
    # Skip if agent type is not available
    if not HAS_LLM_AGENTS:
        pytest.skip(f"LLM agents not available")
    
    try:
        if agent_type == "openai":
            from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent as AgentClass
        elif agent_type == "anthropic":
            from agentmap.agents.builtins.llm.anthropic_agent import AnthropicAgent as AgentClass
        elif agent_type == "google":
            from agentmap.agents.builtins.llm.google_agent import GoogleAgent as AgentClass
        else:
            pytest.skip(f"Unknown agent type: {agent_type}")
    except ImportError:
        pytest.skip(f"{agent_type} agent not available")
    
    # Patch the API call to avoid real API calls
    with patch.object(AgentClass, "_call_api") as mock_call_api:
        mock_call_api.return_value = f"Mock {agent_type} response"
        
        # Create the agent
        agent = AgentClass(
            name=f"test_{agent_type}_agent",
            prompt="Test prompt: {input}",
            context={
                "input_fields": ["input", "conversation_memory"],
                "output_field": "output",
                "memory_key": "conversation_memory"
            }
        )
        
        # Create a state with memory
        memory = create_basic_memory()
        state = {
            "input": f"Test input for {agent_type}",
            "conversation_memory": memory
        }
        
        # Run the agent
        result = agent.run(state)
        
        # Verify memory handling
        result_memory = StateAdapter.get_value(result, "conversation_memory")
        assert result_memory is not None
        assert hasattr(result_memory, "chat_memory")
        assert len(result_memory.chat_memory.messages) >= 4
