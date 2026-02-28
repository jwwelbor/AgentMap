"""
Unit tests for modernized CSVReaderAgent.

This test suite verifies that CSVReaderAgent works correctly after
removing ReaderOperationsMixin, ensuring clean architecture and
proper service delegation.
"""

import unittest
from unittest.mock import Mock, patch

from agentmap.agents.builtins.storage.base_storage_agent import BaseStorageAgent
from agentmap.agents.builtins.storage.csv.base_agent import CSVAgent
from agentmap.agents.builtins.storage.csv.reader import CSVReaderAgent
from agentmap.models.storage import DocumentResult
from agentmap.services.protocols import CSVCapableAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestModernizedCSVReaderAgent(unittest.TestCase):
    """Test suite for modernized CSVReaderAgent."""

    def setUp(self):
        """Set up test fixtures with mock dependencies."""
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )

        # Get mock logger for verification
        self.mock_logger = self.mock_logging_service.get_class_logger(CSVReaderAgent)

        # Create mock CSV service
        self.mock_csv_service = Mock()
        self.mock_csv_service.read.return_value = [
            {"id": "1", "name": "John", "age": "25"},
            {"id": "2", "name": "Jane", "age": "30"},
        ]

    def create_csv_reader_agent(self, **context_overrides):
        """Helper to create CSV reader agent with common configuration."""
        context = {
            "input_fields": ["file_path", "query"],
            "output_field": "csv_data",
            "description": "Test CSV reader agent",
            **context_overrides,
        }

        return CSVReaderAgent(
            name="test_csv_reader",
            prompt="test_data.csv",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

    # =============================================================================
    # 1. Agent Modernization Tests
    # =============================================================================

    def test_agent_inheritance_is_clean(self):
        """Test that agent inherits only from CSVAgent (no mixins)."""
        agent = self.create_csv_reader_agent()

        # Verify inheritance chain
        self.assertIsInstance(agent, CSVReaderAgent)
        self.assertIsInstance(agent, CSVAgent)
        self.assertIsInstance(agent, BaseStorageAgent)
        self.assertIsInstance(agent, CSVCapableAgent)

        # Check that no mixin classes are in the MRO
        mro_class_names = [cls.__name__ for cls in agent.__class__.__mro__]

        # Should NOT contain any mixin classes
        self.assertNotIn("ReaderOperationsMixin", mro_class_names)
        self.assertNotIn("WriterOperationsMixin", mro_class_names)
        self.assertNotIn("StorageErrorHandlerMixin", mro_class_names)

        # Should contain expected base classes
        self.assertIn("CSVReaderAgent", mro_class_names)
        self.assertIn("CSVAgent", mro_class_names)
        self.assertIn("BaseStorageAgent", mro_class_names)
        self.assertIn("CSVCapableAgent", mro_class_names)

    def test_agent_instantiation_without_errors(self):
        """Test that agent can be instantiated without errors."""
        try:
            agent = self.create_csv_reader_agent()
            self.assertIsNotNone(agent)
            self.assertEqual(agent.name, "test_csv_reader")
            self.assertEqual(agent.prompt, "test_data.csv")

            # Verify configuration was set correctly
            self.assertEqual(agent.context["output_field"], "csv_data")
            self.assertEqual(agent.context["input_fields"], ["file_path", "query"])
        except Exception as e:
            self.fail(f"Agent instantiation failed: {e}")

    def test_agent_has_required_methods(self):
        """Test that agent has all required methods after mixin removal."""
        agent = self.create_csv_reader_agent()

        # Core BaseStorageAgent methods should be available
        self.assertTrue(hasattr(agent, "process"))
        self.assertTrue(hasattr(agent, "_execute_operation"))
        self.assertTrue(hasattr(agent, "_validate_inputs"))
        self.assertTrue(hasattr(agent, "_log_operation_start"))
        self.assertTrue(hasattr(agent, "_handle_operation_error"))

        # CSVAgent specific methods
        self.assertTrue(hasattr(agent, "configure_csv_service"))

        # Test csv_service property works after configuration
        agent.configure_csv_service(self.mock_csv_service)
        self.assertTrue(hasattr(agent, "csv_service"))

        # Should NOT have mixin-specific methods
        self.assertFalse(hasattr(agent, "_validate_reader_inputs"))
        self.assertFalse(hasattr(agent, "_log_read_operation"))

    # =============================================================================
    # 2. Service Delegation Tests
    # =============================================================================

    def test_service_delegation_setup(self):
        """Test that service delegation is properly set up via protocol."""
        agent = self.create_csv_reader_agent()

        # Configure CSV service via protocol
        agent.configure_csv_service(self.mock_csv_service)

        # Verify the service is accessible
        self.assertEqual(agent.csv_service, self.mock_csv_service)

    def test_csv_service_not_configured_error(self):
        """Test that accessing csv_service without configuration raises clear error."""
        agent = self.create_csv_reader_agent()

        with self.assertRaises(ValueError) as cm:
            _ = agent.csv_service

        self.assertIn("CSV service not configured", str(cm.exception))
        self.assertIn("test_csv_reader", str(cm.exception))

    def test_execute_operation_calls_csv_service(self):
        """Test that _execute_operation properly delegates to csv_service."""
        agent = self.create_csv_reader_agent()
        agent.configure_csv_service(self.mock_csv_service)

        # Test inputs
        collection = "test_data.csv"
        inputs = {
            "document_id": "row_1",
            "query": {"name": "John"},
            "path": "records.0",
            "format": "dict",
            "id_field": "id",
        }

        # Execute operation
        result = agent._execute_operation(collection, inputs)

        # Verify csv_service.read was called with correct parameters
        self.mock_csv_service.read.assert_called_once_with(
            collection=collection,
            document_id="row_1",
            query={"name": "John"},
            path="records.0",
            format="dict",
            id_field="id",
        )

        # Verify result
        expected_result = [
            {"id": "1", "name": "John", "age": "25"},
            {"id": "2", "name": "Jane", "age": "30"},
        ]
        self.assertEqual(result, expected_result)

    def test_execute_operation_with_defaults(self):
        """Test _execute_operation with default parameters."""
        agent = self.create_csv_reader_agent()
        agent.configure_csv_service(self.mock_csv_service)

        collection = "simple.csv"
        inputs = {}  # Minimal inputs

        agent._execute_operation(collection, inputs)

        # Verify service called with defaults
        self.mock_csv_service.read.assert_called_once_with(
            collection=collection,
            document_id=None,
            query=None,
            path=None,
            format="records",  # Default format
            id_field="id",  # Default id_field
        )

    def test_execute_operation_with_id_alias(self):
        """Test that 'id' input parameter is mapped to 'document_id'."""
        agent = self.create_csv_reader_agent()
        agent.configure_csv_service(self.mock_csv_service)

        collection = "test.csv"
        inputs = {"id": "specific_row"}  # Using 'id' instead of 'document_id'

        agent._execute_operation(collection, inputs)

        # Verify 'id' was mapped to 'document_id'
        self.mock_csv_service.read.assert_called_once_with(
            collection=collection,
            document_id="specific_row",  # Should be mapped from 'id'
            query=None,
            path=None,
            format="records",
            id_field="id",
        )

    # =============================================================================
    # 3. Validation Tests
    # =============================================================================

    def test_validation_uses_base_agent_methods(self):
        """Test that validation uses BaseStorageAgent methods, not mixin methods."""
        agent = self.create_csv_reader_agent()

        # Mock get_collection to return a test CSV path
        with patch.object(agent, "get_collection", return_value="nonexistent.csv"):
            inputs = {"file_path": "nonexistent.csv"}

            # Since file existence validation has been moved to the service layer,
            # _validate_inputs should complete without raising FileNotFoundError
            try:
                agent._validate_inputs(inputs)
                # Validation should pass at the agent level
            except ValueError as e:
                # Only ValueError should be raised for missing collection
                if "collection" not in str(e):
                    self.fail(f"Unexpected ValueError: {e}")
            except FileNotFoundError:
                self.fail(
                    "FileNotFoundError should not be raised at agent level - validation moved to service layer"
                )

    def test_csv_extension_validation_warning(self):
        """Test that non-CSV extension generates warning but doesn't fail."""
        agent = self.create_csv_reader_agent()

        with patch.object(agent, "get_collection", return_value="data.txt"):
            with patch("os.path.exists", return_value=True):
                inputs = {"file_path": "data.txt"}

                # Should not raise exception but log warning
                try:
                    agent._validate_inputs(inputs)
                except Exception as e:
                    self.fail(f"Validation failed unexpectedly: {e}")

                # Check that warning was logged
                logger_calls = self.mock_logger.calls
                warning_calls = [call for call in logger_calls if call[0] == "warning"]
                warning_logged = any(
                    "does not end with .csv" in call[1] for call in warning_calls
                )
                self.assertTrue(
                    warning_logged, "Expected CSV extension warning to be logged"
                )

    def test_missing_collection_validation(self):
        """Test that missing collection parameter raises ValueError."""
        agent = self.create_csv_reader_agent()

        with patch.object(agent, "get_collection", return_value=None):
            inputs = {}

            with self.assertRaises(ValueError) as cm:
                agent._validate_inputs(inputs)

            self.assertIn("Missing required 'collection' parameter", str(cm.exception))

    # =============================================================================
    # 4. Error Handling Tests
    # =============================================================================

    def test_error_handling_uses_base_agent_methods(self):
        """Test that error handling uses BaseStorageAgent._handle_operation_error."""
        agent = self.create_csv_reader_agent()

        # Create a test error
        test_error = FileNotFoundError("Test CSV file not found")
        collection = "missing.csv"
        inputs = {"file_path": "missing.csv"}

        # Call the error handler
        result = agent._handle_operation_error(test_error, collection, inputs)

        # Should return DocumentResult (from BaseStorageAgent method)
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertIn("CSV file not found", result.error)
        self.assertEqual(result.file_path, collection)

    def test_csv_specific_error_handling(self):
        """Test that CSV-specific errors are handled correctly."""
        agent = self.create_csv_reader_agent()

        test_error = PermissionError("Permission denied")
        collection = "protected.csv"
        inputs = {"file_path": "protected.csv"}

        # Call the error handler
        result = agent._handle_operation_error(test_error, collection, inputs)

        # Should return DocumentResult
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertEqual(result.file_path, collection)

    def test_generic_error_handling_delegates_to_base_agent(self):
        """Test that generic errors delegate to BaseStorageAgent._handle_operation_error."""
        agent = self.create_csv_reader_agent()

        # Mock the super()._handle_operation_error method
        with patch.object(
            BaseStorageAgent, "_handle_operation_error"
        ) as mock_base_error:
            expected_result = DocumentResult(success=False, error="Base agent error")
            mock_base_error.return_value = expected_result

            test_error = RuntimeError("Generic runtime error")
            collection = "test.csv"
            inputs = {"file_path": "test.csv"}

            # Call the error handler
            result = agent._handle_operation_error(test_error, collection, inputs)

            # Verify base agent method was called
            mock_base_error.assert_called_once_with(test_error, collection, inputs)
            self.assertEqual(result, expected_result)

    # =============================================================================
    # 5. Integration Tests
    # =============================================================================

    def test_csv_file_existence_validation_integration(self):
        """Test that file existence validation is handled at service layer."""
        agent = self.create_csv_reader_agent()
        agent.configure_csv_service(self.mock_csv_service)

        # File existence is no longer validated at agent level
        with patch.object(agent, "get_collection", return_value="existing.csv"):
            inputs = {"file_path": "existing.csv"}

            # Should not raise any exceptions at agent validation level
            try:
                agent._validate_inputs(inputs)
            except Exception as e:
                self.fail(f"Validation failed unexpectedly: {e}")

    def test_logging_integration(self):
        """Test that logging works correctly after mixin removal."""
        agent = self.create_csv_reader_agent()

        collection = "test.csv"
        inputs = {"format": "records"}

        # Call log operation start
        agent._log_operation_start(collection, inputs)

        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]

        # Should have logged the CSV read operation
        logged_messages = [call[1] for call in debug_calls]
        read_logged = any(
            "Starting CSV read operation" in msg for msg in logged_messages
        )
        self.assertTrue(
            read_logged, f"Expected CSV read operation logged, got: {logged_messages}"
        )

    def test_service_configuration_via_protocol(self):
        """Test that CSV service can be configured via CSVCapableAgent protocol."""
        agent = self.create_csv_reader_agent()

        # Verify agent implements the protocol
        self.assertIsInstance(agent, CSVCapableAgent)

        # Configure service
        agent.configure_csv_service(self.mock_csv_service)

        # Verify configuration worked
        self.assertEqual(agent.csv_service, self.mock_csv_service)
        self.assertEqual(
            agent._client, self.mock_csv_service
        )  # Should also set as main client

    def test_full_operation_workflow(self):
        """Test complete CSV read operation workflow."""
        agent = self.create_csv_reader_agent()
        agent.configure_csv_service(self.mock_csv_service)

        # Mock file existence (no longer validated at agent level)
        with patch.object(agent, "get_collection", return_value="test.csv"):

            # Test inputs
            collection = "test.csv"
            inputs = {
                "file_path": "test.csv",
                "format": "dict",
                "query": {"status": "active"},
            }

            # Execute full workflow
            agent._validate_inputs(inputs)
            agent._log_operation_start(collection, inputs)
            result = agent._execute_operation(collection, inputs)

            # Verify service was called correctly
            self.mock_csv_service.read.assert_called_once_with(
                collection=collection,
                document_id=None,
                query={"status": "active"},
                path=None,
                format="dict",
                id_field="id",
            )

            # Verify result
            expected_result = [
                {"id": "1", "name": "John", "age": "25"},
                {"id": "2", "name": "Jane", "age": "30"},
            ]
            self.assertEqual(result, expected_result)

    def test_configuration_properties_preserved(self):
        """Test that CSV processing configuration is preserved after modernization."""
        custom_config = {
            "input_fields": ["csv_file", "filter"],
            "output_field": "csv_records",
            "description": "Custom CSV reader",
            "id_field": "row_id",
        }

        agent = self.create_csv_reader_agent(**custom_config)

        # Verify configuration was preserved
        self.assertEqual(agent.context["input_fields"], ["csv_file", "filter"])
        self.assertEqual(agent.context["output_field"], "csv_records")
        self.assertEqual(agent.context["description"], "Custom CSV reader")
        self.assertEqual(agent.context["id_field"], "row_id")

    # =============================================================================
    # 6. Service Layer Validation Tests
    # =============================================================================

    def test_file_not_found_handled_by_service_layer(self):
        """Test that FileNotFoundError is now handled at the service layer."""
        agent = self.create_csv_reader_agent()

        # Configure service to raise FileNotFoundError
        self.mock_csv_service.read.side_effect = FileNotFoundError(
            "File not found at service layer"
        )
        agent.configure_csv_service(self.mock_csv_service)

        collection = "nonexistent.csv"
        inputs = {"file_path": "nonexistent.csv"}

        # The error should be caught and handled by _handle_operation_error
        result = agent._handle_operation_error(
            FileNotFoundError("File not found at service layer"), collection, inputs
        )

        # Should return DocumentResult with error info
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertIn("CSV file not found", result.error)


if __name__ == "__main__":
    unittest.main(verbosity=2)
