"""
Dependency injection module for AgentMap.

This module provides a DI framework integration that leverages
the existing ConfigManager.
"""
from typing import Optional, Union
from pathlib import Path

from agentmap.di.containers import (
    ApplicationContainer,
    initialize_container,
    application
)

# Initialize on import for backward compatibility
initialized = False

def init(config_path: Optional[Union[str, Path]] = None) -> ApplicationContainer:
    """
    Initialize the dependency injection system.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Initialized application container
    """
    global initialized
    container = initialize_container(config_path)
    initialized = True
    return container


# Export public API
__all__ = [
    'ApplicationContainer',
    'initialize_container',
    'init',
    'application'
]