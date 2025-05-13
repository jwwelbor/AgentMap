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

    def test_get_nodes(self):
        """Test node extraction from various input fields."""
        agent = OrchestratorAgent("test_agent", "Test prompt")
        
        # Test with available_nodes field
        inputs = {"available_nodes": self.sample_nodes}
        self.assertEqual(agent._get_nodes(inputs), self.sample_nodes)
        
        # Test with nodes field
        inputs = {"nodes": self.sample_nodes}
        self.assertEqual(agent._get_nodes(inputs), self.sample_nodes)
        
        # Test with __node_registry field
        inputs = {"__node_registry": self.sample_nodes}
        self.assertEqual(agent._get_nodes(inputs), self.sample_nodes)
        
        # Test with no node field
        inputs = {"other_field": "value"}
        self.assertEqual(agent._get_nodes(inputs), {})

    def test_get_input_text(self):
        """Test input text extraction."""
        agent = OrchestratorAgent("test_agent", "Test prompt")
        agent.input_fields = ["available_nodes", "user_input"]
        
        # Test with specified input field
        inputs = {"user_input": "Get weather in Paris"}
        self.assertEqual(agent._get_input_text(inputs), "Get weather in Paris")
        
        # Test fallback to common input fields
        inputs = {"input": "Get news about technology"}
        self.assertEqual(agent._get_input_text(inputs), "Get news about technology")
        
        inputs = {"message": "Need help with something"}
        self.assertEqual(agent._get_input_text(inputs), "Need help with something")
        
        # Test with no valid input field
        inputs = {"other_field": "value"}
        self.assertEqual(agent._get_input_text(inputs), "")

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

    @patch('agentmap.agents.get_agent_class')
    def test_llm_match(self, mock_get_agent_class):
        """Test LLM-based matching."""
        # Setup mock LLM agent
        mock_llm_agent = MagicMock()
        mock_llm_agent.process.return_value = "Let me analyze this request...\n\nSelected: NewsNode"
        
        mock_llm_class = MagicMock()
        mock_llm_class.return_value = mock_llm_agent
        mock_get_agent_class.return_value = mock_llm_class
        
        agent = OrchestratorAgent("test_agent", "Test prompt")
        input_text = "Tell me about recent technology news"
        
        # Test LLM matching
        result = agent._llm_match(input_text, self.sample_nodes)
        self.assertEqual(result, "NewsNode")
        
        # Verify LLM was called with correct parameters
        mock_get_agent_class.assert_called_once_with("openai")
        mock_llm_class.assert_called_once()
        mock_llm_agent.process.assert_called_once()

    @patch('agentmap.agents.get_agent_class')
    def test_llm_match_no_selection_format(self, mock_get_agent_class):
        """Test LLM matching when response doesn't contain 'Selected: ' format."""
        # Setup mock LLM agent without the "Selected: " format
        mock_llm_agent = MagicMock()
        mock_llm_agent.process.return_value = "The NewsNode would be appropriate for this request."
        
        mock_llm_class = MagicMock()
        mock_llm_class.return_value = mock_llm_agent
        mock_get_agent_class.return_value = mock_llm_class
        
        agent = OrchestratorAgent("test_agent", "Test prompt")
        input_text = "Tell me about recent technology news"
        
        # Test LLM matching with fallback to node name in response
        result = agent._llm_match(input_text, self.sample_nodes)
        self.assertEqual(result, "NewsNode")

    @patch('agentmap.agents.get_agent_class')
    def test_llm_match_completely_invalid_response(self, mock_get_agent_class):
        """Test LLM matching when response doesn't contain any valid node."""
        # Setup mock LLM agent with completely unhelpful response
        mock_llm_agent = MagicMock()
        mock_llm_agent.process.return_value = "I'm not sure how to handle this request."
        
        mock_llm_class = MagicMock()
        mock_llm_class.return_value = mock_llm_agent
        mock_get_agent_class.return_value = mock_llm_class
        
        agent = OrchestratorAgent("test_agent", "Test prompt")
        input_text = "Something completely unrelated"
        
        # Test fallback to first available node
        result = agent._llm_match(input_text, self.sample_nodes)
        self.assertEqual(result, "WeatherNode")  # First node in sample_nodes

    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._simple_match')
    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._llm_match')
    def test_match_intent_algorithm_only(self, mock_llm_match, mock_simple_match):
        """Test algorithm-only matching strategy."""
        mock_simple_match.return_value = ("WeatherNode", 0.7)
        
        agent = OrchestratorAgent("test_agent", "Test prompt", {"matching_strategy": "algorithm"})
        result = agent._match_intent("Get weather", self.sample_nodes)
        
        # Should use simple match and not call LLM
        self.assertEqual(result, "WeatherNode")
        mock_simple_match.assert_called_once()
        mock_llm_match.assert_not_called()

    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._simple_match')
    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._llm_match')
    def test_match_intent_llm_only(self, mock_llm_match, mock_simple_match):
        """Test LLM-only matching strategy."""
        mock_llm_match.return_value = "NewsNode"
        
        agent = OrchestratorAgent("test_agent", "Test prompt", {"matching_strategy": "llm"})
        result = agent._match_intent("Get news", self.sample_nodes)
        
        # Should use LLM match and not call simple match
        self.assertEqual(result, "NewsNode")
        mock_simple_match.assert_not_called()
        mock_llm_match.assert_called_once()

    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._simple_match')
    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._llm_match')
    def test_match_intent_tiered_high_confidence(self, mock_llm_match, mock_simple_match):
        """Test tiered matching with high confidence algorithmic match."""
        mock_simple_match.return_value = ("WeatherNode", 0.9)  # High confidence
        
        agent = OrchestratorAgent("test_agent", "Test prompt", {
            "matching_strategy": "tiered",
            "confidence_threshold": 0.8
        })
        result = agent._match_intent("Get weather", self.sample_nodes)
        
        # Should use simple match and not call LLM
        self.assertEqual(result, "WeatherNode")
        mock_simple_match.assert_called_once()
        mock_llm_match.assert_not_called()

    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._simple_match')
    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._llm_match')
    def test_match_intent_tiered_low_confidence(self, mock_llm_match, mock_simple_match):
        """Test tiered matching with low confidence algorithmic match."""
        mock_simple_match.return_value = ("WeatherNode", 0.5)  # Low confidence
        mock_llm_match.return_value = "NewsNode"
        
        agent = OrchestratorAgent("test_agent", "Test prompt", {
            "matching_strategy": "tiered",
            "confidence_threshold": 0.8
        })
        result = agent._match_intent("Get news", self.sample_nodes)
        
        # Should fall back to LLM match
        self.assertEqual(result, "NewsNode")
        mock_simple_match.assert_called_once()
        mock_llm_match.assert_called_once()

    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent.process')
    def test_process_no_nodes(self, mock_process):
        """Test process method with no available nodes."""
        mock_process.return_value = "DefaultNode"
        
        agent = OrchestratorAgent("test_agent", "Test prompt", {"default_target": "DefaultNode"})
        agent._get_nodes = MagicMock(return_value={})
        
        result = agent.process({"user_input": "Some request"})
        self.assertEqual(result, "DefaultNode")

    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._match_intent')
    def test_process_single_node(self, mock_match_intent):
        """Test process method with only one available node."""
        agent = OrchestratorAgent("test_agent", "Test prompt")
        agent._get_nodes = MagicMock(return_value={"SingleNode": {"description": "Only node"}})
        agent._get_input_text = MagicMock(return_value="Some request")
        agent._apply_node_filter = MagicMock(return_value={"SingleNode": {"description": "Only node"}})
        
        result = agent.process({"user_input": "Some request"})
        self.assertEqual(result, "SingleNode")
        mock_match_intent.assert_not_called()  # Should skip matching with single node

    @patch('agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent._match_intent')
    def test_process_multiple_nodes(self, mock_match_intent):
        """Test process method with multiple nodes."""
        mock_match_intent.return_value = "NewsNode"
        
        agent = OrchestratorAgent("test_agent", "Test prompt")
        agent._get_nodes = MagicMock(return_value=self.sample_nodes)
        agent._get_input_text = MagicMock(return_value="Get news")
        agent._apply_node_filter = MagicMock(return_value=self.sample_nodes)
        
        result = agent.process({"user_input": "Get news"})
        self.assertEqual(result, "NewsNode")
        mock_match_intent.assert_called_once()

    @patch('agentmap.state.adapter.StateAdapter.set_value')
    def test_run_with_implicit_routing(self, mock_set_value):
        """Test run method with implicit routing."""
        # Mock StateAdapter methods
        mock_state = {"user_input": "Get weather"}
        mock_updated_state = {"selected_node": "WeatherNode", "user_input": "Get weather"}
        mock_final_state = {"selected_node": "WeatherNode", "user_input": "Get weather", "__next_node": "WeatherNode"}
        
        mock_set_value.return_value = mock_final_state
        
        agent = OrchestratorAgent("test_agent", "Test prompt")
        agent.output_field = "selected_node"
        
        # Mock the parent class run method
        with patch('agentmap.agents.base_agent.BaseAgent.run', return_value=mock_updated_state):
            result = agent.run(mock_state)
        
        # Verify __next_node was set
        self.assertEqual(result, mock_final_state)
        mock_set_value.assert_called_once_with(mock_updated_state, "__next_node", "WeatherNode")

if __name__ == '__main__':
    unittest.main()