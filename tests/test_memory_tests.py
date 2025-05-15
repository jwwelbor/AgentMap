import unittest
from unittest.mock import patch, MagicMock, Mock

# Import functions under test
from agentmap.agents.builtins.memory.utils import serialize_memory, deserialize_memory


class MemorySerializationTests(unittest.TestCase):
    """Test serialization and deserialization of memory objects."""

    def setUp(self):
        """Set up common test fixtures."""
        # Skip tests if LangChain is not available

        # Import LangChain components
        from langchain.memory import ConversationBufferMemory
        from langchain.schema import HumanMessage, AIMessage

        # Create a basic memory with messages for use in tests
        self.memory = ConversationBufferMemory(return_messages=True)
        self.memory.chat_memory.add_user_message("Hello")
        self.memory.chat_memory.add_ai_message("Hi there!")

    def test_buffer_memory_serialization(self):
        """Test serialization of ConversationBufferMemory."""
        # Serialize the memory
        serialized = serialize_memory(self.memory)
        
        # Check structure
        self.assertEqual(serialized["_type"], "langchain_memory")
        self.assertEqual(serialized["memory_type"], "buffer")
        self.assertEqual(len(serialized["messages"]), 2)
        self.assertEqual(serialized["messages"][0]["type"], "human")
        self.assertEqual(serialized["messages"][0]["content"], "Hello")
        self.assertEqual(serialized["messages"][1]["type"], "ai")
        self.assertEqual(serialized["messages"][1]["content"], "Hi there!")
        
    def test_buffer_window_memory_serialization(self):
        """Test serialization of ConversationBufferWindowMemory."""
        from langchain.memory import ConversationBufferWindowMemory
        
        # Create memory with window size and messages
        memory = ConversationBufferWindowMemory(k=3, return_messages=True)
        for i in range(5):  # Add 5 exchanges, but window should be 3
            memory.chat_memory.add_user_message(f"User message {i}")
            memory.chat_memory.add_ai_message(f"AI message {i}")
        
        # Serialize
        serialized = serialize_memory(memory)
        
        # Check structure
        self.assertEqual(serialized["memory_type"], "buffer_window")
        self.assertEqual(serialized["k"], 3)
        # Should have the last 3 exchanges (6 messages)
        self.assertEqual(len(serialized["messages"]), 6)
        
    def test_token_buffer_memory_serialization(self):
        """Test serialization of ConversationTokenBufferMemory."""
        from langchain.memory import ConversationTokenBufferMemory
        
        # Create memory with token limit
        memory = ConversationTokenBufferMemory(max_token_limit=1000, return_messages=True)
        memory.chat_memory.add_user_message("Short user message")
        memory.chat_memory.add_ai_message("Short AI response")
        
        # Serialize
        serialized = serialize_memory(memory)
        
        # Check structure
        self.assertEqual(serialized["memory_type"], "token_buffer")
        self.assertEqual(serialized["max_token_limit"], 1000)
        self.assertEqual(len(serialized["messages"]), 2)
        
    def test_deserialization(self):
        """Test deserialization of memory object."""
        # Create serialized memory data
        serialized = {
            "_type": "langchain_memory",
            "memory_type": "buffer",
            "messages": [
                {"type": "human", "content": "What's the weather?"},
                {"type": "ai", "content": "It's sunny today."}
            ]
        }
        
        # Deserialize
        from langchain.memory import ConversationBufferMemory
        memory = deserialize_memory(serialized)
        
        # Check memory object
        self.assertIsInstance(memory, ConversationBufferMemory)
        self.assertEqual(len(memory.chat_memory.messages), 2)
        self.assertEqual(memory.chat_memory.messages[0].content, "What's the weather?")
        self.assertEqual(memory.chat_memory.messages[1].content, "It's sunny today.")
        
    def test_round_trip(self):
        """Test that serialization and deserialization preserve memory contents."""
        # Round trip
        serialized = serialize_memory(self.memory)
        deserialized = deserialize_memory(serialized)
        
        # Check equivalence
        self.assertEqual(len(self.memory.chat_memory.messages), len(deserialized.chat_memory.messages))
        self.assertEqual(self.memory.chat_memory.messages[0].content, deserialized.chat_memory.messages[0].content)
        self.assertEqual(self.memory.chat_memory.messages[1].content, deserialized.chat_memory.messages[1].content)

    def test_system_message_deserialization(self):
        """Test that system messages are correctly deserialized."""
        # Create serialized memory with system message
        serialized = {
            "_type": "langchain_memory",
            "memory_type": "buffer",
            "messages": [
                {"type": "system", "content": "You are a helpful assistant."},
                {"type": "human", "content": "Hello"},
                {"type": "ai", "content": "Hi there!"}
            ]
        }
        
        # Deserialize
        memory = deserialize_memory(serialized)
        
        # Check memory object
        self.assertEqual(len(memory.chat_memory.messages), 3)
        self.assertEqual(memory.chat_memory.messages[0].type, "system")
        self.assertEqual(memory.chat_memory.messages[0].content, "You are a helpful assistant.")


class MockedMemorySerializationTests(unittest.TestCase):
    """Tests memory serialization with mocks to isolate from LangChain."""
    
    @patch('agentmap.agents.builtins.memory.utils.ConversationBufferMemory')
    def test_serialize_with_mocked_memory(self, mock_memory_class):
        """Test serialization with mocked memory object."""
        # Create a mock memory instance
        mock_memory = MagicMock()
        mock_message1 = MagicMock(type="human", content="Hello")
        mock_message2 = MagicMock(type="ai", content="Hi there!")
        mock_memory.chat_memory.messages = [mock_message1, mock_message2]
        
        # Serialize the mock memory
        serialized = serialize_memory(mock_memory)
        
        # Check structure
        self.assertEqual(serialized["_type"], "langchain_memory")
        self.assertEqual(serialized["memory_type"], "buffer")
        self.assertEqual(len(serialized["messages"]), 2)
        self.assertEqual(serialized["messages"][0]["type"], "human")
        self.assertEqual(serialized["messages"][0]["content"], "Hello")
        
    @patch('agentmap.agents.builtins.memory.utils.ConversationBufferMemory')
    def test_deserialize_with_mocked_classes(self, mock_memory_class):
        """Test deserialization with mocked LangChain classes."""
        # Setup the mock memory classes
        mock_memory_instance = MagicMock()
        mock_memory_class.return_value = mock_memory_instance
        
        # Create serialized memory data
        serialized = {
            "_type": "langchain_memory",
            "memory_type": "buffer",
            "messages": [
                {"type": "human", "content": "Hello"},
                {"type": "ai", "content": "Hi there!"}
            ]
        }
        
        # Deserialize
        memory = deserialize_memory(serialized)
        
        # Verify the memory was created correctly
        mock_memory_class.assert_called_once()
        self.assertEqual(mock_memory_instance.chat_memory.add_user_message.call_count, 1)
        self.assertEqual(mock_memory_instance.chat_memory.add_ai_message.call_count, 1)
        mock_memory_instance.chat_memory.add_user_message.assert_called_with("Hello")
        mock_memory_instance.chat_memory.add_ai_message.assert_called_with("Hi there!")


class ErrorCaseTests(unittest.TestCase):
    """Test error handling during serialization and deserialization."""
    
    def test_serialize_none(self):
        """Test serializing None."""
        result = serialize_memory(None)
        self.assertIsNone(result)
    
    def test_serialize_non_memory_object(self):
        """Test serializing an object that's not a memory."""
        # Create a regular object without chat_memory attribute
        class FakeObject:
            pass
        
        obj = FakeObject()
        result = serialize_memory(obj)
        # Should return the object unchanged
        self.assertIs(result, obj)
    
    def test_deserialize_none(self):
        """Test deserializing None."""
        result = deserialize_memory(None)
        self.assertIsNone(result)
    
    def test_deserialize_non_dict(self):
        """Test deserializing a non-dict value."""
        result = deserialize_memory("not a dict")
        self.assertEqual(result, "not a dict")
    
    def test_deserialize_wrong_type(self):
        """Test deserializing a dict without the correct _type."""
        data = {"foo": "bar"}
        result = deserialize_memory(data)
        self.assertEqual(result, data)
    
    def test_deserialize_without_langchain(self):
        """Test deserializing when LangChain is not available."""
        data = {
            "_type": "langchain_memory",
            "memory_type": "buffer", 
            "messages": []
        }
        result = deserialize_memory(data)
        # Should return the original data unchanged
        self.assertEqual(result, data)
    
    @patch('agentmap.agents.builtins.memory.utils.ConversationBufferMemory')
    def test_deserialize_with_exception(self, mock_memory_class):
        """Test deserializing when an exception occurs."""
        # Make the memory constructor raise an exception
        mock_memory_class.side_effect = Exception("Test error")
        
        data = {
            "_type": "langchain_memory",
            "memory_type": "buffer", 
            "messages": []
        }
        result = deserialize_memory(data)
        # Should return the original data unchanged
        self.assertEqual(result, data)


class StateAdapterIntegrationTests(unittest.TestCase):
    """Test integration with StateAdapter."""
    
    def test_state_adapter_with_memory(self):
        """Test StateAdapter handling of memory objects."""
        from agentmap.state.adapter import StateAdapter
        
        # Skip if StateAdapter is not available
        try:
            from agentmap.state.adapter import StateAdapter
        except ImportError:
            self.skipTest("StateAdapter is not available")
        
        # Create a mock memory object
        mock_memory = MagicMock()
        mock_memory.chat_memory.messages = []
        
        # Create a state with memory
        state = {"conversation_memory": mock_memory}
        
        # Mock serialize_memory to verify it's called
        with patch('agentmap.agents.builtins.memory.utils.serialize_memory') as mock_serialize:
            mock_serialize.return_value = {"_type": "langchain_memory", "memory_type": "buffer", "messages": []}
            
            # Set memory in state, which should trigger serialization
            StateAdapter.set_value(state, "conversation_memory", mock_memory)
            
            # Verify serialization was called
            mock_serialize.assert_called_once_with(mock_memory)


if __name__ == '__main__':
    unittest.main()
