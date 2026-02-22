"""
Integration test for two-layer (nested) graph execution.

Tests that a graph can call a subgraph defined in the same CSV file
using the GraphAgent with the 'graph' agent type. This validates the
full runtime pipeline: CSV parsing → bundle creation → subgraph pre-resolution → nested execution.

Supports both the new {workflow=...} Context syntax and the legacy
Prompt-based resolution path.
"""

import unittest
from pathlib import Path

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest


class TestTwoLayerGraphIntegration(BaseIntegrationTest):
    """Integration tests for nested graph execution via GraphAgent."""

    # New syntax: {workflow=::SubgraphName} in the Context column.
    TWO_LAYER_CSV = """\
GraphName,Node,AgentType,Input_Fields,Output_Field,Success_Next,Failure_Next,Context,Prompt
TestOuter,Start,default,input,data,CallInner,,,Initialize data
TestOuter,CallInner,graph,data,inner_result,Done,,{workflow=::TestInner},Call inner graph
TestOuter,Done,default,inner_result|data,final_result,,,,Return final result
TestInner,Process,default,data,processed,InnerDone,,,Process inner data
TestInner,InnerDone,default,processed|data,inner_final,,,,Return inner result
"""

    # Legacy syntax: subgraph name in Prompt column, no Context directive.
    LEGACY_TWO_LAYER_CSV = """\
GraphName,Node,AgentType,Input_Fields,Output_Field,Success_Next,Failure_Next,Context,Prompt
TestOuter,Start,default,input,data,CallInner,,,Initialize data
TestOuter,CallInner,graph,data,inner_result,Done,,,TestInner
TestOuter,Done,default,inner_result|data,final_result,,,,Return final result
TestInner,Process,default,data,processed,InnerDone,,,Process inner data
TestInner,InnerDone,default,processed|data,inner_final,,,,Return inner result
"""

    def setup_services(self):
        """Initialize services needed for graph execution."""
        super().setup_services()
        self.graph_runner_service = self.container.graph_runner_service()
        self.graph_bundle_service = self.container.graph_bundle_service()
        self.graph_execution_service = self.container.graph_execution_service()

    def _create_two_layer_csv(self, filename="two_layer_test.csv", content=None):
        """Create the two-layer CSV file and return its path."""
        csv_path = self.create_test_csv_file(
            content or self.TWO_LAYER_CSV,
            filename=filename,
        )
        return csv_path

    # --- New {workflow=...} syntax tests ---

    def test_outer_graph_calls_inner_graph(self):
        """
        Test that an outer graph can execute an inner graph defined in the same CSV
        using the new {workflow=::TestInner} Context syntax.
        """
        csv_path = self._create_two_layer_csv()

        bundle, _ = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="TestOuter",
        )

        self.assertIsNotNone(bundle, "Should create bundle for TestOuter")
        self.assertEqual(bundle.graph_name, "TestOuter")

        initial_state = {
            "input": "hello world",
            "data": "test data",
        }

        result = self.graph_runner_service.run(bundle, initial_state=initial_state)

        self.assertIsNotNone(result, "Should return a result")

        from agentmap.models.execution.result import ExecutionResult

        if isinstance(result, ExecutionResult):
            self.assertTrue(
                result.success,
                f"Outer graph should execute successfully. Error: {result.error}",
            )
            self.assertIsNotNone(result.final_state)
        else:
            self.assertIsInstance(result, dict)
            self.assertNotIn(
                "error", result, f"Should not have error: {result.get('error')}"
            )

    def test_inner_graph_exists_in_bundle(self):
        """Verify that both graphs are parsed from the CSV."""
        csv_path = self._create_two_layer_csv()

        inner_bundle, _ = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="TestInner",
        )

        self.assertIsNotNone(inner_bundle, "Should create bundle for TestInner")
        self.assertEqual(inner_bundle.graph_name, "TestInner")

    # --- Legacy Prompt-based resolution tests ---

    def test_legacy_prompt_based_resolution(self):
        """
        Test that the legacy path (subgraph name in Prompt column, no Context
        directive) still works via the fallback in _resolve_legacy_subgraph.
        """
        csv_path = self._create_two_layer_csv(
            filename="legacy_two_layer.csv",
            content=self.LEGACY_TWO_LAYER_CSV,
        )

        bundle, _ = self.graph_bundle_service.get_or_create_bundle(
            csv_path=csv_path,
            graph_name="TestOuter",
        )

        initial_state = {
            "input": "hello world",
            "data": "test data",
        }

        result = self.graph_runner_service.run(bundle, initial_state=initial_state)

        self.assertIsNotNone(result, "Should return a result")

        from agentmap.models.execution.result import ExecutionResult

        if isinstance(result, ExecutionResult):
            self.assertTrue(
                result.success,
                f"Legacy resolution should succeed. Error: {result.error}",
            )

    # --- Unit-level checks ---

    def test_graph_agent_reads_bundle_from_state(self):
        """
        Verify GraphAgent.process reads pre-resolved bundle from state
        and raises RuntimeError when it's missing.
        """
        import logging

        from agentmap.agents.builtins.graph_agent import GraphAgent

        agent = GraphAgent(
            name="CallInner",
            prompt="Call inner graph",
            context={},
            logger=logging.getLogger("test"),
        )

        # Should raise when subgraph_bundles is missing
        with self.assertRaises(RuntimeError) as ctx:
            agent.process({"data": "test"})

        self.assertIn("No pre-resolved subgraph bundle", str(ctx.exception))
        self.assertIn("CallInner", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
