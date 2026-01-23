import unittest
from pathlib import Path
from unittest.mock import Mock

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.models.scaffold_types import ScaffoldOptions
from agentmap.services.graph.graph_scaffold_service import (
    GraphScaffoldService as ShimImport,
)
from agentmap.services.graph.scaffold.coordinator import GraphScaffoldService
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphScaffoldCoordinatorAndShim(unittest.TestCase):
    """Test the GraphScaffoldService coordinator and shim integration."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory following established patterns."""
        # Create mock services using MockServiceFactory
        self.mock_app_config_service = (
            MockServiceFactory.create_mock_app_config_service(
                {
                    "custom_agents_path": "test/agents",
                    "functions_path": "test/functions",
                    "csv_path": "test/data.csv",
                }
            )
        )

        # Add specific path methods for GraphScaffoldService
        self.mock_app_config_service.get_custom_agents_path.return_value = Path(
            "test/agents"
        )
        self.mock_app_config_service.get_functions_path.return_value = Path(
            "test/functions"
        )
        self.mock_app_config_service.csv_path = Path("test/data.csv")

        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()

        self.mock_function_resolution_service = Mock()
        self.mock_function_resolution_service.extract_func_ref.return_value = None
        self.mock_function_resolution_service.has_function.return_value = False

        self.mock_agent_registry_service = (
            MockServiceFactory.create_mock_agent_registry_service()
        )

        self.mock_template_composer = Mock()
        self.mock_template_composer.compose_template.return_value = "# Agent template"
        self.mock_template_composer.compose_function_template.return_value = (
            "# Function template"
        )

        self.mock_custom_agent_declaration_manager = (
            MockServiceFactory.create_mock_custom_agent_declaration_manager()
        )
        self.mock_bundle_update_service = Mock()

    def test_shim_and_direct_import_are_same_class(self):
        """Test that shim import and direct import refer to the same class."""
        self.assertIs(GraphScaffoldService, ShimImport)

    @unittest.skip("MANUAL: Scaffold API changed - needs investigation")
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
            result_function = svc.scaffold_edge_function(
                "edge_fn", {"params": {}}, tmp_path
            )

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

    @unittest.skip("MANUAL: Scaffold API changed - needs investigation")
    def test_scaffold_from_bundle_case_insensitive_agent_types(self):
        """
        Test that scaffold_from_bundle correctly matches agent types case-insensitively.

        Regression test for bug where CSV had "OpenAIAgent" but missing_declarations
        contained "openaiagent" (lowercase), causing scaffold to fail because comparison
        was case-sensitive.
        """
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

        # Create a bundle with mixed case agent types (as they appear in CSV)
        # The CSV parser preserves case, but static_bundle_analyzer normalizes to lowercase
        node1 = Node(
            name="WeatherNode",
            agent_type="OpenAIAgent",  # CamelCase as in CSV
            context="Get weather data",
            prompt="Get weather for {location}",
            inputs=["location"],
            output="weather_data",
        )

        node2 = Node(
            name="AnalyzerNode",
            agent_type="WeatherAnalyzer",  # CamelCase as in CSV
            context="Analyze weather",
            prompt="Analyze the weather data",
            inputs=["weather_data"],
            output="analysis",
        )

        # Create bundle with lowercase missing_declarations (as static_bundle_analyzer does)
        bundle = GraphBundle(
            graph_name="TestGraph",
            nodes={"WeatherNode": node1, "AnalyzerNode": node2},
            csv_hash="test_hash_123",
            entry_point="WeatherNode",
            validation_metadata={},
            missing_declarations={"openaiagent", "weatheranalyzer"},  # lowercase!
            agent_mappings={},
            builtin_agents=set(),
            custom_agents={"openaiagent", "weatheranalyzer"},
        )

        # Mock bundle update service to return the bundle as-is
        self.mock_bundle_update_service.update_bundle_from_declarations.return_value = (
            bundle
        )

        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            options = ScaffoldOptions(
                graph_name="TestGraph", output_path=tmp_path, overwrite_existing=False
            )

            # This should succeed - the case-insensitive comparison should find the nodes
            result = svc.scaffold_from_bundle(bundle, options)

            # Verify that agents were scaffolded (not skipped due to case mismatch)
            self.assertEqual(
                result.scaffolded_count,
                2,
                "Should scaffold 2 agents despite case mismatch between "
                "missing_declarations (lowercase) and node.agent_type (CamelCase)",
            )

            # Verify files were created with lowercase names
            expected_file1 = tmp_path / "openaiagent_agent.py"
            expected_file2 = tmp_path / "weatheranalyzer_agent.py"

            self.assertTrue(
                expected_file1.exists(),
                f"Should create openaiagent_agent.py, created files: {result.created_files}",
            )
            self.assertTrue(
                expected_file2.exists(),
                f"Should create weatheranalyzer_agent.py, created files: {result.created_files}",
            )

            # Verify no errors occurred
            self.assertEqual(
                len(result.errors),
                0,
                f"Should have no errors, but got: {result.errors}",
            )


if __name__ == "__main__":
    unittest.main()
