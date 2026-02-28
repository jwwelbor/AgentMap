"""
Parallel Graph Assembly Integration Tests.

Test graph assembly for parallel agent execution with routing functions.
Validates that GraphAssemblyService correctly creates LangGraph routing
functions that return List[str] for parallel execution.

Test Coverage:
- Parallel routing function generation
- LangGraph conditional edges with list returns
- Mixed single/parallel routing
- Backward compatibility with single-target edges
"""

import unittest
from typing import Any, Dict

from agentmap.models.graph import Graph
from agentmap.models.node import Node
from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest


class TestParallelGraphAssemblyIntegration(BaseIntegrationTest):
    """Integration tests for graph assembly with parallel routing."""

    def setup_services(self):
        """Initialize services for parallel graph assembly tests."""
        super().setup_services()

        self.graph_assembly_service = self.container.graph_assembly_service()
        self.graph_factory_service = self.container.graph_factory_service()
        self.agent_factory_service = self.container.agent_factory_service()

        self.assert_service_created(self.graph_assembly_service, "GraphAssemblyService")
        self.assert_service_created(self.graph_factory_service, "GraphFactoryService")
        self.assert_service_created(self.agent_factory_service, "AgentFactoryService")

    # =============================================================================
    # Basic Parallel Routing
    # =============================================================================

    def test_simple_parallel_default_edge(self):
        """Test assembly with simple parallel default edge."""
        print("\n=== Testing Simple Parallel Default Edge ===")

        # Create graph with parallel default edge
        start_node = Node(name="Start", agent_type="input")
        start_node.add_edge("default", ["ProcessA", "ProcessB", "ProcessC"])

        graph = Graph(
            name="ParallelDefault",
            entry_point="Start",
            nodes={
                "Start": start_node,
                "ProcessA": Node(name="ProcessA", agent_type="echo"),
                "ProcessB": Node(name="ProcessB", agent_type="echo"),
                "ProcessC": Node(name="ProcessC", agent_type="echo"),
                "End": Node(name="End", agent_type="output"),
            },
        )

        # Create agent instances
        agent_instances = self._create_agent_instances(graph)

        # Assemble graph
        compiled_graph = self.graph_assembly_service.assemble_graph(
            graph, agent_instances
        )

        # Verify compilation succeeded
        self.assertIsNotNone(compiled_graph, "Graph should compile successfully")

        print("✅ Parallel default edge assembled correctly")

    def test_parallel_success_edge(self):
        """Test assembly with parallel success edge."""
        print("\n=== Testing Parallel Success Edge ===")

        start_node = Node(name="Start", agent_type="validator")
        start_node.add_edge("success", ["ProcessA", "ProcessB", "ProcessC"])
        start_node.add_edge("failure", "ErrorHandler")

        graph = Graph(
            name="ParallelSuccess",
            entry_point="Start",
            nodes={
                "Start": start_node,
                "ProcessA": Node(name="ProcessA", agent_type="echo"),
                "ProcessB": Node(name="ProcessB", agent_type="echo"),
                "ProcessC": Node(name="ProcessC", agent_type="echo"),
                "ErrorHandler": Node(name="ErrorHandler", agent_type="echo"),
                "End": Node(name="End", agent_type="output"),
            },
        )

        agent_instances = self._create_agent_instances(graph)
        compiled_graph = self.graph_assembly_service.assemble_graph(
            graph, agent_instances
        )

        self.assertIsNotNone(compiled_graph)

        print("✅ Parallel success edge assembled correctly")

    def test_parallel_failure_edge(self):
        """Test assembly with parallel failure edge."""
        print("\n=== Testing Parallel Failure Edge ===")

        start_node = Node(name="Start", agent_type="validator")
        start_node.add_edge("success", "SuccessHandler")
        start_node.add_edge("failure", ["ErrorA", "ErrorB", "ErrorC"])

        graph = Graph(
            name="ParallelFailure",
            entry_point="Start",
            nodes={
                "Start": start_node,
                "SuccessHandler": Node(name="SuccessHandler", agent_type="echo"),
                "ErrorA": Node(name="ErrorA", agent_type="echo"),
                "ErrorB": Node(name="ErrorB", agent_type="echo"),
                "ErrorC": Node(name="ErrorC", agent_type="echo"),
                "End": Node(name="End", agent_type="output"),
            },
        )

        agent_instances = self._create_agent_instances(graph)
        compiled_graph = self.graph_assembly_service.assemble_graph(
            graph, agent_instances
        )

        self.assertIsNotNone(compiled_graph)

        print("✅ Parallel failure edge assembled correctly")

    def test_both_edges_parallel(self):
        """Test assembly with both success and failure edges parallel."""
        print("\n=== Testing Both Edges Parallel ===")

        start_node = Node(name="Start", agent_type="validator")
        start_node.add_edge("success", ["SuccessA", "SuccessB"])
        start_node.add_edge("failure", ["ErrorA", "ErrorB"])

        graph = Graph(
            name="BothParallel",
            entry_point="Start",
            nodes={
                "Start": start_node,
                "SuccessA": Node(name="SuccessA", agent_type="echo"),
                "SuccessB": Node(name="SuccessB", agent_type="echo"),
                "ErrorA": Node(name="ErrorA", agent_type="echo"),
                "ErrorB": Node(name="ErrorB", agent_type="echo"),
                "End": Node(name="End", agent_type="output"),
            },
        )

        agent_instances = self._create_agent_instances(graph)
        compiled_graph = self.graph_assembly_service.assemble_graph(
            graph, agent_instances
        )

        self.assertIsNotNone(compiled_graph)

        print("✅ Both edges parallel assembled correctly")

    # =============================================================================
    # Backward Compatibility
    # =============================================================================

    def test_single_target_backward_compatibility(self):
        """Test that single-target edges still work (backward compatibility)."""
        print("\n=== Testing Single Target Backward Compatibility ===")

        start_node = Node(name="Start", agent_type="input")
        start_node.add_edge("default", "Process")

        process_node = Node(name="Process", agent_type="echo")
        process_node.add_edge("default", "End")

        graph = Graph(
            name="SingleTarget",
            entry_point="Start",
            nodes={
                "Start": start_node,
                "Process": process_node,
                "End": Node(name="End", agent_type="output"),
            },
        )

        agent_instances = self._create_agent_instances(graph)
        compiled_graph = self.graph_assembly_service.assemble_graph(
            graph, agent_instances
        )

        self.assertIsNotNone(compiled_graph)

        print("✅ Single target backward compatibility verified")

    def test_mixed_single_and_parallel_edges(self):
        """Test graph with mix of single and parallel edges."""
        print("\n=== Testing Mixed Single/Parallel Edges ===")

        start_node = Node(name="Start", agent_type="input")
        start_node.add_edge("default", "Sequential1")

        sequential1_node = Node(name="Sequential1", agent_type="echo")
        sequential1_node.add_edge("default", ["ParallelA", "ParallelB", "ParallelC"])

        parallel_a = Node(name="ParallelA", agent_type="echo")
        parallel_a.add_edge("default", "End")

        graph = Graph(
            name="MixedEdges",
            entry_point="Start",
            nodes={
                "Start": start_node,
                "Sequential1": sequential1_node,
                "ParallelA": parallel_a,
                "ParallelB": Node(name="ParallelB", agent_type="echo"),
                "ParallelC": Node(name="ParallelC", agent_type="echo"),
                "End": Node(name="End", agent_type="output"),
            },
        )

        agent_instances = self._create_agent_instances(graph)
        compiled_graph = self.graph_assembly_service.assemble_graph(
            graph, agent_instances
        )

        self.assertIsNotNone(compiled_graph)

        print("✅ Mixed single/parallel edges assembled correctly")

    # =============================================================================
    # Complex Scenarios
    # =============================================================================

    def test_multiple_parallel_sections(self):
        """Test graph with multiple parallel sections."""
        print("\n=== Testing Multiple Parallel Sections ===")

        start_node = Node(name="Start", agent_type="input")
        start_node.add_edge("default", ["A1", "A2", "A3"])

        consolidate1 = Node(name="Consolidate1", agent_type="aggregator")
        consolidate1.add_edge("default", ["B1", "B2"])

        graph = Graph(
            name="MultiParallel",
            entry_point="Start",
            nodes={
                "Start": start_node,
                "A1": Node(name="A1", agent_type="echo"),
                "A2": Node(name="A2", agent_type="echo"),
                "A3": Node(name="A3", agent_type="echo"),
                "Consolidate1": consolidate1,
                "B1": Node(name="B1", agent_type="echo"),
                "B2": Node(name="B2", agent_type="echo"),
                "End": Node(name="End", agent_type="output"),
            },
        )

        agent_instances = self._create_agent_instances(graph)
        compiled_graph = self.graph_assembly_service.assemble_graph(
            graph, agent_instances
        )

        self.assertIsNotNone(compiled_graph)

        print("✅ Multiple parallel sections assembled correctly")

    def test_nested_conditional_with_parallel(self):
        """Test nested conditional routing with parallel edges."""
        print("\n=== Testing Nested Conditional with Parallel ===")

        validator1 = Node(name="Validator1", agent_type="validator")
        validator1.add_edge("success", ["ProcessA", "ProcessB"])
        validator1.add_edge("failure", "ErrorHandler")

        validator2 = Node(name="Validator2", agent_type="validator")
        validator2.add_edge("success", "SuccessHandler")
        validator2.add_edge("failure", ["ErrorA", "ErrorB"])

        graph = Graph(
            name="NestedConditional",
            entry_point="Start",
            nodes={
                "Start": Node(name="Start", agent_type="input"),
                "Validator1": validator1,
                "ProcessA": Node(name="ProcessA", agent_type="echo"),
                "ProcessB": Node(name="ProcessB", agent_type="echo"),
                "ErrorHandler": Node(name="ErrorHandler", agent_type="echo"),
                "Validator2": validator2,
                "SuccessHandler": Node(name="SuccessHandler", agent_type="echo"),
                "ErrorA": Node(name="ErrorA", agent_type="echo"),
                "ErrorB": Node(name="ErrorB", agent_type="echo"),
                "End": Node(name="End", agent_type="output"),
            },
        )

        agent_instances = self._create_agent_instances(graph)
        compiled_graph = self.graph_assembly_service.assemble_graph(
            graph, agent_instances
        )

        self.assertIsNotNone(compiled_graph)

        print("✅ Nested conditional with parallel assembled correctly")

    # =============================================================================
    # Helper Methods
    # =============================================================================

    def _create_agent_instances(self, graph: Graph) -> Dict[str, Any]:
        """Create stub agent instances for testing graph assembly.

        For graph assembly tests, we only need agent instances with a .run() method.
        The actual agent logic is not tested here.
        """
        agent_instances = {}

        class StubAgent:
            """Minimal stub agent for graph assembly testing."""

            def __init__(self, name):
                self.name = name

            def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
                """Stub run method that returns a simple result."""
                return {"output": f"Result from {self.name}"}

        for node_name, node in graph.nodes.items():
            agent_instances[node_name] = StubAgent(node_name)

        return agent_instances


if __name__ == "__main__":
    unittest.main()
