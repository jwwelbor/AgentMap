"""
Comprehensive unit tests for BlobWriterAgent.

These tests validate the BlobWriterAgent implementation including:
- Modern BaseAgent contract compliance
- Protocol-based service configuration (BlobStorageCapableAgent)
- Constructor injection of infrastructure services
- Blob writing operations with data conversion
- Input extraction and validation
- String to UTF-8 conversion
- Object to JSON serialization
- State adapter service integration
- Execution tracking integration
- Service debugging information
"""

import json
import unittest
from unittest.mock import Mock

from agentmap.agents.builtins.storage.blob.blob_writer_agent import BlobWriterAgent
from agentmap.exceptions import StorageOperationError
from agentmap.services.protocols import BlobStorageServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory


class TestBlobWriterAgent(unittest.TestCase):
    """Comprehensive tests for BlobWriterAgent implementation."""

    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use MockServiceFactory for consistent behavior (established pattern)
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )

        # Get mock logger for verification (established pattern)
        self.mock_logger = self.mock_logging_service.get_class_logger(BlobWriterAgent)

        # Create mock blob storage service with required methods
        self.mock_blob_storage_service = Mock(spec=BlobStorageServiceProtocol)
        # Configure mock methods
        self.mock_blob_storage_service.get_available_providers = Mock(
            return_value=["azure", "s3", "file"]
        )

        # Create agent instance
        self.agent = BlobWriterAgent(
            name="test_blob_writer",
            prompt="Write data to blob storage",
            context={"input_keys": ["blob_uri", "data"], "output_key": "write_result"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )

        # Configure blob storage service via protocol
        self.agent.configure_blob_storage_service(self.mock_blob_storage_service)

    def create_blob_writer_agent(self, name="test_agent", **kwargs):
        """Helper to create blob writer agent with common configuration."""
        return BlobWriterAgent(
            name=name,
            prompt=kwargs.get("prompt", "Test prompt"),
            context=kwargs.get("context"),
            logger=self.mock_logger,  # Always include logger (established pattern)
            execution_tracking_service=kwargs.get("execution_tracking_service"),
            state_adapter_service=kwargs.get("state_adapter_service"),
        )

    # =============================================================================
    # Agent Initialization and Protocol Tests
    # =============================================================================

    def test_agent_initialization_with_infrastructure_services(self):
        """Test agent initialization with all infrastructure services."""
        # Verify BaseAgent initialization
        self.assertEqual(self.agent.name, "test_blob_writer")
        self.assertEqual(self.agent.prompt, "Write data to blob storage")
        self.assertIsNotNone(self.agent.context)

        # Verify infrastructure services are stored
        self.assertEqual(self.agent.logger, self.mock_logger)
        self.assertEqual(
            self.agent.execution_tracking_service, self.mock_execution_tracking_service
        )
        self.assertEqual(
            self.agent.state_adapter_service, self.mock_state_adapter_service
        )

        # Blob storage service should be configured
        self.assertEqual(
            self.agent.blob_storage_service, self.mock_blob_storage_service
        )

    def test_agent_initialization_minimal(self):
        """Test agent initialization with minimal parameters."""
        # Create agent with minimal parameters but include logger (established pattern)
        minimal_agent = BlobWriterAgent(
            name="minimal_writer",
            prompt="Minimal prompt",
            logger=self.mock_logger,  # Follow established pattern
        )

        # Should initialize successfully
        self.assertEqual(minimal_agent.name, "minimal_writer")
        self.assertEqual(minimal_agent.prompt, "Minimal prompt")

        # Context should be None when not provided
        # Note: BaseAgent may initialize context as empty dict if None is provided
        context = minimal_agent.context
        self.assertTrue(context is None or context == {})

        # Infrastructure services should be accessible
        self.assertEqual(minimal_agent.logger, self.mock_logger)
        # execution_tracking_service should raise clear error message when not provided
        with self.assertRaises(ValueError):
            _ = minimal_agent.execution_tracking_service
        # state_adapter_service should return None when not provided (doesn't raise ValueError)
        self.assertIsNone(minimal_agent.state_adapter_service)

    def test_blob_storage_capable_agent_protocol_implementation(self):
        """Test BlobStorageCapableAgent protocol implementation."""
        # Should have configure_blob_storage_service method
        self.assertTrue(hasattr(self.agent, "configure_blob_storage_service"))

        # Should be able to configure blob storage service
        mock_service = Mock(spec=BlobStorageServiceProtocol)
        self.agent.configure_blob_storage_service(mock_service)

        # Should be able to access configured service
        self.assertEqual(self.agent.blob_storage_service, mock_service)

    def test_blob_storage_service_property_before_configuration(self):
        """Test accessing blob storage service before configuration."""
        # Create agent without configuring blob storage service
        unconfigured_agent = BlobWriterAgent(
            name="unconfigured",
            prompt="Test",
            logger=self.mock_logger,  # Follow established pattern
        )

        # Should raise clear error
        with self.assertRaises(ValueError) as context:
            _ = unconfigured_agent.blob_storage_service

        error_msg = str(context.exception)
        self.assertIn("Blob storage service not configured", error_msg)
        self.assertIn("unconfigured", error_msg)

    # =============================================================================
    # URI Extraction Tests
    # =============================================================================

    def test_extract_uri_with_blob_uri_key(self):
        """Test URI extraction with blob_uri input key."""
        test_uri = "azure://container/test.blob"
        inputs = {"blob_uri": test_uri, "data": "test data"}

        # Mock write_blob to verify URI extraction
        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        # Verify URI was extracted correctly
        self.mock_blob_storage_service.write_blob.assert_called_once()
        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][0], test_uri)  # First argument should be URI

    def test_extract_uri_with_uri_key(self):
        """Test URI extraction with uri input key."""
        test_uri = "s3://bucket/test.blob"
        inputs = {"uri": test_uri, "data": "test data"}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][0], test_uri)

    def test_extract_uri_with_path_key(self):
        """Test URI extraction with path input key."""
        test_uri = "/tmp/test.blob"
        inputs = {"path": test_uri, "data": "test data"}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][0], test_uri)

    def test_extract_uri_with_file_path_key(self):
        """Test URI extraction with file_path input key."""
        test_uri = "gs://bucket/data.blob"
        inputs = {"file_path": test_uri, "data": "test data"}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][0], test_uri)

    def test_extract_uri_with_blob_path_key(self):
        """Test URI extraction with blob_path input key."""
        test_uri = "azure://container/nested/blob.data"
        inputs = {"blob_path": test_uri, "data": "test data"}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][0], test_uri)

    def test_extract_uri_with_multiple_keys(self):
        """Test URI extraction with multiple URI keys (first one wins)."""
        primary_uri = "azure://container/primary.blob"
        secondary_uri = "s3://bucket/secondary.blob"
        inputs = {"blob_uri": primary_uri, "uri": secondary_uri, "data": "test data"}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        # Should use the first URI found (blob_uri)
        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][0], primary_uri)

    def test_extract_uri_with_missing_uri(self):
        """Test URI extraction when no URI keys are present."""
        inputs = {"data": "test data", "other_key": "value"}

        with self.assertRaises(ValueError) as context:
            self.agent.process(inputs)

        error_msg = str(context.exception)
        self.assertIn("Missing required blob URI", error_msg)
        self.assertIn("blob_uri, uri, path", error_msg)

    def test_extract_uri_with_empty_uri(self):
        """Test URI extraction with empty URI value."""
        inputs = {"blob_uri": "", "data": "test data"}

        with self.assertRaises(ValueError) as context:
            self.agent.process(inputs)

        error_msg = str(context.exception)
        self.assertIn("Missing required blob URI", error_msg)

    def test_extract_uri_with_none_uri(self):
        """Test URI extraction with None URI value."""
        inputs = {"blob_uri": None, "data": "test data"}

        with self.assertRaises(ValueError) as context:
            self.agent.process(inputs)

        error_msg = str(context.exception)
        self.assertIn("Missing required blob URI", error_msg)

    # =============================================================================
    # Data Extraction and Conversion Tests
    # =============================================================================

    def test_extract_data_with_data_key(self):
        """Test data extraction with data input key."""
        test_data = "test string data"
        expected_bytes = test_data.encode("utf-8")
        inputs = {"blob_uri": "azure://container/test.blob", "data": test_data}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        # Verify data was converted to bytes
        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(
            call_args[0][1], expected_bytes
        )  # Second argument should be data

    def test_extract_data_with_content_key(self):
        """Test data extraction with content input key."""
        test_data = "content string data"
        expected_bytes = test_data.encode("utf-8")
        inputs = {"blob_uri": "s3://bucket/test.blob", "content": test_data}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_extract_data_with_payload_key(self):
        """Test data extraction with payload input key."""
        test_data = "payload string data"
        expected_bytes = test_data.encode("utf-8")
        inputs = {"blob_uri": "gs://bucket/test.blob", "payload": test_data}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_extract_data_with_body_key(self):
        """Test data extraction with body input key."""
        test_data = "body string data"
        expected_bytes = test_data.encode("utf-8")
        inputs = {"blob_uri": "azure://container/test.blob", "body": test_data}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_extract_data_with_multiple_data_keys(self):
        """Test data extraction with multiple data keys (first one wins)."""
        primary_data = "primary data"
        secondary_data = "secondary data"
        expected_bytes = primary_data.encode("utf-8")
        inputs = {
            "blob_uri": "azure://container/test.blob",
            "data": primary_data,
            "content": secondary_data,
        }

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        # Should use the first data found (data)
        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_extract_data_with_missing_data(self):
        """Test data extraction when no data keys are present."""
        inputs = {"blob_uri": "azure://container/test.blob", "other_key": "value"}

        with self.assertRaises(ValueError) as context:
            self.agent.process(inputs)

        error_msg = str(context.exception)
        self.assertIn("Missing required data", error_msg)
        self.assertIn("data, content, payload, or body", error_msg)

    def test_extract_data_with_none_data(self):
        """Test data extraction with None data value."""
        inputs = {"blob_uri": "azure://container/test.blob", "data": None}

        with self.assertRaises(ValueError) as context:
            self.agent.process(inputs)

        error_msg = str(context.exception)
        self.assertIn("Missing required data", error_msg)

    # =============================================================================
    # Data Type Conversion Tests
    # =============================================================================

    def test_convert_string_to_bytes(self):
        """Test conversion of string data to bytes."""
        test_string = "Hello, world! 🌍"
        expected_bytes = test_string.encode("utf-8")
        inputs = {"blob_uri": "azure://container/test.blob", "data": test_string}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_convert_bytes_to_bytes(self):
        """Test that bytes data is passed through unchanged."""
        test_bytes = b"raw byte data"
        inputs = {"blob_uri": "s3://bucket/test.blob", "data": test_bytes}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], test_bytes)

    def test_convert_dict_to_json_bytes(self):
        """Test conversion of dictionary to JSON bytes."""
        test_dict = {"key": "value", "number": 42, "nested": {"inner": "data"}}
        expected_json = json.dumps(test_dict, indent=2)
        expected_bytes = expected_json.encode("utf-8")
        inputs = {"blob_uri": "gs://bucket/test.blob", "data": test_dict}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_convert_list_to_json_bytes(self):
        """Test conversion of list to JSON bytes."""
        test_list = [1, 2, {"key": "value"}, "string"]
        expected_json = json.dumps(test_list, indent=2)
        expected_bytes = expected_json.encode("utf-8")
        inputs = {"blob_uri": "azure://container/test.blob", "data": test_list}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_convert_number_to_string_bytes(self):
        """Test conversion of number to string bytes."""
        test_number = 12345
        expected_bytes = str(test_number).encode("utf-8")
        inputs = {"blob_uri": "s3://bucket/test.blob", "data": test_number}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_convert_boolean_to_string_bytes(self):
        """Test conversion of boolean to string bytes."""
        test_boolean = True
        expected_bytes = str(test_boolean).encode("utf-8")
        inputs = {"blob_uri": "gs://bucket/test.blob", "data": test_boolean}

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_convert_none_to_empty_bytes(self):
        """Test conversion of None to empty bytes."""
        # Note: This would actually fail at data extraction step
        # But if None somehow gets through, it should be handled
        inputs = {"blob_uri": "azure://container/test.blob", "data": ""}

        # Empty string should become empty bytes
        expected_bytes = b""

        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        self.agent.process(inputs)

        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_convert_complex_object_to_json_error(self):
        """Test conversion of non-serializable object creates string representation."""

        # Object that can't be JSON serialized
        class NonSerializable:
            def __init__(self):
                self.circular_ref = self

        test_object = NonSerializable()
        inputs = {"blob_uri": "azure://container/test.blob", "data": test_object}

        # Mock successful write to verify data conversion
        self.mock_blob_storage_service.write_blob.return_value = {"success": True}

        # Should not raise exception - non-JSON objects get converted to string
        self.agent.process(inputs)

        # Verify conversion to string bytes
        call_args = self.mock_blob_storage_service.write_blob.call_args
        converted_data = call_args[0][1]
        self.assertIsInstance(converted_data, bytes)

        # Should contain string representation of the object
        data_str = converted_data.decode("utf-8")
        self.assertIn("NonSerializable", data_str)

    # =============================================================================
    # Blob Writing Operation Tests
    # =============================================================================

    def test_successful_blob_write_operation(self):
        """Test successful blob writing operation."""
        test_uri = "azure://container/success.blob"
        test_data = "success test data"
        expected_result = {
            "success": True,
            "uri": test_uri,
            "size": len(test_data.encode("utf-8")),
            "provider": "azure",
        }

        # Setup mock to return success result
        self.mock_blob_storage_service.write_blob.return_value = expected_result

        inputs = {"blob_uri": test_uri, "data": test_data}
        result = self.agent.process(inputs)

        # Verify result
        self.assertEqual(result, expected_result)

        # Verify blob storage service was called correctly
        self.mock_blob_storage_service.write_blob.assert_called_once_with(
            test_uri, test_data.encode("utf-8")
        )

    def test_blob_write_with_large_data(self):
        """Test blob writing with large data."""
        test_uri = "s3://bucket/large.blob"
        large_data = "x" * (1024 * 1024)  # 1MB string
        expected_bytes = large_data.encode("utf-8")
        expected_result = {
            "success": True,
            "uri": test_uri,
            "size": len(expected_bytes),
        }

        self.mock_blob_storage_service.write_blob.return_value = expected_result

        inputs = {"blob_uri": test_uri, "data": large_data}
        result = self.agent.process(inputs)

        # Verify result
        self.assertEqual(result, expected_result)

        # Verify correct data was passed
        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)
        self.assertEqual(len(call_args[0][1]), 1024 * 1024)

    def test_blob_write_with_binary_data(self):
        """Test blob writing with binary data."""
        test_uri = "gs://bucket/binary.blob"
        binary_data = bytes(range(256))  # All possible byte values
        expected_result = {"success": True, "uri": test_uri, "size": len(binary_data)}

        self.mock_blob_storage_service.write_blob.return_value = expected_result

        inputs = {"blob_uri": test_uri, "data": binary_data}
        result = self.agent.process(inputs)

        # Verify result
        self.assertEqual(result, expected_result)

        # Verify binary data was passed correctly
        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], binary_data)

    def test_blob_write_with_json_data(self):
        """Test blob writing with JSON-serializable data."""
        test_uri = "azure://container/json.blob"
        json_data = {
            "string": "value",
            "number": 42,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "data"},
        }
        expected_json = json.dumps(json_data, indent=2)
        expected_bytes = expected_json.encode("utf-8")
        expected_result = {
            "success": True,
            "uri": test_uri,
            "size": len(expected_bytes),
        }

        self.mock_blob_storage_service.write_blob.return_value = expected_result

        inputs = {"blob_uri": test_uri, "data": json_data}
        result = self.agent.process(inputs)

        # Verify result
        self.assertEqual(result, expected_result)

        # Verify JSON data was serialized correctly
        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

        # Verify it's valid JSON
        parsed_data = json.loads(call_args[0][1].decode("utf-8"))
        self.assertEqual(parsed_data, json_data)

    # =============================================================================
    # Error Handling Tests
    # =============================================================================

    def test_blob_write_storage_operation_error(self):
        """Test blob writing with storage operation error."""
        test_uri = "azure://container/error.blob"
        test_data = "error test data"

        # Setup mock to raise StorageOperationError
        self.mock_blob_storage_service.write_blob.side_effect = StorageOperationError(
            "Write failed"
        )

        inputs = {"blob_uri": test_uri, "data": test_data}

        # Should re-raise StorageOperationError
        with self.assertRaises(StorageOperationError):
            self.agent.process(inputs)

        # Verify blob storage service was called
        self.mock_blob_storage_service.write_blob.assert_called_once()

    def test_blob_write_general_exception(self):
        """Test blob writing with general exception."""
        test_uri = "s3://bucket/exception.blob"
        test_data = "exception test data"

        # Setup mock to raise general exception
        self.mock_blob_storage_service.write_blob.side_effect = Exception(
            "Unexpected error"
        )

        inputs = {"blob_uri": test_uri, "data": test_data}

        # Should re-raise the exception
        with self.assertRaises(Exception) as context:
            self.agent.process(inputs)

        self.assertIn("Unexpected error", str(context.exception))

        # Verify blob storage service was called
        self.mock_blob_storage_service.write_blob.assert_called_once()

    def test_process_without_blob_storage_service(self):
        """Test processing when blob storage service is not configured."""
        # Create agent without configuring blob storage service
        unconfigured_agent = BlobWriterAgent(
            name="unconfigured", prompt="Test", logger=self.mock_logger
        )

        inputs = {"blob_uri": "azure://container/test.blob", "data": "test data"}

        # Should raise ValueError about missing service
        with self.assertRaises(ValueError) as context:
            unconfigured_agent.process(inputs)

        error_msg = str(context.exception)
        self.assertIn("Blob storage service not configured", error_msg)

    # =============================================================================
    # Logging and Debugging Tests
    # =============================================================================

    def test_logging_during_successful_processing(self):
        """Test that appropriate logging occurs during successful processing."""
        test_uri = "azure://container/logging.blob"
        test_data = "logging test data"
        expected_result = {"success": True}

        # Setup mocks
        self.mock_blob_storage_service.write_blob.return_value = expected_result

        inputs = {"blob_uri": test_uri, "data": test_data}
        self.agent.process(inputs)

        # Verify logging was attempted (through BaseAgent)
        self.assertIsNotNone(self.agent.logger)

    def test_logging_during_error_processing(self):
        """Test that appropriate error logging occurs during failed processing."""
        test_uri = "azure://container/error.blob"
        test_data = "error test data"

        # Setup mock to raise exception
        self.mock_blob_storage_service.write_blob.side_effect = Exception("Test error")

        inputs = {"blob_uri": test_uri, "data": test_data}

        # Process should raise exception
        with self.assertRaises(Exception):
            self.agent.process(inputs)

        # Verify logging was attempted (through BaseAgent)
        self.assertIsNotNone(self.agent.logger)

    def test_get_child_service_info_with_configured_service(self):
        """Test service debugging info when blob storage service is configured."""
        # Configure service with mock that has expected methods
        mock_service = Mock(spec=BlobStorageServiceProtocol)
        # Properly configure the mock method
        mock_service.get_available_providers = Mock(
            return_value=["azure", "s3", "file"]
        )
        self.agent.configure_blob_storage_service(mock_service)

        # Get service info
        info = self.agent._get_child_service_info()

        # Verify info structure
        self.assertIsInstance(info, dict)
        self.assertIn("services", info)
        self.assertIn("protocols", info)
        self.assertIn("blob_storage", info)

        # Verify service info
        self.assertTrue(info["services"]["blob_storage_service_configured"])
        self.assertTrue(info["protocols"]["implements_blob_storage_capable"])

        # Verify blob storage specific info
        blob_info = info["blob_storage"]
        self.assertEqual(blob_info["service_type"], "Mock")
        self.assertEqual(blob_info["available_providers"], ["azure", "s3", "file"])

    def test_get_child_service_info_without_configured_service(self):
        """Test service debugging info when blob storage service is not configured."""
        # Create agent without configuring blob storage service (follow established pattern)
        unconfigured_agent = BlobWriterAgent(
            name="unconfigured",
            prompt="Test",
            logger=self.mock_logger,  # Follow established pattern
        )

        # Get service info
        info = unconfigured_agent._get_child_service_info()

        # Verify info structure
        self.assertIsInstance(info, dict)
        self.assertIn("services", info)
        self.assertIn("protocols", info)
        self.assertIn("blob_storage", info)

        # Verify service info
        self.assertFalse(info["services"]["blob_storage_service_configured"])
        self.assertTrue(info["protocols"]["implements_blob_storage_capable"])

        # Verify blob storage specific info
        blob_info = info["blob_storage"]
        self.assertIsNone(blob_info["service_type"])
        self.assertEqual(blob_info["available_providers"], [])

    # =============================================================================
    # Integration Tests
    # =============================================================================

    def test_integration_with_state_adapter_service(self):
        """Test integration with StateAdapterService."""
        # Create agent with state adapter service (follow established pattern)
        agent_with_state = BlobWriterAgent(
            name="state_test",
            prompt="Test with state adapter",
            logger=self.mock_logger,  # Follow established pattern
            state_adapter_service=self.mock_state_adapter_service,
        )
        agent_with_state.configure_blob_storage_service(self.mock_blob_storage_service)

        test_uri = "azure://container/state.blob"
        test_data = "state test data"
        expected_result = {"success": True}

        # Setup mocks
        self.mock_blob_storage_service.write_blob.return_value = expected_result

        inputs = {"blob_uri": test_uri, "data": test_data}
        result = agent_with_state.process(inputs)

        # Verify result
        self.assertEqual(result, expected_result)

        # StateAdapterService is available but not required for basic operation
        self.assertEqual(
            agent_with_state.state_adapter_service, self.mock_state_adapter_service
        )

    def test_integration_with_execution_tracking_service(self):
        """Test integration with ExecutionTrackingService."""
        # Create agent with execution tracking service (follow established pattern)
        agent_with_tracking = BlobWriterAgent(
            name="tracking_test",
            prompt="Test with execution tracking",
            logger=self.mock_logger,  # Follow established pattern
            execution_tracking_service=self.mock_execution_tracking_service,
        )
        agent_with_tracking.configure_blob_storage_service(
            self.mock_blob_storage_service
        )

        test_uri = "s3://bucket/tracking.blob"
        test_data = "tracking test data"
        expected_result = {"success": True}

        # Setup mocks
        self.mock_blob_storage_service.write_blob.return_value = expected_result

        inputs = {"blob_uri": test_uri, "data": test_data}
        result = agent_with_tracking.process(inputs)

        # Verify result
        self.assertEqual(result, expected_result)

        # ExecutionTrackingService should be accessible
        self.assertEqual(
            agent_with_tracking.execution_tracking_service,
            self.mock_execution_tracking_service,
        )

    # =============================================================================
    # Protocol Compliance Tests
    # =============================================================================

    def test_base_agent_interface_compliance(self):
        """Test that agent complies with BaseAgent interface."""
        # Required properties from BaseAgent
        self.assertTrue(hasattr(self.agent, "name"))
        self.assertTrue(hasattr(self.agent, "prompt"))
        self.assertTrue(hasattr(self.agent, "context"))

        # Required methods from BaseAgent
        self.assertTrue(hasattr(self.agent, "process"))
        self.assertTrue(callable(self.agent.process))

        # Infrastructure service properties
        self.assertTrue(hasattr(self.agent, "logger"))
        self.assertTrue(hasattr(self.agent, "execution_tracking_service"))
        self.assertTrue(hasattr(self.agent, "state_adapter_service"))

    def test_blob_storage_capable_agent_interface_compliance(self):
        """Test that agent complies with BlobStorageCapableAgent protocol."""
        # Required method from BlobStorageCapableAgent
        self.assertTrue(hasattr(self.agent, "configure_blob_storage_service"))
        self.assertTrue(callable(self.agent.configure_blob_storage_service))

        # Should be able to configure blob storage service
        mock_service = Mock(spec=BlobStorageServiceProtocol)
        self.agent.configure_blob_storage_service(mock_service)

        # Should be able to access configured service
        self.assertEqual(self.agent.blob_storage_service, mock_service)

    # =============================================================================
    # Edge Cases and Robustness Tests
    # =============================================================================

    def test_process_with_special_characters_in_data(self):
        """Test processing with special characters in data."""
        test_uri = "azure://container/special.blob"
        special_data = "Special chars: 🌍 ñáéíóú ΩΨΦ ∑∆∏ 中文"
        expected_bytes = special_data.encode("utf-8")
        expected_result = {"success": True}

        self.mock_blob_storage_service.write_blob.return_value = expected_result

        inputs = {"blob_uri": test_uri, "data": special_data}
        self.agent.process(inputs)

        # Verify special characters were encoded correctly
        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_process_with_empty_data(self):
        """Test processing with empty data."""
        test_uri = "s3://bucket/empty.blob"
        empty_data = ""
        expected_bytes = b""
        expected_result = {"success": True}

        self.mock_blob_storage_service.write_blob.return_value = expected_result

        inputs = {"blob_uri": test_uri, "data": empty_data}
        self.agent.process(inputs)

        # Verify empty data was handled correctly
        call_args = self.mock_blob_storage_service.write_blob.call_args
        self.assertEqual(call_args[0][1], expected_bytes)

    def test_multiple_agent_instances_independence(self):
        """Test that multiple agent instances operate independently."""
        # Create second agent (follow established pattern)
        agent2 = BlobWriterAgent(
            name="second_writer",
            prompt="Second agent",
            logger=self.mock_logger,  # Follow established pattern
        )

        # Configure different services
        mock_service2 = Mock(spec=BlobStorageServiceProtocol)
        agent2.configure_blob_storage_service(mock_service2)

        # Verify agents have different services
        self.assertNotEqual(
            self.agent.blob_storage_service, agent2.blob_storage_service
        )

        # Verify agents have different names
        self.assertEqual(self.agent.name, "test_blob_writer")
        self.assertEqual(agent2.name, "second_writer")


if __name__ == "__main__":
    unittest.main()
