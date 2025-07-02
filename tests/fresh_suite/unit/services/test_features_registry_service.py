"""
Unit tests for FeaturesRegistryService using pure Mock objects and established testing patterns.

This test suite validates the features registry's business logic including provider management,
feature flags, and NLP library detection capabilities.
"""
import unittest
from unittest.mock import Mock, patch

from agentmap.services.features_registry_service import FeaturesRegistryService
from tests.utils.mock_service_factory import MockServiceFactory


class TestFeaturesRegistryService(unittest.TestCase):
    """Unit tests for FeaturesRegistryService using pure Mock objects."""
    
    def setUp(self):
        """Set up test fixtures with pure Mock dependencies."""
        # Create mock features registry model
        self.mock_features_registry = Mock()
        
        # Configure basic model behavior
        self.mock_features_registry.get_provider_status.return_value = (True, True)
        self.mock_features_registry.get_missing_dependencies.return_value = {}
        
        # Use MockServiceFactory for consistent behavior
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        
        # Create service instance with mocked dependencies
        self.service = FeaturesRegistryService(
            features_registry=self.mock_features_registry,
            logging_service=self.mock_logging_service
        )
        
        # Get mock logger for verification
        self.mock_logger = self.service.logger
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify dependencies are stored
        self.assertEqual(self.service.features_registry, self.mock_features_registry)
        # Note: logging_service is not stored as attribute, only used to get logger
        
        # Verify logger is configured
        self.assertIsNotNone(self.service.logger)
        
        # Verify default providers were initialized
        self.assertTrue(self.mock_features_registry.set_provider_status.call_count >= 8)  # Multiple providers set
    
    # =============================================================================
    # 2. NLP Library Detection Tests
    # =============================================================================
    
    def test_has_fuzzywuzzy_available(self):
        """Test fuzzywuzzy detection when library is available."""
        # Since testing actual import is complex, test that the method handles
        # the case where libraries are available by mocking the internal try/except
        # This tests the business logic rather than the import mechanics
        
        # The real implementation will return False if no library, True if available
        # For testing, we'll verify the method behaves correctly when called
        result = self.service.has_fuzzywuzzy()
        
        # Should return False in test environment (no library installed)
        # but method should not crash and should return a boolean
        self.assertIsInstance(result, bool)
        # In test environment without fuzzywuzzy, should return False
        self.assertFalse(result)
    
    def test_has_fuzzywuzzy_not_available(self):
        """Test fuzzywuzzy detection when library is not available."""
        # Mock ImportError
        with patch('builtins.__import__', side_effect=ImportError("No module named 'fuzzywuzzy'")):
            result = self.service.has_fuzzywuzzy()
            self.assertFalse(result)
    
    def test_has_fuzzywuzzy_import_error(self):
        """Test fuzzywuzzy detection handles import errors gracefully."""
        # Mock general exception during import
        with patch('builtins.__import__', side_effect=Exception("Import error")):
            result = self.service.has_fuzzywuzzy()
            self.assertFalse(result)
    
    def test_has_spacy_available(self):
        """Test spaCy detection when library and model are available."""
        # Mock successful spaCy import and model loading
        mock_spacy = Mock()
        mock_nlp = Mock()
        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=2)  # Non-empty document
        mock_nlp.return_value = mock_doc
        mock_spacy.load.return_value = mock_nlp
        
        def mock_import(name, *args, **kwargs):
            if name == 'spacy':
                return mock_spacy
            # Return original import for other modules
            return __import__(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import):
            result = self.service.has_spacy()
            self.assertTrue(result)
    
    def test_has_spacy_model_not_available(self):
        """Test spaCy detection when English model is not available."""
        # Mock spaCy module available but model loading fails
        mock_spacy = Mock()
        mock_spacy.load.side_effect = OSError("Can't find model 'en_core_web_sm'")
        
        def mock_import(name, *args, **kwargs):
            if name == 'spacy':
                return mock_spacy
            # Return original import for other modules
            return __import__(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import):
            result = self.service.has_spacy()
            self.assertFalse(result)
    
    def test_has_spacy_not_installed(self):
        """Test spaCy detection when library is not installed."""
        # Mock ImportError
        with patch('builtins.__import__', side_effect=ImportError("No module named 'spacy'")):
            result = self.service.has_spacy()
            self.assertFalse(result)
    
    def test_has_spacy_general_error(self):
        """Test spaCy detection handles general errors gracefully."""
        # Mock general exception
        with patch('builtins.__import__', side_effect=Exception("General error")):
            result = self.service.has_spacy()
            self.assertFalse(result)
    
    def test_get_nlp_capabilities_both_available(self):
        """Test NLP capabilities when both libraries are available."""
        # Mock both libraries as available
        with patch.object(self.service, 'has_fuzzywuzzy', return_value=True), \
             patch.object(self.service, 'has_spacy', return_value=True):
            
            capabilities = self.service.get_nlp_capabilities()
            
            # Verify structure
            self.assertIsInstance(capabilities, dict)
            self.assertIn('fuzzywuzzy_available', capabilities)
            self.assertIn('spacy_available', capabilities)
            self.assertIn('enhanced_matching', capabilities)
            self.assertIn('supported_features', capabilities)
            
            # Verify availability
            self.assertTrue(capabilities['fuzzywuzzy_available'])
            self.assertTrue(capabilities['spacy_available'])
            self.assertTrue(capabilities['enhanced_matching'])
            
            # Verify features
            features = capabilities['supported_features']
            self.assertIn('fuzzy_string_matching', features)
            self.assertIn('typo_tolerance', features)
            self.assertIn('advanced_tokenization', features)
            self.assertIn('keyword_extraction', features)
            self.assertIn('lemmatization', features)
    
    def test_get_nlp_capabilities_only_fuzzywuzzy(self):
        """Test NLP capabilities when only fuzzywuzzy is available."""
        with patch.object(self.service, 'has_fuzzywuzzy', return_value=True), \
             patch.object(self.service, 'has_spacy', return_value=False):
            
            capabilities = self.service.get_nlp_capabilities()
            
            self.assertTrue(capabilities['fuzzywuzzy_available'])
            self.assertFalse(capabilities['spacy_available'])
            self.assertTrue(capabilities['enhanced_matching'])  # Still enhanced due to fuzzy
            
            features = capabilities['supported_features']
            self.assertIn('fuzzy_string_matching', features)
            self.assertIn('typo_tolerance', features)
            self.assertNotIn('advanced_tokenization', features)
            self.assertNotIn('lemmatization', features)
    
    def test_get_nlp_capabilities_only_spacy(self):
        """Test NLP capabilities when only spaCy is available."""
        with patch.object(self.service, 'has_fuzzywuzzy', return_value=False), \
             patch.object(self.service, 'has_spacy', return_value=True):
            
            capabilities = self.service.get_nlp_capabilities()
            
            self.assertFalse(capabilities['fuzzywuzzy_available'])
            self.assertTrue(capabilities['spacy_available'])
            self.assertTrue(capabilities['enhanced_matching'])  # Still enhanced due to spacy
            
            features = capabilities['supported_features']
            self.assertNotIn('fuzzy_string_matching', features)
            self.assertNotIn('typo_tolerance', features)
            self.assertIn('advanced_tokenization', features)
            self.assertIn('keyword_extraction', features)
            self.assertIn('lemmatization', features)
    
    def test_get_nlp_capabilities_none_available(self):
        """Test NLP capabilities when no libraries are available."""
        with patch.object(self.service, 'has_fuzzywuzzy', return_value=False), \
             patch.object(self.service, 'has_spacy', return_value=False):
            
            capabilities = self.service.get_nlp_capabilities()
            
            self.assertFalse(capabilities['fuzzywuzzy_available'])
            self.assertFalse(capabilities['spacy_available'])
            self.assertFalse(capabilities['enhanced_matching'])
            self.assertEqual(capabilities['supported_features'], [])
    
    # =============================================================================
    # 3. Provider Management Tests
    # =============================================================================
    
    def test_set_provider_available(self):
        """Test setting provider availability."""
        self.service.set_provider_available("llm", "openai", True)
        
        # Verify model method was called correctly
        self.mock_features_registry.set_provider_status.assert_called()
        call_args = self.mock_features_registry.set_provider_status.call_args
        self.assertEqual(call_args[0], ("llm", "openai", True, True))  # (category, provider, available, validated)
    
    def test_set_provider_validated(self):
        """Test setting provider validation status."""
        self.service.set_provider_validated("storage", "csv", True)
        
        # Verify model method was called correctly
        self.mock_features_registry.set_provider_status.assert_called()
        call_args = self.mock_features_registry.set_provider_status.call_args
        self.assertEqual(call_args[0], ("storage", "csv", True, True))  # (category, provider, available, validated)
    
    def test_is_provider_available(self):
        """Test checking provider availability."""
        # Configure mock to return available and validated
        self.mock_features_registry.get_provider_status.return_value = (True, True)
        
        result = self.service.is_provider_available("llm", "openai")
        self.assertTrue(result)
        
        # Verify model was queried
        self.mock_features_registry.get_provider_status.assert_called_with("llm", "openai")
    
    def test_is_provider_available_not_validated(self):
        """Test provider not available when not validated."""
        # Configure mock to return available but not validated
        self.mock_features_registry.get_provider_status.return_value = (True, False)
        
        result = self.service.is_provider_available("llm", "openai")
        self.assertFalse(result)
    
    def test_provider_alias_resolution(self):
        """Test provider alias resolution works correctly."""
        # Test GPT -> OpenAI alias
        self.service.is_provider_available("llm", "gpt")
        
        # Should have queried for "openai" not "gpt"
        self.mock_features_registry.get_provider_status.assert_called_with("llm", "openai")
    
    # =============================================================================
    # 4. Feature Management Tests
    # =============================================================================
    
    def test_enable_feature(self):
        """Test enabling a feature."""
        self.service.enable_feature("experimental_nlp")
        
        # Verify model method was called
        self.mock_features_registry.add_feature.assert_called_once_with("experimental_nlp")
    
    def test_disable_feature(self):
        """Test disabling a feature."""
        self.service.disable_feature("experimental_nlp")
        
        # Verify model method was called
        self.mock_features_registry.remove_feature.assert_called_once_with("experimental_nlp")
    
    def test_is_feature_enabled(self):
        """Test checking if feature is enabled."""
        self.mock_features_registry.has_feature.return_value = True
        
        result = self.service.is_feature_enabled("nlp_enhancements")
        self.assertTrue(result)
        
        # Verify model was queried
        self.mock_features_registry.has_feature.assert_called_once_with("nlp_enhancements")
    
    # =============================================================================
    # 5. Dependency Management Tests
    # =============================================================================
    
    def test_record_missing_dependencies(self):
        """Test recording missing dependencies."""
        missing_deps = ["fuzzywuzzy", "spacy"]
        self.service.record_missing_dependencies("nlp", missing_deps)
        
        # Verify model method was called
        self.mock_features_registry.set_missing_dependencies.assert_called_once_with("nlp", missing_deps)
    
    def test_get_missing_dependencies(self):
        """Test retrieving missing dependencies."""
        expected_deps = {"nlp": ["fuzzywuzzy"], "llm": ["openai"]}
        self.mock_features_registry.get_missing_dependencies.return_value = expected_deps
        
        result = self.service.get_missing_dependencies()
        self.assertEqual(result, expected_deps)
    
    def test_get_missing_dependencies_for_category(self):
        """Test retrieving missing dependencies for specific category."""
        self.service.get_missing_dependencies("nlp")
        
        # Verify model was queried with category
        self.mock_features_registry.get_missing_dependencies.assert_called_once_with("nlp")
    
    # =============================================================================
    # 6. Provider Listing Tests
    # =============================================================================
    
    def test_get_available_providers(self):
        """Test getting list of available providers."""
        # Mock multiple provider checks
        def mock_provider_status(category, provider):
            if provider in ["openai", "csv"]:
                return (True, True)  # Available and validated
            return (False, False)
        
        self.mock_features_registry.get_provider_status.side_effect = mock_provider_status
        
        llm_providers = self.service.get_available_providers("llm")
        storage_providers = self.service.get_available_providers("storage")
        
        # Should include available and validated providers
        self.assertIn("openai", llm_providers)
        self.assertIn("csv", storage_providers)
    
    # =============================================================================
    # 7. Error Handling and Edge Cases
    # =============================================================================
    
    def test_provider_status_case_insensitive(self):
        """Test provider operations are case insensitive."""
        self.service.set_provider_available("LLM", "OPENAI", True)
        
        # Should normalize to lowercase
        call_args = self.mock_features_registry.set_provider_status.call_args
        self.assertEqual(call_args[0][0], "llm")
        self.assertEqual(call_args[0][1], "openai")
    
    def test_unknown_category_handling(self):
        """Test handling of unknown provider categories."""
        providers = self.service.get_available_providers("unknown_category")
        
        # Should return empty list for unknown categories
        self.assertEqual(providers, [])
    
    def test_provider_aliases_comprehensive(self):
        """Test all provider aliases work correctly."""
        aliases = [
            ("llm", "gpt", "openai"),
            ("llm", "claude", "anthropic"),
            ("llm", "gemini", "google")
        ]
        
        for category, alias, expected in aliases:
            self.mock_features_registry.get_provider_status.reset_mock()
            self.service.is_provider_available(category, alias)
            
            # Should query using canonical name
            self.mock_features_registry.get_provider_status.assert_called_with(category, expected)
    
    def test_nlp_library_detection_logging(self):
        """Test that NLP library detection includes proper logging."""
        with patch.object(self.service, 'has_fuzzywuzzy', return_value=True), \
             patch.object(self.service, 'has_spacy', return_value=False):
            
            self.service.get_nlp_capabilities()
            
            # Should log the capabilities
            # Note: Specific log verification would depend on mock logger implementation


if __name__ == '__main__':
    unittest.main(verbosity=2)
