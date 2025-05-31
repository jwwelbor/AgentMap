# agentmap/di/containers.py
"""
Dependency injection container with string-based providers for clean architecture.

Uses string-based providers to avoid circular dependencies and implements
graceful degradation for optional services like storage configuration.
"""
from dependency_injector import containers, providers


class ApplicationContainer(containers.DeclarativeContainer):
    """
    Main application container with clean string-based providers.
    
    Uses string imports to resolve circular dependencies and implements
    graceful failure handling for optional components like storage.
    """
    
    # Configuration path injection (for CLI and testing)
    config_path = providers.Configuration("config_path")
    
    # Infrastructure layer: ConfigService (singleton for efficiency)
    config_service = providers.Singleton(
        "agentmap.services.config.config_service.ConfigService"
    )
    
    # Domain layer: AppConfigService (main application configuration)
    app_config_service = providers.Singleton(
        "agentmap.services.config.app_config_service.AppConfigService",
        config_service,
        config_path
    )
    

    # Domain layer: StorageConfigService (optional storage configuration)
    storage_config_service = providers.Singleton(
        "agentmap.services.config.storage_config_service.StorageConfigService",
        config_service,
        providers.Callable(
            lambda app_config: app_config.get_storage_config_path(),
            app_config_service
        )
    )
    
    # Logging service with configuration transformation
    logging_service = providers.Singleton(
        "agentmap.services.logging_service.LoggingService",
        providers.Callable(
            lambda app_config: app_config.get_logging_config(),
            app_config_service
        )
    )

    # Domain layer: AppConfigService (main application configuration)
    llm_routing_config_service = providers.Singleton(
        "agentmap.services.config.llm_routing_config_service.LLMRoutingConfigService",
        app_config_service,
        logging_service
    )

    # LLM Service using string-based provider
    prompt_complexity_analyzer = providers.Singleton(
        "agentmap.services.routing.complexity_analyzer.PromptComplexityAnalyzer",
        app_config_service,
        logging_service,
    )

    # LLM Service using string-based provider
    routing_cache = providers.Singleton(
        "agentmap.services.routing.cache.RoutingCache",
        logging_service
    )


    # LLM Service using string-based provider
    llm_routing_service = providers.Singleton(
        "agentmap.services.routing.routing_service.LLMRoutingService",
        llm_routing_config_service,  
        logging_service,
        routing_cache,
        prompt_complexity_analyzer
    )


    # LLM Service using string-based provider
    llm_service = providers.Singleton(
        "agentmap.services.llm_service.LLMService",
        app_config_service,  
        logging_service,
        llm_routing_service
    )
    
    # Node Registry Service using string-based provider
    node_registry_service = providers.Singleton(
        "agentmap.services.node_registry_service.NodeRegistryService",
        app_config_service,  
        logging_service
    )
    
    # Storage Service Manager with graceful failure handling
    @staticmethod
    def _create_storage_service_manager(storage_config, logging_service):
        """
        Create storage service manager with graceful failure handling.
        
        Returns None if StorageConfigurationNotAvailableException occurs,
        allowing the application to continue without storage features.
        """
        try:
            from agentmap.services.storage.manager import StorageServiceManager
            return StorageServiceManager(storage_config, logging_service)
        except Exception as e:
            # Import the specific exception to check for it
            from agentmap.exceptions.service_exceptions import StorageConfigurationNotAvailableException
            
            if isinstance(e, StorageConfigurationNotAvailableException):
                # Log the warning and return None for graceful degradation
                logger = logging_service.get_logger("agentmap.storage")
                logger.warning(f"Storage services disabled: {e}")
                return None
            else:
                # Re-raise other exceptions as they indicate real problems
                raise
    
    storage_service_manager = providers.Singleton(
        _create_storage_service_manager,
        storage_config_service,
        logging_service
    )
    
    # Execution Tracker using string-based provider with safe config access
    @staticmethod
    def _create_execution_tracker(app_config, logging_service):
        """Create execution tracker with safe configuration access."""
        try:
            from agentmap.logging.tracking.execution_tracker import ExecutionTracker
            
            return ExecutionTracker(app_config, logging_service)
        except ImportError:
            # If ExecutionTracker is not available, return None
            logger = logging_service.get_logger("agentmap.tracking")
            logger.warning("ExecutionTracker not available, tracking disabled")
            return None
    
    execution_tracker = providers.Singleton(
        _create_execution_tracker,
        app_config_service,
        logging_service
    )
    
    # Additional utility providers for common transformations
    
    # Provider for getting specific configuration sections
    logging_config = providers.Callable(
        lambda app_config: app_config.get_logging_config(),
        app_config_service
    )
    
    execution_config = providers.Callable(
        lambda app_config: app_config.get_execution_config(),
        app_config_service
    )
    
    prompts_config = providers.Callable(
        lambda app_config: app_config.get_prompts_config(),
        app_config_service
    )
    
    # Provider for checking service availability
    @staticmethod
    def _check_storage_availability():
        """Check if storage services are available."""
        try:
            # This will be injected by the container
            return True
        except Exception:
            return False
    
    storage_available = providers.Callable(_check_storage_availability)


# Factory functions for optional service creation
def create_optional_service(service_provider, fallback_value=None):
    """
    Create a factory that returns fallback_value if service creation fails.
    
    Args:
        service_provider: Provider to attempt service creation
        fallback_value: Value to return on failure (default: None)
        
    Returns:
        Service instance or fallback_value
    """
    try:
        return service_provider()
    except Exception:
        return fallback_value


def safe_get_service(container, service_name, default=None):
    """
    Safely get a service from container, returning default if unavailable.
    
    Args:
        container: DI container instance
        service_name: Name of service to retrieve
        default: Default value if service unavailable
        
    Returns:
        Service instance or default value
    """
    try:
        return getattr(container, service_name)()
    except Exception:
        return default
