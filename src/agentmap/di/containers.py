# src/agentmap/di/containers.py
from dependency_injector import containers, providers
from agentmap.config.base import load_config
from agentmap.config.configuration import Configuration

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
    
    # Logging setup - create logging service directly
    def _create_logging_service(config):
        """Create logging service with safe configuration."""
        try:
            if config is None:
                logging_config = {}
            else:
                logging_config = config.get_section("logging") or {}
        except Exception:
            logging_config = {}
        
        from agentmap.logging.service import LoggingService
        return LoggingService(logging_config)
    
    logging_service = providers.Singleton(
        _create_logging_service,
        configuration
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
    
    # Node Registry Service - use lazy factory import to avoid circular dependency
    def _create_node_registry_service(config, logger):
        # Import here to avoid circular dependency
        from agentmap.services.node_registry_service import NodeRegistryService
        return NodeRegistryService(config, logger)
    
    node_registry_service = providers.Singleton(
        _create_node_registry_service,
        configuration,
        logging_service
    )
    
    # Storage Service Manager - use lazy factory import to avoid circular dependency
    def _create_storage_service_manager(config, logger):
        # Import here to avoid circular dependency
        from agentmap.services.storage.manager import StorageServiceManager
        return StorageServiceManager(config, logger)
    
    storage_service_manager = providers.Singleton(
        _create_storage_service_manager,
        configuration,
        logging_service
    )