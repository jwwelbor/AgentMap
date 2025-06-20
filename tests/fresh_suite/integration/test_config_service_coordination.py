"""
Configuration Service Coordination Integration Tests.

This module tests the coordination between ConfigService and AppConfigService
using real DI container instances, validating that the architectural boundaries
between pure infrastructure (ConfigService) and domain logic (AppConfigService)
are maintained.
"""

import unittest
import tempfile
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from agentmap.exceptions.base_exceptions import ConfigurationException


class TestConfigServiceCoordination(BaseIntegrationTest):
    """
    Integration tests for ConfigService ↔ AppConfigService coordination.
    
    Tests the workflow from raw file loading through domain-specific configuration
    processing, ensuring architectural boundaries are maintained:
    - ConfigService: Pure infrastructure (YAML loading only)
    - AppConfigService: Domain logic with defaults merging
    """
    
    def setup_services(self):
        """Initialize configuration services for coordination testing."""
        super().setup_services()
        
        # Core configuration services
        self.config_service = self.container.config_service()
        # app_config_service already initialized in base class
        
        # Storage configuration service (may be None if not available)
        self.storage_config_service = self.container.storage_config_service()
        
        # LLM routing configuration service
        self.llm_routing_config_service = self.container.llm_routing_config_service()
    
    # =============================================================================
    # 1. ConfigService Infrastructure Layer Tests
    # =============================================================================
    
    def test_config_service_pure_infrastructure(self):
        """Test ConfigService remains pure infrastructure without domain logic."""
        # Verify ConfigService is created correctly
        self.assert_service_created(self.config_service, "ConfigService")
        
        # Test pure file loading capability
        test_config_data = {
            "simple": {"value": "test"},
            "nested": {"section": {"key": "nested_value"}},
            "list": ["item1", "item2", "item3"]
        }
        
        config_path = Path(self.temp_dir) / "pure_test_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(test_config_data, f)
        
        # ConfigService should load raw YAML without any domain logic
        loaded_config = self.config_service.load_config(config_path)
        
        # Verify exact match without defaults or transformation
        self.assertEqual(loaded_config, test_config_data, 
                        "ConfigService should load YAML exactly as-is without domain logic")
        
        # Test dot notation value retrieval (infrastructure utility)
        simple_value = self.config_service.get_value_from_config(loaded_config, "simple.value")
        self.assertEqual(simple_value, "test")
        
        nested_value = self.config_service.get_value_from_config(loaded_config, "nested.section.key")
        self.assertEqual(nested_value, "nested_value")
        
        # Test default handling in infrastructure layer
        missing_value = self.config_service.get_value_from_config(loaded_config, "missing.path", "default")
        self.assertEqual(missing_value, "default")
    
    def test_config_service_error_handling(self):
        """Test ConfigService error handling for infrastructure failures."""
        # Test missing file
        missing_path = Path(self.temp_dir) / "missing.yaml"
        loaded_config = self.config_service.load_config(missing_path)
        self.assertEqual(loaded_config, {}, "Missing file should return empty config")
        
        # Test invalid YAML
        invalid_yaml_path = Path(self.temp_dir) / "invalid.yaml"
        invalid_yaml_path.write_text("invalid: yaml: content: [unclosed")
        
        with self.assertRaises(ConfigurationException) as context:
            self.config_service.load_config(invalid_yaml_path)
        
        self.assertIn("Failed to parse config file", str(context.exception))
        self.assertIn("invalid.yaml", str(context.exception))
    
    def test_config_service_singleton_behavior(self):
        """Test ConfigService singleton pattern across container access."""
        # Get ConfigService instance multiple times
        config_service_1 = self.container.config_service()
        config_service_2 = self.container.config_service()
        
        # Should be the same instance (singleton)
        self.assertIs(config_service_1, config_service_2, 
                     "ConfigService should be singleton across container access")
        
        # Should be the same as stored instance
        self.assertIs(self.config_service, config_service_1,
                     "ConfigService instances should be identical")
    
    # =============================================================================
    # 2. AppConfigService Domain Logic Layer Tests
    # =============================================================================
    
    def test_app_config_service_domain_logic(self):
        """Test AppConfigService implements domain-specific business logic."""
        # Verify AppConfigService is created correctly
        self.assert_service_created(self.app_config_service, "AppConfigService")
        
        # Test domain-specific methods exist
        self.assertTrue(hasattr(self.app_config_service, 'get_routing_config'),
                       "AppConfigService should have domain-specific routing config method")
        self.assertTrue(hasattr(self.app_config_service, 'get_llm_config'),
                       "AppConfigService should have domain-specific LLM config method")
        self.assertTrue(hasattr(self.app_config_service, 'get_execution_config'),
                       "AppConfigService should have domain-specific execution config method")
        
        # Test defaults merging (domain logic)
        routing_config = self.app_config_service.get_routing_config()
        self.assertIsInstance(routing_config, dict, "Routing config should be dictionary")
        
        # Should have defaults even if not in config file
        self.assertIn('enabled', routing_config, "Should have default enabled setting")
        self.assertIn('complexity_analysis', routing_config, "Should have default complexity analysis")
        
        # Test domain-specific validation
        validation_result = self.app_config_service.validate_config()
        self.assertIsInstance(validation_result, bool, "Config validation should return boolean")
    
    def test_app_config_service_uses_config_service(self):
        """Test AppConfigService properly delegates infrastructure concerns to ConfigService."""
        # Create minimal config to test delegation
        minimal_config = {"test_section": {"test_key": "test_value"}}
        config_path = Path(self.temp_dir) / "delegation_test.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(minimal_config, f)
        
        # Create new AppConfigService with specific config path
        from agentmap.services.config.app_config_service import AppConfigService
        test_app_config = AppConfigService(self.config_service, config_path)
        
        # Test that AppConfigService can access loaded config
        test_value = test_app_config.get_value("test_section.test_key")
        self.assertEqual(test_value, "test_value", 
                        "AppConfigService should delegate to ConfigService for value retrieval")
        
        # Test that section access works
        test_section = test_app_config.get_section("test_section")
        self.assertEqual(test_section, {"test_key": "test_value"},
                        "AppConfigService should delegate to ConfigService for section access")
    
    def test_app_config_service_defaults_integration(self):
        """Test AppConfigService merges defaults correctly with loaded config."""
        # Create config with partial routing configuration
        partial_config = {
            "routing": {
                "enabled": False,  # Override default
                "custom_setting": "custom_value"  # Additional setting
            },
            "execution": {
                "max_retries": 5  # Override default
            }
        }
        
        config_path = Path(self.temp_dir) / "partial_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(partial_config, f)
        
        # Create AppConfigService with partial config
        from agentmap.services.config.app_config_service import AppConfigService
        test_app_config = AppConfigService(self.config_service, config_path)
        
        # Test routing config merging
        routing_config = test_app_config.get_routing_config()
        
        # Should have overridden value
        self.assertEqual(routing_config['enabled'], False, 
                        "Should use configured value over default")
        
        # Should have custom value
        self.assertEqual(routing_config['custom_setting'], "custom_value",
                        "Should preserve custom configuration values")
        
        # Should have defaults for unspecified values
        self.assertIn('complexity_analysis', routing_config,
                     "Should include default complexity analysis configuration")
        self.assertIn('task_types', routing_config,
                     "Should include default task types configuration")
        
        # Test execution config merging
        execution_config = test_app_config.get_execution_config()
        self.assertIsInstance(execution_config, dict, "Execution config should be dictionary")
    
    # =============================================================================
    # 3. Service Coordination Workflow Tests
    # =============================================================================
    
    def test_config_loading_workflow_coordination(self):
        """Test complete configuration loading workflow coordination."""
        # Create comprehensive test configuration
        comprehensive_config = {
            "logging": {
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO"
                    }
                }
            },
            "llm": {
                "anthropic": {
                    "api_key": "test_anthropic_key",
                    "model": "claude-3-sonnet-20240229",
                    "temperature": 0.7
                },
                "openai": {
                    "api_key": "test_openai_key", 
                    "model": "gpt-4",
                    "temperature": 0.5
                }
            },
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    "anthropic": {
                        "low": "claude-3-haiku-20240307",
                        "medium": "claude-3-sonnet-20240229",
                        "high": "claude-3-opus-20240229",
                        "critical": "claude-3-opus-20240229"
                    }
                }
            },
            "execution": {
                "max_retries": 3,
                "timeout": 30
            },
            "paths": {
                "custom_agents": "test_agents",
                "functions": "test_functions"
            }
        }
        
        config_path = Path(self.temp_dir) / "comprehensive_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(comprehensive_config, f)
        
        # Test workflow: ConfigService → AppConfigService
        
        # Step 1: ConfigService loads raw YAML
        raw_config = self.config_service.load_config(config_path)
        self.assertEqual(raw_config, comprehensive_config,
                        "ConfigService should load raw configuration exactly")
        
        # Step 2: AppConfigService processes with domain logic
        from agentmap.services.config.app_config_service import AppConfigService
        workflow_app_config = AppConfigService(self.config_service, config_path)
        
        # Step 3: Verify domain-specific processing
        llm_config = workflow_app_config.get_llm_config("anthropic")
        self.assertEqual(llm_config['api_key'], "test_anthropic_key",
                        "AppConfigService should provide LLM-specific configuration")
        
        routing_config = workflow_app_config.get_routing_config()
        self.assertTrue(routing_config['enabled'],
                       "AppConfigService should process routing configuration")
        
        execution_config = workflow_app_config.get_execution_config()
        self.assertEqual(execution_config['max_retries'], 3,
                        "AppConfigService should provide execution configuration")
        
        # Step 4: Verify path resolution
        custom_agents_path = workflow_app_config.get_custom_agents_path()
        self.assertEqual(str(custom_agents_path), "test_agents",
                        "AppConfigService should provide path resolution")
    
    def test_environment_specific_configuration_coordination(self):
        """Test coordination with environment-specific configurations."""
        # Create base configuration
        base_config = {
            "llm": {
                "anthropic": {
                    "model": "claude-3-haiku-20240307",
                    "temperature": 0.7
                }
            },
            "execution": {
                "max_retries": 3
            }
        }
        
        # Create environment override
        env_override = {
            "llm": {
                "anthropic": {
                    "model": "claude-3-sonnet-20240229",  # Override
                    "api_key": "env_specific_key"  # Addition
                }
            },
            "execution": {
                "timeout": 60  # Addition
            }
        }
        
        base_path = Path(self.temp_dir) / "base_config.yaml"
        env_path = Path(self.temp_dir) / "env_config.yaml"
        
        with open(base_path, 'w') as f:
            yaml.dump(base_config, f)
        with open(env_path, 'w') as f:
            yaml.dump(env_override, f)
        
        # Test coordination with multiple config sources
        # ConfigService handles file loading independently
        base_loaded = self.config_service.load_config(base_path)
        env_loaded = self.config_service.load_config(env_path)
        
        # AppConfigService would handle merging in real scenario
        # Here we test that both can be loaded correctly
        self.assertEqual(base_loaded['llm']['anthropic']['model'], "claude-3-haiku-20240307")
        self.assertEqual(env_loaded['llm']['anthropic']['model'], "claude-3-sonnet-20240229")
        
        # Verify infrastructure layer doesn't merge automatically
        self.assertNotEqual(base_loaded, env_loaded,
                           "ConfigService should not automatically merge configurations")
    
    def test_configuration_coordination_with_missing_sections(self):
        """Test coordination handles missing configuration sections gracefully."""
        # Create config with missing sections
        minimal_config = {
            "llm": {
                "anthropic": {
                    "api_key": "test_key"
                }
            }
            # Missing: logging, routing, execution, paths
        }
        
        config_path = Path(self.temp_dir) / "minimal_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(minimal_config, f)
        
        # Test ConfigService handles missing sections
        loaded_config = self.config_service.load_config(config_path)
        self.assertEqual(loaded_config, minimal_config,
                        "ConfigService should load minimal config as-is")
        
        # Missing sections should return None/empty when accessed directly
        missing_section = self.config_service.get_value_from_config(loaded_config, "routing.enabled")
        self.assertIsNone(missing_section,
                         "ConfigService should return None for missing configuration paths")
        
        # Test AppConfigService provides defaults for missing sections
        from agentmap.services.config.app_config_service import AppConfigService
        minimal_app_config = AppConfigService(self.config_service, config_path)
        
        # Should provide defaults even with missing sections
        routing_config = minimal_app_config.get_routing_config()
        self.assertIsInstance(routing_config, dict,
                             "AppConfigService should provide default routing config")
        self.assertIn('enabled', routing_config,
                     "AppConfigService should provide default enabled setting")
        
        execution_config = minimal_app_config.get_execution_config()
        self.assertIsInstance(execution_config, dict,
                             "AppConfigService should provide default execution config")
    
    # =============================================================================
    # 4. Architectural Boundary Validation Tests
    # =============================================================================
    
    def test_architectural_boundary_enforcement(self):
        """Test that architectural boundaries between services are maintained."""
        # Verify ConfigService doesn't have domain-specific methods
        config_service_methods = [method for method in dir(self.config_service) 
                                 if not method.startswith('_')]
        
        # ConfigService should only have infrastructure methods
        expected_infrastructure_methods = {
            'load_config', 'get_value_from_config', 'replace_logger'
        }
        
        domain_specific_patterns = [
            'get_routing', 'get_llm', 'get_execution', 'get_logging',
            'get_prompts', 'get_storage', 'validate_config', 'merge'
        ]
        
        for method in config_service_methods:
            # Should not have domain-specific methods
            for pattern in domain_specific_patterns:
                self.assertNotIn(pattern, method.lower(),
                               f"ConfigService should not have domain-specific method: {method}")
        
        # Should have expected infrastructure methods
        for expected_method in expected_infrastructure_methods:
            self.assertIn(expected_method, config_service_methods,
                         f"ConfigService should have infrastructure method: {expected_method}")
    
    def test_domain_logic_separation(self):
        """Test that domain logic is properly separated in AppConfigService."""
        # Verify AppConfigService has domain-specific methods
        app_config_methods = [method for method in dir(self.app_config_service)
                             if not method.startswith('_')]
        
        # Should have domain-specific methods
        expected_domain_methods = [
            'get_routing_config', 'get_llm_config', 'get_execution_config',
            'get_logging_config', 'get_prompts_config', 'validate_config'
        ]
        
        for expected_method in expected_domain_methods:
            self.assertIn(expected_method, app_config_methods,
                         f"AppConfigService should have domain method: {expected_method}")
        
        # Test that domain methods provide processed results, not raw config
        routing_config = self.app_config_service.get_routing_config()
        
        # Should have defaults merged in (domain logic)
        self.assertIn('enabled', routing_config,
                     "Domain logic should provide default 'enabled' setting")
        self.assertIn('complexity_analysis', routing_config,
                     "Domain logic should provide default complexity analysis")
        
        # Test that infrastructure delegation still works
        self.assertTrue(hasattr(self.app_config_service, 'get_value'),
                       "AppConfigService should delegate infrastructure methods")
        self.assertTrue(hasattr(self.app_config_service, 'get_section'),
                       "AppConfigService should delegate infrastructure methods")
    
    def test_service_dependency_isolation(self):
        """Test that services maintain proper dependency isolation."""
        # ConfigService should not depend on AppConfigService
        config_service_deps = getattr(self.config_service, '__dict__', {})
        
        for attr_name, attr_value in config_service_deps.items():
            if hasattr(attr_value, '__class__'):
                class_name = attr_value.__class__.__name__
                self.assertNotIn('AppConfig', class_name,
                               f"ConfigService should not depend on AppConfigService: {attr_name}")
        
        # AppConfigService should depend on ConfigService
        app_config_deps = getattr(self.app_config_service, '__dict__', {})
        
        has_config_service_dep = False
        for attr_name, attr_value in app_config_deps.items():
            if hasattr(attr_value, '__class__'):
                class_name = attr_value.__class__.__name__
                if 'ConfigService' in class_name:
                    has_config_service_dep = True
                    break
        
        self.assertTrue(has_config_service_dep,
                       "AppConfigService should depend on ConfigService")
    
    # =============================================================================
    # 5. Configuration Pipeline Integration Tests  
    # =============================================================================
    
    def test_full_configuration_pipeline_coordination(self):
        """Test complete configuration pipeline with all services."""
        # Create comprehensive configuration for full pipeline test
        full_config = {
            "logging": {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "simple": {"format": "[%(levelname)s] %(name)s: %(message)s"}
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "simple"
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["console"]
                }
            },
            "llm": {
                "anthropic": {
                    "api_key": "test_key",
                    "model": "claude-3-sonnet-20240229"
                }
            },
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    "anthropic": {
                        "low": "claude-3-haiku-20240307",
                        "medium": "claude-3-sonnet-20240229",
                        "high": "claude-3-opus-20240229",
                        "critical": "claude-3-opus-20240229"
                    }
                }
            },
            "storage_config_path": str(Path(self.temp_dir) / "storage_config.yaml")
        }
        
        # Create storage configuration
        storage_config = {
            "csv": {
                "default_directory": str(Path(self.temp_dir) / "csv_data"),
                "collections": {}
            },
            "vector": {
                "default_provider": "chroma",
                "collections": {}
            }
        }
        
        config_path = Path(self.temp_dir) / "full_pipeline_config.yaml"
        storage_config_path = Path(self.temp_dir) / "storage_config.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(full_config, f)
        with open(storage_config_path, 'w') as f:
            yaml.dump(storage_config, f)
        
        # Test full pipeline coordination
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.config.storage_config_service import StorageConfigService
        
        # Step 1: ConfigService infrastructure layer
        raw_config = self.config_service.load_config(config_path)
        self.assertEqual(raw_config['logging']['version'], 1)
        
        # Step 2: AppConfigService domain layer
        pipeline_app_config = AppConfigService(self.config_service, config_path)
        
        # Verify domain processing
        logging_config = pipeline_app_config.get_logging_config()
        self.assertEqual(logging_config['version'], 1)
        
        llm_config = pipeline_app_config.get_llm_config("anthropic")
        self.assertEqual(llm_config['model'], "claude-3-sonnet-20240229")
        
        # Step 3: StorageConfigService (if available)
        storage_path = pipeline_app_config.get_storage_config_path()
        self.assertEqual(str(storage_path), str(storage_config_path))
        
        try:
            pipeline_storage_config = StorageConfigService(self.config_service, storage_path)
            csv_config = pipeline_storage_config.get_csv_config()
            self.assertIsInstance(csv_config, dict)
        except Exception as e:
            # Storage config might not be available in test environment
            self.assertIn("StorageConfigurationNotAvailableException", str(type(e).__name__))
        
        # Step 4: LLMRoutingConfigService coordination
        self.assert_service_created(self.llm_routing_config_service, "LLMRoutingConfigService")
        
        # Verify routing service uses processed configuration
        routing_matrix = self.llm_routing_config_service.routing_matrix
        self.assertIsInstance(routing_matrix, dict)
        
        # Check the routing matrix structure: provider -> complexity -> model
        if routing_matrix:  # May be empty in test environment
            # Should have anthropic provider from default config or test config
            available_providers = self.llm_routing_config_service.get_available_providers()
            self.assertIsInstance(available_providers, list, "Should get list of available providers")
            
            # Should have at least one provider (from defaults or test config)
            if available_providers:
                self.assertIn('anthropic', available_providers, "Should have anthropic provider")
                
                # Test that we can get models for complexity levels
                medium_model = self.llm_routing_config_service.get_model_for_complexity("anthropic", "medium")
                self.assertIsNotNone(medium_model, "Should get model for anthropic medium complexity")
                
            # Test that we can get provider preferences
            provider_preferences = self.llm_routing_config_service.get_provider_preference("general")
            self.assertIsInstance(provider_preferences, list, "Should get provider preference list")
    
    def test_configuration_error_propagation_coordination(self):
        """Test error propagation coordination across configuration services."""
        # Test infrastructure error propagation
        invalid_yaml_path = Path(self.temp_dir) / "invalid_pipeline.yaml"
        invalid_yaml_path.write_text("invalid: yaml: [unclosed")
        
        # ConfigService should catch and re-raise as ConfigurationException
        with self.assertRaises(ConfigurationException):
            self.config_service.load_config(invalid_yaml_path)
        
        # AppConfigService should handle ConfigService errors gracefully
        from agentmap.services.config.app_config_service import AppConfigService
        with self.assertRaises(ConfigurationException):
            AppConfigService(self.config_service, invalid_yaml_path)
        
        # Test domain-specific error handling
        missing_file_path = Path(self.temp_dir) / "missing_pipeline.yaml"
        
        # Should handle missing files gracefully (return empty config)
        empty_config = self.config_service.load_config(missing_file_path)
        self.assertEqual(empty_config, {})
        
        # AppConfigService should work with empty config (using defaults)
        empty_app_config = AppConfigService(self.config_service, missing_file_path)
        
        # Should still provide defaults for missing configuration
        routing_config = empty_app_config.get_routing_config()
        self.assertIsInstance(routing_config, dict)
        self.assertIn('enabled', routing_config)


if __name__ == '__main__':
    unittest.main()
