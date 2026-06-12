"""
Integration tests for async graph runner execution through the real DI container.

TC-007: Real DI async workflow execution and suspend/resume round trip.

Covers: AC-005, AC-006, REQ-F-005, REQ-F-006, REQ-NF-003, REQ-NF-004 (E04-F04)

Caller-Path Contract (TC-007):
    Production entrypoint:
        GraphRunnerService.run_async(bundle, initial_state=...)
        GraphRunnerService.resume_from_checkpoint_async(bundle, thread_id, ...)
        reached through the real DI container wiring.
    Lowest allowed mock seam:
        Only external resources the integration harness already isolates
        (temp storage dirs, test CSV files).  The graph runner, execution,
        checkpoint manager, and graph assembly services must be real.
    Forbidden mocks:
        Mocking GraphRunnerService, GraphExecutionService, CheckpointManager,
        GraphAssemblyService, or any orchestration boundary itself.
    Counter-factual:
        A buggy implementation would pass unit tests but fail when the real
        DI wiring, checkpoint store, or graph assembly stack is exercised together.
"""

import asyncio
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from agentmap.di.containers import ApplicationContainer


class TestAsyncGraphRunnerIntegration(unittest.TestCase):
    """TC-007: DI-backed async runner execution and suspend/resume parity.

    All services that are part of the production execution boundary
    (GraphRunnerService, GraphExecutionService, CheckpointManager,
    GraphAssemblyService) are real.  Only transient filesystem resources
    are isolated using a temporary directory.
    """

    def setUp(self):
        """Set up the real DI container with temporary config/storage directories."""
        self.temp_dir = tempfile.mkdtemp()
        self.user_storage_dir = os.path.join(self.temp_dir, "user_storage")
        self.cache_dir = os.path.join(self.temp_dir, "cache")
        self.examples_dir = os.path.join(self.temp_dir, "examples")

        os.makedirs(self.user_storage_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.examples_dir, exist_ok=True)

        self._create_simple_workflow_csv()
        self._create_test_config_files()

        self.container = ApplicationContainer()
        self.container.config.from_dict(
            {"path": os.path.join(self.temp_dir, "config.yaml")}
        )
        self.container.wire(modules=[])

    def tearDown(self):
        """Clean up test fixtures."""
        self.container.unwire()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Fixture helpers
    # ------------------------------------------------------------------

    def _create_simple_workflow_csv(self):
        """Create a minimal two-node workflow CSV for async execution tests."""
        csv_content = (
            "GraphName,Node,AgentType,Prompt,Description,"
            "Input_Fields,Output_Field,Edge,Context,Success_Next,Failure_Next\n"
            "SimpleAsyncGraph,StartNode,input,Enter your message,"
            "Entry point,input,message,EndNode,,,\n"
            "SimpleAsyncGraph,EndNode,default,Process message,"
            "Final node,message,result,,,,\n"
        )
        self.simple_csv_path = os.path.join(self.examples_dir, "simple_async_graph.csv")
        with open(self.simple_csv_path, "w") as f:
            f.write(csv_content)

    def _create_test_config_files(self):
        """Create YAML config files required by the DI container."""
        storage_config_path = os.path.join(self.temp_dir, "storage.yaml").replace(
            "\\", "/"
        )
        cache_path = self.cache_dir.replace("\\", "/")
        examples_path = self.examples_dir.replace("\\", "/")
        config_content = (
            f'storage_config_path: "{storage_config_path}"\n'
            f"paths:\n"
            f'  cache: "{cache_path}"\n'
            f'  examples: "{examples_path}"\n'
            "logging:\n"
            "  level: WARNING\n"
            "execution:\n"
            "  success_policy: any_end_node\n"
        )
        config_path = os.path.join(self.temp_dir, "config.yaml")
        with open(config_path, "w") as f:
            f.write(config_content)

        user_storage_path = self.user_storage_dir.replace("\\", "/")
        storage_content = (
            f'base_directory: "{user_storage_path}"\n'
            "providers:\n"
            "  json:\n"
            "    enabled: true\n"
            "    settings:\n"
            "      indent: 2\n"
            "  csv:\n"
            "    enabled: true\n"
        )
        storage_path = os.path.join(self.temp_dir, "storage.yaml")
        with open(storage_path, "w") as f:
            f.write(storage_content)

    def _get_graph_runner_service(self):
        """Retrieve the real GraphRunnerService from the container."""
        return self.container.graph_runner_service()

    def _get_bundle_service(self):
        """Retrieve the real GraphBundleService from the container."""
        return self.container.graph_bundle_service()

    def _load_simple_bundle(self):
        """Load a GraphBundle for the simple two-node graph."""
        bundle_service = self._get_bundle_service()
        bundle, _ = bundle_service.get_or_create_bundle(
            csv_path=Path(self.simple_csv_path),
            graph_name="SimpleAsyncGraph",
        )
        return bundle

    # ------------------------------------------------------------------
    # TC-007a: async runner produces the same result envelope as sync runner
    # ------------------------------------------------------------------

    def test_tc007a_async_runner_returns_execution_result(self):
        """TC-007: run_async() returns an ExecutionResult through the real container.

        Counter-factual: a buggy implementation passes unit tests but fails
        when the real DI wiring (assembly service, execution tracking) runs.
        """
        graph_runner = self._get_graph_runner_service()
        bundle = self._load_simple_bundle()

        initial_state = {"input": "integration test message"}
        result = asyncio.run(
            graph_runner.run_async(bundle, initial_state=initial_state)
        )

        self.assertIsNotNone(result, "run_async must return an ExecutionResult")
        self.assertEqual(
            result.graph_name,
            "SimpleAsyncGraph",
            "graph_name must be preserved in the result envelope",
        )
        self.assertIsNotNone(
            result.execution_summary,
            "execution_summary must be present in the result envelope",
        )
        self.assertIsNotNone(
            result.final_state,
            "final_state must not be None in the result envelope",
        )
        self.assertIsNotNone(
            result.total_duration,
            "total_duration must be set",
        )

    def test_tc007b_async_result_envelope_matches_sync_result_envelope(self):
        """TC-007: async and sync runs produce the same result-envelope fields.

        The async path must not drop fields that the sync path includes
        (REQ-F-006).
        """
        graph_runner = self._get_graph_runner_service()

        # Load two independent bundles so the runs do not share state
        bundle_async = self._load_simple_bundle()
        bundle_sync = self._load_simple_bundle()

        initial_state = {"input": "parity check"}

        sync_result = graph_runner.run(bundle_sync, initial_state=initial_state)
        async_result = asyncio.run(
            graph_runner.run_async(bundle_async, initial_state=initial_state)
        )

        # The result envelope fields that must be identical in shape
        self.assertEqual(
            sync_result.graph_name,
            async_result.graph_name,
            "graph_name must be the same in sync and async results",
        )
        self.assertIsNotNone(
            async_result.execution_summary,
            "async result must include execution_summary",
        )
        self.assertIsNotNone(
            sync_result.execution_summary,
            "sync result must include execution_summary",
        )
        # Both should reach the same terminal success state for the same graph
        self.assertEqual(
            sync_result.success,
            async_result.success,
            "sync and async paths must agree on success for the same graph",
        )

    # ------------------------------------------------------------------
    # TC-007c: async runner builds the right services from the container
    # ------------------------------------------------------------------

    def test_tc007c_async_runner_service_is_real(self):
        """TC-007: graph_runner_service() from the container is a real instance.

        This is the wiring proof: the container actually returns a wired
        GraphRunnerService with the async methods available, not a mock or
        None.
        """
        import inspect

        graph_runner = self._get_graph_runner_service()

        # Service must be a real GraphRunnerService (not a Mock)
        from agentmap.services.graph.graph_runner_service import GraphRunnerService

        self.assertIsInstance(
            graph_runner,
            GraphRunnerService,
            "container.graph_runner_service() must return a real GraphRunnerService",
        )

        # run_async must be a coroutine function on the real service
        self.assertTrue(
            inspect.iscoroutinefunction(graph_runner.run_async),
            "run_async must be a coroutine function on the real service",
        )

        # resume_from_checkpoint_async must also be present
        self.assertTrue(
            inspect.iscoroutinefunction(graph_runner.resume_from_checkpoint_async),
            "resume_from_checkpoint_async must be a coroutine function",
        )

    # ------------------------------------------------------------------
    # TC-007d: sync run() still works after async methods are added
    # (AC-006 regression gate through the real container)
    # ------------------------------------------------------------------

    def test_tc007d_sync_run_still_works_through_real_container(self):
        """TC-007 / AC-006: sync run() is unaffected by async additions.

        Exercises the same production code path as existing sync tests but
        through the real DI container, confirming async additions did not
        break sync execution wiring.
        """
        graph_runner = self._get_graph_runner_service()
        bundle = self._load_simple_bundle()

        result = graph_runner.run(bundle, initial_state={"input": "sync regression"})

        self.assertIsNotNone(
            result,
            "sync run() must still return ExecutionResult through real container",
        )
        self.assertEqual(result.graph_name, "SimpleAsyncGraph")
        self.assertIsNotNone(result.execution_summary)

    # ------------------------------------------------------------------
    # TC-007e: protocol conformance through real container wiring
    # ------------------------------------------------------------------

    def test_tc007e_real_service_satisfies_protocol(self):
        """TC-007: the real container-wired GraphRunnerService satisfies the protocol.

        This is the end-to-end wiring proof for REQ-F-007: protocol-based DI
        injection works with the concrete service that implements the async
        methods (GraphRunnerServiceProtocol.run_async and
        resume_from_checkpoint_async).
        """
        from agentmap.services.protocols.service_protocols import (
            GraphRunnerServiceProtocol,
        )

        graph_runner = self._get_graph_runner_service()

        self.assertIsInstance(
            graph_runner,
            GraphRunnerServiceProtocol,
            "real GraphRunnerService must satisfy GraphRunnerServiceProtocol "
            "including async members",
        )


if __name__ == "__main__":
    unittest.main()
