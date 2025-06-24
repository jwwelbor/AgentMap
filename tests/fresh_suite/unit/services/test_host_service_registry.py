"""
Unit tests for HostServiceRegistry.

These tests validate the HostServiceRegistry using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock
from typing import Type, Protocol, Dict, Any, List, runtime_checkable
from agentmap.services.host_service_registry import HostServiceRegistry
from tests.utils.mock_service_factory import MockServiceFactory


# Test protocol classes for testing protocol registration
@runtime_checkable
class TestProtocol(Protocol):
    """Test protocol for unit testing."""
    
    def test_method(self) -> str:
        """Test method in protocol."""
        ...


@runtime_checkable
class DatabaseServiceProtocol(Protocol):
    """Database service protocol for testing."""
    
    def connect(self, host: str) -> bool:
        """Connect to database."""
        ...
    
    def query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute query."""
        ...


@runtime_checkable
class CacheServiceProtocol(Protocol):
    """Cache service protocol for testing."""
    
    def get(self, key: str) -> Any:
        """Get value from cache."""
        ...
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        ...


class TestServiceProvider:
    """Test service provider class."""
    
    def __init__(self, name: str):
        self.name = name
        self.initialized = True
    
    def process(self, data: Any) -> Any:
        return f"Processed {data} by {self.name}"


class TestHostServiceRegistry(unittest.TestCase):
    """Unit tests for HostServiceRegistry with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use MockServiceFactory for consistent logging behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Create service instance with mocked logging
        self.service = HostServiceRegistry(
            logging_service=self.mock_logging_service
        )
        
        # Get the mock logger for verification (established pattern)
        self.mock_logger = self.service.logger
        
        # Create test service providers and protocols
        self.test_provider = TestServiceProvider("TestProvider")
        self.test_factory = lambda: TestServiceProvider("FactoryProvider")
        self.test_instance = {"type": "instance", "data": "test_data"}
        
        # Test protocol lists
        self.single_protocol = [TestProtocol]
        self.multiple_protocols = [TestProtocol, DatabaseServiceProtocol, CacheServiceProtocol]
        
        # Test metadata
        self.test_metadata = {
            "version": "1.0.0",
            "description": "Test service provider",
            "author": "AgentMap Team"
        }
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify logging service is stored
        self.assertIsNotNone(self.service.logger)
        
        # Verify internal storage is initialized
        self.assertEqual(len(self.service._service_providers), 0)
        self.assertEqual(len(self.service._protocol_implementations), 0)
        self.assertEqual(len(self.service._service_metadata), 0)
        self.assertEqual(len(self.service._protocol_cache), 0)
        
        # Verify initialization log message (established pattern)
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Initialized" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    # =============================================================================
    # 2. register_service_provider() Method Tests
    # =============================================================================
    
    def test_register_service_provider_basic(self):
        """Test basic service provider registration without protocols."""
        # Act
        self.service.register_service_provider("test_service", self.test_provider)
        
        # Assert
        self.assertTrue(self.service.is_service_registered("test_service"))
        retrieved_provider = self.service.get_service_provider("test_service")
        self.assertEqual(retrieved_provider, self.test_provider)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Registered service provider: test_service" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    def test_register_service_provider_with_protocols(self):
        """Test service provider registration with protocol implementations."""
        # Act
        self.service.register_service_provider(
            "test_service", 
            self.test_provider,
            protocols=self.single_protocol
        )
        
        # Assert
        self.assertTrue(self.service.is_service_registered("test_service"))
        self.assertTrue(self.service.is_protocol_implemented(TestProtocol))
        
        # Verify protocol mapping
        implementing_service = self.service.get_protocol_implementation(TestProtocol)
        self.assertEqual(implementing_service, "test_service")
        
        # Verify protocol cache
        cached_protocols = self.service.get_service_protocols("test_service")
        self.assertEqual(cached_protocols, self.single_protocol)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Registered protocol TestProtocol -> test_service" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_register_service_provider_with_metadata(self):
        """Test service provider registration with metadata."""
        # Act
        self.service.register_service_provider(
            "test_service",
            self.test_provider,
            metadata=self.test_metadata
        )
        
        # Assert
        retrieved_metadata = self.service.get_service_metadata("test_service")
        self.assertEqual(retrieved_metadata, self.test_metadata)
        
        # Verify metadata is a copy (safety)
        retrieved_metadata["new_key"] = "new_value"
        original_metadata = self.service.get_service_metadata("test_service")
        self.assertNotIn("new_key", original_metadata)
    
    def test_register_service_provider_with_multiple_protocols(self):
        """Test service provider registration with multiple protocols."""
        # Act
        self.service.register_service_provider(
            "multi_service",
            self.test_provider,
            protocols=self.multiple_protocols
        )
        
        # Assert
        for protocol in self.multiple_protocols:
            self.assertTrue(self.service.is_protocol_implemented(protocol))
            implementing_service = self.service.get_protocol_implementation(protocol)
            self.assertEqual(implementing_service, "multi_service")
        
        # Verify all protocols are cached
        cached_protocols = self.service.get_service_protocols("multi_service")
        self.assertEqual(set(cached_protocols), set(self.multiple_protocols))
    
    def test_register_service_provider_overwrite_existing(self):
        """Test that registering overwrites existing service."""
        # Arrange
        old_provider = TestServiceProvider("OldProvider")
        self.service.register_service_provider("test_service", old_provider)
        
        # Act
        self.service.register_service_provider("test_service", self.test_provider)
        
        # Assert
        retrieved_provider = self.service.get_service_provider("test_service")
        self.assertEqual(retrieved_provider, self.test_provider)
        self.assertNotEqual(retrieved_provider, old_provider)
        
        # Verify warning logging for overwrite
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("already registered, overwriting" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    def test_register_service_provider_empty_name_warning(self):
        """Test that empty service name logs warning."""
        # Act
        self.service.register_service_provider("", self.test_provider)
        
        # Assert
        self.assertFalse(self.service.is_service_registered(""))
        
        # Verify warning logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Empty service name provided" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    def test_register_service_provider_empty_provider_warning(self):
        """Test that empty provider logs warning."""
        # Act
        self.service.register_service_provider("test_service", None)
        
        # Assert
        self.assertFalse(self.service.is_service_registered("test_service"))
        
        # Verify warning logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Empty provider provided for service 'test_service'" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    def test_register_service_provider_invalid_protocol(self):
        """Test registration with invalid protocol logs warning."""
        # Act - Using a non-Protocol class
        invalid_protocols = [str, int, TestServiceProvider]  # Not Protocol classes
        self.service.register_service_provider(
            "test_service",
            self.test_provider,
            protocols=invalid_protocols
        )
        
        # Assert - Service still registered but protocols may be filtered
        self.assertTrue(self.service.is_service_registered("test_service"))
        
        # Verify warning logging for invalid protocols
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Invalid protocol provided" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    # =============================================================================
    # 3. register_protocol_implementation() Method Tests
    # =============================================================================
    
    def test_register_protocol_implementation_success(self):
        """Test successful protocol implementation registration."""
        # Arrange
        self.service.register_service_provider("test_service", self.test_provider)
        
        # Act
        self.service.register_protocol_implementation(TestProtocol, "test_service")
        
        # Assert
        self.assertTrue(self.service.is_protocol_implemented(TestProtocol))
        implementing_service = self.service.get_protocol_implementation(TestProtocol)
        self.assertEqual(implementing_service, "test_service")
        
        # Verify protocol is added to cache
        cached_protocols = self.service.get_service_protocols("test_service")
        self.assertIn(TestProtocol, cached_protocols)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Registered protocol TestProtocol -> test_service" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_register_protocol_implementation_invalid_protocol(self):
        """Test protocol registration with invalid protocol."""
        # Arrange
        self.service.register_service_provider("test_service", self.test_provider)
        
        # Act
        self.service.register_protocol_implementation(str, "test_service")  # Not a Protocol
        
        # Assert - Should not register
        self.assertFalse(self.service.is_protocol_implemented(str))
        
        # Verify warning logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Invalid protocol" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    def test_register_protocol_implementation_unregistered_service(self):
        """Test protocol registration for unregistered service."""
        # Act
        self.service.register_protocol_implementation(TestProtocol, "nonexistent_service")
        
        # Assert - Should not register
        self.assertFalse(self.service.is_protocol_implemented(TestProtocol))
        
        # Verify warning logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Service 'nonexistent_service' not registered" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    # =============================================================================
    # 4. get_service_provider() Method Tests
    # =============================================================================
    
    def test_get_service_provider_existing_service(self):
        """Test getting existing service provider."""
        # Arrange
        self.service.register_service_provider("test_service", self.test_provider)
        
        # Act
        result = self.service.get_service_provider("test_service")
        
        # Assert
        self.assertEqual(result, self.test_provider)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Retrieved service provider: test_service" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_get_service_provider_nonexistent_service(self):
        """Test getting nonexistent service provider."""
        # Act
        result = self.service.get_service_provider("nonexistent_service")
        
        # Assert
        self.assertIsNone(result)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Service 'nonexistent_service' not found" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    # =============================================================================
    # 5. get_protocol_implementation() Method Tests
    # =============================================================================
    
    def test_get_protocol_implementation_existing(self):
        """Test getting existing protocol implementation."""
        # Arrange
        self.service.register_service_provider(
            "test_service", 
            self.test_provider,
            protocols=self.single_protocol
        )
        
        # Act
        result = self.service.get_protocol_implementation(TestProtocol)
        
        # Assert
        self.assertEqual(result, "test_service")
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Protocol TestProtocol implemented by: test_service" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_get_protocol_implementation_nonexistent(self):
        """Test getting nonexistent protocol implementation."""
        # Act
        result = self.service.get_protocol_implementation(TestProtocol)
        
        # Assert
        self.assertIsNone(result)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("No implementation found for protocol: TestProtocol" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    # =============================================================================
    # 6. discover_services_by_protocol() Method Tests
    # =============================================================================
    
    def test_discover_services_by_protocol_single_implementation(self):
        """Test discovering services with single implementation."""
        # Arrange
        self.service.register_service_provider(
            "test_service", 
            self.test_provider,
            protocols=self.single_protocol
        )
        
        # Act
        result = self.service.discover_services_by_protocol(TestProtocol)
        
        # Assert
        self.assertEqual(result, ["test_service"])
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Found 1 services implementing TestProtocol" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_discover_services_by_protocol_multiple_implementations(self):
        """Test discovering services with multiple implementations."""
        # Arrange
        self.service.register_service_provider(
            "service1", 
            self.test_provider,
            protocols=self.single_protocol
        )
        self.service.register_service_provider(
            "service2", 
            TestServiceProvider("Service2"),
            protocols=self.single_protocol
        )
        
        # Act
        result = self.service.discover_services_by_protocol(TestProtocol)
        
        # Assert
        self.assertEqual(set(result), {"service1", "service2"})
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Found 2 services implementing TestProtocol" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_discover_services_by_protocol_no_implementations(self):
        """Test discovering services with no implementations."""
        # Act
        result = self.service.discover_services_by_protocol(TestProtocol)
        
        # Assert
        self.assertEqual(result, [])
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("No services found implementing TestProtocol" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    # =============================================================================
    # 7. list_registered_services() Method Tests
    # =============================================================================
    
    def test_list_registered_services_with_services(self):
        """Test listing registered services when services exist."""
        # Arrange
        services = ["service1", "service2", "service3"]
        for service_name in services:
            self.service.register_service_provider(service_name, TestServiceProvider(service_name))
        
        # Act
        result = self.service.list_registered_services()
        
        # Assert
        self.assertEqual(set(result), set(services))
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("3 services registered" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_list_registered_services_empty_registry(self):
        """Test listing registered services when registry is empty."""
        # Act
        result = self.service.list_registered_services()
        
        # Assert
        self.assertEqual(result, [])
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("0 services registered" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    # =============================================================================
    # 8. get_service_metadata() and update_service_metadata() Tests
    # =============================================================================
    
    def test_get_service_metadata_existing_service(self):
        """Test getting metadata for existing service."""
        # Arrange
        self.service.register_service_provider(
            "test_service", 
            self.test_provider,
            metadata=self.test_metadata
        )
        
        # Act
        result = self.service.get_service_metadata("test_service")
        
        # Assert
        self.assertEqual(result, self.test_metadata)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Retrieved metadata for service: test_service" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_get_service_metadata_nonexistent_service(self):
        """Test getting metadata for nonexistent service."""
        # Act
        result = self.service.get_service_metadata("nonexistent_service")
        
        # Assert
        self.assertIsNone(result)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("No metadata found for service: nonexistent_service" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_update_service_metadata_existing_service(self):
        """Test updating metadata for existing service."""
        # Arrange
        self.service.register_service_provider("test_service", self.test_provider)
        update_metadata = {"updated": True, "timestamp": "2024-01-01"}
        
        # Act
        result = self.service.update_service_metadata("test_service", update_metadata)
        
        # Assert
        self.assertTrue(result)
        retrieved_metadata = self.service.get_service_metadata("test_service")
        self.assertEqual(retrieved_metadata["updated"], True)
        self.assertEqual(retrieved_metadata["timestamp"], "2024-01-01")
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Updated metadata for service: test_service" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_update_service_metadata_nonexistent_service(self):
        """Test updating metadata for nonexistent service."""
        # Act
        result = self.service.update_service_metadata("nonexistent_service", {"test": "data"})
        
        # Assert
        self.assertFalse(result)
        
        # Verify warning logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Cannot update metadata for unregistered service: nonexistent_service" in call[1] 
                          for call in logger_calls if call[0] == "warning"))
    
    # =============================================================================
    # 9. get_service_protocols() Method Tests
    # =============================================================================
    
    def test_get_service_protocols_with_protocols(self):
        """Test getting protocols for service with protocols."""
        # Arrange
        self.service.register_service_provider(
            "test_service", 
            self.test_provider,
            protocols=self.multiple_protocols
        )
        
        # Act
        result = self.service.get_service_protocols("test_service")
        
        # Assert
        self.assertEqual(set(result), set(self.multiple_protocols))
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Service 'test_service' implements 3 protocols" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_get_service_protocols_no_protocols(self):
        """Test getting protocols for service without protocols."""
        # Arrange
        self.service.register_service_provider("test_service", self.test_provider)
        
        # Act
        result = self.service.get_service_protocols("test_service")
        
        # Assert
        self.assertEqual(result, [])
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("No protocols cached for service: test_service" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    # =============================================================================
    # 10. is_service_registered() and is_protocol_implemented() Tests
    # =============================================================================
    
    def test_is_service_registered_true(self):
        """Test is_service_registered returns True for registered service."""
        # Arrange
        self.service.register_service_provider("test_service", self.test_provider)
        
        # Act & Assert
        self.assertTrue(self.service.is_service_registered("test_service"))
    
    def test_is_service_registered_false(self):
        """Test is_service_registered returns False for unregistered service."""
        # Act & Assert
        self.assertFalse(self.service.is_service_registered("nonexistent_service"))
    
    def test_is_protocol_implemented_true(self):
        """Test is_protocol_implemented returns True for implemented protocol."""
        # Arrange
        self.service.register_service_provider(
            "test_service", 
            self.test_provider,
            protocols=self.single_protocol
        )
        
        # Act & Assert
        self.assertTrue(self.service.is_protocol_implemented(TestProtocol))
    
    def test_is_protocol_implemented_false(self):
        """Test is_protocol_implemented returns False for unimplemented protocol."""
        # Act & Assert
        self.assertFalse(self.service.is_protocol_implemented(TestProtocol))
    
    # =============================================================================
    # 11. unregister_service() Method Tests
    # =============================================================================
    
    def test_unregister_service_existing_service(self):
        """Test unregistering existing service with cleanup."""
        # Arrange
        self.service.register_service_provider(
            "test_service", 
            self.test_provider,
            protocols=self.multiple_protocols,
            metadata=self.test_metadata
        )
        
        # Verify service is registered
        self.assertTrue(self.service.is_service_registered("test_service"))
        self.assertTrue(self.service.is_protocol_implemented(TestProtocol))
        
        # Act
        result = self.service.unregister_service("test_service")
        
        # Assert
        self.assertTrue(result)
        self.assertFalse(self.service.is_service_registered("test_service"))
        self.assertFalse(self.service.is_protocol_implemented(TestProtocol))
        self.assertIsNone(self.service.get_service_metadata("test_service"))
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Unregistered service: test_service" in call[1] 
                          for call in logger_calls if call[0] == "info"))
        self.assertTrue(any("Removed 3 protocol mappings" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_unregister_service_nonexistent_service(self):
        """Test unregistering nonexistent service."""
        # Act
        result = self.service.unregister_service("nonexistent_service")
        
        # Assert
        self.assertFalse(result)
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Service 'nonexistent_service' not registered" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    # =============================================================================
    # 12. clear_registry() Method Tests
    # =============================================================================
    
    def test_clear_registry(self):
        """Test clearing the entire registry."""
        # Arrange
        self.service.register_service_provider(
            "service1", 
            self.test_provider,
            protocols=self.single_protocol
        )
        self.service.register_service_provider(
            "service2", 
            TestServiceProvider("Service2"),
            protocols=[DatabaseServiceProtocol]
        )
        
        # Verify services are registered
        self.assertEqual(len(self.service.list_registered_services()), 2)
        
        # Act
        self.service.clear_registry()
        
        # Assert
        self.assertEqual(len(self.service.list_registered_services()), 0)
        self.assertFalse(self.service.is_protocol_implemented(TestProtocol))
        self.assertFalse(self.service.is_protocol_implemented(DatabaseServiceProtocol))
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Cleared registry: 2 services, 2 protocols" in call[1] 
                          for call in logger_calls if call[0] == "info"))
    
    # =============================================================================
    # 13. get_registry_summary() Method Tests
    # =============================================================================
    
    def test_get_registry_summary_with_services(self):
        """Test getting registry summary with services."""
        # Arrange
        self.service.register_service_provider(
            "test_service", 
            self.test_provider,
            protocols=self.multiple_protocols,
            metadata=self.test_metadata
        )
        
        # Act
        summary = self.service.get_registry_summary()
        
        # Assert
        self.assertEqual(summary["service"], "HostServiceRegistry")
        self.assertEqual(summary["total_services"], 1)
        self.assertEqual(summary["total_protocols"], 3)
        self.assertIn("test_service", summary["registered_services"])
        self.assertIn("TestProtocol", summary["implemented_protocols"])
        self.assertIn("DatabaseServiceProtocol", summary["implemented_protocols"])
        self.assertIn("CacheServiceProtocol", summary["implemented_protocols"])
        self.assertEqual(summary["services_with_metadata"], 1)
        self.assertEqual(summary["services_with_protocols"], 1)
        
        # Verify health indicators
        health = summary["registry_health"]
        self.assertTrue(health["providers_storage_ok"])
        self.assertTrue(health["protocols_storage_ok"])
        self.assertTrue(health["metadata_storage_ok"])
        self.assertTrue(health["cache_storage_ok"])
    
    def test_get_registry_summary_empty_registry(self):
        """Test getting registry summary for empty registry."""
        # Act
        summary = self.service.get_registry_summary()
        
        # Assert
        self.assertEqual(summary["total_services"], 0)
        self.assertEqual(summary["total_protocols"], 0)
        self.assertEqual(summary["registered_services"], [])
        self.assertEqual(summary["implemented_protocols"], [])
    
    # =============================================================================
    # 14. validate_service_provider() Method Tests
    # =============================================================================
    
    def test_validate_service_provider_valid_service(self):
        """Test validating a properly configured service."""
        # Arrange
        self.service.register_service_provider(
            "test_service", 
            self.test_provider,
            protocols=self.multiple_protocols,
            metadata=self.test_metadata
        )
        
        # Act
        validation = self.service.validate_service_provider("test_service")
        
        # Assert
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["service_name"], "test_service")
        self.assertEqual(validation["protocol_count"], 3)
        
        checks = validation["checks"]
        self.assertTrue(checks["provider_exists"])
        self.assertTrue(checks["provider_is_valid"])
        self.assertTrue(checks["has_protocols"])
        self.assertTrue(checks["protocols_valid"])
        self.assertTrue(checks["has_metadata"])
        self.assertTrue(checks["protocol_mappings_consistent"])
    
    def test_validate_service_provider_nonexistent_service(self):
        """Test validating nonexistent service."""
        # Act
        validation = self.service.validate_service_provider("nonexistent_service")
        
        # Assert
        self.assertFalse(validation["valid"])
        self.assertIn("not registered", validation["error"])
    
    def test_validate_service_provider_no_protocols(self):
        """Test validating service without protocols."""
        # Arrange
        self.service.register_service_provider("test_service", self.test_provider)
        
        # Act
        validation = self.service.validate_service_provider("test_service")
        
        # Assert
        self.assertFalse(validation["valid"])  # Fails has_protocols check
        self.assertIn("has_protocols", validation["failed_checks"])
    
    # =============================================================================
    # 15. _is_valid_protocol() Method Tests
    # =============================================================================
    
    def test_is_valid_protocol_runtime_checkable_protocol(self):
        """Test protocol validation for runtime checkable protocols."""
        # Act & Assert
        self.assertTrue(self.service._is_valid_protocol(TestProtocol))
        self.assertTrue(self.service._is_valid_protocol(DatabaseServiceProtocol))
        self.assertTrue(self.service._is_valid_protocol(CacheServiceProtocol))
    
    def test_is_valid_protocol_non_protocol_class(self):
        """Test protocol validation for non-protocol classes."""
        # Act & Assert
        self.assertFalse(self.service._is_valid_protocol(str))
        self.assertFalse(self.service._is_valid_protocol(int))
        self.assertFalse(self.service._is_valid_protocol(TestServiceProvider))
    
    def test_is_valid_protocol_non_class(self):
        """Test protocol validation for non-class objects."""
        # Act & Assert
        self.assertFalse(self.service._is_valid_protocol("not_a_class"))
        self.assertFalse(self.service._is_valid_protocol(123))
        self.assertFalse(self.service._is_valid_protocol(None))
    
    # =============================================================================
    # 16. Error Handling and Edge Cases
    # =============================================================================
    
    def test_service_provider_types(self):
        """Test registration with different provider types."""
        provider_types = {
            "class_provider": TestServiceProvider,
            "instance_provider": self.test_provider,
            "factory_provider": self.test_factory,
            "dict_provider": self.test_instance
        }
        
        for name, provider in provider_types.items():
            with self.subTest(provider_type=name):
                # Act
                self.service.register_service_provider(name, provider)
                
                # Assert
                self.assertTrue(self.service.is_service_registered(name))
                retrieved = self.service.get_service_provider(name)
                self.assertEqual(retrieved, provider)
    
    def test_error_handling_during_registration(self):
        """Test error handling during service registration."""
        # Mock an error in protocol validation
        with unittest.mock.patch.object(self.service, '_is_valid_protocol', side_effect=Exception("Validation error")):
            # Should not crash, should handle gracefully
            self.service.register_service_provider(
                "test_service", 
                self.test_provider,
                protocols=self.single_protocol
            )
            
            # Verify error logging
            logger_calls = self.mock_logger.calls
            self.assertTrue(any("Failed to register service 'test_service'" in call[1] 
                              for call in logger_calls if call[0] == "error"))
    
    def test_protocol_registration_consistency(self):
        """Test that protocol registration maintains consistency."""
        # Register service with protocol
        self.service.register_service_provider(
            "service1", 
            self.test_provider,
            protocols=[TestProtocol]
        )
        
        # Register different service with same protocol  
        self.service.register_service_provider(
            "service2", 
            TestServiceProvider("Service2"),
            protocols=[TestProtocol]
        )
        
        # The second registration should overwrite the protocol mapping
        implementing_service = self.service.get_protocol_implementation(TestProtocol)
        self.assertEqual(implementing_service, "service2")
        
        # But both services should have the protocol in their cache
        protocols1 = self.service.get_service_protocols("service1") 
        protocols2 = self.service.get_service_protocols("service2")
        self.assertIn(TestProtocol, protocols1)
        self.assertIn(TestProtocol, protocols2)
    
    def test_registry_state_isolation(self):
        """Test that registry operations maintain proper state isolation."""
        # Register multiple services
        services = {
            "service1": (self.test_provider, [TestProtocol]),
            "service2": (TestServiceProvider("Service2"), [DatabaseServiceProtocol]),
            "service3": (TestServiceProvider("Service3"), [CacheServiceProtocol])
        }
        
        for name, (provider, protocols) in services.items():
            self.service.register_service_provider(name, provider, protocols=protocols)
        
        # Unregister one service
        self.service.unregister_service("service2")
        
        # Verify other services are unaffected
        self.assertTrue(self.service.is_service_registered("service1"))
        self.assertTrue(self.service.is_service_registered("service3"))
        self.assertFalse(self.service.is_service_registered("service2"))
        
        # Verify protocols are properly isolated
        self.assertTrue(self.service.is_protocol_implemented(TestProtocol))
        self.assertFalse(self.service.is_protocol_implemented(DatabaseServiceProtocol))
        self.assertTrue(self.service.is_protocol_implemented(CacheServiceProtocol))
    
    def test_cleanup_partial_registration(self):
        """Test cleanup of partial registration data."""
        # This tests the private _cleanup_partial_registration method indirectly
        # by triggering an error during registration
        
        # Mock protocol validation to fail partway through
        call_count = 0
        def failing_validation(protocol):
            nonlocal call_count
            call_count += 1
            if call_count > 1:  # Fail on second protocol
                raise Exception("Validation failed")
            return True
        
        with unittest.mock.patch.object(self.service, '_is_valid_protocol', side_effect=failing_validation):
            # Attempt registration with multiple protocols
            self.service.register_service_provider(
                "test_service",
                self.test_provider,
                protocols=self.multiple_protocols
            )
            
            # Service should not be registered due to cleanup
            self.assertFalse(self.service.is_service_registered("test_service"))


if __name__ == '__main__':
    unittest.main()
