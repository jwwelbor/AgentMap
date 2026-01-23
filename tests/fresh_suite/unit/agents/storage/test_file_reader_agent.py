"""
Unit tests for modernized FileReaderAgent.

This test suite verifies that FileReaderAgent works correctly after
removing both ReaderOperationsMixin and StorageErrorHandlerMixin,
ensuring clean architecture and proper error handling.
"""

import os
import unittest
from typing import Any, Dict
from unittest.mock import Mock, patch

from agentmap.agents.builtins.storage.base_storage_agent import BaseStorageAgent
from agentmap.agents.builtins.storage.file.reader import FileReaderAgent
from agentmap.models.storage import DocumentResult
from agentmap.services.protocols import FileCapableAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestModernizedFileReaderAgent(unittest.TestCase):
    """Test suite for modernized FileReaderAgent."""

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
        self.mock_logger = self.mock_logging_service.get_class_logger(FileReaderAgent)

        # Create mock file service
        self.mock_file_service = Mock()
        self.mock_file_service.read.return_value = "Sample file content data"

    def create_file_reader_agent(self, **context_overrides):
        """Helper to create file reader agent with common configuration."""
        context = {
            "input_fields": ["file_path", "query"],
            "output_field": "file_data",
            "description": "Test file reader agent",
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "should_split": False,
            "include_metadata": True,
            **context_overrides,
        }

        return FileReaderAgent(
            name="test_file_reader",
            prompt="test_file.txt",
            context=context,
            logger=self.mock_logger,
            execution_tracker_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

    # =============================================================================
    # 1. Agent Modernization Tests
    # =============================================================================

    def test_agent_inheritance_is_clean(self):
        """Test that agent inherits only from BaseStorageAgent and FileCapableAgent (no mixins)."""
        agent = self.create_file_reader_agent()

        # Verify inheritance chain
        self.assertIsInstance(agent, FileReaderAgent)
        self.assertIsInstance(agent, BaseStorageAgent)
        self.assertIsInstance(agent, FileCapableAgent)

        # Check that no mixin classes are in the MRO
        mro_class_names = [cls.__name__ for cls in agent.__class__.__mro__]

        # Should NOT contain any mixin classes
        self.assertNotIn("ReaderOperationsMixin", mro_class_names)
        self.assertNotIn("StorageErrorHandlerMixin", mro_class_names)
        self.assertNotIn("WriterOperationsMixin", mro_class_names)

        # Should contain expected base classes
        self.assertIn("FileReaderAgent", mro_class_names)
        self.assertIn("BaseStorageAgent", mro_class_names)
        self.assertIn("FileCapableAgent", mro_class_names)

    def test_agent_instantiation_without_errors(self):
        """Test that agent can be instantiated without errors."""
        try:
            agent = self.create_file_reader_agent()
            self.assertIsNotNone(agent)
            self.assertEqual(agent.name, "test_file_reader")
            self.assertEqual(agent.prompt, "test_file.txt")

            # Verify configuration was set correctly
            self.assertEqual(agent.chunk_size, 1000)
            self.assertEqual(agent.chunk_overlap, 200)
            self.assertFalse(agent.should_split)
            self.assertTrue(agent.include_metadata)
        except Exception as e:
            self.fail(f"Agent instantiation failed: {e}")

    def test_agent_has_required_methods(self):
        """Test that agent has all required methods after mixin removal."""
        agent = self.create_file_reader_agent()

        # Core BaseStorageAgent methods should be available
        self.assertTrue(hasattr(agent, "process"))
        self.assertTrue(hasattr(agent, "_execute_operation"))
        self.assertTrue(hasattr(agent, "_validate_inputs"))
        self.assertTrue(hasattr(agent, "_log_operation_start"))
        self.assertTrue(hasattr(agent, "_handle_operation_error"))

        # FileCapableAgent protocol method
        self.assertTrue(hasattr(agent, "_initialize_client"))

        # Should NOT have mixin-specific methods
        self.assertFalse(hasattr(agent, "_validate_reader_inputs"))
        self.assertFalse(hasattr(agent, "_handle_storage_error"))

    # =============================================================================
    # 2. Service Delegation Tests
    # =============================================================================

    def test_service_delegation_setup(self):
        """Test that service delegation is properly set up."""
        agent = self.create_file_reader_agent()

        # Mock the file_service property
        agent.file_service = self.mock_file_service

        # Verify the service is accessible
        self.assertEqual(agent.file_service, self.mock_file_service)

    def test_execute_operation_calls_file_service(self):
        """Test that _execute_operation properly delegates to file_service."""
        agent = self.create_file_reader_agent()
        agent.file_service = self.mock_file_service

        # Test inputs
        collection = "test_document.pdf"
        inputs = {
            "document_id": "doc_456",
            "query": {"page": 1},
            "path": "content.text",
            "format": "text",
        }

        # Execute operation
        result = agent._execute_operation(collection, inputs)

        # Verify file_service.read was called with correct parameters
        self.mock_file_service.read.assert_called_once_with(
            collection=collection,
            document_id="doc_456",
            query={"page": 1},
            path="content.text",
            format="text",
        )

        # Verify result
        self.assertEqual(result, "Sample file content data")

    def test_execute_operation_with_defaults(self):
        """Test _execute_operation with default parameters."""
        agent = self.create_file_reader_agent()
        agent.file_service = self.mock_file_service

        collection = "simple.txt"
        inputs = {}  # Minimal inputs

        result = agent._execute_operation(collection, inputs)

        # Verify service called with defaults
        self.mock_file_service.read.assert_called_once_with(
            collection=collection,
            document_id=None,
            query=None,
            path=None,
            format="default",  # Default format
        )

    # =============================================================================
    # 3. Error Handling Tests (Critical for FileReaderAgent)
    # =============================================================================

    def test_validation_uses_base_agent_methods(self):
        """Test that validation uses BaseStorageAgent methods, not mixin methods."""
        agent = self.create_file_reader_agent()

        # Mock get_collection to return a test file path
        with patch.object(agent, "get_collection", return_value="nonexistent.txt"):
            with patch("os.path.exists", return_value=False):
                inputs = {"file_path": "nonexistent.txt"}

                # Should raise FileNotFoundError due to BaseStorageAgent validation
                with self.assertRaises(FileNotFoundError) as cm:
                    agent._validate_inputs(inputs)

                self.assertIn("File not found", str(cm.exception))

    def test_error_handling_uses_base_agent_methods(self):
        """Test that error handling uses BaseStorageAgent._handle_operation_error instead of mixin methods."""
        agent = self.create_file_reader_agent()

        # Create a test error
        test_error = FileNotFoundError("Test file not found")
        collection = "missing.txt"
        inputs = {"file_path": "missing.txt"}

        # Call the error handler
        result = agent._handle_operation_error(test_error, collection, inputs)

        # Should return DocumentResult (from BaseStorageAgent method)
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertIn("File not found", result.error)
        self.assertEqual(result.file_path, collection)

    def test_permission_error_handling(self):
        """Test that permission errors are handled correctly."""
        agent = self.create_file_reader_agent()

        test_error = PermissionError("Permission denied")
        collection = "protected.txt"
        inputs = {"file_path": "protected.txt"}

        # Call the error handler
        result = agent._handle_operation_error(test_error, collection, inputs)

        # Should return DocumentResult with permission error mapped to "file not found"
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertIn(
            "File not found", result.error
        )  # FileReaderAgent maps permission to file not found

        # Verify that the actual permission error was logged for debugging
        logger_calls = self.mock_logger.calls
        warning_calls = [call for call in logger_calls if call[0] == "warning"]

        # Should have logged the permission error
        logged_messages = [call[1] for call in warning_calls]
        permission_logged = any(
            "Permission denied accessing file: protected.txt" in msg
            for msg in logged_messages
        )
        self.assertTrue(
            permission_logged,
            f"Expected permission error to be logged, got warning calls: {logged_messages}",
        )

    def test_generic_error_handling_delegates_to_base_agent(self):
        """Test that generic errors delegate to BaseStorageAgent._handle_operation_error."""
        agent = self.create_file_reader_agent()

        # Mock the super()._handle_operation_error method
        with patch.object(
            BaseStorageAgent, "_handle_operation_error"
        ) as mock_base_error:
            expected_result = DocumentResult(success=False, error="Base agent error")
            mock_base_error.return_value = expected_result

            test_error = RuntimeError("Generic runtime error")
            collection = "test.txt"
            inputs = {"file_path": "test.txt"}

            # Call the error handler
            result = agent._handle_operation_error(test_error, collection, inputs)

            # Verify base agent method was called
            mock_base_error.assert_called_once_with(test_error, collection, inputs)
            self.assertEqual(result, expected_result)

    # =============================================================================
    # 4. Integration Tests
    # =============================================================================

    def test_file_existence_validation_integration(self):
        """Test file existence validation in _validate_inputs."""
        agent = self.create_file_reader_agent()

        # Mock file existence check
        with patch("os.path.exists", return_value=True):
            with patch.object(agent, "get_collection", return_value="existing.txt"):
                inputs = {"file_path": "existing.txt"}

                # Should not raise any exceptions
                try:
                    agent._validate_inputs(inputs)
                except Exception as e:
                    self.fail(f"Validation failed unexpectedly: {e}")

    def test_logging_integration(self):
        """Test that logging works correctly after mixin removal."""
        agent = self.create_file_reader_agent()

        collection = "test.pdf"
        inputs = {"format": "text"}

        # Call log operation start
        agent._log_operation_start(collection, inputs)

        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]

        # Should have logged the read operation
        logged_messages = [call[1] for call in debug_calls]
        read_logged = any(
            "Starting read operation on file" in msg for msg in logged_messages
        )
        self.assertTrue(
            read_logged, f"Expected read operation logged, got: {logged_messages}"
        )

    def test_configuration_properties_preserved(self):
        """Test that file processing configuration is preserved after modernization."""
        custom_config = {
            "chunk_size": 2000,
            "chunk_overlap": 400,
            "should_split": True,
            "include_metadata": False,
        }

        agent = self.create_file_reader_agent(**custom_config)

        # Verify configuration was preserved
        self.assertEqual(agent.chunk_size, 2000)
        self.assertEqual(agent.chunk_overlap, 400)
        self.assertTrue(agent.should_split)
        self.assertFalse(agent.include_metadata)


if __name__ == "__main__":
    unittest.main(verbosity=2)
