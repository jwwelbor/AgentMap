"""
Prompt-related configuration for AgentMap.
"""
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agentmap.config.base import load_config, get_config_section

def get_prompts_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Get the prompt configuration from the config.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Dictionary containing prompt configuration
    """
    return get_config_section("prompts", config_path)

def get_prompts_directory(config_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Get the path for the prompts directory from config.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Path object for the prompts directory
    """
    config = load_config(config_path)
    return Path(config.get("prompts", {}).get("directory", "prompts"))

def get_prompt_registry_path(config_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Get the path for the prompt registry file from config.
    
    Args:
        config_path: Optional path to a custom config file
        
    Returns:
        Path object for the prompt registry file
    """
    config = load_config(config_path)
    return Path(config.get("prompts", {}).get("registry_file", "prompts/registry.yaml"))