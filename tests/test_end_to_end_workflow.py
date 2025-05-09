import unittest
from unittest.mock import patch
from agentmap.runner import run_graph
from agentmap.graph.builder import GraphBuilder
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
                "GraphName", "Node", "Edge", "Context", "AgentType", 
                "Success_Next", "Failure_Next", "Input_Fields", "Output_Field", "Prompt"
            ])
            # Node 1 with memory initialization
            writer.writerow([
                "TestGraph", "Node1", "", 
                '{"memory":{"type":"buffer","memory_key":"chat_memory"}}', 
                "echo", "Node2", "", "input", "output", "Echo: {input}"
            ])
            # Node 2 using memory from Node 1
            writer.writerow([
                "TestGraph", "Node2", "", 
                '{"memory":{"memory_key":"chat_memory"}}',
                "echo", "", "", "input|output|chat_memory", "final_output", 
                "Previous: {output}, New: {input}"
            ])
    
    def tearDown(self):
        """Clean up the test CSV."""
        os.close(self.csv_fd)
        os.unlink(self.csv_path)
        
    @patch('agentmap.agents.builtins.echo_agent.EchoAgent.process')
    def test_memory_flow_through_graph(self, mock_process):
        """Test memory flows through graph nodes correctly."""
        # Mock the EchoAgent.process method to handle memory
        def mock_echo_process(self, inputs):
            output = f"Echo: {inputs.get('input', '')}"
            
            # If there's memory, get it
            memory = inputs.get("chat_memory")
            
            # Add to memory and return if available
            if hasattr(self, "memory") and self.memory:
                # Add to memory
                self.memory.chat_memory.add_user_message(inputs.get('input', ''))
                self.memory.chat_memory.add_ai_message(output)
                
                # Serialize memory for output
                from agentmap.agents.builtins.memory.utils import serialize_memory
                serialized_memory = serialize_memory(self.memory)
                
                # Return with memory
                return {
                    self.output_field: output,
                    "chat_memory": serialized_memory
                }
            
            return output
            
        mock_process.side_effect = mock_echo_process
        
        # Run the graph
        result = run_graph(
            graph_name="TestGraph",
            initial_state={"input": "Hello"},
            csv_path=self.csv_path
        )
        
        # Check result
        self.assertIn("final_output", result)
        self.assertIn("chat_memory", result)
        
        # Verify memory structure
        memory = result["chat_memory"]
        self.assertEqual(memory["_type"], "langchain_memory")
        self.assertGreaterEqual(len(memory["messages"]), 2)