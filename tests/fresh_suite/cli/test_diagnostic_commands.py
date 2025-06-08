"""
CLI Diagnostic Commands Tests - Simplified and Working.

Tests for diagnostic and configuration CLI commands:
- diagnose: Check system dependencies and configuration
- config: Display current configuration
- validate-cache: Manage validation result cache
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from agentmap.core.cli.main_cli import app


class SimpleCLITestBase(unittest.TestCase):
    """Simplified base class for CLI testing without complex mixins."""
    
    def setUp(self):
        """Set up CLI test environment."""
        self.runner = CliRunner()
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create mock services with simple, realistic defaults
        self.mock_features_service = Mock()
        self.mock_dependency_checker = Mock()
        self.mock_app_config_service = Mock()
        self.mock_validation_cache_service = Mock()
        self.setup_service_defaults()
    
    def setup_service_defaults(self):
        """Configure realistic service defaults."""
        # Features registry service
        self.mock_features_service.is_feature_enabled.return_value = True
        self.mock_features_service.is_provider_available.return_value = True
        self.mock_features_service.is_provider_registered.return_value = True
        self.mock_features_service.is_provider_validated.return_value = True
        
        # Dependency checker service
        self.mock_dependency_checker.check_llm_dependencies.return_value = (True, [])
        self.mock_dependency_checker.check_storage_dependencies.return_value = (True, [])
        
        # App config service
        self.mock_app_config_service.get_all.return_value = {
            "logging": {"level": "INFO"},
            "execution": {"timeout": 30},
            "paths": {"csv_data": "/path/to/csv"}
        }
        
        # Validation cache service
        cache_stats = {
            "total_files": 5,
            "valid_files": 4,
            "expired_files": 1,
            "corrupted_files": 0
        }
        self.mock_validation_cache_service.get_validation_cache_stats.return_value = cache_stats
        self.mock_validation_cache_service.clear_validation_cache.return_value = 3
        self.mock_validation_cache_service.cleanup_validation_cache.return_value = 1
    
    def run_command(self, args):
        """Run CLI command with proper container mocking."""
        mock_container = Mock()
        mock_container.features_registry_service.return_value = self.mock_features_service
        mock_container.dependency_checker_service.return_value = self.mock_dependency_checker
        mock_container.app_config_service.return_value = self.mock_app_config_service
        mock_container.validation_cache_service.return_value = self.mock_validation_cache_service
        
        # Patch all possible import paths for diagnostic commands
        patches = [
            patch('agentmap.core.cli.diagnostic_commands.initialize_di', return_value=mock_container),
            patch('agentmap.di.initialize_di', return_value=mock_container),
        ]
        
        # Start all patches
        for p in patches:
            p.start()
        
        try:
            return self.runner.invoke(app, args, catch_exceptions=True)
        finally:
            # Stop all patches
            for p in patches:
                try:
                    p.stop()
                except RuntimeError:
                    pass  # Patch was already stopped
    
    def assert_success(self, result, expected_text=None):
        """Assert command succeeded."""
        self.assertEqual(result.exit_code, 0, f"Command failed: {result.stdout}")
        if expected_text:
            self.assertIn(expected_text, result.stdout)
    
    def assert_failure(self, result, expected_text=None):
        """Assert command failed."""
        self.assertNotEqual(result.exit_code, 0, f"Command should have failed: {result.stdout}")
        if expected_text:
            self.assertIn(expected_text, result.stdout)
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestDiagnoseCommand(SimpleCLITestBase):
    """Test diagnose command."""
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["diagnose", "--help"])
        self.assert_success(result)
        self.assertIn("diagnose", result.stdout.lower())
    
    def test_diagnose_all_good(self):
        """Test diagnose when all dependencies are available."""
        result = self.run_command(["diagnose"])
        
        self.assert_success(result)
        self.assertIn("AgentMap Dependency Diagnostics", result.stdout)
        self.assertIn("LLM Dependencies", result.stdout)
        self.assertIn("Storage Dependencies", result.stdout)
        
        # Verify services were called
        self.mock_dependency_checker.check_llm_dependencies.assert_called()
        self.mock_dependency_checker.check_storage_dependencies.assert_called()
    
    def test_diagnose_missing_dependencies(self):
        """Test diagnose when some dependencies are missing."""
        # Configure specific LLM dependencies as missing
        def mock_llm_dependencies(provider=None):
            if provider == "openai":
                return (False, ["openai>=1.0.0"])
            elif provider == "anthropic":
                return (False, ["anthropic>=0.3.0"])
            elif provider == "google":
                return (True, [])  # Google has dependencies
            else:
                return (False, ["openai>=1.0.0"])  # Default case
        
        self.mock_dependency_checker.check_llm_dependencies.side_effect = mock_llm_dependencies
        
        # Also configure these providers as not available in features service
        def mock_provider_available(feature_type, provider):
            if feature_type == "llm" and provider in ["openai", "anthropic"]:
                return False
            return True
        
        self.mock_features_service.is_provider_available.side_effect = mock_provider_available
        
        result = self.run_command(["diagnose"])
        
        self.assert_success(result)
        self.assertIn("❌ Not available", result.stdout)
        self.assertIn("Installation Suggestions", result.stdout)
    
    def test_diagnose_with_config(self):
        """Test diagnose with custom configuration."""
        result = self.run_command(["diagnose", "--config", "custom_config.yaml"])
        
        self.assert_success(result)
    
    def test_diagnose_shows_environment_info(self):
        """Test that diagnose shows environment information."""
        result = self.run_command(["diagnose"])
        
        self.assert_success(result)
        self.assertIn("Environment Information", result.stdout)


class TestConfigCommand(SimpleCLITestBase):
    """Test config command."""
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["config", "--help"])
        self.assert_success(result)
        self.assertIn("config", result.stdout.lower())
    
    def test_show_config(self):
        """Test basic config display."""
        result = self.run_command(["config"])
        
        self.assert_success(result)
        self.assertIn("Configuration values", result.stdout)
        self.assertIn("logging", result.stdout)
        self.assertIn("level: INFO", result.stdout)
        
        # Verify config service was called
        self.mock_app_config_service.get_all.assert_called_once()
    
    def test_config_with_custom_path(self):
        """Test config with custom configuration file."""
        result = self.run_command(["config", "--path", "custom_config.yaml"])
        
        self.assert_success(result)
    
    def test_config_with_nested_values(self):
        """Test config display with nested configuration."""
        # Configure nested config
        nested_config = {
            "llm": {
                "providers": {
                    "openai": {
                        "model": "gpt-4",
                        "temperature": 0.7
                    }
                }
            }
        }
        self.mock_app_config_service.get_all.return_value = nested_config
        
        result = self.run_command(["config"])
        
        self.assert_success(result)
        self.assertIn("llm:", result.stdout)
        self.assertIn("providers:", result.stdout)
        self.assertIn("openai:", result.stdout)
    
    def test_config_load_failure(self):
        """Test config command when configuration loading fails."""
        # Configure service to fail
        self.mock_app_config_service.get_all.side_effect = Exception("Config load error")
        
        result = self.run_command(["config"])
        
        self.assert_failure(result)
        self.assertIn("❌ Failed to load configuration", result.stdout)


class TestValidateCacheCommand(SimpleCLITestBase):
    """Test validate-cache command."""
    
    def test_help_output(self):
        """Test --help shows usage information."""
        result = self.run_command(["validate-cache", "--help"])
        self.assert_success(result)
        self.assertIn("validate-cache", result.stdout.lower())
    
    def test_show_cache_stats(self):
        """Test showing cache statistics."""
        result = self.run_command(["validate-cache"])
        
        self.assert_success(result)
        self.assertIn("Validation Cache Statistics", result.stdout)
        self.assertIn("Total files: 5", result.stdout)
        self.assertIn("Valid files: 4", result.stdout)
        self.assertIn("Expired files: 1", result.stdout)
        
        # Verify cache service was called
        self.mock_validation_cache_service.get_validation_cache_stats.assert_called_once()
    
    def test_show_stats_explicit(self):
        """Test cache stats with explicit --stats flag."""
        result = self.run_command(["validate-cache", "--stats"])
        
        self.assert_success(result)
        self.assertIn("Validation Cache Statistics", result.stdout)
    
    def test_clear_cache(self):
        """Test clearing cache."""
        result = self.run_command(["validate-cache", "--clear"])
        
        self.assert_success(result)
        self.assertIn("✅ Cleared 3 cache entries", result.stdout)
        
        # Verify clear method was called
        self.mock_validation_cache_service.clear_validation_cache.assert_called_once()
    
    def test_clear_specific_file(self):
        """Test clearing cache for specific file."""
        result = self.run_command(["validate-cache", "--clear", "--file", "specific.csv"])
        
        self.assert_success(result)
        self.assertIn("✅ Cleared 3 cache entries for specific.csv", result.stdout)
    
    def test_cleanup_expired(self):
        """Test cleaning up expired cache entries."""
        result = self.run_command(["validate-cache", "--cleanup"])
        
        self.assert_success(result)
        self.assertIn("✅ Removed 1 expired cache entries", result.stdout)
        
        # Verify cleanup method was called
        self.mock_validation_cache_service.cleanup_validation_cache.assert_called_once()
    
    def test_cache_suggestions(self):
        """Test cache shows cleanup suggestions when needed."""
        # Configure cache with issues
        cache_with_issues = {
            "total_files": 10,
            "valid_files": 7,
            "expired_files": 2,
            "corrupted_files": 1
        }
        self.mock_validation_cache_service.get_validation_cache_stats.return_value = cache_with_issues
        
        result = self.run_command(["validate-cache"])
        
        self.assert_success(result)
        self.assertIn("Expired files: 2", result.stdout)
        self.assertIn("Corrupted files: 1", result.stdout)
        self.assertIn("💡 Run 'agentmap validate-cache --cleanup'", result.stdout)
        self.assertIn("⚠️  Found 1 corrupted cache files", result.stdout)
    
    def test_clean_cache_no_suggestions(self):
        """Test clean cache shows no suggestions."""
        # Configure clean cache
        clean_cache = {
            "total_files": 5,
            "valid_files": 5,
            "expired_files": 0,
            "corrupted_files": 0
        }
        self.mock_validation_cache_service.get_validation_cache_stats.return_value = clean_cache
        
        result = self.run_command(["validate-cache"])
        
        self.assert_success(result)
        self.assertIn("Expired files: 0", result.stdout)
        self.assertIn("Corrupted files: 0", result.stdout)
        # Should not contain suggestions
        self.assertNotIn("💡", result.stdout)
        self.assertNotIn("⚠️", result.stdout)


class TestDiagnosticCommandsIntegration(SimpleCLITestBase):
    """Test integration scenarios for diagnostic commands."""
    
    def test_full_diagnostic_workflow(self):
        """Test running all diagnostic commands in sequence."""
        # Test diagnose
        diagnose_result = self.run_command(["diagnose"])
        self.assert_success(diagnose_result)
        
        # Test config
        config_result = self.run_command(["config"])
        self.assert_success(config_result)
        
        # Test cache stats
        cache_result = self.run_command(["validate-cache"])
        self.assert_success(cache_result)
        
        # Verify all services were called
        self.mock_dependency_checker.check_llm_dependencies.assert_called()
        self.mock_app_config_service.get_all.assert_called()
        self.mock_validation_cache_service.get_validation_cache_stats.assert_called()
    
    def test_cache_maintenance_sequence(self):
        """Test sequence of cache maintenance operations."""
        # Check stats
        stats_result = self.run_command(["validate-cache", "--stats"])
        self.assert_success(stats_result)
        
        # Clean up expired
        cleanup_result = self.run_command(["validate-cache", "--cleanup"])
        self.assert_success(cleanup_result)
        
        # Clear all
        clear_result = self.run_command(["validate-cache", "--clear"])
        self.assert_success(clear_result)
        
        # Verify operations were called
        self.mock_validation_cache_service.get_validation_cache_stats.assert_called()
        self.mock_validation_cache_service.cleanup_validation_cache.assert_called()
        self.mock_validation_cache_service.clear_validation_cache.assert_called()


if __name__ == '__main__':
    unittest.main()
