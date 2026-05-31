"""Tests for the GraphRunnerService missing-service wiring gate.

The gate enforces the "compiler error" invariant at run/execute time: a graph
whose declared agents require an undeclared/unregistered service must hard-fail
before execution. Assembly records ``bundle.missing_services``; ``run()``
refuses. Scaffold/update/validate paths do not pass through ``run()``.
"""

import unittest

from agentmap.exceptions.graph_exceptions import MissingServiceDeclarationError
from tests.unit.services.graph.test_graph_runner_telemetry import (
    _make_graph_runner_service,
    _make_mock_bundle,
    _setup_successful_run,
)


class TestMissingServicesGate(unittest.TestCase):
    """Validate the run() wiring gate behaviour."""

    def test_run_raises_when_missing_services_present(self):
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("g")
        bundle.missing_services = {"bogus_service"}

        with self.assertRaises(MissingServiceDeclarationError) as ctx:
            service.run(bundle)

        self.assertIn("bogus_service", str(ctx.exception))
        # Gate fires before any scoped-registry / execution work begins.
        mocks["declaration"].create_scoped_registry_for_bundle.assert_not_called()

    def test_run_proceeds_when_no_missing_services(self):
        service, mocks = _make_graph_runner_service()
        bundle = _make_mock_bundle("g")
        bundle.missing_services = set()
        result = _setup_successful_run(mocks, bundle)

        self.assertEqual(service.run(bundle), result)
        mocks["declaration"].create_scoped_registry_for_bundle.assert_called_once()

    def test_check_missing_services_helper_is_noop_when_attr_absent(self):
        """A bundle without the field (legacy) must not trip the gate."""
        service, _ = _make_graph_runner_service()

        class _LegacyBundle:
            graph_name = "legacy"

        # Should not raise.
        service._check_missing_services(_LegacyBundle())


if __name__ == "__main__":
    unittest.main()
