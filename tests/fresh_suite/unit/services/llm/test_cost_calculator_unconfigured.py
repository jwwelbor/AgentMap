"""The existing zero-catalog calculator contract, split for the file limit."""

import unittest

from agentmap.models.llm_execution import LLMUsage
from tests.fresh_suite.unit.services.llm.test_cost_calculator import _make_calculator


class TestCostCalculatorZeroCostWhenUnconfigured(unittest.TestCase):
    """TC-NFR2-01: an empty catalog cannot produce a priced receipt."""

    def test_tc_nfr2_01_empty_catalog_calculate_returns_none(self):
        calculator = _make_calculator({})

        result = calculator.calculate(
            LLMUsage(input_tokens=1, output_tokens=1), "openai", "gpt-4"
        )

        self.assertIsNone(result)
        self.assertIsNone(calculator.catalog_version)
