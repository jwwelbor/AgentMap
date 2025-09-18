"""
Unit tests for graph identifier parsing in _resolve_csv_path function.

Tests the new filename::graph_name syntax alongside existing patterns.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from agentmap.exceptions.runtime_exceptions import GraphNotFound
from agentmap.runtime.workflow_ops import _resolve_csv_path


class TestGraphIdentifierParsing:
    """Test cases for graph identifier parsing functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock container and services
        self.container = Mock()
        self.app_config_service = Mock()
        self.logging_service = Mock()
        self.logger = Mock()
        
        # Setup container service returns
        self.container.app_config_service.return_value = self.app_config_service
        self.container.logging_service.return_value = self.logging_service
        self.logging_service.get_logger.return_value = self.logger
        
        # Setup default CSV repository path
        self.csv_repository = Path("/test/repo")
        self.app_config_service.get_csv_repository_path.return_value = self.csv_repository

    def test_double_colon_syntax_repository_workflow(self):
        """Test filename::graph_name syntax with repository workflow."""
        graph_name = "workflow::specific_graph"
        workflow_file = self.csv_repository / "workflow.csv"
        
        with patch.object(Path, 'exists', return_value=True):
            csv_path, resolved_graph_name = _resolve_csv_path(graph_name, self.container)
        
        assert csv_path == workflow_file
        assert resolved_graph_name == "specific_graph"
        self.logger.debug.assert_called_once()

    def test_double_colon_syntax_direct_path(self):
        """Test filename::graph_name syntax with direct file path."""
        graph_name = "custom_workflow::my_graph"
        workflow_file = self.csv_repository / "custom_workflow.csv"
        
        with patch.object(Path, 'exists', return_value=False):
            csv_path, resolved_graph_name = _resolve_csv_path(graph_name, self.container)
        
        assert csv_path == Path("custom_workflow")
        assert resolved_graph_name == "my_graph"

    def test_double_colon_invalid_syntax_multiple_delimiters(self):
        """Test validation for multiple :: delimiters."""
        graph_name = "workflow::graph::extra"
        
        with pytest.raises(GraphNotFound, match="Invalid :: syntax"):
            _resolve_csv_path(graph_name, self.container)

    def test_double_colon_empty_workflow_name(self):
        """Test validation for empty workflow name in :: syntax."""
        graph_name = "::graph_name"
        
        with pytest.raises(GraphNotFound, match="Empty workflow name"):
            _resolve_csv_path(graph_name, self.container)

    def test_double_colon_empty_graph_name(self):
        """Test validation for empty graph name in :: syntax."""
        graph_name = "workflow::"
        
        with pytest.raises(GraphNotFound, match="Empty workflow name or graph name"):
            _resolve_csv_path(graph_name, self.container)

    def test_double_colon_whitespace_handling(self):
        """Test whitespace is properly stripped in :: syntax."""
        graph_name = "  workflow  ::  graph_name  "
        workflow_file = self.csv_repository / "workflow.csv"
        
        with patch.object(Path, 'exists', return_value=True):
            csv_path, resolved_graph_name = _resolve_csv_path(graph_name, self.container)
        
        assert csv_path == workflow_file
        assert resolved_graph_name == "graph_name"

    def test_existing_slash_syntax_unchanged(self):
        """Test existing workflow/graph syntax still works."""
        graph_name = "workflow/graph_name"
        workflow_file = self.csv_repository / "workflow.csv"
        
        with patch.object(Path, 'exists', return_value=True):
            csv_path, resolved_graph_name = _resolve_csv_path(graph_name, self.container)
        
        assert csv_path == workflow_file
        assert resolved_graph_name == "graph_name"

    def test_existing_slash_syntax_direct_path(self):
        """Test existing workflow/graph syntax with direct file path."""
        graph_name = "path/to/workflow/graph_name"
        
        with patch.object(Path, 'exists', return_value=False):
            csv_path, resolved_graph_name = _resolve_csv_path(graph_name, self.container)
        
        assert csv_path == Path("path/to/workflow/graph_name")
        assert resolved_graph_name == "graph_name"

    def test_simple_name_repository_workflow(self):
        """Test simple name resolves to repository workflow with same graph name."""
        graph_name = "simple_workflow"
        workflow_file = self.csv_repository / "simple_workflow.csv"
        
        with patch.object(Path, 'exists', return_value=True):
            csv_path, resolved_graph_name = _resolve_csv_path(graph_name, self.container)
        
        assert csv_path == workflow_file
        assert resolved_graph_name == "simple_workflow"

    def test_simple_name_direct_path(self):
        """Test simple name as direct file path."""
        graph_name = "direct_file"
        
        with patch.object(Path, 'exists', return_value=False):
            csv_path, resolved_graph_name = _resolve_csv_path(graph_name, self.container)
        
        assert csv_path == Path("direct_file")
        assert resolved_graph_name == "direct_file"

    def test_double_colon_takes_precedence_over_slash(self):
        """Test :: syntax takes precedence when both :: and / are present."""
        graph_name = "workflow/sub::graph_name"
        # The first part before :: is "workflow/sub", second part is "graph_name"
        
        with patch.object(Path, 'exists', return_value=False):
            csv_path, resolved_graph_name = _resolve_csv_path(graph_name, self.container)
        
        assert csv_path == Path("workflow/sub")
        assert resolved_graph_name == "graph_name"

    def test_service_error_handling(self):
        """Test error handling when services fail."""
        graph_name = "test_workflow"
        self.app_config_service.get_csv_repository_path.side_effect = Exception("Service error")
        
        with pytest.raises(GraphNotFound, match="Failed to resolve graph path"):
            _resolve_csv_path(graph_name, self.container)

    def test_logging_called_for_double_colon_syntax(self):
        """Test that logging is called when :: syntax is detected."""
        graph_name = "workflow::graph"
        
        with patch.object(Path, 'exists', return_value=True):
            _resolve_csv_path(graph_name, self.container)
        
        # Verify logger.debug was called with expected message
        self.logger.debug.assert_called_once()
        call_args = self.logger.debug.call_args[0][0]
        assert "Detected :: syntax" in call_args
        assert "workflow='workflow'" in call_args
        assert "graph='graph'" in call_args

    def test_return_type_is_tuple(self):
        """Test that function returns a tuple of (Path, str)."""
        graph_name = "test_workflow"
        
        with patch.object(Path, 'exists', return_value=True):
            result = _resolve_csv_path(graph_name, self.container)
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], Path)
        assert isinstance(result[1], str)

    def test_edge_case_single_colon(self):
        """Test single colon is not treated as :: syntax."""
        graph_name = "workflow:graph"
        workflow_file = self.csv_repository / "workflow:graph.csv"
        
        with patch.object(Path, 'exists', return_value=True):
            csv_path, resolved_graph_name = _resolve_csv_path(graph_name, self.container)
        
        # Should treat as simple name, not :: syntax
        assert csv_path == workflow_file
        assert resolved_graph_name == "workflow:graph"

    def test_edge_case_triple_colon(self):
        """Test triple colon triggers validation error."""
        graph_name = "workflow:::graph"
        
        with pytest.raises(GraphNotFound, match="Invalid :: syntax"):
            _resolve_csv_path(graph_name, self.container)
