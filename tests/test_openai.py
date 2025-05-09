import unittest
from unittest.mock import patch, MagicMock
from agentmap.agents.builtins.openai_agent import OpenAIAgent

class OpenAIAgentTests(unittest.TestCase):
    @patch('openai.ChatCompletion.create')
    def test_openai_agent_with_memory(self, mock_create):
        """Test OpenAI agent with memory integration."""
        # Mock the API call
        mock_create.return_value = {
            'choices': [{'message': {'content': 'Test response'}}]
        }
        
        # Create agent with memory config
        agent = OpenAIAgent(
            "test_agent", 
            "Hello, {input}",
            context={
                "memory": {"type": "buffer"},
                "memory_key": "chat_memory"
            }
        )
        
        # Execute with state
        state = {"input": "test input"}
        result = agent.run(state)
        
        # Check memory in result
        self.assertIn("chat_memory", result)
        memory_data = result["chat_memory"]
        self.assertEqual(memory_data["_type"], "langchain_memory")
        self.assertEqual(len(memory_data["messages"]), 2)  # One exchange (human + AI)