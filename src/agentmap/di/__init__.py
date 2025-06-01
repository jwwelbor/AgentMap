# agentmap/di/__init__.py
from typing import Optional, Union
from pathlib import Path
from agentmap.di.containers import ApplicationContainer

# Global container instance
application = ApplicationContainer()


def _replace_bootstrap_loggers(app_config_service, logging_service):
    """
    Replace bootstrap loggers with real loggers after LoggingService is online.
    
    Args:
        app_config_service: AppConfigService instance
        logging_service: LoggingService instance
    """
    # Get the ConfigService instance from AppConfigService
    config_service = app_config_service._config_service
    
    # Create real loggers with appropriate names
    config_logger = logging_service.get_logger("agentmap.config")
    app_config_logger = logging_service.get_logger("agentmap.app_config")
    
    # Replace bootstrap loggers in config services
    try:
        config_service.replace_logger(config_logger)
        app_config_service.replace_logger(app_config_logger)
        
        # Log successful replacements
        config_logger.debug("Bootstrap logger replaced with real logger for ConfigService")
        app_config_logger.debug("Bootstrap logger replaced with real logger for AppConfigService")
        
    except Exception as e:
        # If replacement fails, log the error but continue
        logging_service.get_logger("agentmap.di").warning(
            f"Failed to replace bootstrap loggers for config services: {e}"
        )
    
    # Try to replace logger for storage config service (may not exist)
    try:
        storage_config_service = application.storage_config_service()
        if storage_config_service:
            storage_config_logger = logging_service.get_logger("agentmap.storage_config")
            storage_config_service.replace_logger(storage_config_logger)
            storage_config_logger.debug("Bootstrap logger replaced with real logger for StorageConfigService")
    except Exception:
        # Storage config service is optional and may not be available
        # This is expected behavior, so we don't log it as an error
        pass


def initialize_di(config_path: Optional[Union[str, Path]] = None) -> ApplicationContainer:
    """
    Initialize the DI container for CLI usage.

    This should be called at the start of every CLI command before
    any code that uses @inject decorators.

    Args:
        config_path: Path to the configuration file

    Returns:
        Initialized application container
    """
    # Configure the container with the provided config path
    config_path = config_path or "agentmap_config.yaml"
    application.config_path.override(config_path)

    # Initialize configuration services first
    # This will load the main config and validate it
    app_config_service = application.app_config_service()
    
    # Initialize logging service early - this ensures logging is configured
    # before any other code that might want to log
    logging_service = application.logging_service()
    logging_service.initialize()
    
    # Replace bootstrap loggers with real loggers now that LoggingService is online
    _replace_bootstrap_loggers(app_config_service, logging_service)

    # Try to initialize storage config service (may fail gracefully)
    try:
        storage_config_service = application.storage_config_service()
    except Exception as e:
        # Storage config failure is expected and handled gracefully
        from agentmap.exceptions.service_exceptions import StorageConfigurationNotAvailableException
        if isinstance(e, StorageConfigurationNotAvailableException):
            # This is expected - storage is optional
            pass
        else:
            # Re-raise unexpected errors
            raise

    # Wire the container to all modules that use injection
    application.wire(modules=[
        "agentmap.compiler",
        "agentmap.graph.assembler",
        "agentmap.graph.builder",
        "agentmap.graph.scaffold",
        "agentmap.prompts.manager",
        "agentmap.services.llm_service",
        "agentmap.services.node_registry_service",
        "agentmap.services.routing.cache",
        "agentmap.services.routing.complexity_analyzer",
        "agentmap.services.routing.routing_service",
        "agentmap.runner",
    ])

    # Force initialization of core services to catch any errors early
    _ = application.llm_service()
    
    # Check if storage services are available
    storage_manager = application.storage_service_manager()
    if storage_manager is None:
        # Log that storage is unavailable but continue
        logger = logging_service.get_logger("agentmap.di")
        logger.info("Storage services are not available - running without storage features")

    return application


def cleanup():
    """Clean up the DI container (useful for testing or between commands)."""
    try:
        # Reset logging if available
        logging_service = application.logging_service()
        if logging_service and logging_service.is_initialized():
            logging_service.reset()
    except Exception:
        # If logging service is not available, continue cleanup
        pass
    
    # Reset any bootstrap loggers in config services
    try:
        app_config_service = application.app_config_service()
        if hasattr(app_config_service, '_logger'):
            app_config_service._logger = None
        
        config_service = app_config_service._config_service
        if hasattr(config_service, '_bootstrap_logger'):
            config_service._bootstrap_logger = None
    except Exception:
        # Config services may not be available
        pass

    # Unwire the container
    application.unwire()
    
    # Reset any cached providers
    application.reset_last_provided()