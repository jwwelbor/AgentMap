"""
Test suite for ConfigService - Pure infrastructure layer testing.

This module tests the ConfigService which should contain ONLY infrastructure code
(YAML loading) and NO business logic per the recent architecture fix.
"""

import unittest
from unittest.mock import Mock, patch, mock_open
import tempfile
import os
import yaml
from pathlib import Path

from src.agentmap.services.config.config_service import ConfigService
from agentmap.exceptions.base_exceptions import ConfigurationException
from tests.utils.mock_service_factory import MockServiceFactory


class TestConfigService(unittest.TestCase):
    """Test suite for ConfigService - Pure infrastructure layer."""
    
    def setUp(self):
        """Set up test fixtures with mock service factory."""
        self.mock_factory = MockServiceFactory()
        self.temp_dir = tempfile.mkdtemp()
        # ConfigService is a singleton, so we need to handle this carefully
        ConfigService._instance = None  # Reset singleton for testing
        self.config_service = ConfigService()
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        # Reset singleton for other tests
        ConfigService._instance = None
    
    def test_load_config_success(self):
        """Test successful config file loading - pure infrastructure."""
        # Create a test YAML file
        test_config = {
            'database': {
                'host': 'localhost',
                'port': 5432
            },
            'logging': {
                'level': 'INFO'
            }
        }
        
        test_file = os.path.join(self.temp_dir, 'test_config.yaml')
        with open(test_file, 'w') as f:
            yaml.dump(test_config, f)
        
        # Test loading
        result = self.config_service.load_config(test_file)
        
        self.assertEqual(result, test_config)
        self.assertIsInstance(result, dict)
    
    def test_load_config_none_path(self):
        """Test config loading with None path returns empty config."""
        result = self.config_service.load_config(None)
        self.assertEqual(result, {})
        self.assertIsInstance(result, dict)
    
    def test_load_config_file_not_found(self):
        """Test config loading with non-existent file returns empty config."""
        non_existent_file = os.path.join(self.temp_dir, 'non_existent.yaml')
        
        result = self.config_service.load_config(non_existent_file)
        self.assertEqual(result, {})
    
    def test_load_config_invalid_yaml(self):
        """Test config loading with invalid YAML content raises exception."""
        test_file = os.path.join(self.temp_dir, 'invalid.yaml')
        with open(test_file, 'w') as f:
            f.write('invalid: yaml: content: {\n')  # Invalid YAML
        
        with self.assertRaises(ConfigurationException):
            self.config_service.load_config(test_file)
    
    def test_load_config_empty_file(self):
        """Test config loading with empty file returns empty dict."""
        test_file = os.path.join(self.temp_dir, 'empty.yaml')
        with open(test_file, 'w') as f:
            f.write('')
        
        result = self.config_service.load_config(test_file)
        self.assertEqual(result, {})
    
    def test_get_value_from_config_simple(self):
        """Test getting simple values from config using dot notation."""
        config_data = {
            'database': {
                'host': 'localhost',
                'port': 5432
            },
            'logging': {
                'level': 'INFO'
            }
        }
        
        # Test simple value access
        result = self.config_service.get_value_from_config(config_data, 'database.host')
        self.assertEqual(result, 'localhost')
        
        result = self.config_service.get_value_from_config(config_data, 'database.port')
        self.assertEqual(result, 5432)
        
        result = self.config_service.get_value_from_config(config_data, 'logging.level')
        self.assertEqual(result, 'INFO')
    
    def test_get_value_from_config_nested(self):
        """Test getting nested values from config using dot notation."""
        config_data = {
            'services': {
                'agent': {
                    'config': {
                        'timeout': 30,
                        'retries': 3
                    }
                }
            }
        }
        
        result = self.config_service.get_value_from_config(config_data, 'services.agent.config.timeout')
        self.assertEqual(result, 30)
        
        result = self.config_service.get_value_from_config(config_data, 'services.agent.config.retries')
        self.assertEqual(result, 3)
    
    def test_get_value_from_config_default(self):
        """Test getting values with default when path doesn't exist."""
        config_data = {
            'database': {
                'host': 'localhost'
            }
        }
        
        # Test missing path returns default
        result = self.config_service.get_value_from_config(config_data, 'database.port', 3306)
        self.assertEqual(result, 3306)
        
        result = self.config_service.get_value_from_config(config_data, 'missing.section', 'default_value')
        self.assertEqual(result, 'default_value')
        
        # Test missing path with no default returns None
        result = self.config_service.get_value_from_config(config_data, 'missing.section')
        self.assertIsNone(result)
    
    def test_get_value_from_config_partial_path(self):
        """Test getting values when partial path exists."""
        config_data = {
            'database': {
                'host': 'localhost'
            }
        }
        
        # Test when intermediate path exists but final doesn't
        result = self.config_service.get_value_from_config(config_data, 'database.missing_key', 'default')
        self.assertEqual(result, 'default')
    
    def test_singleton_pattern(self):
        """Test that ConfigService follows singleton pattern."""
        service1 = ConfigService()
        service2 = ConfigService()
        
        self.assertIs(service1, service2)
        self.assertIs(service1, self.config_service)
    
    def test_replace_logger(self):
        """Test logger replacement functionality."""
        mock_logger = Mock()
        
        # Should not raise exception
        self.config_service.replace_logger(mock_logger)
        
        # Logger should be replaced
        self.assertIs(self.config_service._bootstrap_logger, mock_logger)
    
    def test_yaml_file_with_comments(self):
        """Test YAML file loading preserves data but ignores comments."""
        yaml_content = """
        # This is a comment
        database:
          host: localhost  # Another comment
          port: 5432
        # Final comment
        """
        
        test_file = os.path.join(self.temp_dir, 'commented_config.yaml')
        with open(test_file, 'w') as f:
            f.write(yaml_content)
        
        result = self.config_service.load_config(test_file)
        expected = {
            'database': {
                'host': 'localhost',
                'port': 5432
            }
        }
        
        self.assertEqual(result, expected)
    
    def test_basic_encoding_handling(self):
        """Test YAML file loading with basic text content."""
        # Test with basic ASCII and simple characters to avoid encoding issues
        test_config = {
            'text_key': 'simple_text_value',
            'number_key': 42,
            'boolean_key': True
        }
        test_file = os.path.join(self.temp_dir, 'text_config.yaml')
        
        with open(test_file, 'w') as f:
            yaml.dump(test_config, f)
        
        result = self.config_service.load_config(test_file)
        self.assertEqual(result, test_config)
    
    def test_infrastructure_only_methods(self):
        """CRITICAL: Ensure ConfigService contains ONLY infrastructure methods."""
        # This test validates the architecture fix
        # ConfigService should only have infrastructure methods
        
        allowed_methods = {
            'load_config',
            'get_value_from_config',
            'replace_logger',
            '__init__',
            '__new__'
        }
        
        actual_methods = set(method for method in dir(self.config_service) 
                           if not method.startswith('_') or method in ['__init__', '__new__'])
        
        # Check that only infrastructure methods exist
        extra_methods = actual_methods - allowed_methods
        self.assertEqual(extra_methods, set(), 
                        f"ConfigService contains unexpected methods (possible business logic): {extra_methods}")


if __name__ == '__main__':
    unittest.main()
