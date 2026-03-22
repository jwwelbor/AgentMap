"""
Integration tests for max_tokens support in the LLM routing pipeline.

Tests the end-to-end flow of max_tokens from activity config through
routing types, activity routing, routing service, and into the LLM service.
"""

import unittest
from unittest.mock import Mock, create_autospec

from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.config.llm_routing_validators import (
    validate_activities_config,
)
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.activity_routing import ActivityRoutingTable
from agentmap.services.routing.types import (
    RoutingContext,
    RoutingDecision,
    TaskComplexity,
)


class TestMaxTokensInRoutingTypes(unittest.TestCase):
    """Test max_tokens field on RoutingContext and RoutingDecision."""

    def test_routing_context_max_tokens_default(self):
        """max_tokens defaults to None on RoutingContext."""
        ctx = RoutingContext()
        self.assertIsNone(ctx.max_tokens)

    def test_routing_context_max_tokens_set(self):
        """max_tokens can be set on RoutingContext."""
        ctx = RoutingContext(max_tokens=4096)
        self.assertEqual(ctx.max_tokens, 4096)

    def test_routing_context_roundtrip(self):
        """max_tokens survives to_dict/from_dict roundtrip."""
        ctx = RoutingContext(max_tokens=2048)
        d = ctx.to_dict()
        self.assertEqual(d["max_tokens"], 2048)
        restored = RoutingContext.from_dict(d)
        self.assertEqual(restored.max_tokens, 2048)

    def test_routing_context_roundtrip_none(self):
        """None max_tokens survives roundtrip."""
        ctx = RoutingContext()
        d = ctx.to_dict()
        self.assertIsNone(d["max_tokens"])
        restored = RoutingContext.from_dict(d)
        self.assertIsNone(restored.max_tokens)

    def test_routing_context_roundtrip_zero(self):
        """Zero max_tokens survives roundtrip."""
        ctx = RoutingContext(max_tokens=0)
        d = ctx.to_dict()
        self.assertEqual(d["max_tokens"], 0)
        restored = RoutingContext.from_dict(d)
        self.assertEqual(restored.max_tokens, 0)

    def test_routing_decision_max_tokens_default(self):
        """max_tokens defaults to None on RoutingDecision."""
        decision = RoutingDecision(
            provider="anthropic", model="claude-3", complexity=TaskComplexity.MEDIUM
        )
        self.assertIsNone(decision.max_tokens)

    def test_routing_decision_max_tokens_set(self):
        """max_tokens can be set on RoutingDecision."""
        decision = RoutingDecision(
            provider="anthropic",
            model="claude-3",
            complexity=TaskComplexity.MEDIUM,
            max_tokens=4096,
        )
        self.assertEqual(decision.max_tokens, 4096)

    def test_routing_decision_to_dict_includes_max_tokens(self):
        """to_dict includes max_tokens."""
        decision = RoutingDecision(
            provider="anthropic",
            model="claude-3",
            complexity=TaskComplexity.MEDIUM,
            max_tokens=1000,
        )
        d = decision.to_dict()
        self.assertEqual(d["max_tokens"], 1000)


class TestMaxTokensInActivityRouting(unittest.TestCase):
    """Test max_tokens extraction in ActivityRoutingTable.plan()."""

    def _make_table(self, activities=None):
        mock_config = create_autospec(LLMRoutingConfigService, instance=True)
        mock_config.get_activities_config.return_value = activities or {}
        mock_logger = create_autospec(LoggingService, instance=True)
        mock_logger.get_class_logger.return_value = Mock()
        return ActivityRoutingTable(mock_config, mock_logger)

    def test_plan_extracts_tier_max_tokens(self):
        """plan() extracts tier-level max_tokens into candidate entries."""
        table = self._make_table(
            {
                "code_gen": {
                    "low": {
                        "max_tokens": 2048,
                        "primary": {"provider": "anthropic", "model": "haiku"},
                        "fallbacks": [{"provider": "openai", "model": "gpt-mini"}],
                    }
                }
            }
        )
        candidates = table.plan("code_gen", "low")
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["max_tokens"], 2048)
        self.assertEqual(candidates[1]["max_tokens"], 2048)

    def test_plan_candidate_max_tokens_overrides_tier(self):
        """Candidate-level max_tokens overrides tier-level; fallback inherits tier."""
        table = self._make_table(
            {
                "code_gen": {
                    "high": {
                        "max_tokens": 4096,
                        "primary": {
                            "provider": "anthropic",
                            "model": "sonnet",
                            "max_tokens": 8192,
                        },
                        "fallbacks": [{"provider": "openai", "model": "gpt"}],
                    }
                }
            }
        )
        candidates = table.plan("code_gen", "high")
        self.assertEqual(candidates[0]["max_tokens"], 8192)  # candidate override
        # Fallback inherits from tier (4096), not primary (8192)
        self.assertEqual(candidates[1]["max_tokens"], 4096)

    def test_plan_no_max_tokens_when_absent(self):
        """When max_tokens is absent, entries don't include the key."""
        table = self._make_table(
            {
                "research": {
                    "any": {
                        "primary": {"provider": "google", "model": "gemini"},
                        "fallbacks": [],
                    }
                }
            }
        )
        candidates = table.plan("research", "any")
        self.assertEqual(len(candidates), 1)
        self.assertNotIn("max_tokens", candidates[0])

    def test_plan_zero_max_tokens(self):
        """Zero max_tokens is passed through (means 'no limit')."""
        table = self._make_table(
            {
                "critical": {
                    "critical": {
                        "max_tokens": 0,
                        "primary": {"provider": "openai", "model": "o3"},
                        "fallbacks": [],
                    }
                }
            }
        )
        candidates = table.plan("critical", "critical")
        self.assertEqual(candidates[0]["max_tokens"], 0)

    def test_plan_candidate_zero_overrides_tier_nonzero(self):
        """Candidate max_tokens=0 overrides tier's nonzero value."""
        table = self._make_table(
            {
                "mixed": {
                    "low": {
                        "max_tokens": 1024,
                        "primary": {
                            "provider": "anthropic",
                            "model": "haiku",
                            "max_tokens": 0,
                        },
                        "fallbacks": [],
                    }
                }
            }
        )
        candidates = table.plan("mixed", "low")
        self.assertEqual(candidates[0]["max_tokens"], 0)


class TestMaxTokensValidation(unittest.TestCase):
    """Test max_tokens validation in activities config."""

    def test_valid_positive_integer(self):
        activities = {
            "a": {
                "low": {"max_tokens": 4096, "primary": {"provider": "x", "model": "y"}}
            }
        }
        errors = validate_activities_config(activities)
        self.assertEqual(errors, [])

    def test_valid_zero(self):
        activities = {
            "a": {"low": {"max_tokens": 0, "primary": {"provider": "x", "model": "y"}}}
        }
        errors = validate_activities_config(activities)
        self.assertEqual(errors, [])

    def test_valid_none(self):
        activities = {
            "a": {
                "low": {"max_tokens": None, "primary": {"provider": "x", "model": "y"}}
            }
        }
        errors = validate_activities_config(activities)
        self.assertEqual(errors, [])

    def test_valid_absent(self):
        activities = {"a": {"low": {"primary": {"provider": "x", "model": "y"}}}}
        errors = validate_activities_config(activities)
        self.assertEqual(errors, [])

    def test_invalid_negative(self):
        activities = {
            "a": {"low": {"max_tokens": -1, "primary": {"provider": "x", "model": "y"}}}
        }
        errors = validate_activities_config(activities)
        self.assertEqual(len(errors), 1)
        self.assertIn("non-negative", errors[0])

    def test_invalid_string(self):
        activities = {
            "a": {
                "low": {
                    "max_tokens": "4096",
                    "primary": {"provider": "x", "model": "y"},
                }
            }
        }
        errors = validate_activities_config(activities)
        self.assertEqual(len(errors), 1)
        self.assertIn("non-negative integer", errors[0])

    def test_invalid_float(self):
        activities = {
            "a": {
                "low": {
                    "max_tokens": 4096.5,
                    "primary": {"provider": "x", "model": "y"},
                }
            }
        }
        errors = validate_activities_config(activities)
        self.assertEqual(len(errors), 1)

    def test_invalid_bool(self):
        activities = {
            "a": {
                "low": {"max_tokens": True, "primary": {"provider": "x", "model": "y"}}
            }
        }
        errors = validate_activities_config(activities)
        self.assertEqual(len(errors), 1)

    def test_candidate_level_validation(self):
        activities = {
            "a": {
                "low": {
                    "primary": {"provider": "x", "model": "y", "max_tokens": -5},
                    "fallbacks": [{"provider": "z", "model": "w", "max_tokens": "bad"}],
                }
            }
        }
        errors = validate_activities_config(activities)
        self.assertEqual(len(errors), 2)

    def test_empty_activities(self):
        errors = validate_activities_config({})
        self.assertEqual(errors, [])

    def test_none_activities(self):
        errors = validate_activities_config(None)
        self.assertEqual(errors, [])


class TestMaxTokensBackwardCompatibility(unittest.TestCase):
    """Test that existing configs without max_tokens continue to work."""

    def _make_table(self, activities=None):
        mock_config = create_autospec(LLMRoutingConfigService, instance=True)
        mock_config.get_activities_config.return_value = activities or {}
        mock_logger = create_autospec(LoggingService, instance=True)
        mock_logger.get_class_logger.return_value = Mock()
        return ActivityRoutingTable(mock_config, mock_logger)

    def test_existing_config_without_max_tokens(self):
        """Pre-E03 activity configs work unchanged."""
        table = self._make_table(
            {
                "code_generation": {
                    "low": {
                        "primary": {"provider": "anthropic", "model": "haiku"},
                        "fallbacks": [{"provider": "openai", "model": "gpt-mini"}],
                    },
                    "medium": {
                        "primary": {"provider": "anthropic", "model": "sonnet"},
                        "fallbacks": [],
                    },
                }
            }
        )

        low = table.plan("code_generation", "low")
        self.assertEqual(len(low), 2)
        self.assertEqual(low[0]["provider"], "anthropic")
        self.assertNotIn("max_tokens", low[0])

        medium = table.plan("code_generation", "medium")
        self.assertEqual(len(medium), 1)
        self.assertNotIn("max_tokens", medium[0])

    def test_routing_context_from_dict_without_max_tokens(self):
        """Pre-E03 routing context dicts work without max_tokens."""
        data = {
            "task_type": "general",
            "routing_enabled": True,
            "activity": "code_generation",
        }
        ctx = RoutingContext.from_dict(data)
        self.assertIsNone(ctx.max_tokens)
        self.assertEqual(ctx.activity, "code_generation")


if __name__ == "__main__":
    unittest.main()
