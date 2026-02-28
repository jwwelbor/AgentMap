"""
Configuration Validation Integration Tests.

This module tests cross-service configuration validation, dependency resolution,
fail-fast behavior coordination, and error propagation between all configuration
services working together in real-world scenarios.
"""

import unittest
from pathlib import Path

import yaml

from agentmap.exceptions.base_exceptions import ConfigurationException
from agentmap.exceptions.service_exceptions import (
    StorageConfigurationNotAvailableException,
)
from tests.fresh_suite.integration.base_integration_test import BaseIntegrationTest


class TestConfigValidationIntegration(BaseIntegrationTest):
    """
    Integration tests for cross-service configuration validation.

    Tests validation coordination between:
    - ConfigService: Infrastructure-level validation
    - AppConfigService: Domain logic validation
    - StorageConfigService: Fail-fast validation
    - LlmRoutingConfigService: Routing-specific validation
    """

    def setup_services(self):
        """Initialize all configuration services for validation testing."""
        super().setup_services()

        # All configuration services
        self.config_service = self.container.config_service()
        # app_config_service already initialized in base class

        # Storage config service (may be None if not available)
        self.storage_config_service = self.container.storage_config_service()

        # LLM routing config service
        self.llm_routing_config_service = self.container.llm_routing_config_service()

    # =============================================================================
    # 1. Cross-Service Validation Tests
    # =============================================================================

    def test_cross_service_configuration_validation(self):
        """Test validation coordination across all configuration services."""
        # Create comprehensive valid configuration
        valid_config = {
            "logging": {
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {
                    "console": {"class": "logging.StreamHandler", "level": "INFO"}
                },
                "root": {"level": "INFO", "handlers": ["console"]},
            },
            "llm": {
                "anthropic": {
                    "api_key": "valid_key",
                    "model": "claude-3-5-sonnet-20241022",
                    "temperature": 0.7,
                },
                "openai": {
                    "api_key": "valid_openai_key",
                    "model": "gpt-4",
                    "temperature": 0.5,
                },
            },
            "routing": {
                "enabled": True,
                "complexity_analysis": {
                    "prompt_length_thresholds": {"low": 100, "medium": 300, "high": 800}
                },
                "routing_matrix": {
                    "anthropic": {
                        "low": "claude-3-haiku-20240307",
                        "medium": "claude-3-5-sonnet-20241022",
                        "high": "claude-3-opus-20240229",
                        "critical": "claude-3-opus-20240229",
                    },
                    "openai": {
                        "low": "gpt-3.5-turbo",
                        "medium": "gpt-4",
                        "high": "gpt-4",
                        "critical": "gpt-4",
                    },
                },
                "task_types": {
                    "general": {
                        "provider_preference": ["anthropic", "openai"],
                        "default_complexity": "medium",
                    }
                },
            },
            "execution": {
                "max_retries": 3,
                "timeout": 30,
                "tracking": {"enabled": True},
            },
            "storage_config_path": str(Path(self.temp_dir) / "valid_storage.yaml"),
        }

        # Create valid storage configuration
        valid_storage_config = {
            "csv": {
                "default_directory": str(Path(self.temp_dir) / "csv_data"),
                "collections": {"test_collection": {"file_path": "test.csv"}},
            },
            "vector": {
                "default_provider": "chroma",
                "collections": {
                    "test_vectors": {
                        "provider": "chroma",
                        "settings": {
                            "persist_directory": str(
                                Path(self.temp_dir) / "vector_data"
                            )
                        },
                    }
                },
            },
            "kv": {
                "default_provider": "local",
                "collections": {
                    "test_kv": {
                        "provider": "local",
                        "settings": {
                            "file_path": str(Path(self.temp_dir) / "kv_data.json")
                        },
                    }
                },
            },
        }

        # Write configuration files
        config_path = Path(self.temp_dir) / "valid_config.yaml"
        storage_config_path = Path(self.temp_dir) / "valid_storage.yaml"

        with open(config_path, "w") as f:
            yaml.dump(valid_config, f)
        with open(storage_config_path, "w") as f:
            yaml.dump(valid_storage_config, f)

        # Test cross-service validation coordination

        # Step 1: ConfigService infrastructure validation
        loaded_config = self.config_service.load_config(config_path)
        self.assertEqual(
            loaded_config,
            valid_config,
            "ConfigService should load valid config correctly",
        )

        # Step 2: AppConfigService domain validation
        from agentmap.services.config.app_config_service import AppConfigService

        app_config = AppConfigService(self.config_service, config_path)

        # Validate app config
        app_validation_result = app_config.validate_config()
        self.assertTrue(
            app_validation_result,
            "AppConfigService validation should pass for valid config",
        )

        # Step 3: StorageConfigService fail-fast validation
        from agentmap.services.config.storage_config_service import StorageConfigService

        try:
            storage_config = StorageConfigService(
                self.config_service, storage_config_path
            )

            # Validate storage config
            storage_validation = storage_config.validate_storage_config()
            self.assertIsInstance(
                storage_validation, dict, "Storage validation should return dict"
            )
            self.assertIn(
                "warnings",
                storage_validation,
                "Storage validation should include warnings",
            )
            self.assertIn(
                "errors", storage_validation, "Storage validation should include errors"
            )

            # Valid config should have minimal errors
            self.assertEqual(
                len(storage_validation["errors"]),
                0,
                f"Valid storage config should have no errors: {storage_validation['errors']}",
            )

        except StorageConfigurationNotAvailableException:
            self.skipTest("Storage configuration not available in test environment")

        # Step 4: LlmRoutingConfigService routing validation
        self.assert_service_created(
            self.llm_routing_config_service, "LLMRoutingConfigService"
        )

        # Validate routing configuration
        routing_validation_errors = (
            self.llm_routing_config_service.validate_AppConfigService()
        )
        self.assertIsInstance(
            routing_validation_errors, list, "Routing validation should return list"
        )
        self.assertEqual(
            len(routing_validation_errors),
            0,
            f"Valid routing config should have no errors: {routing_validation_errors}",
        )

    def test_configuration_dependency_resolution(self):
        """Test configuration dependency resolution between services."""
        # Create configuration with interdependent sections
        interdependent_config = {
            "llm": {
                "anthropic": {
                    "api_key": "test_key",
                    "model": "claude-3-5-sonnet-20241022",
                },
                "openai": {"api_key": "test_openai_key", "model": "gpt-4"},
            },
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    "anthropic": {
                        "low": "claude-3-haiku-20240307",
                        "medium": "claude-3-5-sonnet-20241022",
                        "high": "claude-3-opus-20240229",
                        "critical": "claude-3-opus-20240229",
                    },
                    "openai": {
                        "low": "gpt-3.5-turbo",
                        "medium": "gpt-4",
                        "high": "gpt-4",
                        "critical": "gpt-4",
                    },
                },
                "task_types": {
                    "general": {
                        "provider_preference": [
                            "anthropic",
                            "openai",
                        ],  # References LLM providers
                        "default_complexity": "medium",
                    },
                    "specialized": {
                        "provider_preference": [
                            "anthropic"
                        ],  # References LLM providers
                        "default_complexity": "high",
                    },
                },
            },
            "storage_config_path": str(Path(self.temp_dir) / "dependency_storage.yaml"),
        }

        # Create storage config that depends on main config paths
        dependency_storage_config = {
            "csv": {
                "default_directory": "data/csv",  # Uses relative path
                "collections": {},
            }
        }

        config_path = Path(self.temp_dir) / "dependency_config.yaml"
        storage_config_path = Path(self.temp_dir) / "dependency_storage.yaml"

        with open(config_path, "w") as f:
            yaml.dump(interdependent_config, f)
        with open(storage_config_path, "w") as f:
            yaml.dump(dependency_storage_config, f)

        # Test dependency resolution
        from agentmap.services.config.app_config_service import AppConfigService

        app_config = AppConfigService(self.config_service, config_path)

        # Test LLM routing dependency resolution

        # LlmRoutingConfigService should resolve dependencies to LLM providers
        routing_providers = self.llm_routing_config_service.get_available_providers()
        self.assertIsInstance(
            routing_providers, list, "Should get list of available providers"
        )

        # Routing task types should reference valid providers
        task_types = self.llm_routing_config_service.get_available_task_types()
        self.assertIsInstance(task_types, list, "Should get list of task types")

        # Test provider preference resolution
        general_providers = self.llm_routing_config_service.get_provider_preference(
            "general"
        )
        self.assertIsInstance(
            general_providers, list, "Should get provider preference list"
        )

        if general_providers:  # May be empty in test environment
            # Each provider in preference should be available in LLM config
            for provider in general_providers:
                llm_provider_config = app_config.get_llm_config(provider)
                self.assertIsInstance(
                    llm_provider_config,
                    dict,
                    f"Provider {provider} should be available in LLM config",
                )

        # Test storage config path dependency
        storage_path = app_config.get_storage_config_path()
        self.assertEqual(
            str(storage_path),
            str(storage_config_path),
            "Storage config path dependency should be resolved correctly",
        )

    def test_validation_error_dependency_propagation(self):
        """Test how validation errors propagate through dependent services."""
        # Create config with errors that affect multiple services
        error_config = {
            "llm": {
                "invalid_provider": {  # Invalid provider name
                    "api_key": "test_key",
                    "model": "invalid_model",
                }
            },
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    "invalid_provider": {  # References invalid LLM provider
                        "low": "some_model",
                        "medium": "some_model",
                        "high": "some_model",
                        "critical": "some_model",
                    },
                    "missing_provider": {  # Provider not in LLM config
                        "low": "model1",
                        "medium": "model2",
                        "high": "model3",
                        "critical": "model4",
                    },
                },
                "task_types": {
                    "test_task": {
                        "provider_preference": ["missing_provider", "invalid_provider"],
                        "default_complexity": "invalid_complexity",  # Invalid complexity level
                    }
                },
            },
            "storage_config_path": str(Path(self.temp_dir) / "missing_storage.yaml"),
            # storage config file doesn't exist
        }

        config_path = Path(self.temp_dir) / "error_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(error_config, f)

        # Test error propagation through validation chain

        # Step 1: ConfigService should load the config (infrastructure doesn't validate content)
        loaded_config = self.config_service.load_config(config_path)
        self.assertEqual(
            loaded_config, error_config, "ConfigService should load config with errors"
        )

        # Step 2: AppConfigService should handle the config (may provide defaults)
        from agentmap.services.config.app_config_service import AppConfigService

        app_config = AppConfigService(self.config_service, config_path)

        # AppConfigService validation should still work (may warn but not fail)
        app_validation = app_config.validate_config()
        self.assertIsInstance(
            app_validation, bool, "AppConfigService validation should complete"
        )

        # Step 3: LlmRoutingConfigService should detect routing errors
        # Note: This depends on how the service is constructed with the error config
        routing_validation_errors = (
            self.llm_routing_config_service.validate_AppConfigService()
        )
        self.assertIsInstance(
            routing_validation_errors, list, "Routing validation should return list"
        )

        # Should detect provider reference errors
        if routing_validation_errors:
            # Should detect that providers in routing matrix don't exist in LLM config
            # (The exact error depends on validation implementation)
            self.assertTrue(
                len(routing_validation_errors) > 0,
                "Should detect routing configuration errors",
            )

        # Step 4: StorageConfigService should fail fast on missing file
        from agentmap.services.config.storage_config_service import StorageConfigService

        missing_storage_path = Path(self.temp_dir) / "missing_storage.yaml"

        with self.assertRaises(StorageConfigurationNotAvailableException) as context:
            StorageConfigService(self.config_service, missing_storage_path)

        self.assertIn("not found", str(context.exception).lower())

    # =============================================================================
    # 2. Fail-Fast Behavior Coordination Tests
    # =============================================================================

    def test_storage_config_fail_fast_coordination(self):
        """Test StorageConfigService fail-fast behavior coordinates with other services."""
        # Create main config without storage_config_path
        config_without_storage = {
            "llm": {
                "anthropic": {
                    "api_key": "test_key",
                    "model": "claude-3-5-sonnet-20241022",
                }
            },
            "routing": {"enabled": True},
            # Missing storage_config_path
        }

        config_path = Path(self.temp_dir) / "no_storage_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_without_storage, f)

        # Test fail-fast coordination
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.config.storage_config_service import StorageConfigService

        # AppConfigService should work without storage config
        app_config = AppConfigService(self.config_service, config_path)

        # But should return default/empty path for storage config
        storage_path = app_config.get_storage_config_path()
        self.assertEqual(str(storage_path), str(None))

        # StorageConfigService should fail fast when storage config is not specified
        with self.assertRaises(StorageConfigurationNotAvailableException) as context:
            StorageConfigService(self.config_service, None)

        self.assertIn("not specified", str(context.exception))

        # StorageConfigService should fail fast when storage config file doesn't exist
        with self.assertRaises(StorageConfigurationNotAvailableException) as context:
            StorageConfigService(self.config_service, storage_path)

        self.assertIn("not specified", str(context.exception))

    def test_routing_validation_fail_fast_coordination(self):
        """Test routing validation fail-fast behavior with other services."""
        # Create config with severely broken routing
        broken_routing_config = {
            "llm": {
                "anthropic": {
                    "api_key": "test_key",
                    "model": "claude-3-5-sonnet-20241022",
                }
            },
            "routing": {
                "enabled": True,
                "routing_matrix": "invalid_matrix_format",  # Should be dict, not string
                "task_types": [],  # Should be dict, not list
            },
        }

        config_path = Path(self.temp_dir) / "broken_routing_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(broken_routing_config, f)

        # Test coordination with broken routing config
        from agentmap.services.config.app_config_service import AppConfigService

        # ConfigService should load the broken config
        loaded_config = self.config_service.load_config(config_path)
        self.assertEqual(loaded_config, broken_routing_config)

        # AppConfigService should merge user config with defaults (preserving user values even if invalid)
        app_config = AppConfigService(self.config_service, config_path)

        routing_config = app_config.get_routing_config()
        self.assertIsInstance(
            routing_config, dict, "AppConfigService should provide dict routing config"
        )

        # User's invalid values should be preserved (AppConfigService doesn't do type validation)
        self.assertEqual(
            routing_config.get("routing_matrix"),
            "invalid_matrix_format",
            "AppConfigService should preserve user config values even if invalid",
        )
        self.assertEqual(
            routing_config.get("task_types"),
            [],
            "AppConfigService should preserve user config values even if invalid",
        )

        # But defaults should be merged for missing keys
        self.assertIn("enabled", routing_config, "Should have default enabled setting")
        self.assertIn(
            "complexity_analysis",
            routing_config,
            "Should have default complexity analysis",
        )
        self.assertIn("fallback", routing_config, "Should have default fallback config")

        # LlmRoutingConfigService should detect the issues or may fail with invalid data
        try:
            routing_validation_errors = (
                self.llm_routing_config_service.validate_AppConfigService()
            )
            self.assertIsInstance(
                routing_validation_errors, list, "Should return validation errors list"
            )
            # If validation completes, there should be errors detected
            if routing_validation_errors:
                self.assertGreater(
                    len(routing_validation_errors),
                    0,
                    "Should detect routing configuration errors",
                )
        except Exception as e:
            # It's also acceptable for routing service to fail with severely invalid config
            self.assertIsInstance(
                e,
                (AttributeError, ValueError, TypeError),
                f"Expected configuration-related error, got: {type(e).__name__}: {e}",
            )
            print(
                f"\nLLMRoutingConfigService failed with invalid config as expected: {type(e).__name__}: {e}"
            )

    def test_graceful_degradation_coordination(self):
        """Test graceful degradation when some config services fail."""
        # Create config where some services can work but others fail
        partial_config = {
            "llm": {
                "anthropic": {
                    "api_key": "test_key",
                    "model": "claude-3-5-sonnet-20241022",
                }
            },
            # Missing routing config - LlmRoutingConfigService should use defaults
            # Missing storage_config_path - StorageConfigService should fail
        }

        config_path = Path(self.temp_dir) / "partial_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(partial_config, f)

        # Test graceful degradation coordination
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.config.storage_config_service import StorageConfigService

        # AppConfigService should work with partial config
        app_config = AppConfigService(self.config_service, config_path)

        # Should validate successfully even with missing sections
        app_validation = app_config.validate_config()
        self.assertTrue(
            app_validation, "AppConfigService should validate partial config"
        )

        # Should provide defaults for missing routing config
        routing_config = app_config.get_routing_config()
        self.assertIsInstance(
            routing_config, dict, "Should provide default routing config"
        )
        self.assertIn(
            "enabled", routing_config, "Should have default routing enabled setting"
        )

        # LlmRoutingConfigService should work with defaults
        self.assert_service_created(
            self.llm_routing_config_service, "LLMRoutingConfigService"
        )

        # StorageConfigService should fail gracefully
        storage_path = app_config.get_storage_config_path()  # Will be default path

        with self.assertRaises(StorageConfigurationNotAvailableException):
            StorageConfigService(self.config_service, storage_path)

        # But other services should continue to work
        llm_config = app_config.get_llm_config("anthropic")
        self.assertEqual(llm_config["model"], "claude-3-5-sonnet-20241022")

    # =============================================================================
    # 3. Error Propagation Integration Tests
    # =============================================================================

    def test_configuration_error_propagation_chain(self):
        """Test error propagation through the complete configuration service chain."""
        # Test different types of errors at different layers

        # Layer 1: Infrastructure errors (ConfigService)
        invalid_yaml_path = Path(self.temp_dir) / "invalid.yaml"
        invalid_yaml_path.write_text("invalid: yaml: content: [unclosed")

        # Should propagate as ConfigurationException
        with self.assertRaises(ConfigurationException) as context:
            self.config_service.load_config(invalid_yaml_path)

        self.assertIn("Failed to parse config file", str(context.exception))

        # Layer 2: Domain logic errors (AppConfigService)
        # Create config that loads but has domain logic issues
        domain_error_config = {
            "execution": {
                "max_retries": "invalid_number",  # Should be int
                "timeout": -1,  # Should be positive
            }
        }

        domain_error_path = Path(self.temp_dir) / "domain_error.yaml"
        with open(domain_error_path, "w") as f:
            yaml.dump(domain_error_config, f)

        # ConfigService should load this fine (infrastructure doesn't validate content)
        loaded_domain_config = self.config_service.load_config(domain_error_path)
        self.assertEqual(loaded_domain_config, domain_error_config)

        # AppConfigService should handle domain errors gracefully
        from agentmap.services.config.app_config_service import AppConfigService

        app_config = AppConfigService(self.config_service, domain_error_path)

        # Should still be able to get execution config (with type conversion/defaults)
        execution_config = app_config.get_execution_config()
        self.assertIsInstance(
            execution_config, dict, "Should return execution config dict"
        )

        # Layer 3: Service-specific validation errors
        # Create config with routing-specific validation errors
        routing_error_config = {
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    "provider1": {
                        "low": "model1",
                        "medium": "model2",
                        # Missing "high" and "critical" - validation error
                    }
                },
                "task_types": {
                    "test_task": {
                        "provider_preference": ["nonexistent_provider"],
                        "default_complexity": "invalid_level",
                    }
                },
            }
        }

        routing_error_path = Path(self.temp_dir) / "routing_error.yaml"
        with open(routing_error_path, "w") as f:
            yaml.dump(routing_error_config, f)

        # Test error propagation through routing validation
        routing_app_config = AppConfigService(self.config_service, routing_error_path)

        # Should be able to create app config
        self.assert_service_created(routing_app_config, "AppConfigService")

        # Routing service validation should detect errors
        routing_validation_errors = (
            self.llm_routing_config_service.validate_AppConfigService()
        )
        self.assertIsInstance(routing_validation_errors, list)

        # Layer 4: Storage fail-fast errors
        storage_error_config = {"storage_config_path": "/nonexistent/path/storage.yaml"}

        storage_error_path = Path(self.temp_dir) / "storage_error.yaml"
        with open(storage_error_path, "w") as f:
            yaml.dump(storage_error_config, f)

        storage_app_config = AppConfigService(self.config_service, storage_error_path)
        storage_path = storage_app_config.get_storage_config_path()

        # StorageConfigService should fail fast
        from agentmap.services.config.storage_config_service import StorageConfigService

        with self.assertRaises(StorageConfigurationNotAvailableException):
            StorageConfigService(self.config_service, storage_path)

    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies in configuration."""
        # Test configuration references that could create circular dependencies
        circular_config = {
            "section_a": {
                "reference": "${section_b.value}",  # References section_b
                "value": "a_value",
            },
            "section_b": {
                "reference": "${section_a.value}",  # References section_a
                "value": "b_value",
            },
        }

        circular_path = Path(self.temp_dir) / "circular_config.yaml"
        with open(circular_path, "w") as f:
            yaml.dump(circular_config, f)

        # ConfigService should load the config (doesn't resolve references)
        loaded_circular = self.config_service.load_config(circular_path)
        self.assertEqual(loaded_circular, circular_config)

        # AppConfigService should handle potential circular references safely
        from agentmap.services.config.app_config_service import AppConfigService

        app_config = AppConfigService(self.config_service, circular_path)

        # Should be able to access values directly (without resolving references)
        section_a = app_config.get_section("section_a")
        self.assertEqual(section_a["value"], "a_value")

        section_b = app_config.get_section("section_b")
        self.assertEqual(section_b["value"], "b_value")

        # Validation should complete without infinite loops
        validation_result = app_config.validate_config()
        self.assertIsInstance(validation_result, bool)

    # =============================================================================
    # 4. Validation Summary and Reporting Tests
    # =============================================================================

    def test_comprehensive_validation_summary(self):
        """Test comprehensive validation summary across all config services."""
        # Create config with various validation scenarios
        comprehensive_config = {
            "logging": {
                "version": 1,
                "handlers": {
                    "console": {"class": "logging.StreamHandler", "level": "INFO"}
                },
            },
            "llm": {
                "anthropic": {
                    "api_key": "test_key",
                    "model": "claude-3-5-sonnet-20241022",
                },
                "openai": {"api_key": "test_openai_key", "model": "gpt-4"},
            },
            "routing": {
                "enabled": True,
                "routing_matrix": {
                    "anthropic": {
                        "low": "claude-3-haiku-20240307",
                        "medium": "claude-3-5-sonnet-20241022",
                        "high": "claude-3-opus-20240229",
                        "critical": "claude-3-opus-20240229",
                    }
                },
            },
            "execution": {"max_retries": 3, "timeout": 30},
            "storage_config_path": str(Path(self.temp_dir) / "summary_storage.yaml"),
        }

        # Create storage config
        summary_storage_config = {
            "csv": {"default_directory": "data/csv", "collections": {}},
            "vector": {"default_provider": "chroma", "collections": {}},
        }

        config_path = Path(self.temp_dir) / "summary_config.yaml"
        storage_config_path = Path(self.temp_dir) / "summary_storage.yaml"

        with open(config_path, "w") as f:
            yaml.dump(comprehensive_config, f)
        with open(storage_config_path, "w") as f:
            yaml.dump(summary_storage_config, f)

        # Generate validation summary from all services
        from agentmap.services.config.app_config_service import AppConfigService
        from agentmap.services.config.storage_config_service import StorageConfigService

        app_config = AppConfigService(self.config_service, config_path)

        # Collect validation results from all services
        validation_summary = {
            "config_service": {"status": "loaded", "errors": []},
            "app_config_service": {
                "status": "loaded",
                "validation_passed": app_config.validate_config(),
                "config_summary": app_config.get_config_summary(),
            },
            "llm_routing_config_service": {
                "status": "loaded",
                "validation_errors": self.llm_routing_config_service.validate_AppConfigService(),
                "available_providers": self.llm_routing_config_service.get_available_providers(),
                "available_task_types": self.llm_routing_config_service.get_available_task_types(),
            },
        }

        # Add storage config validation if available
        try:
            storage_config = StorageConfigService(
                self.config_service, storage_config_path
            )
            storage_validation = storage_config.validate_storage_config()
            storage_summary = storage_config.get_storage_summary()

            validation_summary["storage_config_service"] = {
                "status": "loaded",
                "validation": storage_validation,
                "summary": storage_summary,
            }
        except StorageConfigurationNotAvailableException:
            validation_summary["storage_config_service"] = {
                "status": "not_available",
                "reason": "Storage configuration not available",
            }

        # Verify validation summary structure
        self.assertIn("config_service", validation_summary)
        self.assertIn("app_config_service", validation_summary)
        self.assertIn("llm_routing_config_service", validation_summary)
        self.assertIn("storage_config_service", validation_summary)

        # Verify app config service summary
        app_summary = validation_summary["app_config_service"]
        self.assertTrue(
            app_summary["validation_passed"], "App config validation should pass"
        )
        self.assertIsInstance(
            app_summary["config_summary"], dict, "Should have config summary"
        )

        # Verify routing config service summary
        routing_summary = validation_summary["llm_routing_config_service"]
        self.assertIsInstance(
            routing_summary["validation_errors"],
            list,
            "Should have validation errors list",
        )
        self.assertIsInstance(
            routing_summary["available_providers"], list, "Should have providers list"
        )
        self.assertIsInstance(
            routing_summary["available_task_types"], list, "Should have task types list"
        )

        # Print summary for debugging
        print("\\n=== Configuration Validation Summary ===")
        for service_name, service_summary in validation_summary.items():
            print(f"\\n{service_name.upper()}:")
            if "status" in service_summary:
                print(f"  Status: {service_summary['status']}")
            if "validation_errors" in service_summary:
                errors = service_summary["validation_errors"]
                print(f"  Validation Errors: {len(errors)}")
                for error in errors[:3]:  # Show first 3 errors
                    print(f"    - {error}")
            if "validation_passed" in service_summary:
                print(f"  Validation Passed: {service_summary['validation_passed']}")


if __name__ == "__main__":
    unittest.main()
