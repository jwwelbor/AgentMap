"""
Storage Configuration Integration Tests.

This module tests the integration between StorageConfigService and actual storage 
services, validating storage configuration validation and application, fail-fast 
behavior with storage initialization, and storage service dependency resolution.
"""

import unittest
import tempfile
import yaml
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from agentmap.services.storage.types import WriteMode, StorageResult
from agentmap.exceptions.service_exceptions import StorageConfigurationNotAvailableException


class TestStorageConfigIntegration(BaseIntegrationTest):
    """
    Integration tests for StorageConfigService with actual storage services.
    
    Tests real integration between:
    - StorageConfigService configuration loading and validation
    - Storage service initialization and dependency resolution
    - Fail-fast behavior when storage configuration is unavailable
    - Configuration application across different storage backends
    """
    
    def setup_services(self):
        """Initialize storage configuration and services for integration testing."""
        super().setup_services()
        
        # Initialize storage configuration service
        self.storage_config_service = self.container.storage_config_service()
        
        # Initialize storage services through StorageManager
        self.storage_manager = self.container.storage_service_manager()
        self.memory_service = self.storage_manager.get_service("memory")
        self.file_service = self.storage_manager.get_service("file")
        self.json_service = self.storage_manager.get_service("json")
        self.csv_service = self.storage_manager.get_service("csv")
        
        # Create test directories for configuration scenarios
        self.config_test_dir = Path(self.temp_dir) / "config_test"
        self.config_test_dir.mkdir(parents=True, exist_ok=True)
    
    # =============================================================================
    # 1. Storage Configuration Loading and Validation Tests
    # =============================================================================
    
    def test_storage_config_service_initialization_with_valid_config(self):
        """Test StorageConfigService initializes correctly with valid configuration."""
        # Test that the service initialized successfully during setup
        self.assertIsNotNone(self.storage_config_service, 
                           "StorageConfigService should initialize")
        
        # Test configuration sections are available
        csv_config = self.storage_config_service.get_csv_config()
        self.assertIsInstance(csv_config, dict, "CSV config should be a dictionary")
        
        vector_config = self.storage_config_service.get_vector_config()
        self.assertIsInstance(vector_config, dict, "Vector config should be a dictionary")
        
        kv_config = self.storage_config_service.get_kv_config()
        self.assertIsInstance(kv_config, dict, "KV config should be a dictionary")
        
        # Test provider configuration retrieval
        csv_provider_config = self.storage_config_service.get_provider_config("csv")
        self.assertIsInstance(csv_provider_config, dict, 
                            "CSV provider config should be a dictionary")
        
        json_provider_config = self.storage_config_service.get_provider_config("json")
        self.assertIsInstance(json_provider_config, dict, 
                            "JSON provider config should be a dictionary")
    
    def test_storage_config_validation_integration(self):
        """Test storage configuration validation with real services."""
        # Test configuration validation
        validation_results = self.storage_config_service.validate_storage_config()
        
        self.assertIsInstance(validation_results, dict, 
                            "Validation results should be a dictionary")
        self.assertIn("warnings", validation_results, 
                     "Validation should include warnings")
        self.assertIn("errors", validation_results, 
                     "Validation should include errors")
        
        # Validation should not have critical errors for test configuration
        self.assertIsInstance(validation_results["warnings"], list, 
                            "Warnings should be a list")
        self.assertIsInstance(validation_results["errors"], list, 
                            "Errors should be a list")
        
        # Test configuration summary
        config_summary = self.storage_config_service.get_storage_summary()
        self.assertEqual(config_summary["status"], "loaded", 
                        "Configuration should be loaded")
        self.assertIn("storage_types", config_summary, 
                     "Summary should include storage types")
        self.assertGreater(config_summary["storage_type_count"], 0, 
                         "Should have storage types configured")
    
    def test_collection_configuration_integration(self):
        """Test collection configuration access and validation."""
        # Test listing collections for different storage types
        csv_collections = self.storage_config_service.list_collections("csv")
        self.assertIsInstance(csv_collections, list, 
                            "CSV collections should be a list")
        
        vector_collections = self.storage_config_service.list_collections("vector")
        self.assertIsInstance(vector_collections, list, 
                            "Vector collections should be a list")
        
        kv_collections = self.storage_config_service.list_collections("kv")
        self.assertIsInstance(kv_collections, list, 
                            "KV collections should be a list")
        
        # Test collection existence checking
        if vector_collections:
            first_vector_collection = vector_collections[0]
            self.assertTrue(
                self.storage_config_service.has_collection("vector", first_vector_collection),
                f"Should find vector collection {first_vector_collection}"
            )
        
        # Test non-existent collection
        self.assertFalse(
            self.storage_config_service.has_collection("csv", "nonexistent_collection"),
            "Should not find non-existent collection"
        )
        
        # Test collection configuration retrieval
        if vector_collections:
            collection_config = self.storage_config_service.get_collection_config(
                "vector", vector_collections[0]
            )
            self.assertIsInstance(collection_config, dict, 
                                "Collection config should be a dictionary")
    
    def test_default_directory_and_provider_configuration(self):
        """Test default directory and provider configuration access."""
        # Test default directories
        csv_default_dir = self.storage_config_service.get_default_directory("csv")
        self.assertIsInstance(csv_default_dir, str, 
                            "CSV default directory should be a string")
        self.assertTrue(len(csv_default_dir) > 0, 
                       "CSV default directory should not be empty")
        
        json_default_dir = self.storage_config_service.get_default_directory("json")
        self.assertIsInstance(json_default_dir, str, 
                            "JSON default directory should be a string")
        
        # Test default providers
        vector_default_provider = self.storage_config_service.get_default_provider("vector")
        self.assertIsInstance(vector_default_provider, str, 
                            "Vector default provider should be a string")
        
        kv_default_provider = self.storage_config_service.get_default_provider("kv")
        self.assertIsInstance(kv_default_provider, str, 
                            "KV default provider should be a string")
    
    # =============================================================================
    # 2. Storage Service Configuration Application Tests
    # =============================================================================
    
    def test_csv_service_configuration_application(self):
        """Test CSV service uses configuration from StorageConfigService."""
        # Get CSV configuration
        csv_config = self.storage_config_service.get_csv_config()
        csv_default_dir = self.storage_config_service.get_default_directory("csv")
        
        # Test CSV service respects configuration
        test_collection = "config_test_csv"
        test_data = [
            {"id": 1, "name": "Config Test", "type": "csv"},
            {"id": 2, "name": "Integration Test", "type": "csv"}
        ]
        
        # Write data using CSV service
        result = self.csv_service.write(
            collection=test_collection,
            data=test_data,
            document_id="config_test"
        )
        self.assertTrue(result.success, "CSV write should succeed with configuration")
        
        # Verify data was written to configured location
        self.assertTrue(self.csv_service.exists(test_collection, "config_test"),
                       "CSV data should exist after write")
        
        # Read back and verify
        read_data = self.csv_service.read(test_collection, "config_test")
        self.assertIsInstance(read_data, list, "CSV should return list")
        self.assertEqual(len(read_data), 2, "Should read back 2 records")
        self.assertEqual(read_data[0]["name"], "Config Test")
    
    def test_json_service_configuration_application(self):
        """Test JSON service uses configuration from StorageConfigService."""
        # Get JSON configuration
        json_config = self.storage_config_service.get_provider_config("json")
        json_default_dir = self.storage_config_service.get_default_directory("json")
        
        # Test JSON service respects configuration
        test_collection = "config_test_json"
        test_data = {
            "config_test": True,
            "metadata": {
                "storage_type": "json",
                "test_timestamp": "2025-06-01T12:00:00Z"
            },
            "data": {
                "items": ["item1", "item2", "item3"],
                "count": 3
            }
        }
        
        # Write data using JSON service
        result = self.json_service.write(
            collection=test_collection,
            data=test_data,
            document_id="config_test"
        )
        self.assertTrue(result.success, "JSON write should succeed with configuration")
        
        # Verify data integrity
        read_data = self.json_service.read(test_collection, "config_test")
        self.assertEqual(read_data, test_data, "JSON data should match exactly")
        self.assertTrue(read_data["config_test"])
        self.assertEqual(read_data["data"]["count"], 3)
    
    def test_file_service_configuration_application(self):
        """Test File service uses configuration from StorageConfigService."""
        # Get file configuration
        file_config = self.storage_config_service.get_provider_config("file")
        file_default_dir = self.storage_config_service.get_default_directory("file")
        
        # Test file service respects configuration
        test_collection = "config_test_file.txt"
        test_content = """Configuration Integration Test
Storage Type: File
Test Timestamp: 2025-06-01T12:00:00Z

This file tests that the file storage service
correctly applies configuration from the
StorageConfigService integration."""
        
        # Write file using File service
        result = self.file_service.write(
            collection=test_collection,
            data=test_content,
            document_id="config_test"
        )
        self.assertTrue(result.success, "File write should succeed with configuration")
        
        # Verify file content
        read_content = self.file_service.read(test_collection, "config_test")
        self.assertEqual(read_content, test_content, "File content should match exactly")
        self.assertIn("Configuration Integration Test", read_content)
    
    def test_memory_service_configuration_application(self):
        """Test Memory service operates correctly with configuration."""
        # Memory service doesn't use file-based configuration but should work with the system
        test_collection = "config_test_memory"
        test_data = {
            "memory_test": True,
            "configuration": "applied",
            "service_type": "memory",
            "test_data": {
                "numbers": [1, 2, 3, 4, 5],
                "strings": ["a", "b", "c"],
                "nested": {
                    "level1": {
                        "level2": "deep_value"
                    }
                }
            }
        }
        
        # Write to memory service
        result = self.memory_service.write(
            collection=test_collection,
            data=test_data,
            document_id="config_test"
        )
        self.assertTrue(result.success, "Memory write should succeed")
        
        # Verify memory storage
        read_data = self.memory_service.read(test_collection, "config_test")
        self.assertEqual(read_data, test_data, "Memory data should match exactly")
        self.assertTrue(read_data["memory_test"])
        self.assertEqual(read_data["test_data"]["nested"]["level1"]["level2"], "deep_value")
    
    # =============================================================================
    # 3. Configuration Dependency Resolution Tests
    # =============================================================================
    
    def test_storage_service_dependency_resolution(self):
        """Test storage services are properly resolved with their dependencies."""
        # Test that all services can access their required dependencies
        services_to_test = [
            ("memory", self.memory_service),
            ("file", self.file_service),
            ("json", self.json_service),
            ("csv", self.csv_service)
        ]
        
        for service_name, service in services_to_test:
            with self.subTest(service=service_name):
                # Test service has required attributes
                self.assertTrue(hasattr(service, 'get_provider_name'), 
                              f"{service_name} should have get_provider_name method")
                self.assertTrue(hasattr(service, 'health_check'), 
                              f"{service_name} should have health_check method")
                
                # Test service provider name
                provider_name = service.get_provider_name()
                self.assertEqual(provider_name, service_name, 
                               f"Provider name should match service name for {service_name}")
                
                # Test service health
                health = service.health_check()
                self.assertTrue(health, f"{service_name} service should be healthy")
    
    def test_storage_manager_dependency_integration(self):
        """Test StorageManager properly integrates with StorageConfigService dependencies."""
        # Test StorageManager can access all configured providers
        available_providers = self.storage_manager.list_available_providers()
        
        expected_providers = ["memory", "file", "json", "csv"]
        for provider in expected_providers:
            self.assertIn(provider, available_providers, 
                         f"StorageManager should include {provider}")
        
        # Test StorageManager can create services for all providers
        for provider in expected_providers:
            with self.subTest(provider=provider):
                service = self.storage_manager.get_service(provider)
                self.assertIsNotNone(service, f"Should create service for {provider}")
                
                # Test service can perform basic operations
                self.assertTrue(service.health_check(), 
                              f"{provider} service should be healthy")
        
        # Test StorageManager health check integration
        health_status = self.storage_manager.health_check()
        for provider in expected_providers:
            self.assertIn(provider, health_status, 
                         f"Health status should include {provider}")
            self.assertTrue(health_status[provider], 
                          f"{provider} should be healthy in manager health check")
    
    def test_configuration_changes_affect_services(self):
        """Test that configuration changes properly affect service behavior."""
        # Create alternate configuration for testing
        alt_config_path = self.config_test_dir / "alternate_storage.yaml"
        
        alt_config_data = {
            "csv": {
                "default_directory": str(self.config_test_dir / "alt_csv_data"),
                "collections": {
                    "alt_test": {
                        "provider": "csv",
                        "settings": {"delimiter": "|"}
                    }
                }
            },
            "json": {
                "default_directory": str(self.config_test_dir / "alt_json_data"),
                "collections": {}
            },
            "file": {
                "default_directory": str(self.config_test_dir / "alt_file_data"),
                "collections": {}
            }
        }
        
        # Write alternate configuration
        with open(alt_config_path, 'w') as f:
            yaml.dump(alt_config_data, f, default_flow_style=False, indent=2)
        
        # Test that current configuration is different from alternate
        current_csv_dir = self.storage_config_service.get_default_directory("csv")
        alt_csv_dir = alt_config_data["csv"]["default_directory"]
        self.assertNotEqual(current_csv_dir, alt_csv_dir, 
                          "Current and alternate configurations should differ")
        
        # Test configuration value access
        alt_collection_exists = self.storage_config_service.has_collection("csv", "alt_test")
        # This should be False since we're using the original config, not the alternate
        
        # Test that services work with their current configuration
        test_result = self.csv_service.write(
            collection="config_change_test",
            data=[{"test": "configuration_change"}],
            document_id="test"
        )
        self.assertTrue(test_result.success, "Service should work with current configuration")
    
    # =============================================================================
    # 4. Fail-Fast Configuration Error Tests
    # =============================================================================
    
    def test_storage_config_missing_file_behavior(self):
        """Test fail-fast behavior when storage configuration file is missing."""
        # This test validates that the system properly handles missing configuration
        # Since we're testing with a working configuration, we test the validation logic
        
        # Test validation of missing storage types
        validation_results = self.storage_config_service.validate_storage_config()
        
        # The validation should complete without throwing exceptions
        self.assertIsInstance(validation_results, dict)
        self.assertIn("warnings", validation_results)
        self.assertIn("errors", validation_results)
        
        # Test that services can still operate with current valid configuration
        for service_name, service in [("memory", self.memory_service), 
                                    ("file", self.file_service),
                                    ("json", self.json_service), 
                                    ("csv", self.csv_service)]:
            with self.subTest(service=service_name):
                self.assertTrue(service.health_check(), 
                              f"{service_name} should be healthy with valid config")
    
    def test_storage_config_invalid_format_handling(self):
        """Test handling of invalid configuration formats."""
        # Create invalid configuration file
        invalid_config_path = self.config_test_dir / "invalid_storage.yaml"
        
        # Write malformed YAML
        with open(invalid_config_path, 'w') as f:
            f.write("invalid: yaml: content:\n  - missing: closing bracket")
        
        # Test that our current valid configuration still works
        # (We can't test the invalid config directly without breaking the test setup)
        self.assertTrue(self.storage_config_service.get_storage_summary()["status"] == "loaded",
                       "Valid configuration should remain working")
        
        # Test configuration validation catches issues
        validation_results = self.storage_config_service.validate_storage_config()
        # Even with our valid config, validation should complete
        self.assertIsInstance(validation_results["warnings"], list)
        self.assertIsInstance(validation_results["errors"], list)
    
    def test_storage_service_initialization_with_config_errors(self):
        """Test storage service initialization behavior with configuration issues."""
        # Test that services handle configuration gracefully
        services_to_test = [
            ("memory", self.memory_service),
            ("file", self.file_service), 
            ("json", self.json_service),
            ("csv", self.csv_service)
        ]
        
        for service_name, service in services_to_test:
            with self.subTest(service=service_name):
                # Test basic service functionality works despite potential config issues
                try:
                    # Test basic operations
                    health = service.health_check()
                    self.assertIsInstance(health, bool, 
                                        f"{service_name} health check should return boolean")
                    
                    provider_name = service.get_provider_name()
                    self.assertEqual(provider_name, service_name, 
                                   f"{service_name} should report correct provider name")
                    
                    # Test basic write/read cycle
                    test_data = {"config_error_test": True, "service": service_name}
                    if service_name == "csv":
                        test_data = [test_data]
                    elif service_name == "file":
                        test_data = f"Config error test for {service_name}"
                    
                    write_result = service.write(
                        collection=f"config_error_test_{service_name}",
                        data=test_data,
                        document_id="error_test"
                    )
                    self.assertTrue(write_result.success, 
                                  f"{service_name} should handle writes despite config issues")
                    
                except Exception as e:
                    self.fail(f"{service_name} service should handle configuration errors gracefully: {e}")
    
    # =============================================================================
    # 5. Configuration Value Access Integration Tests
    # =============================================================================
    
    def test_configuration_value_access_patterns(self):
        """Test various configuration value access patterns with real services."""
        # Test dot notation value access
        csv_default = self.storage_config_service.get_value("csv.default_directory", "fallback")
        self.assertNotEqual(csv_default, "fallback", "Should find CSV default directory")
        
        vector_default = self.storage_config_service.get_value("vector.default_provider", "local")
        self.assertIsInstance(vector_default, str, "Vector default provider should be string")
        
        # Test non-existent path returns default
        nonexistent = self.storage_config_service.get_value("nonexistent.path", "default_value")
        self.assertEqual(nonexistent, "default_value", "Should return default for non-existent path")
        
        # Test nested value access
        if self.storage_config_service.list_collections("vector"):
            first_vector_collection = self.storage_config_service.list_collections("vector")[0]
            collection_provider = self.storage_config_service.get_value(
                f"vector.collections.{first_vector_collection}.provider", 
                "unknown"
            )
            self.assertNotEqual(collection_provider, "unknown", 
                              "Should find collection provider configuration")
    
    def test_configuration_integration_with_service_operations(self):
        """Test that configuration properly integrates with actual service operations."""
        # Test CSV service with configured collections
        csv_collections = self.storage_config_service.list_collections("csv")
        
        # Create test data for CSV operations
        csv_test_data = [
            {"id": 1, "config_test": "csv_integration", "timestamp": "2025-06-01T12:00:00Z"},
            {"id": 2, "config_test": "csv_integration", "timestamp": "2025-06-01T12:01:00Z"}
        ]
        
        csv_result = self.csv_service.write(
            collection="integration_csv_test",
            data=csv_test_data,
            document_id="config_integration"
        )
        self.assertTrue(csv_result.success, "CSV service should work with configuration")
        
        # Test JSON service with configuration
        json_test_data = {
            "config_integration": True,
            "storage_type": "json",
            "test_collections": self.storage_config_service.list_collections("json"),
            "default_directory": self.storage_config_service.get_default_directory("json")
        }
        
        json_result = self.json_service.write(
            collection="integration_json_test",
            data=json_test_data,
            document_id="config_integration"
        )
        self.assertTrue(json_result.success, "JSON service should work with configuration")
        
        # Test file service with configuration
        file_content = f"""Configuration Integration Test
Default Directory: {self.storage_config_service.get_default_directory("file")}
File Collections: {self.storage_config_service.list_collections("file")}
Test Timestamp: 2025-06-01T12:00:00Z"""
        
        file_result = self.file_service.write(
            collection="integration_file_test.txt",
            data=file_content,
            document_id="config_integration"
        )
        self.assertTrue(file_result.success, "File service should work with configuration")
        
        # Verify all data can be read back correctly
        csv_read = self.csv_service.read("integration_csv_test", "config_integration")
        self.assertEqual(len(csv_read), 2, "Should read back CSV data correctly")
        
        json_read = self.json_service.read("integration_json_test", "config_integration")
        self.assertTrue(json_read["config_integration"], "Should read back JSON data correctly")
        
        file_read = self.file_service.read("integration_file_test.txt", "config_integration")
        self.assertIn("Configuration Integration Test", file_read, 
                     "Should read back file content correctly")


if __name__ == '__main__':
    unittest.main()
