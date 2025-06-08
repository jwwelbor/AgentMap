# agentmap/config/app_config.py
"""
Domain service for application configuration with business logic.

Provides business logic layer for application configuration, using ConfigService
for infrastructure concerns while maintaining backward compatibility with the
existing Configuration class interface.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union, TypeVar

from agentmap.services.config.config_service import ConfigService
from agentmap.exceptions.base_exceptions import ConfigurationException

T = TypeVar('T')


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
            config_path: Optional[Union[str, Path]] = None
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
                format="(BOOTSTRAP) [%(asctime)s] %(levelname)s: %(message)s"
            )
        self._logger = logging.getLogger("bootstrap.app_config")
        self._logger.debug("[AppConfigService] Bootstrap logger initialized")
    
    def _load_config(self, config_path: Optional[Union[str, Path]]):
        """Load configuration using ConfigService."""
        try:
            self._logger.info("[AppConfigService] Loading application configuration")
            self._config_data = self._config_service.load_config(config_path)
            self._logger.info("[AppConfigService] Application configuration loaded successfully")
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
            self._logger.debug("[AppConfigService] Replaced bootstrap logger with real logger")
    
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
        return self._config_service.get_value_from_config(self._config_data, path, default)

    # Path accessors 
    def get_custom_agents_path(self) -> Path:
        """Get the path for custom agents."""
        return Path(self.get_value("paths.custom_agents", "agentmap/custom_agents"))

    def get_functions_path(self) -> Path:
        """Get the path for functions."""
        return Path(self.get_value("paths.functions", "agentmap/custom_functions"))

    def get_compiled_graphs_path(self) -> Path:
        """Get the path for compiled graphs."""
        return Path(self.get_value("paths.compiled_graphs", "agentmap/compiled_graphs"))

    def get_csv_path(self) -> Path:
        """Get the path for the workflow CSV file."""
        return Path(self.get_value("csv_path", "examples/SingleNodeGraph.csv"))

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
        
        # Default routing configuration
        defaults = {
            "enabled": True,
            "complexity_analysis": {
                "prompt_length_thresholds": {
                    "low": 100,
                    "medium": 300,
                    "high": 800
                },
                "methods": {
                    "prompt_length": True,
                    "keyword_analysis": True,
                    "context_analysis": True,
                    "memory_analysis": True,
                    "structure_analysis": True
                },
                "keyword_weights": {
                    "complexity_keywords": 0.4,
                    "task_specific_keywords": 0.3,
                    "prompt_structure": 0.3
                },
                "context_analysis": {
                    "memory_size_threshold": 10,
                    "input_field_count_threshold": 5
                }
            },
            "task_types": {
                "general": {
                    "description": "General purpose tasks",
                    "provider_preference": ["anthropic", "openai", "google"],
                    "default_complexity": "medium",
                    "complexity_keywords": {
                        "high": ["analyze", "complex", "detailed", "comprehensive"],
                        "critical": ["urgent", "critical", "important", "decision"]
                    }
                }
            },
            "fallback": {
                "default_provider": "anthropic",
                "default_model": "claude-3-haiku-20240307",
                "retry_with_lower_complexity": True
            }
        }
        
        # Merge with defaults
        return self._merge_with_defaults(routing_config, defaults)

    # Prompts accessors 
    def get_prompts_config(self) -> Dict[str, Any]:
        """Get the prompt configuration."""
        return self.get_section("prompts", {})

    def get_prompts_directory(self) -> Path:
        """Get the path for the prompts directory."""
        return Path(self.get_value("prompts.directory", "prompts"))

    def get_prompt_registry_path(self) -> Path:
        """Get the path for the prompt registry file."""
        return Path(self.get_value("prompts.registry_file", "prompts/registry.yaml"))

    # Execution accessors 
    def get_execution_config(self) -> Dict[str, Any]:
        """Get execution configuration."""
        return self.get_section("execution", {})

    def get_tracking_config(self) -> Dict[str, Any]:
        """Get tracking configuration."""
        return self.get_value("execution.tracking", {})

    # Storage config path accessor (storage loading moved to StorageConfigService)
    def get_storage_config_path(self) -> Path:
        """Get the path for the storage configuration file."""
        return Path(self.get_value("storage_config_path", "storage_config.yaml"))

    # Legacy method for backward compatibility (delegates file I/O to ConfigService)
    def load_storage_config(self) -> Dict[str, Any]:
        """
        Load storage configuration from YAML file.
        
        Note: This method is preserved for backward compatibility but violates
        separation of concerns. Consider using StorageConfigService instead.
        """
        storage_config_path = self.get_storage_config_path()
        
        # Use ConfigService to load the storage config file
        try:
            storage_config = self._config_service.load_config(storage_config_path)
        except ConfigurationException:
            # If file doesn't exist, return empty config
            storage_config = {}
        
        # Default storage configuration
        defaults = {
            "csv": {"default_directory": "data/csv", "collections": {}},
            "vector": {"default_provider": "local", "collections": {}},
            "kv": {"default_provider": "local", "collections": {}}
        }
        
        # Merge with defaults using ConfigService's merge logic
        return self._merge_with_defaults(storage_config, defaults)

    # Utility methods for domain-specific business logic
    def _merge_with_defaults(self, config: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
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
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
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
        
        return {
            "status": "loaded",
            "sections": list(self._config_data.keys()),
            "section_count": len(self._config_data),
            "llm_providers": list(self._config_data.get("llm", {}).keys()),
            "has_storage_config": "storage_config_path" in self._config_data
        }
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration data.
        
        Returns:
            Complete configuration dictionary
        """
        if self._config_data is None:
            raise ConfigurationException("Configuration not loaded")
        return self._config_data.copy()
