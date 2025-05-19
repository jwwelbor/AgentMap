"""
Base configuration loading functionality for AgentMap.
"""
from pathlib import Path
import yaml
from typing import Any, Dict, Optional, Union

from agentmap.config.defaults import get_default_config

# Default config file location
DEFAULT_CONFIG_FILE = Path("agentmap_config.yaml")

def load_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file with environment variable fallbacks.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Dictionary containing configuration values
    """
    # Determine which config file to use
    config_file = Path(config_path) if config_path else DEFAULT_CONFIG_FILE
    
    # Check if config file exists
    config = {}
    if config_file.exists():
        with config_file.open() as f:
            config = yaml.safe_load(f) or {}
    elif config_path:
        import logging
        logging.warning(f"Config file not found at {config_file}. Using defaults.")
    
    # Get default configuration
    defaults = get_default_config()
    
    # Merge with defaults (recursive for nested dictionaries)
    return _merge_with_defaults(config, defaults)

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

def get_config_section(section: str, config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Get a specific section from the configuration.
    
    Args:
        section: Section name to retrieve
        config_path: Optional path to a custom config file
        
    Returns:
        Configuration section or empty dict if not found
    """
    config = load_config(config_path)
    return config.get(section, {})