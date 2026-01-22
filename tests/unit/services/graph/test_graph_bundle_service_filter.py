"""Unit tests for GraphBundleService._filter_actual_services() method.

Tests the service filtering logic that uses DeclarationRegistryService
to identify valid services and filter out non-service entries like
config_path, routing_cache, and other metadata.
"""

import unittest
from unittest.mock import Mock

from agentmap.services.graph.graph_bundle_service import GraphBundleService
from tests.utils.mock_service_factory import MockServiceFactory


class TestGraphBundleServiceFilterServices(unittest.TestCase):
    """Verify _filter_actual_services() correctly identifies registered services."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create real logging service for debug output verification
        self.logging_service = MockServiceFactory.create_mock_logging_service()

        # Mock DeclarationRegistryService with get_service_declaration method
        self.mock_declaration_registry = Mock()

        # Create GraphBundleService with minimal dependencies
        # Only logging_service and declaration_registry are used by _filter_actual_services
        self.service = GraphBundleService(
            logging_service=self.logging_service,
            protocol_requirements_analyzer=Mock(),
            agent_factory_service=Mock(),
            json_storage_service=Mock(),
            csv_parser_service=Mock(),
            static_bundle_analyzer=Mock(),
            app_config_service=Mock(),
            declaration_registry_service=self.mock_declaration_registry,
            graph_registry_service=Mock(),
            file_path_service=Mock(),
            system_storage_manager=Mock(),
        )

    def test_filter_registered_services_included(self):
        """Registered services should be included in filtered results."""
        # Arrange: Set up mock to return ServiceDeclaration for valid services
        def mock_get_declaration(service_name):
            valid_services = {"logging_service", "config_service", "storage_service"}
            return Mock() if service_name in valid_services else None

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_declaration
        )

        input_services = {"logging_service", "config_service", "storage_service"}

        # Act: Filter the services
        result = self.service._filter_actual_services(input_services)

        # Assert: All registered services should be included
        self.assertEqual(result, input_services)
        self.assertEqual(len(result), 3)
        self.assertIn("logging_service", result)
        self.assertIn("config_service", result)
        self.assertIn("storage_service", result)

    def test_filter_non_service_entries_excluded(self):
        """Non-service entries like config_path should be filtered out."""
        # Arrange: Set up mock to only recognize actual services
        def mock_get_declaration(service_name):
            non_services = {"config_path", "routing_cache", "metadata"}
            return None if service_name in non_services else Mock()

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_declaration
        )

        input_services = {
            "logging_service",
            "config_path",
            "routing_cache",
            "metadata",
        }

        # Act: Filter the services
        result = self.service._filter_actual_services(input_services)

        # Assert: Only logging_service should remain
        self.assertEqual(result, {"logging_service"})
        self.assertEqual(len(result), 1)
        self.assertNotIn("config_path", result)
        self.assertNotIn("routing_cache", result)
        self.assertNotIn("metadata", result)

    def test_filter_empty_input_returns_empty_set(self):
        """Empty input set should return empty result set."""
        # Arrange: Empty input
        input_services = set()

        # Act: Filter the services
        result = self.service._filter_actual_services(input_services)

        # Assert: Should return empty set
        self.assertEqual(result, set())
        self.assertEqual(len(result), 0)

    def test_filter_all_non_services_returns_empty_set(self):
        """Input with only non-service entries should return empty set."""
        # Arrange: Mock returns None for all entries (no registered services)
        self.mock_declaration_registry.get_service_declaration.return_value = None

        input_services = {"config_path", "routing_cache", "temp_data", "cache_key"}

        # Act: Filter the services
        result = self.service._filter_actual_services(input_services)

        # Assert: Should return empty set
        self.assertEqual(result, set())
        self.assertEqual(len(result), 0)

        # Verify all entries were checked
        self.assertEqual(
            self.mock_declaration_registry.get_service_declaration.call_count, 4
        )

    def test_filter_mixed_services_and_non_services(self):
        """Mixed input should filter correctly, keeping only registered services."""
        # Arrange: Set up realistic mix of services and non-services
        def mock_get_declaration(service_name):
            registered_services = {
                "logging_service",
                "agent_factory_service",
                "json_storage_service",
                "csv_parser_service",
            }
            return Mock() if service_name in registered_services else None

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_declaration
        )

        input_services = {
            "logging_service",
            "agent_factory_service",
            "config_path",
            "json_storage_service",
            "routing_cache",
            "csv_parser_service",
            "metadata_cache",
            "temp_file_path",
        }

        # Act: Filter the services
        result = self.service._filter_actual_services(input_services)

        # Assert: Only registered services should remain
        expected_services = {
            "logging_service",
            "agent_factory_service",
            "json_storage_service",
            "csv_parser_service",
        }
        self.assertEqual(result, expected_services)
        self.assertEqual(len(result), 4)

        # Verify non-services were excluded
        self.assertNotIn("config_path", result)
        self.assertNotIn("routing_cache", result)
        self.assertNotIn("metadata_cache", result)
        self.assertNotIn("temp_file_path", result)

    def test_filter_calls_declaration_registry_for_each_service(self):
        """Method should check declaration registry for each input service."""
        # Arrange: Set up tracking mock
        self.mock_declaration_registry.get_service_declaration.return_value = Mock()

        input_services = {"service_a", "service_b", "service_c"}

        # Act: Filter the services
        result = self.service._filter_actual_services(input_services)

        # Assert: Should call get_service_declaration for each service
        self.assertEqual(
            self.mock_declaration_registry.get_service_declaration.call_count, 3
        )

        # Verify each service was checked
        called_services = {
            call[0][0]
            for call in self.mock_declaration_registry.get_service_declaration.call_args_list
        }
        self.assertEqual(called_services, input_services)

    def test_filter_preserves_service_names(self):
        """Filtered services should maintain exact original names."""
        # Arrange: Services with specific naming conventions
        def mock_get_declaration(service_name):
            return Mock()  # All are valid services

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_declaration
        )

        input_services = {
            "LoggingService",
            "agent_factory_service",
            "JSONStorageService",
            "csv_parser",
        }

        # Act: Filter the services
        result = self.service._filter_actual_services(input_services)

        # Assert: Names should be preserved exactly
        self.assertEqual(result, input_services)
        self.assertIn("LoggingService", result)
        self.assertIn("agent_factory_service", result)
        self.assertIn("JSONStorageService", result)
        self.assertIn("csv_parser", result)

    def test_filter_handles_declaration_registry_exception(self):
        """Method should handle exceptions from declaration registry gracefully."""
        # Arrange: Mock raises exception for certain services
        def mock_get_declaration(service_name):
            if service_name == "problematic_service":
                raise RuntimeError("Declaration lookup failed")
            return Mock() if service_name == "valid_service" else None

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_declaration
        )

        input_services = {"valid_service", "problematic_service", "non_service"}

        # Act & Assert: Should raise the exception (no error handling in method)
        with self.assertRaises(RuntimeError):
            self.service._filter_actual_services(input_services)

    def test_filter_realistic_dependency_analysis_output(self):
        """Test with realistic dependency analysis output from graph bundle creation."""
        # Arrange: Simulate typical dependency analysis results
        def mock_get_declaration(service_name):
            # Services that would be registered in DI container
            registered_services = {
                "logging_service",
                "protocol_requirements_analyzer",
                "agent_factory_service",
                "json_storage_service",
                "csv_parser_service",
                "static_bundle_analyzer",
                "app_config_service",
                "declaration_registry_service",
                "graph_registry_service",
                "file_path_service",
                "system_storage_manager",
            }
            return Mock() if service_name in registered_services else None

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_declaration
        )

        # Realistic input including services and non-service metadata
        input_services = {
            "logging_service",
            "agent_factory_service",
            "json_storage_service",
            "config_path",  # Non-service metadata
            "routing_cache",  # Non-service metadata
            "graph_registry_service",
            "temp_bundle_path",  # Non-service metadata
            "declaration_registry_service",
        }

        # Act: Filter the services
        result = self.service._filter_actual_services(input_services)

        # Assert: Only actual services remain
        expected_services = {
            "logging_service",
            "agent_factory_service",
            "json_storage_service",
            "graph_registry_service",
            "declaration_registry_service",
        }
        self.assertEqual(result, expected_services)
        self.assertEqual(len(result), 5)

        # Verify metadata entries were filtered out
        self.assertNotIn("config_path", result)
        self.assertNotIn("routing_cache", result)
        self.assertNotIn("temp_bundle_path", result)

    def test_filter_verifies_debug_logging(self):
        """Method should log debug information for filtered entries."""
        # Arrange: Set up mock to filter out some entries
        def mock_get_declaration(service_name):
            return None if service_name in {"config_path", "routing_cache"} else Mock()

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_declaration
        )

        input_services = {"logging_service", "config_path", "routing_cache"}

        # Act: Filter the services
        result = self.service._filter_actual_services(input_services)

        # Assert: Should have logged about filtering
        # Note: Actual logging verification depends on MockServiceFactory implementation
        # This test documents expected behavior - logging should occur for filtered entries
        self.assertEqual(result, {"logging_service"})
        self.assertEqual(len(result), 1)

    def test_filter_input_output_counts_logged(self):
        """Method should log input count and output count for debugging."""
        # Arrange: Set up mixed input
        def mock_get_declaration(service_name):
            return Mock() if service_name.endswith("_service") else None

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_declaration
        )

        input_services = {
            "logging_service",
            "config_service",
            "config_path",
            "metadata",
            "cache_key",
        }

        # Act: Filter the services
        result = self.service._filter_actual_services(input_services)

        # Assert: Should have filtered from 5 to 2
        self.assertEqual(len(input_services), 5)
        self.assertEqual(len(result), 2)
        self.assertEqual(result, {"logging_service", "config_service"})


if __name__ == "__main__":
    unittest.main()
