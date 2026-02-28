"""
Test suite for StorageConfigService - Fail-fast behavior testing.

This module tests the StorageConfigService which implements fail-fast behavior
with strict validation and exception-based failure handling.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from agentmap.exceptions.service_exceptions import (
    StorageConfigurationNotAvailableException,
)
from src.agentmap.services.config.config_service import ConfigService
from src.agentmap.services.config.storage_config_service import StorageConfigService
from tests.utils.mock_service_factory import MockServiceFactory


class TestStorageConfigService(unittest.TestCase):
    """Test suite for StorageConfigService - Fail-fast behavior."""

    def setUp(self):
        """Set up test fixtures with mock service factory."""
        self.mock_factory = MockServiceFactory()
        # Create a mock ConfigService
        self.mock_config_service = Mock(spec=ConfigService)
        # Create a mock availability cache service following MockServiceFactory pattern
        self.mock_availability_cache_service = Mock()
        self.mock_availability_cache_service.get_availability.return_value = None
        self.mock_availability_cache_service.set_availability.return_value = True
        self.mock_config_service.load_config.return_value = {
            "csv": {
                "default_directory": "csv",
                "collections": {
                    "users": {"file": "users.csv"},
                    "products": {"file": "products.csv"},
                },
            },
            "vector": {
                "default_directory": "vector",
                "default_provider": "local",
                "collections": {"embeddings": {"dimension": 768}},
            },
            "kv": {
                "default_directory": "kv",
                "default_provider": "local",
                "collections": {"cache": {"ttl": 3600}},
            },
            "json": {
                "default_directory": "json",
                "collections": {"documents": {"file": "documents.json"}},
            },
            "file": {"default_directory": "files", "collections": {"attachments": {}}},
            "blob": {
                "default_directory": "blob",
                "default_provider": "file",
                "providers": {
                    "azure": {
                        "connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test==;EndpointSuffix=core.windows.net",
                        "container_name": "blobs",
                    },
                    "s3": {"bucket_name": "test-bucket", "region": "us-east-1"},
                    "gcs": {
                        "bucket_name": "test-gcs-bucket",
                        "project_id": "test-project",
                    },
                    "file": {"base_path": "data/blob/files"},
                },
            },
        }
        self.mock_config_service.get_value_from_config.side_effect = (
            self._mock_get_value
        )

        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "storage_config.yaml")

        # Create a test storage config file
        with open(self.config_path, "w") as f:
            f.write("csv:\n  default_directory: data/csv\n")

        self.storage_config_service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

    def _mock_get_value(self, config_data, path, default=None):
        """Mock implementation of get_value_from_config."""
        parts = path.split(".")
        current = config_data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_initialization_success(self):
        """Test successful initialization with valid config."""
        # Service should initialize without errors
        self.assertIsNotNone(self.storage_config_service)
        self.mock_config_service.load_config.assert_called_once_with(self.config_path)

    def test_initialization_none_path(self):
        """Test fail-fast behavior when config path is None."""
        with self.assertRaises(StorageConfigurationNotAvailableException) as context:
            StorageConfigService(
                config_service=self.mock_config_service,
                storage_config_path=None,
                availability_cache_service=self.mock_availability_cache_service,
            )

        self.assertIn("Storage config path not specified", str(context.exception))

    def test_initialization_missing_file(self):
        """Test fail-fast behavior when config file doesn't exist."""
        missing_path = os.path.join(self.temp_dir, "missing_config.yaml")

        with self.assertRaises(StorageConfigurationNotAvailableException) as context:
            StorageConfigService(
                config_service=self.mock_config_service,
                storage_config_path=missing_path,
                availability_cache_service=self.mock_availability_cache_service,
            )

        self.assertIn("Storage config file not found", str(context.exception))

    def test_initialization_config_load_error(self):
        """Test fail-fast behavior when config loading fails."""
        mock_config_service = Mock(spec=ConfigService)
        mock_config_service.load_config.side_effect = Exception("Parse error")

        with self.assertRaises(StorageConfigurationNotAvailableException) as context:
            StorageConfigService(
                config_service=mock_config_service,
                storage_config_path=self.config_path,
                availability_cache_service=self.mock_availability_cache_service,
            )

        self.assertIn("Failed to load storage config", str(context.exception))

    def test_get_csv_config(self):
        """Test getting CSV storage configuration."""
        result = self.storage_config_service.get_csv_config()

        expected = {
            "default_directory": "csv",
            "collections": {
                "users": {"file": "users.csv"},
                "products": {"file": "products.csv"},
            },
        }

        self.assertEqual(result, expected)

    def test_get_vector_config(self):
        """Test getting vector storage configuration."""
        result = self.storage_config_service.get_vector_config()

        expected = {
            "default_directory": "vector",
            "default_provider": "local",
            "collections": {"embeddings": {"dimension": 768}},
        }

        self.assertEqual(result, expected)

    def test_get_kv_config(self):
        """Test getting key-value storage configuration."""
        result = self.storage_config_service.get_kv_config()

        expected = {
            "default_directory": "kv",
            "default_provider": "local",
            "collections": {"cache": {"ttl": 3600}},
        }

        self.assertEqual(result, expected)

    def test_get_blob_config(self):
        """Test getting blob storage configuration."""
        result = self.storage_config_service.get_blob_config()

        expected = {
            "default_directory": "blob",
            "default_provider": "file",
            "providers": {
                "azure": {
                    "connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test==;EndpointSuffix=core.windows.net",
                    "container_name": "blobs",
                },
                "s3": {"bucket_name": "test-bucket", "region": "us-east-1"},
                "gcs": {"bucket_name": "test-gcs-bucket", "project_id": "test-project"},
                "file": {"base_path": "data/blob/files"},
            },
        }

        self.assertEqual(result, expected)

    def test_get_provider_config(self):
        """Test getting configuration for specific provider."""
        result = self.storage_config_service.get_provider_config("csv")

        expected = {
            "default_directory": "csv",
            "collections": {
                "users": {"file": "users.csv"},
                "products": {"file": "products.csv"},
            },
        }

        self.assertEqual(result, expected)

        # Test non-existing provider
        result = self.storage_config_service.get_provider_config("missing")
        self.assertEqual(result, {})

    def test_get_blob_provider_config(self):
        """Test getting blob provider-specific configuration."""
        # Test Azure provider
        result = self.storage_config_service.get_blob_provider_config("azure")
        expected = {
            "connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test==;EndpointSuffix=core.windows.net",
            "container_name": "blobs",
        }
        self.assertEqual(result, expected)

        # Test S3 provider
        result = self.storage_config_service.get_blob_provider_config("s3")
        expected = {"bucket_name": "test-bucket", "region": "us-east-1"}
        self.assertEqual(result, expected)

        # Test GCS provider
        result = self.storage_config_service.get_blob_provider_config("gcs")
        expected = {"bucket_name": "test-gcs-bucket", "project_id": "test-project"}
        self.assertEqual(result, expected)

        # Test file provider
        result = self.storage_config_service.get_blob_provider_config("file")
        expected = {"base_path": "data/blob/files"}
        self.assertEqual(result, expected)

        # Test non-existing provider
        result = self.storage_config_service.get_blob_provider_config("missing")
        self.assertEqual(result, {})

    def test_get_value(self):
        """Test getting values using dot notation."""
        result = self.storage_config_service.get_value("csv.default_directory")
        self.assertEqual(result, "csv")

        result = self.storage_config_service.get_value("vector.default_provider")
        self.assertEqual(result, "local")

        # Test with default
        result = self.storage_config_service.get_value("missing.value", "default")
        self.assertEqual(result, "default")

    def test_get_collection_config(self):
        """Test getting configuration for specific collection."""
        result = self.storage_config_service.get_collection_config("csv", "users")
        self.assertEqual(result, {"file": "users.csv"})

        result = self.storage_config_service.get_collection_config(
            "vector", "embeddings"
        )
        self.assertEqual(result, {"dimension": 768})

        # Test non-existing collection
        result = self.storage_config_service.get_collection_config("csv", "missing")
        self.assertEqual(result, {})

    def test_get_default_directory(self):
        """Test getting default directory for storage type."""
        result = self.storage_config_service.get_default_directory("csv")
        self.assertEqual(result, "csv")

        # Test with fallback default
        result = self.storage_config_service.get_default_directory("missing")
        self.assertEqual(result, "data/missing")

    def test_get_default_provider(self):
        """Test getting default provider for storage type."""
        result = self.storage_config_service.get_default_provider("vector")
        self.assertEqual(result, "local")

        # Test with fallback default
        result = self.storage_config_service.get_default_provider("missing")
        self.assertEqual(result, "local")

    def test_list_collections(self):
        """Test listing collections for storage type."""
        result = self.storage_config_service.list_collections("csv")
        self.assertEqual(set(result), {"users", "products"})

        result = self.storage_config_service.list_collections("vector")
        self.assertEqual(result, ["embeddings"])

        # Test non-existing storage type
        result = self.storage_config_service.list_collections("missing")
        self.assertEqual(result, [])

    def test_has_collection(self):
        """Test checking if collection exists."""
        self.assertTrue(self.storage_config_service.has_collection("csv", "users"))
        self.assertTrue(
            self.storage_config_service.has_collection("vector", "embeddings")
        )

        self.assertFalse(self.storage_config_service.has_collection("csv", "missing"))
        self.assertFalse(
            self.storage_config_service.has_collection("missing", "collection")
        )

    def test_get_storage_summary(self):
        """Test getting storage configuration summary."""
        result = self.storage_config_service.get_storage_summary()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "loaded")
        self.assertIn("storage_types", result)
        self.assertIn("storage_type_count", result)
        self.assertIn("csv_collections", result)
        self.assertIn("vector_collections", result)
        self.assertIn("kv_collections", result)

        # Check specific values
        self.assertEqual(
            set(result["storage_types"]),
            {"csv", "vector", "kv", "json", "file", "blob"},
        )
        self.assertEqual(result["storage_type_count"], 6)
        self.assertEqual(set(result["csv_collections"]), {"users", "products"})
        self.assertEqual(result["vector_collections"], ["embeddings"])
        self.assertEqual(set(result["blob_providers"]), {"azure", "s3", "gcs", "file"})
        self.assertEqual(result["blob_provider_count"], 4)
        self.assertEqual(result["blob_default_provider"], "file")

    def test_replace_logger(self):
        """Test replacing bootstrap logger."""
        mock_logger = Mock()

        # Should not raise exception
        self.storage_config_service.replace_logger(mock_logger)

        # Logger should be replaced
        self.assertIs(self.storage_config_service._logger, mock_logger)

    def test_is_csv_storage_enabled_cache_hit(self):
        """Test CSV storage availability check with cache hit."""
        # Configure cache to return cached result
        cached_result = {
            "enabled": True,
            "validation_passed": True,
            "last_error": None,
            "checked_at": "cached",
            "warnings": [],
            "performance_metrics": {"validation_duration": 0.1},
            "validation_results": {"config_present": True},
        }
        self.mock_availability_cache_service.get_availability.return_value = (
            cached_result
        )

        # Call method
        result = self.storage_config_service.is_csv_storage_enabled()

        # Verify cache was checked
        self.mock_availability_cache_service.get_availability.assert_called_once_with(
            "storage", "csv"
        )

        # Verify result matches cached value
        self.assertTrue(result)

        # Verify cache was not set (since we got a hit)
        self.mock_availability_cache_service.set_availability.assert_not_called()

    def test_is_csv_storage_enabled_cache_miss(self):
        """Test CSV storage availability check with cache miss and fallback."""
        # Configure cache to return None (cache miss)
        self.mock_availability_cache_service.get_availability.return_value = None

        # Call method
        result = self.storage_config_service.is_csv_storage_enabled()

        # Verify cache was checked
        self.mock_availability_cache_service.get_availability.assert_called_once_with(
            "storage", "csv"
        )

        # Verify result is based on config (CSV is configured in setUp)
        self.assertTrue(result)

        # Verify cache was set with result
        self.mock_availability_cache_service.set_availability.assert_called_once()
        call_args = self.mock_availability_cache_service.set_availability.call_args
        self.assertEqual(call_args[0][:2], ("storage", "csv"))
        cached_data = call_args[0][2]
        self.assertTrue(cached_data["enabled"])

    def test_has_vector_storage_cache_scenarios(self):
        """Test vector storage availability with cache scenarios."""
        # Test cache hit scenario
        cached_result = {"enabled": True}
        self.mock_availability_cache_service.get_availability.return_value = (
            cached_result
        )

        result = self.storage_config_service.is_vector_storage_enabled()
        self.assertTrue(result)
        self.mock_availability_cache_service.get_availability.assert_called_with(
            "storage", "vector"
        )

        # Reset mock and test cache miss
        self.mock_availability_cache_service.reset_mock()
        self.mock_availability_cache_service.get_availability.return_value = None

        result = self.storage_config_service.is_vector_storage_enabled()
        self.assertTrue(result)  # Vector is configured in setUp
        self.mock_availability_cache_service.set_availability.assert_called_once()

    def test_has_kv_storage_cache_scenarios(self):
        """Test KV storage availability with cache scenarios."""
        # Test cache hit scenario
        cached_result = {"enabled": False}
        self.mock_availability_cache_service.get_availability.return_value = (
            cached_result
        )

        result = self.storage_config_service.is_kv_storage_enabled()
        self.assertFalse(result)
        self.mock_availability_cache_service.get_availability.assert_called_with(
            "storage", "kv"
        )

        # Reset mock and test cache miss
        self.mock_availability_cache_service.reset_mock()
        self.mock_availability_cache_service.get_availability.return_value = None

        result = self.storage_config_service.is_kv_storage_enabled()
        self.assertTrue(result)  # KV is configured in setUp
        self.mock_availability_cache_service.set_availability.assert_called_once()

    def test_is_json_storage_enabled_cache_scenarios(self):
        """Test JSON storage availability with cache scenarios."""
        # Test cache hit scenario
        cached_result = {"enabled": True, "validation_passed": True}
        self.mock_availability_cache_service.get_availability.return_value = (
            cached_result
        )

        result = self.storage_config_service.is_json_storage_enabled()
        self.assertTrue(result)
        self.mock_availability_cache_service.get_availability.assert_called_with(
            "storage", "json"
        )

        # Reset mock and test cache miss
        self.mock_availability_cache_service.reset_mock()
        self.mock_availability_cache_service.get_availability.return_value = None

        result = self.storage_config_service.is_json_storage_enabled()
        self.assertTrue(result)  # JSON is configured in setUp
        self.mock_availability_cache_service.set_availability.assert_called_once()

    def test_is_blob_storage_enabled_cache_scenarios(self):
        """Test blob storage availability with cache scenarios."""
        # Test cache hit scenario
        cached_result = {"enabled": True}
        self.mock_availability_cache_service.get_availability.return_value = (
            cached_result
        )

        result = self.storage_config_service.is_blob_storage_enabled()
        self.assertTrue(result)
        self.mock_availability_cache_service.get_availability.assert_called_with(
            "storage", "blob"
        )

        # Reset mock and test cache miss
        self.mock_availability_cache_service.reset_mock()
        self.mock_availability_cache_service.get_availability.return_value = None

        result = self.storage_config_service.is_blob_storage_enabled()
        self.assertTrue(result)  # Blob is configured in setUp
        self.mock_availability_cache_service.set_availability.assert_called_once()

    def test_cache_service_unavailable_fallback(self):
        """Test behavior when availability cache service is None."""
        # Create service without cache service
        service_without_cache = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=None,
        )

        # Should still work with direct config checks
        result = service_without_cache.is_csv_storage_enabled()
        self.assertTrue(result)  # CSV is configured

        # No cache calls should have been made
        self.mock_availability_cache_service.get_availability.assert_not_called()
        self.mock_availability_cache_service.set_availability.assert_not_called()

    def test_cache_service_exception_handling(self):
        """Test graceful handling of cache service exceptions."""
        # Configure cache service to raise exceptions
        self.mock_availability_cache_service.get_availability.side_effect = Exception(
            "Cache error"
        )
        self.mock_availability_cache_service.set_availability.side_effect = Exception(
            "Cache error"
        )

        # Should still work with fallback to direct config checks
        result = self.storage_config_service.is_csv_storage_enabled()
        self.assertTrue(result)  # CSV is configured

        # Cache should have been attempted but failed gracefully
        self.mock_availability_cache_service.get_availability.assert_called_once_with(
            "storage", "csv"
        )

    def test_is_storage_type_enabled(self):
        """Test checking if storage types are enabled."""
        # Test all configured storage types
        self.assertTrue(self.storage_config_service.is_storage_type_enabled("csv"))
        self.assertTrue(self.storage_config_service.is_storage_type_enabled("vector"))
        self.assertTrue(self.storage_config_service.is_storage_type_enabled("kv"))
        self.assertTrue(self.storage_config_service.is_storage_type_enabled("json"))
        self.assertTrue(self.storage_config_service.is_storage_type_enabled("blob"))
        self.assertTrue(self.storage_config_service.is_storage_type_enabled("file"))

        # Test non-configured storage type
        self.assertFalse(self.storage_config_service.is_storage_type_enabled("missing"))

    def test_is_storage_type_enabled_disabled_storage(self):
        """Test storage type checking with explicitly disabled storage."""
        # Set up config with disabled CSV storage (which does check enabled field)
        self.mock_config_service.load_config.return_value = {
            "csv": {"enabled": False, "default_directory": "csv"}
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Should return False for explicitly disabled CSV storage
        self.assertFalse(service.is_storage_type_enabled("csv"))

    def test_is_storage_type_enabled_blob_with_empty_config(self):
        """Test blob storage type checking with empty configuration."""
        # Set up config with empty blob storage (is_blob_storage_enabled now checks enabled field)
        self.mock_config_service.load_config.return_value = {
            "blob": {}  # Empty config missing default_directory, should return False
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Should return False for empty blob config (no default_directory)
        self.assertFalse(service.is_storage_type_enabled("blob"))

    def test_is_storage_type_enabled_blob_with_populated_config(self):
        """Test blob storage type checking with populated configuration."""
        # Set up config with populated blob storage
        self.mock_config_service.load_config.return_value = {
            "blob": {
                "default_directory": "blob",
                "providers": {"file": {"base_path": "data/blob/files"}},
            }
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Should return True for populated blob config
        self.assertTrue(service.is_storage_type_enabled("blob"))

    def test_is_storage_type_enabled_missing_blob_config(self):
        """Test blob storage type checking with missing configuration."""
        # Set up config without blob storage
        self.mock_config_service.load_config.return_value = {
            "csv": {"default_directory": "csv"}
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Should return False for missing blob config
        self.assertFalse(service.is_storage_type_enabled("blob"))

    def test_get_blob_data_path(self):
        """Test getting blob data directory path."""
        # Mock Path operations to avoid actually creating directories
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            result = self.storage_config_service.get_blob_data_path()

            # Should return correct hierarchical path: base_directory/storage_directory
            # Config has 'default_directory': 'blob', so path becomes agentmap_data/data/blob
            self.assertEqual(str(result), os.path.normpath("agentmap_data/data/blob"))

            # Should attempt to create directory since blob is enabled
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_get_blob_data_path_with_empty_config(self):
        """Test getting blob data path when blob storage config is empty."""
        # Set up config with empty blob storage (is_blob_storage_enabled returns False for {})
        self.mock_config_service.load_config.return_value = {
            "blob": {}  # Empty config, is_blob_storage_enabled() returns False
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Mock Path operations to verify directory creation is not attempted
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            result = service.get_blob_data_path()

            # Should return hierarchical path: base_directory/storage_type
            # Empty config falls back to storage type name 'blob', so path becomes agentmap_data/data/blob
            self.assertEqual(str(result), os.path.normpath("agentmap_data/data/blob"))

            # Should not attempt to create directory since blob config is empty
            mock_mkdir.assert_not_called()

    def test_get_blob_data_path_with_enabled_false(self):
        """Test getting blob data path when blob has enabled=false but config exists."""
        # Set up config with enabled=false but non-empty config
        # Note: is_blob_storage_enabled() now properly checks the enabled field
        self.mock_config_service.load_config.return_value = {
            "blob": {
                "enabled": False,  # This field is now respected by is_blob_storage_enabled()
                "default_directory": "blob",
            }
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Mock Path operations - directory creation should NOT be attempted since enabled=False
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            result = service.get_blob_data_path()

            # Should return hierarchical path: base_directory/storage_directory
            # Config has 'default_directory': 'blob', so path becomes agentmap_data/data/blob
            self.assertEqual(str(result), os.path.normpath("agentmap_data/data/blob"))

            # Should NOT attempt to create directory since is_blob_storage_enabled() returns False
            # (because enabled=False is explicitly set)
            mock_mkdir.assert_not_called()

    def test_has_vector_storage_with_enabled_false(self):
        """Test vector storage availability when explicitly disabled."""
        # Set up config with enabled=false
        self.mock_config_service.load_config.return_value = {
            "vector": {
                "enabled": False,
                "default_directory": "vector",
                "default_provider": "local",
            }
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Should return False when explicitly disabled
        self.assertFalse(service.is_vector_storage_enabled())

    def test_has_vector_storage_missing_default_directory(self):
        """Test vector storage availability when default_directory is missing."""
        # Set up config without default_directory
        self.mock_config_service.load_config.return_value = {
            "vector": {
                "default_provider": "local"
                # Missing default_directory
            }
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Should return False when default_directory is missing
        self.assertFalse(service.is_vector_storage_enabled())

    def test_has_kv_storage_with_enabled_false(self):
        """Test KV storage availability when explicitly disabled."""
        # Set up config with enabled=false
        self.mock_config_service.load_config.return_value = {
            "kv": {
                "enabled": False,
                "default_directory": "kv",
                "default_provider": "local",
            }
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Should return False when explicitly disabled
        self.assertFalse(service.is_kv_storage_enabled())

    def test_has_kv_storage_missing_default_directory(self):
        """Test KV storage availability when default_directory is missing."""
        # Set up config without default_directory
        self.mock_config_service.load_config.return_value = {
            "kv": {
                "default_provider": "local"
                # Missing default_directory
            }
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Should return False when default_directory is missing
        self.assertFalse(service.is_kv_storage_enabled())

    def test_is_blob_storage_enabled_with_enabled_false(self):
        """Test blob storage availability when explicitly disabled."""
        # Set up config with enabled=false
        self.mock_config_service.load_config.return_value = {
            "blob": {
                "enabled": False,
                "default_directory": "blob",
                "default_provider": "file",
            }
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Should return False when explicitly disabled
        self.assertFalse(service.is_blob_storage_enabled())

    def test_is_blob_storage_enabled_missing_default_directory(self):
        """Test blob storage availability when default_directory is missing."""
        # Set up config without default_directory
        self.mock_config_service.load_config.return_value = {
            "blob": {
                "default_provider": "file",
                "providers": {"file": {"base_path": "data/blob/files"}},
                # Missing default_directory
            }
        }

        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service,
        )

        # Should return False when default_directory is missing
        self.assertFalse(service.is_blob_storage_enabled())


if __name__ == "__main__":
    unittest.main()
