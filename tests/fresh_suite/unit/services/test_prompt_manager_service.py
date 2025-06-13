"""
Unit tests for PromptManagerService.

These tests validate the PromptManagerService using actual interface methods
and follow the established MockServiceFactory patterns for consistent testing.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml
import tempfile
import os

from agentmap.services.prompt_manager_service import PromptManagerService
from tests.utils.mock_service_factory import MockServiceFactory


class TestPromptManagerService(unittest.TestCase):
    """Unit tests for PromptManagerService with comprehensive prompt management coverage."""
    
    def setUp(self):
        """Set up test fixtures with mocked dependencies."""
        # Create mock services using MockServiceFactory
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_app_config_service = MockServiceFactory.create_mock_app_config_service()
        
        # Configure mock app config service with prompts configuration
        self.prompts_config = {
            "directory": "test_prompts",
            "registry_file": "test_prompts/registry.yaml",
            "enable_cache": True
        }
        self.mock_app_config_service.get_prompts_config.return_value = self.prompts_config
        
        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_prompts_dir = Path(self.temp_dir) / "test_prompts"
        self.test_prompts_dir.mkdir(exist_ok=True)
        
        # Initialize PromptManagerService with mocked dependencies
        with patch('pathlib.Path.mkdir'):  # Prevent actual directory creation during init
            self.service = PromptManagerService(
                app_config_service=self.mock_app_config_service,
                logging_service=self.mock_logging_service
            )
        
        # Get the mock logger for verification
        self.mock_logger = self.service.logger
        
        # Mock registry data
        self.mock_registry = {
            "welcome": "Welcome to AgentMap!",
            "error": "An error occurred: {error_message}",
            "success": "Operation completed successfully.",
            "complex": "Process {item_count} items with {mode} mode at {timestamp}."
        }
    
    # =============================================================================
    # 1. Service Initialization Tests
    # =============================================================================
    
    def test_service_initialization(self):
        """Test that service initializes correctly with all dependencies."""
        # Verify all dependencies are stored
        self.assertEqual(self.service.config, self.mock_app_config_service)
        self.assertIsNotNone(self.service.logger)
        
        # Verify configuration values
        self.assertEqual(self.service.prompts_dir, Path("test_prompts"))
        self.assertEqual(self.service.registry_path, Path("test_prompts/registry.yaml"))
        self.assertTrue(self.service.enable_cache)
        
        # Verify logger setup
        self.mock_logging_service.get_class_logger.assert_called_once()
        
        # Verify cache initialization
        self.assertIsInstance(self.service._cache, dict)
    
    def test_service_initialization_with_custom_config(self):
        """Test service initialization with custom configuration."""
        custom_config = {
            "directory": "custom_prompts",
            "registry_file": "custom_prompts/custom_registry.yaml",
            "enable_cache": False
        }
        
        mock_config = MockServiceFactory.create_mock_app_config_service()
        mock_config.get_prompts_config.return_value = custom_config
        
        with patch('pathlib.Path.mkdir'):
            service = PromptManagerService(
                app_config_service=mock_config,
                logging_service=self.mock_logging_service
            )
        
        # Verify custom configuration is used
        self.assertEqual(service.prompts_dir, Path("custom_prompts"))
        self.assertEqual(service.registry_path, Path("custom_prompts/custom_registry.yaml"))
        self.assertFalse(service.enable_cache)
    
    # =============================================================================
    # 2. Registry Loading Tests
    # =============================================================================
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    def test_load_registry_from_configured_path(self, mock_yaml_load, mock_file_open, mock_exists):
        """Test _load_registry() loads from configured registry path."""
        # Configure mocks
        mock_exists.return_value = True
        mock_yaml_load.return_value = self.mock_registry
        
        # Create new service to trigger registry loading
        with patch('pathlib.Path.mkdir'):
            service = PromptManagerService(
                app_config_service=self.mock_app_config_service,
                logging_service=self.mock_logging_service
            )
        
        # Verify registry was loaded
        self.assertEqual(service._registry, self.mock_registry)
        mock_file_open.assert_called_once()
        mock_yaml_load.assert_called_once()
    
    @patch('pathlib.Path.exists')
    def test_load_registry_file_not_found(self, mock_exists):
        """Test _load_registry() handles missing registry file gracefully."""
        # Configure no registry file exists
        mock_exists.return_value = False
        
        with patch.object(PromptManagerService, '_find_resource', return_value=None):
            with patch('pathlib.Path.mkdir'):
                service = PromptManagerService(
                    app_config_service=self.mock_app_config_service,
                    logging_service=self.mock_logging_service
                )
        
        # Should initialize with empty registry
        self.assertEqual(service._registry, {})
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    def test_load_registry_yaml_parse_error(self, mock_yaml_load, mock_file_open, mock_exists):
        """Test _load_registry() handles YAML parsing errors."""
        # Configure YAML parsing to fail
        mock_exists.return_value = True
        mock_yaml_load.side_effect = yaml.YAMLError("Invalid YAML")
        
        with patch('pathlib.Path.mkdir'):
            service = PromptManagerService(
                app_config_service=self.mock_app_config_service,
                logging_service=self.mock_logging_service
            )
        
        # Should fall back to empty registry
        self.assertEqual(service._registry, {})
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    def test_load_registry_with_system_fallback(self, mock_yaml_load, mock_file_open, mock_exists):
        """Test _load_registry() falls back to system registry."""
        # Configure primary registry doesn't exist, but system registry does
        # First call (primary registry) returns False, subsequent calls return True
        mock_exists.side_effect = [False, True]  # First False, then True for system registry
        mock_yaml_load.return_value = {"system_prompt": "System prompt"}
        
        with patch.object(PromptManagerService, '_find_resource') as mock_find:
            mock_find.return_value = Path("system/registry.yaml")
            
            with patch('pathlib.Path.mkdir'):
                service = PromptManagerService(
                    app_config_service=self.mock_app_config_service,
                    logging_service=self.mock_logging_service
                )
        
        # Should load system registry
        self.assertEqual(service._registry, {"system_prompt": "System prompt"})
    
    # =============================================================================
    # 3. Resource Finding Tests
    # =============================================================================
    
    def test_find_resource_absolute_path_exists(self):
        """Test _find_resource() with existing absolute path."""
        # Create temporary file
        temp_file = Path(self.temp_dir) / "test_resource.txt"
        temp_file.write_text("test content")
        
        # Test absolute path
        result = self.service._find_resource(str(temp_file))
        self.assertEqual(result, temp_file)
    
    def test_find_resource_local_path_exists(self):
        """Test _find_resource() with existing local path."""
        # Create file in prompts directory
        local_file = self.test_prompts_dir / "local_resource.txt"
        local_file.write_text("local content")
        
        with patch.object(self.service, 'prompts_dir', self.test_prompts_dir):
            result = self.service._find_resource("local_resource.txt")
            self.assertEqual(result, local_file)
    
    def test_find_resource_embedded_resource(self):
        """Test _find_resource() falls back to embedded resource."""
        with patch.object(self.service, '_try_get_resource') as mock_try_get:
            mock_embedded_path = Path("embedded/resource.txt")
            mock_try_get.return_value = mock_embedded_path
            
            result = self.service._find_resource("nonexistent_local.txt")
            self.assertEqual(result, mock_embedded_path)
            mock_try_get.assert_called_once_with("nonexistent_local.txt")
    
    def test_find_resource_not_found_anywhere(self):
        """Test _find_resource() returns None when resource not found."""
        with patch.object(self.service, '_try_get_resource', return_value=None):
            result = self.service._find_resource("completely_missing.txt")
            self.assertIsNone(result)
    
    # =============================================================================
    # 4. Embedded Resource Tests
    # =============================================================================
    
    @patch('importlib.resources.files')
    def test_try_get_resource_modern_importlib(self, mock_files):
        """Test _try_get_resource() with modern importlib.resources."""
        # Mock modern importlib.resources behavior
        mock_resource = Mock()
        mock_resource.exists.return_value = True
        mock_files.return_value.joinpath.return_value = mock_resource
        
        result = self.service._try_get_resource("test_resource.txt")
        self.assertEqual(result, mock_resource)
        mock_files.assert_called_once_with(self.service.template_location)
    
    def test_try_get_resource_handles_import_failures_gracefully(self):
        """Test _try_get_resource() handles import failures gracefully."""
        # Test business logic: when all import methods fail, return None gracefully
        with patch('importlib.resources.files', side_effect=ImportError), \
             patch('importlib.resources.path', side_effect=ImportError), \
             patch('importlib.util.find_spec', return_value=None):
            
            result = self.service._try_get_resource("missing_resource.txt")
            
            # Should handle failures gracefully
            self.assertIsNone(result)
    
    def test_try_get_resource_returns_valid_path_when_found(self):
        """Test _try_get_resource() returns valid path when resource is found."""
        # Test business logic: when resource exists, return a valid Path
        with patch('importlib.resources.files') as mock_files:
            # Mock successful resource finding
            mock_resource = Mock()
            mock_resource.exists.return_value = True
            mock_files.return_value.joinpath.return_value = mock_resource
            
            result = self.service._try_get_resource("found_resource.txt")
            
            # Should return the found resource
            self.assertEqual(result, mock_resource)
            self.assertIsNotNone(result)
    
    def test_try_get_resource_spec_fallback_works(self):
        """Test _try_get_resource() can find resources using spec fallback."""
        # Test business logic: spec-based resource finding works
        with patch('importlib.resources.files', side_effect=ImportError), \
             patch('importlib.resources.path', side_effect=ImportError), \
             patch('importlib.util.find_spec') as mock_find_spec, \
             patch('pathlib.Path.exists', return_value=True):
            
            # Mock spec-based fallback
            mock_spec = Mock()
            mock_spec.origin = "/path/to/package/__init__.py"
            mock_find_spec.return_value = mock_spec
            
            result = self.service._try_get_resource("resource.txt")
            
            # Verify business outcome: resource was found using spec method
            self.assertIsInstance(result, Path)
            self.assertIsNotNone(result)
            mock_find_spec.assert_called_once()
    
    def test_try_get_resource_all_methods_fail(self):
        """Test _try_get_resource() returns None when all methods fail."""
        with patch('importlib.resources.files', side_effect=ImportError), \
             patch('importlib.resources.path', side_effect=ImportError), \
             patch('importlib.util.find_spec', return_value=None):
            
            result = self.service._try_get_resource("missing_resource.txt")
            self.assertIsNone(result)
    
    # =============================================================================
    # 5. Prompt Resolution Tests
    # =============================================================================
    
    def test_resolve_prompt_registry_reference(self):
        """Test resolve_prompt() with registry reference."""
        # Set up registry
        self.service._registry = self.mock_registry
        
        result = self.service.resolve_prompt("prompt:welcome")
        self.assertEqual(result, "Welcome to AgentMap!")
    
    def test_resolve_prompt_registry_reference_not_found(self):
        """Test resolve_prompt() with missing registry reference."""
        # Set up registry
        self.service._registry = self.mock_registry
        
        result = self.service.resolve_prompt("prompt:nonexistent")
        self.assertEqual(result, "[Prompt not found: nonexistent]")
    
    @patch('builtins.open', new_callable=mock_open, read_data="File prompt content")
    def test_resolve_prompt_file_reference(self, mock_file):
        """Test resolve_prompt() with file reference."""
        with patch.object(self.service, '_find_resource') as mock_find:
            mock_find.return_value = Path("test_prompt.txt")
            
            result = self.service.resolve_prompt("file:test_prompt.txt")
            self.assertEqual(result, "File prompt content")
            mock_file.assert_called_once()
    
    def test_resolve_prompt_file_reference_not_found(self):
        """Test resolve_prompt() with missing file reference."""
        with patch.object(self.service, '_find_resource', return_value=None):
            result = self.service.resolve_prompt("file:missing.txt")
            self.assertEqual(result, "[Prompt file not found: missing.txt]")
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    def test_resolve_prompt_yaml_reference(self, mock_yaml_load, mock_file):
        """Test resolve_prompt() with YAML reference."""
        # Mock YAML content
        yaml_content = {
            "prompts": {
                "greeting": "Hello from YAML!",
                "nested": {
                    "deep": "Deep YAML value"
                }
            }
        }
        mock_yaml_load.return_value = yaml_content
        
        with patch.object(self.service, '_find_resource') as mock_find:
            mock_find.return_value = Path("test.yaml")
            
            # Test simple key path
            result = self.service.resolve_prompt("yaml:test.yaml#prompts.greeting")
            self.assertEqual(result, "Hello from YAML!")
            
            # Test nested key path
            result = self.service.resolve_prompt("yaml:test.yaml#prompts.nested.deep")
            self.assertEqual(result, "Deep YAML value")
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    def test_resolve_prompt_yaml_reference_key_not_found(self, mock_yaml_load, mock_file):
        """Test resolve_prompt() with YAML reference and missing key."""
        yaml_content = {"existing": "value"}
        mock_yaml_load.return_value = yaml_content
        
        with patch.object(self.service, '_find_resource') as mock_find:
            mock_find.return_value = Path("test.yaml")
            
            result = self.service.resolve_prompt("yaml:test.yaml#missing.key")
            self.assertEqual(result, "[Key not found in YAML: missing.key]")
    
    def test_resolve_prompt_yaml_reference_invalid_format(self):
        """Test resolve_prompt() with invalid YAML reference format."""
        result = self.service.resolve_prompt("yaml:missing_hash_key")
        self.assertEqual(result, "[Invalid YAML reference (missing #key): missing_hash_key]")
    
    def test_resolve_prompt_plain_text(self):
        """Test resolve_prompt() with plain text (no prefix)."""
        plain_text = "This is just plain text"
        result = self.service.resolve_prompt(plain_text)
        self.assertEqual(result, plain_text)
    
    def test_resolve_prompt_none_or_empty(self):
        """Test resolve_prompt() with None or empty string."""
        self.assertIsNone(self.service.resolve_prompt(None))
        self.assertEqual(self.service.resolve_prompt(""), "")
    
    def test_resolve_prompt_caching_enabled(self):
        """Test resolve_prompt() uses caching when enabled."""
        self.service.enable_cache = True
        self.service._registry = self.mock_registry
        
        # First call
        result1 = self.service.resolve_prompt("prompt:welcome")
        self.assertEqual(result1, "Welcome to AgentMap!")
        
        # Second call should use cache
        result2 = self.service.resolve_prompt("prompt:welcome")
        self.assertEqual(result2, "Welcome to AgentMap!")
        
        # Verify cache was populated
        self.assertIn("prompt:welcome", self.service._cache)
        self.assertEqual(self.service._cache["prompt:welcome"], "Welcome to AgentMap!")
    
    def test_resolve_prompt_caching_disabled(self):
        """Test resolve_prompt() doesn't cache when disabled."""
        self.service.enable_cache = False
        self.service._registry = self.mock_registry
        
        result = self.service.resolve_prompt("prompt:welcome")
        self.assertEqual(result, "Welcome to AgentMap!")
        
        # Cache should remain empty
        self.assertEqual(len(self.service._cache), 0)
    
    # =============================================================================
    # 6. Prompt Formatting Tests
    # =============================================================================
    
    def test_format_prompt_with_langchain(self):
        """Test format_prompt() using LangChain PromptTemplate."""
        template = "Hello {name}, you have {count} messages."
        values = {"name": "Alice", "count": 5}
        
        with patch('langchain.prompts.PromptTemplate') as mock_template_class:
            mock_template = Mock()
            mock_template.format.return_value = "Hello Alice, you have 5 messages."
            mock_template_class.return_value = mock_template
            
            result = self.service.format_prompt(template, values)
            self.assertEqual(result, "Hello Alice, you have 5 messages.")
            
            # Verify LangChain was used correctly
            mock_template_class.assert_called_once_with(
                template=template,
                input_variables=["name", "count"]
            )
            mock_template.format.assert_called_once_with(**values)
    
    def test_format_prompt_langchain_fallback_to_standard(self):
        """Test format_prompt() falls back to standard formatting when LangChain fails."""
        template = "Hello {name}, you have {count} messages."
        values = {"name": "Bob", "count": 3}
        
        with patch('langchain.prompts.PromptTemplate') as mock_template_class:
            # Configure LangChain to fail
            mock_template_class.side_effect = ImportError("LangChain not available")
            
            result = self.service.format_prompt(template, values)
            self.assertEqual(result, "Hello Bob, you have 3 messages.")
    
    def test_format_prompt_standard_formatting_fallback(self):
        """Test format_prompt() falls back to manual replacement when standard formatting fails."""
        template = "Process {item_count} items with {mode} mode and {missing_var} extra"  # Well-formed but missing variable
        values = {"item_count": 10, "mode": "fast"}  # Missing 'missing_var'
        
        with patch('langchain.prompts.PromptTemplate') as mock_template_class:
            mock_template_class.side_effect = ImportError("LangChain not available")
            
            # Standard format will fail due to missing variable, fall back to manual
            result = self.service.format_prompt(template, values)
            
            # Should replace available variables and leave unknown ones as-is
            self.assertIn("10", result)
            self.assertIn("fast", result)
            self.assertIn("{missing_var}", result)  # Should remain unreplaced
    
    def test_format_prompt_with_prompt_reference(self):
        """Test format_prompt() resolves prompt reference before formatting."""
        self.service._registry = self.mock_registry
        values = {"error_message": "Connection failed"}
        
        result = self.service.format_prompt("prompt:error", values)
        self.assertEqual(result, "An error occurred: Connection failed")
    
    def test_format_prompt_complex_template(self):
        """Test format_prompt() with complex template and multiple variables."""
        self.service._registry = self.mock_registry
        values = {
            "item_count": 42,
            "mode": "strict",
            "timestamp": "2024-01-01 12:00:00"
        }
        
        result = self.service.format_prompt("prompt:complex", values)
        expected = "Process 42 items with strict mode at 2024-01-01 12:00:00."
        self.assertEqual(result, expected)
    
    def test_format_prompt_missing_variables(self):
        """Test format_prompt() handles missing variables gracefully."""
        template = "Hello {name}, your score is {score}"
        values = {"name": "Charlie"}  # Missing 'score'
        
        with patch('langchain.prompts.PromptTemplate') as mock_template_class:
            mock_template_class.side_effect = ImportError("LangChain not available")
            
            # Standard formatting should fail, fall back to manual
            result = self.service.format_prompt(template, values)
            
            # Should contain the name but leave {score} as-is
            self.assertIn("Charlie", result)
            self.assertIn("{score}", result)
    
    # =============================================================================
    # 7. Service Management Tests
    # =============================================================================
    
    def test_get_registry(self):
        """Test get_registry() returns copy of current registry."""
        self.service._registry = self.mock_registry.copy()
        
        registry = self.service.get_registry()
        
        # Should be equal but not the same object
        self.assertEqual(registry, self.mock_registry)
        self.assertIsNot(registry, self.service._registry)
        
        # Modifications to returned registry shouldn't affect service
        registry["new_key"] = "new_value"
        self.assertNotIn("new_key", self.service._registry)
    
    def test_clear_cache(self):
        """Test clear_cache() empties the prompt cache."""
        # Populate cache
        self.service._cache = {
            "prompt:test1": "cached value 1",
            "file:test2.txt": "cached value 2"
        }
        
        self.service.clear_cache()
        
        # Cache should be empty
        self.assertEqual(len(self.service._cache), 0)
    
    def test_get_service_info(self):
        """Test get_service_info() returns comprehensive service information."""
        # Populate some test data
        self.service._cache = {"test": "value"}
        self.service._registry = self.mock_registry
        
        info = self.service.get_service_info()
        
        # Verify service information structure
        self.assertEqual(info["service"], "PromptManagerService")
        self.assertTrue(info["config_available"])
        self.assertEqual(info["cache_enabled"], self.service.enable_cache)
        self.assertEqual(info["cache_size"], 1)
        self.assertEqual(info["registry_size"], len(self.mock_registry))
        
        # Verify supported prefixes
        expected_prefixes = ["prompt:", "file:", "yaml:"]
        self.assertEqual(info["supported_prefixes"], expected_prefixes)
    
    # =============================================================================
    # 8. Global Functions Tests
    # =============================================================================
    
    def test_get_prompt_manager_singleton_behavior(self):
        """Test get_prompt_manager() singleton behavior."""
        from agentmap.services.prompt_manager_service import get_prompt_manager
        
        # Mock the PromptManagerService constructor to avoid dependency issues
        with patch('agentmap.services.prompt_manager_service.PromptManagerService') as mock_service_class:
            mock_instance = Mock(spec=PromptManagerService)
            mock_service_class.return_value = mock_instance
            
            # Reset the global singleton for this test
            import agentmap.services.prompt_manager_service as pms
            original_manager = pms._prompt_manager
            pms._prompt_manager = None
            
            try:
                # First call should create new instance
                manager1 = get_prompt_manager()
                
                # Second call should return same instance
                manager2 = get_prompt_manager()
                
                # Both should be the same instance (singleton behavior)
                self.assertEqual(manager1, manager2)
                self.assertEqual(manager1, mock_instance)
                
                # Constructor should only be called once
                mock_service_class.assert_called_once()
                
            finally:
                # Restore original state
                pms._prompt_manager = original_manager
    
    def test_resolve_prompt_global_function(self):
        """Test global resolve_prompt() function."""
        from agentmap.services.prompt_manager_service import resolve_prompt
        
        # Test plain text
        result = resolve_prompt("Plain text")
        self.assertEqual(result, "Plain text")
        
        # Test None
        result = resolve_prompt(None)
        self.assertIsNone(result)
    
    def test_format_prompt_global_function(self):
        """Test global format_prompt() function."""
        from agentmap.services.prompt_manager_service import format_prompt
        
        with patch('agentmap.services.prompt_manager_service.get_prompt_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.format_prompt.return_value = "Formatted prompt"
            mock_get_manager.return_value = mock_manager
            
            result = format_prompt("Template {var}", {"var": "value"})
            self.assertEqual(result, "Formatted prompt")
            
            mock_manager.format_prompt.assert_called_once_with("Template {var}", {"var": "value"})
    
    def test_get_formatted_prompt_helper_function(self):
        """Test get_formatted_prompt() helper function with fallback logic."""
        from agentmap.services.prompt_manager_service import get_formatted_prompt
        
        mock_logger = Mock()
        values = {"key": "value"}
        
        with patch('agentmap.services.prompt_manager_service.get_prompt_manager') as mock_get_manager, \
             patch('agentmap.services.prompt_manager_service.resolve_prompt') as mock_resolve:
            
            mock_manager = Mock()
            mock_manager.format_prompt.return_value = "Final formatted prompt"
            mock_get_manager.return_value = mock_manager
            mock_resolve.return_value = "Resolved template"
            
            # Test with primary prompt
            result = get_formatted_prompt(
                primary_prompt="Primary template",
                template_file="fallback_file.txt",
                default_template="Default template",
                values=values,
                logger=mock_logger,
                context_name="TestAgent"
            )
            
            self.assertEqual(result, "Final formatted prompt")
            mock_resolve.assert_called_once_with("Primary template")
    
    def test_get_formatted_prompt_fallback_chain(self):
        """Test get_formatted_prompt() fallback chain when primary fails."""
        from agentmap.services.prompt_manager_service import get_formatted_prompt
        
        mock_logger = Mock()
        values = {"key": "value"}
        
        with patch('agentmap.services.prompt_manager_service.get_prompt_manager') as mock_get_manager, \
             patch('agentmap.services.prompt_manager_service.resolve_prompt') as mock_resolve:
            
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager
            
            # Configure primary to fail, template_file to succeed
            def resolve_side_effect(prompt):
                if prompt == "Primary template":
                    raise Exception("Primary failed")
                elif prompt == "fallback_file.txt":
                    return "Resolved fallback"
                else:
                    return prompt
            
            mock_resolve.side_effect = resolve_side_effect
            mock_manager.format_prompt.return_value = "Fallback formatted"
            
            result = get_formatted_prompt(
                primary_prompt="Primary template",
                template_file="fallback_file.txt",
                default_template="Default template",
                values=values,
                logger=mock_logger
            )
            
            self.assertEqual(result, "Fallback formatted")
    
    # =============================================================================
    # 9. Error Handling and Edge Cases
    # =============================================================================
    
    def test_resolve_prompt_error_handling(self):
        """Test resolve_prompt() error handling for various failure scenarios."""
        # Test file reading error
        with patch.object(self.service, '_find_resource') as mock_find:
            mock_find.return_value = Path("problematic_file.txt")
            
            with patch('builtins.open', side_effect=PermissionError("Access denied")):
                result = self.service.resolve_prompt("file:problematic_file.txt")
                self.assertIn("[Error reading prompt file:", result)
    
    def test_resolve_prompt_yaml_non_scalar_value(self):
        """Test resolve_prompt() with YAML reference returning non-scalar value."""
        yaml_content = {"config": {"settings": {"complex": {"nested": "object"}}}}
        
        with patch.object(self.service, '_find_resource') as mock_find, \
             patch('builtins.open', new_callable=mock_open), \
             patch('yaml.safe_load', return_value=yaml_content):
            
            mock_find.return_value = Path("test.yaml")
            
            result = self.service.resolve_prompt("yaml:test.yaml#config.settings")
            self.assertIn("[Invalid prompt type in YAML:", result)
    
    def test_format_prompt_all_methods_fail(self):
        """Test format_prompt() when all formatting methods fail."""
        problematic_template = "Template with {unclosed formatting"
        values = {"var": "value"}
        
        with patch('langchain.prompts.PromptTemplate', side_effect=ImportError):
            # This should still try manual replacement
            result = self.service.format_prompt(problematic_template, values)
            
            # Should contain the template (possibly partially processed)
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)
    
    def test_large_registry_performance(self):
        """Test service performance with large registry."""
        # Create large registry
        large_registry = {f"prompt_{i}": f"Content for prompt {i}" for i in range(1000)}
        self.service._registry = large_registry
        
        # Test registry operations
        result = self.service.resolve_prompt("prompt:prompt_500")
        self.assertEqual(result, "Content for prompt 500")
        
        # Test registry retrieval
        registry_copy = self.service.get_registry()
        self.assertEqual(len(registry_copy), 1000)
    
    def test_concurrent_cache_access_simulation(self):
        """Test cache behavior under simulated concurrent access."""
        self.service.enable_cache = True
        self.service._registry = self.mock_registry
        
        # Simulate multiple rapid cache accesses
        results = []
        for i in range(10):
            result = self.service.resolve_prompt("prompt:welcome")
            results.append(result)
        
        # All results should be consistent
        self.assertTrue(all(r == "Welcome to AgentMap!" for r in results))
        
        # Cache should have the entry
        self.assertIn("prompt:welcome", self.service._cache)
    
    # =============================================================================
    # 10. Integration Tests
    # =============================================================================
    
    @patch('pathlib.Path.mkdir')
    def test_full_prompt_workflow_integration(self, mock_mkdir):
        """Test complete prompt workflow from initialization to formatting."""
        # Set up realistic configuration
        full_config = {
            "directory": "integration_prompts",
            "registry_file": "integration_prompts/registry.yaml",
            "enable_cache": True
        }
        
        mock_config = MockServiceFactory.create_mock_app_config_service()
        mock_config.get_prompts_config.return_value = full_config
        
        # Create service
        service = PromptManagerService(
            app_config_service=mock_config,
            logging_service=self.mock_logging_service
        )
        
        # Mock registry data
        integration_registry = {
            "user_greeting": "Welcome {username} to {system_name}!",
            "error_template": "Error in {component}: {error_details}",
            "success_message": "Successfully processed {item_count} items in {duration}ms"
        }
        service._registry = integration_registry
        
        # Test complete workflow
        # 1. Registry-based prompt with formatting
        result1 = service.format_prompt("prompt:user_greeting", {
            "username": "TestUser",
            "system_name": "AgentMap"
        })
        self.assertEqual(result1, "Welcome TestUser to AgentMap!")
        
        # 2. Error handling scenario
        result2 = service.format_prompt("prompt:error_template", {
            "component": "PromptManager",
            "error_details": "Template not found"
        })
        self.assertEqual(result2, "Error in PromptManager: Template not found")
        
        # 3. Success scenario with metrics
        result3 = service.format_prompt("prompt:success_message", {
            "item_count": 150,
            "duration": 2500
        })
        self.assertEqual(result3, "Successfully processed 150 items in 2500ms")
        
        # 4. Verify caching worked
        self.assertEqual(len(service._cache), 3)
        
        # 5. Test service info reflects the integration
        info = service.get_service_info()
        self.assertEqual(info["registry_size"], 3)
        self.assertEqual(info["cache_size"], 3)


if __name__ == '__main__':
    unittest.main()
