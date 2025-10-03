import unittest
from pathlib import Path
from unittest.mock import Mock

from agentmap.services.graph.scaffold.coordinator import GraphScaffoldService
from agentmap.services.graph.graph_scaffold_service import GraphScaffoldService as ShimImport
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphScaffoldCoordinatorAndShim(unittest.TestCase):
    """Test the GraphScaffoldService coordinator and shim integration."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory following established patterns."""
        # Create mock services using MockServiceFactory
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service({
            "custom_agents_path": "test/agents",
            "functions_path": "test/functions", 
            "csv_path": "test/data.csv"
        })
        
        # Add specific path methods for GraphScaffoldService
        self.mock_app_config_service.get_custom_agents_path.return_value = Path("test/agents")
        self.mock_app_config_service.get_functions_path.return_value = Path("test/functions")
        self.mock_app_config_service.csv_path = Path("test/data.csv")
        
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        self.mock_function_resolution_service = Mock()
        self.mock_function_resolution_service.extract_func_ref.return_value = None
        self.mock_function_resolution_service.has_function.return_value = False
        
        self.mock_agent_registry_service = MockServiceFactory.create_mock_agent_registry_service()
        
        self.mock_template_composer = Mock()
        self.mock_template_composer.compose_template.return_value = "# Agent template"
        self.mock_template_composer.compose_function_template.return_value = "# Function template"
        
        self.mock_custom_agent_declaration_manager = MockServiceFactory.create_mock_custom_agent_declaration_manager()
        self.mock_bundle_update_service = Mock()

    def test_shim_and_direct_import_are_same_class(self):
        """Test that shim import and direct import refer to the same class."""
        self.assertIs(GraphScaffoldService, ShimImport)

    def test_coordinator_scaffolds_both(self):
        """Test that coordinator can scaffold both agent and function files."""
        # Create service with mocked dependencies
        svc = GraphScaffoldService(
            app_config_service=self.mock_app_config_service,
            logging_service=self.mock_logging_service,
            function_resolution_service=self.mock_function_resolution_service,
            agent_registry_service=self.mock_agent_registry_service,
            template_composer=self.mock_template_composer,
            custom_agent_declaration_manager=self.mock_custom_agent_declaration_manager,
            bundle_update_service=self.mock_bundle_update_service,
        )

        # Create temporary output directory (not files)
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Pass directory paths - let the service create the filenames
            result_agent = svc.scaffold_agent_class("Demo", {"attrs": {}}, tmp_path)
            result_function = svc.scaffold_edge_function("edge_fn", {"params": {}}, tmp_path)

            # Verify files were created with expected names
            expected_agent_file = tmp_path / "demo_agent.py"
            expected_function_file = tmp_path / "edge_fn.py"
            
            self.assertTrue(expected_agent_file.exists())
            self.assertTrue(expected_function_file.exists())
            self.assertEqual(result_agent, expected_agent_file)
            self.assertEqual(result_function, expected_function_file)

            # Verify template composer was called
            self.mock_template_composer.compose_template.assert_called_once()
            self.mock_template_composer.compose_function_template.assert_called_once()


if __name__ == '__main__':
    unittest.main()
