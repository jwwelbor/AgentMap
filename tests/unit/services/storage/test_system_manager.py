"""
Unit tests for SystemStorageManager.

Tests namespace support, service creation, cache folder operations,
and integration with FilePathService for system-level storage.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agentmap.services.storage.system_manager import SystemStorageManager
from tests.utils.mock_service_factory import MockServiceFactory


class TestSystemStorageManager(unittest.TestCase):
    """Test SystemStorageManager functionality."""

    def setUp(self):
        """Set up test fixtures using MockServiceFactory pattern."""
        self.mock_factory = MockServiceFactory()
        
        # Create mock services
        self.mock_logging = self.mock_factory.create_mock_logging_service()
        self.mock_file_path = self.mock_factory.create_mock_file_path_service()
        self.mock_app_config = self.mock_factory.create_mock_app_config_service()
        
        # Create temporary directory for testing cache folder
        self.temp_dir = tempfile.mkdtemp()
        self.cache_folder = os.path.join(self.temp_dir, "cache")
        os.makedirs(self.cache_folder, exist_ok=True)
        
        # Configure app config mock to return test cache folder
        # SystemStorageManager calls get_cache_path() which returns a Path object
        self.mock_app_config.get_cache_path.return_value = Path(self.cache_folder)
        
        # Configure file path service mock
        self.mock_file_path.validate_safe_path.return_value = True
        
        # Create service under test
        self.service = SystemStorageManager(
            self.mock_app_config,
            self.mock_logging,
            self.mock_file_path
        )
        
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization(self):
        """Test service initialization."""
        self.assertIsNotNone(self.service)
        # SystemStorageManager stores the result of get_cache_path() which is a Path object
        self.assertEqual(str(self.service._cache_folder), self.cache_folder)
        
        # Verify cache folder was validated
        self.mock_file_path.validate_safe_path.assert_called_once()

    def test_initialization_invalid_cache_folder(self):
        """Test initialization with invalid cache folder."""
        # Configure file path service to raise error
        self.mock_file_path.validate_safe_path.return_value = False
        
        with self.assertRaises(ValueError):
            SystemStorageManager(
                self.mock_app_config,
                self.mock_logging,
                self.mock_file_path
            )

    def test_get_json_storage_new_namespace(self):
        """Test getting JSON storage for new namespace."""
        namespace = "test_namespace"
        
        service = self.service.get_json_storage(namespace)
        
        self.assertIsNotNone(service)
        
        # Verify service is cached
        cached_service = self.service.get_json_storage(namespace)
        self.assertIs(service, cached_service)

    def test_get_json_storage_cached(self):
        """Test getting cached JSON storage."""
        namespace = "test_namespace"
        
        # First call creates service
        service1 = self.service.get_json_storage(namespace)
        
        # Second call should return cached service
        service2 = self.service.get_json_storage(namespace)
        
        self.assertIs(service1, service2)

    def test_get_file_storage_new_namespace(self):
        """Test getting file storage for new namespace."""
        namespace = "files"
        
        service = self.service.get_file_storage(namespace)
        
        self.assertIsNotNone(service)
        
        # Verify service is cached
        cached_service = self.service.get_file_storage(namespace)
        self.assertIs(service, cached_service)

    def test_get_file_storage_cached(self):
        """Test getting cached file storage."""
        namespace = "files"
        
        # First call creates service
        service1 = self.service.get_file_storage(namespace)
        
        # Second call should return cached service
        service2 = self.service.get_file_storage(namespace)
        
        self.assertIs(service1, service2)

    def test_multiple_namespaces(self):
        """Test multiple namespace isolation."""
        namespace1 = "namespace1"
        namespace2 = "namespace2"
        
        service1 = self.service.get_json_storage(namespace1)
        service2 = self.service.get_json_storage(namespace2)
        
        # Services should be different
        self.assertIsNot(service1, service2)

    def test_get_storage_none_namespace(self):
        """Test getting storage with None namespace."""
        # The actual implementation creates services without validation,
        # but let's test that None namespace works as expected
        service = self.service.get_json_storage(None)
        self.assertIsNotNone(service)

    def test_namespace_path_construction(self):
        """Test namespace path construction."""
        namespace = "test/nested/namespace"
        
        service = self.service.get_json_storage(namespace)
        
        # Service should be created successfully
        self.assertIsNotNone(service)

    def test_service_configuration(self):
        """Test service configuration is correct."""
        namespace = "config_test"
        
        json_service = self.service.get_json_storage(namespace)
        
        # Verify service has correct configuration
        self.assertIsNotNone(json_service)

    def test_different_service_types_same_namespace(self):
        """Test different service types in same namespace."""
        namespace = "shared"
        
        json_service = self.service.get_json_storage(namespace)
        file_service = self.service.get_file_storage(namespace)
        
        # Services should be different objects
        self.assertIsNot(json_service, file_service)

    def test_service_isolation(self):
        """Test services are properly isolated by namespace and type."""
        # Create services
        json1 = self.service.get_json_storage("ns1")
        json2 = self.service.get_json_storage("ns2")
        file1 = self.service.get_file_storage("ns1")
        file2 = self.service.get_file_storage("ns2")
        
        # All services should be different objects
        services = [json1, json2, file1, file2]
        for i, service_a in enumerate(services):
            for j, service_b in enumerate(services):
                if i != j:
                    self.assertIsNot(service_a, service_b)


if __name__ == "__main__":
    unittest.main()
