# src/agentmap/di/containers.py
from dependency_injector import containers, providers
from agentmap.config.base import load_config
from agentmap.config.configuration import Configuration
from agentmap.logging.service import LoggingService

class ApplicationContainer(containers.DeclarativeContainer):
    """Main application container - flat structure."""
    
    # Configuration setup
    config_path = providers.Configuration("config_path", default=None)
    
    config_data = providers.Singleton(
        load_config,
        config_path
    )
    
    configuration = providers.Singleton(
        Configuration,
        config_data
    )
    
    # Logging setup
    logging_service = providers.Singleton(
        LoggingService,
        providers.Factory(
            lambda cfg: cfg.get_section("logging") if cfg else {},
            configuration
        )
    )
    
    # LLM Service - use lazy factory import to avoid circular dependency
    def _create_llm_service(config, logger):
        # Import here to avoid circular dependency
        from agentmap.services.llm_service import LLMService
        return LLMService(config, logger)
    
    llm_service = providers.Singleton(
        _create_llm_service,
        configuration,
        logging_service
    )