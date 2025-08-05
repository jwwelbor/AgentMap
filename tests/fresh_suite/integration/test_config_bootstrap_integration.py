"""
Configuration Bootstrap Integration Tests.

This module tests application bootstrap with the full configuration pipeline,
including service initialization order, configuration hot-reloading, and
graceful degradation scenarios with all configuration services working together.
"""

import unittest
import tempfile
import yaml
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest
from agentmap.exceptions.base_exceptions import ConfigurationException
from agentmap.exceptions.service_exceptions import StorageConfigurationNotAvailableException


class TestConfigBootstrapIntegration(BaseIntegrationTest):
    """
    Integration tests for application bootstrap with full configuration pipeline.
    
    Tests complete application startup scenarios including:
    - Service initialization order with configuration dependencies
    - Bootstrap logging coordination before real logging is available
    - Graceful degradation when optional config services fail
    - Configuration hot-reloading and service reconfiguration
    """
    
    def setup_services(self):
        """Initialize all services for bootstrap integration testing."""
        super().setup_services()
        
        # All configuration services for bootstrap testing
        self.config_service = self.container.config_service()
        # app_config_service already initialized in base class
        
        # Optional services that may not be available
        self.storage_config_service = self.container.storage_config_service()
        self.llm_routing_config_service = self.container.llm_routing_config_service()
        
        # Additional services involved in bootstrap
        self.application_bootstrap_service = self.container.application_bootstrap_service()
        
        # Track bootstrap events for testing
        self.bootstrap_events = []
    
    # =============================================================================
    # 1. Application Bootstrap Order Tests
    # =============================================================================
    
    def test_service_initialization_order(self):
        """Test configuration services initialize in correct dependency order."""
        # Create comprehensive bootstrap configuration
        bootstrap_config = {
            "logging": {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "bootstrap": {
                        "format": "[BOOTSTRAP] [%(asctime)s] %(levelname)s: %(message)s"
                    },
                    "standard": {
                        "format": "[%(asctime)s] %(name)s - %(levelname)s: %(message)s"
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO",
                        "formatter": "standard"
                    },
                    "bootstrap_console": {
                        "class": "logging.StreamHandler",
                        "level": "DEBUG",
                        "formatter": "bootstrap"
                    }
                },
                "loggers": {
                    "agentmap.bootstrap": {
                        "level": "DEBUG",
                        "handlers": ["bootstrap_console"],
                        "propagate": False
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["console"]
                }
            },
            "llm": {
                "anthropic": {
                    "api_key": "bootstrap_test_key",
                    "model": "claude-3-5-sonnet-20241022"
                }
            },
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    "anthropic": {
                        "low": "claude-3-haiku-20240307",
                        "medium": "claude-3-5-sonnet-20241022",
                        "high": "claude-3-opus-20240229",
                        "critical": "claude-3-opus-20240229"
                    }
                }
            },
            "execution": {
                "max_retries": 3,
                "timeout": 30
            },
            "storage_config_path": str(Path(self.temp_dir) / "bootstrap_storage.yaml")
        }
        
        # Create storage configuration
        bootstrap_storage_config = {
            "csv": {
                "default_directory": str(Path(self.temp_dir) / "csv_data"),
                "collections": {}
            },
            "vector": {
                "default_provider": "chroma",
                "collections": {}
            }
        }
        
        config_path = Path(self.temp_dir) / "bootstrap_config.yaml"
        storage_config_path = Path(self.temp_dir) / "bootstrap_storage.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(bootstrap_config, f)
        with open(storage_config_path, 'w') as f:
            yaml.dump(bootstrap_storage_config, f)
        
        # Test bootstrap initialization order using fresh container
        from agentmap.di import initialize_application
        
        # Initialize application with comprehensive config
        bootstrap_container = initialize_application(str(config_path))
        
        # Verify services are initialized in correct order
        
        # Level 1: Infrastructure services (ConfigService)
        bootstrap_config_service = bootstrap_container.config_service()
        self.assert_service_created(bootstrap_config_service, "ConfigService")
        
        # Level 2: Domain configuration services (AppConfigService)
        bootstrap_app_config = bootstrap_container.app_config_service()
        self.assert_service_created(bootstrap_app_config, "AppConfigService")
        
        # Level 3: Logging service (depends on app config)
        bootstrap_logging_service = bootstrap_container.logging_service()
        self.assert_service_created(bootstrap_logging_service, "LoggingService")
        
        # Level 4: Optional services (StorageConfigService, LlmRoutingConfigService)
        try:
            bootstrap_storage_config_service = bootstrap_container.storage_config_service()
            if bootstrap_storage_config_service is not None:
                self.assert_service_created(bootstrap_storage_config_service, "StorageConfigService")
        except Exception:
            pass  # Storage config may not be available
        
        bootstrap_routing_config = bootstrap_container.llm_routing_config_service()
        self.assert_service_created(bootstrap_routing_config, "LLMRoutingConfigService")
        
        # Level 5: Application services that depend on configuration
        bootstrap_app_bootstrap = bootstrap_container.application_bootstrap_service()
        self.assert_service_created(bootstrap_app_bootstrap, "ApplicationBootstrapService")
        
        # Verify configuration consistency across all services
        self.assertEqual(
            bootstrap_config_service.load_config(config_path),
            bootstrap_config,
            "ConfigService should load consistent configuration"
        )
        
        # Verify app config provides processed configuration
        llm_config = bootstrap_app_config.get_llm_config("anthropic")
        self.assertEqual(llm_config['model'], "claude-3-5-sonnet-20241022")
        
        routing_config = bootstrap_app_config.get_routing_config()
        self.assertTrue(routing_config['enabled'])
    
    def test_bootstrap_logging_coordination(self):
        """Test bootstrap logging coordination before real logging is available."""
        # Create config with complex logging setup
        logging_config = {
            "logging": {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "detailed": {
                        "format": "[%(asctime)s] %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "DEBUG",
                        "formatter": "detailed"
                    }
                },
                "loggers": {
                    "agentmap": {
                        "level": "DEBUG",
                        "handlers": ["console"],
                        "propagate": False
                    },
                    "config.bootstrap": {
                        "level": "DEBUG", 
                        "handlers": ["console"],
                        "propagate": False
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["console"]
                }
            },
            "llm": {
                "anthropic": {
                    "api_key": "logging_test_key",
                    "model": "claude-3-5-sonnet-20241022"
                }
            }
        }
        
        config_path = Path(self.temp_dir) / "logging_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(logging_config, f)
        
        # Test bootstrap logging sequence
        from agentmap.services.config.config_service import ConfigService
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.logging_service import LoggingService
        
        # Step 1: ConfigService with bootstrap logging
        config_service = ConfigService()
        self.assert_service_has_logging(config_service, "ConfigService")
        
        # Step 2: AppConfigService with bootstrap logging
        app_config = AppConfigService(config_service, config_path)
        self.assert_service_has_logging(app_config, "AppConfigService")
        
        # Step 3: LoggingService initialization
        logging_config_data = app_config.get_logging_config()
        logging_service = LoggingService(logging_config_data)
        logging_service.initialize()
        
        # Step 4: Replace bootstrap loggers with real loggers
        real_config_logger = logging_service.get_logger("agentmap.config")
        real_app_config_logger = logging_service.get_logger("agentmap.app_config")
        
        # Test logger replacement
        config_service.replace_logger(real_config_logger)
        app_config.replace_logger(real_app_config_logger)
        
        # Verify logging works after replacement
        self.assert_service_has_logging(config_service, "ConfigService")
        self.assert_service_has_logging(app_config, "AppConfigService")
        
        # Test that services can log without errors
        try:
            # These should not raise exceptions
            test_config_data = {"test": "value"}
            test_path = Path(self.temp_dir) / "logging_test.yaml"
            with open(test_path, 'w') as f:
                yaml.dump(test_config_data, f)
            
            loaded_test = config_service.load_config(test_path)
            self.assertEqual(loaded_test, test_config_data)
            
            test_value = app_config.get_value("test")
            # Test value might be None if not in the loaded config, which is fine
            
        except Exception as e:
            self.fail(f"Logging coordination should not cause errors: {e}")
    
    def test_configuration_service_initialization_dependencies(self):
        """Test configuration service dependencies are resolved correctly during bootstrap."""
        # Create config that tests service dependencies
        dependency_config = {
            "llm": {
                "anthropic": {
                    "api_key": "dependency_test_key",
                    "model": "claude-3-5-sonnet-20241022"
                },
                "openai": {
                    "api_key": "openai_dependency_key",
                    "model": "gpt-4"
                }
            },
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    "anthropic": {
                        "low": "claude-3-haiku-20240307",
                        "medium": "claude-3-5-sonnet-20241022",
                        "high": "claude-3-opus-20240229",
                        "critical": "claude-3-opus-20240229"
                    },
                    "openai": {
                        "low": "gpt-3.5-turbo",
                        "medium": "gpt-4",
                        "high": "gpt-4",
                        "critical": "gpt-4"
                    }
                },
                "task_types": {
                    "general": {
                        "provider_preference": ["anthropic", "openai"],
                        "default_complexity": "medium"
                    }
                }
            },
            "storage_config_path": str(Path(self.temp_dir) / "dependency_storage.yaml")
        }
        
        # Create storage config that depends on main config
        dependency_storage_config = {
            "csv": {
                "default_directory": "test_csv",
                "collections": {
                    "test_collection": {
                        "file_path": "test.csv"
                    }
                }
            }
        }
        
        config_path = Path(self.temp_dir) / "dependency_config.yaml"
        storage_config_path = Path(self.temp_dir) / "dependency_storage.yaml"
        
        with open(config_path, 'w') as f:
            yaml.dump(dependency_config, f)
        with open(storage_config_path, 'w') as f:
            yaml.dump(dependency_storage_config, f)
        
        # Test service dependency resolution during bootstrap
        from agentmap.services.config.config_service import ConfigService
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.config.storage_config_service import StorageConfigService
        from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
        from agentmap.services.logging_service import LoggingService
        
        # Initialize services in dependency order
        config_service = ConfigService()
        app_config = AppConfigService(config_service, config_path)
        
        # Initialize logging before routing service
        logging_config = app_config.get_logging_config()
        logging_service = LoggingService(logging_config)
        logging_service.initialize()
        
        # StorageConfigService depends on ConfigService and path from AppConfigService
        try:
            storage_config = StorageConfigService(config_service, storage_config_path)
            self.assert_service_created(storage_config, "StorageConfigService")
        except StorageConfigurationNotAvailableException:
            storage_config = None
        
        # LlmRoutingConfigService depends on AppConfigService and LoggingService
        routing_config_service = LLMRoutingConfigService(app_config, logging_service)
        self.assert_service_created(routing_config_service, "LLMRoutingConfigService")
        
        # Verify dependency resolution worked correctly
        
        # AppConfigService should provide data for other services
        routing_config = app_config.get_routing_config()
        self.assertTrue(routing_config['enabled'])
        
        # LlmRoutingConfigService should use AppConfigService data
        available_providers = routing_config_service.get_available_providers()
        self.assertIsInstance(available_providers, list)
        
        # Verify provider preferences resolve correctly
        general_providers = routing_config_service.get_provider_preference("general")
        self.assertIsInstance(general_providers, list)
        
        # Each provider in routing should be available in LLM config
        for provider in general_providers[:2]:  # Check first 2 providers
            llm_provider_config = app_config.get_llm_config(provider)
            self.assertIsInstance(llm_provider_config, dict)
            if llm_provider_config:  # May be empty in test environment
                self.assertIn('api_key', llm_provider_config)
        
        # StorageConfigService should work independently if available
        if storage_config:
            csv_config = storage_config.get_csv_config()
            self.assertIsInstance(csv_config, dict)
            self.assertEqual(csv_config['default_directory'], "test_csv")
    
    # =============================================================================
    # 2. Graceful Degradation Tests
    # =============================================================================
    
    def test_graceful_degradation_storage_unavailable(self):
        """Test graceful degradation when storage configuration is unavailable."""
        # Create config without storage configuration
        no_storage_config = {
            "logging": {
                "version": 1,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO"
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["console"]
                }
            },
            "llm": {
                "anthropic": {
                    "api_key": "no_storage_test_key",
                    "model": "claude-3-5-sonnet-20241022"
                }
            },
            "routing": {
                "enabled": True
            }
            # No storage_config_path - storage should be unavailable
        }
        
        config_path = Path(self.temp_dir) / "no_storage_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(no_storage_config, f)
        
        # Test graceful degradation with missing storage
        from agentmap.di import initialize_application
        
        # Application should initialize successfully even without storage
        degraded_container = initialize_application(str(config_path))
        
        # Core services should be available
        degraded_config_service = degraded_container.config_service()
        self.assert_service_created(degraded_config_service, "ConfigService")
        
        degraded_app_config = degraded_container.app_config_service()
        self.assert_service_created(degraded_app_config, "AppConfigService")
        
        degraded_logging_service = degraded_container.logging_service()
        self.assert_service_created(degraded_logging_service, "LoggingService")
        
        # Storage service should be None (graceful degradation)
        degraded_storage_service = degraded_container.storage_service_manager()
        self.assertIsNone(degraded_storage_service, 
                         "Storage service should be None when configuration unavailable")
        
        # Storage config service should be None
        degraded_storage_config = degraded_container.storage_config_service()
        self.assertIsNone(degraded_storage_config,
                         "Storage config service should be None when configuration unavailable")
        
        # Other services should continue to work
        degraded_routing_config = degraded_container.llm_routing_config_service()
        self.assert_service_created(degraded_routing_config, "LLMRoutingConfigService")
        
        # Verify functionality still works
        llm_config = degraded_app_config.get_llm_config("anthropic")
        self.assertEqual(llm_config['model'], "claude-3-5-sonnet-20241022")
        
        routing_config = degraded_app_config.get_routing_config()
        self.assertTrue(routing_config['enabled'])
    
    def test_graceful_degradation_invalid_routing_config(self):
        """Test graceful degradation when routing configuration is invalid."""
        # Create config with invalid routing that should degrade gracefully
        invalid_routing_config = {
            "logging": {
                "version": 1,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO"
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["console"]
                }
            },
            "llm": {
                "anthropic": {
                    "api_key": "invalid_routing_test_key",
                    "model": "claude-3-5-sonnet-20241022"
                }
            },
            "routing": {
                "enabled": True,
                "routing_matrix": "invalid_format",  # Should be dict, not string
                "task_types": ["invalid", "format"]  # Should be dict, not list
            }
        }
        
        config_path = Path(self.temp_dir) / "invalid_routing_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(invalid_routing_config, f)
        
        # Test graceful degradation with invalid routing
        from agentmap.di import initialize_application
        
        # Application should initialize despite invalid routing config
        degraded_container = initialize_application(str(config_path))
        
        # Core services should work
        degraded_app_config = degraded_container.app_config_service()
        self.assert_service_created(degraded_app_config, "AppConfigService")
        
        # AppConfigService should merge user config with defaults (preserving user values even if invalid)
        routing_config = degraded_app_config.get_routing_config()
        self.assertIsInstance(routing_config, dict, "Should provide dict routing config")
        self.assertIn('enabled', routing_config, "Should have enabled setting")
        
        # User's invalid values should be preserved (AppConfigService doesn't do type validation)
        self.assertEqual(routing_config.get('routing_matrix'), "invalid_format",
                        "AppConfigService should preserve user config values even if invalid")
        self.assertEqual(routing_config.get('task_types'), ["invalid", "format"],
                        "AppConfigService should preserve user config values even if invalid")
        
        # But defaults should be merged for missing keys
        self.assertIn('complexity_analysis', routing_config,
                     "Should have default complexity analysis")
        self.assertIn('fallback', routing_config,
                     "Should have default fallback config")
        
        # LlmRoutingConfigService may fail to initialize with severely invalid config
        try:
            degraded_routing_config = degraded_container.llm_routing_config_service()
            self.assert_service_created(degraded_routing_config, "LLMRoutingConfigService")
            
            # If service initializes, it should handle invalid data gracefully
            available_providers = degraded_routing_config.get_available_providers()
            self.assertIsInstance(available_providers, list)
            
            available_task_types = degraded_routing_config.get_available_task_types()
            self.assertIsInstance(available_task_types, list)
            
        except Exception as e:
            # It's acceptable for services to fail with severely malformed configuration
            # This tests that the application can still initialize other services
            self.assertIsInstance(e, (AttributeError, ValueError, TypeError),
                                f"Expected configuration-related error, got: {type(e).__name__}: {e}")
            
            # Verify the error is related to invalid configuration format
            error_message = str(e).lower()
            self.assertTrue(
                any(keyword in error_message for keyword in ['items', 'attribute', 'format', 'type']),
                f"Error should be related to invalid configuration format: {e}"
            )
            
            print(f"\nLLMRoutingConfigService failed as expected with invalid config: {type(e).__name__}: {e}")
    
    def test_graceful_degradation_partial_service_failures(self):
        """Test graceful degradation when some services fail during bootstrap."""
        # Create config that will cause specific service failures
        partial_failure_config = {
            "logging": {
                "version": 1,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO"
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["console"]
                }
            },
            "llm": {
                "anthropic": {
                    "api_key": "partial_failure_test_key",
                    "model": "claude-3-5-sonnet-20241022"
                }
            },
            "storage_config_path": "/invalid/path/that/does/not/exist.yaml"
        }
        
        config_path = Path(self.temp_dir) / "partial_failure_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(partial_failure_config, f)
        
        # Test partial service failure handling
        from agentmap.di import initialize_application
        
        # Application should initialize with some services failing
        partial_container = initialize_application(str(config_path))
        
        # Core services should work
        partial_config_service = partial_container.config_service()
        self.assert_service_created(partial_config_service, "ConfigService")
        
        partial_app_config = partial_container.app_config_service()
        self.assert_service_created(partial_app_config, "AppConfigService")
        
        partial_logging_service = partial_container.logging_service()
        self.assert_service_created(partial_logging_service, "LoggingService")
        
        # Storage services should fail gracefully (return None)
        partial_storage_config = partial_container.storage_config_service()
        self.assertIsNone(partial_storage_config,
                         "Storage config service should be None when path invalid")
        
        partial_storage_manager = partial_container.storage_service_manager()
        self.assertIsNone(partial_storage_manager,
                         "Storage service manager should be None when config unavailable")
        
        # Other services should continue to work
        partial_routing_config = partial_container.llm_routing_config_service()
        self.assert_service_created(partial_routing_config, "LLMRoutingConfigService")
        
        # Application should be functional despite partial failures
        llm_config = partial_app_config.get_llm_config("anthropic")
        self.assertEqual(llm_config['model'], "claude-3-5-sonnet-20241022")
    
    # =============================================================================
    # 3. Configuration Hot-Reloading Tests
    # =============================================================================
    
    def test_configuration_hot_reloading_coordination(self):
        """Test configuration hot-reloading coordination across services."""
        # Create initial configuration
        initial_config = {
            "logging": {
                "version": 1,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO"
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["console"]
                }
            },
            "llm": {
                "anthropic": {
                    "api_key": "initial_key",
                    "model": "claude-3-haiku-20240307",  # Initial model
                    "temperature": 0.5
                }
            },
            "routing": {
                "enabled": False  # Initially disabled
            },
            "execution": {
                "max_retries": 2,  # Initial value
                "timeout": 20
            }
        }
        
        config_path = Path(self.temp_dir) / "hot_reload_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(initial_config, f)
        
        # Initialize services with initial config
        from agentmap.services.config.config_service import ConfigService
        from agentmap.services.config.app_config_service import AppConfigService
        
        config_service = ConfigService()
        app_config = AppConfigService(config_service, config_path)
        
        # Verify initial configuration
        initial_llm_config = app_config.get_llm_config("anthropic")
        self.assertEqual(initial_llm_config['model'], "claude-3-haiku-20240307")
        self.assertEqual(initial_llm_config['temperature'], 0.5)
        
        initial_routing_config = app_config.get_routing_config()
        self.assertFalse(initial_routing_config['enabled'])
        
        initial_execution_config = app_config.get_execution_config()
        self.assertEqual(initial_execution_config['max_retries'], 2)
        
        # Create updated configuration
        updated_config = {
            "logging": {
                "version": 1,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "DEBUG"  # Changed level
                    }
                },
                "root": {
                    "level": "DEBUG",  # Changed level
                    "handlers": ["console"]
                }
            },
            "llm": {
                "anthropic": {
                    "api_key": "updated_key",
                    "model": "claude-3-5-sonnet-20241022",  # Updated model
                    "temperature": 0.7  # Updated temperature
                },
                "openai": {  # Added new provider
                    "api_key": "new_openai_key",
                    "model": "gpt-4"
                }
            },
            "routing": {
                "enabled": True,  # Enabled routing
                "routing_matrix": {
                    "anthropic": {
                        "low": "claude-3-haiku-20240307",
                        "medium": "claude-3-5-sonnet-20241022",
                        "high": "claude-3-opus-20240229",
                        "critical": "claude-3-opus-20240229"
                    }
                }
            },
            "execution": {
                "max_retries": 5,  # Increased retries
                "timeout": 60  # Increased timeout
            }
        }
        
        # Simulate hot-reload by updating config file and reloading
        with open(config_path, 'w') as f:
            yaml.dump(updated_config, f)
        
        # Create new services to simulate reload (in real scenario, this would be coordinated)
        reloaded_app_config = AppConfigService(config_service, config_path)
        
        # Verify configuration hot-reload worked
        updated_llm_config = reloaded_app_config.get_llm_config("anthropic")
        self.assertEqual(updated_llm_config['model'], "claude-3-5-sonnet-20241022")
        self.assertEqual(updated_llm_config['temperature'], 0.7)
        
        # New provider should be available
        openai_config = reloaded_app_config.get_llm_config("openai")
        self.assertEqual(openai_config['model'], "gpt-4")
        
        updated_routing_config = reloaded_app_config.get_routing_config()
        self.assertTrue(updated_routing_config['enabled'])
        
        updated_execution_config = reloaded_app_config.get_execution_config()
        self.assertEqual(updated_execution_config['max_retries'], 5)
        self.assertEqual(updated_execution_config['timeout'], 60)
    
    def test_configuration_change_propagation(self):
        """Test configuration change propagation across dependent services."""
        # Create config with service dependencies
        dependency_config = {
            "llm": {
                "anthropic": {
                    "api_key": "dependency_key",
                    "model": "claude-3-5-sonnet-20241022"
                }
            },
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    "anthropic": {
                        "low": "claude-3-haiku-20240307",
                        "medium": "claude-3-5-sonnet-20241022",
                        "high": "claude-3-opus-20240229", 
                        "critical": "claude-3-opus-20240229"
                    }
                }
            }
        }
        
        config_path = Path(self.temp_dir) / "dependency_change_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(dependency_config, f)
        
        # Initialize dependent services
        from agentmap.services.config.config_service import ConfigService
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
        from agentmap.services.logging_service import LoggingService
        
        config_service = ConfigService()
        app_config = AppConfigService(config_service, config_path)
        
        logging_config = app_config.get_logging_config()
        logging_service = LoggingService(logging_config)
        logging_service.initialize()
        
        routing_config_service = LLMRoutingConfigService(app_config, logging_service)
        
        # Verify initial state
        initial_providers = routing_config_service.get_available_providers()
        self.assertIn('anthropic', initial_providers)
        
        # Change configuration to add new provider
        updated_dependency_config = {
            "llm": {
                "anthropic": {
                    "api_key": "dependency_key",
                    "model": "claude-3-5-sonnet-20241022"
                },
                "openai": {  # Add new provider
                    "api_key": "new_provider_key",
                    "model": "gpt-4"
                }
            },
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    "anthropic": {
                        "low": "claude-3-haiku-20240307",
                        "medium": "claude-3-5-sonnet-20241022",
                        "high": "claude-3-opus-20240229",
                        "critical": "claude-3-opus-20240229"
                    },
                    "openai": {  # Add routing for new provider
                        "low": "gpt-3.5-turbo",
                        "medium": "gpt-4",
                        "high": "gpt-4",
                        "critical": "gpt-4"
                    }
                }
            }
        }
        
        # Update config file
        with open(config_path, 'w') as f:
            yaml.dump(updated_dependency_config, f)
        
        # Create new services to simulate change propagation
        updated_app_config = AppConfigService(config_service, config_path)
        updated_routing_config_service = LLMRoutingConfigService(updated_app_config, logging_service)
        
        # Verify change propagation
        updated_providers = updated_routing_config_service.get_available_providers()
        self.assertIn('anthropic', updated_providers, "Should still have original provider")
        self.assertIn('openai', updated_providers, "Should have new provider")
        
        # Test routing to new provider
        openai_model = updated_routing_config_service.get_model_for_complexity("openai", "medium")
        self.assertEqual(openai_model, "gpt-4")
        
        # Verify LLM config is available for new provider
        openai_llm_config = updated_app_config.get_llm_config("openai")
        self.assertEqual(openai_llm_config['model'], "gpt-4")
    
    # =============================================================================
    # 4. Bootstrap Performance and Reliability Tests
    # =============================================================================
    
    def test_bootstrap_performance_with_large_config(self):
        """Test bootstrap performance with large configuration files."""
        # Create large configuration with many sections
        large_config = {
            "logging": {
                "version": 1,
                "formatters": {f"formatter_{i}": {"format": f"format_{i}"} for i in range(50)},
                "handlers": {f"handler_{i}": {"class": "logging.StreamHandler"} for i in range(50)},
                "root": {"level": "INFO", "handlers": ["handler_0"]}
            },
            "llm": {
                f"provider_{i}": {
                    "api_key": f"key_{i}",
                    "model": f"model_{i}",
                    "temperature": 0.5 + (i * 0.01)
                } for i in range(20)
            },
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    f"provider_{i}": {
                        "low": f"model_low_{i}",
                        "medium": f"model_medium_{i}",
                        "high": f"model_high_{i}",
                        "critical": f"model_critical_{i}"
                    } for i in range(20)
                },
                "task_types": {
                    f"task_type_{i}": {
                        "provider_preference": [f"provider_{j}" for j in range(min(3, 20))],
                        "default_complexity": "medium"
                    } for i in range(50)
                }
            },
            "execution": {
                "max_retries": 3,
                "timeout": 30
            }
        }
        
        config_path = Path(self.temp_dir) / "large_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(large_config, f)
        
        # Test bootstrap performance
        start_time = time.time()
        
        from agentmap.di import initialize_application
        large_container = initialize_application(str(config_path))
        
        initialization_time = time.time() - start_time
        
        # Verify services initialized correctly
        large_config_service = large_container.config_service()
        self.assert_service_created(large_config_service, "ConfigService")
        
        large_app_config = large_container.app_config_service()
        self.assert_service_created(large_app_config, "AppConfigService")
        
        large_routing_config = large_container.llm_routing_config_service()
        self.assert_service_created(large_routing_config, "LLMRoutingConfigService")
        
        # Verify configuration was loaded correctly
        routing_config = large_app_config.get_routing_config()
        self.assertTrue(routing_config['enabled'])
        
        # Should have multiple providers available
        available_providers = large_routing_config.get_available_providers()
        self.assertGreater(len(available_providers), 10, "Should have many providers loaded")
        
        # Bootstrap should complete in reasonable time (adjust threshold as needed)
        self.assertLess(initialization_time, 5.0, 
                       f"Bootstrap should complete quickly, took {initialization_time:.2f}s")
        
        print(f"\\nBootstrap performance test: {initialization_time:.3f}s for large config")
    
    def test_bootstrap_reliability_with_concurrent_access(self):
        """Test bootstrap reliability under concurrent access scenarios."""
        # Create shared configuration
        concurrent_config = {
            "logging": {
                "version": 1,
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "level": "INFO"
                    }
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["console"]
                }
            },
            "llm": {
                "anthropic": {
                    "api_key": "concurrent_test_key",
                    "model": "claude-3-5-sonnet-20241022"
                }
            },
            "routing": {
                "enabled": True
            }
        }
        
        config_path = Path(self.temp_dir) / "concurrent_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(concurrent_config, f)
        
        # Test concurrent bootstrap initialization
        results = []
        errors = []
        
        def bootstrap_worker(worker_id):
            """Worker function for concurrent bootstrap testing."""
            try:
                from agentmap.di import initialize_application
                container = initialize_application(str(config_path))
                
                # Verify services work
                config_service = container.config_service()
                app_config = container.app_config_service()
                
                llm_config = app_config.get_llm_config("anthropic")
                
                results.append({
                    'worker_id': worker_id,
                    'success': True,
                    'model': llm_config.get('model')
                })
                
            except Exception as e:
                errors.append({
                    'worker_id': worker_id,
                    'error': str(e),
                    'error_type': type(e).__name__
                })
        
        # Run multiple concurrent bootstrap operations
        threads = []
        num_workers = 5
        
        for i in range(num_workers):
            thread = threading.Thread(target=bootstrap_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10.0)  # 10 second timeout
        
        # Verify concurrent bootstrap reliability
        self.assertEqual(len(errors), 0, f"No errors should occur in concurrent bootstrap: {errors}")
        self.assertEqual(len(results), num_workers, f"All workers should complete successfully")
        
        # Verify all workers got consistent results
        models = [result['model'] for result in results]
        self.assertTrue(all(model == "claude-3-5-sonnet-20241022" for model in models),
                       "All workers should get consistent configuration")
        
        print(f"\\nConcurrent bootstrap test: {len(results)}/{num_workers} workers succeeded")


if __name__ == '__main__':
    unittest.main()
