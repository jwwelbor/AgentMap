"""
Storage-related configuration for AgentMap.
"""
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agentmap.config.base import load_config, _merge_with_defaults

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
            storage_config = yaml.safe_load(f) or {}
    else:
        storage_config = {}
    
    # Default storage configuration
    defaults = {
        "csv": {"default_directory": "data/csv", "collections": {}},
        "vector": {"default_provider": "local", "collections": {}},
        "kv": {"default_provider": "local", "collections": {}}
    }
    
    # Merge with defaults
    return _merge_with_defaults(storage_config, defaults)