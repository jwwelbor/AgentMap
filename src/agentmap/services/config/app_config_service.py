# agentmap_data/config/app_config.py
"""
Domain service for application configuration with business logic.

Provides business logic layer for application configuration, using ConfigService
for infrastructure concerns while maintaining backward compatibility with the
existing Configuration class interface.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union

from agentmap.exceptions.base_exceptions import ConfigurationException
from agentmap.services.config.config_service import ConfigService

T = TypeVar("T")


class AppConfigService:
    """
    Domain service for application configuration with business logic.

    This service provides business logic for application configuration:
    - Loads main application config file via ConfigService
    - Provides same interface as existing Configuration class for compatibility
    - Implements bootstrap logging pattern with logger replacement
    - Adds domain-specific validation and business rules

    Storage configuration is handled by separate StorageConfigService.
    """

    def __init__(
        self,
        config_service: ConfigService,
        config_path: Optional[Union[str, Path]] = None,
    ):
        """
        Initialize AppConfigService with configuration path.

        Args:
            config_service: ConfigService instance for infrastructure operations
            config_path: Optional path to configuration file. If None, uses defaults only.
        """
        self._config_service = config_service
        self._config_data = None
        self._logger = None
        self._config_file_path = Path(config_path) if config_path else None

        # Setup bootstrap logging - will be replaced later by DI
        self._setup_bootstrap_logging()

        # Load configuration
        self._load_config(config_path)

    def _setup_bootstrap_logging(self):
        """Set up bootstrap logger for config loading before real logging is available."""
        # Only set up basic config if no handlers exist to avoid conflicts
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=os.environ.get("AGENTMAP_CONFIG_LOG_LEVEL", "INFO").upper(),
                format="(BOOTSTRAP) [%(asctime)s] %(levelname)s: %(message)s",
            )
        self._logger = logging.getLogger("bootstrap.app_config")
        self._logger.debug("[AppConfigService] Bootstrap logger initialized")

    def _load_config(self, config_path: Optional[Union[str, Path]]):
        """Load configuration using ConfigService."""
        try:
            self._logger.info("[AppConfigService] Loading application configuration")
            self._config_data = self._config_service.load_config(config_path)
            self._logger.info(
                "[AppConfigService] Application configuration loaded successfully"
            )
        except Exception as e:
            error_msg = f"Failed to load application configuration: {e}"
            self._logger.error(error_msg)
            raise ConfigurationException(error_msg) from e

    def replace_logger(self, logger: logging.Logger):
        """
        Replace bootstrap logger with real logger once logging service is online.

        Args:
            logger: Real logger instance from LoggingService
        """
        if logger and self._logger:
            # Clean up bootstrap logger handlers
            for handler in list(self._logger.handlers):
                self._logger.removeHandler(handler)
            self._logger.propagate = False

            # Switch to real logger
            self._logger = logger
            self._logger.debug(
                "[AppConfigService] Replaced bootstrap logger with real logger"
            )

    # Core access methods
    def get_section(self, section: str, default: T = None) -> Dict[str, Any]:
        """Get a configuration section."""
        if self._config_data is None:
            raise ConfigurationException("Configuration not loaded")
        return self._config_data.get(section, default)

    def get_value(self, path: str, default: T = None) -> T:
        """Get a specific configuration value using dot notation."""
        if self._config_data is None:
            raise ConfigurationException("Configuration not loaded")
        return self._config_service.get_value_from_config(
            self._config_data, path, default
        )

    # Path accessors
    def get_cache_path(self) -> Path:
        """Get the path for custom agents."""
        return Path(self.get_value("paths.cache", "agentmap_data/cache"))

    def get_custom_agents_path(self) -> Path:
        """Get the path for custom agents."""
        return Path(
            self.get_value("paths.custom_agents", "agentmap_data/custom_agents")
        )

    def get_functions_path(self) -> Path:
        """Get the path for functions."""
        return Path(self.get_value("paths.functions", "agentmap_data/custom_functions"))

    def get_metadata_bundles_path(self) -> Path:
        """Get the path for metadata bundles."""
        metadata_bundles_path = Path(
            self.get_value("paths.metadata_bundles", "agentmap_data/metadata_bundles")
        )

        # Ensure the directory exists
        try:
            metadata_bundles_path.mkdir(parents=True, exist_ok=True)
            self._logger.debug(
                f"[AppConfigService] Metadata bundles path ensured: {metadata_bundles_path}"
            )
        except Exception as e:
            error_msg = f"Could not create metadata bundles directory {metadata_bundles_path}: {e}"
            self._logger.error(f"[AppConfigService] {error_msg}")
            raise ConfigurationException(error_msg) from e

        return metadata_bundles_path

    def get_csv_repository_path(self) -> Path:
        """Get the path for the CSV repository directory where workflows are stored."""
        csv_repo_path = Path(
            self.get_value("paths.csv_repository", "agentmap_data/workflows")
        )

        # Ensure the directory exists
        try:
            csv_repo_path.mkdir(parents=True, exist_ok=True)
            self._logger.debug(
                f"[AppConfigService] CSV repository path ensured: {csv_repo_path}"
            )
        except Exception as e:
            self._logger.warning(
                f"[AppConfigService] Could not create CSV repository directory {csv_repo_path}: {e}"
            )

        return csv_repo_path

    # Logging accessors
    def get_logging_config(self) -> Dict[str, Any]:
        """Get the logging configuration."""
        return self.get_section("logging", {})

    # LLM accessors
    def get_llm_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for a specific LLM provider."""
        return self.get_value(f"llm.{provider}", {})

    # Routing accessors
    def get_routing_config(self) -> Dict[str, Any]:
        """Get the routing configuration with default values."""
        routing_config = self.get_section("routing", {})

        # Default routing configuration matching LLMRoutingConfigService expectations
        defaults = {
            "enabled": True,
            "routing_matrix": {},
            "task_types": {
                "general": {
                    "description": "General purpose tasks",
                    "provider_preference": ["anthropic", "openai", "google"],
                    "default_complexity": "medium",
                    "complexity_keywords": {
                        "low": ["simple", "basic", "quick"],
                        "medium": ["analyze", "process", "standard"],
                        "high": ["complex", "detailed", "comprehensive", "advanced"],
                        "critical": ["urgent", "critical", "important", "emergency"],
                    },
                }
            },
            "complexity_analysis": {
                "enabled": True,
                "prompt_length_thresholds": {"low": 500, "medium": 2000, "high": 8000},
                "content_analysis": {
                    "enabled": True,
                    "keyword_weights": {
                        "complexity_indicators": 2.0,
                        "technical_terms": 1.5,
                        "urgency_indicators": 1.8,
                    },
                },
            },
            "cost_optimization": {
                "enabled": True,
                "max_cost_tier": "high",
                "cost_aware_routing": True,
            },
            "fallback": {
                "enabled": True,
                "default_provider": "anthropic",
                # Note: default_model is loaded from routing.fallback.default_model
                # If not specified in config, LLMModelsConfigService provides the default
                "max_retries": 2,
            },
            "performance": {
                "enable_routing_cache": True,
                "cache_ttl": 300,
                "async_routing": True,
            },
        }

        # Merge with defaults
        return self._merge_with_defaults(routing_config, defaults)

    # Prompts accessors
    def get_prompts_config(self) -> Dict[str, Any]:
        """Get the prompt configuration."""
        return self.get_section("prompts", {})

    def get_prompts_directory(self) -> Path:
        """Get the path for the prompts directory."""
        return Path(self.get_value("prompts.directory", "agentmap_data/prompts"))

    def get_prompt_registry_path(self) -> Path:
        """Get the path for the prompt registry file."""
        return Path(
            self.get_value(
                "prompts.registry_file", "agentmap_data/prompts/prompt_registry.yaml"
            )
        )

    # Execution accessors
    def get_execution_config(self) -> Dict[str, Any]:
        """Get execution configuration."""
        return self.get_section("execution", {})

    def get_tracking_config(self) -> Dict[str, Any]:
        """Get tracking configuration."""
        return self.get_value("execution.tracking", {})

    # Authentication accessors
    def get_auth_config(self) -> Dict[str, Any]:
        """Get authentication configuration with default values."""
        auth_config = self.get_section("authentication", {})

        # Default authentication configuration
        defaults = {
            "enabled": True,
            "api_keys": {},  # API keys should be defined in config or env vars
            "jwt": {
                "secret": None,  # Should be set in environment or config
                "algorithm": "HS256",
                "expiry_hours": 24,
            },
            "supabase": {
                "url": None,  # Should be set in environment or config
                "anon_key": None,  # Should be set in environment or config
            },
            "public_endpoints": [
                "/",
                "/health",
                "/docs",
                "/openapi.json",
                "/redoc",
                "/favicon.ico",
            ],
            "embedded_mode": {
                "enabled": True,  # Allow embedded mode for local development
                "bypass_auth": True,  # Bypass auth for embedded mode
            },
            "permissions": {
                "default_permissions": ["read"],
                "admin_permissions": ["read", "write", "execute", "admin"],
                "execution_permissions": ["read", "execute"],
            },
        }

        # Merge with defaults
        merged_config = self._merge_with_defaults(auth_config, defaults)

        # Log auth configuration status for visibility
        if auth_config:
            self._logger.debug(
                f"[AppConfigService] Authentication config loaded: enabled={merged_config.get('enabled', True)}"
            )
        else:
            self._logger.debug(
                "[AppConfigService] No authentication config found, using defaults"
            )

        return merged_config

    def is_authentication_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return self.get_value("authentication.enabled", True)

    def get_api_keys_config(self) -> Dict[str, Any]:
        """Get API keys configuration."""
        return self.get_value("authentication.api_keys", {})

    def get_jwt_config(self) -> Dict[str, Any]:
        """Get JWT authentication configuration."""
        return self.get_value(
            "authentication.jwt",
            {"secret": None, "algorithm": "HS256", "expiry_hours": 24},
        )

    def get_supabase_auth_config(self) -> Dict[str, Any]:
        """Get Supabase authentication configuration."""
        return self.get_value(
            "authentication.supabase", {"url": None, "anon_key": None}
        )

    def get_public_endpoints(self) -> List[str]:
        """Get list of public endpoints that don't require authentication."""
        return self.get_value(
            "authentication.public_endpoints",
            ["/", "/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"],
        )

    def get_embedded_mode_config(self) -> Dict[str, Any]:
        """Get embedded mode configuration."""
        return self.get_value(
            "authentication.embedded_mode", {"enabled": True, "bypass_auth": True}
        )

    def get_auth_permissions_config(self) -> Dict[str, Any]:
        """Get authentication permissions configuration."""
        return self.get_value(
            "authentication.permissions",
            {
                "default_permissions": ["read"],
                "admin_permissions": ["read", "write", "execute", "admin"],
                "execution_permissions": ["read", "execute"],
            },
        )

    def validate_auth_config(self) -> Dict[str, Any]:
        """
        Validate authentication configuration and return validation results.

        Returns:
            Dictionary with validation status:
            - 'valid': Boolean indicating if config is valid
            - 'warnings': List of non-critical issues
            - 'errors': List of critical issues
            - 'summary': Summary of validation results
        """
        warnings = []
        errors = []

        try:
            auth_config = self.get_auth_config()

            # Check if auth is enabled but no auth methods configured
            if auth_config.get("enabled", True):
                api_keys = auth_config.get("api_keys", {})
                jwt_secret = auth_config.get("jwt", {}).get("secret")
                supabase_config = auth_config.get("supabase", {})

                has_auth_method = (
                    bool(api_keys)
                    or bool(jwt_secret)
                    or (
                        bool(supabase_config.get("url"))
                        and bool(supabase_config.get("anon_key"))
                    )
                )

                if not has_auth_method:
                    warnings.append(
                        "Authentication is enabled but no auth methods are configured (API keys, JWT, or Supabase)"
                    )

            # Validate JWT configuration
            jwt_config = auth_config.get("jwt", {})
            if jwt_config.get("secret") and len(jwt_config["secret"]) < 32:
                warnings.append(
                    "JWT secret should be at least 32 characters long for security"
                )

            # Validate public endpoints
            public_endpoints = auth_config.get("public_endpoints", [])
            if not isinstance(public_endpoints, list):
                errors.append("Public endpoints configuration must be a list")
            elif not public_endpoints:
                warnings.append(
                    "No public endpoints configured - all endpoints will require authentication"
                )

            # Validate permissions configuration
            permissions_config = auth_config.get("permissions", {})
            if not isinstance(permissions_config, dict):
                errors.append("Permissions configuration must be a dictionary")
            else:
                default_perms = permissions_config.get("default_permissions", [])
                if not isinstance(default_perms, list):
                    errors.append("Default permissions must be a list")

        except Exception as e:
            errors.append(f"Error during auth config validation: {str(e)}")

        # Determine overall validity
        is_valid = len(errors) == 0

        # Create summary
        summary = {
            "total_issues": len(warnings) + len(errors),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "auth_enabled": self.is_authentication_enabled(),
            "public_endpoints_count": len(self.get_public_endpoints()),
            "has_api_keys": bool(self.get_api_keys_config()),
            "has_jwt_secret": bool(self.get_jwt_config().get("secret")),
            "has_supabase_config": bool(
                self.get_supabase_auth_config().get("url")
                and self.get_supabase_auth_config().get("anon_key")
            ),
        }

        # Log validation results
        if is_valid:
            if warnings:
                self._logger.info(
                    f"[AppConfigService] Auth config validation completed with {len(warnings)} warnings"
                )
            else:
                self._logger.debug("[AppConfigService] Auth config validation passed")
        else:
            self._logger.error(
                f"[AppConfigService] Auth config validation failed with {len(errors)} errors"
            )

        return {
            "valid": is_valid,
            "warnings": warnings,
            "errors": errors,
            "summary": summary,
        }

    # Config file path accessor for debugging mostly
    def get_config_file_path(self) -> Optional[Path]:
        """Get the path to the main configuration file that was used during initialization."""
        return self._config_file_path

    # Storage config path accessor (storage loading moved to StorageConfigService)
    def get_storage_config_path(self) -> Optional[Path]:
        """Get the path for the storage configuration file."""
        storage_path = self.get_value("storage_config_path")
        return Path(storage_path) if storage_path else None

    # Host application configuration accessors
    def get_host_application_config(self) -> Dict[str, Any]:
        """
        Get host application configuration with default values.

        Allows host applications to store their configuration in the main AgentMap
        config file under a 'host_application' section. Provides graceful degradation
        when no host config is present.

        Returns:
            Dictionary containing host application configuration
        """
        host_config = self.get_section("host_application", {})

        # Default host application configuration
        defaults = {
            "enabled": True,
            "services": {},
            "protocol_folders": [],
            "service_discovery": {
                "enabled": True,
                "scan_on_startup": True,
                "cache_protocols": True,
            },
            "configuration": {},
            "features": {
                "dynamic_protocols": True,
                "runtime_registration": True,
                "graceful_degradation": True,
            },
        }

        # Merge with defaults
        merged_config = self._merge_with_defaults(host_config, defaults)

        # Log host application status for visibility
        if host_config:
            self._logger.debug(
                f"[AppConfigService] Host application config loaded with sections: {list(host_config.keys())}"
            )
        else:
            self._logger.debug(
                "[AppConfigService] No host application config found, using defaults"
            )

        return merged_config

    def get_host_protocol_folders(self) -> List[Path]:
        """
        Get list of folders to scan for host-defined protocols.

        Returns protocol discovery paths from configuration, with sensible defaults
        for common host application structures.

        Returns:
            List of Path objects for protocol discovery folders
        """
        # Get protocol folders from host application config
        protocol_folders_config = self.get_value(
            "host_application.protocol_folders", []
        )

        # Convert strings to Path objects
        protocol_folders = []
        for folder in protocol_folders_config:
            try:
                protocol_folders.append(Path(folder))
            except Exception as e:
                self._logger.warning(
                    f"[AppConfigService] Invalid protocol folder path '{folder}': {e}"
                )

        # Add default protocol discovery paths if none configured
        if not protocol_folders:
            default_folders = [
                "host_services/protocols",
                "custom_protocols",
                "protocols",
            ]
            protocol_folders = [Path(folder) for folder in default_folders]
            self._logger.debug(
                f"[AppConfigService] Using default protocol folders: {default_folders}"
            )
        else:
            folder_paths = [str(folder) for folder in protocol_folders]
            self._logger.debug(
                f"[AppConfigService] Using configured protocol folders: {folder_paths}"
            )

        return protocol_folders

    def get_host_service_config(self, service_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific host service.

        Args:
            service_name: Name of the host service

        Returns:
            Dictionary containing service-specific configuration
        """
        if not service_name:
            self._logger.warning("[AppConfigService] Empty service name provided")
            return {}

        # Get service configuration from host application config
        service_config = self.get_value(f"host_application.services.{service_name}", {})

        # Provide default service configuration structure
        defaults = {
            "enabled": True,
            "auto_configure": True,
            "dependencies": [],
            "configuration": {},
            "metadata": {},
        }

        # Merge with defaults
        merged_config = self._merge_with_defaults(service_config, defaults)

        if service_config:
            self._logger.debug(
                f"[AppConfigService] Host service '{service_name}' config loaded"
            )
        else:
            self._logger.debug(
                f"[AppConfigService] No config found for host service '{service_name}', using defaults"
            )

        return merged_config

    def get_host_configuration_section(self, section_name: str) -> Dict[str, Any]:
        """
        Get a specific configuration section from host application config.

        Args:
            section_name: Name of the configuration section

        Returns:
            Dictionary containing the requested configuration section
        """
        return self.get_value(f"host_application.configuration.{section_name}", {})

    def validate_host_config(self) -> Dict[str, Any]:
        """
        Validate host application configuration and return validation results.

        Returns:
            Dictionary with validation status:
            - 'valid': Boolean indicating if config is valid
            - 'warnings': List of non-critical issues
            - 'errors': List of critical issues
            - 'summary': Summary of validation results
        """
        warnings = []
        errors = []

        try:
            host_config = self.get_host_application_config()

            # Validate protocol folders exist
            protocol_folders = self.get_host_protocol_folders()
            for folder in protocol_folders:
                if not folder.exists():
                    warnings.append(f"Protocol folder does not exist: {folder}")
                elif not folder.is_dir():
                    errors.append(f"Protocol folder path is not a directory: {folder}")

            # Validate services configuration
            services_config = host_config.get("services", {})
            if not isinstance(services_config, dict):
                errors.append(
                    "Host application services configuration must be a dictionary"
                )
            else:
                for service_name, service_config in services_config.items():
                    if not isinstance(service_config, dict):
                        errors.append(
                            f"Service '{service_name}' configuration must be a dictionary"
                        )

            # Validate service discovery configuration
            discovery_config = host_config.get("service_discovery", {})
            if not isinstance(discovery_config, dict):
                warnings.append(
                    "Service discovery configuration should be a dictionary"
                )

            # Validate features configuration
            features_config = host_config.get("features", {})
            if not isinstance(features_config, dict):
                warnings.append("Features configuration should be a dictionary")

            # Check for common configuration issues
            if not host_config.get("enabled", True):
                warnings.append("Host application support is disabled")

            if not protocol_folders:
                warnings.append("No protocol folders configured for service discovery")

        except Exception as e:
            errors.append(f"Error during host config validation: {str(e)}")

        # Determine overall validity
        is_valid = len(errors) == 0

        # Create summary
        summary = {
            "total_issues": len(warnings) + len(errors),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "protocol_folders_count": (
                len(self.get_host_protocol_folders()) if not errors else 0
            ),
            "services_count": (
                len(self.get_host_application_config().get("services", {}))
                if not errors
                else 0
            ),
        }

        # Log validation results
        if is_valid:
            if warnings:
                self._logger.info(
                    f"[AppConfigService] Host config validation completed with {len(warnings)} warnings"
                )
            else:
                self._logger.debug("[AppConfigService] Host config validation passed")
        else:
            self._logger.error(
                f"[AppConfigService] Host config validation failed with {len(errors)} errors"
            )

        return {
            "valid": is_valid,
            "warnings": warnings,
            "errors": errors,
            "summary": summary,
        }

    def is_host_application_enabled(self) -> bool:
        """
        Check if host application support is enabled.

        Returns:
            True if host application support is enabled
        """
        return self.get_value("host_application.enabled", True)

    # Declaration configuration accessors
    def get_declaration_paths(self) -> List[Path]:
        """
        Get list of custom declaration directories.

        Returns:
            List of Path objects for custom declaration directories
        """
        declaration_paths_config = self.get_value("declarations.custom", [])

        declaration_paths = []
        for path_config in declaration_paths_config:
            try:
                # Handle both string and dict formats
                if isinstance(path_config, str):
                    path = path_config
                elif isinstance(path_config, dict) and "path" in path_config:
                    path = path_config["path"]
                else:
                    self._logger.warning(
                        f"[AppConfigService] Invalid declaration path config: {path_config}"
                    )
                    continue

                # Expand environment variables
                expanded_path = os.path.expandvars(path)
                declaration_paths.append(Path(expanded_path))

            except Exception as e:
                self._logger.warning(
                    f"[AppConfigService] Invalid declaration path '{path_config}': {e}"
                )

        # Log configured paths
        if declaration_paths:
            path_strs = [str(p) for p in declaration_paths]
            self._logger.debug(
                f"[AppConfigService] Using custom declaration paths: {path_strs}"
            )
        else:
            self._logger.debug(
                "[AppConfigService] No custom declaration paths configured"
            )

        return declaration_paths

    def get_host_declaration_paths(self) -> List[Path]:
        """
        Get list of host application declaration directories.

        Returns:
            List of Path objects for host declaration directories
        """
        if not self.is_host_declarations_enabled():
            return []

        host_paths_config = self.get_value("declarations.host.paths", [])

        host_paths = []
        for path in host_paths_config:
            try:
                # Expand environment variables
                expanded_path = os.path.expandvars(path)
                host_paths.append(Path(expanded_path))
            except Exception as e:
                self._logger.warning(
                    f"[AppConfigService] Invalid host declaration path '{path}': {e}"
                )

        # Log configured paths
        if host_paths:
            path_strs = [str(p) for p in host_paths]
            self._logger.debug(
                f"[AppConfigService] Using host declaration paths: {path_strs}"
            )
        else:
            self._logger.debug(
                "[AppConfigService] No host declaration paths configured"
            )

        return host_paths

    def is_host_declarations_enabled(self) -> bool:
        """
        Check if host declarations are enabled.

        Returns:
            True if host declarations are enabled
        """
        return self.get_value("declarations.host.enabled", False)

    def get_host_declarations_namespace(self) -> Optional[str]:
        """
        Get the namespace for host declarations.

        Returns:
            Namespace string or None if not configured
        """
        return self.get_value("declarations.host.namespace", None)

    def get_declaration_validation_settings(self) -> Dict[str, Any]:
        """
        Get declaration validation settings.

        Returns:
            Dictionary with validation settings
        """
        validation_config = self.get_value("declarations.validation", {})

        # Default validation settings
        defaults = {
            "strict": False,
            "warn_on_missing": True,
            "require_versions": False,
            "allow_unknown_protocols": True,
            "validate_class_paths": False,
        }

        # Merge with defaults
        merged_settings = self._merge_with_defaults(validation_config, defaults)

        # Log validation settings
        if validation_config:
            self._logger.debug(
                f"[AppConfigService] Declaration validation settings: strict={merged_settings['strict']}, "
                f"warn_on_missing={merged_settings['warn_on_missing']}"
            )
        else:
            self._logger.debug(
                "[AppConfigService] Using default declaration validation settings"
            )

        return merged_settings

    # Utility methods for domain-specific business logic
    def _merge_with_defaults(
        self, config: Dict[str, Any], defaults: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recursively merge configuration with defaults.

        Args:
            config: User configuration
            defaults: Default configuration

        Returns:
            Merged configuration
        """
        result = defaults.copy()

        for key, value in config.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_with_defaults(value, result[key])
            else:
                result[key] = value

        return result

    def validate_config(self) -> bool:
        """
        Validate that the configuration contains required sections.

        Returns:
            True if configuration is valid

        Raises:
            ConfigurationException: If required configuration is missing
        """
        if self._config_data is None:
            raise ConfigurationException("Configuration not loaded")

        # Validate required sections exist (can be empty)
        required_sections = ["logging", "llm", "prompts", "execution"]
        missing_sections = []

        for section in required_sections:
            if section not in self._config_data:
                missing_sections.append(section)

        if missing_sections:
            self._logger.warning(f"Missing configuration sections: {missing_sections}")
            # Don't raise exception - just log warning since defaults will be used

        self._logger.debug("Configuration validation completed")
        return True

    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the loaded configuration for debugging.

        Returns:
            Dictionary with configuration summary
        """
        if self._config_data is None:
            return {"status": "not_loaded"}

        # Basic configuration summary
        summary = {
            "status": "loaded",
            "sections": list(self._config_data.keys()),
            "section_count": len(self._config_data),
            "llm_providers": list(self._config_data.get("llm", {}).keys()),
            "has_storage_config": "storage_config_path" in self._config_data,
        }

        # Add host application summary if available
        if "host_application" in self._config_data:
            try:
                host_config = self.get_host_application_config()
                summary["host_application"] = {
                    "enabled": host_config.get("enabled", False),
                    "services_configured": len(host_config.get("services", {})),
                    "protocol_folders_configured": len(
                        host_config.get("protocol_folders", [])
                    ),
                    "service_discovery_enabled": host_config.get(
                        "service_discovery", {}
                    ).get("enabled", False),
                    "features_enabled": list(
                        k for k, v in host_config.get("features", {}).items() if v
                    ),
                }
            except Exception as e:
                summary["host_application"] = {
                    "error": f"Failed to load host config: {str(e)}"
                }
        else:
            summary["host_application"] = {"configured": False}

        return summary

    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration data.

        Returns:
            Complete configuration dictionary
        """
        if self._config_data is None:
            raise ConfigurationException("Configuration not loaded")
        return self._config_data.copy()
