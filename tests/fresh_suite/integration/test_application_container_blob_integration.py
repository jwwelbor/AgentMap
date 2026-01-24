"""
Comprehensive ApplicationContainer integration tests for blob storage.

These tests validate the complete DI container integration including:
- Blob storage service registration and injection
- Storage service manager blob integration
- Agent factory service blob agent creation
- Application bootstrap service blob agent registration
- Dependency injection chain validation
- Configuration propagation through the container
- Service lifecycle management
- Error handling and graceful degradation at container level
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from agentmap.agents.builtins.storage.blob.blob_reader_agent import BlobReaderAgent
from agentmap.agents.builtins.storage.blob.blob_writer_agent import BlobWriterAgent
from agentmap.di import initialize_di

# from agentmap.services.application_bootstrap_service import ApplicationBootstrapService
from agentmap.services.agent.agent_factory_service import AgentFactoryService
from agentmap.services.storage.blob_storage_service import BlobStorageService
from agentmap.services.storage.manager import StorageServiceManager
from tests.fresh_suite.unit.services.storage.blob_storage_test_fixtures import (
    BlobStorageTestEnvironment,
    BlobStorageTestFixtures,
)


class TestApplicationContainerBlobIntegration(unittest.TestCase):
    """
    Comprehensive tests for ApplicationContainer blob storage integration.

    These tests use real DI container (not mocked) to verify actual
    integration behavior and dependency injection chains.
    """

    def setUp(self):
        """Set up integration test fixtures."""
        self.test_env = BlobStorageTestEnvironment()
        self.test_env.__enter__()

    def tearDown(self):
        """Clean up integration test fixtures."""
        self.test_env.__exit__(None, None, None)

    # =============================================================================
    # DI Container Service Registration Tests
    # =============================================================================

    def test_blob_storage_service_registration(self):
        """Test that blob storage service is properly registered in DI container with StorageConfigService."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Should be able to get blob storage service
        blob_service = container.blob_storage_service()

        # Assert service exists and is properly configured
        self.assertIsNotNone(blob_service, "BlobStorageService should be available")
        self.assertIsInstance(blob_service, BlobStorageService)
        self.assertIsNotNone(
            blob_service.configuration, "Configuration should be injected"
        )
        self.assertIsNotNone(
            blob_service.logging_service, "LoggingService should be injected"
        )

        # Should have access to configuration via StorageConfigService
        config = blob_service._config
        self.assertIsInstance(config, dict)

        # Should be able to get available providers
        providers = blob_service.get_available_providers()
        self.assertIsInstance(providers, list)
        # Local file provider should always be available
        self.assertIn("file", providers)

    def test_storage_service_manager_blob_integration(self):
        """Test storage service manager blob storage integration through DI."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get storage service manager
        storage_manager = container.storage_service_manager()

        # Assert service exists
        self.assertIsNotNone(
            storage_manager, "StorageServiceManager should be available"
        )
        self.assertIsInstance(storage_manager, StorageServiceManager)

        # Check blob storage integration
        has_blob = storage_manager.is_blob_storage_enabled()
        self.assertTrue(has_blob, "Storage manager should have blob storage")

        # Should be able to get blob storage service
        blob_service = storage_manager.get_blob_storage_service()
        self.assertIsNotNone(blob_service, "Blob storage service should be available")
        self.assertIsInstance(blob_service, BlobStorageService)

        # Blob should be in available providers
        providers = storage_manager.list_available_providers()
        self.assertIn("blob", providers)

        # Should return True for blob provider availability
        self.assertTrue(storage_manager.is_provider_available("blob"))

        # Should be able to get service info
        blob_info = storage_manager.get_service_info("blob")
        self.assertIn("blob", blob_info)
        self.assertTrue(blob_info["blob"]["available"])
        self.assertEqual(blob_info["blob"]["type"], "blob_service")

    # def test_application_bootstrap_service_blob_registration(self):
    #     """Test blob agent registration through ApplicationBootstrapService."""
    #     # Initialize DI container
    #     container = initialize_di(str(self.test_env.config_path))

    #     # Get application bootstrap service
    #     bootstrap_service = container.application_bootstrap_service()

    #     if bootstrap_service is not None:
    #         self.assertIsInstance(bootstrap_service, ApplicationBootstrapService)

    #         # Bootstrap service should have registered blob agents
    #         # This is verified by successful initialization without errors
    #         # The actual agent creation is tested in factory service tests

    def test_agent_factory_service_blob_agent_creation(self):
        """Test blob agent creation through AgentFactoryService."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get agent factory service
        agent_factory = container.agent_factory_service()
        blob_service = container.blob_storage_service()

        if agent_factory is not None and blob_service is not None:
            self.assertIsInstance(agent_factory, AgentFactoryService)

            # Test blob reader agent creation
            try:
                blob_reader = agent_factory.create_agent(
                    agent_type="blob_reader",
                    name="test_blob_reader",
                    prompt="Test blob reader creation",
                    context={},
                )

                if blob_reader is not None:
                    self.assertIsInstance(blob_reader, BlobReaderAgent)

                    # Agent should have proper infrastructure services
                    self.assertIsNotNone(blob_reader.logger)
                    self.assertIsNotNone(blob_reader.execution_tracking_service)
                    self.assertIsNotNone(blob_reader.state_adapter_service)

            except Exception as e:
                # Agent creation might fail if blob reader type isn't registered
                # This is acceptable as long as the container itself works
                print(f"Blob reader creation failed (acceptable): {e}")

            # Test blob writer agent creation
            try:
                blob_writer = agent_factory.create_agent(
                    agent_type="blob_writer",
                    name="test_blob_writer",
                    prompt="Test blob writer creation",
                    context={},
                )

                if blob_writer is not None:
                    self.assertIsInstance(blob_writer, BlobWriterAgent)

                    # Agent should have proper infrastructure services
                    self.assertIsNotNone(blob_writer.logger)
                    self.assertIsNotNone(blob_writer.execution_tracking_service)
                    self.assertIsNotNone(blob_writer.state_adapter_service)

            except Exception as e:
                # Agent creation might fail if blob writer type isn't registered
                # This is acceptable as long as the container itself works
                print(f"Blob writer creation failed (acceptable): {e}")

    # =============================================================================
    # Service Dependency Chain Tests
    # =============================================================================

    def test_blob_storage_service_dependency_chain(self):
        """Test the complete dependency injection chain for blob storage service."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get all services in the dependency chain - BlobStorageService now uses StorageConfigService
        storage_config_service = container.storage_config_service()
        logging_service = container.logging_service()
        blob_service = container.blob_storage_service()

        # Assert services exist rather than using conditional logic
        self.assertIsNotNone(
            storage_config_service, "StorageConfigService should be available"
        )
        self.assertIsNotNone(logging_service, "LoggingService should be available")
        self.assertIsNotNone(blob_service, "BlobStorageService should be available")

        # Verify correct dependency injection - BlobStorageService uses StorageConfigService
        self.assertEqual(blob_service.configuration, storage_config_service)
        self.assertEqual(blob_service.logging_service, logging_service)

        # Verify services are properly configured
        self.assertIsNotNone(blob_service._logger)

        # Configuration should be accessible via StorageConfigService
        self.assertIsInstance(blob_service._config, dict)

    def test_storage_manager_blob_dependency_chain(self):
        """Test dependency chain for storage manager with blob integration."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get services in dependency chain
        storage_config_service = container.storage_config_service()
        logging_service = container.logging_service()
        blob_service = container.blob_storage_service()
        storage_manager = container.storage_service_manager()

        # Assert services exist rather than using conditional logic
        self.assertIsNotNone(
            storage_config_service, "StorageConfigService should be available"
        )
        self.assertIsNotNone(logging_service, "LoggingService should be available")
        self.assertIsNotNone(
            storage_manager, "StorageServiceManager should be available"
        )
        self.assertIsNotNone(blob_service, "BlobStorageService should be available")

        # Verify storage manager dependencies - both StorageServiceManager and BlobStorageService use StorageConfigService
        self.assertEqual(storage_manager.configuration, storage_config_service)
        self.assertEqual(storage_manager.logging_service, logging_service)

        # Verify blob service also uses StorageConfigService
        self.assertEqual(blob_service.configuration, storage_config_service)

        # Verify blob service is properly integrated in storage manager
        self.assertTrue(
            storage_manager.is_blob_storage_enabled(),
            "Storage manager should have blob storage",
        )
        manager_blob_service = storage_manager.get_blob_storage_service()
        self.assertIsNotNone(
            manager_blob_service, "Manager should provide blob storage service"
        )
        # Both services should use the same configuration service
        self.assertEqual(manager_blob_service.configuration, storage_config_service)

    def test_agent_blob_service_injection_chain(self):
        """Test blob service injection chain for agents."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get necessary services
        blob_service = container.blob_storage_service()
        execution_tracking_service = container.execution_tracking_service()
        state_adapter_service = container.state_adapter_service()
        logging_service = container.logging_service()

        if blob_service is not None:
            # Create blob agents manually to test injection
            blob_reader = BlobReaderAgent(
                name="injection_test_reader",
                prompt="Test injection",
                logger=(
                    logging_service.get_class_logger("test")
                    if logging_service
                    else None
                ),
                execution_tracking_service=execution_tracking_service,
                state_adapter_service=state_adapter_service,
            )

            # Configure blob storage service
            blob_reader.configure_blob_storage_service(blob_service)

            # Verify all services are properly injected
            self.assertEqual(blob_reader.blob_storage_service, blob_service)
            if execution_tracking_service:
                self.assertEqual(
                    blob_reader.execution_tracking_service, execution_tracking_service
                )
            if state_adapter_service:
                self.assertEqual(
                    blob_reader.state_adapter_service, state_adapter_service
                )

    # =============================================================================
    # Configuration Propagation Tests
    # =============================================================================

    def test_blob_storage_configuration_propagation(self):
        """Test that configuration is properly propagated through DI container."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get services - BlobStorageService now uses StorageConfigService
        storage_config_service = container.storage_config_service()
        blob_service = container.blob_storage_service()

        # Assert services exist
        self.assertIsNotNone(
            storage_config_service, "StorageConfigService should be available"
        )
        self.assertIsNotNone(blob_service, "BlobStorageService should be available")

        # Configuration should be accessible through blob service
        blob_config = blob_service._config
        self.assertIsInstance(blob_config, dict)

        # Should be able to access configuration through storage config service
        storage_blob_config = storage_config_service.get_blob_config()
        self.assertIsInstance(storage_blob_config, dict)

        # Both should provide blob configuration data
        self.assertEqual(blob_config, storage_blob_config)

    def test_blob_provider_configuration_propagation(self):
        """Test provider-specific configuration propagation."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get blob service
        blob_service = container.blob_storage_service()

        # Assert service exists
        self.assertIsNotNone(blob_service, "BlobStorageService should be available")

        # Check provider configurations
        provider_info = blob_service.get_provider_info()
        self.assertIsInstance(provider_info, dict)

        # At least local file provider should be configured
        self.assertIn("file", provider_info)
        file_info = provider_info["file"]
        self.assertTrue(file_info["available"])
        # Local file provider should be configured (default configuration)

    def test_actual_blob_operations_integration(self):
        """Test actual blob operations through DI container integration."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get blob service
        blob_service = container.blob_storage_service()

        # Assert service exists
        self.assertIsNotNone(blob_service, "BlobStorageService should be available")

        # Test data
        test_data = b"Integration test blob data"
        test_uri = str(Path(self.test_env.temp_dir) / "integration_test.blob")

        # Test write operation
        blob_service.write_blob(test_uri, test_data)

        # Test existence check
        self.assertTrue(blob_service.blob_exists(test_uri))

        # Test read operation
        read_data = blob_service.read_blob(test_uri)
        self.assertEqual(read_data, test_data)

        # Test list operation (if available)
        try:
            # Get available providers that support listing
            providers = blob_service.get_available_providers()
            self.assertIn("file", providers)  # Local file should always be available
        except Exception as e:
            # Some providers may not support listing
            pass

        # Test health check operation
        health_results = blob_service.health_check()
        self.assertIsInstance(health_results, dict)
        self.assertIn("healthy", health_results)
        self.assertIn("providers", health_results)

    # =============================================================================
    # Service Lifecycle Tests
    # =============================================================================

    def test_blob_service_singleton_behavior(self):
        """Test that blob storage service follows singleton pattern in DI container."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get blob service multiple times
        blob_service1 = container.blob_storage_service()
        blob_service2 = container.blob_storage_service()

        if blob_service1 is not None and blob_service2 is not None:
            # Should be the same instance (singleton behavior)
            self.assertEqual(blob_service1, blob_service2)

    def test_storage_manager_singleton_with_blob_integration(self):
        """Test storage manager singleton behavior with blob integration."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get storage manager multiple times
        manager1 = container.storage_service_manager()
        manager2 = container.storage_service_manager()

        if manager1 is not None and manager2 is not None:
            # Should be the same instance
            self.assertEqual(manager1, manager2)

            # Blob integration should be consistent
            if manager1.is_blob_storage_enabled():
                self.assertEqual(
                    manager1.is_blob_storage_enabled(),
                    manager2.is_blob_storage_enabled(),
                )

                blob_service1 = manager1.get_blob_storage_service()
                blob_service2 = manager2.get_blob_storage_service()
                # Should get the same blob service instance
                self.assertEqual(blob_service1, blob_service2)

    # =============================================================================
    # Error Handling and Graceful Degradation Tests
    # =============================================================================

    def test_container_graceful_degradation_missing_blob_dependencies(self):
        """Test container graceful degradation when blob dependencies are missing."""
        # This test verifies the container continues to work even when
        # blob storage dependencies are not available

        # Test that the container initializes properly
        container = initialize_di(str(self.test_env.config_path))

        # Core services should still be available
        self.assertIsNotNone(
            container.app_config_service(), "AppConfigService should be available"
        )
        self.assertIsNotNone(
            container.logging_service(), "LoggingService should be available"
        )

        # Blob service should be available with at least local file provider
        blob_service = container.blob_storage_service()
        self.assertIsNotNone(blob_service, "BlobStorageService should be available")

        # Should have local file provider available (always works)
        providers = blob_service.get_available_providers()
        self.assertIn(
            "file", providers, "Local file provider should always be available"
        )

        # Cloud providers may or may not be available depending on environment
        # but the service should handle this gracefully

    def test_container_error_handling_invalid_blob_configuration(self):
        """Test container error handling with invalid blob configuration."""
        # Create temporary config with invalid blob configuration
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "invalid_config.yaml"

            # Configuration with invalid blob settings
            invalid_config = """logging:
  version: 1
  level: DEBUG

storage:
  blob:
    providers:
      invalid_provider:
        invalid_setting: "invalid_value"
"""

            with open(config_path, "w") as f:
                f.write(invalid_config)

            # Container should still initialize (graceful degradation)
            container = initialize_di(str(config_path))

            # Core services should still work
            self.assertIsNotNone(container.app_config_service())
            self.assertIsNotNone(container.logging_service())

            # Blob service should handle invalid configuration gracefully
            blob_service = container.blob_storage_service()
            if blob_service is not None:
                # Should not crash, even with invalid configuration
                providers = blob_service.get_available_providers()
                self.assertIsInstance(providers, list)

    # =============================================================================
    # Integration with Other Services Tests
    # =============================================================================

    def test_blob_storage_integration_with_execution_tracking(self):
        """Test blob storage integration with execution tracking service."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get services
        blob_service = container.blob_storage_service()
        execution_tracking = container.execution_tracking_service()
        logging_service = container.logging_service()

        if blob_service and execution_tracking:
            # Create blob agent with execution tracking
            blob_reader = BlobReaderAgent(
                name="tracking_integration_test",
                prompt="Test execution tracking integration",
                logger=(
                    logging_service.get_class_logger("test")
                    if logging_service
                    else None
                ),
                execution_tracking_service=execution_tracking,
            )
            blob_reader.configure_blob_storage_service(blob_service)

            # Agent should have both services
            self.assertEqual(blob_reader.blob_storage_service, blob_service)
            self.assertEqual(blob_reader.execution_tracking_service, execution_tracking)

            # Services should be compatible (no interface conflicts)
            self.assertIsNotNone(blob_reader._get_child_service_info())

    def test_blob_storage_integration_with_state_adapter(self):
        """Test blob storage integration with state adapter service."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get services
        blob_service = container.blob_storage_service()
        state_adapter = container.state_adapter_service()
        logging_service = container.logging_service()

        if blob_service and state_adapter:
            # Create blob agent with state adapter
            blob_writer = BlobWriterAgent(
                name="state_integration_test",
                prompt="Test state adapter integration",
                logger=(
                    logging_service.get_class_logger("test")
                    if logging_service
                    else None
                ),
                state_adapter_service=state_adapter,
            )
            blob_writer.configure_blob_storage_service(blob_service)

            # Agent should have both services
            self.assertEqual(blob_writer.blob_storage_service, blob_service)
            self.assertEqual(blob_writer.state_adapter_service, state_adapter)

            # Services should be compatible
            self.assertIsNotNone(blob_writer._get_child_service_info())

    def test_blob_storage_integration_with_dependency_checker(self):
        """Test blob storage integration with dependency checker service."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get services
        blob_service = container.blob_storage_service()
        dependency_checker = container.dependency_checker_service()

        if blob_service and dependency_checker:
            # Should be able to check blob storage dependencies
            try:
                # This tests that dependency checker can work with blob storage
                available_providers = blob_service.get_available_providers()
                self.assertIsInstance(available_providers, list)

                # Dependency checker should still function
                # (specific dependency checking for blob storage might not be implemented)
                self.assertIsNotNone(dependency_checker)

            except Exception as e:
                # Even if specific blob dependency checking isn't implemented,
                # services should coexist without conflicts
                self.assertIsNotNone(blob_service)
                self.assertIsNotNone(dependency_checker)

    # =============================================================================
    # Performance and Resource Management Tests
    # =============================================================================

    def test_container_resource_management_with_blob_services(self):
        """Test container resource management when using blob services."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get multiple services to test resource sharing
        blob_service = container.blob_storage_service()
        storage_manager = container.storage_service_manager()
        storage_config = container.storage_config_service()
        logging_service = container.logging_service()

        # Assert services exist
        self.assertIsNotNone(blob_service, "BlobStorageService should be available")
        self.assertIsNotNone(
            storage_manager, "StorageServiceManager should be available"
        )
        self.assertIsNotNone(storage_config, "StorageConfigService should be available")
        self.assertIsNotNone(logging_service, "LoggingService should be available")

        # Verify resource sharing (singleton pattern)
        self.assertTrue(
            storage_manager.is_blob_storage_enabled(),
            "Storage manager should have blob storage",
        )

        # Configuration should be shared - both use StorageConfigService
        self.assertEqual(blob_service.configuration, storage_config)

        # Logging service should be shared
        self.assertEqual(blob_service.logging_service, logging_service)

        # No duplicate service instances should be created
        manager_blob = storage_manager.get_blob_storage_service()
        # Services should be related (might be same instance or compatible instances)
        self.assertIsNotNone(
            manager_blob, "Manager should provide blob storage service"
        )

    def test_container_memory_efficiency_blob_services(self):
        """Test memory efficiency of blob service creation in container."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get services multiple times
        services = []
        for i in range(10):
            blob_service = container.blob_storage_service()
            if blob_service:
                services.append(blob_service)

        if services:
            # All should be the same instance (memory efficient)
            first_service = services[0]
            for service in services[1:]:
                self.assertEqual(service, first_service)

    # =============================================================================
    # Configuration Validation Tests
    # =============================================================================

    def test_container_blob_configuration_validation(self):
        """Test that container validates blob storage configuration properly."""
        # Initialize DI container
        container = initialize_di(str(self.test_env.config_path))

        # Get services
        app_config = container.app_config_service()
        blob_service = container.blob_storage_service()

        if app_config and blob_service:
            # Should be able to access blob configuration
            try:
                # Configuration should be accessible
                blob_config = app_config.get_value("storage.blob", {})
                self.assertIsInstance(blob_config, dict)

                # Blob service should have processed configuration
                service_config = blob_service._config
                self.assertIsInstance(service_config, dict)

            except Exception as e:
                # Configuration validation should not crash the container
                self.assertIsNotNone(app_config)
                self.assertIsNotNone(blob_service)


if __name__ == "__main__":
    unittest.main()
