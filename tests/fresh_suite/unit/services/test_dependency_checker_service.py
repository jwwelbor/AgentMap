"""
Unit tests for DependencyCheckerService.

These tests validate the DependencyCheckerService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Optional
import sys

from agentmap.services.dependency_checker_service import DependencyCheckerService
from tests.utils.mock_service_factory import MockServiceFactory


class TestDependencyCheckerService(unittest.TestCase):
    """Unit tests for DependencyCheckerService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_features_registry_service = Mock()
        
        # Initialize DependencyCheckerService with mocked dependencies
        self.service = DependencyCheckerService(
            logging_service=self.mock_logging_service,
            features_registry_service=self.mock_features_registry_service
        )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
        
        # Reset mock call counts
        self.mock_features_registry_service.reset_mock()
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.features_registry, self.mock_features_registry_service)
        self.assertIsNotNone(self.service.logger)
        
        # Verify class logger was requested
        self.mock_logging_service.get_class_logger.assert_called_once()
                
    # =============================================================================
    # 2. Single Dependency Check Tests
    # =============================================================================
    
    @patch('agentmap.services.dependency_checker_service.importlib')
    def test_check_dependency_success(self, mock_importlib):
        """Test check_dependency() returns True for available packages."""
        # Configure successful import
        mock_importlib.import_module.return_value = MagicMock()
        
        # Execute test
        result = self.service.check_dependency("test_package")
        
        # Verify result
        self.assertTrue(result)
        mock_importlib.import_module.assert_called_once_with("test_package")
    
    @patch('agentmap.services.dependency_checker_service.importlib')
    def test_check_dependency_not_found(self, mock_importlib):
        """Test check_dependency() returns False for missing packages."""
        # Configure import failure
        mock_importlib.import_module.side_effect = ImportError("No module named 'missing_package'")
        
        # Execute test
        result = self.service.check_dependency("missing_package")
        
        # Verify result
        self.assertFalse(result)
        mock_importlib.import_module.assert_called_once_with("missing_package")
    
    @patch('agentmap.services.dependency_checker_service.importlib')
    def test_check_dependency_with_version(self, mock_importlib):
        """Test check_dependency() handles version requirements."""
        # Mock package with version
        mock_module = MagicMock()
        mock_module.__version__ = "2.0.0"
        mock_importlib.import_module.return_value = mock_module
        
        with patch('packaging.version.parse') as mock_version_parse:
            # Configure version parsing - 2.0.0 >= 1.5.0 should return True
            mock_parsed_current = MagicMock()
            mock_parsed_required = MagicMock() 
            mock_parsed_current.__lt__ = MagicMock(return_value=False)  # 2.0.0 is not < 1.5.0
            
            mock_version_parse.side_effect = lambda v: mock_parsed_current if v == "2.0.0" else mock_parsed_required
            
            # Execute test with version requirement
            result = self.service.check_dependency("test_package>=1.5.0")
            
            # Verify result
            self.assertTrue(result)
            mock_importlib.import_module.assert_called_with("test_package")
    
    @patch('agentmap.services.dependency_checker_service.importlib')
    def test_check_dependency_dotted_package(self, mock_importlib):
        """Test check_dependency() handles dotted package names correctly."""
        # Configure successful imports for dotted package
        mock_importlib.import_module.return_value = MagicMock()
        
        # Execute test
        result = self.service.check_dependency("google.generativeai")
        
        # Verify both imports were attempted
        self.assertTrue(result)
        self.assertEqual(mock_importlib.import_module.call_count, 2)
        mock_importlib.import_module.assert_any_call("google")
        mock_importlib.import_module.assert_any_call("google.generativeai")
    
    # =============================================================================
    # 3. Import Validation Tests
    # =============================================================================
    
    def test_validate_imports_all_valid(self):
        """Test validate_imports() with all valid modules."""
        with patch.object(self.service, 'check_dependency', return_value=True):
            # Execute test
            success, invalid = self.service.validate_imports(["module1", "module2", "module3"])
            
            # Verify result
            self.assertTrue(success)
            self.assertEqual(invalid, [])
    
    def test_validate_imports_some_invalid(self):
        """Test validate_imports() with mixed valid/invalid modules."""
        def mock_check_dependency(module_name):
            return module_name != "missing_module"
        
        with patch.object(self.service, 'check_dependency', side_effect=mock_check_dependency):
            # Execute test
            success, invalid = self.service.validate_imports(["valid_module", "missing_module", "another_valid"])
            
            # Verify result
            self.assertFalse(success)
            self.assertEqual(invalid, ["missing_module"])
    
    def test_validate_imports_with_versions(self):
        """Test validate_imports() handles version requirements."""
        modules = ["package>=1.0.0", "another_package>=2.0.0"]
        
        with patch.object(self.service, 'check_dependency', return_value=True):
            # Execute test
            success, invalid = self.service.validate_imports(modules)
            
            # Verify result
            self.assertTrue(success)
            self.assertEqual(invalid, [])
    
    def test_validate_imports_already_imported(self):
        """Test validate_imports() handles already imported modules."""
        # Mock sys.modules
        with patch.dict(sys.modules, {"already_imported": MagicMock()}):
            # Mock check_dependency to return True for new modules
            with patch.object(self.service, 'check_dependency', return_value=True):
                # Execute test
                success, invalid = self.service.validate_imports(["already_imported", "new_module"])
                
                # Should succeed since already_imported is in sys.modules and new_module passes check_dependency
                self.assertTrue(success)
                self.assertEqual(invalid, [])
    
    # =============================================================================
    # 4. LLM Dependencies Tests
    # =============================================================================
    
    def test_check_llm_dependencies_feature_disabled(self):
        """Test check_llm_dependencies() when LLM feature is disabled."""
        # Configure feature as disabled
        self.mock_features_registry_service.is_feature_enabled.return_value = False
        
        # Execute test
        result, missing = self.service.check_llm_dependencies()
        
        # Verify result
        self.assertFalse(result)
        self.assertEqual(missing, ["llm feature not enabled"])
        self.mock_features_registry_service.is_feature_enabled.assert_called_once_with("llm")
    
    def test_check_llm_dependencies_specific_provider_success(self):
        """Test check_llm_dependencies() for specific provider success."""
        # Configure feature as enabled
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        
        with patch.object(self.service, '_validate_llm_provider', return_value=(True, [])):
            # Execute test
            result, missing = self.service.check_llm_dependencies(provider="openai")
            
            # Verify result
            self.assertTrue(result)
            self.assertEqual(missing, [])
            
            # Verify registry updates
            self.mock_features_registry_service.set_provider_validated.assert_called_once_with("llm", "openai", True)
    
    def test_check_llm_dependencies_specific_provider_failure(self):
        """Test check_llm_dependencies() for specific provider failure."""
        # Configure feature as enabled
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        
        missing_deps = ["langchain_openai"]
        with patch.object(self.service, '_validate_llm_provider', return_value=(False, missing_deps)):
            # Execute test
            result, missing = self.service.check_llm_dependencies(provider="openai")
            
            # Verify result
            self.assertFalse(result)
            self.assertEqual(missing, missing_deps)
            
            # Verify registry updates
            self.mock_features_registry_service.set_provider_validated.assert_called_once_with("llm", "openai", False)
            self.mock_features_registry_service.record_missing_dependencies.assert_called_once_with("llm.openai", missing_deps)
    
    def test_check_llm_dependencies_any_provider_available(self):
        """Test check_llm_dependencies() when at least one provider is available."""
        # Configure feature as enabled
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        
        def mock_validate_provider(provider, force=False):
            # Only anthropic is available
            return (True, []) if provider == "anthropic" else (False, [f"missing_{provider}"])
        
        with patch.object(self.service, '_validate_llm_provider', side_effect=mock_validate_provider):
            # Execute test
            result, missing = self.service.check_llm_dependencies()
            
            # Verify result - should succeed since anthropic is available
            self.assertTrue(result)
            self.assertEqual(missing, [])
    
    def test_check_llm_dependencies_no_providers_available(self):
        """Test check_llm_dependencies() when no providers are available."""
        # Configure feature as enabled
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        
        def mock_validate_provider(provider, force=False):
            return (False, [f"missing_{provider}"])
        
        with patch.object(self.service, '_validate_llm_provider', side_effect=mock_validate_provider):
            # Execute test
            result, missing = self.service.check_llm_dependencies()
            
            # Verify result - should fail since no providers available
            self.assertFalse(result)
            self.assertTrue(len(missing) > 0)
    
    # =============================================================================
    # 5. Storage Dependencies Tests
    # =============================================================================
    
    def test_check_storage_dependencies_feature_disabled(self):
        """Test check_storage_dependencies() when storage feature is disabled."""
        # Configure feature as disabled
        self.mock_features_registry_service.is_feature_enabled.return_value = False
        
        # Execute test
        result, missing = self.service.check_storage_dependencies()
        
        # Verify result
        self.assertFalse(result)
        self.assertEqual(missing, ["storage feature not enabled"])
        self.mock_features_registry_service.is_feature_enabled.assert_called_once_with("storage")
    
    def test_check_storage_dependencies_specific_type_success(self):
        """Test check_storage_dependencies() for specific storage type success."""
        # Configure feature as enabled
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        
        with patch.object(self.service, '_validate_storage_type', return_value=(True, [])):
            # Execute test
            result, missing = self.service.check_storage_dependencies(storage_type="csv")
            
            # Verify result
            self.assertTrue(result)
            self.assertEqual(missing, [])
            
            # Verify registry updates
            self.mock_features_registry_service.set_provider_validated.assert_called_once_with("storage", "csv", True)
    
    def test_check_storage_dependencies_core_csv_check(self):
        """Test check_storage_dependencies() checks core CSV dependencies by default."""
        # Configure feature as enabled
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        
        with patch.object(self.service, '_validate_storage_type', return_value=(True, [])) as mock_validate:
            # Execute test without specific storage type
            result, missing = self.service.check_storage_dependencies()
            
            # Verify CSV validation was called
            mock_validate.assert_called_once_with("csv")
            self.assertTrue(result)
    
    # =============================================================================
    # 6. Provider Availability Tests
    # =============================================================================
    
    def test_can_use_provider_feature_disabled(self):
        """Test can_use_provider() when feature is disabled."""
        # Configure feature as disabled
        self.mock_features_registry_service.is_feature_enabled.return_value = False
        
        # Execute test
        result = self.service.can_use_provider("llm", "openai")
        
        # Verify result
        self.assertFalse(result)
        self.mock_features_registry_service.is_feature_enabled.assert_called_once_with("llm")
    
    def test_can_use_provider_enabled_and_validated(self):
        """Test can_use_provider() when feature is enabled and provider is validated."""
        # Configure feature as enabled and provider as validated
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        self.mock_features_registry_service.is_provider_validated.return_value = True
        
        # Execute test
        result = self.service.can_use_provider("llm", "openai")
        
        # Verify result
        self.assertTrue(result)
        self.mock_features_registry_service.is_feature_enabled.assert_called_once_with("llm")
        self.mock_features_registry_service.is_provider_validated.assert_called_once_with("llm", "openai")
    
    def test_can_use_provider_enabled_but_not_validated(self):
        """Test can_use_provider() when feature is enabled but provider is not validated."""
        # Configure feature as enabled but provider as not validated
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        self.mock_features_registry_service.is_provider_validated.return_value = False
        
        # Execute test
        result = self.service.can_use_provider("llm", "openai")
        
        # Verify result
        self.assertFalse(result)
    
    # =============================================================================
    # 7. Provider Discovery Tests
    # =============================================================================
    
    def test_discover_and_validate_providers_llm(self):
        """Test discover_and_validate_providers() for LLM category."""
        def mock_validate_provider(provider, force=False):
            # Only openai and anthropic are available
            return (True, []) if provider in ["openai", "anthropic"] else (False, [f"missing_{provider}"])
        
        with patch.object(self.service, '_validate_llm_provider', side_effect=mock_validate_provider):
            # Execute test
            results = self.service.discover_and_validate_providers("llm")
            
            # Verify results
            self.assertIn("openai", results)
            self.assertIn("anthropic", results)
            self.assertIn("google", results)
            self.assertTrue(results["openai"])
            self.assertTrue(results["anthropic"])
            self.assertFalse(results["google"])
            
            # Verify registry updates were called
            self.assertEqual(self.mock_features_registry_service.set_provider_validated.call_count, 3)
    
    def test_discover_and_validate_providers_storage(self):
        """Test discover_and_validate_providers() for storage category."""
        def mock_validate_storage(storage_type, force=False):
            # Only csv and vector are available
            return (True, []) if storage_type in ["csv", "vector"] else (False, [f"missing_{storage_type}"])
        
        with patch.object(self.service, '_validate_storage_type', side_effect=mock_validate_storage):
            # Execute test
            results = self.service.discover_and_validate_providers("storage")
            
            # Verify results
            self.assertIn("csv", results)
            self.assertIn("vector", results)
            self.assertTrue(results["csv"])
            self.assertTrue(results["vector"])
            
            # Verify registry updates were called for all storage types
            self.assertTrue(self.mock_features_registry_service.set_provider_validated.call_count >= 2)
    
    def test_discover_and_validate_providers_unknown_category(self):
        """Test discover_and_validate_providers() with unknown category."""
        # Execute test
        results = self.service.discover_and_validate_providers("unknown")
        
        # Should return empty results for unknown category
        self.assertEqual(results, {})
    
    # =============================================================================
    # 8. Provider Validation Internal Methods Tests
    # =============================================================================
    
    def test_validate_llm_provider_known_provider(self):
        """Test _validate_llm_provider() with known provider."""
        with patch.object(self.service, 'validate_imports', return_value=(True, [])):
            # Execute test
            result, missing = self.service._validate_llm_provider("openai")
            
            # Verify result
            self.assertTrue(result)
            self.assertEqual(missing, [])
    
    def test_validate_llm_provider_unknown_provider(self):
        """Test _validate_llm_provider() with unknown provider."""
        # Execute test
        result, missing = self.service._validate_llm_provider("unknown_provider")
        
        # Verify result
        self.assertFalse(result)
        self.assertEqual(missing, ["unknown-provider:unknown_provider"])
    
    def test_validate_storage_type_known_type(self):
        """Test _validate_storage_type() with known storage type."""
        with patch.object(self.service, 'validate_imports', return_value=(True, [])):
            # Execute test
            result, missing = self.service._validate_storage_type("csv")
            
            # Verify result
            self.assertTrue(result)
            self.assertEqual(missing, [])
    
    def test_validate_storage_type_unknown_type(self):
        """Test _validate_storage_type() with unknown storage type."""
        # Execute test
        result, missing = self.service._validate_storage_type("unknown_storage")
        
        # Verify result
        self.assertFalse(result)
        self.assertEqual(missing, ["unknown-storage:unknown_storage"])
    
    # =============================================================================
    # 9. Installation Guide Tests
    # =============================================================================
    
    def test_get_installation_guide_llm_providers(self):
        """Test get_installation_guide() for LLM providers."""
        # Test OpenAI
        guide = self.service.get_installation_guide("openai", "llm")
        self.assertIn("openai", guide.lower())
        self.assertIn("pip install", guide)
        
        # Test Anthropic
        guide = self.service.get_installation_guide("anthropic", "llm")
        self.assertIn("anthropic", guide.lower())
        
        # Test Google
        guide = self.service.get_installation_guide("google", "llm")
        self.assertIn("google", guide.lower())
    
    def test_get_installation_guide_storage_types(self):
        """Test get_installation_guide() for storage types."""
        # Test CSV
        guide = self.service.get_installation_guide("csv", "storage")
        self.assertIn("pandas", guide.lower())
        
        # Test Vector
        guide = self.service.get_installation_guide("vector", "storage")
        self.assertIn("vector", guide.lower())
    
    def test_get_installation_guide_unknown_category(self):
        """Test get_installation_guide() for unknown category."""
        guide = self.service.get_installation_guide("provider", "unknown")
        self.assertIn("pip install", guide)
        self.assertIn("provider", guide)
    
    # =============================================================================
    # 10. Available Providers Tests
    # =============================================================================
    
    def test_get_available_llm_providers_feature_disabled(self):
        """Test get_available_llm_providers() when feature is disabled."""
        # Configure feature as disabled
        self.mock_features_registry_service.is_feature_enabled.return_value = False
        
        # Execute test
        providers = self.service.get_available_llm_providers()
        
        # Verify result
        self.assertEqual(providers, [])
    
    def test_get_available_llm_providers_with_available_providers(self):
        """Test get_available_llm_providers() with some available providers."""
        # Configure feature as enabled
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        
        def mock_is_provider_available(category, provider):
            # Only openai and anthropic are available
            return provider in ["openai", "anthropic"]
        
        self.mock_features_registry_service.is_provider_available.side_effect = mock_is_provider_available
        
        # Execute test
        providers = self.service.get_available_llm_providers()
        
        # Verify result
        self.assertIn("openai", providers)
        self.assertIn("anthropic", providers)
        self.assertNotIn("google", providers)
    
    def test_get_available_storage_types_feature_enabled(self):
        """Test get_available_storage_types() when feature is enabled."""
        # Configure feature as enabled
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        
        def mock_is_provider_available(category, storage_type):
            # Only csv and vector are available
            return storage_type in ["csv", "vector"]
        
        self.mock_features_registry_service.is_provider_available.side_effect = mock_is_provider_available
        
        # Execute test
        storage_types = self.service.get_available_storage_types()
        
        # Verify result
        self.assertIn("csv", storage_types)
        self.assertIn("vector", storage_types)
    
    # =============================================================================
    # 11. Status Summary Tests
    # =============================================================================
    
    def test_get_dependency_status_summary(self):
        """Test get_dependency_status_summary() returns comprehensive status."""
        # Configure mock returns
        self.mock_features_registry_service.is_feature_enabled.side_effect = lambda feature: feature in ["llm", "storage"]
        self.mock_features_registry_service.get_missing_dependencies.return_value = []
        
        with patch.object(self.service, 'get_available_llm_providers', return_value=["openai"]), \
             patch.object(self.service, 'get_available_storage_types', return_value=["csv"]):
            
            # Execute test
            summary = self.service.get_dependency_status_summary()
            
            # Verify structure
            self.assertIn("llm", summary)
            self.assertIn("storage", summary)
            self.assertIn("coordination", summary)
            
            # Verify LLM section
            self.assertTrue(summary["llm"]["feature_enabled"])
            self.assertEqual(summary["llm"]["available_providers"], ["openai"])
            
            # Verify storage section
            self.assertTrue(summary["storage"]["feature_enabled"])
            self.assertEqual(summary["storage"]["available_types"], ["csv"])
            
            # Verify coordination section
            self.assertTrue(summary["coordination"]["features_registry_available"])
            self.assertTrue(summary["coordination"]["automatic_validation_updates"])
    
    # =============================================================================
    # 12. Error Handling and Edge Cases Tests
    # =============================================================================
    
    def test_check_dependency_exception_handling(self):
        """Test check_dependency() handles import-related exceptions gracefully."""
        with patch('agentmap.services.dependency_checker_service.importlib') as mock_importlib:
            # Configure import-related exception (which should be caught)
            mock_importlib.import_module.side_effect = ImportError("Import failed")
            
            # Execute test
            result = self.service.check_dependency("problematic_package")
            
            # Should return False for import exceptions
            self.assertFalse(result)
    
    def test_validate_imports_exception_handling(self):
        """Test validate_imports() handles exceptions during import checking."""
        def problematic_check_dependency(module_name):
            if module_name == "problem_module":
                raise Exception("Check failed")
            return True
        
        with patch.object(self.service, 'check_dependency', side_effect=problematic_check_dependency):
            # Execute test
            success, invalid = self.service.validate_imports(["good_module", "problem_module"])
            
            # Should handle the exception gracefully
            self.assertFalse(success)
            self.assertIn("problem_module", invalid)
    
    def test_features_registry_integration_error_handling(self):
        """Test error handling when features registry operations fail."""
        # Configure feature as enabled
        self.mock_features_registry_service.is_feature_enabled.return_value = True
        
        # Configure registry method to raise exception
        self.mock_features_registry_service.set_provider_validated.side_effect = Exception("Registry error")
        
        with patch.object(self.service, '_validate_llm_provider', return_value=(True, [])):
            # Execute test - should raise the registry exception since it's not caught
            with self.assertRaises(Exception) as context:
                result, missing = self.service.check_llm_dependencies(provider="openai")
            
            # Verify the exception message
            self.assertEqual(str(context.exception), "Registry error")
    
    def test_circular_dependency_patterns(self):
        """Test handling of potential circular dependency patterns."""
        # This tests the service's ability to handle complex dependency scenarios
        # without getting into infinite loops or other problematic states
        
        with patch.object(self.service, 'validate_imports') as mock_validate:
            # Configure complex dependency scenario
            mock_validate.return_value = (True, [])
            
            # Test multiple providers simultaneously
            self.mock_features_registry_service.is_feature_enabled.return_value = True
            
            # Execute discovery for multiple categories
            llm_results = self.service.discover_and_validate_providers("llm")
            storage_results = self.service.discover_and_validate_providers("storage")
            
            # Should complete without issues
            self.assertIsInstance(llm_results, dict)
            self.assertIsInstance(storage_results, dict)


if __name__ == '__main__':
    unittest.main()
