# agentmap/di/containers.py
from dependency_injector import containers, providers
from agentmap.config.base import load_config
from agentmap.config.configuration import Configuration
from agentmap.logging.service import LoggingService

class ConfigProviders(containers.DeclarativeContainer):
    """Configuration providers container."""
    
    # Configuration path
    config_path = providers.Configuration("config_path")
    
    # Load the config data
    config_data = providers.Resource(
        load_config,
        config_path
    )
    
    # Create a single Configuration object
    configuration = providers.Singleton(
        Configuration,
        config_data
    )


class LoggingProviders(containers.DeclarativeContainer):
    """Logging providers container."""

    # Configuration dependency
    configuration = providers.DependenciesContainer()

    # Create logging service
    logging_service = providers.Singleton(
        LoggingService,
        configuration.provided.get_section("logging")
    )


class ApplicationContainer(containers.DeclarativeContainer):
    """Main application container."""

    # Set up config container
    config = providers.Container(
        ConfigProviders,
        config_path=None
    )

    # Set up logging container
    logging = providers.Container(
        LoggingProviders,
        configuration=config.configuration
    )