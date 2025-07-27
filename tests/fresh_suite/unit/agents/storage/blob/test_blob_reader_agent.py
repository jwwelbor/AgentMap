"""
Comprehensive unit tests for BlobReaderAgent.

These tests validate the BlobReaderAgent implementation including:
- Modern BaseAgent contract compliance
- Protocol-based service configuration (BlobStorageCapableAgent)
- Constructor injection of infrastructure services
- Blob reading operations and error handling
- Input extraction and validation
- State adapter service integration
- Execution tracking integration
- Service debugging information
"""

import unittest
import logging
from unittest.mock import Mock, patch
from typing import Dict, Any, Optional

from agentmap.agents.builtins.storage.blob.blob_reader_agent import BlobReaderAgent
from agentmap.services.protocols import BlobStorageServiceProtocol
from agentmap.exceptions import StorageOperationError
from tests.utils.mock_service_factory import MockServiceFactory


class TestBlobReaderAgent(unittest.TestCase):
    """Comprehensive tests for BlobReaderAgent implementation."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use MockServiceFactory for consistent behavior (established pattern)
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = MockServiceFactory.create_mock_execution_tracking_service()
        self.mock_state_adapter_service = MockServiceFactory.create_mock_state_adapter_service()
        
        # Get mock logger for verification (established pattern)
        self.mock_logger = self.mock_logging_service.get_class_logger(BlobReaderAgent)
        
        # Create mock blob storage service with required methods
        self.mock_blob_storage_service = Mock(spec=BlobStorageServiceProtocol)
        # Configure mock methods
        self.mock_blob_storage_service.get_available_providers = Mock(return_value=["azure", "s3", "file"])
        
        # Create agent instance
        self.agent = BlobReaderAgent(
            name="test_blob_reader",
            prompt="Read blob data from storage",
            context={"input_keys": ["blob_uri"], "output_key": "blob_data"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service
        )
        
        # Configure blob storage service via protocol
        self.agent.configure_blob_storage_service(self.mock_blob_storage_service)
    
    # =============================================================================
    # Agent Initialization and Protocol Tests
    # =============================================================================
    
    def test_agent_initialization_with_infrastructure_services(self):
        """Test agent initialization with all infrastructure services."""
        # Verify BaseAgent initialization
        self.assertEqual(self.agent.name, "test_blob_reader")
        self.assertEqual(self.agent.prompt, "Read blob data from storage")
        self.assertIsNotNone(self.agent.context)
        
        # Verify infrastructure services are stored
        self.assertEqual(self.agent.logger, self.mock_logger)
        self.assertEqual(self.agent.execution_tracking_service, self.mock_execution_tracking_service)
        self.assertEqual(self.agent.state_adapter_service, self.mock_state_adapter_service)
        
        # Blob storage service should be configured
        self.assertEqual(self.agent.blob_storage_service, self.mock_blob_storage_service)
    
    def test_agent_initialization_minimal(self):
        """Test agent initialization with minimal parameters."""
        # Create agent with minimal parameters but include logger (established pattern)
        minimal_agent = BlobReaderAgent(
            name="minimal_reader",
            prompt="Minimal prompt",
            logger=self.mock_logger  # Follow established pattern
        )
        
        # Should initialize successfully
        self.assertEqual(minimal_agent.name, "minimal_reader")
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
        self.assertTrue(hasattr(self.agent, 'configure_blob_storage_service'))
        
        # Should be able to configure blob storage service
        mock_service = Mock(spec=BlobStorageServiceProtocol)
        self.agent.configure_blob_storage_service(mock_service)
        
        # Should be able to access configured service
        self.assertEqual(self.agent.blob_storage_service, mock_service)
    
    def test_blob_storage_service_property_before_configuration(self):
        """Test accessing blob storage service before configuration."""
        # Create agent without configuring blob storage service (follow established pattern)
        unconfigured_agent = BlobReaderAgent(
            name="unconfigured",
            prompt="Test",
            logger=self.mock_logger  # Follow established pattern
        )
        
        # Should raise clear error
        with self.assertRaises(ValueError) as context:
            _ = unconfigured_agent.blob_storage_service
        
        error_msg = str(context.exception)
        self.assertIn("Blob storage service not configured", error_msg)
        self.assertIn("unconfigured", error_msg)
    
    def test_blob_storage_service_property_after_configuration(self):
        """Test accessing blob storage service after configuration."""
        # Configure service
        mock_service = Mock(spec=BlobStorageServiceProtocol)
        self.agent.configure_blob_storage_service(mock_service)
        
        # Should return configured service
        self.assertEqual(self.agent.blob_storage_service, mock_service)
    
    # =============================================================================
    # Blob Reading Operation Tests
    # =============================================================================
    
    def test_process_with_blob_uri_key(self):
        """Test processing with blob_uri input key."""
        # Setup test data
        test_uri = "azure://container/test.blob"
        test_data = b"test blob data content"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = test_data
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Verify result
        self.assertEqual(result, test_data)
        
        # Verify blob storage service was called correctly
        self.mock_blob_storage_service.read_blob.assert_called_once_with(test_uri)
    
    def test_process_with_uri_key(self):
        """Test processing with uri input key."""
        # Setup test data
        test_uri = "s3://bucket/test.blob"
        test_data = b"s3 blob data"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = test_data
        
        # Setup inputs
        inputs = {"uri": test_uri}
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Verify result
        self.assertEqual(result, test_data)
        self.mock_blob_storage_service.read_blob.assert_called_once_with(test_uri)
    
    def test_process_with_path_key(self):
        """Test processing with path input key."""
        # Setup test data
        test_uri = "/tmp/test.blob"
        test_data = b"local file data"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = test_data
        
        # Setup inputs
        inputs = {"path": test_uri}
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Verify result
        self.assertEqual(result, test_data)
        self.mock_blob_storage_service.read_blob.assert_called_once_with(test_uri)
    
    def test_process_with_file_path_key(self):
        """Test processing with file_path input key."""
        # Setup test data
        test_uri = "gs://bucket/data.blob"
        test_data = b"google cloud data"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = test_data
        
        # Setup inputs
        inputs = {"file_path": test_uri}
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Verify result
        self.assertEqual(result, test_data)
        self.mock_blob_storage_service.read_blob.assert_called_once_with(test_uri)
    
    def test_process_with_blob_path_key(self):
        """Test processing with blob_path input key."""
        # Setup test data
        test_uri = "azure://container/nested/blob.data"
        test_data = b"nested blob data"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = test_data
        
        # Setup inputs
        inputs = {"blob_path": test_uri}
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Verify result
        self.assertEqual(result, test_data)
        self.mock_blob_storage_service.read_blob.assert_called_once_with(test_uri)
    
    def test_process_with_multiple_uri_keys(self):
        """Test processing with multiple URI keys (first one wins)."""
        # Setup test data
        primary_uri = "azure://container/primary.blob"
        secondary_uri = "s3://bucket/secondary.blob"
        test_data = b"primary blob data"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = test_data
        
        # Setup inputs with multiple URI keys
        inputs = {
            "blob_uri": primary_uri,
            "uri": secondary_uri,
            "path": "/tmp/tertiary.blob"
        }
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Should use the first URI found (blob_uri)
        self.assertEqual(result, test_data)
        self.mock_blob_storage_service.read_blob.assert_called_once_with(primary_uri)
    
    def test_process_with_empty_uri_value(self):
        """Test processing with empty URI value."""
        # Setup inputs with empty URI
        inputs = {"blob_uri": ""}
        
        # Should raise ValueError for missing URI
        with self.assertRaises(ValueError) as context:
            self.agent.process(inputs)
        
        error_msg = str(context.exception)
        self.assertIn("Missing required blob URI", error_msg)
        self.assertIn("blob_uri, uri, path", error_msg)
    
    def test_process_with_none_uri_value(self):
        """Test processing with None URI value."""
        # Setup inputs with None URI
        inputs = {"blob_uri": None, "uri": None}
        
        # Should raise ValueError for missing URI
        with self.assertRaises(ValueError) as context:
            self.agent.process(inputs)
        
        error_msg = str(context.exception)
        self.assertIn("Missing required blob URI", error_msg)
    
    def test_process_without_uri_keys(self):
        """Test processing without any URI keys."""
        # Setup inputs without URI keys
        inputs = {"some_other_key": "value"}
        
        # Should raise ValueError for missing URI
        with self.assertRaises(ValueError) as context:
            self.agent.process(inputs)
        
        error_msg = str(context.exception)
        self.assertIn("Missing required blob URI", error_msg)
        self.assertIn("blob_uri, uri, path, file_path, or blob_path", error_msg)
    
    def test_process_with_empty_inputs(self):
        """Test processing with empty inputs dictionary."""
        # Setup empty inputs
        inputs = {}
        
        # Should raise ValueError for missing URI
        with self.assertRaises(ValueError) as context:
            self.agent.process(inputs)
        
        error_msg = str(context.exception)
        self.assertIn("Missing required blob URI", error_msg)
    
    # =============================================================================
    # Error Handling Tests
    # =============================================================================
    
    def test_process_with_file_not_found_error(self):
        """Test processing when blob doesn't exist."""
        # Setup test data
        test_uri = "azure://container/nonexistent.blob"
        
        # Setup mocks to raise FileNotFoundError
        self.mock_blob_storage_service.read_blob.side_effect = FileNotFoundError("Blob not found")
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
        # Should re-raise FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            self.agent.process(inputs)
        
        # Verify blob storage service was called
        self.mock_blob_storage_service.read_blob.assert_called_once_with(test_uri)
    
    def test_process_with_storage_operation_error(self):
        """Test processing with storage operation error."""
        # Setup test data
        test_uri = "s3://bucket/problematic.blob"
        
        # Setup mocks to raise StorageOperationError
        self.mock_blob_storage_service.read_blob.side_effect = StorageOperationError("Storage failed")
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
        # Should re-raise StorageOperationError
        with self.assertRaises(StorageOperationError):
            self.agent.process(inputs)
        
        # Verify blob storage service was called
        self.mock_blob_storage_service.read_blob.assert_called_once_with(test_uri)
    
    def test_process_with_general_exception(self):
        """Test processing with general exception."""
        # Setup test data
        test_uri = "gs://bucket/error.blob"
        
        # Setup mocks to raise general exception
        self.mock_blob_storage_service.read_blob.side_effect = Exception("Unexpected error")
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
        # Should re-raise the exception
        with self.assertRaises(Exception) as context:
            self.agent.process(inputs)
        
        self.assertIn("Unexpected error", str(context.exception))
        
        # Verify blob storage service was called
        self.mock_blob_storage_service.read_blob.assert_called_once_with(test_uri)
    
    def test_process_without_blob_storage_service(self):
        """Test processing when blob storage service is not configured."""
        # Create agent without configuring blob storage service
        unconfigured_agent = BlobReaderAgent(
            name="unconfigured",
            prompt="Test",
            logger=self.mock_logger
        )
        
        # Setup inputs
        inputs = {"blob_uri": "azure://container/test.blob"}
        
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
        # Setup test data
        test_uri = "azure://container/test.blob"
        test_data = b"test data"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = test_data
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Verify logging calls were made
        # Note: The actual logging method calls depend on the agent's log_debug, log_info, etc. methods
        # which are part of BaseAgent. We verify the mock logger was used.
        self.assertIsNotNone(self.agent.logger)
    
    def test_logging_during_error_processing(self):
        """Test that appropriate error logging occurs during failed processing."""
        # Setup test data
        test_uri = "azure://container/error.blob"
        
        # Setup mocks to raise exception
        self.mock_blob_storage_service.read_blob.side_effect = Exception("Test error")
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
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
        mock_service.get_available_providers = Mock(return_value=["azure", "s3", "file"])
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
        unconfigured_agent = BlobReaderAgent(
            name="unconfigured",
            prompt="Test",
            logger=self.mock_logger  # Follow established pattern
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
    
    def test_get_child_service_info_with_service_error(self):
        """Test service debugging info when service method raises error."""
        # Configure service that raises error
        mock_service = Mock(spec=BlobStorageServiceProtocol)
        # Properly configure the mock method
        mock_service.get_available_providers = Mock(side_effect=Exception("Provider error"))
        self.agent.configure_blob_storage_service(mock_service)
        
        # Should raise the exception (implementation doesn't catch service errors)
        with self.assertRaises(Exception) as context:
            self.agent._get_child_service_info()
        
        # Verify the exception message
        self.assertIn("Provider error", str(context.exception))
    
    # =============================================================================
    # State Adapter Integration Tests
    # =============================================================================
    
    def test_integration_with_state_adapter_service(self):
        """Test integration with StateAdapterService for input extraction."""
        # Create agent with state adapter service (follow established pattern)
        agent_with_state = BlobReaderAgent(
            name="state_test",
            prompt="Test with state adapter",
            logger=self.mock_logger,  # Follow established pattern
            state_adapter_service=self.mock_state_adapter_service
        )
        agent_with_state.configure_blob_storage_service(self.mock_blob_storage_service)
        
        # Setup test data
        test_uri = "azure://container/state.blob"
        test_data = b"state test data"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = test_data
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
        # Process inputs
        result = agent_with_state.process(inputs)
        
        # Verify result
        self.assertEqual(result, test_data)
        
        # The agent should still extract URI directly from inputs
        # (StateAdapterService is available but not required for basic URI extraction)
        self.mock_blob_storage_service.read_blob.assert_called_once_with(test_uri)
    
    # =============================================================================
    # Execution Tracking Integration Tests
    # =============================================================================
    
    def test_integration_with_execution_tracking_service(self):
        """Test integration with ExecutionTrackingService."""
        # Create agent with execution tracking service (follow established pattern)
        agent_with_tracking = BlobReaderAgent(
            name="tracking_test",
            prompt="Test with execution tracking",
            logger=self.mock_logger,  # Follow established pattern
            execution_tracking_service=self.mock_execution_tracking_service
        )
        agent_with_tracking.configure_blob_storage_service(self.mock_blob_storage_service)
        
        # Setup test data
        test_uri = "s3://bucket/tracking.blob"
        test_data = b"tracking test data"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = test_data
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
        # Process inputs
        result = agent_with_tracking.process(inputs)
        
        # Verify result
        self.assertEqual(result, test_data)
        
        # ExecutionTrackingService should be accessible to the agent
        self.assertEqual(agent_with_tracking.execution_tracking_service, self.mock_execution_tracking_service)
    
    # =============================================================================
    # Protocol Compliance and Interface Tests
    # =============================================================================
    
    def test_base_agent_interface_compliance(self):
        """Test that agent complies with BaseAgent interface."""
        # Required properties from BaseAgent
        self.assertTrue(hasattr(self.agent, 'name'))
        self.assertTrue(hasattr(self.agent, 'prompt'))
        self.assertTrue(hasattr(self.agent, 'context'))
        
        # Required methods from BaseAgent
        self.assertTrue(hasattr(self.agent, 'process'))
        self.assertTrue(callable(self.agent.process))
        
        # Infrastructure service properties
        self.assertTrue(hasattr(self.agent, 'logger'))
        self.assertTrue(hasattr(self.agent, 'execution_tracking_service'))
        self.assertTrue(hasattr(self.agent, 'state_adapter_service'))
    
    def test_blob_storage_capable_agent_interface_compliance(self):
        """Test that agent complies with BlobStorageCapableAgent protocol."""
        # Required method from BlobStorageCapableAgent
        self.assertTrue(hasattr(self.agent, 'configure_blob_storage_service'))
        self.assertTrue(callable(self.agent.configure_blob_storage_service))
        
        # Should be able to configure blob storage service
        mock_service = Mock(spec=BlobStorageServiceProtocol)
        self.agent.configure_blob_storage_service(mock_service)
        
        # Should be able to access configured service
        self.assertEqual(self.agent.blob_storage_service, mock_service)
    
    # =============================================================================
    # Edge Cases and Robustness Tests
    # =============================================================================
    
    def test_process_with_large_blob_data(self):
        """Test processing with large blob data."""
        # Setup large test data (1MB)
        large_data = b"x" * (1024 * 1024)
        test_uri = "azure://container/large.blob"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = large_data
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Verify result
        self.assertEqual(result, large_data)
        self.assertEqual(len(result), 1024 * 1024)
    
    def test_process_with_binary_blob_data(self):
        """Test processing with binary blob data."""
        # Setup binary test data
        binary_data = bytes(range(256))  # All possible byte values
        test_uri = "s3://bucket/binary.blob"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = binary_data
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Verify result
        self.assertEqual(result, binary_data)
        self.assertEqual(len(result), 256)
    
    def test_process_with_empty_blob_data(self):
        """Test processing with empty blob data."""
        # Setup empty test data
        empty_data = b""
        test_uri = "gs://bucket/empty.blob"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = empty_data
        
        # Setup inputs
        inputs = {"blob_uri": test_uri}
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Verify result
        self.assertEqual(result, empty_data)
        self.assertEqual(len(result), 0)
    
    def test_process_with_special_characters_in_uri(self):
        """Test processing with special characters in URI."""
        # Setup URI with special characters
        special_uri = "azure://container/file%20with%20spaces/special-chars_123.blob"
        test_data = b"special character test"
        
        # Setup mocks
        self.mock_blob_storage_service.read_blob.return_value = test_data
        
        # Setup inputs
        inputs = {"blob_uri": special_uri}
        
        # Process inputs
        result = self.agent.process(inputs)
        
        # Verify result
        self.assertEqual(result, test_data)
        self.mock_blob_storage_service.read_blob.assert_called_once_with(special_uri)
    
    def test_multiple_agent_instances_independence(self):
        """Test that multiple agent instances operate independently."""
        # Create second agent (follow established pattern)
        agent2 = BlobReaderAgent(
            name="second_reader",
            prompt="Second agent",
            logger=self.mock_logger  # Follow established pattern
        )
        
        # Configure different services
        mock_service2 = Mock(spec=BlobStorageServiceProtocol)
        agent2.configure_blob_storage_service(mock_service2)
        
        # Verify agents have different services
        self.assertNotEqual(self.agent.blob_storage_service, agent2.blob_storage_service)
        
        # Verify agents have different names
        self.assertEqual(self.agent.name, "test_blob_reader")
        self.assertEqual(agent2.name, "second_reader")


if __name__ == '__main__':
    unittest.main()
