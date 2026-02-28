"""
Test suite for AppConfigService - Domain logic layer testing.

This module tests the AppConfigService which contains domain logic
including configuration loading, validation, and business logic methods.
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agentmap.exceptions.base_exceptions import ConfigurationException
from src.agentmap.services.config.app_config_service import AppConfigService
from src.agentmap.services.config.config_service import ConfigService
from tests.utils.mock_service_factory import MockServiceFactory


class TestAppConfigService(unittest.TestCase):
    """Test suite for AppConfigService - Domain logic layer."""

    def setUp(self):
        """Set up test fixtures with mock service factory."""
        self.mock_factory = MockServiceFactory()
        # Create a mock ConfigService
        self.mock_config_service = Mock(spec=ConfigService)
        self.mock_config_service.load_config.return_value = {
            "logging": {"level": "INFO"},
            "llm": {"openai": {"api_key": "test-key"}},
            "prompts": {"directory": "prompts"},
            "execution": {"tracking": {"enabled": True}},
            "csv_path": "test.csv",
            "paths": {
                "custom_agents": "agentmap/custom_agents",
                "functions": "agentmap/custom_functions",
                "compiled_graphs": "agentmap/compiled_graphs",
                "cache": "agentmap_data/cache",
            },
        }
        self.mock_config_service.get_value_from_config.side_effect = (
            self._mock_get_value
        )

        self.app_config_service = AppConfigService(
            config_service=self.mock_config_service, config_path="test_config.yaml"
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

    def test_get_section_success(self):
        """Test getting configuration sections."""
        # Test existing section
        result = self.app_config_service.get_section("logging")
        self.assertEqual(result, {"level": "INFO"})

        # Test non-existing section with default
        result = self.app_config_service.get_section("missing", {"default": "value"})
        self.assertEqual(result, {"default": "value"})

    def test_get_value_success(self):
        """Test getting configuration values using dot notation."""
        # Test existing value
        result = self.app_config_service.get_value("logging.level")
        self.assertEqual(result, "INFO")

        # Test non-existing value with default
        result = self.app_config_service.get_value("missing.value", "default")
        self.assertEqual(result, "default")

    def test_get_custom_agents_path(self):
        """Test getting custom agents path."""
        result = self.app_config_service.get_custom_agents_path()
        self.assertEqual(result, Path("agentmap/custom_agents"))

    def test_get_functions_path(self):
        """Test getting functions path."""
        result = self.app_config_service.get_functions_path()
        self.assertEqual(result, Path("agentmap/custom_functions"))

    def test_get_logging_config(self):
        """Test getting logging configuration."""
        result = self.app_config_service.get_logging_config()
        self.assertEqual(result, {"level": "INFO"})

    def test_get_llm_config(self):
        """Test getting LLM configuration for specific provider."""
        result = self.app_config_service.get_llm_config("openai")
        self.assertEqual(result, {"api_key": "test-key"})

        # Test non-existing provider
        result = self.app_config_service.get_llm_config("missing")
        self.assertEqual(result, {})

    def test_get_routing_config(self):
        """Test getting routing configuration with defaults."""
        result = self.app_config_service.get_routing_config()

        # Should return configuration with defaults merged
        self.assertIsInstance(result, dict)
        self.assertIn("enabled", result)
        self.assertIn("complexity_analysis", result)
        self.assertIn("task_types", result)
        self.assertIn("fallback", result)

        # Test default values
        self.assertTrue(result["enabled"])
        self.assertIn("general", result["task_types"])

    def test_get_prompts_config(self):
        """Test getting prompts configuration."""
        result = self.app_config_service.get_prompts_config()
        self.assertEqual(result, {"directory": "prompts"})

    def test_get_prompts_directory(self):
        """Test getting prompts directory path."""
        result = self.app_config_service.get_prompts_directory()
        self.assertEqual(result, Path("prompts"))

    def test_get_prompt_registry_path(self):
        """Test getting prompt registry path."""
        result = self.app_config_service.get_prompt_registry_path()
        self.assertEqual(result, Path("agentmap_data/prompts/prompt_registry.yaml"))

    def test_get_execution_config(self):
        """Test getting execution configuration."""
        result = self.app_config_service.get_execution_config()
        self.assertEqual(result, {"tracking": {"enabled": True}})

    def test_get_tracking_config(self):
        """Test getting tracking configuration."""
        result = self.app_config_service.get_tracking_config()
        self.assertEqual(result, {"enabled": True})

    def test_get_output_validation_config_with_defaults(self):
        """Test getting output validation config returns proper defaults."""
        # When no config exists, should return all defaults
        result = self.app_config_service.get_output_validation_config()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["multi_output_mode"], "warn")
        self.assertTrue(result["require_all_outputs"])
        self.assertTrue(result["allow_extra_outputs"])

    def test_get_output_validation_config_merges_with_config(self):
        """Test that configured values override defaults."""
        # Update mock config data to include validation config
        self.mock_config_service.load_config.return_value.update(
            {
                "execution": {
                    "validation": {
                        "multi_output_mode": "error",
                        "require_all_outputs": False,
                    }
                }
            }
        )

        # Recreate service with updated config
        app_config_updated = AppConfigService(
            config_service=self.mock_config_service, config_path="test_config.yaml"
        )

        result = app_config_updated.get_output_validation_config()

        # User values should override defaults
        self.assertEqual(result["multi_output_mode"], "error")
        self.assertFalse(result["require_all_outputs"])
        # Default values should still be present for keys not in config
        self.assertTrue(result["allow_extra_outputs"])

    def test_get_output_validation_config_partial_override(self):
        """Test that partial config overrides only specified keys."""
        # Update mock config with partial validation settings
        self.mock_config_service.load_config.return_value.update(
            {
                "execution": {
                    "validation": {
                        "multi_output_mode": "ignore",
                    }
                }
            }
        )

        app_config_partial = AppConfigService(
            config_service=self.mock_config_service, config_path="test_config.yaml"
        )

        result = app_config_partial.get_output_validation_config()

        # Only specified key should be overridden
        self.assertEqual(result["multi_output_mode"], "ignore")
        # Other defaults should remain
        self.assertTrue(result["require_all_outputs"])
        self.assertTrue(result["allow_extra_outputs"])

    def test_get_storage_config_path(self):
        """Test getting storage config path."""
        # Test when config key doesn't exist - should return None
        result = self.app_config_service.get_storage_config_path()
        self.assertIsNone(result)

        # Test when config key exists
        self.mock_config_service.load_config.return_value.update(
            {"storage_config_path": "custom_storage.yaml"}
        )
        # Recreate service with updated config
        app_config_with_storage = AppConfigService(
            config_service=self.mock_config_service, config_path="test_config.yaml"
        )
        result = app_config_with_storage.get_storage_config_path()
        self.assertEqual(result, Path("custom_storage.yaml"))

    def test_get_cache_path(self):
        """Test getting cache path from configuration.

        AppConfigService should only return the configured path value.
        Validation and security checks are handled by FilePathService.
        """
        # Test default cache path
        result = self.app_config_service.get_cache_path()
        self.assertEqual(result, Path("agentmap_data/cache"))

        # Test configured cache path
        self.mock_config_service.load_config.return_value.update(
            {"paths": {"cache": "custom/cache/dir"}}
        )
        app_config_with_cache = AppConfigService(
            config_service=self.mock_config_service, config_path="test_config.yaml"
        )
        result = app_config_with_cache.get_cache_path()
        self.assertEqual(result, Path("custom/cache/dir"))

    def test_cache_path_security_is_not_config_responsibility(self):
        """Test that AppConfigService does NOT validate paths for security.

        This is by design - validation is FilePathService's responsibility.
        AppConfigService should return whatever is configured, even if unsafe.
        """
        # Test that unsafe paths are returned as-is (validation happens elsewhere)
        unsafe_paths = [
            "../../../etc/passwd",
            "cache\x00/test",
            "/etc/shadow",
            "C:\\Windows\\System32",
        ]

        for unsafe_path in unsafe_paths:
            self.mock_config_service.load_config.return_value.update(
                {"paths": {"cache": unsafe_path}}
            )
            app_config = AppConfigService(
                config_service=self.mock_config_service, config_path="test_config.yaml"
            )

            # AppConfigService returns the path as-is without validation
            result = app_config.get_cache_path()
            self.assertEqual(result, Path(unsafe_path))

    def test_validate_config_success(self):
        """Test configuration validation success."""
        result = self.app_config_service.validate_config()
        self.assertTrue(result)

    def test_validate_config_missing_sections(self):
        """Test configuration validation with missing sections."""
        # Set up config with missing sections
        self.app_config_service._config_data = {"logging": {"level": "INFO"}}

        # Should still return True but log warnings
        result = self.app_config_service.validate_config()
        self.assertTrue(result)

    def test_get_config_summary(self):
        """Test getting configuration summary."""
        result = self.app_config_service.get_config_summary()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["status"], "loaded")
        self.assertIn("sections", result)
        self.assertIn("section_count", result)
        self.assertIn("llm_providers", result)

    def test_get_all_config(self):
        """Test getting all configuration data."""
        result = self.app_config_service.get_all()

        self.assertIsInstance(result, dict)
        self.assertIn("logging", result)
        self.assertIn("llm", result)

    def test_replace_logger(self):
        """Test replacing bootstrap logger."""
        mock_logger = Mock()

        # Should not raise exception
        self.app_config_service.replace_logger(mock_logger)

        # Logger should be replaced
        self.assertIs(self.app_config_service._logger, mock_logger)

    def test_merge_with_defaults(self):
        """Test merging configuration with defaults."""
        config = {"section1": {"key1": "value1"}}

        defaults = {
            "section1": {"key1": "default1", "key2": "default2"},
            "section2": {"key3": "default3"},
        }

        result = self.app_config_service._merge_with_defaults(config, defaults)

        expected = {
            "section1": {
                "key1": "value1",  # User value preserved
                "key2": "default2",  # Default added
            },
            "section2": {"key3": "default3"},  # Default section added
        }

        self.assertEqual(result, expected)

    def test_configuration_not_loaded_error(self):
        """Test error when configuration is not loaded."""
        # Create service without loading config
        service = AppConfigService.__new__(AppConfigService)
        service._config_data = None

        with self.assertRaises(ConfigurationException):
            service.get_section("test")

        with self.assertRaises(ConfigurationException):
            service.get_value("test.value")

        with self.assertRaises(ConfigurationException):
            service.validate_config()

        with self.assertRaises(ConfigurationException):
            service.get_all()

    def test_config_loading_error_handling(self):
        """Test error handling during config loading."""
        mock_config_service = Mock(spec=ConfigService)
        mock_config_service.load_config.side_effect = Exception("Config load error")

        with self.assertRaises(ConfigurationException) as context:
            AppConfigService(
                config_service=mock_config_service, config_path="test.yaml"
            )

        self.assertIn(
            "Failed to load application configuration", str(context.exception)
        )

    def test_config_summary_not_loaded(self):
        """Test configuration summary when config is not loaded."""
        service = AppConfigService.__new__(AppConfigService)
        service._config_data = None

        result = service.get_config_summary()
        self.assertEqual(result, {"status": "not_loaded"})


class TestAppConfigServiceWithFilePathService(unittest.TestCase):
    """Test suite demonstrating integration pattern with FilePathService.

    These tests show how services should interact: AppConfigService provides
    raw config values, FilePathService validates them.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config_service = Mock(spec=ConfigService)
        self.mock_config_service.load_config.return_value = {
            "paths": {"cache": "agentmap_data/cache"}
        }
        self.mock_config_service.get_value_from_config.side_effect = (
            self._mock_get_value
        )

        self.app_config_service = AppConfigService(
            config_service=self.mock_config_service, config_path="test_config.yaml"
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

    @patch("agentmap.services.file_path_service.FilePathService")
    def test_proper_separation_of_concerns(self, mock_file_path_service_class):
        """Test that path validation is handled by FilePathService, not config.

        This test demonstrates the proper architectural pattern:
        1. AppConfigService provides raw configuration values
        2. FilePathService validates paths for security
        3. Consumer services coordinate between them
        """
        # Setup mock FilePathService
        mock_file_path_service = Mock()
        mock_file_path_service_class.return_value = mock_file_path_service

        # Simulate a consumer service using both services correctly
        cache_path_config = self.app_config_service.get_cache_path()

        # Consumer would then validate the path through FilePathService
        mock_file_path_service.validate_safe_path.return_value = True
        mock_file_path_service.ensure_directory.return_value = Path(
            "agentmap_data/cache"
        )

        # This is how a consumer service would use both services
        is_valid = mock_file_path_service.validate_safe_path(str(cache_path_config))
        self.assertTrue(is_valid)

        # And ensure the directory exists
        actual_path = mock_file_path_service.ensure_directory(str(cache_path_config))
        self.assertEqual(actual_path, Path("agentmap_data/cache"))

    @patch("agentmap.services.file_path_service.FilePathService")
    def test_unsafe_path_handling_pattern(self, mock_file_path_service_class):
        """Test how unsafe paths should be handled in the architecture.

        AppConfigService returns the configured value (even if unsafe).
        FilePathService detects and blocks unsafe paths.
        """
        # Setup unsafe path in config
        self.mock_config_service.load_config.return_value.update(
            {"paths": {"cache": "../../../etc/passwd"}}
        )
        unsafe_config = AppConfigService(
            config_service=self.mock_config_service, config_path="test_config.yaml"
        )

        # AppConfigService returns the unsafe path as-is
        cache_path = unsafe_config.get_cache_path()
        self.assertEqual(cache_path, Path("../../../etc/passwd"))

        # FilePathService would detect and reject it
        mock_file_path_service = Mock()
        mock_file_path_service_class.return_value = mock_file_path_service

        from agentmap.exceptions.base_exceptions import PathTraversalError

        mock_file_path_service.validate_safe_path.side_effect = PathTraversalError(
            "Path traversal detected"
        )

        # Consumer service would handle the validation error
        with self.assertRaises(PathTraversalError):
            mock_file_path_service.validate_safe_path(str(cache_path))


if __name__ == "__main__":
    unittest.main()
