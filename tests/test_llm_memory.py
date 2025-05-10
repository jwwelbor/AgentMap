import unittest
from unittest.mock import MagicMock, patch
from agentmap.agents.builtins.llm.llm_agent import LLMAgent

class MockLLMAgent(LLMAgent):
    """Mock implementation of LLMAgent for testing."""
    def _get_llm(self):
        # Return a mock LLM
        mock_llm = MagicMock()
        mock_llm.return_value = "Mock response"
        return mock_llm
        
    def _fallback_process(self, inputs):
        return "Fallback response"

class LLMAgentMemoryTests(unittest.TestCase):
    @patch('agentmap.agents.builtins.llm.llm_agent.LANGCHAIN_AVAILABLE', True)
    def test_memory_usage_in_llm_agent(self):
        """Test that LLMAgent correctly uses memory."""
        # Create agent with memory config
        agent = MockLLMAgent(
            "test_agent", 
            "Test prompt",
            context={
                "memory": {"type": "buffer"},
                "memory_key": "chat_history"
            }
        )
        
        # Process with inputs
        result = agent.process({"user_input": "Hello"})
        
        # Check result and memory
        self.assertIsInstance(result, dict)
        self.assertIn("output", result)
        self.assertIn("chat_history", result)
        self.assertEqual(result["output"], "Mock response")
        
        # Process again with memory from previous step
        result2 = agent.process({
            "user_input": "How are you?",
            "chat_history": result["chat_history"]
        })
        
        # Check updated memory
        self.assertIn("chat_history", result2)
        serialized_memory = result2["chat_history"]
        self.assertEqual(len(serialized_memory["messages"]), 4)  # 2 exchanges, 2 messages each