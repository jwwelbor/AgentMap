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
            storage_config_path=self.config_path
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
                storage_config_path=None
            )
        
        self.assertIn('Storage config path not specified', str(context.exception))
    
    def test_initialization_missing_file(self):
        """Test fail-fast behavior when config file doesn't exist."""
        missing_path = os.path.join(self.temp_dir, 'missing_config.yaml')
        
        with self.assertRaises(StorageConfigurationNotAvailableException) as context:
            StorageConfigService(
                config_service=self.mock_config_service,
                storage_config_path=missing_path
            )
        
        self.assertIn('Storage config file not found', str(context.exception))
    
    def test_initialization_config_load_error(self):
        """Test fail-fast behavior when config loading fails."""
        mock_config_service = Mock(spec=ConfigService)
        mock_config_service.load_config.side_effect = Exception("Parse error")
        
        with self.assertRaises(StorageConfigurationNotAvailableException) as context:
            StorageConfigService(
                config_service=mock_config_service,
                storage_config_path=self.config_path
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
        self.assertEqual(set(result['storage_types']), {'csv', 'vector', 'kv'})
        self.assertEqual(result['storage_type_count'], 3)
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
            storage_config_path=self.config_path
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
            storage_config_path=self.config_path
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


if __name__ == '__main__':
    unittest.main()
