# agentmap/config/base.py
from pathlib import Path

import logging
import yaml
import os
import threading
from typing import Any, Dict, List, Optional, Union

# from agentmap.logging.logger_utils import get_clean_logger, configure_basic_logger

# # Set up basic logging for the config module
# def _setup_config_logging():
#     """Set up basic logging for the config module."""
#     logger = get_clean_logger("agentmap.config")
    
#     # Only configure if no handlers exist
#     if not logger.handlers:
#         # Get level from environment with fallback
#         level_name = os.environ.get("AGENTMAP_CONFIG_LOG_LEVEL", "INFO").upper()
#         try:
#             level = getattr(logging, level_name)
#         except AttributeError:
#             level = logging.INFO
            
#         configure_basic_logger(logger, level=level)
    
#     return logger


# Create logger for this module
# logger = _setup_config_logging()

# Default config file location
#DEFAULT_CONFIG_FILE = Path("agentmap_config.yaml")

# Import defaults
from agentmap.config.defaults import get_default_config

import logging
logger = logging.getLogger("agentmap.config")

# Keep the original merge function for backward compatibility
def _merge_with_defaults(config: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge configuration with defaults.
    
    Args:
        config: User configuration
        defaults: Default configuration
        
    Returns:
        Merged configuration
    """
    result = defaults.copy()
    
    # Override defaults with user values
    for key, value in config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = _merge_with_defaults(value, result[key])
        else:
            # Use user value
            result[key] = value
    
    return result


class ConfigManager:
    """
    Singleton configuration manager for AgentMap.
    
    This class provides a centralized way to access configuration with caching
    to avoid repeated file reads.
    """
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConfigManager, cls).__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the configuration manager."""
        self._config = None
        self._config_path = None
        self._initialized = False
        logger.debug("[ConfigManager] Config initialized")
        self._initialized = True
    
    def load_config(self, config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Load configuration from file with caching for performance.
        
        Args:
            config_path: Optional path to a custom config file
            
        Returns:
            Dictionary containing configuration values
        """
        with self._lock:
            # Return cached config if path hasn't changed and we have a config
            if self._config is not None and self._config_path == config_path:
                logger.debug("[ConfigManager] Returning cached configuration")
                return self._config
            
            # Handle None config_path by using defaults only
            if config_path is None:
                logger.debug("[ConfigManager] No config path provided, using defaults only")
                # Get default configuration
                defaults = get_default_config()
                self._config = defaults
                return self._config
            
            # Otherwise, load the configuration
            config_file = Path(config_path)
            self._config_path = config_path
            
            # Log detailed info about config loading
            logger.info(f"[ConfigManager] Loading configuration from: {config_file}")
            if not config_file.exists():
                logger.warning(f"[ConfigManager] Config file not found at {config_file}. Using defaults.")
            
            # Load configuration from file if it exists
            config = {}
            if config_file.exists():
                try:
                    with config_file.open() as f:
                        config = yaml.safe_load(f) or {}
                    logger.info(f"[ConfigManager] Successfully loaded configuration from {config_file}")
                    
                    # Log top-level sections for visibility
                    sections = list(config.keys())
                    logger.info(f"[ConfigManager] Loaded configuration sections: {sections}")
                    
                except Exception as e:
                    logger.error(f"[ConfigManager] Error loading config file {config_file}: {e}")
            
            # Get default configuration
            logger.debug("[ConfigManager] Loading default configuration values")
            defaults = get_default_config()
            
            # Merge with defaults
            logger.debug("[ConfigManager] Merging user configuration with defaults")
            self._config = _merge_with_defaults(config, defaults)  # Use the standalone function
            
            return self._config
    
    def get_config_section(self, section: str, config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Get a specific section from the configuration.
        
        Args:
            section: Section name to retrieve
            config_path: Optional path to a custom config file
            
        Returns:
            Configuration section or empty dict if not found
        """
        logger.trace(f"[ConfigManager] Requested configuration section: {section}")
        config = self.load_config(config_path)
        
        if section not in config:
            logger.warning(f"[ConfigManager] Section '{section}' not found in configuration. Using empty dict.")
            
        config_section = config.get(section, {})
        logger.debug(f"[ConfigManager] Loaded configuration section: {section} -> {config_section}")
        return config_section
    
    def refresh(self, config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """
        Force reload the configuration from disk.
        
        Args:
            config_path: Optional path to a custom config file
            
        Returns:
            Refreshed configuration dictionary
        """
        with self._lock:
            # Clear cached config
            self._config = None
            
            # If no path specified, use the last known path
            if config_path is None:
                config_path = self._config_path
                
            # Load and return the config
            return self.load_config(config_path)
    
    def get_value(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot notation path.
        
        Args:
            path: Dot-separated path to configuration value (e.g. "llm.openai.api_key")
            default: Default value to return if path not found
            
        Returns:
            Configuration value or default if not found
        """
        if self._config is None:
            self.load_config()
            
        config = self._config
        keys = path.split('.')
        
        for key in keys:
            if isinstance(config, dict) and key in config:
                config = config[key]
            else:
                return default
                
        return config

# Create singleton instance
_config_manager = ConfigManager()


# Public API functions for backward compatibility

def load_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file with environment variable fallbacks.
    
    This function uses the singleton ConfigManager for improved performance.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Dictionary containing configuration values
    """
    return _config_manager.load_config(config_path)


def get_config_section(section: str, config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Get a specific section from the configuration.
    
    This function uses the singleton ConfigManager for improved performance.
    
    Args:
        section: Section name to retrieve
        config_path: Optional path to a custom config file
        
    Returns:
        Configuration section or empty dict if not found
    """
    return _config_manager.get_config_section(section, config_path)


def refresh_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Force reload the configuration from disk.
    
    This is useful when the configuration file has been modified at runtime.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Refreshed configuration dictionary
    """
    return _config_manager.refresh(config_path)


def get_config_value(path: str, default: Any = None) -> Any:
    """
    Get a configuration value by dot notation path.
    
    Args:
        path: Dot-separated path to configuration value (e.g. "llm.openai.api_key")
        default: Default value to return if path not found
        
    Returns:
        Configuration value or default if not found
    """
    return _config_manager.get_value(path, default)