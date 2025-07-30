"""
Test suite for StorageConfigService - Fail-fast behavior testing.

This module tests the StorageConfigService which implements fail-fast behavior
with strict validation and exception-based failure handling.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from pathlib import Path

from src.agentmap.services.config.storage_config_service import StorageConfigService
from src.agentmap.services.config.config_service import ConfigService
from agentmap.exceptions.service_exceptions import StorageConfigurationNotAvailableException
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
            'csv': {
                'default_directory': 'data/csv',
                'collections': {
                    'users': {'file': 'users.csv'},
                    'products': {'file': 'products.csv'}
                }
            },
            'vector': {
                'default_provider': 'local',
                'collections': {
                    'embeddings': {'dimension': 768}
                }
            },
            'kv': {
                'default_provider': 'local',
                'collections': {
                    'cache': {'ttl': 3600}
                }
            },
            'json': {
                'default_directory': 'data/json',
                'collections': {
                    'documents': {'file': 'documents.json'}
                }
            },
            'file': {
                'default_directory': 'data/files',
                'collections': {
                    'attachments': {}
                }
            }
        }
        self.mock_config_service.get_value_from_config.side_effect = self._mock_get_value
        
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'storage_config.yaml')
        
        # Create a test storage config file
        with open(self.config_path, 'w') as f:
            f.write('csv:\n  default_directory: data/csv\n')
        
        self.storage_config_service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service
        )
    
    def _mock_get_value(self, config_data, path, default=None):
        """Mock implementation of get_value_from_config."""
        parts = path.split('.')
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
                availability_cache_service=self.mock_availability_cache_service
            )
        
        self.assertIn('Storage config path not specified', str(context.exception))
    
    def test_initialization_missing_file(self):
        """Test fail-fast behavior when config file doesn't exist."""
        missing_path = os.path.join(self.temp_dir, 'missing_config.yaml')
        
        with self.assertRaises(StorageConfigurationNotAvailableException) as context:
            StorageConfigService(
                config_service=self.mock_config_service,
                storage_config_path=missing_path,
                availability_cache_service=self.mock_availability_cache_service
            )
        
        self.assertIn('Storage config file not found', str(context.exception))
    
    def test_initialization_config_load_error(self):
        """Test fail-fast behavior when config loading fails."""
        mock_config_service = Mock(spec=ConfigService)
        mock_config_service.load_config.side_effect = Exception("Parse error")
        
        with self.assertRaises(StorageConfigurationNotAvailableException) as context:
            StorageConfigService(
                config_service=mock_config_service,
                storage_config_path=self.config_path,
                availability_cache_service=self.mock_availability_cache_service
            )
        
        self.assertIn('Failed to load storage config', str(context.exception))
    
    def test_get_csv_config(self):
        """Test getting CSV storage configuration."""
        result = self.storage_config_service.get_csv_config()
        
        expected = {
            'default_directory': 'data/csv',
            'collections': {
                'users': {'file': 'users.csv'},
                'products': {'file': 'products.csv'}
            }
        }
        
        self.assertEqual(result, expected)
    
    def test_get_vector_config(self):
        """Test getting vector storage configuration."""
        result = self.storage_config_service.get_vector_config()
        
        expected = {
            'default_provider': 'local',
            'collections': {
                'embeddings': {'dimension': 768}
            }
        }
        
        self.assertEqual(result, expected)
    
    def test_get_kv_config(self):
        """Test getting key-value storage configuration."""
        result = self.storage_config_service.get_kv_config()
        
        expected = {
            'default_provider': 'local',
            'collections': {
                'cache': {'ttl': 3600}
            }
        }
        
        self.assertEqual(result, expected)
    
    def test_get_provider_config(self):
        """Test getting configuration for specific provider."""
        result = self.storage_config_service.get_provider_config('csv')
        
        expected = {
            'default_directory': 'data/csv',
            'collections': {
                'users': {'file': 'users.csv'},
                'products': {'file': 'products.csv'}
            }
        }
        
        self.assertEqual(result, expected)
        
        # Test non-existing provider
        result = self.storage_config_service.get_provider_config('missing')
        self.assertEqual(result, {})
    
    def test_get_value(self):
        """Test getting values using dot notation."""
        result = self.storage_config_service.get_value('csv.default_directory')
        self.assertEqual(result, 'data/csv')
        
        result = self.storage_config_service.get_value('vector.default_provider')
        self.assertEqual(result, 'local')
        
        # Test with default
        result = self.storage_config_service.get_value('missing.value', 'default')
        self.assertEqual(result, 'default')
    
    def test_get_collection_config(self):
        """Test getting configuration for specific collection."""
        result = self.storage_config_service.get_collection_config('csv', 'users')
        self.assertEqual(result, {'file': 'users.csv'})
        
        result = self.storage_config_service.get_collection_config('vector', 'embeddings')
        self.assertEqual(result, {'dimension': 768})
        
        # Test non-existing collection
        result = self.storage_config_service.get_collection_config('csv', 'missing')
        self.assertEqual(result, {})
    
    def test_get_default_directory(self):
        """Test getting default directory for storage type."""
        result = self.storage_config_service.get_default_directory('csv')
        self.assertEqual(result, 'data/csv')
        
        # Test with fallback default
        result = self.storage_config_service.get_default_directory('missing')
        self.assertEqual(result, 'data/missing')
    
    def test_get_default_provider(self):
        """Test getting default provider for storage type."""
        result = self.storage_config_service.get_default_provider('vector')
        self.assertEqual(result, 'local')
        
        # Test with fallback default
        result = self.storage_config_service.get_default_provider('missing')
        self.assertEqual(result, 'local')
    
    def test_list_collections(self):
        """Test listing collections for storage type."""
        result = self.storage_config_service.list_collections('csv')
        self.assertEqual(set(result), {'users', 'products'})
        
        result = self.storage_config_service.list_collections('vector')
        self.assertEqual(result, ['embeddings'])
        
        # Test non-existing storage type
        result = self.storage_config_service.list_collections('missing')
        self.assertEqual(result, [])
    
    def test_has_collection(self):
        """Test checking if collection exists."""
        self.assertTrue(self.storage_config_service.has_collection('csv', 'users'))
        self.assertTrue(self.storage_config_service.has_collection('vector', 'embeddings'))
        
        self.assertFalse(self.storage_config_service.has_collection('csv', 'missing'))
        self.assertFalse(self.storage_config_service.has_collection('missing', 'collection'))
    
    def test_get_storage_summary(self):
        """Test getting storage configuration summary."""
        result = self.storage_config_service.get_storage_summary()
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['status'], 'loaded')
        self.assertIn('storage_types', result)
        self.assertIn('storage_type_count', result)
        self.assertIn('csv_collections', result)
        self.assertIn('vector_collections', result)
        self.assertIn('kv_collections', result)
        
        # Check specific values
        self.assertEqual(set(result['storage_types']), {'csv', 'vector', 'kv', 'json', 'file'})
        self.assertEqual(result['storage_type_count'], 5)
        self.assertEqual(set(result['csv_collections']), {'users', 'products'})
        self.assertEqual(result['vector_collections'], ['embeddings'])
    
    def test_validate_storage_config(self):
        """Test storage configuration validation."""
        result = self.storage_config_service.validate_storage_config()
        
        self.assertIsInstance(result, dict)
        self.assertIn('warnings', result)
        self.assertIn('errors', result)
        
        # Should have no errors for valid config
        self.assertEqual(result['errors'], [])
    
    def test_validate_storage_config_missing_types(self):
        """Test validation with missing storage types."""
        # Set up config with missing storage types
        self.mock_config_service.load_config.return_value = {
            'csv': {'default_directory': 'data/csv'}
            # Missing 'vector' and 'kv'
        }
        
        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service
        )
        
        result = service.validate_storage_config()
        
        # Should have warnings for missing types
        self.assertGreater(len(result['warnings']), 0)
        self.assertTrue(any('vector' in warning for warning in result['warnings']))
        self.assertTrue(any('kv' in warning for warning in result['warnings']))
    
    def test_validate_storage_config_invalid_structure(self):
        """Test validation with invalid configuration structure."""
        # Set up config with invalid structure
        self.mock_config_service.load_config.return_value = {
            'csv': 'invalid_string_instead_of_dict'
        }
        
        service = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=self.mock_availability_cache_service
        )
        
        result = service.validate_storage_config()
        
        # Should have errors for invalid structure
        self.assertGreater(len(result['errors']), 0)
        self.assertTrue(any('must be a dictionary' in error for error in result['errors']))
    
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
            "validation_results": {"config_present": True}
        }
        self.mock_availability_cache_service.get_availability.return_value = cached_result
        
        # Call method
        result = self.storage_config_service.is_csv_storage_enabled()
        
        # Verify cache was checked
        self.mock_availability_cache_service.get_availability.assert_called_once_with("storage", "csv")
        
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
        self.mock_availability_cache_service.get_availability.assert_called_once_with("storage", "csv")
        
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
        self.mock_availability_cache_service.get_availability.return_value = cached_result
        
        result = self.storage_config_service.has_vector_storage()
        self.assertTrue(result)
        self.mock_availability_cache_service.get_availability.assert_called_with("storage", "vector")
        
        # Reset mock and test cache miss
        self.mock_availability_cache_service.reset_mock()
        self.mock_availability_cache_service.get_availability.return_value = None
        
        result = self.storage_config_service.has_vector_storage()
        self.assertTrue(result)  # Vector is configured in setUp
        self.mock_availability_cache_service.set_availability.assert_called_once()
    
    def test_has_kv_storage_cache_scenarios(self):
        """Test KV storage availability with cache scenarios."""
        # Test cache hit scenario
        cached_result = {"enabled": False}
        self.mock_availability_cache_service.get_availability.return_value = cached_result
        
        result = self.storage_config_service.has_kv_storage()
        self.assertFalse(result)
        self.mock_availability_cache_service.get_availability.assert_called_with("storage", "kv")
        
        # Reset mock and test cache miss
        self.mock_availability_cache_service.reset_mock()
        self.mock_availability_cache_service.get_availability.return_value = None
        
        result = self.storage_config_service.has_kv_storage()
        self.assertTrue(result)  # KV is configured in setUp
        self.mock_availability_cache_service.set_availability.assert_called_once()
    
    def test_is_json_storage_enabled_cache_scenarios(self):
        """Test JSON storage availability with cache scenarios."""
        # Test cache hit scenario
        cached_result = {"enabled": True, "validation_passed": True}
        self.mock_availability_cache_service.get_availability.return_value = cached_result
        
        result = self.storage_config_service.is_json_storage_enabled()
        self.assertTrue(result)
        self.mock_availability_cache_service.get_availability.assert_called_with("storage", "json")
        
        # Reset mock and test cache miss
        self.mock_availability_cache_service.reset_mock()
        self.mock_availability_cache_service.get_availability.return_value = None
        
        result = self.storage_config_service.is_json_storage_enabled()
        self.assertTrue(result)  # JSON is configured in setUp
        self.mock_availability_cache_service.set_availability.assert_called_once()
    
    def test_cache_service_unavailable_fallback(self):
        """Test behavior when availability cache service is None."""
        # Create service without cache service
        service_without_cache = StorageConfigService(
            config_service=self.mock_config_service,
            storage_config_path=self.config_path,
            availability_cache_service=None
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
        self.mock_availability_cache_service.get_availability.side_effect = Exception("Cache error")
        self.mock_availability_cache_service.set_availability.side_effect = Exception("Cache error")
        
        # Should still work with fallback to direct config checks
        result = self.storage_config_service.is_csv_storage_enabled()
        self.assertTrue(result)  # CSV is configured
        
        # Cache should have been attempted but failed gracefully
        self.mock_availability_cache_service.get_availability.assert_called_once_with("storage", "csv")


if __name__ == '__main__':
    unittest.main()
