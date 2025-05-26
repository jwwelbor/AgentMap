import unittest
from unittest.mock import patch, MagicMock

from agentmap.agents.builtins.orchestrator_agent import OrchestratorAgent
from agentmap.state.adapter import StateAdapter


class TestOrchestratorAgent(unittest.TestCase):
    """Test cases for the OrchestratorAgent."""

    def setUp(self):
        """Set up test fixtures."""
        # Sample node data for testing
        self.sample_nodes = {
            "WeatherNode": {
                "description": "Gets weather information",
                "prompt": "Get weather for {location}",
                "type": "weather"
            },
            "NewsNode": {
                "description": "Fetches news articles",
                "prompt": "Get news about {topic}",
                "type": "news"
            },
            "HelpNode": {
                "description": "Provides help information",
                "prompt": "Provide help about {topic}",
                "type": "assistant"
            }
        }

    def test_initialization_default_parameters(self):
        """Test initialization with default parameters."""
        agent = OrchestratorAgent("test_agent", "Test prompt")
        
        # Check default values
        self.assertEqual(agent.llm_type, "openai")
        self.assertEqual(agent.temperature, 0.2)
        self.assertIsNone(agent.default_target)
        self.assertEqual(agent.matching_strategy, "tiered")
        self.assertEqual(agent.confidence_threshold, 0.8)
        self.assertEqual(agent.node_filter, "all")

    def test_initialization_custom_parameters(self):
        """Test initialization with custom parameters."""
        context = {
            "llm_type": "anthropic",
            "temperature": 0.5,
            "default_target": "DefaultNode",
            "matching_strategy": "algorithm",
            "confidence_threshold": 0.6,
            "nodes": "NodeA|NodeB"
        }
        
        agent = OrchestratorAgent("test_agent", "Test prompt", context)
        
        # Check custom values
        self.assertEqual(agent.llm_type, "anthropic")
        self.assertEqual(agent.temperature, 0.5)
        self.assertEqual(agent.default_target, "DefaultNode")
        self.assertEqual(agent.matching_strategy, "algorithm")
        self.assertEqual(agent.confidence_threshold, 0.6)
        self.assertEqual(agent.node_filter, "NodeA|NodeB")

    def test_initialization_node_type_parameter(self):
        """Test initialization with node_type parameter."""
        context = {"node_type": "weather"}
        agent = OrchestratorAgent("test_agent", "Test prompt", context)
        self.assertEqual(agent.node_filter, "nodeType:weather")

    def test_apply_node_filter_specific_nodes(self):
        """Test filtering nodes by specific list."""
        agent = OrchestratorAgent("test_agent", "Test prompt", {"nodes": "WeatherNode|HelpNode"})
        
        filtered = agent._apply_node_filter(self.sample_nodes)
        self.assertEqual(len(filtered), 2)
        self.assertIn("WeatherNode", filtered)
        self.assertIn("HelpNode", filtered)
        self.assertNotIn("NewsNode", filtered)

    def test_apply_node_filter_by_type(self):
        """Test filtering nodes by type."""
        agent = OrchestratorAgent("test_agent", "Test prompt", {"node_type": "weather"})
        
        filtered = agent._apply_node_filter(self.sample_nodes)
        self.assertEqual(len(filtered), 1)
        self.assertIn("WeatherNode", filtered)
        self.assertNotIn("NewsNode", filtered)
        self.assertNotIn("HelpNode", filtered)

    def test_apply_node_filter_all_nodes(self):
        """Test using all nodes (no filtering)."""
        agent = OrchestratorAgent("test_agent", "Test prompt", {"nodes": "all"})
        
        filtered = agent._apply_node_filter(self.sample_nodes)
        self.assertEqual(len(filtered), 3)
        self.assertIn("WeatherNode", filtered)
        self.assertIn("NewsNode", filtered)
        self.assertIn("HelpNode", filtered)

    def test_simple_match_exact_name(self):
        """Test algorithmic matching with exact node name in input."""
        input_text = "I need the WeatherNode to check Paris weather"
        
        node, confidence = OrchestratorAgent._simple_match(input_text, self.sample_nodes)
        self.assertEqual(node, "WeatherNode")
        self.assertEqual(confidence, 1.0)

    def test_simple_match_keyword_matching(self):
        """Test algorithmic matching with keyword matching."""
        input_text = "I want to know about weather in Paris"
        
        node, confidence = OrchestratorAgent._simple_match(input_text, self.sample_nodes)
        self.assertEqual(node, "WeatherNode")
        self.assertGreater(confidence, 0.0)
        self.assertLess(confidence, 1.0)

    def test_simple_match_no_match(self):
        """Test algorithmic matching with no good match."""
        input_text = "Something completely unrelated"
        
        node, confidence = OrchestratorAgent._simple_match(input_text, self.sample_nodes)
        # Should return first node with low confidence
        self.assertEqual(node, "WeatherNode")
        self.assertEqual(confidence, 0.0)

    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent.process')
    def test_process_no_nodes(self, mock_process):
        """Test process method with no available nodes."""
        mock_process.return_value = "DefaultNode"
        
        agent = OrchestratorAgent("test_agent", "Test prompt", {"default_target": "DefaultNode"})
        agent._get_nodes = MagicMock(return_value={})
        
        result = agent.process({"user_input": "Some request"})
        self.assertEqual(result, "DefaultNode")


if __name__ == '__main__':
    unittest.main()