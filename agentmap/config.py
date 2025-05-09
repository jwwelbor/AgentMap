"""
Configuration loader for AgentMap.
Supports loading from YAML or environment variable fallback.
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

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
    if config_file.exists():
        with config_file.open() as f:
            config = yaml.safe_load(f)
            if config is None:  # Handle empty config file
                config = {}
    else:
        # If custom path was specified but doesn't exist, provide a warning
        if config_path:
            import logging
            logging.warning(f"Config file not found at {config_file}. Using defaults.")
        config = {}
    
    # Default values
    defaults = {
        "csv_path": os.environ.get("AGENTMAP_CSV_PATH", "examples/SingleNodeGraph.csv"),
        "autocompile": os.environ.get("AGENTMAP_AUTOCOMPILE", "false").lower() == "true",
        "storage_config_path": os.environ.get("AGENTMAP_STORAGE_CONFIG", "storage_config.yaml"),

        "paths": {
            "custom_agents": os.environ.get("AGENTMAP_CUSTOM_AGENTS_PATH", "agentmap/agents/custom"),
            "functions": os.environ.get("AGENTMAP_FUNCTIONS_PATH", "agentmap/functions"),
            "compiled_graphs": os.environ.get("AGENTMAP_COMPILED_GRAPHS_PATH", "compiled_graphs")
        },
        # Add LLM configurations here for completeness
        "llm": {
            "openai": {
                "api_key": os.environ.get("OPENAI_API_KEY", ""),
                "model": os.environ.get("AGENTMAP_OPENAI_MODEL", "gpt-3.5-turbo"),
                "temperature": float(os.environ.get("AGENTMAP_OPENAI_TEMPERATURE", "0.7"))
            },
            "anthropic": {
                "api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
                "model": os.environ.get("AGENTMAP_ANTHROPIC_MODEL", "claude-3-sonnet-20240229"),
                "temperature": float(os.environ.get("AGENTMAP_ANTHROPIC_TEMPERATURE", "0.7"))
            },
            "google": {
                "api_key": os.environ.get("GOOGLE_API_KEY", ""),
                "model": os.environ.get("AGENTMAP_GOOGLE_MODEL", "gemini-1.0-pro"),
                "temperature": float(os.environ.get("AGENTMAP_GOOGLE_TEMPERATURE", "0.7"))
            }
        },
        # Default memory configuration
        "memory": {
            "enabled": False,
            "default_type": "buffer",
            "buffer_window_size": 5,
            "max_token_limit": 2000,
            "memory_key": "conversation_memory"
        }
    }
    
    # Apply defaults for missing values
    for key, value in defaults.items():
        if key not in config:
            config[key] = value
        elif isinstance(value, dict) and key in config:
            # Merge nested dictionaries
            for nested_key, nested_value in value.items():
                if nested_key not in config[key]:
                    config[key][nested_key] = nested_value
                # Handle third level of nesting for LLM configs
                elif isinstance(nested_value, dict) and nested_key in config[key]:
                    for deep_key, deep_value in nested_value.items():
                        if deep_key not in config[key][nested_key]:
                            config[key][nested_key][deep_key] = deep_value
    
    return config

def get_custom_agents_path(config_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Get the path for custom agents from config.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Path object for the custom agents directory
    """
    config = load_config(config_path)
    return Path(config.get("paths", {}).get("custom_agents", "agentmap/agents/custom"))

def get_functions_path(config_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Get the path for function files from config.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Path object for the functions directory
    """
    config = load_config(config_path)
    return Path(config.get("paths", {}).get("functions", "agentmap/functions"))

def get_compiled_graphs_path(config_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Get the path for compiled graphs from config.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Path object for the compiled graphs directory
    """
    config = load_config(config_path)
    return Path(config.get("paths", {}).get("compiled_graphs", "agentmap/compiled_graphs"))

def get_csv_path(config_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Get the path for the workflow CSV file from config.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Path object for the CSV file
    """
    config = load_config(config_path)
    return Path(config.get("csv_path", "examples/SingleNodeGraph.csv"))

def get_llm_config(provider: str, config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Get configuration for a specific LLM provider.
    
    Args:
        provider: The LLM provider (openai, anthropic, google)
        config_path: Optional path to a custom config file
        
    Returns:
        Dictionary containing LLM configuration
    """
    config = load_config(config_path)
    return config.get("llm", {}).get(provider, {})

# Add to agentmap/config.py

def get_storage_config_path(config_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Get the path for the storage configuration file.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Path object for the storage config file
    """
    config = load_config(config_path)
    return Path(config.get("storage_config_path", "storage_config.yaml"))

def load_storage_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load storage configuration from YAML file.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Dictionary containing storage configuration values
    """
    storage_config_path = get_storage_config_path(config_path)
    
    if storage_config_path.exists():
        with storage_config_path.open() as f:
            storage_config = yaml.safe_load(f)
            if storage_config is None:  # Handle empty config file
                storage_config = {}
    else:
        storage_config = {}
    
    # Default storage configuration
    defaults = {
        "csv": {
            "default_directory": "data/csv",
            "collections": {}
        },
        "vector": {
            "default_provider": "local",
            "collections": {}
        },
        "kv": {
            "default_provider": "local",
            "collections": {}
        }
    }
    
    # Apply defaults for missing values
    for key, value in defaults.items():
        if key not in storage_config:
            storage_config[key] = value
        elif isinstance(value, dict) and key in storage_config:
            # Merge nested dictionaries
            for nested_key, nested_value in value.items():
                if nested_key not in storage_config[key]:
                    storage_config[key][nested_key] = nested_value
    
    return storage_config