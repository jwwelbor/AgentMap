"""
Unit tests for StorageServiceManager.

These tests validate the StorageServiceManager implementation including:
- Storage backend coordination
- Storage type selection and fallback
- Provider registration and management
- Service lifecycle management
- Health checking across providers
- Configuration management
"""

import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Type

from agentmap.services.storage.manager import StorageServiceManager
from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.types import (
    StorageServiceConfigurationError,
    StorageServiceNotAvailableError,
    StorageResult
)
from tests.utils.mock_service_factory import MockServiceFactory


class MockStorageService(BaseStorageService):
    """Mock storage service for testing."""
    
    def __init__(self, provider_name: str, configuration: Any, logging_service: Any, 
                 file_path_service: Any = None, base_directory: Any = None):
        super().__init__(provider_name, configuration, logging_service, file_path_service, base_directory)
        self.is_healthy = True
        self.initialization_error = None
    
    def _initialize_client(self) -> Any:
        if self.initialization_error:
            raise self.initialization_error
        return {"mock": "client"}
    
    def _perform_health_check(self) -> bool:
        return self.is_healthy
    
    def read(self, collection: str, document_id=None, query=None, path=None, **kwargs) -> Any:
        return {"mock": "read_result", "collection": collection}
    
    def write(self, collection: str, data: Any, document_id=None, mode=None, path=None, **kwargs):
        return StorageResult(success=True, operation="write", collection=collection)
    
    def delete(self, collection: str, document_id=None, path=None, **kwargs):
        return StorageResult(success=True, operation="delete", collection=collection)


class FailingStorageService(BaseStorageService):
    """Storage service that fails initialization for testing."""
    
    def _initialize_client(self) -> Any:
        raise Exception("Initialization failed")
    
    def _perform_health_check(self) -> bool:
        return False
    
    def read(self, collection: str, document_id=None, query=None, path=None, **kwargs) -> Any:
        raise Exception("Read failed")
    
    def write(self, collection: str, data: Any, document_id=None, mode=None, path=None, **kwargs):
        raise Exception("Write failed")
    
    def delete(self, collection: str, document_id=None, path=None, **kwargs):
        raise Exception("Delete failed")


class MockStorageServiceFactory:
    """Mock factory for creating storage services."""
    
    def __init__(self, service_class: Type[BaseStorageService]):
        self.service_class = service_class
    
    def create_service(self, provider_name: str, config_data: Dict[str, Any]):
        # Mock configuration object
        mock_config = Mock()
        mock_config.get_value.side_effect = lambda key, default=None: config_data.get(key, default)
        
        # Mock logging service
        mock_logging = Mock()
        mock_logging.get_class_logger.return_value = Mock()
        
        # Mock file path service
        mock_file_path = Mock()
        
        return self.service_class(provider_name, mock_config, mock_logging, mock_file_path)


class TestStorageServiceManager(unittest.TestCase):
    """Unit tests for StorageServiceManager with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_file_path_service = MockServiceFactory.create_mock_file_path_service()
        self.mock_storage_config_service = MockServiceFactory.create_mock_storage_config_service({
            "csv": {
                "enabled": True,
                "default_directory": "/tmp/csv",
                "collections": {
                    "memory": {"filename": "memory.csv"},
                    "test": {"filename": "test.csv"}
                }
            },
            "vector": {"enabled": False},
            "kv": {"enabled": False}
        })
        
        # Patch auto-registration to avoid import issues in tests
        with patch.object(StorageServiceManager, '_auto_register_providers'):
            # Create StorageServiceManager with mocked dependencies
            self.manager = StorageServiceManager(
                configuration=self.mock_storage_config_service,
                logging_service=self.mock_logging_service,
                file_path_service=self.mock_file_path_service
            )
        
        # Get the mock logger for verification
        self.mock_logger = self.manager._logger
    
    def tearDown(self):
        """Clean up after each test."""
        # Shutdown manager to clean up resources
        self.manager.shutdown()
    
    # =============================================================================
    # 1. Manager Initialization Tests
    # =============================================================================
    
    def test_manager_initialization(self):
        """Test that manager initializes correctly with all dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.manager.configuration, self.mock_storage_config_service)
        self.assertEqual(self.manager.logging_service, self.mock_logging_service)
        self.assertEqual(self.manager.file_path_service, self.mock_file_path_service)
        self.assertIsNotNone(self.manager._logger)
        
        # Verify internal storage structures are initialized
        self.assertIsInstance(self.manager._services, dict)
        self.assertIsInstance(self.manager._service_classes, dict)
        self.assertIsInstance(self.manager._factories, dict)
        
        # Initially empty (auto-registration is mocked)
        self.assertEqual(len(self.manager._services), 0)
        self.assertEqual(len(self.manager._service_classes), 0)
        self.assertEqual(len(self.manager._factories), 0)
    
    @patch('agentmap.services.storage.register_all_providers')
    def test_auto_register_providers_success(self, mock_register_all):
        """Test successful auto-registration of providers."""
        # Create manager with real auto-registration
        manager = StorageServiceManager(
            configuration=self.mock_storage_config_service,
            logging_service=self.mock_logging_service,
            file_path_service=self.mock_file_path_service
        )
        
        # Verify auto-registration was called
        mock_register_all.assert_called_once_with(manager)
        
        manager.shutdown()
    
    @patch('agentmap.services.storage.register_all_providers')
    def test_auto_register_providers_import_error(self, mock_register_all):
        """Test auto-registration with import error."""
        mock_register_all.side_effect = ImportError("Module not found")
        
        # Should not fail even if auto-registration fails
        manager = StorageServiceManager(
            configuration=self.mock_storage_config_service,
            logging_service=self.mock_logging_service,
            file_path_service=self.mock_file_path_service
        )
        
        # Manager should still be created
        self.assertIsNotNone(manager)
        
        manager.shutdown()
    
    @patch('agentmap.services.storage.register_all_providers')
    def test_auto_register_providers_general_error(self, mock_register_all):
        """Test auto-registration with general error."""
        mock_register_all.side_effect = Exception("Registration failed")
        
        # Should not fail even if auto-registration fails
        manager = StorageServiceManager(
            configuration=self.mock_storage_config_service,
            logging_service=self.mock_logging_service,
            file_path_service=self.mock_file_path_service
        )
        
        # Manager should still be created
        self.assertIsNotNone(manager)
        
        manager.shutdown()
    
    # =============================================================================
    # 2. Provider Registration Tests
    # =============================================================================
    
    def test_register_provider_success(self):
        """Test successful provider registration."""
        # Register a provider
        self.manager.register_provider("mock", MockStorageService)
        
        # Verify provider was registered
        self.assertIn("mock", self.manager._service_classes)
        self.assertEqual(self.manager._service_classes["mock"], MockStorageService)
        
        # Verify it's available
        self.assertTrue(self.manager.is_provider_available("mock"))
        self.assertIn("mock", self.manager.list_available_providers())
    
    def test_register_provider_invalid_class(self):
        """Test registering provider with invalid class."""
        # Try to register non-BaseStorageService class
        class InvalidService:
            pass
        
        with self.assertRaises(StorageServiceConfigurationError) as context:
            self.manager.register_provider("invalid", InvalidService)
        
        self.assertIn("must inherit from BaseStorageService", str(context.exception))
        
        # Verify provider was not registered
        self.assertNotIn("invalid", self.manager._service_classes)
    
    def test_register_factory_success(self):
        """Test successful factory registration."""
        mock_factory = MockStorageServiceFactory(MockStorageService)
        
        # Register factory
        self.manager.register_factory("factory_provider", mock_factory)
        
        # Verify factory was registered
        self.assertIn("factory_provider", self.manager._factories)
        self.assertEqual(self.manager._factories["factory_provider"], mock_factory)
        
        # Verify it's available
        self.assertTrue(self.manager.is_provider_available("factory_provider"))
        self.assertIn("factory_provider", self.manager.list_available_providers())
    
    def test_list_available_providers(self):
        """Test listing available providers."""
        # Initially empty
        providers = self.manager.list_available_providers()
        self.assertEqual(len(providers), 0)
        
        # Register some providers
        self.manager.register_provider("provider1", MockStorageService)
        self.manager.register_provider("provider2", MockStorageService)
        
        mock_factory = MockStorageServiceFactory(MockStorageService)
        self.manager.register_factory("factory1", mock_factory)
        
        # Should list all providers
        providers = self.manager.list_available_providers()
        self.assertEqual(len(providers), 3)
        self.assertIn("provider1", providers)
        self.assertIn("provider2", providers)
        self.assertIn("factory1", providers)
        
        # Should be sorted
        self.assertEqual(providers, sorted(providers))
    
    def test_is_provider_available(self):
        """Test provider availability checking."""
        # Not available initially
        self.assertFalse(self.manager.is_provider_available("nonexistent"))
        
        # Register provider
        self.manager.register_provider("test_provider", MockStorageService)
        
        # Should be available now
        self.assertTrue(self.manager.is_provider_available("test_provider"))
        
        # Register factory
        mock_factory = MockStorageServiceFactory(MockStorageService)
        self.manager.register_factory("test_factory", mock_factory)
        
        # Should be available too
        self.assertTrue(self.manager.is_provider_available("test_factory"))
    
    # =============================================================================
    # 3. Service Creation Tests
    # =============================================================================
    
    def test_get_service_from_class(self):
        """Test getting service from registered class."""
        # Register provider
        self.manager.register_provider("test_provider", MockStorageService)
        
        # Get service
        service = self.manager.get_service("test_provider")
        
        # Verify service was created
        self.assertIsInstance(service, MockStorageService)
        self.assertEqual(service.provider_name, "test_provider")
        
        # Verify service is cached
        self.assertIn("test_provider", self.manager._services)
        self.assertEqual(self.manager._services["test_provider"], service)
        
        # Second call should return cached service
        service2 = self.manager.get_service("test_provider")
        self.assertEqual(service, service2)
    
    def test_get_service_from_factory(self):
        """Test getting service from registered factory."""
        # Register factory
        mock_factory = MockStorageServiceFactory(MockStorageService)
        self.manager.register_factory("factory_provider", mock_factory)
        
        # Get service
        service = self.manager.get_service("factory_provider")
        
        # Verify service was created
        self.assertIsInstance(service, MockStorageService)
        self.assertEqual(service.provider_name, "factory_provider")
        
        # Verify service is cached
        self.assertIn("factory_provider", self.manager._services)
    
    def test_get_service_not_available(self):
        """Test getting service that is not available."""
        with self.assertRaises(StorageServiceNotAvailableError) as context:
            self.manager.get_service("nonexistent_provider")
        
        error_msg = str(context.exception)
        self.assertIn("not registered", error_msg)
        self.assertIn("Available providers:", error_msg)
    
    def test_get_service_creation_failure(self):
        """Test service creation failure when client is accessed."""
        # Register provider that fails initialization
        self.manager.register_provider("failing_provider", FailingStorageService)
        
        # Service creation should succeed (lazy initialization)
        service = self.manager.get_service("failing_provider")
        self.assertIsInstance(service, FailingStorageService)
        
        # But accessing the client should fail
        with self.assertRaises(StorageServiceConfigurationError) as context:
            _ = service.client
        
        self.assertIn("Failed to initialize failing_provider client", str(context.exception))
    
    def test_get_service_factory_creation_failure(self):
        """Test factory service creation failure when client is accessed."""
        # Create factory that fails
        failing_factory = MockStorageServiceFactory(FailingStorageService)
        self.manager.register_factory("failing_factory", failing_factory)
        
        # Service creation should succeed (lazy initialization)
        service = self.manager.get_service("failing_factory")
        self.assertIsInstance(service, FailingStorageService)
        
        # But accessing the client should fail
        with self.assertRaises(StorageServiceConfigurationError) as context:
            _ = service.client
        
        self.assertIn("Failed to initialize failing_factory client", str(context.exception))
    
    def test_get_default_service(self):
        """Test getting default service."""
        # Register csv provider (which is the determined default based on StorageConfigService)
        self.manager.register_provider("csv", MockStorageService)
        
        # Get default service
        service = self.manager.get_default_service()
        
        # Should return csv service (determined as default by StorageConfigService)
        self.assertIsInstance(service, MockStorageService)
        self.assertEqual(service.provider_name, "csv")
    
    def test_get_default_service_not_configured(self):
        """Test getting default service when no default provider is configured."""
        # Create a new manager with a config that doesn't have default_provider set
        mock_config_without_default = MockServiceFactory.create_mock_app_config_service({
            "storage": {
                "csv": {"options": {"base_directory": "/tmp/csv"}}
                # No "default_provider" key - should fallback to "csv"
            }
        })
        
        # Patch auto-registration to avoid import issues
        with patch.object(StorageServiceManager, '_auto_register_providers'):
            manager = StorageServiceManager(
                configuration=mock_config_without_default,
                logging_service=self.mock_logging_service,
                file_path_service=self.mock_file_path_service
            )
        
        # Register csv provider (the hardcoded fallback)
        manager.register_provider("csv", MockStorageService)
        
        # Get default service (should fallback to csv)
        service = manager.get_default_service()
        
        self.assertIsInstance(service, MockStorageService)
        self.assertEqual(service.provider_name, "csv")
        
        # Clean up
        manager.shutdown()
    
    def test_get_default_service_configured_but_unavailable(self):
        """Test getting default service when configured provider is not available."""
        # Create a config that disables CSV but enables vector storage to test unavailable scenario
        mock_config_no_csv = MockServiceFactory.create_mock_storage_config_service({
            "csv": {"enabled": False},
            "vector": {"enabled": True, "provider": "local"},
            "kv": {"enabled": False}
        })
        
        # Create a new manager with this config
        with patch.object(StorageServiceManager, '_auto_register_providers'):
            test_manager = StorageServiceManager(
                configuration=mock_config_no_csv,
                logging_service=self.mock_logging_service,
                file_path_service=self.mock_file_path_service
            )
        
        # Register a different provider to show it doesn't fall back
        test_manager.register_provider("memory", MockStorageService)
        
        # Should fail because vector storage is enabled but "local" provider is not registered
        with self.assertRaises(StorageServiceNotAvailableError) as context:
            test_manager.get_default_service()
        
        error_msg = str(context.exception)
        self.assertIn("local", error_msg)
        self.assertIn("not registered", error_msg)
        self.assertIn("Available providers: memory", error_msg)
        
        # Clean up
        test_manager.shutdown()
    
    def test_get_default_service_not_available(self):
        """Test getting default service when not available."""
        # Don't register any providers
        
        with self.assertRaises(StorageServiceNotAvailableError):
            self.manager.get_default_service()
    
    # =============================================================================
    # 4. Health Check Tests
    # =============================================================================
    
    def test_health_check_all_providers(self):
        """Test health check for all providers."""
        # Register providers
        self.manager.register_provider("healthy", MockStorageService)
        self.manager.register_provider("unhealthy", MockStorageService)
        
        # Get services to initialize them
        healthy_service = self.manager.get_service("healthy")
        unhealthy_service = self.manager.get_service("unhealthy")
        
        # Make one unhealthy
        unhealthy_service.is_healthy = False
        
        # Perform health check
        results = self.manager.health_check()
        
        # Verify results
        self.assertIn("healthy", results)
        self.assertIn("unhealthy", results)
        self.assertTrue(results["healthy"])
        self.assertFalse(results["unhealthy"])
    
    def test_health_check_specific_provider(self):
        """Test health check for specific provider."""
        # Register provider
        self.manager.register_provider("test_provider", MockStorageService)
        
        # Perform health check on specific provider
        results = self.manager.health_check("test_provider")
        
        # Should only contain the specific provider
        self.assertEqual(len(results), 1)
        self.assertIn("test_provider", results)
        self.assertTrue(results["test_provider"])
    
    def test_health_check_provider_creation_failure(self):
        """Test health check when provider creation fails."""
        # Register failing provider
        self.manager.register_provider("failing", FailingStorageService)
        
        # Health check should handle creation failure
        results = self.manager.health_check("failing")
        
        self.assertIn("failing", results)
        self.assertFalse(results["failing"])
    
    def test_health_check_nonexistent_provider(self):
        """Test health check for non-existent provider."""
        # Health check should handle non-existent provider
        results = self.manager.health_check("nonexistent")
        
        self.assertIn("nonexistent", results)
        self.assertFalse(results["nonexistent"])
    
    # =============================================================================
    # 5. Cache Management Tests
    # =============================================================================
    
    def test_clear_cache_all(self):
        """Test clearing all cached services."""
        # Register and get services
        self.manager.register_provider("provider1", MockStorageService)
        self.manager.register_provider("provider2", MockStorageService)
        
        service1 = self.manager.get_service("provider1")
        service2 = self.manager.get_service("provider2")
        
        # Verify services are cached
        self.assertEqual(len(self.manager._services), 2)
        
        # Clear cache
        self.manager.clear_cache()
        
        # Verify cache is empty
        self.assertEqual(len(self.manager._services), 0)
    
    def test_clear_cache_specific_provider(self):
        """Test clearing cache for specific provider."""
        # Register and get services
        self.manager.register_provider("provider1", MockStorageService)
        self.manager.register_provider("provider2", MockStorageService)
        
        service1 = self.manager.get_service("provider1")
        service2 = self.manager.get_service("provider2")
        
        # Clear cache for specific provider
        self.manager.clear_cache("provider1")
        
        # Verify only specific provider was cleared
        self.assertNotIn("provider1", self.manager._services)
        self.assertIn("provider2", self.manager._services)
    
    def test_clear_cache_nonexistent_provider(self):
        """Test clearing cache for non-existent provider."""
        # Should not raise error
        self.manager.clear_cache("nonexistent")
        
        # Cache should still be empty
        self.assertEqual(len(self.manager._services), 0)
    
    # =============================================================================
    # 6. Service Information Tests
    # =============================================================================
    
    def test_get_service_info_all_providers(self):
        """Test getting information for all providers."""
        # Register different types of providers
        self.manager.register_provider("class_provider", MockStorageService)
        
        mock_factory = MockStorageServiceFactory(MockStorageService)
        self.manager.register_factory("factory_provider", mock_factory)
        
        # Get one service to cache it
        self.manager.get_service("class_provider")
        
        # Get service info
        info = self.manager.get_service_info()
        
        # Verify info structure
        self.assertIn("class_provider", info)
        self.assertIn("factory_provider", info)
        
        # Check class provider info
        class_info = info["class_provider"]
        self.assertTrue(class_info["available"])
        self.assertTrue(class_info["cached"])
        self.assertEqual(class_info["type"], "class")
        self.assertIn("healthy", class_info)
        
        # Check factory provider info
        factory_info = info["factory_provider"]
        self.assertTrue(factory_info["available"])
        self.assertFalse(factory_info["cached"])
        self.assertEqual(factory_info["type"], "factory")
        self.assertNotIn("healthy", factory_info)  # Not cached, so no health info
    
    def test_get_service_info_specific_provider(self):
        """Test getting information for specific provider."""
        # Register provider
        self.manager.register_provider("test_provider", MockStorageService)
        
        # Get service info for specific provider
        info = self.manager.get_service_info("test_provider")
        
        # Should only contain the specific provider
        self.assertEqual(len(info), 1)
        self.assertIn("test_provider", info)
        
        provider_info = info["test_provider"]
        self.assertTrue(provider_info["available"])
        self.assertFalse(provider_info["cached"])
        self.assertEqual(provider_info["type"], "class")
    
    def test_get_service_info_with_health_check_failure(self):
        """Test service info when health check fails."""
        # Register provider and get service
        self.manager.register_provider("test_provider", MockStorageService)
        service = self.manager.get_service("test_provider")
        
        # Make health check fail
        service.is_healthy = False
        
        # Get service info
        info = self.manager.get_service_info("test_provider")
        
        provider_info = info["test_provider"]
        self.assertTrue(provider_info["cached"])
        self.assertFalse(provider_info["healthy"])
    
    def test_get_service_info_with_health_check_exception(self):
        """Test service info when health check raises exception."""
        # Register provider and get service
        self.manager.register_provider("test_provider", MockStorageService)
        service = self.manager.get_service("test_provider")
        
        # Mock health_check to raise exception
        with patch.object(service, 'health_check', side_effect=Exception("Health check failed")):
            # Get service info
            info = self.manager.get_service_info("test_provider")
            
            provider_info = info["test_provider"]
            self.assertTrue(provider_info["cached"])
            self.assertFalse(provider_info["healthy"])
    
    # =============================================================================
    # 7. Manager Shutdown Tests
    # =============================================================================
    
    def test_shutdown(self):
        """Test manager shutdown."""
        # Register providers and get services
        self.manager.register_provider("provider1", MockStorageService)
        mock_factory = MockStorageServiceFactory(MockStorageService)
        self.manager.register_factory("factory1", mock_factory)
        
        service1 = self.manager.get_service("provider1")
        
        # Verify initial state
        self.assertTrue(len(self.manager._services) > 0)
        self.assertTrue(len(self.manager._service_classes) > 0)
        self.assertTrue(len(self.manager._factories) > 0)
        
        # Shutdown manager
        self.manager.shutdown()
        
        # Verify cleanup
        self.assertEqual(len(self.manager._services), 0)
        self.assertEqual(len(self.manager._service_classes), 0)
        self.assertEqual(len(self.manager._factories), 0)
    
    # =============================================================================
    # 8. Integration and End-to-End Tests
    # =============================================================================
    
    def test_complete_service_lifecycle(self):
        """Test complete service lifecycle from registration to usage."""
        # Register provider
        self.manager.register_provider("lifecycle_test", MockStorageService)
        
        # Verify provider is available
        self.assertTrue(self.manager.is_provider_available("lifecycle_test"))
        
        # Get service
        service = self.manager.get_service("lifecycle_test")
        self.assertIsInstance(service, MockStorageService)
        
        # Use service
        read_result = service.read("test_collection")
        self.assertEqual(read_result["collection"], "test_collection")
        
        write_result = service.write("test_collection", {"data": "test"})
        self.assertTrue(write_result.success)
        
        delete_result = service.delete("test_collection")
        self.assertTrue(delete_result.success)
        
        # Check health
        health_results = self.manager.health_check("lifecycle_test")
        self.assertTrue(health_results["lifecycle_test"])
        
        # Clear cache
        self.manager.clear_cache("lifecycle_test")
        self.assertNotIn("lifecycle_test", self.manager._services)
        
        # Get service again (should recreate)
        service2 = self.manager.get_service("lifecycle_test")
        self.assertIsInstance(service2, MockStorageService)
        self.assertNotEqual(service, service2)  # Different instance
    
    def test_multiple_provider_management(self):
        """Test managing multiple providers simultaneously."""
        # Register multiple providers of different types
        self.manager.register_provider("memory", MockStorageService)
        self.manager.register_provider("csv", MockStorageService)
        
        factory1 = MockStorageServiceFactory(MockStorageService)
        factory2 = MockStorageServiceFactory(MockStorageService)
        self.manager.register_factory("json", factory1)
        self.manager.register_factory("vector", factory2)
        
        # Get all services
        memory_service = self.manager.get_service("memory")
        csv_service = self.manager.get_service("csv")
        json_service = self.manager.get_service("json")
        vector_service = self.manager.get_service("vector")
        
        # Verify all services are different instances
        services = [memory_service, csv_service, json_service, vector_service]
        for i, service1 in enumerate(services):
            for j, service2 in enumerate(services):
                if i != j:
                    self.assertNotEqual(service1, service2)
        
        # Verify all services work
        for service in services:
            result = service.read("test")
            self.assertIsNotNone(result)
        
        # Health check all
        health_results = self.manager.health_check()
        self.assertEqual(len(health_results), 4)
        for provider_name, is_healthy in health_results.items():
            self.assertTrue(is_healthy)
        
        # Get service info for all
        info = self.manager.get_service_info()
        self.assertEqual(len(info), 4)
        
        # Verify provider types
        self.assertEqual(info["memory"]["type"], "class")
        self.assertEqual(info["csv"]["type"], "class")
        self.assertEqual(info["json"]["type"], "factory")
        self.assertEqual(info["vector"]["type"], "factory")
    
    def test_error_recovery_scenarios(self):
        """Test error recovery in various scenarios."""
        # Register both healthy and failing providers
        self.manager.register_provider("healthy", MockStorageService)
        self.manager.register_provider("failing", FailingStorageService)
        
        # Register the default provider so get_default_service() works
        # The StorageConfigService determines "csv" as the default provider
        self.manager.register_provider("csv", MockStorageService)
        
        # Get healthy service (should work)
        healthy_service = self.manager.get_service("healthy")
        self.assertIsInstance(healthy_service, MockStorageService)
        
        # Get failing service (should succeed due to lazy initialization)
        failing_service = self.manager.get_service("failing")
        self.assertIsInstance(failing_service, FailingStorageService)
        
        # But accessing the client should fail
        with self.assertRaises(StorageServiceConfigurationError):
            _ = failing_service.client
        
        # Health check should handle both
        health_results = self.manager.health_check()
        self.assertTrue(health_results["healthy"])
        self.assertFalse(health_results["failing"])
        
        # Service info should handle both
        info = self.manager.get_service_info()
        self.assertTrue(info["healthy"]["available"])
        self.assertTrue(info["failing"]["available"])  # Available but will fail
        
        # Manager should still function normally for healthy providers
        default_service = self.manager.get_default_service()
        self.assertIsNotNone(default_service)
    
    # =============================================================================
    # 9. Configuration Integration Tests
    # =============================================================================
    
    def test_configuration_integration(self):
        """Test integration with configuration service."""
        # Register provider
        self.manager.register_provider("config_test", MockStorageService)
        
        # Get service (should use configuration)
        service = self.manager.get_service("config_test")
        
        # Verify configuration was passed to service
        self.assertEqual(service.configuration, self.mock_storage_config_service)
        
        # Configuration should be used for provider-specific settings
        # This is tested through the service's behavior
        self.assertIsNotNone(service.client)  # Client should be initialized with config
    
    def test_factory_configuration_integration(self):
        """Test factory integration with configuration."""
        # Create factory that captures config data
        captured_config = {}
        
        class CapturingFactory:
            def create_service(self, provider_name, config_data):
                captured_config.update(config_data)
                return MockStorageService(provider_name, Mock(), Mock())
        
        # Register factory
        self.manager.register_factory("config_factory", CapturingFactory())
        
        # Get service
        service = self.manager.get_service("config_factory")
        
        # Verify configuration was passed to factory
        # The factory should receive config from configuration service
        self.assertIsInstance(service, MockStorageService)
    
    # =============================================================================
    # 10. Edge Cases and Error Conditions Tests
    # =============================================================================
    
    def test_register_same_provider_twice(self):
        """Test registering the same provider name twice."""
        # Register provider
        self.manager.register_provider("duplicate", MockStorageService)
        
        # Register again with different class (should overwrite)
        self.manager.register_provider("duplicate", FailingStorageService)
        
        # Should use the last registered class
        self.assertEqual(self.manager._service_classes["duplicate"], FailingStorageService)
    
    def test_register_provider_and_factory_same_name(self):
        """Test registering provider class and factory with same name."""
        # Register provider class
        self.manager.register_provider("same_name", MockStorageService)
        
        # Register factory with same name (should coexist)
        factory = MockStorageServiceFactory(MockStorageService)
        self.manager.register_factory("same_name", factory)
        
        # Both should be available
        self.assertIn("same_name", self.manager._service_classes)
        self.assertIn("same_name", self.manager._factories)
        
        # Getting service should prefer class over factory
        service = self.manager.get_service("same_name")
        self.assertIsInstance(service, MockStorageService)
    
    def test_empty_provider_name(self):
        """Test handling of empty provider names."""
        # Empty string
        with self.assertRaises(StorageServiceConfigurationError) as context:
            self.manager.register_provider("", MockStorageService)
        
        self.assertIn("Provider name must be a non-empty string", str(context.exception))
    
    def test_register_factory_invalid_name(self):
        """Test registering factory with invalid provider name."""
        mock_factory = MockStorageServiceFactory(MockStorageService)
        
        # Test empty string
        with self.assertRaises(StorageServiceConfigurationError) as context:
            self.manager.register_factory("", mock_factory)
        self.assertIn("Provider name must be a non-empty string", str(context.exception))
        
        # Test None
        with self.assertRaises(StorageServiceConfigurationError) as context:
            self.manager.register_factory(None, mock_factory)
        self.assertIn("Provider name must be a non-empty string", str(context.exception))
        
        # Test whitespace only
        with self.assertRaises(StorageServiceConfigurationError) as context:
            self.manager.register_factory("  \t\n  ", mock_factory)
        self.assertIn("Provider name must be a non-empty string", str(context.exception))
    
    def test_whitespace_only_provider_name(self):
        """Test handling of whitespace-only provider names."""
        # Whitespace only
        with self.assertRaises(StorageServiceConfigurationError) as context:
            self.manager.register_provider("   ", MockStorageService)
        
        self.assertIn("Provider name must be a non-empty string", str(context.exception))
    
    def test_none_provider_name(self):
        """Test handling of None provider names."""
        # None provider name
        with self.assertRaises(StorageServiceConfigurationError) as context:
            self.manager.register_provider(None, MockStorageService)
        
        self.assertIn("Provider name must be a non-empty string", str(context.exception))
    
    def test_special_characters_in_provider_names(self):
        """Test provider names with special characters."""
        special_names = [
            "provider-with-dashes",
            "provider_with_underscores",
            "provider.with.dots",
            "provider123"
        ]
        
        for name in special_names:
            # Should handle special characters
            self.manager.register_provider(name, MockStorageService)
            self.assertTrue(self.manager.is_provider_available(name))
            
            # Should be able to get service
            service = self.manager.get_service(name)
            self.assertIsInstance(service, MockStorageService)
            self.assertEqual(service.provider_name, name)
    
    def test_large_number_of_providers(self):
        """Test handling large number of providers."""
        # Register many providers
        for i in range(100):
            provider_name = f"provider_{i}"
            self.manager.register_provider(provider_name, MockStorageService)
        
        # All should be available
        providers = self.manager.list_available_providers()
        self.assertEqual(len(providers), 100)
        
        # Should be able to get any service
        service_50 = self.manager.get_service("provider_50")
        self.assertIsInstance(service_50, MockStorageService)
        
        # Health check should handle all
        health_results = self.manager.health_check()
        self.assertEqual(len(health_results), 100)
        
        # All should be healthy
        for is_healthy in health_results.values():
            self.assertTrue(is_healthy)
    
    def test_concurrent_access_simulation(self):
        """Test simulated concurrent access to manager."""
        # Register provider
        self.manager.register_provider("concurrent_test", MockStorageService)
        
        # Simulate multiple rapid accesses
        services = []
        for i in range(10):
            service = self.manager.get_service("concurrent_test")
            services.append(service)
        
        # All should be the same cached instance
        first_service = services[0]
        for service in services[1:]:
            self.assertEqual(service, first_service)
        
        # Simulate cache clearing and re-access
        self.manager.clear_cache("concurrent_test")
        
        new_service = self.manager.get_service("concurrent_test")
        self.assertNotEqual(new_service, first_service)


if __name__ == '__main__':
    unittest.main()
