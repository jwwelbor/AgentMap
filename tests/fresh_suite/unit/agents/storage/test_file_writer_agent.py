"""
Unit tests for modernized FileWriterAgent.

This test suite verifies that FileWriterAgent works correctly after
removing both WriterOperationsMixin and StorageErrorHandlerMixin,
ensuring clean architecture and proper service delegation.
"""

import unittest
from unittest.mock import Mock, patch

from agentmap.agents.builtins.storage.base_storage_agent import BaseStorageAgent
from agentmap.agents.builtins.storage.file.writer import FileWriterAgent
from agentmap.models.storage import DocumentResult, WriteMode
from agentmap.services.protocols import FileCapableAgent
from tests.utils.mock_service_factory import MockServiceFactory


class TestModernizedFileWriterAgent(unittest.TestCase):
    """Test suite for modernized FileWriterAgent."""

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
        self.mock_logger = self.mock_logging_service.get_class_logger(FileWriterAgent)

        # Create mock file service with realistic write response
        self.mock_file_service = Mock()
        self.mock_write_result = DocumentResult(
            success=True,
            file_path="test_output.txt",
            data="Content written successfully",
        )
        self.mock_file_service.write.return_value = self.mock_write_result

    def create_file_writer_agent(self, **context_overrides):
        """Helper to create file writer agent with common configuration."""
        context = {
            "input_fields": ["file_path", "data"],
            "output_field": "write_result",
            "description": "Test file writer agent",
            "encoding": "utf-8",
            "newline": None,
            **context_overrides,
        }

        return FileWriterAgent(
            name="test_file_writer",
            prompt="output.txt",
            context=context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

    # =============================================================================
    # 1. Agent Modernization Tests
    # =============================================================================

    def test_agent_inheritance_is_clean(self):
        """Test that agent inherits only from BaseStorageAgent and FileCapableAgent (no mixins)."""
        agent = self.create_file_writer_agent()

        # Verify inheritance chain
        self.assertIsInstance(agent, FileWriterAgent)
        self.assertIsInstance(agent, BaseStorageAgent)
        self.assertIsInstance(agent, FileCapableAgent)

        # Check that no mixin classes are in the MRO
        mro_class_names = [cls.__name__ for cls in agent.__class__.__mro__]

        # Should NOT contain any mixin classes
        self.assertNotIn("WriterOperationsMixin", mro_class_names)
        self.assertNotIn("ReaderOperationsMixin", mro_class_names)
        self.assertNotIn("StorageErrorHandlerMixin", mro_class_names)

        # Should contain expected base classes
        self.assertIn("FileWriterAgent", mro_class_names)
        self.assertIn("BaseStorageAgent", mro_class_names)
        self.assertIn("FileCapableAgent", mro_class_names)

    def test_agent_instantiation_without_errors(self):
        """Test that agent can be instantiated without errors."""
        try:
            agent = self.create_file_writer_agent()
            self.assertIsNotNone(agent)
            self.assertEqual(agent.name, "test_file_writer")
            self.assertEqual(agent.prompt, "output.txt")

            # Verify configuration was set correctly
            self.assertEqual(agent.encoding, "utf-8")
            self.assertIsNone(agent.newline)  # System default
        except Exception as e:
            self.fail(f"Agent instantiation failed: {e}")

    def test_agent_has_required_methods(self):
        """Test that agent has all required methods for current functionality."""
        agent = self.create_file_writer_agent()

        # Core BaseStorageAgent methods should be available
        self.assertTrue(hasattr(agent, "process"))
        self.assertTrue(hasattr(agent, "_execute_operation"))
        self.assertTrue(hasattr(agent, "_validate_inputs"))
        self.assertTrue(hasattr(agent, "_log_operation_start"))
        self.assertTrue(hasattr(agent, "_handle_operation_error"))
        self.assertTrue(hasattr(agent, "_initialize_client"))

        # FileCapableAgent protocol properties
        self.assertTrue(hasattr(agent, "file_service"))

        # Should NOT have mixin-specific methods
        self.assertFalse(hasattr(agent, "_validate_writer_inputs"))
        self.assertFalse(hasattr(agent, "_handle_storage_error_with_mixin"))

    # =============================================================================
    # 2. Service Delegation Tests
    # =============================================================================

    def test_service_delegation_setup(self):
        """Test that service delegation is properly set up."""
        agent = self.create_file_writer_agent()

        # Set mock file service directly (simulating dependency injection)
        agent.file_service = self.mock_file_service

        # Verify the service is accessible
        self.assertIsNotNone(agent.file_service)
        self.assertEqual(agent.file_service, self.mock_file_service)

    def test_file_service_initialization(self):
        """Test that configure_file_service properly sets up the service."""
        agent = self.create_file_writer_agent()

        # Initially should be None
        self.assertIsNone(agent.file_service)

        # After configuration should be set
        agent.configure_file_service(self.mock_file_service)
        self.assertIsNotNone(agent.file_service)
        self.assertEqual(agent.file_service, self.mock_file_service)
        self.assertEqual(agent._client, self.mock_file_service)

    def test_execute_operation_calls_file_service(self):
        """Test that _execute_operation properly delegates to file_service."""
        agent = self.create_file_writer_agent()
        agent.file_service = self.mock_file_service

        # Test inputs
        collection = "test_output.txt"
        inputs = {
            "data": "Test file content\nSecond line",
            "mode": "write",
            "document_id": "doc_123",
            "path": "content.text",
        }

        # Execute operation
        result = agent._execute_operation(collection, inputs)

        # Verify file_service.write was called with correct parameters
        self.mock_file_service.write.assert_called_once_with(
            collection=collection,
            data="Test file content\nSecond line",
            document_id="doc_123",
            mode=WriteMode.WRITE,
            path="content.text",
        )

        # Verify result
        self.assertEqual(result, self.mock_write_result)

    def test_execute_operation_with_defaults(self):
        """Test _execute_operation with default parameters."""
        agent = self.create_file_writer_agent()
        agent.file_service = self.mock_file_service

        collection = "simple.txt"
        inputs = {"data": "Simple content"}  # Minimal inputs

        agent._execute_operation(collection, inputs)

        # Verify service called with defaults
        self.mock_file_service.write.assert_called_once_with(
            collection=collection,
            data="Simple content",
            document_id=None,
            mode=WriteMode.APPEND,  # Default mode
            path=None,
        )

    def test_execute_operation_different_write_modes(self):
        """Test _execute_operation with different write modes."""
        agent = self.create_file_writer_agent()
        agent.file_service = self.mock_file_service

        test_cases = [
            ("write", WriteMode.WRITE),
            ("append", WriteMode.APPEND),
            ("update", WriteMode.UPDATE),
            ("delete", WriteMode.DELETE),
        ]

        for mode_str, expected_mode in test_cases:
            with self.subTest(mode=mode_str):
                self.mock_file_service.reset_mock()

                collection = f"test_{mode_str}.txt"
                inputs = {"data": f"Content for {mode_str}", "mode": mode_str}

                agent._execute_operation(collection, inputs)

                self.mock_file_service.write.assert_called_once_with(
                    collection=collection,
                    data=f"Content for {mode_str}",
                    document_id=None,
                    mode=expected_mode,
                    path=None,
                )

    def test_execute_operation_invalid_mode(self):
        """Test _execute_operation with invalid write mode."""
        agent = self.create_file_writer_agent()
        agent.file_service = self.mock_file_service

        collection = "test.txt"
        inputs = {"data": "Test content", "mode": "invalid_mode"}

        result = agent._execute_operation(collection, inputs)

        # Should return DocumentResult with error, not call service
        self.mock_file_service.write.assert_not_called()
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertIn("invalid_mode", result.error)

    # =============================================================================
    # 3. Validation Tests
    # =============================================================================

    def test_validation_uses_base_agent_methods(self):
        """Test that validation uses BaseStorageAgent methods, not mixin methods."""
        agent = self.create_file_writer_agent()

        # Mock get_collection to return a test file path
        with patch.object(agent, "get_collection", return_value="test_output.txt"):
            inputs = {"data": "Test content", "mode": "write"}

            # Should not raise any exceptions for valid inputs
            try:
                agent._validate_inputs(inputs)
            except Exception as e:
                self.fail(f"Validation failed unexpectedly: {e}")

    def test_validation_missing_data_for_write_operations(self):
        """Test that validation fails when data is missing for write operations."""
        agent = self.create_file_writer_agent()

        with patch.object(agent, "get_collection", return_value="test.txt"):
            # Test different modes that require data
            for mode in ["write", "append", "update"]:
                with self.subTest(mode=mode):
                    inputs = {"mode": mode}  # Missing data

                    with self.assertRaises(ValueError) as cm:
                        agent._validate_inputs(inputs)

                    self.assertIn(
                        "Missing required 'data' parameter", str(cm.exception)
                    )

    def test_validation_allows_missing_data_for_delete(self):
        """Test that validation allows missing data for delete operations."""
        agent = self.create_file_writer_agent()

        with patch.object(agent, "get_collection", return_value="test.txt"):
            inputs = {"mode": "delete"}  # No data needed for delete

            # Should not raise any exceptions
            try:
                agent._validate_inputs(inputs)
            except Exception as e:
                self.fail(f"Validation failed unexpectedly for delete operation: {e}")

    # =============================================================================
    # 4. Error Handling Tests (Critical for FileWriterAgent)
    # =============================================================================

    def test_file_not_found_error_handling(self):
        """Test that FileNotFoundError is handled correctly."""
        agent = self.create_file_writer_agent()

        test_error = FileNotFoundError("File not found")
        collection = "missing_dir/test.txt"
        inputs = {"data": "Test content"}

        # Call the error handler
        result = agent._handle_operation_error(test_error, collection, inputs)

        # Should return DocumentResult with file not found error
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertIn("File not found", result.error)
        self.assertEqual(result.file_path, collection)

    def test_permission_error_handling(self):
        """Test that PermissionError is handled correctly."""
        agent = self.create_file_writer_agent()

        test_error = PermissionError("Permission denied")
        collection = "protected.txt"
        inputs = {"data": "Test content"}

        # Call the error handler
        result = agent._handle_operation_error(test_error, collection, inputs)

        # Should return DocumentResult with permission error
        self.assertIsInstance(result, DocumentResult)
        self.assertFalse(result.success)
        self.assertIn("Permission denied", result.error)
        self.assertEqual(result.file_path, collection)

    def test_generic_error_handling_delegates_to_base_agent(self):
        """Test that generic errors delegate to BaseStorageAgent._handle_operation_error."""
        agent = self.create_file_writer_agent()

        # Mock the super()._handle_operation_error method
        with patch.object(
            BaseStorageAgent, "_handle_operation_error"
        ) as mock_base_error:
            expected_result = DocumentResult(success=False, error="Base agent error")
            mock_base_error.return_value = expected_result

            test_error = RuntimeError("Generic runtime error")
            collection = "test.txt"
            inputs = {"data": "Test content"}

            # Call the error handler
            result = agent._handle_operation_error(test_error, collection, inputs)

            # Verify base agent method was called
            mock_base_error.assert_called_once_with(test_error, collection, inputs)
            self.assertEqual(result, expected_result)

    # =============================================================================
    # 5. Logging Tests
    # =============================================================================

    def test_logging_operation_start(self):
        """Test that operation start logging works correctly."""
        agent = self.create_file_writer_agent()

        collection = "output.txt"
        inputs = {"data": "Test content", "mode": "append"}

        # Call log operation start
        agent._log_operation_start(collection, inputs)

        # Verify logging occurred
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]

        # Should have logged the write operation with mode
        logged_messages = [call[1] for call in debug_calls]
        write_logged = any(
            "Starting write operation (mode: append) on file: output.txt" in msg
            for msg in logged_messages
        )
        self.assertTrue(
            write_logged, f"Expected write operation logged, got: {logged_messages}"
        )

    def test_logging_default_mode(self):
        """Test logging with default write mode."""
        agent = self.create_file_writer_agent()

        collection = "output.txt"
        inputs = {"data": "Test content"}  # No explicit mode

        agent._log_operation_start(collection, inputs)

        # Verify default mode is logged
        logger_calls = self.mock_logger.calls
        debug_calls = [call for call in logger_calls if call[0] == "debug"]
        logged_messages = [call[1] for call in debug_calls]
        write_logged = any(
            "Starting write operation (mode: write) on file" in msg
            for msg in logged_messages
        )
        self.assertTrue(
            write_logged, f"Expected default write mode logged, got: {logged_messages}"
        )

    # =============================================================================
    # 6. Integration Tests
    # =============================================================================

    def test_file_write_integration(self):
        """Test complete file write operation workflow."""
        agent = self.create_file_writer_agent()
        agent.file_service = self.mock_file_service

        # Test inputs
        collection = "integration_test.txt"
        inputs = {"data": "Integration test content\nMultiple lines", "mode": "write"}

        # Execute full workflow
        agent._validate_inputs(inputs)
        agent._log_operation_start(collection, inputs)
        result = agent._execute_operation(collection, inputs)

        # Verify service was called correctly
        self.mock_file_service.write.assert_called_once_with(
            collection=collection,
            data="Integration test content\nMultiple lines",
            document_id=None,
            mode=WriteMode.WRITE,
            path=None,
        )

        # Verify result
        self.assertEqual(result, self.mock_write_result)

    def test_configuration_properties_preserved(self):
        """Test that file processing configuration is preserved after modernization."""
        custom_config = {
            "encoding": "latin-1",
            "newline": "\r\n",
            "input_fields": ["file_path", "content"],
            "output_field": "file_result",
        }

        agent = self.create_file_writer_agent(**custom_config)

        # Verify configuration was preserved
        self.assertEqual(agent.encoding, "latin-1")
        self.assertEqual(agent.newline, "\r\n")
        self.assertEqual(agent.context["input_fields"], ["file_path", "content"])
        self.assertEqual(agent.context["output_field"], "file_result")

    def test_run_method_state_management(self):
        """Test that run method properly manages state for content preparation."""
        agent = self.create_file_writer_agent()

        # Mock the parent run method
        with patch.object(BaseStorageAgent, "run") as mock_super_run:
            mock_super_run.return_value = {"result": "success"}

            test_state = {"input_data": "test content"}

            # Initially no state stored
            self.assertIsNone(agent._current_state)

            # Call run method
            result = agent.run(test_state)

            # Verify state was passed to parent and cleared after
            mock_super_run.assert_called_once_with(test_state)
            self.assertEqual(result, {"result": "success"})
            self.assertIsNone(agent._current_state)  # Should be cleared

    def test_run_method_state_cleanup_on_exception(self):
        """Test that run method cleans up state even when exception occurs."""
        agent = self.create_file_writer_agent()

        # Mock the parent run method to raise exception
        with patch.object(BaseStorageAgent, "run") as mock_super_run:
            mock_super_run.side_effect = RuntimeError("Test error")

            test_state = {"input_data": "test content"}

            # Call run method and expect exception
            with self.assertRaises(RuntimeError):
                agent.run(test_state)

            # Verify state was cleaned up despite exception
            self.assertIsNone(agent._current_state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
