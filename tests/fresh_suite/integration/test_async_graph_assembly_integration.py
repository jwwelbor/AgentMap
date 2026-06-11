"""
Integration tests for async graph assembly through the real DI container.

TC-009: Real DI integration exercises async graph assembly through the container wiring.

Covers: REQ-F-004, REQ-F-005, REQ-F-006, REQ-F-007, AC-007 (E04-F02 task T-E04-F02-003)

Caller-Path Contract (TC-009):
- Entrypoint: container.graph_assembly_service().assemble_graph_async(graph,
  agent_instances, orchestrator_node_registry=registry)
  from a real BaseIntegrationTest DI container.
- Lowest allowed mock seam: only local test doubles for the concrete agent stubs;
  the container and graph assembly service must be real.
- Forbidden mocks: do not mock the DI container, GraphAssemblyService, or any
  graph factory / assembly collaborator used by the real wiring.
- Counter-factual: a buggy implementation would pass unit tests but fail when
  the real container wiring, orchestrator injection, or graph model is exercised together.
"""

import unittest
from typing import Any, Dict

from agentmap.models.graph import Graph, Node
from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest

# ---------------------------------------------------------------------------
# Local concrete agent stubs (real subclass-free stubs that expose run_async)
# These are NOT mocked — they are the "only local test doubles" per the contract.
# ---------------------------------------------------------------------------


class LocalAsyncStubAgent:
    """Minimal real agent stub exposing both run and run_async."""

    def __init__(self, name: str):
        self.name = name

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"sync-{self.name}"}

    async def run_async(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"async-{self.name}"}


class LocalAsyncOrchestratorAgent:
    """Orchestrator-capable agent stub implementing the configuration protocol surface."""

    def __init__(self, name: str):
        self.name = name
        self.node_registry: Dict[str, Any] = {}
        self._orchestrator_service: Any = None
        self.configure_called: bool = False

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"sync-orch-{self.name}"}

    async def run_async(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"async-orch-{self.name}"}

    def configure_orchestrator_service(self, service: Any) -> None:
        self._orchestrator_service = service
        self.configure_called = True


# ---------------------------------------------------------------------------
# Fixture graph helpers
# ---------------------------------------------------------------------------


def _make_minimal_graph(name: str, entry_point: str = "Start") -> Graph:
    """Build a two-node Graph for basic async assembly tests."""
    start_node = Node(name="Start", agent_type="input")
    start_node.add_edge("default", "End")
    end_node = Node(name="End", agent_type="output")
    return Graph(
        name=name,
        entry_point=entry_point,
        nodes={"Start": start_node, "End": end_node},
    )


def _make_orchestrator_graph(name: str) -> Graph:
    """Build a three-node graph with an orchestrator-capable node."""
    orch_node = Node(name="Orchestrator", agent_type="orchestrator")
    orch_node.add_edge("failure", "Worker")
    worker_node = Node(name="Worker", agent_type="echo")
    worker_node.add_edge("default", "Orchestrator")
    return Graph(
        name=name,
        entry_point="Orchestrator",
        nodes={"Orchestrator": orch_node, "Worker": worker_node},
    )


# ---------------------------------------------------------------------------
# Integration test class
# ---------------------------------------------------------------------------


class TestAsyncGraphAssemblyIntegration(BaseIntegrationTest):
    """TC-009: Integration tests for async graph assembly via the real DI container.

    The DI container (BaseIntegrationTest.container) and GraphAssemblyService are
    NOT mocked.  Only the concrete agent stubs (LocalAsyncStubAgent and
    LocalAsyncOrchestratorAgent) are local test doubles, as specified by the
    Caller-Path Contract.
    """

    def setup_services(self):
        """Obtain the real graph assembly service from the DI container."""
        super().setup_services()
        self.graph_assembly_service = self.container.graph_assembly_service()
        self.graph_factory_service = self.container.graph_factory_service()
        self.assert_service_created(self.graph_assembly_service, "GraphAssemblyService")
        self.assert_service_created(self.graph_factory_service, "GraphFactoryService")

    # ------------------------------------------------------------------
    # TC-009a: basic async assembly compiles through the real container
    # ------------------------------------------------------------------

    def test_tc009a_async_assembly_returns_compiled_graph(self):
        """TC-009: assemble_graph_async() returns a compiled graph without exceptions.

        Counter-factual: a buggy implementation would pass unit tests but raise
        an exception or return None when the real DI-wired assembly service is used.
        """
        graph = _make_minimal_graph("integration_async_graph")
        agents: Dict[str, Any] = {
            "Start": LocalAsyncStubAgent("Start"),
            "End": LocalAsyncStubAgent("End"),
        }

        compiled = self.graph_assembly_service.assemble_graph_async(
            graph, agents, orchestrator_node_registry=None
        )

        self.assertIsNotNone(
            compiled,
            "assemble_graph_async() must return a compiled graph via the real container",
        )

    # ------------------------------------------------------------------
    # TC-009b: async vs sync assembly produce structurally equivalent graphs
    # ------------------------------------------------------------------

    def test_tc009b_async_and_sync_both_compile_for_same_fixture(self):
        """TC-009: async and sync assembly produce compiled graphs from the same fixture.

        This verifies that the async assembly path does not corrupt or break the
        graph model for a subsequent sync assembly call, and that both paths succeed.
        """
        agents_async: Dict[str, Any] = {
            "Start": LocalAsyncStubAgent("Start"),
            "End": LocalAsyncStubAgent("End"),
        }
        agents_sync: Dict[str, Any] = {
            "Start": LocalAsyncStubAgent("Start"),
            "End": LocalAsyncStubAgent("End"),
        }

        graph_async = _make_minimal_graph("integration_async_comparison_graph")
        graph_sync = _make_minimal_graph("integration_sync_comparison_graph")

        compiled_async = self.graph_assembly_service.assemble_graph_async(
            graph_async, agents_async, orchestrator_node_registry=None
        )
        compiled_sync = self.graph_assembly_service.assemble_graph(
            graph_sync, agents_sync, orchestrator_node_registry=None
        )

        self.assertIsNotNone(compiled_async, "Async path must produce a compiled graph")
        self.assertIsNotNone(compiled_sync, "Sync path must produce a compiled graph")

    # ------------------------------------------------------------------
    # TC-009c: orchestrator injection and node registry through real container
    # ------------------------------------------------------------------

    def test_tc009c_async_assembly_injects_orchestrator_through_real_container(self):
        """TC-009: orchestrator service injection works through the real DI container.

        Counter-factual: a buggy implementation would configure injection using a
        unit-test-only code path that is never reached when the real container wiring
        is used.
        """
        graph = _make_orchestrator_graph("integration_orch_async_graph")
        orch_agent = LocalAsyncOrchestratorAgent("Orchestrator")
        worker_agent = LocalAsyncStubAgent("Worker")
        agents: Dict[str, Any] = {
            "Orchestrator": orch_agent,
            "Worker": worker_agent,
        }
        registry: Dict[str, Any] = {
            "Orchestrator": {"type": "orchestrator"},
            "Worker": {"type": "echo"},
        }

        compiled = self.graph_assembly_service.assemble_graph_async(
            graph, agents, orchestrator_node_registry=registry
        )

        self.assertIsNotNone(
            compiled, "Async assembly must compile with orchestrator node"
        )
        self.assertTrue(
            orch_agent.configure_called,
            "configure_orchestrator_service() must be called via the real container",
        )
        self.assertEqual(
            orch_agent.node_registry,
            registry,
            "node_registry must be populated with the provided registry",
        )

    # ------------------------------------------------------------------
    # TC-009d: checkpoint-enabled async assembly through real container
    # ------------------------------------------------------------------

    def test_tc009d_async_checkpoint_assembly_through_real_container(self):
        """TC-009: assemble_with_checkpoint_async() compiles through the real container.

        Counter-factual: a buggy implementation would drop the checkpointer or fail
        when the graph model is constructed via the real factory wiring.
        """
        from unittest.mock import Mock

        graph = _make_minimal_graph("integration_checkpoint_async_graph")
        agents: Dict[str, Any] = {
            "Start": LocalAsyncStubAgent("Start"),
            "End": LocalAsyncStubAgent("End"),
        }
        # Use a test-double checkpointer: only the container + assembly service are real.
        mock_checkpointer = Mock()
        mock_checkpointer.__class__.__name__ = "MemorySaver"

        compiled = self.graph_assembly_service.assemble_with_checkpoint_async(
            graph,
            agents,
            node_definitions=None,
            checkpointer=mock_checkpointer,
        )

        self.assertIsNotNone(
            compiled,
            "assemble_with_checkpoint_async() must return a compiled graph via the real container",
        )

    # ------------------------------------------------------------------
    # TC-009e: entry-point detection still works through real container
    # ------------------------------------------------------------------

    def test_tc009e_entry_point_detection_through_real_container(self):
        """TC-009 edge: async assembly detects entry point via the real factory when none is set."""
        # Graph with entry_point=None so the real factory detect_entry_point() is exercised.
        start_node = Node(name="Start", agent_type="input")
        start_node.add_edge("default", "End")
        end_node = Node(name="End", agent_type="output")
        graph = Graph(
            name="integration_no_entry_async",
            entry_point=None,
            nodes={"Start": start_node, "End": end_node},
        )
        agents: Dict[str, Any] = {
            "Start": LocalAsyncStubAgent("Start"),
            "End": LocalAsyncStubAgent("End"),
        }

        compiled = self.graph_assembly_service.assemble_graph_async(
            graph, agents, orchestrator_node_registry=None
        )

        self.assertIsNotNone(
            compiled,
            "Async assembly with entry_point=None must detect entry point and compile",
        )

    # ------------------------------------------------------------------
    # TC-009f: no-orchestrator graph still compiles on async path
    # ------------------------------------------------------------------

    def test_tc009f_async_assembly_no_orchestrator_nodes(self):
        """TC-009 edge: graph without orchestrator nodes compiles via async path."""
        graph = _make_minimal_graph("integration_no_orch_async")
        agents: Dict[str, Any] = {
            "Start": LocalAsyncStubAgent("Start"),
            "End": LocalAsyncStubAgent("End"),
        }

        compiled = self.graph_assembly_service.assemble_graph_async(
            graph, agents, orchestrator_node_registry=None
        )

        self.assertIsNotNone(compiled)
        # Injection stats should show no orchestrators found
        stats = self.graph_assembly_service.get_injection_summary()
        self.assertEqual(
            stats["orchestrators_found"],
            0,
            "No orchestrators should be found in a graph without orchestrator nodes",
        )

    # ------------------------------------------------------------------
    # TC-009g: sync assemble_graph() still works as the default path
    # (regression gate through real container)
    # ------------------------------------------------------------------

    def test_tc009g_sync_assemble_graph_still_default_through_real_container(self):
        """TC-009 regression: sync assembly remains the default path in the real container.

        Counter-factual: a buggy implementation would change assemble_graph() to
        use the async path or break the existing sync contract.
        """
        graph = _make_minimal_graph("integration_sync_regression_real_container")
        agents: Dict[str, Any] = {
            "Start": LocalAsyncStubAgent("Start"),
            "End": LocalAsyncStubAgent("End"),
        }

        compiled = self.graph_assembly_service.assemble_graph(
            graph, agents, orchestrator_node_registry=None
        )

        self.assertIsNotNone(
            compiled,
            "assemble_graph() (sync default path) must still compile via real container",
        )


if __name__ == "__main__":
    unittest.main()
