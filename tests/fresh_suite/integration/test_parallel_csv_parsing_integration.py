"""
Parallel CSV Parsing Integration Tests.

Test CSV parsing for parallel agent execution with pipe-delimited targets.
Validates that CSVGraphParserService correctly parses pipe syntax and creates
appropriate NodeSpec structures with List[str] for parallel edges.

Test Coverage:
- Pipe-delimited target parsing (A|B|C)
- Whitespace handling
- Edge case scenarios (trailing pipes, empty elements)
- Backward compatibility with single targets
- Multiple edge types with parallel targets
"""

import unittest
from pathlib import Path
from typing import List

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from tests.fresh_suite.integration.test_data_factories import IntegrationTestDataManager
from agentmap.models.graph_spec import GraphSpec, NodeSpec


class TestParallelCSVParsingIntegration(BaseIntegrationTest):
    """Integration tests for CSV parsing with parallel targets."""

    def setup_services(self):
        """Initialize services for parallel CSV parsing tests."""
        super().setup_services()

        self.csv_parser_service = self.container.csv_graph_parser_service()
        self.test_data_manager = IntegrationTestDataManager(Path(self.temp_dir))

        self.assert_service_created(self.csv_parser_service, "CSVGraphParserService")

    # =============================================================================
    # Basic Parallel Target Parsing
    # =============================================================================

    def test_simple_parallel_targets_parsing(self):
        """Test parsing simple pipe-delimited parallel targets."""
        print("\n=== Testing Simple Parallel Targets Parsing ===")

        csv_content = """GraphName,Node,AgentType,Edge,Success_Next,Failure_Next
ParallelTest,Start,input,ProcessA|ProcessB|ProcessC,,
ParallelTest,ProcessA,echo,End,,
ParallelTest,ProcessB,echo,End,,
ParallelTest,ProcessC,echo,End,,
ParallelTest,End,output,,"""

        csv_path = self._create_csv(csv_content, "simple_parallel.csv")
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        # Verify graph structure
        self.assertIn("ParallelTest", graph_spec.graphs)
        nodes = graph_spec.graphs["ParallelTest"]

        # Find Start node
        start_node = next(n for n in nodes if n.name == "Start")

        # Verify parallel edge is parsed as List[str]
        self.assertIsInstance(start_node.edge, list, "Parallel edge should be list")
        self.assertEqual(len(start_node.edge), 3, "Should have 3 parallel targets")
        self.assertEqual(set(start_node.edge), {"ProcessA", "ProcessB", "ProcessC"})

        # Verify helper methods
        self.assertTrue(start_node.is_parallel_edge("edge"), "Should detect parallel edge")
        targets = start_node.get_edge_targets("edge")
        self.assertEqual(len(targets), 3, "Should return 3 targets")

        print("✅ Simple parallel targets parsed correctly")

    def test_single_target_remains_string(self):
        """Test that single targets remain as strings (backward compatibility)."""
        print("\n=== Testing Single Target Backward Compatibility ===")

        csv_content = """GraphName,Node,AgentType,Edge
SingleTest,Start,input,End
SingleTest,End,output,"""

        csv_path = self._create_csv(csv_content, "single_target.csv")
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        nodes = graph_spec.graphs["SingleTest"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Single target should be string, not list
        self.assertIsInstance(start_node.edge, str, "Single target should be string")
        self.assertEqual(start_node.edge, "End")
        self.assertFalse(start_node.is_parallel_edge("edge"), "Should not detect parallel")

        print("✅ Single target backward compatibility verified")

    def test_whitespace_handling(self):
        """Test that whitespace around pipe-separated targets is trimmed."""
        print("\n=== Testing Whitespace Handling ===")

        csv_content = """GraphName,Node,AgentType,Edge
WhitespaceTest,Start,input,  ProcessA  |  ProcessB  |  ProcessC
WhitespaceTest,ProcessA,echo,End
WhitespaceTest,ProcessB,echo,End
WhitespaceTest,ProcessC,echo,End
WhitespaceTest,End,output,"""

        csv_path = self._create_csv(csv_content, "whitespace_test.csv")
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        nodes = graph_spec.graphs["WhitespaceTest"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Verify whitespace is trimmed
        self.assertIsInstance(start_node.edge, list)
        self.assertEqual(set(start_node.edge), {"ProcessA", "ProcessB", "ProcessC"})

        # Ensure no leading/trailing spaces in targets
        for target in start_node.edge:
            self.assertEqual(target, target.strip(), f"Target '{target}' should be trimmed")

        print("✅ Whitespace handling verified")

    # =============================================================================
    # Edge Case Scenarios
    # =============================================================================

    def test_trailing_pipe_handling(self):
        """Test handling of trailing pipe characters."""
        print("\n=== Testing Trailing Pipe Handling ===")

        csv_content = """GraphName,Node,AgentType,Edge
TrailingPipeTest,Start,input,ProcessA|
TrailingPipeTest,ProcessA,echo,End
TrailingPipeTest,End,output,"""

        csv_path = self._create_csv(csv_content, "trailing_pipe.csv")
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        nodes = graph_spec.graphs["TrailingPipeTest"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Trailing pipe should result in single target (not list)
        self.assertIsInstance(start_node.edge, str, "Trailing pipe should yield string")
        self.assertEqual(start_node.edge, "ProcessA")

        print("✅ Trailing pipe handled correctly")

    def test_empty_middle_elements(self):
        """Test handling of empty elements between pipes."""
        print("\n=== Testing Empty Middle Elements ===")

        csv_content = """GraphName,Node,AgentType,Edge
EmptyElementTest,Start,input,ProcessA||ProcessC
EmptyElementTest,ProcessA,echo,End
EmptyElementTest,ProcessC,echo,End
EmptyElementTest,End,output,"""

        csv_path = self._create_csv(csv_content, "empty_elements.csv")
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        nodes = graph_spec.graphs["EmptyElementTest"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Empty elements should be filtered out
        self.assertIsInstance(start_node.edge, list)
        self.assertEqual(len(start_node.edge), 2, "Empty elements should be filtered")
        self.assertEqual(set(start_node.edge), {"ProcessA", "ProcessC"})

        print("✅ Empty elements filtered correctly")

    # =============================================================================
    # Multiple Edge Types
    # =============================================================================

    def test_parallel_success_next(self):
        """Test parallel targets in Success_Next field."""
        print("\n=== Testing Parallel Success_Next ===")

        csv_content = """GraphName,Node,AgentType,Success_Next,Failure_Next
SuccessParallel,Start,validator,ProcessA|ProcessB|ProcessC,FailureHandler
SuccessParallel,ProcessA,echo,End,
SuccessParallel,ProcessB,echo,End,
SuccessParallel,ProcessC,echo,End,
SuccessParallel,FailureHandler,echo,End,
SuccessParallel,End,output,,"""

        csv_path = self._create_csv(csv_content, "success_parallel.csv")
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        nodes = graph_spec.graphs["SuccessParallel"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Verify Success_Next is parallel
        self.assertIsInstance(start_node.success_next, list)
        self.assertEqual(len(start_node.success_next), 3)
        self.assertEqual(set(start_node.success_next), {"ProcessA", "ProcessB", "ProcessC"})

        # Verify Failure_Next is single target
        self.assertIsInstance(start_node.failure_next, str)
        self.assertEqual(start_node.failure_next, "FailureHandler")

        # Verify helper methods
        self.assertTrue(start_node.is_parallel_edge("success_next"))
        self.assertFalse(start_node.is_parallel_edge("failure_next"))

        print("✅ Parallel Success_Next parsed correctly")

    def test_parallel_failure_next(self):
        """Test parallel targets in Failure_Next field."""
        print("\n=== Testing Parallel Failure_Next ===")

        csv_content = """GraphName,Node,AgentType,Success_Next,Failure_Next
FailureParallel,Start,validator,SuccessHandler,ErrorA|ErrorB|ErrorC
FailureParallel,SuccessHandler,echo,End,
FailureParallel,ErrorA,echo,End,
FailureParallel,ErrorB,echo,End,
FailureParallel,ErrorC,echo,End,
FailureParallel,End,output,,"""

        csv_path = self._create_csv(csv_content, "failure_parallel.csv")
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        nodes = graph_spec.graphs["FailureParallel"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Verify Failure_Next is parallel
        self.assertIsInstance(start_node.failure_next, list)
        self.assertEqual(len(start_node.failure_next), 3)
        self.assertEqual(set(start_node.failure_next), {"ErrorA", "ErrorB", "ErrorC"})

        # Verify Success_Next is single target
        self.assertIsInstance(start_node.success_next, str)
        self.assertEqual(start_node.success_next, "SuccessHandler")

        print("✅ Parallel Failure_Next parsed correctly")

    def test_both_edges_parallel(self):
        """Test both Success_Next and Failure_Next with parallel targets."""
        print("\n=== Testing Both Edges Parallel ===")

        csv_content = """GraphName,Node,AgentType,Success_Next,Failure_Next
BothParallel,Start,validator,SuccessA|SuccessB,ErrorA|ErrorB
BothParallel,SuccessA,echo,End,
BothParallel,SuccessB,echo,End,
BothParallel,ErrorA,echo,End,
BothParallel,ErrorB,echo,End,
BothParallel,End,output,,"""

        csv_path = self._create_csv(csv_content, "both_parallel.csv")
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        nodes = graph_spec.graphs["BothParallel"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Both should be parallel
        self.assertIsInstance(start_node.success_next, list)
        self.assertIsInstance(start_node.failure_next, list)

        self.assertEqual(set(start_node.success_next), {"SuccessA", "SuccessB"})
        self.assertEqual(set(start_node.failure_next), {"ErrorA", "ErrorB"})

        self.assertTrue(start_node.is_parallel_edge("success_next"))
        self.assertTrue(start_node.is_parallel_edge("failure_next"))

        print("✅ Both edges parallel parsed correctly")

    # =============================================================================
    # Complex Scenarios
    # =============================================================================

    def test_mixed_parallel_sequential(self):
        """Test graph with mix of parallel and sequential edges."""
        print("\n=== Testing Mixed Parallel/Sequential Graph ===")

        csv_content = """GraphName,Node,AgentType,Edge
MixedGraph,Start,input,Sequential1
MixedGraph,Sequential1,echo,ParallelFanOut
MixedGraph,ParallelFanOut,distributor,ProcessA|ProcessB|ProcessC
MixedGraph,ProcessA,echo,Sequential2
MixedGraph,ProcessB,echo,Sequential2
MixedGraph,ProcessC,echo,Sequential2
MixedGraph,Sequential2,echo,End
MixedGraph,End,output,"""

        csv_path = self._create_csv(csv_content, "mixed_graph.csv")
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        nodes = graph_spec.graphs["MixedGraph"]
        nodes_by_name = {n.name: n for n in nodes}

        # Verify sequential edges are strings
        self.assertIsInstance(nodes_by_name["Start"].edge, str)
        self.assertEqual(nodes_by_name["Start"].edge, "Sequential1")

        # Verify parallel edge is list
        self.assertIsInstance(nodes_by_name["ParallelFanOut"].edge, list)
        self.assertEqual(len(nodes_by_name["ParallelFanOut"].edge), 3)

        # Verify convergence is sequential
        self.assertIsInstance(nodes_by_name["ProcessA"].edge, str)
        self.assertEqual(nodes_by_name["ProcessA"].edge, "Sequential2")

        print("✅ Mixed parallel/sequential graph parsed correctly")

    def test_multiple_parallel_sections(self):
        """Test graph with multiple parallel sections."""
        print("\n=== Testing Multiple Parallel Sections ===")

        csv_content = """GraphName,Node,AgentType,Edge
MultiParallel,Start,input,FirstParallel
MultiParallel,FirstParallel,distributor,A1|A2|A3
MultiParallel,A1,echo,Consolidate1
MultiParallel,A2,echo,Consolidate1
MultiParallel,A3,echo,Consolidate1
MultiParallel,Consolidate1,aggregator,SecondParallel
MultiParallel,SecondParallel,distributor,B1|B2
MultiParallel,B1,echo,End
MultiParallel,B2,echo,End
MultiParallel,End,output,"""

        csv_path = self._create_csv(csv_content, "multi_parallel.csv")
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        nodes = graph_spec.graphs["MultiParallel"]
        nodes_by_name = {n.name: n for n in nodes}

        # First parallel section
        self.assertIsInstance(nodes_by_name["FirstParallel"].edge, list)
        self.assertEqual(len(nodes_by_name["FirstParallel"].edge), 3)

        # Second parallel section
        self.assertIsInstance(nodes_by_name["SecondParallel"].edge, list)
        self.assertEqual(len(nodes_by_name["SecondParallel"].edge), 2)

        print("✅ Multiple parallel sections parsed correctly")

    # =============================================================================
    # Helper Methods
    # =============================================================================

    def _create_csv(self, content: str, filename: str) -> Path:
        """Create a test CSV file with given content."""
        csv_path = Path(self.temp_dir) / "csv_data" / filename
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text(content, encoding='utf-8')
        return csv_path


if __name__ == '__main__':
    unittest.main()
