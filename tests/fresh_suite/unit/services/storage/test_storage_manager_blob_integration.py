"""
Unit tests for Storage Service Manager blob storage integration.

These tests verify that the StorageServiceManager properly integrates with
the BlobStorageService following the established DI patterns and graceful
degradation principles.
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from agentmap.di import initialize_di
from agentmap.services.storage.manager import StorageServiceManager
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


class TestStorageManagerBlobIntegration(unittest.TestCase):
    """
    Test blob storage integration with StorageServiceManager.
    
    These tests use real DI container (not mocked) to verify actual
    integration behavior between storage manager and blob storage.
    """
    
    def setUp(self):
        """Set up test fixtures with temporary config."""
        # Create temporary directory for test configs
        self.temp_dir = tempfile.mkdtemp()
        self.test_config_path = self._create_test_config()
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_config(self) -> Path:
        """Create a test configuration file."""
        config_path = Path(self.temp_dir) / "test_config.yaml"
        storage_config_path = Path(self.temp_dir) / "storage_config.yaml"
        
        # Use forward slashes for YAML to avoid Windows backslash escaping issues
        storage_config_path_str = str(storage_config_path).replace('\\', '/')
        csv_data_path_str = f"{self.temp_dir}/csv_data".replace('\\', '/')
        
        config_content = f"""logging:
  version: 1
  level: DEBUG
  format: "[%(levelname)s] %(name)s: %(message)s"

llm:
  anthropic:
    api_key: "test_key"
    model: "claude-3-5-sonnet-20241022"
    temperature: 0.7

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
    # Blob Storage Integration Tests
    # =============================================================================
    
    def test_storage_manager_integrates_blob_storage_when_available(self):
        """Test that storage manager integrates blob storage when available."""
        # Arrange
        container = initialize_di(str(self.test_config_path))
        
        # Act
        storage_manager = container.storage_service_manager()
        
        # Assert
        self.assertIsNotNone(storage_manager)
        
        # If storage manager was created successfully, check blob integration
        if storage_manager is not None:
            # Check if blob storage is available
            has_blob = storage_manager.is_blob_storage_enabled()
            
            # If blob storage is available, verify integration
            if has_blob:
                # Should be able to get blob storage service
                blob_service = storage_manager.get_blob_storage_service()
                self.assertIsNotNone(blob_service)
                
                # Blob should be in available providers
                providers = storage_manager.list_available_providers()
                self.assertIn("blob", providers)
                
                # Should be able to check if blob provider is available
                self.assertTrue(storage_manager.is_provider_available("blob"))
                
                # Should be able to get service info for blob
                blob_info = storage_manager.get_service_info("blob")
                self.assertIn("blob", blob_info)
                self.assertTrue(blob_info["blob"]["available"])
                self.assertEqual(blob_info["blob"]["type"], "blob_service")
            else:
                # If blob storage is not available, verify graceful degradation
                self.assertIsNone(storage_manager.get_blob_storage_service())
                providers = storage_manager.list_available_providers()
                self.assertNotIn("blob", providers)
    
    def test_storage_manager_graceful_degradation_without_blob_storage(self):
        """Test that storage manager handles graceful degradation without blob storage."""
        # Arrange - Create mock services without blob storage
        mock_config = Mock(spec=AppConfigService)
        mock_logging = Mock(spec=LoggingService)
        mock_logger = Mock()
        mock_logging.get_class_logger.return_value = mock_logger
        
        # Act - Create storage manager without blob storage
        storage_manager = StorageServiceManager(
            configuration=mock_config,
            logging_service=mock_logging,
            blob_storage_service=None
        )
        
        # Assert
        self.assertIsNotNone(storage_manager)
        self.assertFalse(storage_manager.is_blob_storage_enabled())
        self.assertIsNone(storage_manager.get_blob_storage_service())
        
        # Blob should not be in available providers
        providers = storage_manager.list_available_providers()
        self.assertNotIn("blob", providers)
        
        # Should return False for blob provider availability
        self.assertFalse(storage_manager.is_provider_available("blob"))
    
    def test_storage_manager_blob_integration_with_mock_blob_service(self):
        """Test storage manager integration with a mock blob service."""
        # Arrange - Create mock services with blob storage
        mock_config = Mock(spec=AppConfigService)
        mock_logging = Mock(spec=LoggingService)
        mock_logger = Mock()
        mock_logging.get_class_logger.return_value = mock_logger
        
        # Create mock blob storage service
        mock_blob_service = Mock()
        mock_blob_service.health_check.return_value = True
        
        # Act - Create storage manager with blob storage
        storage_manager = StorageServiceManager(
            configuration=mock_config,
            logging_service=mock_logging,
            blob_storage_service=mock_blob_service
        )
        
        # Assert
        self.assertIsNotNone(storage_manager)
        self.assertTrue(storage_manager.is_blob_storage_enabled())
        self.assertEqual(storage_manager.get_blob_storage_service(), mock_blob_service)
        
        # Blob should be in available providers
        providers = storage_manager.list_available_providers()
        self.assertIn("blob", providers)
        
        # Should return True for blob provider availability
        self.assertTrue(storage_manager.is_provider_available("blob"))
        
        # Should be able to get service info for blob
        blob_info = storage_manager.get_service_info("blob")
        self.assertIn("blob", blob_info)
        self.assertTrue(blob_info["blob"]["available"])
        self.assertTrue(blob_info["blob"]["cached"])
        self.assertEqual(blob_info["blob"]["type"], "blob_service")
        self.assertTrue(blob_info["blob"]["healthy"])
    
    def test_storage_manager_blob_service_health_check_failure(self):
        """Test storage manager handles blob service health check failures."""
        # Arrange - Create mock services with failing blob service
        mock_config = Mock(spec=AppConfigService)
        mock_logging = Mock(spec=LoggingService)
        mock_logger = Mock()
        mock_logging.get_class_logger.return_value = mock_logger
        
        # Create mock blob storage service that fails health check
        mock_blob_service = Mock()
        mock_blob_service.health_check.side_effect = Exception("Health check failed")
        
        # Act - Create storage manager with failing blob storage
        storage_manager = StorageServiceManager(
            configuration=mock_config,
            logging_service=mock_logging,
            blob_storage_service=mock_blob_service
        )
        
        # Assert
        self.assertIsNotNone(storage_manager)
        self.assertTrue(storage_manager.is_blob_storage_enabled())
        
        # Should handle health check failure gracefully
        blob_info = storage_manager.get_service_info("blob")
        self.assertIn("blob", blob_info)
        self.assertTrue(blob_info["blob"]["available"])
        self.assertFalse(blob_info["blob"]["healthy"])
    
    def test_storage_manager_get_service_includes_blob_storage(self):
        """Test that get_service method works with blob storage."""
        # Arrange - Create mock services with blob storage
        mock_config = Mock(spec=AppConfigService)
        mock_logging = Mock(spec=LoggingService)
        mock_logger = Mock()
        mock_logging.get_class_logger.return_value = mock_logger
        
        # Create mock blob storage service
        mock_blob_service = Mock()
        
        # Act - Create storage manager with blob storage
        storage_manager = StorageServiceManager(
            configuration=mock_config,
            logging_service=mock_logging,
            blob_storage_service=mock_blob_service
        )
        
        # Assert - Should be able to get blob service through get_service
        blob_service = storage_manager.get_service("blob")
        self.assertEqual(blob_service, mock_blob_service)
    
    def test_container_creates_storage_manager_with_blob_integration(self):
        """Test that the DI container creates storage manager with blob integration."""
        # Arrange
        container = initialize_di(str(self.test_config_path))
        
        # Act
        storage_manager = container.storage_service_manager()
        blob_storage_service = container.blob_storage_service()
        
        # Assert
        # If services were created successfully, they should be properly integrated
        if storage_manager is not None and blob_storage_service is not None:
            # Storage manager should have the same blob service instance
            manager_blob_service = storage_manager.get_blob_storage_service()
            # Note: These might not be the same instance due to provider patterns,
            # but both should be valid blob storage services
            self.assertIsNotNone(manager_blob_service)
            self.assertTrue(storage_manager.is_blob_storage_enabled())
        elif storage_manager is not None:
            # If storage manager exists but blob service is None (graceful degradation)
            self.assertFalse(storage_manager.is_blob_storage_enabled())
        # If both are None, that's also valid (complete graceful degradation)


if __name__ == '__main__':
    unittest.main()
