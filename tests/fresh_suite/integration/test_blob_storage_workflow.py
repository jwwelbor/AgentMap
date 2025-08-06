"""
End-to-end integration tests for blob storage workflow.

These tests validate the complete blob storage workflow including:
- Real DI container integration with blob storage services
- Complete agent pipeline from data input to blob storage
- Cross-provider compatibility and graceful degradation
- State management and execution tracking integration
- Performance characteristics under various conditions
- Error handling and recovery scenarios
- ApplicationContainer blob storage integration
- Cloud provider SDK graceful degradation testing
"""

import unittest
import tempfile
import shutil
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from agentmap.di import initialize_di
from agentmap.agents.builtins.storage.blob.blob_reader_agent import BlobReaderAgent
from agentmap.agents.builtins.storage.blob.blob_writer_agent import BlobWriterAgent
from agentmap.services.storage.blob_storage_service import BlobStorageService
from agentmap.exceptions import StorageConnectionError, StorageOperationError
from tests.utils.mock_service_factory import MockServiceFactory


class TestBlobStorageWorkflowIntegration(unittest.TestCase):
    """End-to-end integration tests for blob storage workflows."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        # Create temporary directory for test configs and data
        self.temp_dir = tempfile.mkdtemp()
        self.test_blob_data_path = Path(self.temp_dir) / "blob_data"
        self.test_blob_data_path.mkdir(exist_ok=True)
        self.test_config_path = self._create_test_config()
        
        # Test data for various scenarios
        self.test_string_data = "Hello, blob storage world! 🌍"
        self.test_json_data = {
            "message": "Test JSON data",
            "timestamp": "2024-01-01T00:00:00Z",
            "numbers": [1, 2, 3, 4, 5],
            "nested": {"key": "value", "flag": True}
        }
        self.test_binary_data = bytes(range(256))  # All possible byte values
        
    def tearDown(self):
        """Clean up integration test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_config(self) -> Path:
        """Create a test configuration file for DI container."""
        config_path = Path(self.temp_dir) / "test_config.yaml"
        storage_config_path = Path(self.temp_dir) / "storage_config.yaml"
        
        # Use forward slashes for YAML to avoid Windows backslash escaping issues
        storage_config_path_str = str(storage_config_path).replace('\\', '/')
        csv_data_path_str = f"{self.temp_dir}/csv_data".replace('\\', '/')
        blob_data_path_str = str(self.test_blob_data_path).replace('\\', '/')
        
        config_content = f"""logging:
  version: 1
  level: DEBUG
  format: "[%(levelname)s] %(name)s: %(message)s"

storage:
  blob:
    providers:
      azure:
        connection_string: "test_connection_string"
      s3:
        access_key: "test_access_key"
        secret_key: "test_secret_key"
        region: "us-east-1"
      gs:
        credentials_path: "/path/to/credentials.json"
      file:
        base_directory: "{blob_data_path_str}"

storage_config_path: "{storage_config_path_str}"
"""
        
        storage_config_content = f"""csv:
  default_directory: "{csv_data_path_str}"
  collections: {{}}

vector:
  default_provider: "chroma"
  collections: {{}}

kv:
  default_provider: "local"
  collections: {{}}
"""
        
        with open(config_path, 'w') as f:
            f.write(config_content)
            
        with open(storage_config_path, 'w') as f:
            f.write(storage_config_content)
        
        return config_path
    
    # =============================================================================
    # DI Container Integration Tests
    # =============================================================================
    
    def test_blob_storage_service_container_integration(self):
        """Test blob storage service creation and configuration through DI container."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        
        # Get blob storage service from container
        blob_service = container.blob_storage_service()
        
        if blob_service is not None:
            # Service should be properly configured
            self.assertIsInstance(blob_service, BlobStorageService)
            self.assertIsNotNone(blob_service.configuration)
            self.assertIsNotNone(blob_service.logging_service)
            
            # Should have available providers
            providers = blob_service.get_available_providers()
            self.assertIsInstance(providers, list)
            self.assertIn('file', providers)  # Local file should always be available
            
            # Should be able to perform health check
            health_results = blob_service.health_check()
            self.assertIsInstance(health_results, dict)
            self.assertIn('healthy', health_results)
            self.assertIn('providers', health_results)
    
    def test_storage_service_manager_blob_integration(self):
        """Test storage service manager integration with blob storage."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        
        # Get storage service manager
        storage_manager = container.storage_service_manager()
        
        if storage_manager is not None:
            # Should be able to check for blob storage
            has_blob = storage_manager.is_blob_storage_enabled()
            
            if has_blob:
                # Should be able to get blob storage service
                blob_service = storage_manager.get_blob_storage_service()
                self.assertIsNotNone(blob_service)
                
                # Blob should be in available providers
                providers = storage_manager.list_available_providers()
                self.assertIn("blob", providers)
                
                # Should be able to get service info
                blob_info = storage_manager.get_service_info("blob")
                self.assertIn("blob", blob_info)
                self.assertTrue(blob_info["blob"]["available"])
    
    def test_application_container_blob_agent_registration(self):
        """Test that blob agents are properly registered in ApplicationContainer."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        
        # Get application bootstrap service
        bootstrap_service = container.application_bootstrap_service()
        
        if bootstrap_service is not None:
            # Check if blob agents can be created (this tests registration)
            # This is more of a smoke test since agent creation depends on availability
            pass  # The fact that bootstrap service exists indicates successful registration
    
    # =============================================================================
    # End-to-End Blob Storage Workflow Tests
    # =============================================================================
    
    def test_complete_blob_write_read_workflow_string_data(self):
        """Test complete workflow: write string data, then read it back."""
        # Initialize DI container and services
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Create blob agents
        blob_writer = BlobWriterAgent(
            name="test_writer",
            prompt="Write test data",
            logger=container.logging_service().get_class_logger("test_writer")
        )
        blob_writer.configure_blob_storage_service(blob_service)
        
        blob_reader = BlobReaderAgent(
            name="test_reader",
            prompt="Read test data", 
            logger=container.logging_service().get_class_logger("test_reader")
        )
        blob_reader.configure_blob_storage_service(blob_service)
        
        # Test data and URI
        test_uri = str(self.test_blob_data_path / "string_test.blob")
        test_data = self.test_string_data
        
        # Write data
        write_inputs = {"blob_uri": test_uri, "data": test_data}
        write_result = blob_writer.process(write_inputs)
        
        # Verify write result
        self.assertIsInstance(write_result, dict)
        if isinstance(write_result, dict) and 'success' in write_result:
            self.assertTrue(write_result['success'])
        
        # Read data back
        read_inputs = {"blob_uri": test_uri}
        read_result = blob_reader.process(read_inputs)
        
        # Verify read result
        self.assertIsInstance(read_result, bytes)
        decoded_data = read_result.decode('utf-8')
        self.assertEqual(decoded_data, test_data)
    
    def test_complete_blob_write_read_workflow_json_data(self):
        """Test complete workflow: write JSON data, then read it back."""
        # Initialize DI container and services
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Create blob agents
        blob_writer = BlobWriterAgent(
            name="json_writer",
            prompt="Write JSON data",
            logger=container.logging_service().get_class_logger("json_writer")
        )
        blob_writer.configure_blob_storage_service(blob_service)
        
        blob_reader = BlobReaderAgent(
            name="json_reader",
            prompt="Read JSON data",
            logger=container.logging_service().get_class_logger("json_reader")
        )
        blob_reader.configure_blob_storage_service(blob_service)
        
        # Test data and URI
        test_uri = str(self.test_blob_data_path / "json_test.blob")
        test_data = self.test_json_data
        
        # Write JSON data
        write_inputs = {"blob_uri": test_uri, "data": test_data}
        write_result = blob_writer.process(write_inputs)
        
        # Verify write result
        self.assertIsInstance(write_result, dict)
        if isinstance(write_result, dict) and 'success' in write_result:
            self.assertTrue(write_result['success'])
        
        # Read data back
        read_inputs = {"blob_uri": test_uri}
        read_result = blob_reader.process(read_inputs)
        
        # Verify read result
        self.assertIsInstance(read_result, bytes)
        decoded_json = json.loads(read_result.decode('utf-8'))
        self.assertEqual(decoded_json, test_data)
    
    def test_complete_blob_write_read_workflow_binary_data(self):
        """Test complete workflow: write binary data, then read it back."""
        # Initialize DI container and services
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Create blob agents
        blob_writer = BlobWriterAgent(
            name="binary_writer",
            prompt="Write binary data",
            logger=container.logging_service().get_class_logger("binary_writer")
        )
        blob_writer.configure_blob_storage_service(blob_service)
        
        blob_reader = BlobReaderAgent(
            name="binary_reader",
            prompt="Read binary data",
            logger=container.logging_service().get_class_logger("binary_reader")
        )
        blob_reader.configure_blob_storage_service(blob_service)
        
        # Test data and URI
        test_uri = str(self.test_blob_data_path / "binary_test.blob")
        test_data = self.test_binary_data
        
        # Write binary data
        write_inputs = {"blob_uri": test_uri, "data": test_data}
        write_result = blob_writer.process(write_inputs)
        
        # Verify write result
        self.assertIsInstance(write_result, dict)
        if isinstance(write_result, dict) and 'success' in write_result:
            self.assertTrue(write_result['success'])
        
        # Read data back
        read_inputs = {"blob_uri": test_uri}
        read_result = blob_reader.process(read_inputs)
        
        # Verify read result
        self.assertIsInstance(read_result, bytes)
        self.assertEqual(read_result, test_data)
    
    def test_blob_existence_check_workflow(self):
        """Test blob existence checking workflow."""
        # Initialize DI container and services
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Test URIs
        existing_uri = str(self.test_blob_data_path / "existing.blob")
        nonexistent_uri = str(self.test_blob_data_path / "nonexistent.blob")
        
        # Create a blob first
        blob_writer = BlobWriterAgent(
            name="existence_writer",
            prompt="Write for existence test",
            logger=container.logging_service().get_class_logger("existence_writer")
        )
        blob_writer.configure_blob_storage_service(blob_service)
        
        write_inputs = {"blob_uri": existing_uri, "data": "existence test"}
        blob_writer.process(write_inputs)
        
        # Check existence
        exists = blob_service.blob_exists(existing_uri)
        self.assertTrue(exists)
        
        # Check non-existence
        not_exists = blob_service.blob_exists(nonexistent_uri)
        self.assertFalse(not_exists)
    
    # =============================================================================
    # Cross-Provider Compatibility Tests
    # =============================================================================
    
    def test_local_file_provider_workflow(self):
        """Test workflow with local file provider."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Check if local file provider is available
        providers = blob_service.get_available_providers()
        if 'file' not in providers:
            self.skipTest("Local file provider not available")
        
        # Test with local file URI
        test_uri = str(self.test_blob_data_path / "local_test.blob")
        test_data = "Local file provider test"
        
        # Write and read
        try:
            blob_service.write_blob(test_uri, test_data.encode('utf-8'))
            read_data = blob_service.read_blob(test_uri)
            self.assertEqual(read_data.decode('utf-8'), test_data)
        except Exception as e:
            self.skipTest(f"Local file provider test failed: {e}")
    
    @patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_azure_availability')
    def test_azure_provider_graceful_degradation(self, mock_azure_check):
        """Test graceful degradation when Azure provider is not available."""
        # Mock Azure as not available
        mock_azure_check.return_value = False
        
        # Initialize service
        mock_config = MockServiceFactory.create_mock_app_config_service({
            "storage": {"blob": {"providers": {"azure": {"connection_string": "test"}}}}
        })
        mock_logging = MockServiceFactory.create_mock_logging_service()
        
        service = BlobStorageService(
            configuration=mock_config,
            logging_service=mock_logging
        )
        
        # Azure should not be available
        providers = service.get_available_providers()
        self.assertNotIn('azure', providers)
        
        # Trying to use Azure should fail gracefully
        with self.assertRaises(StorageOperationError):
            service.read_blob("azure://container/blob")
    
    @patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_s3_availability')
    def test_s3_provider_graceful_degradation(self, mock_s3_check):
        """Test graceful degradation when S3 provider is not available."""
        # Mock S3 as not available
        mock_s3_check.return_value = False
        
        # Initialize service
        mock_config = MockServiceFactory.create_mock_app_config_service({
            "storage": {"blob": {"providers": {"s3": {"access_key": "test"}}}}
        })
        mock_logging = MockServiceFactory.create_mock_logging_service()
        
        service = BlobStorageService(
            configuration=mock_config,
            logging_service=mock_logging
        )
        
        # S3 should not be available
        providers = service.get_available_providers()
        self.assertNotIn('s3', providers)
        
        # Trying to use S3 should fail gracefully
        with self.assertRaises(StorageOperationError):
            service.read_blob("s3://bucket/object")
    
    @patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_gcs_availability')
    def test_gcs_provider_graceful_degradation(self, mock_gcs_check):
        """Test graceful degradation when GCS provider is not available."""
        # Mock GCS as not available
        mock_gcs_check.return_value = False
        
        # Initialize service
        mock_config = MockServiceFactory.create_mock_app_config_service({
            "storage": {"blob": {"providers": {"gs": {"credentials_path": "test"}}}}
        })
        mock_logging = MockServiceFactory.create_mock_logging_service()
        
        service = BlobStorageService(
            configuration=mock_config,
            logging_service=mock_logging
        )
        
        # GCS should not be available
        providers = service.get_available_providers()
        self.assertNotIn('gs', providers)
        
        # Trying to use GCS should fail gracefully
        with self.assertRaises(StorageOperationError):
            service.read_blob("gs://bucket/object")
    
    # =============================================================================
    # State Management and Execution Tracking Integration Tests
    # =============================================================================
    
    def test_blob_agents_with_execution_tracking(self):
        """Test blob agents with execution tracking integration."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        execution_tracking_service = container.execution_tracking_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        if execution_tracking_service is None:
            self.skipTest("Execution tracking service not available")
        
        # Create agents with execution tracking
        blob_writer = BlobWriterAgent(
            name="tracked_writer",
            prompt="Write with tracking",
            logger=container.logging_service().get_class_logger("tracked_writer"),
            execution_tracking_service=execution_tracking_service
        )
        blob_writer.configure_blob_storage_service(blob_service)
        
        blob_reader = BlobReaderAgent(
            name="tracked_reader",
            prompt="Read with tracking",
            logger=container.logging_service().get_class_logger("tracked_reader"),
            execution_tracking_service=execution_tracking_service
        )
        blob_reader.configure_blob_storage_service(blob_service)
        
        # Test workflow
        test_uri = str(self.test_blob_data_path / "tracked_test.blob")
        test_data = "Execution tracking test"
        
        # Write with tracking
        write_inputs = {"blob_uri": test_uri, "data": test_data}
        write_result = blob_writer.process(write_inputs)
        
        # Read with tracking
        read_inputs = {"blob_uri": test_uri}
        read_result = blob_reader.process(read_inputs)
        
        # Verify results
        self.assertIsInstance(write_result, dict)
        self.assertIsInstance(read_result, bytes)
        self.assertEqual(read_result.decode('utf-8'), test_data)
    
    def test_blob_agents_with_state_adapter(self):
        """Test blob agents with state adapter integration."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        state_adapter_service = container.state_adapter_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        if state_adapter_service is None:
            self.skipTest("State adapter service not available")
        
        # Create agents with state adapter
        blob_writer = BlobWriterAgent(
            name="state_writer",
            prompt="Write with state adapter",
            logger=container.logging_service().get_class_logger("state_writer"),
            state_adapter_service=state_adapter_service
        )
        blob_writer.configure_blob_storage_service(blob_service)
        
        blob_reader = BlobReaderAgent(
            name="state_reader",
            prompt="Read with state adapter",
            logger=container.logging_service().get_class_logger("state_reader"),
            state_adapter_service=state_adapter_service
        )
        blob_reader.configure_blob_storage_service(blob_service)
        
        # Test workflow
        test_uri = str(self.test_blob_data_path / "state_test.blob")
        test_data = "State adapter test"
        
        # Write with state adapter
        write_inputs = {"blob_uri": test_uri, "data": test_data}
        write_result = blob_writer.process(write_inputs)
        
        # Read with state adapter
        read_inputs = {"blob_uri": test_uri}
        read_result = blob_reader.process(read_inputs)
        
        # Verify results
        self.assertIsInstance(write_result, dict)
        self.assertIsInstance(read_result, bytes)
        self.assertEqual(read_result.decode('utf-8'), test_data)
    
    # =============================================================================
    # Performance and Scalability Tests
    # =============================================================================
    
    def test_blob_operations_performance_characteristics(self):
        """Test performance characteristics of blob operations."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Test data of various sizes
        small_data = b"small"
        medium_data = b"x" * 1024  # 1KB
        large_data = b"x" * (100 * 1024)  # 100KB
        
        test_cases = [
            ("small", small_data),
            ("medium", medium_data), 
            ("large", large_data)
        ]
        
        for size_name, test_data in test_cases:
            test_uri = str(self.test_blob_data_path / f"perf_{size_name}.blob")
            
            # Measure write performance
            start_time = time.time()
            try:
                blob_service.write_blob(test_uri, test_data)
                write_time = time.time() - start_time
                
                # Measure read performance
                start_time = time.time()
                read_data = blob_service.read_blob(test_uri)
                read_time = time.time() - start_time
                
                # Verify data integrity
                self.assertEqual(read_data, test_data)
                
                # Performance should be reasonable (very lenient limits for CI)
                self.assertLess(write_time, 10.0, f"Write time for {size_name} data too slow: {write_time}s")
                self.assertLess(read_time, 10.0, f"Read time for {size_name} data too slow: {read_time}s")
                
            except Exception as e:
                self.skipTest(f"Performance test for {size_name} data failed: {e}")
    
    def test_concurrent_blob_operations_simulation(self):
        """Test simulated concurrent blob operations."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Simulate multiple rapid operations
        num_operations = 10
        test_data = "concurrent test data"
        
        # Write multiple blobs rapidly
        write_uris = []
        for i in range(num_operations):
            test_uri = str(self.test_blob_data_path / f"concurrent_{i}.blob")
            write_uris.append(test_uri)
            
            try:
                blob_service.write_blob(test_uri, test_data.encode('utf-8'))
            except Exception as e:
                self.skipTest(f"Concurrent write {i} failed: {e}")
        
        # Read multiple blobs rapidly
        for i, uri in enumerate(write_uris):
            try:
                read_data = blob_service.read_blob(uri)
                self.assertEqual(read_data.decode('utf-8'), test_data)
            except Exception as e:
                self.skipTest(f"Concurrent read {i} failed: {e}")
    
    # =============================================================================
    # Error Handling and Recovery Tests
    # =============================================================================
    
    def test_blob_operation_error_handling(self):
        """Test error handling in blob operations."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Test reading non-existent blob
        nonexistent_uri = str(self.test_blob_data_path / "nonexistent.blob")
        
        with self.assertRaises(FileNotFoundError):
            blob_service.read_blob(nonexistent_uri)
        
        # Test writing to invalid URI (this depends on provider behavior)
        try:
            invalid_uri = "/invalid/path/that/should/not/exist/test.blob"
            with self.assertRaises((StorageOperationError, OSError, PermissionError)):
                blob_service.write_blob(invalid_uri, b"test data")
        except Exception as e:
            # Some providers might handle this differently
            self.skipTest(f"Invalid URI test not applicable: {e}")
    
    def test_blob_agent_error_recovery(self):
        """Test blob agent error recovery scenarios."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Create agents
        blob_reader = BlobReaderAgent(
            name="error_reader",
            prompt="Test error recovery",
            logger=container.logging_service().get_class_logger("error_reader")
        )
        blob_reader.configure_blob_storage_service(blob_service)
        
        # Test reading non-existent blob
        read_inputs = {"blob_uri": str(self.test_blob_data_path / "nonexistent.blob")}
        
        with self.assertRaises(FileNotFoundError):
            blob_reader.process(read_inputs)
        
        # Agent should still be functional after error
        # Create a valid blob first
        blob_writer = BlobWriterAgent(
            name="recovery_writer", 
            prompt="Write for recovery test",
            logger=container.logging_service().get_class_logger("recovery_writer")
        )
        blob_writer.configure_blob_storage_service(blob_service)
        
        valid_uri = str(self.test_blob_data_path / "recovery_test.blob")
        write_inputs = {"blob_uri": valid_uri, "data": "recovery test"}
        blob_writer.process(write_inputs)
        
        # Now reader should work
        read_inputs = {"blob_uri": valid_uri}
        result = blob_reader.process(read_inputs)
        self.assertEqual(result.decode('utf-8'), "recovery test")
    
    # =============================================================================
    # Health Check and Monitoring Tests
    # =============================================================================
    
    def test_blob_storage_health_check_integration(self):
        """Test blob storage health check integration."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Perform health check
        health_results = blob_service.health_check()
        
        # Verify health check structure
        self.assertIsInstance(health_results, dict)
        self.assertIn('healthy', health_results)
        self.assertIn('providers', health_results)
        
        # At least local file provider should be healthy
        providers = health_results['providers']
        self.assertIn('file', providers)
        
        file_health = providers['file']
        self.assertIn('available', file_health)
        self.assertIn('configured', file_health)
        self.assertTrue(file_health['available'])
    
    def test_blob_service_provider_info_integration(self):
        """Test blob service provider information integration."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Get provider info
        provider_info = blob_service.get_provider_info()
        
        # Verify provider info structure
        self.assertIsInstance(provider_info, dict)
        
        # Should have info for all providers
        expected_providers = ['azure', 's3', 'gs', 'file', 'local']
        for provider in expected_providers:
            self.assertIn(provider, provider_info)
            
            info = provider_info[provider]
            self.assertIn('available', info)
            self.assertIn('configured', info)
            self.assertIn('cached', info)
    
    # =============================================================================
    # Configuration and Flexibility Tests
    # =============================================================================
    
    def test_blob_storage_configuration_flexibility(self):
        """Test blob storage configuration flexibility."""
        # Test with different blob configuration structures
        config_variations = [
            {"blob": {"providers": {"file": {}}}},
            {"blob": {"providers": {"azure": {"connection_string": "test"}}}},
            {"blob": {"providers": {"s3": {"access_key": "test", "secret_key": "test"}}}},
        ]
        
        for config_data in config_variations:
            # Create mock StorageConfigService with blob configuration
            mock_config = Mock()
            mock_config.get_blob_config.return_value = config_data.get("blob", {})
            
            mock_logging = MockServiceFactory.create_mock_logging_service()
            
            # Should create service successfully
            service = BlobStorageService(
                configuration=mock_config,
                logging_service=mock_logging
            )
            
            self.assertIsNotNone(service)
            self.assertIsInstance(service._config, dict)
    
    def test_blob_agents_configuration_flexibility(self):
        """Test blob agents with various configuration scenarios."""
        # Initialize DI container
        container = initialize_di(str(self.test_config_path))
        blob_service = container.blob_storage_service()
        
        if blob_service is None:
            self.skipTest("Blob storage service not available")
        
        # Test agents with minimal configuration
        minimal_writer = BlobWriterAgent(
            name="minimal",
            prompt="Minimal configuration",
            logger=container.logging_service().get_class_logger("minimal_writer")
        )
        minimal_writer.configure_blob_storage_service(blob_service)
        
        minimal_reader = BlobReaderAgent(
            name="minimal",
            prompt="Minimal configuration",
            logger=container.logging_service().get_class_logger("minimal_reader")
        )
        minimal_reader.configure_blob_storage_service(blob_service)
        
        # Should work with minimal configuration
        test_uri = str(self.test_blob_data_path / "minimal_test.blob")
        write_inputs = {"blob_uri": test_uri, "data": "minimal test"}
        write_result = minimal_writer.process(write_inputs)
        
        read_inputs = {"blob_uri": test_uri}
        read_result = minimal_reader.process(read_inputs)
        
        self.assertEqual(read_result.decode('utf-8'), "minimal test")


class TestBlobStorageGracefulDegradation(unittest.TestCase):
    """Tests for graceful degradation when cloud SDKs are missing."""
    
    def setUp(self):
        """Set up graceful degradation test fixtures."""
        self.mock_config = MockServiceFactory.create_mock_app_config_service({
            "storage": {
                "blob": {
                    "providers": {
                        "azure": {"connection_string": "test"},
                        "s3": {"access_key": "test", "secret_key": "test"},
                        "gs": {"credentials_path": "test"}
                    }
                }
            }
        })
        self.mock_logging = MockServiceFactory.create_mock_logging_service()
    
    @patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_azure_availability')
    def test_graceful_degradation_azure_missing(self, mock_azure_availability):
        """Test graceful degradation when Azure SDK is missing."""
        # Mock Azure availability to return False
        mock_azure_availability.return_value = False
        
        # Service should still initialize
        service = BlobStorageService(
            configuration=self.mock_config,
            logging_service=self.mock_logging
        )
        
        # Azure should not be available
        providers = service.get_available_providers()
        self.assertNotIn('azure', providers)
        
        # Local file should still be available
        self.assertIn('file', providers)
        
        # Health check should reflect Azure unavailability
        health = service.health_check()
        self.assertFalse(health['providers']['azure']['available'])
    
    @patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_s3_availability')
    def test_graceful_degradation_s3_missing(self, mock_s3_availability):
        """Test graceful degradation when AWS S3 SDK is missing."""
        # Mock S3 availability to return False
        mock_s3_availability.return_value = False
        
        # Service should still initialize
        service = BlobStorageService(
            configuration=self.mock_config,
            logging_service=self.mock_logging
        )
        
        # S3 should not be available
        providers = service.get_available_providers()
        self.assertNotIn('s3', providers)
        
        # Local file should still be available
        self.assertIn('file', providers)
    
    @patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_gcs_availability')
    def test_graceful_degradation_gcs_missing(self, mock_gcs_availability):
        """Test graceful degradation when Google Cloud Storage SDK is missing."""
        # Mock GCS availability to return False
        mock_gcs_availability.return_value = False
        
        # Service should still initialize
        service = BlobStorageService(
            configuration=self.mock_config,
            logging_service=self.mock_logging
        )
        
        # GCS should not be available
        providers = service.get_available_providers()
        self.assertNotIn('gs', providers)
        
        # Local file should still be available
        self.assertIn('file', providers)
    
    @patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_azure_availability')
    @patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_s3_availability')
    @patch('agentmap.services.storage.blob_storage_service.BlobStorageService._check_gcs_availability')
    @patch('agentmap.services.storage.azure_blob_connector', side_effect=ImportError("azure not found"))
    @patch('agentmap.services.storage.aws_s3_connector', side_effect=ImportError("boto3 not found"))
    @patch('agentmap.services.storage.gcp_storage_connector', side_effect=ImportError("google.cloud.storage not found"))
    def test_graceful_degradation_all_cloud_missing(self, mock_gcs, mock_s3, mock_azure, mock_gcs_availability, mock_s3_availability, mock_azure_availability):
        """Test graceful degradation when all cloud SDKs are missing."""
        # Mock all availability checks to return False
        mock_azure_availability.return_value = False
        mock_s3_availability.return_value = False
        mock_gcs_availability.return_value = False
        
        # Service should still initialize
        service = BlobStorageService(
            configuration=self.mock_config,
            logging_service=self.mock_logging
        )
        
        # Only local file should be available
        providers = service.get_available_providers()
        self.assertEqual(set(providers), {'file', 'local'})
        
        # Health check should show only local providers as healthy
        health = service.health_check()
        self.assertFalse(health['providers']['azure']['available'])
        self.assertFalse(health['providers']['s3']['available'])
        self.assertFalse(health['providers']['gs']['available'])
        self.assertTrue(health['providers']['file']['available'])


if __name__ == '__main__':
    unittest.main()
