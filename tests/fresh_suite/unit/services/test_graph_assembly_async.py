"""
Unit tests for GraphAssemblyService async assembly siblings.

TC-005: assemble_graph_async() binds run_async and preserves node ordering
TC-006: assemble_with_checkpoint_async() compiles with a checkpointer and binds run_async
TC-007: Async assembly injects orchestrator service and node registry on orchestrator-capable agents
TC-008: Existing sync assembly remains the default path and still binds run

Covers: REQ-F-004, REQ-F-005, REQ-F-006, REQ-F-007, REQ-NF-002, REQ-NF-004,
        AC-003, AC-004, AC-005, AC-006 (E04-F02 task T-E04-F02-003)

Caller-Path Contracts:
- TC-005 Entrypoint: GraphAssemblyService.assemble_graph_async(graph, agent_instances,
  orchestrator_node_registry=None)
  Lowest mock seam: StateGraph.add_node/compile binding seam and agent callables.
  Forbidden: do not mock _assemble_graph_common, _process_all_nodes,
  _add_orchestrator_routers, or add_node itself.
  Counter-factual: buggy impl keeps binding run in the async path.

- TC-006 Entrypoint: assemble_with_checkpoint_async(graph, agent_instances,
  node_definitions=None, checkpointer=checkpointer)
  Lowest mock seam: StateGraph.compile(checkpointer=...) and agent callables.
  Forbidden: do not mock _compile_graph, _assemble_graph_common, or private
  checkpoint helpers.
  Counter-factual: buggy impl drops the checkpointer or keeps sync run binding.

- TC-007 Entrypoint: assemble_graph_async(graph, agent_instances, orchestrator_node_registry=registry)
  Lowest mock seam: agent_instance.configure_orchestrator_service() and node_registry attribute.
  Forbidden: do not mock orchestrator-capable agent API, add_node, or injection branch.
  Counter-factual: buggy impl skips injection or only injects on sync path.

- TC-008 Entrypoint: assemble_graph(graph, agent_instances, orchestrator_node_registry=None)
  Lowest mock seam: StateGraph.add_node/compile and sync run callable.
  Forbidden: do not mock async methods or shims.
  Counter-factual: buggy impl changes default sync binding to run_async.
"""

import unittest
from typing import Any, Dict, List
from unittest.mock import Mock, patch

from agentmap.models.graph import Graph, Node
from agentmap.services.graph.graph_assembly_service import GraphAssemblyService

# ---------------------------------------------------------------------------
# Local agent stubs
# ---------------------------------------------------------------------------


class StubAsyncAgent:
    """Minimal stub agent that exposes both run and run_async."""

    def __init__(self, name: str):
        self.name = name
        self._run_calls: List[Any] = []
        self._run_async_calls: List[Any] = []

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        self._run_calls.append(state)
        return {"output": f"sync-{self.name}"}

    async def run_async(self, state: Dict[str, Any]) -> Dict[str, Any]:
        self._run_async_calls.append(state)
        return {"output": f"async-{self.name}"}


class StubOrchestratorAgent:
    """Orchestrator-capable agent stub that implements the protocol surface."""

    def __init__(self, name: str):
        self.name = name
        self.node_registry: Dict[str, Any] = {}
        self._orchestrator_service: Any = None
        self.configure_called = False

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"sync-orch-{self.name}"}

    async def run_async(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"output": f"async-orch-{self.name}"}

    def configure_orchestrator_service(self, service: Any) -> None:
        self._orchestrator_service = service
        self.configure_called = True


# Make StubOrchestratorAgent structurally satisfy OrchestrationCapableAgent
# by registering it — protocols are checked via isinstance at runtime.
# The protocol uses runtime_checkable, so we verify attribute presence.


class TestGraphAssemblyAsync(unittest.TestCase):
    """Unit tests for async graph assembly methods."""

    # ------------------------------------------------------------------
    # Shared setup
    # ------------------------------------------------------------------

    def setUp(self):
        """Construct a GraphAssemblyService with all dependencies mocked."""
        self.mock_config = Mock()
        self.mock_logging = Mock()
        self.mock_logger = Mock()
        self.mock_logging.get_class_logger.return_value = self.mock_logger
        self.mock_state_adapter = Mock()
        self.mock_features = Mock()
        self.mock_function_resolution = Mock()
        self.mock_graph_factory = Mock()
        self.mock_orchestrator_service = Mock()

        # Patch StateSchemaBuilder and EdgeProcessor so __init__ doesn't hit real
        # langgraph internals (they would need a valid schema config).
        with (
            patch(
                "agentmap.services.graph.graph_assembly_service.StateSchemaBuilder"
            ) as mock_ssb_cls,
            patch(
                "agentmap.services.graph.graph_assembly_service.EdgeProcessor"
            ) as mock_ep_cls,
        ):
            mock_ssb = Mock()
            mock_ssb.get_state_schema_from_config.return_value = dict
            mock_ssb.get_schema_for_graph.return_value = dict
            mock_ssb_cls.return_value = mock_ssb

            mock_ep = Mock()
            mock_ep_cls.return_value = mock_ep

            with patch(
                "agentmap.services.graph.graph_assembly_service.StateGraph"
            ) as mock_sg_cls:
                mock_sg_cls.return_value = Mock()
                self.assembly_service = GraphAssemblyService(
                    app_config_service=self.mock_config,
                    logging_service=self.mock_logging,
                    state_adapter_service=self.mock_state_adapter,
                    features_registry_service=self.mock_features,
                    function_resolution_service=self.mock_function_resolution,
                    graph_factory_service=self.mock_graph_factory,
                    orchestrator_service=self.mock_orchestrator_service,
                )
                self.mock_state_schema_builder = mock_ssb
                self.mock_edge_processor = mock_ep

        # Keep the schema builder mock on the service so _initialize_builder
        # uses it throughout the test.
        self.assembly_service.state_schema_builder = self.mock_state_schema_builder
        self.assembly_service.edge_processor = self.mock_edge_processor

    def _make_builder_mock(self) -> Mock:
        """Return a fresh StateGraph mock with compile() returning a mock compiled graph."""
        mock_builder = Mock()
        mock_compiled = Mock()
        mock_builder.compile.return_value = mock_compiled
        return mock_builder

    def _make_simple_graph(self, name: str, entry_point: str = "Start") -> Graph:
        """Build a minimal Graph domain object with two nodes."""
        start_node = Node(name="Start", agent_type="input")
        start_node.add_edge("default", "End")
        end_node = Node(name="End", agent_type="output")
        graph = Graph(
            name=name,
            entry_point=entry_point,
            nodes={"Start": start_node, "End": end_node},
        )
        return graph

    def _make_agent_instances(self, graph: Graph) -> Dict[str, Any]:
        """Return StubAsyncAgent instances for every node in graph."""
        return {name: StubAsyncAgent(name) for name in graph.nodes}

    # ------------------------------------------------------------------
    # TC-005: assemble_graph_async() binds run_async and preserves node ordering
    # ------------------------------------------------------------------

    def test_tc005_assemble_graph_async_binds_run_async(self):
        """TC-005: assemble_graph_async() binds run_async instead of run.

        Counter-factual: a buggy implementation would still call add_node with
        agent_instance.run (sync), making the async path behaviorally identical
        to the sync path and breaking async graph execution.
        """
        graph = self._make_simple_graph("async_graph")
        agents = self._make_agent_instances(graph)

        add_node_calls: List[tuple] = []

        def capture_add_node(name: str, callable_: Any) -> None:
            add_node_calls.append((name, callable_))

        mock_builder = self._make_builder_mock()
        mock_builder.add_node.side_effect = capture_add_node

        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            compiled = self.assembly_service.assemble_graph_async(
                graph, agents, orchestrator_node_registry=None
            )

        self.assertIsNotNone(
            compiled, "assemble_graph_async() must return a compiled graph"
        )

        # All registered callables must be run_async methods
        for node_name, bound_callable in add_node_calls:
            agent = agents[node_name]
            self.assertEqual(
                bound_callable,
                agent.run_async,
                f"Node '{node_name}' should bind run_async; got {bound_callable!r}",
            )

        # Node insertion order must match graph.nodes order
        registered_names = [name for name, _ in add_node_calls]
        self.assertEqual(
            registered_names,
            list(graph.nodes.keys()),
            "Node insertion order must match graph.nodes order",
        )

    def test_tc005_assemble_graph_async_sync_path_still_binds_run(self):
        """TC-005 (negative gate): sync assemble_graph() must NOT bind run_async.

        This sub-test is part of TC-005 and validates the split is clean.
        """
        graph = self._make_simple_graph("sync_control_graph")
        agents = self._make_agent_instances(graph)

        add_node_calls: List[tuple] = []

        def capture_add_node(name: str, callable_: Any) -> None:
            add_node_calls.append((name, callable_))

        mock_builder = self._make_builder_mock()
        mock_builder.add_node.side_effect = capture_add_node

        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            self.assembly_service.assemble_graph(
                graph, agents, orchestrator_node_registry=None
            )

        for node_name, bound_callable in add_node_calls:
            agent = agents[node_name]
            self.assertEqual(
                bound_callable,
                agent.run,
                f"Sync path: node '{node_name}' should bind run; got {bound_callable!r}",
            )
            self.assertNotEqual(
                bound_callable,
                agent.run_async,
                f"Sync path: node '{node_name}' must NOT bind run_async",
            )

    # ------------------------------------------------------------------
    # TC-006: assemble_with_checkpoint_async() preserves checkpointer and binds run_async
    # ------------------------------------------------------------------

    def test_tc006_assemble_with_checkpoint_async_uses_checkpointer(self):
        """TC-006: assemble_with_checkpoint_async() must compile with the supplied checkpointer.

        Counter-factual: a buggy implementation would compile without checkpoint
        support, silently dropping the checkpointer argument.
        """
        graph = self._make_simple_graph("checkpoint_async_graph")
        agents = self._make_agent_instances(graph)
        mock_checkpointer = Mock()
        mock_checkpointer.__class__.__name__ = "MemorySaver"

        compile_kwargs_captured: List[Dict[str, Any]] = []

        def capture_compile(**kwargs: Any) -> Mock:
            compile_kwargs_captured.append(kwargs)
            return Mock()

        mock_builder = self._make_builder_mock()
        mock_builder.compile.side_effect = capture_compile

        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            self.assembly_service.assemble_with_checkpoint_async(
                graph,
                agents,
                node_definitions=None,
                checkpointer=mock_checkpointer,
            )

        self.assertTrue(
            len(compile_kwargs_captured) > 0,
            "compile() must have been called",
        )
        self.assertIs(
            compile_kwargs_captured[0].get("checkpointer"),
            mock_checkpointer,
            "assemble_with_checkpoint_async() must pass the checkpointer to compile()",
        )

    def test_tc006_assemble_with_checkpoint_async_binds_run_async(self):
        """TC-006: assemble_with_checkpoint_async() must bind run_async, not run.

        Counter-factual: a buggy impl would use the sync add_node path and bind run.
        """
        graph = self._make_simple_graph("checkpoint_async_graph_2")
        agents = self._make_agent_instances(graph)
        mock_checkpointer = Mock()

        add_node_calls: List[tuple] = []

        def capture_add_node(name: str, callable_: Any) -> None:
            add_node_calls.append((name, callable_))

        mock_builder = self._make_builder_mock()
        mock_builder.add_node.side_effect = capture_add_node

        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            self.assembly_service.assemble_with_checkpoint_async(
                graph,
                agents,
                node_definitions=None,
                checkpointer=mock_checkpointer,
            )

        for node_name, bound_callable in add_node_calls:
            agent = agents[node_name]
            self.assertEqual(
                bound_callable,
                agent.run_async,
                f"Checkpoint-async path: node '{node_name}' must bind run_async",
            )

    def test_tc006_node_ordering_preserved_in_checkpoint_async(self):
        """TC-006 (edge): node insertion order matches graph.nodes for checkpoint async path."""
        graph = self._make_simple_graph("checkpoint_order_graph")
        agents = self._make_agent_instances(graph)
        mock_checkpointer = Mock()

        add_node_calls: List[tuple] = []
        mock_builder = self._make_builder_mock()
        mock_builder.add_node.side_effect = lambda n, c: add_node_calls.append((n, c))

        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            self.assembly_service.assemble_with_checkpoint_async(
                graph, agents, node_definitions=None, checkpointer=mock_checkpointer
            )

        self.assertEqual(
            [n for n, _ in add_node_calls],
            list(graph.nodes.keys()),
        )

    # ------------------------------------------------------------------
    # TC-007: Orchestrator injection on the async assembly path
    # ------------------------------------------------------------------

    def test_tc007_async_assembly_injects_orchestrator_service(self):
        """TC-007: assemble_graph_async() must call configure_orchestrator_service() on
        orchestrator-capable agents.

        Counter-factual: a buggy implementation would only inject on the sync path,
        leaving orchestrator nodes unconfigured when the async path is used.
        """
        orch_agent = StubOrchestratorAgent("Orchestrator")
        worker_agent = StubAsyncAgent("Worker")

        orch_node = Node(name="Orchestrator", agent_type="orchestrator")
        orch_node.add_edge("default", "Worker")
        worker_node = Node(name="Worker", agent_type="echo")
        worker_node.add_edge("default", "Orchestrator")

        graph = Graph(
            name="orchestrated_async_graph",
            entry_point="Orchestrator",
            nodes={"Orchestrator": orch_node, "Worker": worker_node},
        )
        agents = {"Orchestrator": orch_agent, "Worker": worker_agent}
        registry = {
            "Orchestrator": {"type": "orchestrator"},
            "Worker": {"type": "echo"},
        }

        mock_builder = self._make_builder_mock()
        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            self.assembly_service.assemble_graph_async(
                graph, agents, orchestrator_node_registry=registry
            )

        self.assertTrue(
            orch_agent.configure_called,
            "configure_orchestrator_service() must be called on async assembly path",
        )
        self.assertIs(
            orch_agent._orchestrator_service,
            self.mock_orchestrator_service,
            "Injected orchestrator service must be the one from the container",
        )
        self.assertEqual(
            orch_agent.node_registry,
            registry,
            "node_registry must be populated with the supplied registry",
        )

    def test_tc007_async_assembly_injects_orchestrator_without_registry(self):
        """TC-007 edge: orchestrator service injection still occurs when no registry is provided."""
        orch_agent = StubOrchestratorAgent("Orchestrator")
        worker_agent = StubAsyncAgent("Worker")

        orch_node = Node(name="Orchestrator", agent_type="orchestrator")
        orch_node.add_edge("default", "Worker")
        worker_node = Node(name="Worker", agent_type="echo")

        graph = Graph(
            name="orch_no_registry_graph",
            entry_point="Orchestrator",
            nodes={"Orchestrator": orch_node, "Worker": worker_node},
        )
        agents = {"Orchestrator": orch_agent, "Worker": worker_agent}

        mock_builder = self._make_builder_mock()
        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            self.assembly_service.assemble_graph_async(
                graph, agents, orchestrator_node_registry=None
            )

        self.assertTrue(
            orch_agent.configure_called,
            "configure_orchestrator_service() must be called even without registry",
        )
        # When no registry was provided, node_registry must stay empty (not replaced)
        self.assertEqual(
            orch_agent.node_registry,
            {},
            "node_registry must remain empty when no registry was provided",
        )

    def test_tc007_injection_failure_raises_value_error(self):
        """TC-007 negative: injection failure raises ValueError and increments failure counter."""

        class FailingOrchestratorAgent:
            node_registry: Dict[str, Any] = {}

            def run(self, state):
                return {}

            async def run_async(self, state):
                return {}

            def configure_orchestrator_service(self, service):
                raise RuntimeError("DI failure")

        orch_agent = FailingOrchestratorAgent()
        worker_agent = StubAsyncAgent("Worker")

        orch_node = Node(name="Orchestrator", agent_type="orchestrator")
        orch_node.add_edge("default", "Worker")
        worker_node = Node(name="Worker", agent_type="echo")

        graph = Graph(
            name="failing_orch_graph",
            entry_point="Orchestrator",
            nodes={"Orchestrator": orch_node, "Worker": worker_node},
        )
        agents = {"Orchestrator": orch_agent, "Worker": worker_agent}

        mock_builder = self._make_builder_mock()
        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            with self.assertRaises(ValueError):
                self.assembly_service.assemble_graph_async(
                    graph, agents, orchestrator_node_registry=None
                )

        self.assertEqual(self.assembly_service.injection_stats["injection_failures"], 1)

    # ------------------------------------------------------------------
    # TC-008: Sync assembly remains the default; still binds run
    # ------------------------------------------------------------------

    def test_tc008_sync_assembly_default_path_binds_run(self):
        """TC-008: assemble_graph() must keep binding run even when agents also have run_async.

        Counter-factual: a buggy implementation would accidentally bind run_async
        for the default sync path after adding the async feature.
        """
        graph = self._make_simple_graph("sync_regression_graph")
        agents = self._make_agent_instances(graph)

        add_node_calls: List[tuple] = []
        mock_builder = self._make_builder_mock()
        mock_builder.add_node.side_effect = lambda n, c: add_node_calls.append((n, c))

        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            compiled = self.assembly_service.assemble_graph(
                graph, agents, orchestrator_node_registry=None
            )

        self.assertIsNotNone(compiled)

        for node_name, bound_callable in add_node_calls:
            agent = agents[node_name]
            self.assertEqual(
                bound_callable,
                agent.run,
                f"Sync regression: '{node_name}' must bind run, not run_async",
            )

    def test_tc008_sync_assembly_with_orchestrator_capable_agent(self):
        """TC-008 edge: sync assembly with orchestrator-capable agent compiles unchanged."""
        orch_agent = StubOrchestratorAgent("Orchestrator")
        worker_agent = StubAsyncAgent("Worker")

        orch_node = Node(name="Orchestrator", agent_type="orchestrator")
        orch_node.add_edge("default", "Worker")
        worker_node = Node(name="Worker", agent_type="echo")
        worker_node.add_edge("default", "Orchestrator")

        graph = Graph(
            name="sync_orch_regression_graph",
            entry_point="Orchestrator",
            nodes={"Orchestrator": orch_node, "Worker": worker_node},
        )
        agents = {"Orchestrator": orch_agent, "Worker": worker_agent}

        add_node_calls: List[tuple] = []
        mock_builder = self._make_builder_mock()
        mock_builder.add_node.side_effect = lambda n, c: add_node_calls.append((n, c))

        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            compiled = self.assembly_service.assemble_graph(
                graph, agents, orchestrator_node_registry=None
            )

        self.assertIsNotNone(compiled)
        # Orchestrator node must still bind run (sync), not run_async
        orch_callable = next(c for n, c in add_node_calls if n == "Orchestrator")
        self.assertEqual(
            orch_callable,
            orch_agent.run,
            "Sync path with orchestrator-capable agent must bind run, not run_async",
        )

    def test_tc008_assemble_graph_signature_unchanged(self):
        """TC-008: assemble_graph() must remain callable with the original signature.

        This verifies no new required parameters were added that would break
        existing callers.
        """
        graph = self._make_simple_graph("signature_test_graph")
        agents = self._make_agent_instances(graph)

        mock_builder = self._make_builder_mock()
        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            # Must be callable with positional graph + agent_instances only
            compiled = self.assembly_service.assemble_graph(graph, agents)

        self.assertIsNotNone(compiled)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_single_node_graph_async_binds_correctly(self):
        """Edge: a graph with a single node binds run_async correctly."""
        single_node = Node(name="Solo", agent_type="echo")
        graph = Graph(
            name="single_node_async", entry_point="Solo", nodes={"Solo": single_node}
        )
        agent = StubAsyncAgent("Solo")
        agents = {"Solo": agent}

        add_node_calls: List[tuple] = []
        mock_builder = self._make_builder_mock()
        mock_builder.add_node.side_effect = lambda n, c: add_node_calls.append((n, c))

        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            self.assembly_service.assemble_graph_async(graph, agents)

        self.assertEqual(len(add_node_calls), 1)
        self.assertEqual(add_node_calls[0][1], agent.run_async)

    def test_missing_agent_instance_raises_value_error(self):
        """Edge: missing agent instance raises ValueError on async path."""
        graph = self._make_simple_graph("missing_agent_graph")
        # Deliberately omit End agent
        agents = {"Start": StubAsyncAgent("Start")}

        mock_builder = self._make_builder_mock()
        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            with self.assertRaises(ValueError):
                self.assembly_service.assemble_graph_async(graph, agents)

    def test_sync_only_agent_wrapped_in_executor_for_async_assembly(self):
        """Fallback: assemble_graph_async() wraps sync-only agents in an async executor.

        Counter-factual: a strict guard would raise ValueError, breaking backwards
        compatibility with legacy agents that only implement run().  The fallback
        keeps the event loop responsive and stays compatible with all existing agents.
        """
        import inspect

        class SyncOnlyAgent:
            def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
                return {}

        single_node = Node(name="Solo", agent_type="echo")
        graph = Graph(
            name="sync_only_fallback_graph",
            entry_point="Solo",
            nodes={"Solo": single_node},
        )
        agent_instance = SyncOnlyAgent()
        agents = {"Solo": agent_instance}

        mock_builder = self._make_builder_mock()
        self.mock_state_schema_builder.get_schema_for_graph.return_value = dict

        with patch(
            "agentmap.services.graph.graph_assembly_service.StateGraph"
        ) as mock_sg_cls:
            mock_sg_cls.return_value = mock_builder
            self.assembly_service.assemble_graph_async(graph, agents)

        # Verify add_node was called and the callable registered is a coroutine function
        mock_builder.add_node.assert_called_once()
        _name, registered_callable = mock_builder.add_node.call_args[0]
        self.assertEqual(_name, "Solo")
        self.assertTrue(
            inspect.iscoroutinefunction(registered_callable),
            "Sync-only agent must be wrapped in an async callable for async graph assembly",
        )


if __name__ == "__main__":
    unittest.main()
