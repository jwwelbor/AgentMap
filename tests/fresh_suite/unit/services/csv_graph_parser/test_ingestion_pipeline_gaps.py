"""
Unit tests for ingestion pipeline gap resolutions.

Tests cover:
1. Output_Field validator support for pipe-separated multi-output fields
2. Edge target validation (cross-references against defined nodes)
3. Duplicate node name detection within graphs
4. Orphan node detection (isolated nodes with no edges)
5. AgentType validation with typo suggestions
6. CSV hash computation with content return
"""

import tempfile
import unittest
from io import StringIO
from pathlib import Path

import pandas as pd

from agentmap.models.validation.csv_row_model import CSVRowModel
from agentmap.models.validation.validation_models import ValidationResult
from agentmap.services.csv_graph_parser.column_config import CSVColumnConfig
from agentmap.services.csv_graph_parser.validators import CSVStructureValidator
from tests.utils.mock_service_factory import MockServiceFactory


def _make_df(csv_text: str) -> pd.DataFrame:
    """Helper to create a DataFrame from CSV text."""
    return pd.read_csv(StringIO(csv_text))


def _make_validator():
    """Helper to create a CSVStructureValidator instance."""
    mock_factory = MockServiceFactory()
    logger = mock_factory.create_mock_logging_service()
    column_config = CSVColumnConfig()
    return CSVStructureValidator(column_config, logger)


class TestOutputFieldMultiOutput(unittest.TestCase):
    """Test that Output_Field validator supports pipe-separated multi-output fields."""

    def test_single_output_field_valid(self):
        """Single output field should pass validation."""
        model = CSVRowModel(GraphName="test", Node="node1", Output_Field="summary")
        self.assertEqual(model.Output_Field, "summary")

    def test_pipe_separated_multi_output_valid(self):
        """Pipe-separated output fields should pass validation."""
        model = CSVRowModel(
            GraphName="test", Node="node1", Output_Field="summary|analysis|score"
        )
        self.assertEqual(model.Output_Field, "summary|analysis|score")

    def test_pipe_separated_with_underscores(self):
        """Multi-output fields with underscores should pass."""
        model = CSVRowModel(
            GraphName="test", Node="node1", Output_Field="final_summary|raw_data"
        )
        self.assertEqual(model.Output_Field, "final_summary|raw_data")

    def test_pipe_separated_with_dashes(self):
        """Multi-output fields with dashes should pass."""
        model = CSVRowModel(
            GraphName="test", Node="node1", Output_Field="my-output|other-output"
        )
        self.assertEqual(model.Output_Field, "my-output|other-output")

    def test_pipe_separated_trims_whitespace(self):
        """Whitespace around pipes should be trimmed."""
        model = CSVRowModel(
            GraphName="test", Node="node1", Output_Field="summary | analysis | score"
        )
        self.assertEqual(model.Output_Field, "summary|analysis|score")

    def test_invalid_field_name_in_multi_output(self):
        """Invalid characters in any field should raise an error."""
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            CSVRowModel(GraphName="test", Node="node1", Output_Field="summary|an@lysis")

    def test_none_output_field(self):
        """None output field should pass validation."""
        model = CSVRowModel(GraphName="test", Node="node1", Output_Field=None)
        self.assertIsNone(model.Output_Field)

    def test_trailing_pipe_handled(self):
        """Trailing pipe should be handled gracefully."""
        model = CSVRowModel(
            GraphName="test", Node="node1", Output_Field="summary|analysis|"
        )
        self.assertEqual(model.Output_Field, "summary|analysis")


class TestEdgeTargetValidation(unittest.TestCase):
    """Test that edge targets are validated against defined nodes."""

    def setUp(self):
        self.validator = _make_validator()

    def test_valid_edge_targets(self):
        """Valid edge targets referencing existing nodes should pass."""
        df = _make_df(
            "GraphName,Node,Edge\n"
            "test,start,process\n"
            "test,process,end\n"
            "test,end,\n"
        )
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        edge_errors = [
            e for e in result.errors if "does not match any node" in e.message
        ]
        self.assertEqual(len(edge_errors), 0)

    def test_invalid_edge_target_detected(self):
        """Edge target referencing non-existent node should produce an error."""
        df = _make_df(
            "GraphName,Node,Edge\n"
            "test,start,nonexistent\n"
            "test,process,end\n"
            "test,end,\n"
        )
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        edge_errors = [
            e for e in result.errors if "does not match any node" in e.message
        ]
        self.assertEqual(len(edge_errors), 1)
        self.assertIn("nonexistent", edge_errors[0].message)

    def test_typo_suggestion_provided(self):
        """Close matches should provide 'Did you mean' suggestions."""
        df = _make_df(
            "GraphName,Node,Edge\n"
            "test,start,procss\n"
            "test,process,end\n"
            "test,end,\n"
        )
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        edge_errors = [
            e for e in result.errors if "does not match any node" in e.message
        ]
        self.assertEqual(len(edge_errors), 1)
        self.assertIn("process", edge_errors[0].suggestion)

    def test_parallel_edge_targets_validated(self):
        """Pipe-separated parallel edge targets should all be validated."""
        df = _make_df(
            "GraphName,Node,Edge\n"
            "test,start,process|nonexistent\n"
            "test,process,end\n"
            "test,end,\n"
        )
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        edge_errors = [
            e for e in result.errors if "does not match any node" in e.message
        ]
        self.assertEqual(len(edge_errors), 1)
        self.assertIn("nonexistent", edge_errors[0].message)

    def test_conditional_edge_targets_validated(self):
        """Success_Next and Failure_Next targets should be validated."""
        df = _make_df(
            "GraphName,Node,Success_Next,Failure_Next\n"
            "test,start,process,bad_node\n"
            "test,process,,\n"
        )
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        edge_errors = [
            e for e in result.errors if "does not match any node" in e.message
        ]
        self.assertEqual(len(edge_errors), 1)
        self.assertIn("bad_node", edge_errors[0].message)

    def test_cross_graph_targets_not_allowed(self):
        """Edge targets should only reference nodes in the same graph."""
        df = _make_df(
            "GraphName,Node,Edge\n"
            "graph1,start,other_graph_node\n"
            "graph2,other_graph_node,\n"
        )
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        edge_errors = [
            e for e in result.errors if "does not match any node" in e.message
        ]
        self.assertEqual(len(edge_errors), 1)


class TestDuplicateNodeValidation(unittest.TestCase):
    """Test that duplicate node names within a graph are detected."""

    def setUp(self):
        self.validator = _make_validator()

    def test_unique_nodes_pass(self):
        """Unique node names should not trigger errors."""
        df = _make_df("GraphName,Node\n" "test,start\n" "test,process\n" "test,end\n")
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        dup_errors = [e for e in result.errors if "Duplicate node" in e.message]
        self.assertEqual(len(dup_errors), 0)

    def test_duplicate_nodes_detected(self):
        """Duplicate node names within same graph should produce errors."""
        df = _make_df("GraphName,Node\n" "test,start\n" "test,start\n" "test,end\n")
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        dup_errors = [e for e in result.errors if "Duplicate node" in e.message]
        self.assertEqual(len(dup_errors), 1)
        self.assertIn("start", dup_errors[0].message)

    def test_same_name_different_graphs_ok(self):
        """Same node name in different graphs should not trigger errors."""
        df = _make_df("GraphName,Node\n" "graph1,start\n" "graph2,start\n")
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        dup_errors = [e for e in result.errors if "Duplicate node" in e.message]
        self.assertEqual(len(dup_errors), 0)


class TestOrphanNodeValidation(unittest.TestCase):
    """Test that isolated nodes (no edges in or out) are warned about."""

    def setUp(self):
        self.validator = _make_validator()

    def test_connected_nodes_no_warning(self):
        """Well-connected nodes should not trigger orphan warnings."""
        df = _make_df(
            "GraphName,Node,Edge\n"
            "test,start,process\n"
            "test,process,end\n"
            "test,end,\n"
        )
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        orphan_warnings = [w for w in result.warnings if "isolated node" in w.message]
        self.assertEqual(len(orphan_warnings), 0)

    def test_isolated_node_warned(self):
        """A node with no incoming or outgoing edges should generate a warning."""
        df = _make_df(
            "GraphName,Node,Edge\n" "test,start,end\n" "test,orphan,\n" "test,end,\n"
        )
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        orphan_warnings = [w for w in result.warnings if "isolated node" in w.message]
        self.assertEqual(len(orphan_warnings), 1)
        self.assertIn("orphan", orphan_warnings[0].message)

    def test_single_node_graph_not_orphan(self):
        """A graph with only one node should not be flagged as orphan."""
        df = _make_df("GraphName,Node\n" "test,only_node\n")
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        orphan_warnings = [w for w in result.warnings if "isolated node" in w.message]
        self.assertEqual(len(orphan_warnings), 0)


class TestAgentTypeValidation(unittest.TestCase):
    """Test that unrecognized agent types produce warnings with suggestions."""

    def setUp(self):
        self.validator = _make_validator()

    def test_known_agent_type_no_warning(self):
        """Known agent types should not produce warnings."""
        df = _make_df(
            "GraphName,Node,AgentType\n"
            "test,start,echo\n"
            "test,process,openai\n"
            "test,store,csv_reader\n"
        )
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        agent_warnings = [
            w for w in result.warnings if "Unrecognized agent type" in w.message
        ]
        self.assertEqual(len(agent_warnings), 0)

    def test_unknown_agent_type_warned(self):
        """Unknown agent types should produce a warning."""
        df = _make_df("GraphName,Node,AgentType\n" "test,start,my_custom_agent\n")
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        agent_warnings = [
            w for w in result.warnings if "Unrecognized agent type" in w.message
        ]
        self.assertEqual(len(agent_warnings), 1)

    def test_typo_suggestion_for_agent_type(self):
        """Close match agent type should get a 'Did you mean' suggestion."""
        df = _make_df("GraphName,Node,AgentType\n" "test,start,opanai\n")
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        agent_warnings = [
            w for w in result.warnings if "Unrecognized agent type" in w.message
        ]
        self.assertEqual(len(agent_warnings), 1)
        self.assertIn("openai", agent_warnings[0].suggestion)

    def test_none_agent_type_no_warning(self):
        """Missing/None agent type should not produce a warning."""
        df = _make_df("GraphName,Node,AgentType\n" "test,start,\n")
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        agent_warnings = [
            w for w in result.warnings if "Unrecognized agent type" in w.message
        ]
        self.assertEqual(len(agent_warnings), 0)

    def test_agent_type_aliases_recognized(self):
        """Agent type aliases (claude, gpt, gemini, chatgpt) should be recognized."""
        df = _make_df(
            "GraphName,Node,AgentType\n"
            "test,n1,claude\n"
            "test,n2,gpt\n"
            "test,n3,gemini\n"
            "test,n4,chatgpt\n"
        )
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result)

        agent_warnings = [
            w for w in result.warnings if "Unrecognized agent type" in w.message
        ]
        self.assertEqual(len(agent_warnings), 0)


class TestCustomAgentTypeRecognition(unittest.TestCase):
    """Test that custom agent types are recognized when known_agent_types is provided."""

    def setUp(self):
        self.validator = _make_validator()

    def test_custom_agent_recognized_via_known_types(self):
        """Custom agents in known_agent_types should not produce warnings."""
        df = _make_df(
            "GraphName,Node,AgentType\n"
            "test,start,my_custom_agent\n"
            "test,process,another_custom\n"
        )
        # Include custom types alongside builtins
        known = {"echo", "openai", "my_custom_agent", "another_custom"}
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result, known_agent_types=known)

        agent_warnings = [
            w for w in result.warnings if "Unrecognized agent type" in w.message
        ]
        self.assertEqual(len(agent_warnings), 0)

    def test_unknown_agent_still_warned_with_custom_types(self):
        """Agents not in known_agent_types should still produce warnings."""
        df = _make_df("GraphName,Node,AgentType\n" "test,start,totally_unknown\n")
        known = {"echo", "openai", "my_custom_agent"}
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        self.validator.validate_graph_semantics(df, result, known_agent_types=known)

        agent_warnings = [
            w for w in result.warnings if "Unrecognized agent type" in w.message
        ]
        self.assertEqual(len(agent_warnings), 1)
        self.assertIn("totally_unknown", agent_warnings[0].message)

    def test_builtin_fallback_when_no_known_types(self):
        """Without known_agent_types, should fall back to builtin constants."""
        df = _make_df("GraphName,Node,AgentType\n" "test,start,echo\n")
        result = ValidationResult(file_path="test.csv", file_type="csv", is_valid=True)
        # No known_agent_types passed - falls back to _KNOWN_AGENT_TYPES module constant
        self.validator.validate_graph_semantics(df, result)

        agent_warnings = [
            w for w in result.warnings if "Unrecognized agent type" in w.message
        ]
        self.assertEqual(len(agent_warnings), 0)


class TestComputeHashWithContent(unittest.TestCase):
    """Test the compute_hash_with_content method."""

    def test_returns_hash_and_content(self):
        """Should return both hash string and file content bytes."""
        from agentmap.services.graph.graph_registry_service import GraphRegistryService

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("GraphName,Node\ntest,start\n")
            f.flush()
            csv_path = Path(f.name)

        try:
            csv_hash, content = GraphRegistryService.compute_hash_with_content(csv_path)
            self.assertIsInstance(csv_hash, str)
            self.assertEqual(len(csv_hash), 64)  # SHA-256 hex digest length
            self.assertIsInstance(content, bytes)
            self.assertIn(b"GraphName", content)
        finally:
            csv_path.unlink()

    def test_hash_matches_compute_hash(self):
        """Hash from compute_hash_with_content should match compute_hash."""
        from agentmap.services.graph.graph_registry_service import GraphRegistryService

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("GraphName,Node\ntest,start\n")
            f.flush()
            csv_path = Path(f.name)

        try:
            hash_only = GraphRegistryService.compute_hash(csv_path)
            hash_with_content, _ = GraphRegistryService.compute_hash_with_content(
                csv_path
            )
            self.assertEqual(hash_only, hash_with_content)
        finally:
            csv_path.unlink()

    def test_file_not_found_raises(self):
        """Non-existent file should raise FileNotFoundError."""
        from agentmap.services.graph.graph_registry_service import GraphRegistryService

        with self.assertRaises(FileNotFoundError):
            GraphRegistryService.compute_hash_with_content(Path("/nonexistent.csv"))


if __name__ == "__main__":
    unittest.main()
