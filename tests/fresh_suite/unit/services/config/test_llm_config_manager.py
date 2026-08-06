"""
Unit tests for LLMConfigManager.get_pricing_config() (T-E05-F06-003).

Covers TC-009a (absent llm.pricing block yields a structural-defaults-only
empty catalog) and TC-009c (apply_cost_optimization / max_cost_tier remain a
no-op, confirming the catalog is architecturally separate from
routing.cost_optimization).
"""

import unittest
from unittest.mock import Mock

from agentmap.services.config.config_managers.llm_config_manager import (
    LLMConfigManager,
)
from agentmap.services.config.config_service import ConfigService
from agentmap.services.routing.model_selector import ModelSelector
from agentmap.services.routing.types import TaskComplexity


def _mock_get_value(config_data, path, default=None):
    """Mirror the real dot-notation traversal used by ConfigService."""
    parts = path.split(".")
    current = config_data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def _make_manager(config_data):
    mock_config_service = Mock(spec=ConfigService)
    mock_config_service.get_value_from_config.side_effect = _mock_get_value
    return LLMConfigManager(mock_config_service, config_data)


class TestLLMConfigManagerPricingConfig(unittest.TestCase):
    """TC-009a: Absent llm.pricing block yields empty catalog."""

    def test_tc_009a_absent_block_yields_structural_defaults_only(self):
        """No 'llm.pricing' key in loaded YAML -> structural defaults only,
        no fabricated rates (Out of Scope 8)."""
        manager = _make_manager({"llm": {"anthropic": {"api_key": "x"}}})

        catalog = manager.get_pricing_config()

        self.assertEqual(
            catalog, {"catalog_version": None, "currency": "USD", "models": {}}
        )

    def test_tc_009a_no_top_level_llm_section_yields_structural_defaults(self):
        manager = _make_manager({})

        catalog = manager.get_pricing_config()

        self.assertIsNone(catalog["catalog_version"])
        self.assertEqual(catalog["currency"], "USD")
        self.assertEqual(catalog["models"], {})

    def test_populated_block_returns_configured_rates_by_provider_model(self):
        manager = _make_manager(
            {
                "llm": {
                    "pricing": {
                        "catalog_version": "2026-08-01",
                        "currency": "USD",
                        "models": {
                            "anthropic": {
                                "claude-sonnet-4-5": {
                                    "input_per_1m": 3.00,
                                    "output_per_1m": 15.00,
                                }
                            }
                        },
                    }
                }
            }
        )

        catalog = manager.get_pricing_config()

        self.assertEqual(catalog["catalog_version"], "2026-08-01")
        self.assertEqual(
            catalog["models"]["anthropic"]["claude-sonnet-4-5"]["input_per_1m"], 3.00
        )

    def test_get_pricing_config_not_mocked_out_in_this_suite(self):
        """Counter-factual guard: fail loudly if a future edit replaces this
        test's manager with a Mock of get_pricing_config() itself, which
        would defeat TC-009a's purpose."""
        manager = _make_manager({})
        self.assertFalse(isinstance(manager.get_pricing_config, Mock))


class TestApplyCostOptimizationRemainsNoOp(unittest.TestCase):
    """TC-009c / TC-021: apply_cost_optimization / max_cost_tier remain a
    no-op -- pricing is an architecturally separate config surface
    (Decision 6). This is a regression assertion on existing,
    already-a-no-op behavior; unaffected by llm.pricing being present."""

    def test_tc_009c_apply_cost_optimization_unaffected_by_pricing_presence(self):
        selector = ModelSelector(routing_config=Mock(), logger=Mock())
        providers = ["anthropic", "openai"]

        result_without_pricing = selector.apply_cost_optimization(
            providers, TaskComplexity.HIGH, max_cost_tier="low"
        )
        result_with_pricing_tier = selector.apply_cost_optimization(
            providers, TaskComplexity.HIGH, max_cost_tier="critical"
        )

        # A no-op ignores max_cost_tier entirely -- both calls return the
        # unfiltered input list, regardless of tier.
        self.assertEqual(result_without_pricing, providers)
        self.assertEqual(result_with_pricing_tier, providers)


if __name__ == "__main__":
    unittest.main()
