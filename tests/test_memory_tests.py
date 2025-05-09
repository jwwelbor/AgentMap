import unittest
from unittest.mock import patch
from langchain.memory import ConversationBufferMemory
from agentmap.agents.builtins.memory.utils import serialize_memory, deserialize_memory

class MemorySerializationTests(unittest.TestCase):
    def test_buffer_memory_serialization(self):
        """Test serialization of ConversationBufferMemory."""
        # Create memory with messages
        memory = ConversationBufferMemory(return_messages=True)
        memory.chat_memory.add_user_message("Hello")
        memory.chat_memory.add_ai_message("Hi there!")
        
        # Serialize
        serialized = serialize_memory(memory)
        
        # Check structure
        self.assertEqual(serialized["_type"], "langchain_memory")
        self.assertEqual(serialized["memory_type"], "buffer")
        self.assertEqual(len(serialized["messages"]), 2)
        self.assertEqual(serialized["messages"][0]["type"], "human")
        self.assertEqual(serialized["messages"][0]["content"], "Hello")
        
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
        self.assertEqual(len(serialized["messages"]), 6)  # 3 exchanges, 2 messages each
        
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
        memory = deserialize_memory(serialized)
        
        # Check memory object
        self.assertIsInstance(memory, ConversationBufferMemory)
        self.assertEqual(len(memory.chat_memory.messages), 2)
        self.assertEqual(memory.chat_memory.messages[0].content, "What's the weather?")
        
    def test_round_trip(self):
        """Test that serialization and deserialization preserve memory contents."""
        # Create original memory
        memory = ConversationBufferMemory(return_messages=True)
        memory.chat_memory.add_user_message("Hello")
        memory.chat_memory.add_ai_message("Hi there!")
        
        # Round trip
        serialized = serialize_memory(memory)
        deserialized = deserialize_memory(serialized)
        
        # Check equivalence
        self.assertEqual(len(memory.chat_memory.messages), len(deserialized.chat_memory.messages))
        self.assertEqual(memory.chat_memory.messages[0].content, deserialized.chat_memory.messages[0].content)
        self.assertEqual(memory.chat_memory.messages[1].content, deserialized.chat_memory.messages[1].content)