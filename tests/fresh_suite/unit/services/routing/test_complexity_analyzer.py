"""
Unit tests for PromptComplexityAnalyzer.

These tests validate the complexity analysis system using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import re
import unittest

from agentmap.services.routing.complexity_analyzer import PromptComplexityAnalyzer
from agentmap.services.routing.types import (
    RoutingContext,
    TaskComplexity,
)
from tests.utils.mock_service_factory import MockServiceFactory


class TestPromptComplexityAnalyzer(unittest.TestCase):
    """Unit tests for PromptComplexityAnalyzer with mocked dependencies."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()

        # Create mock AppConfigService with routing config
        self.mock_app_config = MockServiceFactory.create_mock_app_config_service()

        # Mock routing configuration
        self.mock_routing_config = {
            "complexity_analysis": {
                "prompt_length_thresholds": {"low": 100, "medium": 300, "high": 800},
                "methods": {
                    "prompt_length": True,
                    "keyword_analysis": True,
                    "context_analysis": True,
                    "memory_analysis": True,
                    "structure_analysis": True,
                },
                "keyword_weights": {
                    "complexity_keywords": 0.4,
                    "task_specific_keywords": 0.3,
                    "prompt_structure": 0.3,
                },
                "context_analysis": {
                    "memory_size_threshold": 10,
                    "input_field_count_threshold": 5,
                },
            },
            "task_types": {
                "analysis": {
                    "default_complexity": "medium",
                    "complexity_keywords": {
                        "high": ["detailed", "comprehensive", "advanced"],
                        "critical": ["urgent", "critical", "emergency"],
                    },
                },
                "general": {"default_complexity": "medium", "complexity_keywords": {}},
            },
        }

        self.mock_app_config.get_routing_config.return_value = self.mock_routing_config

        # Initialize PromptComplexityAnalyzer with mocked dependencies
        self.analyzer = PromptComplexityAnalyzer(
            configuration=self.mock_app_config,
            logging_service=self.mock_logging_service,
        )

        # Get the mock logger for verification
        self.mock_logger = self.analyzer._logger

    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================

    def test_analyzer_initialization(self):
        """Test that analyzer initializes correctly with all dependencies."""
        # Verify configuration was loaded
        self.assertEqual(self.analyzer.config, self.mock_routing_config)
        self.assertEqual(
            self.analyzer.complexity_config,
            self.mock_routing_config["complexity_analysis"],
        )

        # Verify thresholds were loaded
        expected_thresholds = {"low": 100, "medium": 300, "high": 800}
        self.assertEqual(self.analyzer.length_thresholds, expected_thresholds)

        # Verify analysis methods were loaded
        expected_methods = {
            "prompt_length": True,
            "keyword_analysis": True,
            "context_analysis": True,
            "memory_analysis": True,
            "structure_analysis": True,
        }
        self.assertEqual(self.analyzer.analysis_methods, expected_methods)

        # Verify regex patterns were compiled
        self.assertIsInstance(self.analyzer.patterns["questions"], type(re.compile("")))
        self.assertIsInstance(self.analyzer.patterns["commands"], type(re.compile("")))

    def test_configuration_loading_methods(self):
        """Test individual configuration loading methods."""
        # Test length thresholds loading
        thresholds = self.analyzer._load_length_thresholds()
        self.assertEqual(thresholds["low"], 100)
        self.assertEqual(thresholds["medium"], 300)
        self.assertEqual(thresholds["high"], 800)

        # Test analysis methods loading
        methods = self.analyzer._load_analysis_methods()
        self.assertTrue(methods["prompt_length"])
        self.assertTrue(methods["keyword_analysis"])

        # Test keyword weights loading
        weights = self.analyzer._load_keyword_weights()
        self.assertEqual(weights["complexity_keywords"], 0.4)
        self.assertEqual(weights["task_specific_keywords"], 0.3)

        # Test context thresholds loading
        context_thresholds = self.analyzer._load_context_thresholds()
        self.assertEqual(context_thresholds["memory_size_threshold"], 10)
        self.assertEqual(context_thresholds["input_field_count_threshold"], 5)

    # =============================================================================
    # 2. Prompt Length Analysis Tests
    # =============================================================================

    def test_analyze_prompt_length_low_complexity(self):
        """Test prompt length analysis for low complexity."""
        short_prompt = "Short question?"  # 15 chars, < 100

        signal = self.analyzer._analyze_prompt_length(short_prompt)

        self.assertEqual(signal.complexity, TaskComplexity.LOW)
        self.assertEqual(signal.source, "prompt_length")
        self.assertGreaterEqual(signal.confidence, 0.7)
        self.assertIn("Short prompt", signal.reasoning)

    def test_analyze_prompt_length_medium_complexity(self):
        """Test prompt length analysis for medium complexity."""
        medium_prompt = (
            "This is a medium length prompt that should trigger medium complexity analysis. "
            * 3
        )  # ~240 chars

        signal = self.analyzer._analyze_prompt_length(medium_prompt)

        self.assertEqual(signal.complexity, TaskComplexity.MEDIUM)
        self.assertEqual(signal.source, "prompt_length")
        self.assertGreaterEqual(signal.confidence, 0.6)
        self.assertIn("Medium-length prompt", signal.reasoning)

    def test_analyze_prompt_length_high_complexity(self):
        """Test prompt length analysis for high complexity."""
        long_prompt = (
            "This is a very long prompt that should trigger high complexity analysis. "
            * 8
        )  # ~584 chars

        signal = self.analyzer._analyze_prompt_length(long_prompt)

        self.assertEqual(signal.complexity, TaskComplexity.HIGH)
        self.assertEqual(signal.source, "prompt_length")
        self.assertGreaterEqual(signal.confidence, 0.7)
        self.assertIn("Long prompt", signal.reasoning)

    def test_analyze_prompt_length_critical_complexity(self):
        """Test prompt length analysis for critical complexity."""
        very_long_prompt = (
            "This is an extremely long prompt that should trigger critical complexity analysis. "
            * 20
        )  # ~1700 chars

        signal = self.analyzer._analyze_prompt_length(very_long_prompt)

        self.assertEqual(signal.complexity, TaskComplexity.CRITICAL)
        self.assertEqual(signal.source, "prompt_length")
        self.assertGreaterEqual(signal.confidence, 0.8)
        self.assertIn("Very long prompt", signal.reasoning)

    # =============================================================================
    # 3. Keyword Analysis Tests
    # =============================================================================

    def test_analyze_prompt_keywords_urgency_indicators(self):
        """Test keyword analysis for urgency indicators (critical complexity)."""
        urgent_prompt = (
            "This is an urgent critical emergency task that needs immediate attention"
        )

        signal = self.analyzer._analyze_prompt_keywords(urgent_prompt)

        self.assertEqual(signal.complexity, TaskComplexity.CRITICAL)
        self.assertEqual(signal.source, "keyword_analysis")
        self.assertGreater(signal.confidence, 0.3)
        self.assertIn("Keyword analysis", signal.reasoning)

    def test_analyze_prompt_keywords_complexity_indicators(self):
        """Test keyword analysis for complexity indicators (high complexity)."""
        complex_prompt = "Please provide a detailed comprehensive analysis of this complex advanced topic"

        signal = self.analyzer._analyze_prompt_keywords(complex_prompt)

        self.assertEqual(signal.complexity, TaskComplexity.HIGH)
        self.assertEqual(signal.source, "keyword_analysis")
        self.assertGreater(signal.confidence, 0.2)

    def test_analyze_prompt_keywords_technical_terms(self):
        """Test keyword analysis for technical terms (medium-high complexity)."""
        technical_prompt = (
            "Help me design an API that returns JSON data using HTTP algorithms"
        )

        signal = self.analyzer._analyze_prompt_keywords(technical_prompt)

        # Should detect technical terms and assign appropriate complexity
        self.assertIn(signal.complexity, [TaskComplexity.MEDIUM, TaskComplexity.HIGH])
        self.assertEqual(signal.source, "keyword_analysis")

    def test_analyze_prompt_keywords_creative_indicators(self):
        """Test keyword analysis for creative indicators."""
        creative_prompt = (
            "Write a creative innovative story with an artistic narrative style"
        )

        signal = self.analyzer._analyze_prompt_keywords(creative_prompt)

        # Should detect creative indicators
        self.assertIn(signal.complexity, [TaskComplexity.MEDIUM, TaskComplexity.HIGH])
        self.assertEqual(signal.source, "keyword_analysis")

    def test_analyze_prompt_keywords_no_indicators(self):
        """Test keyword analysis with no specific indicators."""
        simple_prompt = "Hello how are you today"

        signal = self.analyzer._analyze_prompt_keywords(simple_prompt)

        self.assertEqual(signal.complexity, TaskComplexity.MEDIUM)  # Default
        self.assertEqual(signal.confidence, 0.3)  # Low confidence
        self.assertIn("No specific complexity keywords", signal.reasoning)

    # =============================================================================
    # 4. Structure Analysis Tests
    # =============================================================================

    def test_analyze_prompt_structure_simple(self):
        """Test structure analysis for simple prompts."""
        simple_prompt = "What is AI?"

        signal = self.analyzer._analyze_prompt_structure(simple_prompt)

        self.assertEqual(signal.complexity, TaskComplexity.LOW)
        self.assertEqual(signal.source, "structure_analysis")
        self.assertIn("simple structure", signal.reasoning)

    def test_analyze_prompt_structure_complex(self):
        """Test structure analysis for complex structured prompts."""
        # Create a prompt with clear structural complexity
        complex_prompt = """
        Please analyze the following comprehensive data set carefully.

        First, examine these key components:
        1. Data quality assessment
        2. Statistical analysis requirements
        3. Visualization needs
        4. Reporting standards

        Then address these critical questions:
        - What are the primary data sources?
        - How should we validate the results?
        - Which metrics are most important?
        - When should we complete this analysis?
        - Where should we focus our efforts?

        Finally, create a detailed implementation plan.
        Include specific timelines and deliverables.
        Address potential risks and mitigation strategies.
        """

        signal = self.analyzer._analyze_prompt_structure(complex_prompt)

        # Test that structure analysis recognizes complexity indicators
        self.assertEqual(signal.source, "structure_analysis")
        self.assertIn(signal.complexity, [TaskComplexity.MEDIUM, TaskComplexity.HIGH])

        # Should detect multiple structural elements
        reasoning_lower = signal.reasoning.lower()
        # Should mention at least some structural elements (questions, sentences, lists, or paragraphs)
        has_structure_indicators = any(
            indicator in reasoning_lower
            for indicator in ["question", "sentence", "list", "paragraph"]
        )
        self.assertTrue(
            has_structure_indicators,
            f"Expected structure indicators in reasoning: {signal.reasoning}",
        )

    def test_analyze_prompt_structure_medium(self):
        """Test structure analysis for medium complexity structure."""
        medium_prompt = """
        Please explain this concept. What are the key points?
        How does it work in practice?
        """

        signal = self.analyzer._analyze_prompt_structure(medium_prompt)

        self.assertIn(signal.complexity, [TaskComplexity.LOW, TaskComplexity.MEDIUM])
        self.assertEqual(signal.source, "structure_analysis")

    # =============================================================================
    # 5. Context Analysis Tests
    # =============================================================================

    def test_analyze_context_complexity_high_input_count(self):
        """Test context analysis with high input field count."""
        context = {
            "input_field_count": 8,  # > threshold of 5
            "data_field_1": "value1",
            "data_field_2": "value2",
            "data_field_3": "value3",
        }

        complexity = self.analyzer.analyze_context_complexity(context)

        self.assertEqual(complexity, TaskComplexity.HIGH)

    def test_analyze_context_complexity_medium_input_count(self):
        """Test context analysis with medium input field count."""
        context = {
            "input_field_count": 3,  # Between 2 and 5
            "data_field_1": "value1",
            "data_field_2": "value2",
        }

        complexity = self.analyzer.analyze_context_complexity(context)

        self.assertEqual(complexity, TaskComplexity.MEDIUM)

    def test_analyze_context_complexity_large_data(self):
        """Test context analysis with large context data."""
        large_data = "x" * 1500  # > 1000 chars
        context = {"input_field_count": 2, "large_field": large_data}

        complexity = self.analyzer.analyze_context_complexity(context)

        self.assertEqual(complexity, TaskComplexity.HIGH)

    def test_analyze_context_complexity_disabled(self):
        """Test context analysis when disabled."""
        # Disable context analysis
        self.analyzer.analysis_methods["context_analysis"] = False

        context = {"input_field_count": 10}
        complexity = self.analyzer.analyze_context_complexity(context)

        self.assertEqual(complexity, TaskComplexity.MEDIUM)  # Default

    # =============================================================================
    # 6. Memory Analysis Tests
    # =============================================================================

    def test_analyze_memory_complexity_large_memory(self):
        """Test memory analysis with large conversation history."""
        memory_size = 15  # > threshold of 10
        memory_content = [
            {"content": "Message 1"},
            {"content": "Message 2"},
            {"content": "Long message content " * 50},  # Large content
        ]

        complexity = self.analyzer.analyze_memory_complexity(
            memory_size, memory_content
        )

        self.assertEqual(complexity, TaskComplexity.HIGH)

    def test_analyze_memory_complexity_medium_memory(self):
        """Test memory analysis with medium conversation history."""
        memory_size = 7  # Between 5 and 10
        memory_content = [{"content": "Message 1"}, {"content": "Message 2"}]

        complexity = self.analyzer.analyze_memory_complexity(
            memory_size, memory_content
        )

        self.assertEqual(complexity, TaskComplexity.MEDIUM)

    def test_analyze_memory_complexity_no_memory(self):
        """Test memory analysis with no conversation history."""
        memory_size = 0
        memory_content = []

        complexity = self.analyzer.analyze_memory_complexity(
            memory_size, memory_content
        )

        self.assertEqual(complexity, TaskComplexity.LOW)

    def test_analyze_memory_complexity_disabled(self):
        """Test memory analysis when disabled."""
        # Disable memory analysis
        self.analyzer.analysis_methods["memory_analysis"] = False

        memory_size = 20
        memory_content = []
        complexity = self.analyzer.analyze_memory_complexity(
            memory_size, memory_content
        )

        self.assertEqual(complexity, TaskComplexity.LOW)  # Default when disabled

    # =============================================================================
    # 7. Task Type Analysis Tests
    # =============================================================================

    def test_analyze_task_type_complexity_with_keywords(self):
        """Test task type analysis with complexity keywords."""
        task_type = "analysis"
        prompt = "Please provide a detailed comprehensive analysis"

        signal = self.analyzer.analyze_task_type_complexity(task_type, prompt)

        self.assertEqual(signal.complexity, TaskComplexity.HIGH)  # Keywords detected
        self.assertEqual(signal.source, "task_type_analysis")
        self.assertGreater(signal.confidence, 0.5)
        self.assertIn("analysis", signal.reasoning)

    def test_analyze_task_type_complexity_critical_keywords(self):
        """Test task type analysis with critical keywords."""
        task_type = "analysis"
        prompt = "This is an urgent critical emergency analysis task"

        signal = self.analyzer.analyze_task_type_complexity(task_type, prompt)

        self.assertEqual(signal.complexity, TaskComplexity.CRITICAL)
        self.assertGreater(signal.confidence, 0.5)

    def test_analyze_task_type_complexity_default(self):
        """Test task type analysis with default complexity."""
        task_type = "general"
        prompt = "Simple question"

        signal = self.analyzer.analyze_task_type_complexity(task_type, prompt)

        self.assertEqual(signal.complexity, TaskComplexity.MEDIUM)  # Default
        self.assertEqual(signal.confidence, 0.4)
        self.assertIn("Default complexity", signal.reasoning)

    def test_analyze_task_type_complexity_unknown_task(self):
        """Test task type analysis with unknown task type."""
        task_type = "unknown_task"
        prompt = "Test prompt"

        signal = self.analyzer.analyze_task_type_complexity(task_type, prompt)

        self.assertEqual(signal.complexity, TaskComplexity.MEDIUM)  # Default fallback
        self.assertEqual(signal.confidence, 0.4)

    # =============================================================================
    # 8. Signal Combination Tests
    # =============================================================================

    def test_combine_complexity_signals_single_signal(self):
        """Test combining a single complexity signal."""
        signals = [TaskComplexity.HIGH]

        result = self.analyzer.combine_complexity_signals(signals)

        self.assertEqual(result, TaskComplexity.HIGH)

    def test_combine_complexity_signals_majority_vote(self):
        """Test combining multiple signals with clear majority."""
        signals = [TaskComplexity.HIGH, TaskComplexity.HIGH, TaskComplexity.MEDIUM]

        result = self.analyzer.combine_complexity_signals(signals)

        # Should lean towards higher complexity
        self.assertIn(result, [TaskComplexity.MEDIUM, TaskComplexity.HIGH])

    def test_combine_complexity_signals_weighted_average(self):
        """Test combining signals using weighted average."""
        signals = [TaskComplexity.LOW, TaskComplexity.CRITICAL]

        result = self.analyzer.combine_complexity_signals(signals)

        # Should be somewhere in the middle
        self.assertIn(result, [TaskComplexity.MEDIUM, TaskComplexity.HIGH])

    def test_combine_complexity_signals_empty_list(self):
        """Test combining empty signal list."""
        signals = []

        result = self.analyzer.combine_complexity_signals(signals)

        self.assertEqual(result, TaskComplexity.MEDIUM)  # Default

    # =============================================================================
    # 9. Overall Complexity Determination Tests
    # =============================================================================

    def test_determine_overall_complexity_with_override(self):
        """Test overall complexity determination with override."""
        prompt = "Simple prompt"
        task_type = "general"
        routing_context = RoutingContext(complexity_override="critical")

        result = self.analyzer.determine_overall_complexity(
            prompt, task_type, routing_context
        )

        self.assertEqual(result, TaskComplexity.CRITICAL)

    def test_determine_overall_complexity_invalid_override(self):
        """Test overall complexity determination with invalid override."""
        prompt = "Simple prompt"
        task_type = "general"
        routing_context = RoutingContext(complexity_override="invalid_level")

        # Should fall back to analysis when override is invalid
        result = self.analyzer.determine_overall_complexity(
            prompt, task_type, routing_context
        )

        # Should still return a valid complexity
        self.assertIsInstance(result, TaskComplexity)

    def test_determine_overall_complexity_auto_detect_disabled(self):
        """Test overall complexity determination with auto-detect disabled."""
        prompt = "Complex analytical task requiring detailed analysis"
        task_type = "analysis"
        routing_context = RoutingContext(auto_detect_complexity=False)

        result = self.analyzer.determine_overall_complexity(
            prompt, task_type, routing_context
        )

        # Should use task type default
        self.assertEqual(result, TaskComplexity.MEDIUM)  # Default for analysis

    def test_determine_overall_complexity_full_analysis(self):
        """Test overall complexity determination with full analysis."""
        prompt = "Please provide a comprehensive detailed analysis of this complex technical system"
        task_type = "analysis"
        routing_context = RoutingContext(
            auto_detect_complexity=True,
            input_context={"input_field_count": 3},
            memory_size=8,
        )

        result = self.analyzer.determine_overall_complexity(
            prompt, task_type, routing_context
        )

        # Should combine multiple analysis signals
        self.assertIsInstance(result, TaskComplexity)
        # Likely to be HIGH due to multiple complexity indicators
        self.assertIn(
            result,
            [TaskComplexity.MEDIUM, TaskComplexity.HIGH, TaskComplexity.CRITICAL],
        )

    def test_determine_overall_complexity_simple_prompt(self):
        """Test overall complexity determination with simple prompt."""
        prompt = "Hi"
        task_type = "general"
        routing_context = RoutingContext(auto_detect_complexity=True, memory_size=0)

        result = self.analyzer.determine_overall_complexity(
            prompt, task_type, routing_context
        )

        # Should be low complexity
        self.assertIn(result, [TaskComplexity.LOW, TaskComplexity.MEDIUM])

    # =============================================================================
    # 10. Integration and Full Analysis Tests
    # =============================================================================

    def test_analyze_prompt_complexity_all_methods_enabled(self):
        """Test full prompt complexity analysis with all methods enabled."""
        prompt = "Please analyze this complex technical problem in detail with comprehensive documentation"

        result = self.analyzer.analyze_prompt_complexity(prompt)

        # Should perform length, keyword, and structure analysis
        self.assertIsInstance(result, TaskComplexity)
        # Likely to be higher complexity due to keywords and length
        self.assertIn(result, [TaskComplexity.MEDIUM, TaskComplexity.HIGH])

    def test_analyze_prompt_complexity_methods_disabled(self):
        """Test prompt complexity analysis with methods disabled."""
        # Disable prompt length analysis
        self.analyzer.analysis_methods["prompt_length"] = False

        prompt = "x" * 1000  # Very long prompt

        result = self.analyzer.analyze_prompt_complexity(prompt)

        # Should still return valid complexity without length analysis
        self.assertIsInstance(result, TaskComplexity)

    def test_analyze_prompt_complexity_empty_prompt(self):
        """Test prompt complexity analysis with empty prompt."""
        prompt = ""

        result = self.analyzer.analyze_prompt_complexity(prompt)

        self.assertEqual(result, TaskComplexity.MEDIUM)  # Default for empty

    # =============================================================================
    # 11. Pattern Matching Tests
    # =============================================================================

    def test_pattern_matching_questions(self):
        """Test regex pattern matching for questions."""
        question_prompt = "What is this? How does it work? Why is that important?"

        questions = self.analyzer.patterns["questions"].findall(question_prompt)

        # Should find question indicators
        self.assertGreater(len(questions), 0)

    def test_pattern_matching_commands(self):
        """Test regex pattern matching for commands."""
        command_prompt = (
            "Analyze this data, create a report, and generate recommendations"
        )

        commands = self.analyzer.patterns["commands"].findall(command_prompt)

        # Should find command indicators
        self.assertGreater(len(commands), 0)

    def test_pattern_matching_technical_terms(self):
        """Test regex pattern matching for technical terms."""
        technical_prompt = "Use the REST API to fetch JSON data and run the algorithm"

        technical = self.analyzer.patterns["technical_terms"].findall(technical_prompt)

        # Should find technical terms
        self.assertGreater(len(technical), 0)

    def test_pattern_matching_complexity_indicators(self):
        """Test regex pattern matching for complexity indicators."""
        complex_prompt = (
            "Provide a comprehensive and detailed analysis of this complex system"
        )

        complexity = self.analyzer.patterns["complexity_indicators"].findall(
            complex_prompt
        )

        # Should find complexity indicators
        self.assertGreater(len(complexity), 0)


if __name__ == "__main__":
    unittest.main()
