"""
Unit tests for LLMCostCalculator (T-E05-F06-003).

Covers TC-001, TC-001a, TC-002, TC-003, TC-004, TC-005, TC-006, TC-009b from
docs/plan/E05-llm-prompt-caching-and-batch-execution/E05-F06-llm-cost-receipts-and-structured-tool-results/test-plan.md.

Scope-boundary note (T-E05-F06-003 explicitly forbids wiring the calculator
into ``LLMService``, deferred to T-E05-F06-004): the test-plan's Caller-Path
Contracts for TC-001, TC-002, TC-003, TC-004, TC-005, TC-006, and TC-NFR2-01
declare ``LLMService.call_llm_async(...)`` as the entrypoint, driving the
calculator through the live async receipt-construction path. T-E05-F06-004's
own task spec explicitly names this file's slice as the calculator-in-isolation
half and schedules "the cost-on-receipt assertions bundled into TC-001/TC-002
(rerun against the live LLMService path, not just the calculator in
isolation)" for itself. Accordingly, this file exercises the same
preconditions/inputs/expected-outputs directly against
``LLMCostCalculator.calculate()`` / ``.get_rates()`` -- the lowest seam
available before LLMService wiring exists -- and TC-NFR2-01 here is narrowed
to the calculator-level zero-config, zero-cost slice (no allocation beyond
returning ``None`` from an empty catalog); the full "no LLMBudgetCheck
constructed" assertion requires the budget-guard integration seam
(T-E05-F06-008) and is out of this task's scope.

Data-integrity note (test-plan arithmetic correction): the test-plan's TC-001
worked example states an expected ``total_cost`` of ``Decimal("0.011250")``,
but summing the four buckets it describes
(``1000/1e6*3.00 + 500/1e6*15.00 + 200/1e6*3.75 + 400/1e6*0.30``) computes to
``Decimal("0.011370")``. This file uses the arithmetically-correct value,
verified independently via Decimal arithmetic below, and implements
REQ-F-001's normative rule ("sum of tokens / 1_000_000 * rate for each
bucket, quantized to 6 decimal places") rather than the test-plan's example
figure.
"""

import unittest
from decimal import Decimal

from agentmap.exceptions import LLMConfigurationError
from agentmap.models.llm_cost import LLMModelRates
from agentmap.models.llm_execution import LLMUsage
from agentmap.services.llm.cost_calculator import LLMCostCalculator
from tests.utils.mock_service_factory import MockServiceFactory

_FULL_CATALOG = {
    "catalog_version": "2026-08-01",
    "currency": "USD",
    "models": {
        "anthropic": {
            "claude-sonnet-4-5": {
                "input_per_1m": 3.00,
                "output_per_1m": 15.00,
                "cache_write_per_1m": 3.75,
                "cache_read_per_1m": 0.30,
            }
        }
    },
}

_PARTIAL_CATALOG = {
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


def _make_calculator(pricing_config):
    logging_service = MockServiceFactory.create_mock_logging_service()
    return LLMCostCalculator(pricing_config, logging_service)


class TestCostCalculatorFullBucketComputation(unittest.TestCase):
    """TC-001: Full four-bucket cost computation."""

    def setUp(self):
        self.calculator = _make_calculator(_FULL_CATALOG)

    def test_tc_001_full_four_bucket_cost_computation(self):
        """TC-001: all four buckets present, deterministic Decimal total."""
        usage = LLMUsage(
            input_tokens=1000,
            output_tokens=500,
            cache_creation_input_tokens=200,
            cache_read_input_tokens=400,
        )

        breakdown = self.calculator.calculate(usage, "anthropic", "claude-sonnet-4-5")

        self.assertIsNotNone(breakdown)
        # See module docstring "Data-integrity note": 0.011370 is the
        # arithmetically-correct sum for these inputs, not the test-plan's
        # example figure of 0.011250.
        self.assertEqual(breakdown.total_cost, Decimal("0.011370"))
        self.assertEqual(breakdown.currency, "USD")
        self.assertEqual(breakdown.catalog_version, "2026-08-01")
        self.assertIsInstance(breakdown.total_cost, Decimal)

    def test_tc_001_zero_bucket_contributes_zero_not_skipped(self):
        """TC-001 edge case: input_tokens=0 contributes Decimal('0'), not skipped."""
        usage = LLMUsage(
            input_tokens=0,
            output_tokens=500,
            cache_creation_input_tokens=200,
            cache_read_input_tokens=400,
        )

        breakdown = self.calculator.calculate(usage, "anthropic", "claude-sonnet-4-5")

        self.assertIsNotNone(breakdown)
        self.assertEqual(breakdown.input_cost, Decimal("0"))

    def test_tc_001_trailing_zero_decimal_strings_parse_identically(self):
        """TC-001 edge case: '3.00' and '3' parse to the same Decimal (NFR-F-005)."""
        catalog_dotted = {
            "currency": "USD",
            "models": {"anthropic": {"m": {"input_per_1m": "3.00"}}},
        }
        catalog_plain = {
            "currency": "USD",
            "models": {"anthropic": {"m": {"input_per_1m": "3"}}},
        }
        calc_dotted = _make_calculator(catalog_dotted)
        calc_plain = _make_calculator(catalog_plain)

        self.assertEqual(
            calc_dotted.get_rates("anthropic", "m").input_per_1m,
            calc_plain.get_rates("anthropic", "m").input_per_1m,
        )


class TestCostCalculatorQuantizationAndMalformedRates(unittest.TestCase):
    """TC-001a: Quantization determinism and malformed catalog rate rejection."""

    def test_tc_001a_quantization_is_deterministic(self):
        """TC-001a Input 1: repeated calls with a non-terminating product are
        byte-identical and quantized to exactly 6 decimal places."""
        catalog = {
            "currency": "USD",
            "models": {"anthropic": {"m": {"input_per_1m": "3.33"}}},
        }
        calculator = _make_calculator(catalog)
        usage = LLMUsage(input_tokens=333)

        result_1 = calculator.calculate(usage, "anthropic", "m")
        result_2 = calculator.calculate(usage, "anthropic", "m")

        self.assertEqual(result_1.total_cost, result_2.total_cost)
        decimal_places = str(result_1.total_cost).split(".")[1]
        self.assertEqual(len(decimal_places), 6)

    def test_tc_001a_malformed_rate_raises_not_silently_none_or_crash(self):
        """TC-001a Input 2: a non-numeric catalog rate value for a bucket with
        positive usage raises a typed config error, rather than silently
        becoming cost=None or crashing with an unhandled InvalidOperation."""
        catalog = {
            "currency": "USD",
            "models": {"anthropic": {"m": {"input_per_1m": "N/A"}}},
        }
        calculator = _make_calculator(catalog)
        usage = LLMUsage(input_tokens=100)

        with self.assertRaises(LLMConfigurationError):
            calculator.calculate(usage, "anthropic", "m")


class TestCostCalculatorTwoBucketUsage(unittest.TestCase):
    """TC-002: Two-bucket usage (cache buckets absent)."""

    def setUp(self):
        self.calculator = _make_calculator(_FULL_CATALOG)

    def test_tc_002_absent_cache_buckets_contribute_zero(self):
        usage = LLMUsage(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=None,
            cache_read_input_tokens=None,
        )

        breakdown = self.calculator.calculate(usage, "anthropic", "claude-sonnet-4-5")

        self.assertIsNotNone(breakdown)
        self.assertEqual(breakdown.cache_write_cost, Decimal("0"))
        self.assertEqual(breakdown.cache_read_cost, Decimal("0"))
        expected_total = (Decimal(100) / Decimal(1_000_000)) * Decimal("3.00") + (
            Decimal(50) / Decimal(1_000_000)
        ) * Decimal("15.00")
        self.assertEqual(
            breakdown.total_cost,
            expected_total.quantize(Decimal("0.000001")),
        )


class TestCostCalculatorNoPricingConfigured(unittest.TestCase):
    """TC-003: No pricing configured at all -> cost is None (never a fabricated zero)."""

    def test_tc_003_empty_catalog_yields_none(self):
        calculator = _make_calculator({})
        usage = LLMUsage(input_tokens=100, output_tokens=50)

        result = calculator.calculate(usage, "openai", "gpt-4")

        self.assertIsNone(result)

    def test_tc_003_no_entry_for_resolved_pair_yields_none(self):
        """No pricing at all also means get_rates() itself returns None, not
        a fabricated zero-rate entry."""
        calculator = _make_calculator({})

        self.assertIsNone(calculator.get_rates("openai", "gpt-4"))


class TestCostCalculatorPositiveBucketWithoutRate(unittest.TestCase):
    """TC-004: Positive bucket with no configured rate -> None, not a partial total."""

    def test_tc_004_positive_unpriced_bucket_yields_none_not_partial(self):
        calculator = _make_calculator(_PARTIAL_CATALOG)
        usage = LLMUsage(
            input_tokens=100, output_tokens=50, cache_read_input_tokens=4000
        )

        result = calculator.calculate(usage, "anthropic", "claude-sonnet-4-5")

        self.assertIsNone(result)


class TestCostCalculatorZeroBucketWithoutRate(unittest.TestCase):
    """TC-005: Same partial catalog, bucket value is zero -> computed from present buckets."""

    def test_tc_005_zero_unpriced_bucket_computes_from_present_buckets(self):
        calculator = _make_calculator(_PARTIAL_CATALOG)
        usage = LLMUsage(input_tokens=100, output_tokens=50, cache_read_input_tokens=0)

        result = calculator.calculate(usage, "anthropic", "claude-sonnet-4-5")

        self.assertIsNotNone(result)
        expected_total = (Decimal(100) / Decimal(1_000_000)) * Decimal("3.00") + (
            Decimal(50) / Decimal(1_000_000)
        ) * Decimal("15.00")
        self.assertEqual(
            result.total_cost, expected_total.quantize(Decimal("0.000001"))
        )


class TestCostCalculatorUsageNone(unittest.TestCase):
    """TC-006: usage is None -> cost is None."""

    def test_tc_006_none_usage_yields_none_cost(self):
        calculator = _make_calculator(_FULL_CATALOG)

        result = calculator.calculate(None, "anthropic", "claude-sonnet-4-5")

        self.assertIsNone(result)


class TestCostCalculatorCaseInsensitiveLookup(unittest.TestCase):
    """TC-009b: Case-insensitive model-rate retrieval."""

    def test_tc_009b_case_insensitive_exact_match(self):
        calculator = _make_calculator(_FULL_CATALOG)

        rates = calculator.get_rates("Anthropic", "Claude-Sonnet-4-5")

        self.assertIsInstance(rates, LLMModelRates)
        self.assertEqual(rates.input_per_1m, Decimal("3.00"))

    def test_tc_009b_no_prefix_or_fuzzy_matching(self):
        calculator = _make_calculator(_FULL_CATALOG)

        self.assertIsNone(calculator.get_rates("anthropic", "claude-sonnet-4"))
        self.assertIsNone(calculator.get_rates("anthropic", "claude-sonnet-4-5-extra"))


class TestCostCalculatorZeroCostWhenUnconfigured(unittest.TestCase):
    """TC-NFR2-01 (calculator-level slice): zero-config catalog returns None
    cheaply, with no exception and no partial computation. The full
    LLMService-level "no LLMBudgetCheck constructed" assertion is out of
    scope here -- see module docstring."""

    def test_tc_nfr2_01_empty_catalog_calculate_returns_none(self):
        calculator = _make_calculator({})

        result = calculator.calculate(
            LLMUsage(input_tokens=1, output_tokens=1), "openai", "gpt-4"
        )

        self.assertIsNone(result)
        self.assertIsNone(calculator.catalog_version)


if __name__ == "__main__":
    unittest.main()
