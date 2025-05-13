import unittest
from unittest.mock import patch
from agentmap.runner import run_graph
import tempfile
import csv
import os

class WorkflowMemoryTests(unittest.TestCase):
    def setUp(self):
        """Create a test CSV with memory configuration."""
        self.csv_fd, self.csv_path = tempfile.mkstemp(suffix='.csv')
        with open(self.csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "GraphName", "Node", "Edge", "Context", "AgentType", "Success_Next", "Failure_Next", 
                "Input_Fields", "Output_Field", "Prompt"
            ])
            # Use OpenAI agent with memory
            writer.writerow([
                "TestGraph", "Node1", "", '{"memory":{"type":"buffer","memory_key":"chat_memory"}}', 
                "openai", "Node2", "", "input", "output", "Echo: {input}"
            ])
            writer.writerow([
                "TestGraph", "Node2", "", '{"memory":{"memory_key":"chat_memory"}}', 
                "openai", "", "", "input|output|chat_memory", "final_output", "Prior: {output}, New: {input}"
            ])
    
    def tearDown(self):
        """Clean up the test CSV."""
        os.close(self.csv_fd)
        os.unlink(self.csv_path)
    
    @patch('agentmap.agents.builtins.llm.llm_agent.LANGCHAIN_AVAILABLE', True)
    @patch('agentmap.agents.builtins.llm.openai_agent.OpenAIAgent._get_llm')
    def test_memory_flow_through_graph(self, mock_get_llm):
        """Test memory flows correctly through the workflow."""
        # Simple mock that returns a response
        mock_llm = mock_get_llm.return_value
        mock_llm.side_effect = lambda x: "LLM response"
        
        # Run the graph
        result = run_graph(
            graph_name="TestGraph",
            initial_state={"input": "Test Input"},
            csv_path=self.csv_path
        )
        
        # Check for memory in result
        self.assertIn("chat_memory", result)
        
        # Verify memory structure
        memory = result["chat_memory"]
        self.assertEqual(memory["_type"], "langchain_memory")
        
        # Verify messages in memory - should have at least 2 exchanges (4 messages)
        self.assertIn("messages", memory)
        self.assertGreaterEqual(len(memory["messages"]), 4)