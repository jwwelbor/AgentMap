"""
Integration test for scaffold command bundle deletion refactoring.

Tests that the scaffold command correctly uses GraphBundleService.delete_bundle()
after scaffolding new agents.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from agentmap.core.cli.scaffold_command import scaffold_command
from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.scaffold_types import ScaffoldResult


class TestScaffoldCommandBundleDeletion(unittest.TestCase):
    """Test that scaffold command uses delete_bundle correctly."""
    
    @patch('agentmap.core.cli.scaffold_command.typer')
    @patch('agentmap.core.cli.scaffold_command.initialize_di')
    @patch('agentmap.core.cli.scaffold_command.resolve_csv_path')
    @patch('agentmap.core.cli.scaffold_command.get_or_create_bundle')
    def test_scaffold_command_uses_delete_bundle(self, mock_get_bundle, mock_resolve_csv, 
                                                  mock_init_di, mock_typer):
        """Test that scaffold command uses delete_bundle when scaffolding succeeds."""
        # Setup mocks
        mock_resolve_csv.return_value = Path("test.csv")
        
        # Create a mock bundle with csv_hash
        mock_bundle = Mock(spec=GraphBundle)
        mock_bundle.graph_name = "test_graph"
        mock_bundle.csv_hash = "abc123def456"
        mock_bundle.missing_declarations = []
        mock_get_bundle.return_value = mock_bundle
        
        # Create mock container with services
        mock_container = Mock()
        mock_bundle_service = Mock()
        mock_registry_service = Mock()
        mock_scaffold_service = Mock()
        
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.graph_registry_service.return_value = mock_registry_service
        mock_container.graph_scaffold_service.return_value = mock_scaffold_service
        mock_init_di.return_value = mock_container
        
        # Setup scaffold result with successful scaffolding
        mock_result = ScaffoldResult(
            scaffolded_count=2,
            created_files=[Path("agent1.py"), Path("agent2.py")],
            errors=[],
            service_stats={"LLMService": 2}
        )
        mock_scaffold_service.scaffold_from_bundle.return_value = mock_result
        
        # Setup delete_bundle to return True
        mock_bundle_service.delete_bundle.return_value = True
        
        # Call the command
        scaffold_command(
            csv_file="test.csv",
            graph=None,
            csv=None,
            output_dir=None,
            func_dir=None,
            config_file=None,
            overwrite=False
        )
        
        # Verify delete_bundle was called with the bundle
        mock_bundle_service.delete_bundle.assert_called_once_with(mock_bundle)
        
        # Verify registry removal was called after successful deletion
        mock_registry_service.remove_entry.assert_called_once_with(mock_bundle.csv_hash)
        
    @patch('agentmap.core.cli.scaffold_command.typer')
    @patch('agentmap.core.cli.scaffold_command.initialize_di')
    @patch('agentmap.core.cli.scaffold_command.resolve_csv_path')
    @patch('agentmap.core.cli.scaffold_command.get_or_create_bundle')
    def test_scaffold_command_no_deletion_when_no_scaffolding(self, mock_get_bundle, 
                                                               mock_resolve_csv, mock_init_di, mock_typer):
        """Test that delete_bundle is NOT called when no agents are scaffolded."""
        # Setup mocks
        mock_resolve_csv.return_value = Path("test.csv")
        
        # Create a mock bundle
        mock_bundle = Mock(spec=GraphBundle)
        mock_bundle.graph_name = "test_graph"
        mock_bundle.csv_hash = "abc123def456"
        mock_bundle.missing_declarations = []
        mock_get_bundle.return_value = mock_bundle
        
        # Create mock container with services
        mock_container = Mock()
        mock_bundle_service = Mock()
        mock_registry_service = Mock()
        mock_scaffold_service = Mock()
        
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.graph_registry_service.return_value = mock_registry_service
        mock_container.graph_scaffold_service.return_value = mock_scaffold_service
        mock_init_di.return_value = mock_container
        
        # Setup scaffold result with NO scaffolding
        mock_result = ScaffoldResult(
            scaffolded_count=0,  # No agents scaffolded
            created_files=[],
            errors=[],
            service_stats={}
        )
        mock_scaffold_service.scaffold_from_bundle.return_value = mock_result
        
        # Call the command
        scaffold_command(
            csv_file="test.csv",
            graph=None,
            csv=None,
            output_dir=None,
            func_dir=None,
            config_file=None,
            overwrite=False
        )
        
        # Verify delete_bundle was NOT called
        mock_bundle_service.delete_bundle.assert_not_called()
        
        # Verify registry removal was NOT called
        mock_registry_service.remove_entry.assert_not_called()
        
    @patch('agentmap.core.cli.scaffold_command.typer')
    @patch('agentmap.core.cli.scaffold_command.initialize_di')
    @patch('agentmap.core.cli.scaffold_command.resolve_csv_path')
    @patch('agentmap.core.cli.scaffold_command.get_or_create_bundle')
    def test_scaffold_command_handles_delete_bundle_error(self, mock_get_bundle, 
                                                          mock_resolve_csv, mock_init_di, mock_typer):
        """Test that scaffold command handles delete_bundle errors gracefully."""
        # Setup mocks
        mock_resolve_csv.return_value = Path("test.csv")
        
        # Create a mock bundle with csv_hash
        mock_bundle = Mock(spec=GraphBundle)
        mock_bundle.graph_name = "test_graph"
        mock_bundle.csv_hash = "abc123def456"
        mock_bundle.missing_declarations = []
        mock_get_bundle.return_value = mock_bundle
        
        # Create mock container with services
        mock_container = Mock()
        mock_bundle_service = Mock()
        mock_registry_service = Mock()
        mock_scaffold_service = Mock()
        
        mock_container.graph_bundle_service.return_value = mock_bundle_service
        mock_container.graph_registry_service.return_value = mock_registry_service
        mock_container.graph_scaffold_service.return_value = mock_scaffold_service
        mock_init_di.return_value = mock_container
        
        # Setup scaffold result with successful scaffolding
        mock_result = ScaffoldResult(
            scaffolded_count=2,
            created_files=[Path("agent1.py"), Path("agent2.py")],
            errors=[],
            service_stats={"LLMService": 2}
        )
        mock_scaffold_service.scaffold_from_bundle.return_value = mock_result
        
        # Setup delete_bundle to raise PermissionError
        mock_bundle_service.delete_bundle.side_effect = PermissionError("Access denied")
        
        # Call the command - should not raise, but handle the error
        scaffold_command(
            csv_file="test.csv",
            graph=None,
            csv=None,
            output_dir=None,
            func_dir=None,
            config_file=None,
            overwrite=False
        )
        
        # Verify delete_bundle was called
        mock_bundle_service.delete_bundle.assert_called_once_with(mock_bundle)
        
        # Verify registry removal was still attempted (best-effort cleanup)
        mock_registry_service.remove_entry.assert_called_once_with(mock_bundle.csv_hash)


if __name__ == "__main__":
    unittest.main()
