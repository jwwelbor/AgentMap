"""
Unit tests for ActivityRoutingTable.

Tests that ActivityRoutingTable correctly uses the LLMRoutingConfigService
interface — specifically that it calls only methods that actually exist
on the real service class.

Uses create_autospec to enforce interface compliance: any call to a method
that doesn't exist on the real LLMRoutingConfigService raises AttributeError.
"""

import unittest
from unittest.mock import Mock, create_autospec

from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.activity_routing import ActivityRoutingTable


class TestActivityRoutingTableInterface(unittest.TestCase):
    """Test that ActivityRoutingTable uses the real LLMRoutingConfigService interface."""

    def _make_table(self, activities=None):
        """Create an ActivityRoutingTable with an autospec'd LLMRoutingConfigService.

        Using create_autospec ensures that only methods that actually exist
        on LLMRoutingConfigService can be called — any call to a nonexistent
        method raises AttributeError immediately.
        """
        mock_config = create_autospec(LLMRoutingConfigService, instance=True)
        mock_config.get_activities_config.return_value = activities or {}
        mock_logger = Mock(spec=LoggingService)
        mock_logger.get_class_logger = Mock(return_value=Mock())
        return ActivityRoutingTable(mock_config, mock_logger), mock_config

    def test_plan_calls_get_activities_config(self):
        """plan() uses get_activities_config() — the proper typed accessor."""
        table, mock_config = self._make_table(
            {
                "extraction": {
                    "low": {
                        "primary": {
                            "provider": "anthropic",
                            "model": "claude-haiku-4-5",
                        },
                        "fallbacks": [],
                    }
                }
            }
        )

        table.plan("extraction", "low")
        mock_config.get_activities_config.assert_called_once()

    def test_plan_returns_candidates(self):
        """plan() returns ordered primary + fallback candidates."""
        activities = {
            "extraction": {
                "low": {
                    "primary": {"provider": "anthropic", "model": "claude-haiku-4-5"},
                    "fallbacks": [
                        {"provider": "openai", "model": "gpt-4o-mini"},
                    ],
                }
            }
        }
        table, _ = self._make_table(activities)

        candidates = table.plan("extraction", "low")
        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            candidates[0], {"provider": "anthropic", "model": "claude-haiku-4-5"}
        )
        self.assertEqual(candidates[1], {"provider": "openai", "model": "gpt-4o-mini"})

    def test_plan_returns_empty_for_unknown_activity(self):
        """plan() returns empty list for unconfigured activities."""
        table, _ = self._make_table({})

        candidates = table.plan("unknown_activity", "low")
        self.assertEqual(candidates, [])

    def test_plan_returns_empty_when_no_activity_provided(self):
        """plan() returns empty list when activity is None."""
        table, _ = self._make_table()
        self.assertEqual(table.plan(None, "low"), [])

    def test_plan_normalizes_activity_name(self):
        """plan() normalizes activity names (case-insensitive, stripped)."""
        activities = {
            "extraction": {
                "low": {
                    "primary": {"provider": "anthropic", "model": "claude-haiku-4-5"},
                    "fallbacks": [],
                }
            }
        }
        table, _ = self._make_table(activities)

        # Should find "extraction" via normalized lookup
        candidates = table.plan("  Extraction  ", "low")
        self.assertEqual(len(candidates), 1)

    def test_plan_falls_back_to_any_complexity(self):
        """plan() uses 'any' tier when specific complexity not found."""
        activities = {
            "generation": {
                "any": {
                    "primary": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
                    "fallbacks": [],
                }
            }
        }
        table, _ = self._make_table(activities)

        # "high" isn't defined, should fall back to "any"
        candidates = table.plan("generation", "high")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["model"], "claude-sonnet-4-6")

    def test_plan_skips_invalid_candidates(self):
        """plan() skips candidates missing provider or model."""
        activities = {
            "analysis": {
                "medium": {
                    "primary": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
                    "fallbacks": [
                        {"provider": "openai"},  # missing model
                        "not-a-dict",  # wrong type
                        {"provider": "google", "model": "gemini-2.5-pro"},
                    ],
                }
            }
        }
        table, _ = self._make_table(activities)

        candidates = table.plan("analysis", "medium")
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["provider"], "anthropic")
        self.assertEqual(candidates[1]["provider"], "google")


if __name__ == "__main__":
    unittest.main()
