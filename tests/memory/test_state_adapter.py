"""
Tests for the StateAdapter class focusing on memory handling.

The StateAdapter is responsible for retrieving and setting values in the
state, with special handling for memory objects.
"""
import pytest
from unittest.mock import MagicMock, patch

try:
    from langchain.memory import ConversationBufferMemory
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False

from agentmap.agents.features import HAS_LLM_AGENTS
from agentmap.state.adapter import StateAdapter
from agentmap.agents.builtins.memory.utils import serialize_memory, deserialize_memory

# Skip tests if dependencies aren't available
pytestmark = pytest.mark.skipif(
    not HAS_LANGCHAIN,
    reason="LangChain not installed. Install with: pip install langchain"
)

# Test fixtures

@pytest.fixture
def memory_object():
    """Create a simple memory object for testing."""
    memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    memory.chat_memory.add_user_message("Test message")
    memory.chat_memory.add_ai_message("Test response")
    return memory

@pytest.fixture
def serialized_memory(memory_object):
    """Create a serialized memory dictionary."""
    return serialize_memory(memory_object)

@pytest.fixture
def dict_state(serialized_memory):
    """Create a dictionary state with serialized memory."""
    return {
        "input": "Test input",
        "conversation_memory": serialized_memory,
        "output": "Test output"
    }

# Test special memory handling in StateAdapter

def test_get_value_with_memory(dict_state):
    """Test that StateAdapter.get_value correctly handles memory objects."""
    # Get memory from state
    memory = StateAdapter.get_value(dict_state, "conversation_memory")
    
    # Should be deserialized to a memory object
    assert memory is not None
    assert hasattr(memory, "chat_memory")
    assert len(memory.chat_memory.messages) == 2
    assert memory.chat_memory.messages[0].content == "Test message"
    assert memory.chat_memory.messages[1].content == "Test response"

def test_set_value_with_memory(dict_state, memory_object):
    """Test that StateAdapter.set_value correctly handles memory objects."""
    # Add another message to memory
    memory_object.chat_memory.add_user_message("Second test message")
    
    # Update state with the modified memory
    new_state = StateAdapter.set_value(dict_state, "conversation_memory", memory_object)
    
    # Get the memory back
    updated_memory = StateAdapter.get_value(new_state, "conversation_memory")
    
    # Should now have 3 messages
    assert updated_memory is not None
    assert hasattr(updated_memory, "chat_memory")
    assert len(updated_memory.chat_memory.messages) == 3
    assert updated_memory.chat_memory.messages[2].content == "Second test message"

def test_get_value_with_nonexistent_key(dict_state):
    """Test that StateAdapter.get_value correctly handles nonexistent keys."""
    value = StateAdapter.get_value(dict_state, "nonexistent_key")
    assert value is None
    
    value = StateAdapter.get_value(dict_state, "nonexistent_key", "default")
    assert value == "default"

def test_set_value_with_serialized_memory(dict_state, serialized_memory):
    """Test that StateAdapter.set_value correctly handles serialized memory dictionaries."""
    # Modify the serialized memory
    modified_memory = serialized_memory.copy()
    modified_memory["messages"].append({"type": "human", "content": "New message"})
    
    # Update state with modified serialized memory
    new_state = StateAdapter.set_value(dict_state, "conversation_memory", modified_memory)
    
    # Get the memory back - should be deserialized
    updated_memory = StateAdapter.get_value(new_state, "conversation_memory")
    
    # Should now have 3 messages
    assert updated_memory is not None
    assert hasattr(updated_memory, "chat_memory")
    assert len(updated_memory.chat_memory.messages) == 3
    assert updated_memory.chat_memory.messages[2].content == "New message"

# Test StateAdapter with different state types

def test_get_value_from_dict():
    """Test StateAdapter.get_value with a plain dictionary state."""
    state = {"key": "value", "nested": {"subkey": "subvalue"}}
    
    assert StateAdapter.get_value(state, "key") == "value"
    assert StateAdapter.get_value(state, "nested") == {"subkey": "subvalue"}
    assert StateAdapter.get_value(state, "nonexistent") is None

def test_set_value_with_dict():
    """Test StateAdapter.set_value with a plain dictionary state."""
    state = {"key": "value"}
    
    new_state = StateAdapter.set_value(state, "key", "new_value")
    assert new_state["key"] == "new_value"
    
    new_state = StateAdapter.set_value(state, "new_key", "new_value")
    assert new_state["new_key"] == "new_value"
    assert "new_key" not in state  # Original state should be unmodified

# Test with Pydantic-like objects (if available)

class MockPydanticModel:
    """Mock implementation of a Pydantic-like model for testing."""
    
    def __init__(self, **data):
        self._data = data
        for key, value in data.items():
            setattr(self, key, value)
    
    def dict(self):
        """Mimic Pydantic v1 dict() method."""
        return self._data.copy()
    
    def model_dump(self):
        """Mimic Pydantic v2 model_dump() method."""
        return self._data.copy()
        
    def __getitem__(self, key):
        """Support dict-like access."""
        return self._data[key]

def test_get_value_with_pydantic_like():
    """Test StateAdapter.get_value with a Pydantic-like object."""
    model = MockPydanticModel(
        input="Test input",
        conversation_memory={"_type": "langchain_memory", "messages": []},
        output="Test output"
    )
    
    assert StateAdapter.get_value(model, "input") == "Test input"
    assert StateAdapter.get_value(model, "output") == "Test output"
    
    # Should handle memory field
    memory = StateAdapter.get_value(model, "conversation_memory")
    assert memory is not None
    assert isinstance(memory, dict)
    assert memory["_type"] == "langchain_memory"

def test_set_value_with_pydantic_like():
    """Test StateAdapter.set_value with a Pydantic-like object."""
    model = MockPydanticModel(
        input="Test input",
        conversation_memory={"_type": "langchain_memory", "messages": []},
        output="Test output"
    )
    
    # Test setting regular values
    new_model = StateAdapter.set_value(model, "input", "New input")
    assert isinstance(new_model, MockPydanticModel)
    assert new_model.input == "New input"
    assert model.input == "Test input"  # Original should be unmodified
    
    # Test setting memory values with Pydantic v1 style
    with patch.object(MockPydanticModel, 'model_dump', None):
        memory = ConversationBufferMemory(return_messages=True, memory_key="history")
        memory.chat_memory.add_user_message("Test message")
        
        new_model = StateAdapter.set_value(model, "conversation_memory", memory)
        assert isinstance(new_model, MockPydanticModel)
        
        # The memory should have been serialized
        assert new_model.conversation_memory is not None
        assert isinstance(new_model.conversation_memory, dict)
        assert new_model.conversation_memory["_type"] == "langchain_memory"
        assert len(new_model.conversation_memory["messages"]) == 1
        assert new_model.conversation_memory["messages"][0]["content"] == "Test message"
    
    # Test setting memory values with Pydantic v2 style
    memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    memory.chat_memory.add_user_message("V2 message")
    
    new_model = StateAdapter.set_value(model, "conversation_memory", memory)
    assert isinstance(new_model, MockPydanticModel)
    
    # The memory should have been serialized
    assert new_model.conversation_memory is not None
    assert isinstance(new_model.conversation_memory, dict)
    assert new_model.conversation_memory["_type"] == "langchain_memory"
    assert len(new_model.conversation_memory["messages"]) == 1
    assert new_model.conversation_memory["messages"][0]["content"] == "V2 message"

# Test memory handling with custom memory keys

def test_custom_memory_key_handling():
    """Test special memory handling with custom memory key names."""
    # Create memory
    memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    memory.chat_memory.add_user_message("Test message")
    
    # Create state with custom memory key
    state = {
        "input": "Test input",
        "custom_memory_key": memory
    }
    
    # Get the memory back - should recognize it as memory despite custom key
    retrieved = StateAdapter.get_value(state, "custom_memory_key")
    assert hasattr(retrieved, "chat_memory")
    assert len(retrieved.chat_memory.messages) == 1
    
    # Update with serialized memory
    serialized = serialize_memory(memory)
    new_state = StateAdapter.set_value({}, "another_memory_key", serialized)
    
    # Get it back - should be deserialized despite custom key
    retrieved = StateAdapter.get_value(new_state, "another_memory_key")
    assert hasattr(retrieved, "chat_memory")
    assert len(retrieved.chat_memory.messages) == 1

# Test for special handling of dynamic memory key detection

def test_detect_memory_object():
    """Test that StateAdapter correctly identifies memory objects by their attributes."""
    # Regular memory object
    memory = ConversationBufferMemory(return_messages=True, memory_key="history")
    state = {"regular_field": memory}
    
    # Should be identified as memory despite non-standard key
    retrieved = StateAdapter.get_value(state, "regular_field")
    assert hasattr(retrieved, "chat_memory")
    
    # Dictionary that looks like serialized memory
    memory_dict = {
        "_type": "langchain_memory",
        "memory_type": "buffer",
        "messages": [{"type": "human", "content": "Hello"}]
    }
    state = {"looks_like_memory": memory_dict}
    
    # Should be identified as serialized memory despite non-standard key
    retrieved = StateAdapter.get_value(state, "looks_like_memory")
    assert hasattr(retrieved, "chat_memory")
    assert len(retrieved.chat_memory.messages) == 1
    
    # Other random dictionary
    not_memory = {"foo": "bar"}
    state = {"not_memory": not_memory}
    
    # Should not be treated as memory
    retrieved = StateAdapter.get_value(state, "not_memory")
    assert not hasattr(retrieved, "chat_memory")
    assert retrieved == not_memory

# Test handling of memory without deserializable structure

def test_invalid_memory_format():
    """Test handling of invalid memory formats."""
    # Invalid memory format
    invalid_memory = {
        "_type": "langchain_memory",
        "memory_type": "invalid_type",
        "messages": "not a list"
    }
    state = {"invalid_memory": invalid_memory}
    
    # Should return the original structure if deserialization fails
    retrieved = StateAdapter.get_value(state, "invalid_memory")
    assert retrieved == invalid_memory
    
    # Empty memory dictionary
    empty_memory = {"_type": "langchain_memory"}
    state = {"empty_memory": empty_memory}
    
    # Should return the original structure
    retrieved = StateAdapter.get_value(state, "empty_memory")
    assert retrieved == empty_memory
