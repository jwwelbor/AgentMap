"""
Unit tests for routing types and utilities.

These tests validate the core routing types, enums, and utility functions
following the established testing patterns for comprehensive coverage.
"""

import unittest

from agentmap.services.routing.types import (
    ComplexitySignal,
    RoutingContext,
    RoutingDecision,
    TaskComplexity,
    TaskType,
    get_complexity_order,
    get_valid_complexity_levels,
    get_valid_task_types,
    normalize_complexity,
    normalize_task_type,
)


class TestTaskComplexity(unittest.TestCase):
    """Unit tests for TaskComplexity enum."""

    def test_task_complexity_values(self):
        """Test TaskComplexity enum values and ordering."""
        # Test enum values
        self.assertEqual(TaskComplexity.LOW.value, 1)
        self.assertEqual(TaskComplexity.MEDIUM.value, 2)
        self.assertEqual(TaskComplexity.HIGH.value, 3)
        self.assertEqual(TaskComplexity.CRITICAL.value, 4)

        # Test ordering by comparing values
        self.assertLess(TaskComplexity.LOW.value, TaskComplexity.MEDIUM.value)
        self.assertLess(TaskComplexity.MEDIUM.value, TaskComplexity.HIGH.value)
        self.assertLess(TaskComplexity.HIGH.value, TaskComplexity.CRITICAL.value)

    def test_task_complexity_string_representation(self):
        """Test TaskComplexity string representation."""
        self.assertEqual(str(TaskComplexity.LOW), "low")
        self.assertEqual(str(TaskComplexity.MEDIUM), "medium")
        self.assertEqual(str(TaskComplexity.HIGH), "high")
        self.assertEqual(str(TaskComplexity.CRITICAL), "critical")

    def test_task_complexity_from_string_valid(self):
        """Test TaskComplexity.from_string() with valid inputs."""
        # Test lowercase
        self.assertEqual(TaskComplexity.from_string("low"), TaskComplexity.LOW)
        self.assertEqual(TaskComplexity.from_string("medium"), TaskComplexity.MEDIUM)
        self.assertEqual(TaskComplexity.from_string("high"), TaskComplexity.HIGH)
        self.assertEqual(
            TaskComplexity.from_string("critical"), TaskComplexity.CRITICAL
        )

        # Test uppercase
        self.assertEqual(TaskComplexity.from_string("LOW"), TaskComplexity.LOW)
        self.assertEqual(TaskComplexity.from_string("MEDIUM"), TaskComplexity.MEDIUM)

        # Test mixed case
        self.assertEqual(TaskComplexity.from_string("High"), TaskComplexity.HIGH)
        self.assertEqual(
            TaskComplexity.from_string("Critical"), TaskComplexity.CRITICAL
        )

    def test_task_complexity_from_string_invalid(self):
        """Test TaskComplexity.from_string() with invalid inputs."""
        with self.assertRaises(ValueError) as context:
            TaskComplexity.from_string("invalid")

        self.assertIn("Invalid complexity level: invalid", str(context.exception))

        with self.assertRaises(ValueError):
            TaskComplexity.from_string("")

        with self.assertRaises(ValueError):
            TaskComplexity.from_string("extreme")


class TestTaskType(unittest.TestCase):
    """Unit tests for TaskType enum."""

    def test_task_type_values(self):
        """Test TaskType enum values."""
        self.assertEqual(TaskType.GENERAL.value, "general")
        self.assertEqual(TaskType.ANALYSIS.value, "analysis")
        self.assertEqual(TaskType.CREATIVE.value, "creative")
        self.assertEqual(TaskType.DIALOGUE.value, "dialogue")
        self.assertEqual(TaskType.TECHNICAL.value, "technical")
        self.assertEqual(TaskType.CUSTOMER_SERVICE.value, "customer_service")
        self.assertEqual(TaskType.DATA_ANALYSIS.value, "data_analysis")
        self.assertEqual(TaskType.CREATIVE_WRITING.value, "creative_writing")
        self.assertEqual(TaskType.CODE_ANALYSIS.value, "code_analysis")

    def test_task_type_string_representation(self):
        """Test TaskType string representation."""
        self.assertEqual(str(TaskType.GENERAL), "general")
        self.assertEqual(str(TaskType.ANALYSIS), "analysis")
        self.assertEqual(str(TaskType.CREATIVE_WRITING), "creative_writing")

    def test_task_type_from_string_valid(self):
        """Test TaskType.from_string() with valid inputs."""
        # Test exact matches
        self.assertEqual(TaskType.from_string("general"), TaskType.GENERAL)
        self.assertEqual(TaskType.from_string("analysis"), TaskType.ANALYSIS)
        self.assertEqual(
            TaskType.from_string("creative_writing"), TaskType.CREATIVE_WRITING
        )

        # Test case insensitive
        self.assertEqual(TaskType.from_string("GENERAL"), TaskType.GENERAL)
        self.assertEqual(TaskType.from_string("Analysis"), TaskType.ANALYSIS)
        self.assertEqual(
            TaskType.from_string("Creative_Writing"), TaskType.CREATIVE_WRITING
        )

    def test_task_type_from_string_invalid(self):
        """Test TaskType.from_string() with invalid inputs."""
        with self.assertRaises(ValueError) as context:
            TaskType.from_string("invalid_task")

        self.assertIn("Invalid task type: invalid_task", str(context.exception))


class TestRoutingContext(unittest.TestCase):
    """Unit tests for RoutingContext dataclass."""

    def test_routing_context_default_values(self):
        """Test RoutingContext default values."""
        context = RoutingContext()

        # Test default values
        self.assertEqual(context.task_type, "general")
        self.assertFalse(context.routing_enabled)
        self.assertIsNone(context.complexity_override)
        self.assertTrue(context.auto_detect_complexity)
        self.assertEqual(context.provider_preference, [])
        self.assertEqual(context.excluded_providers, [])
        self.assertIsNone(context.model_override)
        self.assertIsNone(context.max_cost_tier)
        self.assertEqual(context.prompt, "")
        self.assertEqual(context.input_context, {})
        self.assertEqual(context.memory_size, 0)
        self.assertEqual(context.input_field_count, 0)
        self.assertTrue(context.cost_optimization)
        self.assertFalse(context.prefer_speed)
        self.assertFalse(context.prefer_quality)
        self.assertIsNone(context.fallback_provider)
        self.assertIsNone(context.fallback_model)
        self.assertTrue(context.retry_with_lower_complexity)

    def test_routing_context_custom_values(self):
        """Test RoutingContext with custom values."""
        context = RoutingContext(
            task_type="analysis",
            routing_enabled=True,
            complexity_override="high",
            auto_detect_complexity=False,
            provider_preference=["anthropic", "openai"],
            excluded_providers=["google"],
            model_override="gpt-4",
            max_cost_tier="medium",
            prompt="Analyze this data",
            input_context={"field1": "value1"},
            memory_size=5,
            input_field_count=3,
            cost_optimization=False,
            prefer_speed=True,
            prefer_quality=False,
            fallback_provider="openai",
            fallback_model="gpt-4o-mini",
            retry_with_lower_complexity=False,
        )

        # Verify all custom values
        self.assertEqual(context.task_type, "analysis")
        self.assertTrue(context.routing_enabled)
        self.assertEqual(context.complexity_override, "high")
        self.assertFalse(context.auto_detect_complexity)
        self.assertEqual(context.provider_preference, ["anthropic", "openai"])
        self.assertEqual(context.excluded_providers, ["google"])
        self.assertEqual(context.model_override, "gpt-4")
        self.assertEqual(context.max_cost_tier, "medium")
        self.assertEqual(context.prompt, "Analyze this data")
        self.assertEqual(context.input_context, {"field1": "value1"})
        self.assertEqual(context.memory_size, 5)
        self.assertEqual(context.input_field_count, 3)
        self.assertFalse(context.cost_optimization)
        self.assertTrue(context.prefer_speed)
        self.assertFalse(context.prefer_quality)
        self.assertEqual(context.fallback_provider, "openai")
        self.assertEqual(context.fallback_model, "gpt-4o-mini")
        self.assertFalse(context.retry_with_lower_complexity)

    def test_routing_context_to_dict(self):
        """Test RoutingContext.to_dict() method."""
        context = RoutingContext(
            task_type="coding", routing_enabled=True, provider_preference=["openai"]
        )

        result = context.to_dict()

        # Verify dictionary contains all fields
        self.assertIsInstance(result, dict)
        self.assertEqual(result["task_type"], "coding")
        self.assertTrue(result["routing_enabled"])
        self.assertEqual(result["provider_preference"], ["openai"])

        # Verify all fields are present
        expected_keys = {
            "task_type",
            "routing_enabled",
            "activity",
            "complexity_override",
            "auto_detect_complexity",
            "provider_preference",
            "excluded_providers",
            "model_override",
            "max_cost_tier",
            "prompt",
            "input_context",
            "memory_size",
            "input_field_count",
            "cost_optimization",
            "prefer_speed",
            "prefer_quality",
            "fallback_provider",
            "fallback_model",
            "retry_with_lower_complexity",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_routing_context_from_dict(self):
        """Test RoutingContext.from_dict() method."""
        data = {
            "task_type": "technical",
            "routing_enabled": True,
            "complexity_override": "critical",
            "provider_preference": ["anthropic", "openai"],
            "max_cost_tier": "high",
            "cost_optimization": False,
        }

        context = RoutingContext.from_dict(data)

        # Verify fields from dict
        self.assertEqual(context.task_type, "technical")
        self.assertTrue(context.routing_enabled)
        self.assertEqual(context.complexity_override, "critical")
        self.assertEqual(context.provider_preference, ["anthropic", "openai"])
        self.assertEqual(context.max_cost_tier, "high")
        self.assertFalse(context.cost_optimization)

        # Verify defaults for missing fields
        self.assertTrue(context.auto_detect_complexity)  # Default
        self.assertEqual(context.excluded_providers, [])  # Default

    def test_routing_context_roundtrip_serialization(self):
        """Test RoutingContext roundtrip serialization."""
        original = RoutingContext(
            task_type="data_analysis",
            routing_enabled=True,
            complexity_override="high",
            provider_preference=["anthropic"],
            input_context={"key": "value"},
            memory_size=10,
        )

        # Convert to dict and back
        data = original.to_dict()
        reconstructed = RoutingContext.from_dict(data)

        # Should be equivalent
        self.assertEqual(original.task_type, reconstructed.task_type)
        self.assertEqual(original.routing_enabled, reconstructed.routing_enabled)
        self.assertEqual(
            original.complexity_override, reconstructed.complexity_override
        )
        self.assertEqual(
            original.provider_preference, reconstructed.provider_preference
        )
        self.assertEqual(original.input_context, reconstructed.input_context)
        self.assertEqual(original.memory_size, reconstructed.memory_size)


class TestRoutingDecision(unittest.TestCase):
    """Unit tests for RoutingDecision dataclass."""

    def test_routing_decision_creation(self):
        """Test RoutingDecision creation with required fields."""
        decision = RoutingDecision(
            provider="anthropic",
            model="claude-opus-4-6",
            complexity=TaskComplexity.HIGH,
        )

        # Verify required fields
        self.assertEqual(decision.provider, "anthropic")
        self.assertEqual(decision.model, "claude-opus-4-6")
        self.assertEqual(decision.complexity, TaskComplexity.HIGH)

        # Verify default values
        self.assertEqual(decision.confidence, 1.0)
        self.assertEqual(decision.reasoning, "")
        self.assertFalse(decision.fallback_used)
        self.assertFalse(decision.cache_hit)

    def test_routing_decision_with_all_fields(self):
        """Test RoutingDecision with all fields specified."""
        decision = RoutingDecision(
            provider="openai",
            model="gpt-4",
            complexity=TaskComplexity.CRITICAL,
            confidence=0.85,
            reasoning="Selected for critical analysis task",
            fallback_used=True,
            cache_hit=False,
        )

        # Verify all fields
        self.assertEqual(decision.provider, "openai")
        self.assertEqual(decision.model, "gpt-4")
        self.assertEqual(decision.complexity, TaskComplexity.CRITICAL)
        self.assertEqual(decision.confidence, 0.85)
        self.assertEqual(decision.reasoning, "Selected for critical analysis task")
        self.assertTrue(decision.fallback_used)
        self.assertFalse(decision.cache_hit)

    def test_routing_decision_to_dict(self):
        """Test RoutingDecision.to_dict() method."""
        decision = RoutingDecision(
            provider="google",
            model="gemini-pro",
            complexity=TaskComplexity.MEDIUM,
            confidence=0.9,
            reasoning="Good for medium complexity",
            fallback_used=False,
            cache_hit=True,
        )

        result = decision.to_dict()

        expected = {
            "provider": "google",
            "model": "gemini-pro",
            "complexity": "medium",
            "confidence": 0.9,
            "reasoning": "Good for medium complexity",
            "fallback_used": False,
            "cache_hit": True,
        }

        self.assertEqual(result, expected)

    def test_routing_decision_complexity_string_conversion(self):
        """Test that complexity is converted to string in to_dict()."""
        decision = RoutingDecision(
            provider="test", model="test", complexity=TaskComplexity.LOW
        )

        result = decision.to_dict()

        # Complexity should be string, not enum
        self.assertEqual(result["complexity"], "low")
        self.assertIsInstance(result["complexity"], str)


class TestComplexitySignal(unittest.TestCase):
    """Unit tests for ComplexitySignal dataclass."""

    def test_complexity_signal_creation(self):
        """Test ComplexitySignal creation with valid values."""
        signal = ComplexitySignal(
            complexity=TaskComplexity.HIGH,
            confidence=0.8,
            reasoning="High complexity detected",
            source="keyword_analysis",
        )

        self.assertEqual(signal.complexity, TaskComplexity.HIGH)
        self.assertEqual(signal.confidence, 0.8)
        self.assertEqual(signal.reasoning, "High complexity detected")
        self.assertEqual(signal.source, "keyword_analysis")

    def test_complexity_signal_confidence_validation(self):
        """Test ComplexitySignal confidence value validation."""
        # Valid confidence values
        signal1 = ComplexitySignal(
            complexity=TaskComplexity.LOW,
            confidence=0.0,
            reasoning="Test",
            source="test",
        )
        self.assertEqual(signal1.confidence, 0.0)

        signal2 = ComplexitySignal(
            complexity=TaskComplexity.LOW,
            confidence=1.0,
            reasoning="Test",
            source="test",
        )
        self.assertEqual(signal2.confidence, 1.0)

        signal3 = ComplexitySignal(
            complexity=TaskComplexity.LOW,
            confidence=0.5,
            reasoning="Test",
            source="test",
        )
        self.assertEqual(signal3.confidence, 0.5)

        # Invalid confidence values
        with self.assertRaises(ValueError) as context:
            ComplexitySignal(
                complexity=TaskComplexity.LOW,
                confidence=-0.1,
                reasoning="Test",
                source="test",
            )
        self.assertIn("Confidence must be between 0.0 and 1.0", str(context.exception))

        with self.assertRaises(ValueError) as context:
            ComplexitySignal(
                complexity=TaskComplexity.LOW,
                confidence=1.1,
                reasoning="Test",
                source="test",
            )
        self.assertIn("Confidence must be between 0.0 and 1.0", str(context.exception))


class TestUtilityFunctions(unittest.TestCase):
    """Unit tests for routing utility functions."""

    def test_normalize_task_type_valid(self):
        """Test normalize_task_type with valid inputs."""
        # Test exact matches
        self.assertEqual(normalize_task_type("general"), "general")
        self.assertEqual(normalize_task_type("analysis"), "analysis")
        self.assertEqual(normalize_task_type("creative_writing"), "creative_writing")

        # Test case conversion
        self.assertEqual(normalize_task_type("GENERAL"), "general")
        self.assertEqual(normalize_task_type("Analysis"), "analysis")

        # Test separator replacement
        self.assertEqual(normalize_task_type("creative-writing"), "creative_writing")
        self.assertEqual(normalize_task_type("data analysis"), "data_analysis")

        # Test aliases
        self.assertEqual(normalize_task_type("chat"), "dialogue")
        self.assertEqual(normalize_task_type("conversation"), "dialogue")
        self.assertEqual(normalize_task_type("coding"), "code_analysis")
        self.assertEqual(normalize_task_type("programming"), "code_analysis")
        self.assertEqual(normalize_task_type("writing"), "creative_writing")
        self.assertEqual(normalize_task_type("story"), "creative_writing")
        self.assertEqual(normalize_task_type("support"), "customer_service")
        self.assertEqual(normalize_task_type("help"), "customer_service")
        self.assertEqual(normalize_task_type("data"), "data_analysis")
        self.assertEqual(normalize_task_type("analytics"), "data_analysis")

    def test_normalize_task_type_edge_cases(self):
        """Test normalize_task_type with edge cases."""
        # Empty string
        self.assertEqual(normalize_task_type(""), "general")

        # None
        self.assertEqual(normalize_task_type(None), "general")

        # Unknown task type
        self.assertEqual(normalize_task_type("unknown_task"), "unknown_task")

        # Multiple separators
        self.assertEqual(normalize_task_type("custom-task name"), "custom_task_name")

    def test_normalize_complexity_valid(self):
        """Test normalize_complexity with valid inputs."""
        # Test exact matches
        self.assertEqual(normalize_complexity("low"), "low")
        self.assertEqual(normalize_complexity("medium"), "medium")
        self.assertEqual(normalize_complexity("high"), "high")
        self.assertEqual(normalize_complexity("critical"), "critical")

        # Test case conversion
        self.assertEqual(normalize_complexity("LOW"), "low")
        self.assertEqual(normalize_complexity("Medium"), "medium")
        self.assertEqual(normalize_complexity("HIGH"), "high")

        # Test aliases
        self.assertEqual(normalize_complexity("simple"), "low")
        self.assertEqual(normalize_complexity("basic"), "low")
        self.assertEqual(normalize_complexity("easy"), "low")
        self.assertEqual(normalize_complexity("standard"), "medium")
        self.assertEqual(normalize_complexity("normal"), "medium")
        self.assertEqual(normalize_complexity("moderate"), "medium")
        self.assertEqual(normalize_complexity("advanced"), "high")
        self.assertEqual(normalize_complexity("complex"), "high")
        self.assertEqual(normalize_complexity("difficult"), "high")
        self.assertEqual(normalize_complexity("urgent"), "critical")
        self.assertEqual(normalize_complexity("emergency"), "critical")
        self.assertEqual(normalize_complexity("important"), "critical")

    def test_normalize_complexity_edge_cases(self):
        """Test normalize_complexity with edge cases."""
        # Empty string
        self.assertEqual(normalize_complexity(""), "medium")

        # None
        self.assertEqual(normalize_complexity(None), "medium")

        # Unknown complexity
        self.assertEqual(normalize_complexity("unknown"), "unknown")

        # Whitespace
        self.assertEqual(normalize_complexity("  high  "), "high")

    def test_get_complexity_order(self):
        """Test get_complexity_order function."""
        order = get_complexity_order()

        # Should return list in correct order
        expected = [
            TaskComplexity.LOW,
            TaskComplexity.MEDIUM,
            TaskComplexity.HIGH,
            TaskComplexity.CRITICAL,
        ]
        self.assertEqual(order, expected)

        # Should be sorted by value
        values = [c.value for c in order]
        self.assertEqual(values, sorted(values))

    def test_get_valid_task_types(self):
        """Test get_valid_task_types function."""
        task_types = get_valid_task_types()

        # Should be a list of strings
        self.assertIsInstance(task_types, list)
        self.assertTrue(all(isinstance(t, str) for t in task_types))

        # Should contain expected task types
        expected_types = [
            "general",
            "analysis",
            "creative",
            "dialogue",
            "technical",
            "customer_service",
            "data_analysis",
            "creative_writing",
            "code_analysis",
        ]
        for expected in expected_types:
            self.assertIn(expected, task_types)

    def test_get_valid_complexity_levels(self):
        """Test get_valid_complexity_levels function."""
        complexity_levels = get_valid_complexity_levels()

        # Should be a list of strings
        self.assertIsInstance(complexity_levels, list)
        self.assertTrue(all(isinstance(c, str) for c in complexity_levels))

        # Should contain expected complexity levels
        expected_levels = ["low", "medium", "high", "critical"]
        self.assertEqual(complexity_levels, expected_levels)

    def test_utility_functions_consistency(self):
        """Test consistency between utility functions."""
        # All task types should normalize to themselves
        valid_task_types = get_valid_task_types()
        for task_type in valid_task_types:
            self.assertEqual(normalize_task_type(task_type), task_type)

        # All complexity levels should normalize to themselves
        valid_complexity_levels = get_valid_complexity_levels()
        for complexity in valid_complexity_levels:
            self.assertEqual(normalize_complexity(complexity), complexity)

        # Complexity order should match valid levels
        complexity_order = get_complexity_order()
        complexity_strings = [str(c) for c in complexity_order]
        self.assertEqual(complexity_strings, valid_complexity_levels)


class TestProtocolCompliance(unittest.TestCase):
    """Unit tests for protocol compliance and interface validation."""

    def test_complexity_analyzer_protocol_methods(self):
        """Test that ComplexityAnalyzer protocol methods are defined."""
        # Import the protocol
        from agentmap.services.routing.types import ComplexityAnalyzer

        # Check required methods exist
        required_methods = [
            "analyze_prompt_complexity",
            "analyze_context_complexity",
            "analyze_memory_complexity",
            "combine_complexity_signals",
        ]

        # Verify methods are defined in protocol
        for method_name in required_methods:
            self.assertTrue(hasattr(ComplexityAnalyzer, method_name))

    def test_llm_router_protocol_methods(self):
        """Test that LLMRouter protocol methods are defined."""
        # Import the protocol
        from agentmap.services.routing.types import LLMRouter

        # Check required methods exist
        required_methods = [
            "determine_complexity",
            "select_optimal_model",
            "route_request",
        ]

        # Verify methods are defined in protocol
        for method_name in required_methods:
            self.assertTrue(hasattr(LLMRouter, method_name))

    def test_routing_types_enum_completeness(self):
        """Test that routing type enums have all expected values."""
        # Test TaskComplexity completeness
        complexity_values = [e.value for e in TaskComplexity]
        expected_complexity = [1, 2, 3, 4]
        self.assertEqual(sorted(complexity_values), expected_complexity)

        # Test TaskType completeness
        task_type_values = [e.value for e in TaskType]
        self.assertGreaterEqual(len(task_type_values), 9)  # At least 9 task types
        self.assertIn("general", task_type_values)
        self.assertIn("analysis", task_type_values)
        self.assertIn("creative_writing", task_type_values)

    def test_dataclass_field_types(self):
        """Test that dataclass fields have correct types."""
        # Test RoutingContext field types
        context = RoutingContext()

        self.assertIsInstance(context.task_type, str)
        self.assertIsInstance(context.routing_enabled, bool)
        self.assertIsInstance(context.auto_detect_complexity, bool)
        self.assertIsInstance(context.provider_preference, list)
        self.assertIsInstance(context.excluded_providers, list)
        self.assertIsInstance(context.input_context, dict)
        self.assertIsInstance(context.memory_size, int)
        self.assertIsInstance(context.input_field_count, int)
        self.assertIsInstance(context.cost_optimization, bool)
        self.assertIsInstance(context.prefer_speed, bool)
        self.assertIsInstance(context.prefer_quality, bool)
        self.assertIsInstance(context.retry_with_lower_complexity, bool)

        # Test RoutingDecision field types
        decision = RoutingDecision(
            provider="test", model="test", complexity=TaskComplexity.LOW
        )

        self.assertIsInstance(decision.provider, str)
        self.assertIsInstance(decision.model, str)
        self.assertIsInstance(decision.complexity, TaskComplexity)
        self.assertIsInstance(decision.confidence, float)
        self.assertIsInstance(decision.reasoning, str)
        self.assertIsInstance(decision.fallback_used, bool)
        self.assertIsInstance(decision.cache_hit, bool)


if __name__ == "__main__":
    unittest.main()
