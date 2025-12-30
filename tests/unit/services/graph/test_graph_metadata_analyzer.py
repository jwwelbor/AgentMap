"""Unit tests for GraphMetadataAnalyzer.filter_actual_services() method.

This test module verifies the service filtering logic that uses
DeclarationRegistryService as the single source of truth for
identifying registered services.

Test Coverage:
- Registered services are included in results
- Non-registered entries are filtered out
- Empty input sets are handled correctly
- Mixed sets (some services, some non-services) are properly filtered
- Debug logging occurs for filtered entries
"""

import unittest
from unittest.mock import Mock

from agentmap.models.declaration_models import ServiceDeclaration
from agentmap.services.graph.graph_metadata_analyzer import GraphMetadataAnalyzer
from tests.utils.mock_service_factory_patch import create_fixed_mock_logging_service


class TestGraphMetadataAnalyzerFilterServices(unittest.TestCase):
    """Test suite for filter_actual_services() method.

    This test class focuses exclusively on the service filtering logic,
    ensuring it correctly uses DeclarationRegistryService to identify
    valid services and filter out non-service entries.
    """

    def setUp(self):
        """Set up test fixtures for each test method.

        Creates a GraphMetadataAnalyzer with mocked dependencies:
        - LoggingService: Created via MockServiceFactory for consistent logging
        - AgentFactoryService: Mock object (not used in filter_actual_services)
        - DeclarationRegistryService: Mock with configurable get_service_declaration()
        """
        # Create mock logging service using fixed factory (caches loggers)
        self.mock_logging_service = create_fixed_mock_logging_service()

        # Create mock agent factory service (not used in filter_actual_services)
        self.mock_agent_factory = Mock()

        # Create mock declaration registry service
        self.mock_declaration_registry = Mock()

        # Create analyzer instance with mocked dependencies
        self.analyzer = GraphMetadataAnalyzer(
            logging_service=self.mock_logging_service,
            agent_factory_service=self.mock_agent_factory,
            declaration_registry_service=self.mock_declaration_registry,
        )

    def test_filters_registered_services_included(self):
        """Registered services should be included in filtered results.

        When DeclarationRegistryService.get_service_declaration() returns
        a ServiceDeclaration object for a service name, that service should
        be included in the filtered set.
        """
        # Arrange: Create test input with registered services
        input_services = {"llm_service", "storage_service", "logging_service"}

        # Mock declaration registry to return ServiceDeclaration for all inputs
        def mock_get_service_declaration(service_name):
            if service_name in input_services:
                return ServiceDeclaration(
                    service_name=service_name,
                    class_path=f"agentmap.services.{service_name}",
                )
            return None

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_service_declaration
        )

        # Act: Filter the services
        result = self.analyzer.filter_actual_services(input_services)

        # Assert: All registered services should be included
        self.assertEqual(result, input_services)
        self.assertEqual(len(result), 3)

        # Verify get_service_declaration was called for each service
        self.assertEqual(
            self.mock_declaration_registry.get_service_declaration.call_count, 3
        )

    def test_filters_non_registered_entries_excluded(self):
        """Non-registered entries should be filtered out.

        When DeclarationRegistryService.get_service_declaration() returns
        None for a service name, that entry should be excluded from the
        filtered set and a debug log should be generated.
        """
        # Arrange: Create test input with non-service entries
        input_entries = {"not_a_service", "invalid_entry", "random_string"}

        # Mock declaration registry to return None for all inputs
        self.mock_declaration_registry.get_service_declaration.return_value = None

        # Act: Filter the entries
        result = self.analyzer.filter_actual_services(input_entries)

        # Assert: No entries should be included
        self.assertEqual(result, set())
        self.assertEqual(len(result), 0)

        # Verify get_service_declaration was called for each entry
        self.assertEqual(
            self.mock_declaration_registry.get_service_declaration.call_count, 3
        )

    def test_filters_empty_input_set(self):
        """Empty input set should return empty result.

        When an empty set is provided as input, the method should
        return an empty set without making any registry calls.
        """
        # Arrange: Create empty input set
        input_services = set()

        # Act: Filter the empty set
        result = self.analyzer.filter_actual_services(input_services)

        # Assert: Result should be empty
        self.assertEqual(result, set())
        self.assertEqual(len(result), 0)

        # Verify get_service_declaration was not called
        self.mock_declaration_registry.get_service_declaration.assert_not_called()

    def test_filters_mixed_set_services_and_non_services(self):
        """Mixed set should filter correctly, keeping only registered services.

        When the input contains both registered services and non-service
        entries, only the registered services should be included in the
        filtered result.
        """
        # Arrange: Create mixed input set
        valid_services = {"llm_service", "storage_service"}
        invalid_entries = {"not_a_service", "random_entry", "model_class"}
        input_mixed = valid_services | invalid_entries

        # Mock declaration registry to return ServiceDeclaration only for valid services
        def mock_get_service_declaration(service_name):
            if service_name in valid_services:
                return ServiceDeclaration(
                    service_name=service_name,
                    class_path=f"agentmap.services.{service_name}",
                )
            return None

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_service_declaration
        )

        # Act: Filter the mixed set
        result = self.analyzer.filter_actual_services(input_mixed)

        # Assert: Only valid services should be included
        self.assertEqual(result, valid_services)
        self.assertEqual(len(result), 2)
        self.assertIn("llm_service", result)
        self.assertIn("storage_service", result)
        self.assertNotIn("not_a_service", result)
        self.assertNotIn("random_entry", result)
        self.assertNotIn("model_class", result)

        # Verify get_service_declaration was called for all entries
        self.assertEqual(
            self.mock_declaration_registry.get_service_declaration.call_count, 5
        )

    def test_filters_single_valid_service(self):
        """Single valid service should be included in results.

        Edge case test: When input contains exactly one registered service,
        that service should be included in the filtered result.
        """
        # Arrange: Create single-service input
        input_services = {"llm_service"}

        # Mock declaration registry to return ServiceDeclaration
        self.mock_declaration_registry.get_service_declaration.return_value = (
            ServiceDeclaration(
                service_name="llm_service",
                class_path="agentmap.services.llm_service",
            )
        )

        # Act: Filter the single service
        result = self.analyzer.filter_actual_services(input_services)

        # Assert: Service should be included
        self.assertEqual(result, {"llm_service"})
        self.assertEqual(len(result), 1)

        # Verify get_service_declaration was called once
        self.mock_declaration_registry.get_service_declaration.assert_called_once_with(
            "llm_service"
        )

    def test_filters_single_invalid_entry(self):
        """Single invalid entry should result in empty set.

        Edge case test: When input contains exactly one non-service entry,
        the result should be an empty set.
        """
        # Arrange: Create single invalid entry input
        input_entries = {"not_a_service"}

        # Mock declaration registry to return None
        self.mock_declaration_registry.get_service_declaration.return_value = None

        # Act: Filter the invalid entry
        result = self.analyzer.filter_actual_services(input_entries)

        # Assert: Result should be empty
        self.assertEqual(result, set())
        self.assertEqual(len(result), 0)

        # Verify get_service_declaration was called once
        self.mock_declaration_registry.get_service_declaration.assert_called_once_with(
            "not_a_service"
        )

    def test_filters_debug_logging_for_filtered_entries(self):
        """Debug log should be generated for each filtered entry.

        When entries are filtered out (get_service_declaration returns None),
        a debug log message should be generated for each filtered entry
        containing the entry name.
        """
        # Arrange: Create input with non-service entries
        input_entries = {"invalid_one", "invalid_two"}

        # Mock declaration registry to return None for all inputs
        self.mock_declaration_registry.get_service_declaration.return_value = None

        # Act: Filter the entries
        result = self.analyzer.filter_actual_services(input_entries)

        # Assert: Result should be empty
        self.assertEqual(result, set())

        # Verify debug logging occurred for filtered entries
        # Access the logger that was cached during analyzer initialization
        logger = self.analyzer.logger
        debug_calls = logger.debug.call_args_list

        # Should have at least 3 debug calls: 2 for filtered entries + 1 summary
        self.assertGreaterEqual(len(debug_calls), 3)

        # Verify the summary log message contains the counts
        summary_messages = [
            str(call[0][0]) for call in debug_calls
            if "Filtered" in str(call[0][0]) and "entries to" in str(call[0][0])
        ]
        self.assertEqual(len(summary_messages), 1)
        self.assertIn("2", summary_messages[0])  # 2 input entries
        self.assertIn("0", summary_messages[0])  # 0 actual services

    def test_filters_debug_logging_summary(self):
        """Debug log summary should show correct counts.

        The method should always log a summary message showing the count
        of input entries and the count of filtered services.
        """
        # Arrange: Create mixed input
        valid_services = {"llm_service", "storage_service"}
        invalid_entries = {"not_a_service"}
        input_mixed = valid_services | invalid_entries

        # Mock declaration registry
        def mock_get_service_declaration(service_name):
            if service_name in valid_services:
                return ServiceDeclaration(
                    service_name=service_name,
                    class_path=f"agentmap.services.{service_name}",
                )
            return None

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_service_declaration
        )

        # Act: Filter the services
        result = self.analyzer.filter_actual_services(input_mixed)

        # Assert: Correct number of services filtered
        self.assertEqual(len(result), 2)

        # Verify summary log message
        # Access the logger that was cached during analyzer initialization
        logger = self.analyzer.logger
        debug_calls = logger.debug.call_args_list
        summary_messages = [
            str(call[0][0]) for call in debug_calls
            if "Filtered" in str(call[0][0]) and "entries to" in str(call[0][0])
        ]

        # Should have exactly one summary message
        self.assertEqual(len(summary_messages), 1)

        # Summary should show: 3 entries -> 2 services
        summary = summary_messages[0]
        self.assertIn("3", summary)  # 3 input entries
        self.assertIn("2", summary)  # 2 actual services

    def test_filters_preserves_service_names(self):
        """Service names should be preserved exactly as provided.

        The method should not modify service names in any way
        (no case changes, no trimming, etc.).
        """
        # Arrange: Create input with various service name formats
        input_services = {
            "LLMService",  # PascalCase
            "storage_service",  # snake_case
            "API-Gateway",  # kebab-case
        }

        # Mock declaration registry to accept all as valid
        def mock_get_service_declaration(service_name):
            return ServiceDeclaration(
                service_name=service_name,
                class_path=f"agentmap.services.{service_name}",
            )

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_service_declaration
        )

        # Act: Filter the services
        result = self.analyzer.filter_actual_services(input_services)

        # Assert: Service names should be preserved exactly
        self.assertEqual(result, input_services)
        self.assertIn("LLMService", result)  # Not "llmservice"
        self.assertIn("storage_service", result)  # Not "STORAGE_SERVICE"
        self.assertIn("API-Gateway", result)  # Not "api_gateway"

    def test_filters_large_service_set(self):
        """Method should handle large sets of services efficiently.

        Performance test: Verify the method can handle a large number
        of services without issues.
        """
        # Arrange: Create large input set (100 services)
        input_services = {f"service_{i}" for i in range(100)}

        # Mock declaration registry to return ServiceDeclaration for all
        def mock_get_service_declaration(service_name):
            return ServiceDeclaration(
                service_name=service_name,
                class_path=f"agentmap.services.{service_name}",
            )

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_service_declaration
        )

        # Act: Filter the large set
        result = self.analyzer.filter_actual_services(input_services)

        # Assert: All services should be included
        self.assertEqual(result, input_services)
        self.assertEqual(len(result), 100)

        # Verify get_service_declaration was called for each service
        self.assertEqual(
            self.mock_declaration_registry.get_service_declaration.call_count, 100
        )

    def test_filters_returns_new_set_instance(self):
        """Method should return a new set instance, not modify input.

        The method should not modify the input set and should return
        a new set instance to avoid side effects.
        """
        # Arrange: Create input set
        input_services = {"llm_service", "storage_service"}
        original_input = input_services.copy()

        # Mock declaration registry
        def mock_get_service_declaration(service_name):
            return ServiceDeclaration(
                service_name=service_name,
                class_path=f"agentmap.services.{service_name}",
            )

        self.mock_declaration_registry.get_service_declaration.side_effect = (
            mock_get_service_declaration
        )

        # Act: Filter the services
        result = self.analyzer.filter_actual_services(input_services)

        # Assert: Input should not be modified
        self.assertEqual(input_services, original_input)

        # Assert: Result should be a different instance
        self.assertIsNot(result, input_services)

        # Assert: Result should have the same content
        self.assertEqual(result, input_services)


if __name__ == "__main__":
    unittest.main()
