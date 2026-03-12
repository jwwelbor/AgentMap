"""
Performance benchmark tests for StateAdapterService.get_inputs().

Validates that the overhead of mapped and positional binding modes relative
to direct mode is below 1ms per node (REQ-NF-001).

AC Coverage: AC-05 (Mapping resolution overhead < 1ms per node)
"""

import statistics
import time
import unittest

from agentmap.services.state_adapter_service import StateAdapterService


class TestStateAdapterPerformance(unittest.TestCase):
    """Performance benchmarks for get_inputs binding modes."""

    NUM_FIELDS = 100
    NUM_ITERATIONS = 10
    MAX_OVERHEAD_PER_NODE_SECONDS = 0.001  # 1ms

    def setUp(self) -> None:
        """Create shared test fixtures for all benchmark tests."""
        # State with 100 keys
        self.state = {f"field_{i}": i for i in range(self.NUM_FIELDS)}

        # Direct mode fields: plain names
        self.direct_fields = [f"field_{i}" for i in range(self.NUM_FIELDS)]

        # Mapped mode fields: state_key:param_name
        self.mapped_fields = [f"field_{i}:param_{i}" for i in range(self.NUM_FIELDS)]

        # Positional mode: plain names + expected_params list
        self.positional_expected_params = [f"param_{i}" for i in range(self.NUM_FIELDS)]

    def _measure_median(
        self,
        fields: list,
        expected_params: list = None,
    ) -> float:
        """Run get_inputs NUM_ITERATIONS times and return median elapsed seconds."""
        times = []
        for _ in range(self.NUM_ITERATIONS):
            start = time.perf_counter()
            StateAdapterService.get_inputs(
                self.state, fields, expected_params=expected_params
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        return statistics.median(times)

    def test_get_inputs_mapped_overhead_below_1ms_per_node(self) -> None:
        """Mapped mode overhead vs direct mode must be < 1ms per node."""
        direct_median = self._measure_median(self.direct_fields)
        mapped_median = self._measure_median(self.mapped_fields)

        overhead_per_node = (mapped_median - direct_median) / self.NUM_FIELDS
        self.assertLess(
            overhead_per_node,
            self.MAX_OVERHEAD_PER_NODE_SECONDS,
            f"Mapped overhead per node {overhead_per_node*1000:.4f}ms exceeds 1ms limit. "
            f"Direct median: {direct_median*1000:.4f}ms, "
            f"Mapped median: {mapped_median*1000:.4f}ms",
        )

    def test_get_inputs_positional_overhead_below_1ms_per_node(self) -> None:
        """Positional mode overhead vs direct mode must be < 1ms per node."""
        direct_median = self._measure_median(self.direct_fields)
        positional_median = self._measure_median(
            self.direct_fields, expected_params=self.positional_expected_params
        )

        overhead_per_node = (positional_median - direct_median) / self.NUM_FIELDS
        self.assertLess(
            overhead_per_node,
            self.MAX_OVERHEAD_PER_NODE_SECONDS,
            f"Positional overhead per node {overhead_per_node*1000:.4f}ms exceeds 1ms limit. "
            f"Direct median: {direct_median*1000:.4f}ms, "
            f"Positional median: {positional_median*1000:.4f}ms",
        )

    def test_get_inputs_direct_mode_no_regression(self) -> None:
        """Direct mode on 100 fields must complete in < 10ms (sanity check)."""
        direct_median = self._measure_median(self.direct_fields)
        self.assertLess(
            direct_median,
            0.010,
            f"Direct mode median {direct_median*1000:.4f}ms exceeds 10ms sanity limit",
        )


if __name__ == "__main__":
    unittest.main()
