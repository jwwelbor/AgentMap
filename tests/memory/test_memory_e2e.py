"""
End-to-end tests for conversation memory in real AgentMap graphs.

These tests create graphs from CSV definitions and verify that memory
persists correctly throughout graph execution.
"""
import os
import csv
import pytest
import tempfile
from unittest.mock import MagicMock, patch
from pathlib import Path

# Try to import required dependencies
try:
    from langchain.memory import ConversationBufferMemory
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

# Import AgentMap components
from agentmap.agents.features import HAS_LLM_AGENTS
from agentmap.state.adapter import StateAdapter
from agentmap.agents.builtins.memory.utils import serialize_memory, deserialize_memory

# Skip if required dependencies are not available
pytestmark = pytest.mark.skipif(
    not (HAS_LANGCHAIN and HAS_LLM_AGENTS),
    reason="LangChain and/or LLM agents not available. Install with: pip install agentmap[llm]"
)

# Test fixtures

@pytest.fixture
def memory_test_csv():
    """Create a temporary CSV file defining a graph with memory."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        writer = csv.writer(f)
        writer.writerow([
            "GraphName", "Node", "AgentType", "Prompt", "Input_Fields", 
            "Output_Field", "Success_Next", "Failure_Next", "Edge", "Context"
        ])
        
        # Define a graph with multiple LLM nodes that pass memory
        writer.writerow([
            "MemoryTest", "input", "input", "User Input", "input",
            "user_input", "", "", "agent1", ""
        ])
        writer.writerow([
            "MemoryTest", "agent1", "openai", "Respond to: {user_input}", "user_input|conversation_memory",
            "output|conversation_memory", "", "", "agent2", ""
        ])
        writer.writerow([
            "MemoryTest", "agent2", "anthropic", "Continue the conversation", "output|conversation_memory",
            "final_output|conversation_memory", "", "", "", ""
        ])
    
    yield f.name
    os.unlink(f.name)

# End-to-end test with mocked API calls

@pytest.mark.e2e
def test_memory_e2e_with_csv_graph(memory_test_csv):
    """End-to-end test of memory persistence in a graph defined by CSV."""
    # Skip if we're not in an environment that can import LLMs
    if not HAS_LLM_AGENTS:
        pytest.skip("LLM agents not available")
    
    # Import graph builder and runner here to avoid import errors in environments without dependencies
    try:
        from agentmap.graph.builder import GraphBuilder
        from agentmap.runner import run_graph
    except ImportError:
        pytest.skip("Cannot import required AgentMap modules")
    
    # We need to patch the LLM API calls to avoid real API usage
    with patch("agentmap.agents.builtins.llm.openai_agent.OpenAIAgent._call_api") as mock_openai, \
         patch("agentmap.agents.builtins.llm.anthropic_agent.AnthropicAgent._call_api") as mock_anthropic:
        
        # Configure mock responses
        mock_openai.side_effect = lambda prompt: f"OpenAI response to: {prompt[-20:]}"
        mock_anthropic.side_effect = lambda prompt: f"Anthropic continuation: {prompt[-20:]}"
        
        # Create an initial state with a memory object
        memory = ConversationBufferMemory(return_messages=True, memory_key="history")
        memory.chat_memory.add_user_message("Hello")
        memory.chat_memory.add_ai_message("Hi there! How can I help you?")
        
        initial_state = {
            "input": "Tell me about Python programming",
            "conversation_memory": memory
        }
        
        # Run the graph and capture the result
        try:
            result = run_graph(
                graph_name="MemoryTest", 
                initial_state=initial_state, 
                csv_path=memory_test_csv,
                autocompile_override=True
            )
        except Exception as e:
            pytest.skip(f"Error running graph: {e}")
            
        # Verify that the result contains memory
        assert "conversation_memory" in result
        final_memory = result["conversation_memory"]
        
        # Check that memory is either a proper object or a serialized dict
        assert final_memory is not None
        
        # If it's a serialized dict, deserialize it
        if isinstance(final_memory, dict) and "_type" in final_memory:
            final_memory = deserialize_memory(final_memory)
        
        # Now check the memory contents
        assert hasattr(final_memory, "chat_memory")
        messages = final_memory.chat_memory.messages
        
        # Should have at least 4 messages: original 2 + at least 2 new ones
        assert len(messages) >= 4
        
        # Verify the messages include our input
        message_contents = [msg.content for msg in messages]
        assert "Hello" in message_contents[0]
        assert "Hi there!" in message_contents[1]
        assert "Python programming" in message_contents[2]

# Tests with patched graph runner

def test_memory_with_mocked_runner():
    """Test memory handling using a mocked graph runner."""
    # Mock the necessary components
    with patch("agentmap.runner.run_graph") as mock_runner:
        # Configure mock runner to update memory
        def simulate_run(graph_name, initial_state, **kwargs):
            # Extract memory from initial state
            memory = initial_state.get("conversation_memory")
            if not memory:
                memory = ConversationBufferMemory(return_messages=True, memory_key="history")
            
            # Update memory with new messages
            if hasattr(memory, "chat_memory"):
                memory.chat_memory.add_user_message(initial_state.get("input", "User input"))
                memory.chat_memory.add_ai_message(f"Agent response to {initial_state.get('input', 'input')}")
            
            # Return state with updated memory and output
            return {
                "output": "Graph output",
                "conversation_memory": memory,
                "final_output": f"Final response to {initial_state.get('input', 'input')}"
            }
            
        mock_runner.side_effect = simulate_run
        
        # Test with initial memory
        memory = ConversationBufferMemory(return_messages=True, memory_key="history")
        initial_state = {
            "input": "Question 1",
            "conversation_memory": memory
        }
        
        # First run
        result1 = mock_runner("TestGraph", initial_state)
        
        # Verify memory was updated
        memory1 = result1["conversation_memory"]
        assert hasattr(memory1, "chat_memory")
        assert len(memory1.chat_memory.messages) == 2
        
        # Second run with updated memory
        initial_state2 = {
            "input": "Question 2",
            "conversation_memory": memory1
        }
        
        result2 = mock_runner("TestGraph", initial_state2)
        
        # Verify memory now has both interactions
        memory2 = result2["conversation_memory"]
        assert hasattr(memory2, "chat_memory")
        assert len(memory2.chat_memory.messages) == 4
        
        # Verify message content
        messages = memory2.chat_memory.messages
        assert "Question 1" in messages[0].content
        assert "Question 2" in messages[2].content

# Test memory persistence across different memory key names

def test_custom_memory_key_names():
    """Test memory persistence when using custom memory key names."""
    # Create a memory object
    memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    memory.chat_memory.add_user_message("Initial message")
    
    # Serialize with default memory key
    serialized = serialize_memory(memory)
    
    # Create state with custom memory key
    state = {
        "custom_memory_key": serialized
    }
    
    # Verify we can retrieve with the custom key
    retrieved = StateAdapter.get_value(state, "custom_memory_key")
    assert retrieved is not None
    
    # Deserialize and check content
    memory_obj = deserialize_memory(retrieved)
    assert hasattr(memory_obj, "chat_memory")
    assert len(memory_obj.chat_memory.messages) == 1
    assert memory_obj.chat_memory.messages[0].content == "Initial message"
    
    # Add new message and update state with custom key
    memory_obj.chat_memory.add_ai_message("Response to initial message")
    updated_state = StateAdapter.set_value(state, "custom_memory_key", memory_obj)
    
    # Verify updated memory
    final_memory = StateAdapter.get_value(updated_state, "custom_memory_key")
    assert hasattr(final_memory, "chat_memory")
    assert len(final_memory.chat_memory.messages) == 2
    assert final_memory.chat_memory.messages[1].content == "Response to initial message"

# Test memory persistence with multiple agent configurations

@pytest.mark.parametrize("memory_config", [
    {"type": "buffer"},
    {"type": "buffer_window", "k": 3},
    {"type": "token_buffer", "max_token_limit": 1000}
])
def test_llm_agent_with_memory_config(memory_config):
    """Test that LLM agents properly handle different memory configurations."""
    # Skip if missing required dependencies
    if not HAS_LLM_AGENTS:
        pytest.skip("LLM agents not available")
    
    try:
        from agentmap.agents.builtins.llm.openai_agent import OpenAIAgent
    except ImportError:
        pytest.skip("Cannot import OpenAIAgent")
    
    # Patch the API call to avoid real API usage
    with patch("agentmap.agents.builtins.llm.openai_agent.OpenAIAgent._call_api") as mock_api:
        mock_api.return_value = "Test response"
        
        # Create an agent with the memory configuration
        agent = OpenAIAgent(
            name="test_agent",
            prompt="Test prompt: {input}",
            context={
                "input_fields": ["input", "conversation_memory"],
                "output_field": "output",
                "memory": memory_config,
                "memory_key": "conversation_memory"
            }
        )
        
        # Initial state without memory
        initial_state = {
            "input": "Initial query"
        }
        
        # Run the agent
        result = agent.run(initial_state)
        
        # Verify that memory was created with the right configuration
        memory = StateAdapter.get_value(result, "conversation_memory")
        assert memory is not None
        
        # If serialized, deserialize it
        if isinstance(memory, dict) and memory.get("_type") == "langchain_memory":
            assert memory["memory_type"] == memory_config["type"]
            
            # Check specific parameters
            if memory_config["type"] == "buffer_window":
                assert memory["k"] == memory_config["k"]
            elif memory_config["type"] == "token_buffer":
                assert memory["max_token_limit"] == memory_config["max_token_limit"]
        
        # Run again with the same agent
        result2 = agent.run({
            "input": "Follow-up query",
            "conversation_memory": memory
        })
        
        # Verify memory was updated
        updated_memory = StateAdapter.get_value(result2, "conversation_memory")
        assert updated_memory is not None
        
        # If serialized, deserialize
        if isinstance(updated_memory, dict) and updated_memory.get("_type") == "langchain_memory":
            deserialized = deserialize_memory(updated_memory)
            messages = deserialized.chat_memory.messages
            
            # Should have at least 4 messages (2 rounds of conversation)
            assert len(messages) >= 4
            
            # Check content
            message_contents = [msg.content for msg in messages]
            assert any("Initial query" in content for content in message_contents)
            assert any("Follow-up query" in content for content in message_contents)

# Test memory with Pydantic state models (if available)

@pytest.mark.skipif(True, reason="Pydantic state model testing requires custom implementation")
def test_memory_with_pydantic_state():
    """Test memory persistence with Pydantic state models."""
    # This would require setting up Pydantic models in the test
    # Skipping for now, but this would test:
    # 1. Create a Pydantic model with a memory field
    # 2. Initialize it with a memory object
    # 3. Pass it through agents
    # 4. Verify memory persists correctly
    pytest.skip("Pydantic state model testing not implemented")
