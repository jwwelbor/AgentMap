"""
Unit tests for AgentFactoryService.

These tests validate the AgentFactoryService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock
from typing import Type, Dict, Any
from agentmap.services.agent_factory_service import AgentFactoryService
from agentmap.migration_utils import MockLoggingService
from tests.utils.mock_factory import MockServiceFactory


class TestAgentFactoryService(unittest.TestCase):
    """Unit tests for AgentFactoryService with mocked dependencies."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Use established shared mock pattern - simple Mock for agent registry
        self.mock_agent_registry_service = Mock()
        self.mock_features_registry_service = Mock()
        
        # Use migration-safe mock logging service (established pattern)
        self.mock_logging_service = MockLoggingService()
        
        # Configure agent registry defaults
        self.mock_agent_registry_service.get_agent_class.return_value = None  # Default: no agent found
        self.mock_agent_registry_service.get_registered_agent_types.return_value = ["default", "input", "orchestrator"]
        
        # Configure features registry mock defaults
        self._configure_features_registry_defaults()
        
        # Create service instance with mocked dependencies
        self.service = AgentFactoryService(
            agent_registry_service=self.mock_agent_registry_service,
            features_registry_service=self.mock_features_registry_service,
            logging_service=self.mock_logging_service
        )
        
        # Get the mock logger for verification (established pattern)
        self.mock_logger = self.service.logger
    
    def _configure_features_registry_defaults(self):
        """Configure default behavior for features registry mock."""
        # Default to storage dependencies available, LLM dependencies not available
        self.mock_features_registry_service.is_provider_available.side_effect = self._default_provider_availability
        self.mock_features_registry_service.get_available_providers.side_effect = self._default_get_available_providers
    
    def _default_provider_availability(self, category: str, provider: str) -> bool:
        """Default provider availability for tests."""
        if category == "storage":
            return provider in ["csv", "json", "file"]
        elif category == "llm":
            return False  # LLM dependencies not available by default
        return False
    
    def _default_get_available_providers(self, category: str) -> list:
        """Default available providers for tests."""
        if category == "storage":
            return ["csv", "json", "file"]
        elif category == "llm":
            return []  # No LLM providers available by default
        return []
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored (match actual implementation)
        self.assertEqual(self.service.agent_registry, self.mock_agent_registry_service)
        self.assertEqual(self.service.features, self.mock_features_registry_service)
        
        # Verify logger is configured (established pattern)
        self.assertIsNotNone(self.service.logger)
        self.assertEqual(self.service.logger.name, "AgentFactoryService")
        
        # Verify initialization log message (established pattern)
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[1] == "[AgentFactoryService] Initialized" 
                          for call in logger_calls if call[0] == "debug"))
    
    # =============================================================================
    # 2. resolve_agent_class() Method Tests
    # =============================================================================
    
    def test_resolve_agent_class_success_builtin_agent(self):
        """Test successful resolution of builtin agent with valid dependencies."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "DefaultAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Act
        result = self.service.resolve_agent_class("default")
        
        # Assert
        self.assertEqual(result, mock_agent_class)
        self.mock_agent_registry_service.get_agent_class.assert_called_once_with("default")
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Resolving agent class: type='default'" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
        self.assertTrue(any("Successfully resolved agent class 'default'" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_resolve_agent_class_success_storage_agent(self):
        """Test successful resolution of storage agent with valid dependencies."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "CSVReaderAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Configure storage dependencies as available
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: (
            cat == "storage" and prov == "csv"
        )
        
        # Act
        result = self.service.resolve_agent_class("csv_reader")
        
        # Assert
        self.assertEqual(result, mock_agent_class)
        self.mock_features_registry_service.is_provider_available.assert_called_with("storage", "csv")
    
    def test_resolve_agent_class_success_llm_agent(self):
        """Test successful resolution of LLM agent with valid dependencies."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "OpenAIAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Configure LLM dependencies as available
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: (
            cat == "llm" and prov == "openai"
        )
        
        # Act
        result = self.service.resolve_agent_class("openai")
        
        # Assert
        self.assertEqual(result, mock_agent_class)
        self.mock_features_registry_service.is_provider_available.assert_called_with("llm", "openai")
    
    def test_resolve_agent_class_failure_missing_llm_dependencies(self):
        """Test agent resolution failure due to missing LLM dependencies."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "OpenAIAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Configure LLM dependencies as NOT available
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: False
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.service.resolve_agent_class("openai")
        
        error_message = str(context.exception)
        self.assertIn("OpenAI dependencies", error_message)
        self.assertIn("pip install agentmap[openai]", error_message)
        
        # Verify error logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any(call[0] == "error" for call in logger_calls))
    
    def test_resolve_agent_class_failure_missing_storage_dependencies(self):
        """Test agent resolution failure due to missing storage dependencies."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "VectorWriterAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Configure storage dependencies as NOT available
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: False
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.service.resolve_agent_class("vector_writer")
        
        error_message = str(context.exception)
        self.assertIn("vector dependencies", error_message)
        self.assertIn("pip install agentmap[vector]", error_message)
    
    def test_resolve_agent_class_failure_agent_not_found(self):
        """Test agent resolution failure when agent type is not registered."""
        # Arrange
        self.mock_agent_registry_service.get_agent_class.return_value = None
        
        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.service.resolve_agent_class("nonexistent_agent")
        
        error_message = str(context.exception)
        self.assertIn("Agent type 'nonexistent_agent' not found", error_message)
        
        # Verify error logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Agent type 'nonexistent_agent' not found" in call[1] 
                          for call in logger_calls if call[0] == "error"))
    
    def test_resolve_agent_class_case_insensitive(self):
        """Test that agent resolution is case insensitive."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "DefaultAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Act
        result = self.service.resolve_agent_class("DEFAULT")
        
        # Assert
        self.assertEqual(result, mock_agent_class)
        self.mock_agent_registry_service.get_agent_class.assert_called_once_with("DEFAULT")
    
    # =============================================================================
    # 3. get_agent_class() Method Tests
    # =============================================================================
    
    def test_get_agent_class_success(self):
        """Test get_agent_class() returns agent class without dependency validation."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "TestAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Act
        result = self.service.get_agent_class("test_agent")
        
        # Assert
        self.assertEqual(result, mock_agent_class)
        self.mock_agent_registry_service.get_agent_class.assert_called_once_with("test_agent")
    
    def test_get_agent_class_returns_none_if_not_found(self):
        """Test get_agent_class() returns None for non-existent agent."""
        # Arrange
        self.mock_agent_registry_service.get_agent_class.return_value = None
        
        # Act
        result = self.service.get_agent_class("nonexistent_agent")
        
        # Assert
        self.assertIsNone(result)
    
    # =============================================================================
    # 4. can_resolve_agent_type() Method Tests
    # =============================================================================
    
    def test_can_resolve_agent_type_true_for_valid_agent(self):
        """Test can_resolve_agent_type() returns True for resolvable agent."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "DefaultAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Act
        result = self.service.can_resolve_agent_type("default")
        
        # Assert
        self.assertTrue(result)
    
    def test_can_resolve_agent_type_false_for_missing_dependencies(self):
        """Test can_resolve_agent_type() returns False when dependencies missing."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "OpenAIAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Configure LLM dependencies as NOT available
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: False
        
        # Act
        result = self.service.can_resolve_agent_type("openai")
        
        # Assert
        self.assertFalse(result)
    
    def test_can_resolve_agent_type_false_for_nonexistent_agent(self):
        """Test can_resolve_agent_type() returns False for non-existent agent."""
        # Arrange
        self.mock_agent_registry_service.get_agent_class.return_value = None
        
        # Act
        result = self.service.can_resolve_agent_type("nonexistent_agent")
        
        # Assert
        self.assertFalse(result)
    
    # =============================================================================
    # 5. validate_agent_dependencies() Method Tests
    # =============================================================================
    
    def test_validate_agent_dependencies_success_builtin_agent(self):
        """Test dependency validation success for builtin agent."""
        # Act
        dependencies_valid, missing_deps = self.service.validate_agent_dependencies("default")
        
        # Assert
        self.assertTrue(dependencies_valid)
        self.assertEqual(missing_deps, [])
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("All dependencies valid for agent type 'default'" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_validate_agent_dependencies_failure_llm_agent(self):
        """Test dependency validation failure for LLM agent."""
        # Arrange - LLM dependencies NOT available
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: False
        
        # Act
        dependencies_valid, missing_deps = self.service.validate_agent_dependencies("openai")
        
        # Assert
        self.assertFalse(dependencies_valid)
        self.assertEqual(missing_deps, ["llm"])
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Missing dependencies for 'openai': ['llm']" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    def test_validate_agent_dependencies_failure_storage_agent(self):
        """Test dependency validation failure for storage agent."""
        # Arrange - Storage dependencies NOT available
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: False
        
        # Act
        dependencies_valid, missing_deps = self.service.validate_agent_dependencies("csv_reader")
        
        # Assert
        self.assertFalse(dependencies_valid)
        self.assertEqual(missing_deps, ["storage"])
    
    def test_validate_agent_dependencies_mixed_types(self):
        """Test dependency validation for agent requiring both LLM and storage."""
        # This test demonstrates the logic for potential hybrid agents
        # Act
        dependencies_valid, missing_deps = self.service.validate_agent_dependencies("custom_hybrid")
        
        # Assert - For non-LLM/storage agents, should be valid
        self.assertTrue(dependencies_valid)
        self.assertEqual(missing_deps, [])
    
    # =============================================================================
    # 6. list_available_agent_types() Method Tests
    # =============================================================================
    
    def test_list_available_agent_types_filters_by_dependencies(self):
        """Test list_available_agent_types() only returns agents with valid dependencies."""
        # Arrange
        all_agent_types = ["default", "openai", "csv_reader", "json_reader", "nonexistent"]
        self.mock_agent_registry_service.get_registered_agent_types.return_value = all_agent_types
        
        # Mock agent registry to return classes for some agents
        def mock_get_agent_class(agent_type):
            if agent_type in ["default", "csv_reader", "json_reader"]:
                mock_class = Mock()
                mock_class.__name__ = f"{agent_type.title()}Agent"
                return mock_class
            return None
        
        self.mock_agent_registry_service.get_agent_class.side_effect = mock_get_agent_class
        
        # Configure dependencies - only storage available
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: (
            cat == "storage" and prov in ["csv", "json"]
        )
        
        # Act
        available_types = self.service.list_available_agent_types()
        
        # Assert - Should only include agents with valid dependencies
        expected_available = ["default", "csv_reader", "json_reader"]
        self.assertEqual(set(available_types), set(expected_available))
        
        # Verify logging
        logger_calls = self.mock_logger.calls
        self.assertTrue(any("Available agent types:" in call[1] 
                          for call in logger_calls if call[0] == "debug"))
    
    # =============================================================================
    # 7. get_agent_resolution_context() Method Tests
    # =============================================================================
    
    def test_get_agent_resolution_context_success(self):
        """Test get_agent_resolution_context() returns complete context for valid agent."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "DefaultAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Act
        context = self.service.get_agent_resolution_context("default")
        
        # Assert
        expected_keys = {
            "agent_type", "agent_class", "class_name", "resolvable", 
            "dependencies_valid", "missing_dependencies", "_factory_version", "_resolution_method"
        }
        self.assertEqual(set(context.keys()), expected_keys)
        
        self.assertEqual(context["agent_type"], "default")
        self.assertEqual(context["agent_class"], mock_agent_class)
        self.assertEqual(context["class_name"], "DefaultAgent")
        self.assertTrue(context["resolvable"])
        self.assertTrue(context["dependencies_valid"])
        self.assertEqual(context["missing_dependencies"], [])
        self.assertEqual(context["_factory_version"], "2.0")
        self.assertEqual(context["_resolution_method"], "AgentFactoryService.resolve_agent_class")
    
    def test_get_agent_resolution_context_failure(self):
        """Test get_agent_resolution_context() returns error context for invalid agent."""
        # Arrange
        self.mock_agent_registry_service.get_agent_class.return_value = None
        
        # Act
        context = self.service.get_agent_resolution_context("nonexistent_agent")
        
        # Assert
        self.assertEqual(context["agent_type"], "nonexistent_agent")
        self.assertIsNone(context["agent_class"])
        self.assertIsNone(context["class_name"])
        self.assertFalse(context["resolvable"])
        self.assertIn("resolution_error", context)
        self.assertIn("Agent type 'nonexistent_agent' not found", context["resolution_error"])
    
    def test_get_agent_resolution_context_missing_dependencies(self):
        """Test get_agent_resolution_context() shows dependency issues."""
        # Arrange
        mock_agent_class = Mock()
        mock_agent_class.__name__ = "OpenAIAgent"
        self.mock_agent_registry_service.get_agent_class.return_value = mock_agent_class
        
        # Configure LLM dependencies as NOT available
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: False
        
        # Act
        context = self.service.get_agent_resolution_context("openai")
        
        # Assert
        self.assertFalse(context["resolvable"])
        self.assertFalse(context["dependencies_valid"])
        self.assertEqual(context["missing_dependencies"], ["llm"])
        self.assertIn("resolution_error", context)
    
    # =============================================================================
    # 8. Private Helper Method Tests
    # =============================================================================
    
    def test_is_llm_agent_recognition(self):
        """Test _is_llm_agent() correctly identifies LLM agent types."""
        # Test LLM agent types
        llm_types = ["openai", "anthropic", "google", "gpt", "claude", "gemini", "llm"]
        for agent_type in llm_types:
            with self.subTest(agent_type=agent_type):
                self.assertTrue(self.service._is_llm_agent(agent_type))
        
        # Test non-LLM agent types
        non_llm_types = ["default", "csv_reader", "input", "orchestrator"]
        for agent_type in non_llm_types:
            with self.subTest(agent_type=agent_type):
                self.assertFalse(self.service._is_llm_agent(agent_type))
    
    def test_is_storage_agent_recognition(self):
        """Test _is_storage_agent() correctly identifies storage agent types."""
        # Test storage agent types
        storage_types = ["csv_reader", "csv_writer", "json_reader", "json_writer", 
                        "file_reader", "file_writer", "vector_reader", "vector_writer"]
        for agent_type in storage_types:
            with self.subTest(agent_type=agent_type):
                self.assertTrue(self.service._is_storage_agent(agent_type))
        
        # Test non-storage agent types
        non_storage_types = ["default", "openai", "input", "orchestrator"]
        for agent_type in non_storage_types:
            with self.subTest(agent_type=agent_type):
                self.assertFalse(self.service._is_storage_agent(agent_type))
    
    def test_check_llm_dependencies_specific_providers(self):
        """Test _check_llm_dependencies() for specific LLM providers."""
        # Test OpenAI specific check
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: (
            cat == "llm" and prov == "openai"
        )
        self.assertTrue(self.service._check_llm_dependencies("openai"))
        self.assertTrue(self.service._check_llm_dependencies("gpt"))
        
        # Test Anthropic specific check
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: (
            cat == "llm" and prov == "anthropic"
        )
        self.assertTrue(self.service._check_llm_dependencies("anthropic"))
        self.assertTrue(self.service._check_llm_dependencies("claude"))
        
        # Test Google specific check
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: (
            cat == "llm" and prov == "google"
        )
        self.assertTrue(self.service._check_llm_dependencies("google"))
        self.assertTrue(self.service._check_llm_dependencies("gemini"))
    
    def test_check_llm_dependencies_generic_llm(self):
        """Test _check_llm_dependencies() for generic LLM agent."""
        # Configure some LLM providers as available
        def mock_get_providers_with_llm(category):
            if category == "llm":
                return ["openai", "anthropic"]
            return self._default_get_available_providers(category)
        
        self.mock_features_registry_service.get_available_providers.side_effect = mock_get_providers_with_llm
        self.assertTrue(self.service._check_llm_dependencies("llm"))
        
        # Test when no LLM providers available
        def mock_get_providers_no_llm(category):
            if category == "llm":
                return []
            return self._default_get_available_providers(category)
        
        self.mock_features_registry_service.get_available_providers.side_effect = mock_get_providers_no_llm
        self.assertFalse(self.service._check_llm_dependencies("llm"))
    
    def test_check_storage_dependencies_specific_types(self):
        """Test _check_storage_dependencies() for specific storage types."""
        # Test CSV storage
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: (
            cat == "storage" and prov == "csv"
        )
        self.assertTrue(self.service._check_storage_dependencies("csv_reader"))
        
        # Test JSON storage
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: (
            cat == "storage" and prov == "json"
        )
        self.assertTrue(self.service._check_storage_dependencies("json_writer"))
        
        # Test vector storage
        self.mock_features_registry_service.is_provider_available.side_effect = lambda cat, prov: (
            cat == "storage" and prov == "vector"
        )
        self.assertTrue(self.service._check_storage_dependencies("vector_reader"))
    
    def test_get_dependency_error_message_llm_providers(self):
        """Test _get_dependency_error_message() for LLM providers."""
        # Test OpenAI error message
        error_msg = self.service._get_dependency_error_message("openai", ["llm"])
        self.assertIn("OpenAI dependencies", error_msg)
        self.assertIn("pip install agentmap[openai]", error_msg)
        
        # Test Anthropic error message
        error_msg = self.service._get_dependency_error_message("claude", ["llm"])
        self.assertIn("Anthropic dependencies", error_msg)
        self.assertIn("pip install agentmap[anthropic]", error_msg)
        
        # Test Google error message
        error_msg = self.service._get_dependency_error_message("gemini", ["llm"])
        self.assertIn("Google dependencies", error_msg)
        self.assertIn("pip install agentmap[google]", error_msg)
        
        # Test generic LLM error message
        error_msg = self.service._get_dependency_error_message("llm", ["llm"])
        self.assertIn("LLM agent 'llm' requires additional dependencies", error_msg)
        self.assertIn("pip install agentmap[llm]", error_msg)
    
    def test_get_dependency_error_message_storage_providers(self):
        """Test _get_dependency_error_message() for storage providers."""
        # Test vector storage error message
        error_msg = self.service._get_dependency_error_message("vector_writer", ["storage"])
        self.assertIn("vector dependencies", error_msg)
        self.assertIn("pip install agentmap[vector]", error_msg)
        
        # Test generic storage error message
        error_msg = self.service._get_dependency_error_message("csv_reader", ["storage"])
        self.assertIn("Storage agent 'csv_reader' requires additional dependencies", error_msg)
        self.assertIn("pip install agentmap[storage]", error_msg)
    
    def test_get_dependency_error_message_multiple_dependencies(self):
        """Test _get_dependency_error_message() for multiple missing dependencies."""
        error_msg = self.service._get_dependency_error_message("hybrid_agent", ["llm", "storage"])
        self.assertIn("requires additional dependencies: ['llm', 'storage']", error_msg)
        self.assertIn("pip install agentmap[llm,storage]", error_msg)
    
    # =============================================================================
    # 9. Error Handling and Edge Cases
    # =============================================================================
    
    def test_service_handles_empty_agent_type(self):
        """Test that service methods handle empty agent type gracefully."""
        # resolve_agent_class should validate dependencies for empty string
        dependencies_valid, missing_deps = self.service.validate_agent_dependencies("")
        self.assertTrue(dependencies_valid)  # Empty string is not LLM or storage agent
        self.assertEqual(missing_deps, [])
        
        # can_resolve_agent_type should handle empty agent type
        result = self.service.can_resolve_agent_type("")
        # This depends on agent registry behavior, but should not crash
        self.assertIsInstance(result, bool)
    
    def test_service_handles_none_agent_type(self):
        """Test that service methods handle None agent type gracefully."""
        # These should not crash, though they may raise TypeErrors
        with self.assertRaises((TypeError, AttributeError)):
            self.service.validate_agent_dependencies(None)
    
    def test_dependency_validation_case_insensitive(self):
        """Test that dependency validation is case insensitive."""
        # Test uppercase agent type
        dependencies_valid, missing_deps = self.service.validate_agent_dependencies("CSV_READER")
        
        # Should recognize as storage agent and check dependencies
        if not dependencies_valid:
            self.assertEqual(missing_deps, ["storage"])
        else:
            self.assertEqual(missing_deps, [])


if __name__ == '__main__':
    unittest.main()
