"""
Parallel Validation Integration Tests.

Test validation and error handling for parallel agent execution.
Validates that the system correctly handles edge cases, errors,
and malformed parallel syntax.

Test Coverage:
- Validation for nonexistent parallel targets
- Error handling for malformed parallel syntax
- Warning for output field conflicts (if applicable)
- Edge case validation
"""

import unittest
from pathlib import Path

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest


class TestParallelValidationIntegration(BaseIntegrationTest):
    """Integration tests for parallel execution validation."""

    def setup_services(self):
        """Initialize services for validation tests."""
        super().setup_services()

        self.csv_parser_service = self.container.csv_graph_parser_service()
        self.graph_bundle_service = self.container.graph_bundle_service()

        self.assert_service_created(self.csv_parser_service, "CSVGraphParserService")
        self.assert_service_created(self.graph_bundle_service, "GraphBundleService")

    # =============================================================================
    # Nonexistent Target Validation
    # =============================================================================

    def test_nonexistent_parallel_target_detection(self):
        """Test detection of nonexistent targets in parallel edges."""
        print("\n=== Testing Nonexistent Parallel Target Detection ===")

        csv_content = """GraphName,Node,AgentType,Edge
NonexistentTarget,Start,input,ProcessA|ProcessB|NonexistentNode
NonexistentTarget,ProcessA,echo,End
NonexistentTarget,ProcessB,echo,End
NonexistentTarget,End,output,"""

        csv_path = self._create_csv(csv_content, "nonexistent_target.csv")

        # Parse CSV - should succeed (validation happens later in pipeline)
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        self.assertIsNotNone(graph_spec)

        # Verify the nonexistent target is in the parsed data
        nodes = graph_spec.graphs["NonexistentTarget"]
        start_node = next(n for n in nodes if n.name == "Start")

        targets = start_node.get_edge_targets("edge")
        self.assertIn("NonexistentNode", targets)

        # Note: Actual validation of nonexistent targets would occur during
        # graph assembly or execution, not during CSV parsing

        print("✅ Nonexistent target parsed (validation deferred)")

    def test_all_targets_nonexistent(self):
        """Test case where all parallel targets are nonexistent."""
        print("\n=== Testing All Targets Nonexistent ===")

        csv_content = """GraphName,Node,AgentType,Edge
AllNonexistent,Start,input,NodeA|NodeB|NodeC
AllNonexistent,End,output,"""

        csv_path = self._create_csv(csv_content, "all_nonexistent.csv")

        # Parse should succeed
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        self.assertIsNotNone(graph_spec)

        # All targets are parsed (validation happens later)
        nodes = graph_spec.graphs["AllNonexistent"]
        start_node = next(n for n in nodes if n.name == "Start")
        targets = start_node.get_edge_targets("edge")

        self.assertEqual(set(targets), {"NodeA", "NodeB", "NodeC"})

        print("✅ All nonexistent targets parsed")

    # =============================================================================
    # Malformed Syntax Handling
    # =============================================================================

    def test_only_pipes_syntax(self):
        """Test handling of edge value with only pipes."""
        print("\n=== Testing Only Pipes Syntax ===")

        csv_content = """GraphName,Node,AgentType,Edge
OnlyPipes,Start,input,|||
OnlyPipes,End,output,"""

        csv_path = self._create_csv(csv_content, "only_pipes.csv")

        # Parse CSV
        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)

        nodes = graph_spec.graphs["OnlyPipes"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Only pipes should result in None or empty edge
        # (implementation filters out empty elements)
        self.assertIsNone(start_node.edge, "Only pipes should yield None edge")

        print("✅ Only pipes handled correctly")

    def test_leading_pipe_syntax(self):
        """Test handling of leading pipe character."""
        print("\n=== Testing Leading Pipe Syntax ===")

        csv_content = """GraphName,Node,AgentType,Edge
LeadingPipe,Start,input,|ProcessA|ProcessB
LeadingPipe,ProcessA,echo,End
LeadingPipe,ProcessB,echo,End
LeadingPipe,End,output,"""

        csv_path = self._create_csv(csv_content, "leading_pipe.csv")

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        nodes = graph_spec.graphs["LeadingPipe"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Leading pipe should be filtered out
        targets = start_node.get_edge_targets("edge")
        self.assertEqual(set(targets), {"ProcessA", "ProcessB"})

        print("✅ Leading pipe filtered correctly")

    def test_multiple_consecutive_pipes(self):
        """Test handling of multiple consecutive pipes."""
        print("\n=== Testing Multiple Consecutive Pipes ===")

        csv_content = """GraphName,Node,AgentType,Edge
ConsecutivePipes,Start,input,ProcessA|||ProcessB
ConsecutivePipes,ProcessA,echo,End
ConsecutivePipes,ProcessB,echo,End
ConsecutivePipes,End,output,"""

        csv_path = self._create_csv(csv_content, "consecutive_pipes.csv")

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        nodes = graph_spec.graphs["ConsecutivePipes"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Empty elements should be filtered
        targets = start_node.get_edge_targets("edge")
        self.assertEqual(set(targets), {"ProcessA", "ProcessB"})

        print("✅ Consecutive pipes filtered correctly")

    # =============================================================================
    # Edge Cases
    # =============================================================================

    def test_single_character_node_names(self):
        """Test parallel targets with single-character node names."""
        print("\n=== Testing Single Character Node Names ===")

        csv_content = """GraphName,Node,AgentType,Edge
SingleChar,Start,input,A|B|C
SingleChar,A,echo,End
SingleChar,B,echo,End
SingleChar,C,echo,End
SingleChar,End,output,"""

        csv_path = self._create_csv(csv_content, "single_char.csv")

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        nodes = graph_spec.graphs["SingleChar"]
        start_node = next(n for n in nodes if n.name == "Start")

        targets = start_node.get_edge_targets("edge")
        self.assertEqual(set(targets), {"A", "B", "C"})

        print("✅ Single character node names work correctly")

    def test_node_names_with_special_characters(self):
        """Test parallel targets with special characters in names."""
        print("\n=== Testing Node Names with Special Characters ===")

        csv_content = """GraphName,Node,AgentType,Edge
SpecialChars,Start,input,Process_A|Process-B|Process.C
SpecialChars,Process_A,echo,End
SpecialChars,Process-B,echo,End
SpecialChars,Process.C,echo,End
SpecialChars,End,output,"""

        csv_path = self._create_csv(csv_content, "special_chars.csv")

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        nodes = graph_spec.graphs["SpecialChars"]
        start_node = next(n for n in nodes if n.name == "Start")

        targets = start_node.get_edge_targets("edge")
        self.assertEqual(set(targets), {"Process_A", "Process-B", "Process.C"})

        print("✅ Special characters in node names work correctly")

    def test_very_long_parallel_list(self):
        """Test parallel edge with many targets."""
        print("\n=== Testing Very Long Parallel List ===")

        # Create CSV with 10 parallel targets
        nodes_csv = ["LongList,Start,input," + "|".join([f"Process{i}" for i in range(10)])]
        for i in range(10):
            nodes_csv.append(f"LongList,Process{i},echo,End")
        nodes_csv.append("LongList,End,output,")

        csv_content = "GraphName,Node,AgentType,Edge\n" + "\n".join(nodes_csv)

        csv_path = self._create_csv(csv_content, "long_list.csv")

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        nodes = graph_spec.graphs["LongList"]
        start_node = next(n for n in nodes if n.name == "Start")

        targets = start_node.get_edge_targets("edge")
        self.assertEqual(len(targets), 10, "Should have 10 parallel targets")
        self.assertEqual(set(targets), {f"Process{i}" for i in range(10)})

        print("✅ Long parallel list parsed correctly")

    # =============================================================================
    # Duplicate Target Detection
    # =============================================================================

    def test_duplicate_targets_in_parallel_list(self):
        """Test handling of duplicate targets in parallel edge."""
        print("\n=== Testing Duplicate Targets ===")

        csv_content = """GraphName,Node,AgentType,Edge
Duplicates,Start,input,ProcessA|ProcessB|ProcessA
Duplicates,ProcessA,echo,End
Duplicates,ProcessB,echo,End
Duplicates,End,output,"""

        csv_path = self._create_csv(csv_content, "duplicates.csv")

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        nodes = graph_spec.graphs["Duplicates"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Duplicates are currently allowed (de-duplication would be enhancement)
        targets = start_node.get_edge_targets("edge")

        # Current behavior: duplicates preserved in list
        # Could be enhanced to remove duplicates in future
        print(f"Targets with duplicates: {targets}")
        self.assertIn("ProcessA", targets)
        self.assertIn("ProcessB", targets)

        print("✅ Duplicate targets parsed (de-duplication could be enhancement)")

    # =============================================================================
    # Empty and Whitespace Cases
    # =============================================================================

    def test_whitespace_only_targets(self):
        """Test handling of whitespace-only targets."""
        print("\n=== Testing Whitespace-Only Targets ===")

        csv_content = """GraphName,Node,AgentType,Edge
WhitespaceOnly,Start,input,ProcessA|   |ProcessB
WhitespaceOnly,ProcessA,echo,End
WhitespaceOnly,ProcessB,echo,End
WhitespaceOnly,End,output,"""

        csv_path = self._create_csv(csv_content, "whitespace_only.csv")

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        nodes = graph_spec.graphs["WhitespaceOnly"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Whitespace-only elements should be filtered
        targets = start_node.get_edge_targets("edge")
        self.assertEqual(set(targets), {"ProcessA", "ProcessB"})

        print("✅ Whitespace-only targets filtered correctly")

    def test_empty_edge_value(self):
        """Test handling of completely empty edge value."""
        print("\n=== Testing Empty Edge Value ===")

        csv_content = """GraphName,Node,AgentType,Edge
EmptyEdge,Start,input,
EmptyEdge,End,output,"""

        csv_path = self._create_csv(csv_content, "empty_edge.csv")

        graph_spec = self.csv_parser_service.parse_csv_to_graph_spec(csv_path)
        nodes = graph_spec.graphs["EmptyEdge"]
        start_node = next(n for n in nodes if n.name == "Start")

        # Empty edge should be None
        self.assertIsNone(start_node.edge)

        print("✅ Empty edge value handled correctly")

    # =============================================================================
    # Helper Methods
    # =============================================================================

    def _create_csv(self, content: str, filename: str) -> Path:
        """Create a test CSV file."""
        csv_path = Path(self.temp_dir) / "csv_data" / filename
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text(content, encoding='utf-8')
        return csv_path


if __name__ == '__main__':
    unittest.main()
