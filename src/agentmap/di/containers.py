"""
Dependency injection containers for AgentMap.

This module provides the DI setup using dependency_injector while
leveraging the existing ConfigManager.
"""
from pathlib import Path
from typing import Dict, Any, Optional, Union

from dependency_injector import containers, providers

from agentmap.logging import get_logger
from agentmap.config.base import ConfigManager, load_config

logger = get_logger(__name__)


class ConfigProviders(containers.DeclarativeContainer):
    """Configuration providers container."""
    
    # Configuration path
    config_path = providers.Configuration("config_path")
    
    # Load the config
    config = providers.Resource(
        load_config,
        config_path
    )
    
    # Provider for LLM configuration
    llm_provider_name = providers.Configuration("llm_provider_name")
    
    llm_config = providers.Callable(
        lambda config, provider_name: config.get("llm", {}).get(provider_name, {}),
        config,
        llm_provider_name
    )


class ApplicationContainer(containers.DeclarativeContainer):
    """Main application container."""
    
    # Set up config container
    config = providers.Container(
        ConfigProviders,
        config_path=None
    )


# Global container instance
application = ApplicationContainer()


def initialize_container(config_path: Optional[Union[str, Path]] = None) -> ApplicationContainer:
    """
    Initialize the DI container.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Initialized container
    """
    # Configure with provided path
    application.config.config_path.override(config_path)
    
    # Initialize the config resource
    _ = application.config.config()
    
    logger.debug(f"DI container initialized with config path: {config_path}")
    return application