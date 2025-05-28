import unittest
from agentmap.state.adapter import StateAdapter
from langchain.memory import ConversationBufferMemory

class StateAdapterMemoryTests(unittest.TestCase):
    # def test_state_adapter_memory_handling(self):
    #     """Test StateAdapter handling of memory objects."""
    #     # Create a state dict
    #     state = {}
        
    #     # Create a memory object
    #     memory = ConversationBufferMemory(return_messages=True)
    #     memory.chat_memory.add_user_message("Test message")
        
    #     # Set memory in state
    #     new_state = StateAdapter.set_value(state, "chat_memory", memory)
        
    #     # Check that it's serialized
    #     self.assertIsInstance(new_state["chat_memory"], dict)
    #     self.assertEqual(new_state["chat_memory"]["_type"], "langchain_memory")
        
    #     # Retrieve and check deserialization
    #     retrieved = StateAdapter.get_value(new_state, "chat_memory")
    #     self.assertIsInstance(retrieved, ConversationBufferMemory)
    #     self.assertEqual(retrieved.chat_memory.messages[0].content, "Test message")
        
    def test_state_adapter_regular_values(self):
        """Test StateAdapter handles regular values normally."""
        state = {}
        
        # Set a regular value
        new_state = StateAdapter.set_value(state, "regular_key", "regular_value")
        
        # Check that it's unchanged
        self.assertEqual(new_state["regular_key"], "regular_value")
        
        # Retrieve and check
        retrieved = StateAdapter.get_value(new_state, "regular_key")
        self.assertEqual(retrieved, "regular_value")