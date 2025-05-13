import unittest
from unittest.mock import patch, MagicMock

from agentmap.agents.builtins.summary_agent import SummaryAgent
from agentmap.state.adapter import StateAdapter


class TestSummaryAgent(unittest.TestCase):
    """Test cases for the SummaryAgent."""

    def setUp(self):
        """Set up test fixtures."""
        # Sample input data for testing
        self.sample_inputs = {
            "weather": "Sunny with a high of 75°F",
            "news": "Breaking news: Stock market reaches all-time high",
            "sports": "Local team wins championship"
        }

    def test_initialization_default_parameters(self):
        """Test initialization with default parameters."""
        agent = SummaryAgent("test_agent", "Test prompt")
        
        # Check default values
        self.assertEqual(agent.format_template, "{key}: {value}")
        self.assertEqual(agent.separator, "\n\n")
        self.assertTrue(agent.include_keys)
        self.assertFalse(agent.use_llm)
        self.assertIsNone(agent.llm_type)

    def test_initialization_custom_parameters(self):
        """Test initialization with custom parameters."""
        context = {
            "format": "<{key}> {value}",
            "separator": "\n---\n",
            "include_keys": False,
            "llm": "openai"
        }
        
        agent = SummaryAgent("test_agent", "Test prompt", context)
        
        # Check custom values
        self.assertEqual(agent.format_template, "<{key}> {value}")
        self.assertEqual(agent.separator, "\n---\n")
        self.assertFalse(agent.include_keys)
        self.assertTrue(agent.use_llm)
        self.assertEqual(agent.llm_type, "openai")

    def test_basic_concatenation_with_keys(self):
        """Test basic concatenation mode with keys included."""
        agent = SummaryAgent("test_agent", "Test prompt")
        
        result = agent._basic_concatenation(self.sample_inputs)
        
        # Check that result contains all input values with keys
        self.assertIn("weather: Sunny with a high of 75°F", result)
        self.assertIn("news: Breaking news: Stock market reaches all-time high", result)
        self.assertIn("sports: Local team wins championship", result)
        
        # Check separator
        lines = result.split("\n\n")
        self.assertEqual(len(lines), 3)  # 3 inputs = 3 lines with default separator

    def test_basic_concatenation_without_keys(self):
        """Test basic concatenation mode without keys."""
        agent = SummaryAgent("test_agent", "Test prompt", {"include_keys": False})
        
        result = agent._basic_concatenation(self.sample_inputs)
        
        # Check that result contains all input values without keys
        self.assertIn("Sunny with a high of 75°F", result)
        self.assertIn("Breaking news: Stock market reaches all-time high", result)
        self.assertIn("Local team wins championship", result)
        
        # Values should not be prefixed with keys
        self.assertNotIn("weather:", result)
        self.assertNotIn("news:", result)
        self.assertNotIn("sports:", result)

    def test_basic_concatenation_custom_format(self):
        """Test basic concatenation with custom format template."""
        agent = SummaryAgent("test_agent", "Test prompt", {
            "format": "## {key} ##\n{value}"
        })
        
        result = agent._basic_concatenation(self.sample_inputs)
        
        # Check custom formatting
        self.assertIn("## weather ##\nSunny with a high of 75°F", result)
        self.assertIn("## news ##\nBreaking news: Stock market reaches all-time high", result)
        self.assertIn("## sports ##\nLocal team wins championship", result)

    def test_basic_concatenation_custom_separator(self):
        """Test basic concatenation with custom separator."""
        agent = SummaryAgent("test_agent", "Test prompt", {
            "separator": "\n-----\n"
        })
        
        result = agent._basic_concatenation(self.sample_inputs)
        
        # Check separator
        lines = result.split("\n-----\n")
        self.assertEqual(len(lines), 3)  # 3 inputs = 3 lines with custom separator

    def test_basic_concatenation_none_values(self):
        """Test basic concatenation with None values in input."""
        inputs = {
            "weather": "Sunny with a high of 75°F",
            "news": None,
            "sports": "Local team wins championship"
        }
        
        agent = SummaryAgent("test_agent", "Test prompt")
        
        result = agent._basic_concatenation(inputs)
        
        # None values should be skipped
        self.assertIn("weather: Sunny with a high of 75°F", result)
        self.assertIn("sports: Local team wins championship", result)
        self.assertNotIn("news:", result)
        
        # Only 2 items should be in result
        lines = result.split("\n\n")
        self.assertEqual(len(lines), 2)

    def test_basic_concatenation_empty_inputs(self):
        """Test basic concatenation with empty inputs."""
        agent = SummaryAgent("test_agent", "Test prompt")
        
        result = agent._basic_concatenation({})
        
        # Result should be empty
        self.assertEqual(result, "")

    def test_format_error_handling(self):
        """Test handling of format errors."""
        agent = SummaryAgent("test_agent", "Test prompt", {
            "format": "{key}: {value} - {missing}"  # Format with missing placeholder
        })
        
        result = agent._basic_concatenation(self.sample_inputs)
        
        # Should fall back to "key: value" format
        self.assertIn("weather: Sunny with a high of 75°F", result)
        self.assertIn("news: Breaking news: Stock market reaches all-time high", result)
        self.assertIn("sports: Local team wins championship", result)

    @patch('agentmap.agents.get_agent_class')
    def test_llm_summarization(self, mock_get_agent_class):
        """Test LLM-based summarization."""
        # Setup mock LLM agent
        mock_llm_agent = MagicMock()
        mock_llm_agent.process.return_value = "A sunny day with breaking financial news and local sports victory."
        
        mock_llm_class = MagicMock()
        mock_llm_class.return_value = mock_llm_agent
        mock_get_agent_class.return_value = mock_llm_class
        
        agent = SummaryAgent("test_agent", "Create a brief summary", {"llm": "openai"})
        
        # Mock _basic_concatenation to return a known value
        agent._basic_concatenation = MagicMock(return_value="weather: Sunny\nnews: Breaking news\nsports: Championship")
        
        result = agent._summarize_with_llm(self.sample_inputs)
        
        # Should return LLM output
        self.assertEqual(result, "A sunny day with breaking financial news and local sports victory.")
        
        # Verify LLM was called with correct parameters
        mock_get_agent_class.assert_called_once_with("openai")
        mock_llm_class.assert_called_once()
        mock_llm_agent.process.assert_called_once()

    @patch('agentmap.agents.get_agent_class', return_value=None)
    def test_llm_not_found(self, mock_get_agent_class):
        """Test LLM summarization when LLM type is not found."""
        agent = SummaryAgent("test_agent", "Create a brief summary", {"llm": "nonexistent_llm"})
        
        result = agent._summarize_with_llm(self.sample_inputs)
        
        # Should contain error message and original content
        self.assertIn("ERROR", result)
        self.assertIn("Unsupported LLM type", result)
        self.assertIn("Original content", result)

    @patch('agentmap.agents.builtins.summary_agent.SummaryAgent._summarize_with_llm')
    @patch('agentmap.agents.builtins.summary_agent.SummaryAgent._basic_concatenation')
    def test_process_basic_mode(self, mock_basic_concatenation, mock_summarize_with_llm):
        """Test process method in basic concatenation mode."""
        mock_basic_concatenation.return_value = "Concatenated output"
        
        agent = SummaryAgent("test_agent", "Test prompt")  # Default is basic mode
        result = agent.process(self.sample_inputs)
        
        # Should use basic concatenation
        self.assertEqual(result, "Concatenated output")
        mock_basic_concatenation.assert_called_once_with(self.sample_inputs)
        mock_summarize_with_llm.assert_not_called()

    @patch('agentmap.agents.builtins.summary_agent.SummaryAgent._summarize_with_llm')
    @patch('agentmap.agents.builtins.summary_agent.SummaryAgent._basic_concatenation')
    def test_process_llm_mode(self, mock_basic_concatenation, mock_summarize_with_llm):
        """Test process method in LLM summarization mode."""
        mock_summarize_with_llm.return_value = "LLM summary"
        
        agent = SummaryAgent("test_agent", "Test prompt", {"llm": "openai"})  # LLM mode
        result = agent.process(self.sample_inputs)
        
        # Should use LLM summarization
        self.assertEqual(result, "LLM summary")
        mock_summarize_with_llm.assert_called_once_with(self.sample_inputs)
        mock_basic_concatenation.assert_not_called()

    def test_process_empty_inputs(self):
        """Test process method with empty inputs."""
        agent = SummaryAgent("test_agent", "Test prompt")
        result = agent.process({})
        
        # Should return empty string
        self.assertEqual(result, "")

    @patch('agentmap.agents.builtins.summary_agent.SummaryAgent._get_llm_prompt')
    def test_get_llm_prompt_with_format(self, mock_get_llm_prompt):
        """Test getting LLM prompt with format placeholder."""
        mock_get_llm_prompt.return_value = "Please summarize this: {content}"
        
        agent = SummaryAgent("test_agent", "Please summarize this: {content}")
        result = agent._get_llm_prompt("Sample content")
        
        # Should replace {content} with the provided content
        self.assertEqual(result, "Please summarize this: Sample content")

    def test_get_llm_prompt_no_format(self):
        """Test getting LLM prompt without format placeholder."""
        agent = SummaryAgent("test_agent", "Please summarize:")
        result = agent._get_llm_prompt("Sample content")
        
        # Should append content to prompt
        self.assertEqual(result, "Please summarize:\n\nSample content")

    def test_get_llm_prompt_no_prompt(self):
        """Test getting LLM prompt with no prompt defined."""
        agent = SummaryAgent("test_agent", "")
        result = agent._get_llm_prompt("Sample content")
        
        # Should use default format
        self.assertEqual(result, "Please summarize the following information:\n\nSample content")

if __name__ == '__main__':
    unittest.main()