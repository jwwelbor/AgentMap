"""
Path-related configuration for AgentMap.
"""
from pathlib import Path
from typing import Optional, Union

from agentmap.config.base import load_config

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
    return Path(config.get("paths", {}).get("compiled_graphs", "compiled_graphs"))

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