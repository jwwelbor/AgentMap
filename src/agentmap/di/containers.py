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
    # Use a simple provider that can be overridden with a string value
    config_path = providers.Object(None)
    
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
    @staticmethod
    def _create_storage_config_service(config_service, app_config_service):
        """
        Create storage config service with graceful failure handling.
        
        Returns None if StorageConfigurationNotAvailableException occurs,
        allowing the application to continue without storage configuration.
        """
        try:
            from agentmap.services.config.storage_config_service import StorageConfigService
            storage_config_path = app_config_service.get_storage_config_path()
            return StorageConfigService(config_service, storage_config_path)
        except Exception as e:
            # Import the specific exception to check for it
            from agentmap.exceptions.service_exceptions import StorageConfigurationNotAvailableException
            
            if isinstance(e, StorageConfigurationNotAvailableException):
                # Return None for graceful degradation
                return None
            else:
                # Re-raise other exceptions as they indicate real problems
                raise
    
    storage_config_service = providers.Singleton(
        _create_storage_config_service,
        config_service,
        app_config_service
    )
    
    # Logging service factory that creates AND initializes the service
    @staticmethod
    def _create_and_initialize_logging_service(app_config_service):
        """
        Create and initialize LoggingService.
        
        This factory ensures the LoggingService is properly initialized
        after creation, which is required before other services can use it.
        """
        from agentmap.services.logging_service import LoggingService
        logging_config = app_config_service.get_logging_config()
        service = LoggingService(logging_config)
        service.initialize()  # Critical: initialize before returning
        return service
    
    logging_service = providers.Singleton(
        _create_and_initialize_logging_service,
        app_config_service
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
    def _create_storage_service_manager(storage_config_service, logging_service):
        """
        Create storage service manager with graceful failure handling.
        
        Returns None if storage_config_service is None or if any exception occurs,
        allowing the application to continue without storage features.
        """
        try:
            # If storage config service is None, storage is not available
            if storage_config_service is None:
                logger = logging_service.get_logger("agentmap.storage")
                logger.info("Storage configuration not available - storage services disabled")
                return None
                
            from agentmap.services.storage.manager import StorageServiceManager
            return StorageServiceManager(storage_config_service, logging_service)
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
    
    # NEW SERVICES - Clean Architecture Migration
    
    # LEVEL 1: Utility Services (no business logic dependencies)
    
    # Function Resolution Service for dynamic function loading
    function_resolution_service = providers.Singleton(
        "agentmap.services.function_resolution_service.FunctionResolutionService",
        providers.Callable(
            lambda app_config: app_config.get_functions_path(),
            app_config_service
        )
    )
    
    # Validation Cache Service for caching validation results
    validation_cache_service = providers.Singleton(
        "agentmap.services.validation.validation_cache_service.ValidationCacheService"
    )
    
    # LEVEL 2: Validation Services (depend on Level 1 + basic services)
    
    # CSV Validation Service for validating CSV structure and content
    csv_validation_service = providers.Singleton(
        "agentmap.services.validation.csv_validation_service.CSVValidationService",
        logging_service,
        function_resolution_service
    )
    
    # Config Validation Service for validating configuration files
    config_validation_service = providers.Singleton(
        "agentmap.services.validation.config_validation_service.ConfigValidationService",
        logging_service
    )
    
    # Main Validation Service (orchestrates all validation)
    validation_service = providers.Singleton(
        "agentmap.services.validation.validation_service.ValidationService",
        app_config_service,
        logging_service,
        csv_validation_service,
        config_validation_service,
        validation_cache_service
    )
    
    # LEVEL 3: Core Services (depend on Level 1 & 2)
    
    # StateAdapterService for state management (no dependencies)
    state_adapter_service = providers.Singleton(
        "agentmap.services.state_adapter_service.StateAdapterService"
    )
    
    # Global model instances for shared state
    features_registry_model = providers.Singleton(
        "agentmap.models.features_registry.FeaturesRegistry"
    )
    
    agent_registry_model = providers.Singleton(
        "agentmap.models.agent_registry.AgentRegistry"
    )
    
    # Features registry service (operates on global features model)
    features_registry_service = providers.Singleton(
        "agentmap.services.features_registry_service.FeaturesRegistryService",
        features_registry_model,
        logging_service
    )
    
    # Agent registry service (operates on global agent model)
    agent_registry_service = providers.Singleton(
        "agentmap.services.agent_registry_service.AgentRegistryService",
        agent_registry_model,
        logging_service
    )
    
    # LEVEL 4: Advanced Services (depend on Level 1, 2 & 3)
    
    # Graph Assembly Service for assembling StateGraph instances
    graph_assembly_service = providers.Singleton(
        "agentmap.services.graph_assembly_service.GraphAssemblyService",
        app_config_service,
        logging_service,
        state_adapter_service,
        features_registry_service,
        function_resolution_service
    )
    
    # CSV Graph Parser Service for pure CSV parsing functionality
    csv_graph_parser_service = providers.Singleton(
        "agentmap.services.csv_graph_parser_service.CSVGraphParserService",
        logging_service
    )
    
    # Graph Definition Service (renamed from GraphBuilderService) for graph building with CSV parsing delegation
    graph_definition_service = providers.Singleton(
        "agentmap.services.graph_definition_service.GraphDefinitionService",
        logging_service,                # 1st: logging_service (correct order)
        app_config_service,             # 2nd: app_config_service 
        csv_graph_parser_service        # 3rd: csv_parser
    )

    # Graph Bundle Service for graph bundle operations
    graph_bundle_service = providers.Singleton(
        "agentmap.services.graph_bundle_service.GraphBundleService",
        providers.Callable(
            lambda logging_service: logging_service.get_logger("agentmap.graph_bundle"),
            logging_service
        )
    )

    # Graph Export Service for exporting graphs in various formats
    # Note: CompilationService dependency temporarily removed to avoid circular dependency
    graph_export_service = providers.Singleton(
        "agentmap.services.graph_export_service.GraphExportService",
        app_config_service,
        logging_service,
        function_resolution_service,
        graph_bundle_service,
        # compilation_service,  # TODO: Add back after resolving circular dependency
    )
    
    
    # Compilation Service for graph compilation and auto-compile capabilities
    compilation_service = providers.Singleton(
        "agentmap.services.compilation_service.CompilationService",
        graph_definition_service,
        logging_service,
        app_config_service,
        node_registry_service,
        graph_bundle_service,
        graph_assembly_service,
        function_resolution_service
    )
    
    # ExecutionTrackingService for creating clean ExecutionTracker instances
    execution_tracking_service = providers.Singleton(
        "agentmap.services.execution_tracking_service.ExecutionTrackingService",
        app_config_service,
        logging_service
    )

    # ExecutionPolicyService for policy evaluation (clean architecture)
    execution_policy_service = providers.Singleton(
        "agentmap.services.execution_policy_service.ExecutionPolicyService",
        app_config_service,
        logging_service
    )
    
    # Graph Execution Service for clean execution orchestration
    graph_execution_service = providers.Singleton(
        "agentmap.services.graph_execution_service.GraphExecutionService",
        execution_tracking_service,
        execution_policy_service,
        state_adapter_service,
        graph_assembly_service,
        graph_bundle_service,
        logging_service
    )


    # PromptManagerService for external template management
    prompt_manager_service = providers.Singleton(
        "agentmap.services.prompt_manager_service.PromptManagerService",
        app_config_service,
        logging_service
    )
    
    # IndentedTemplateComposer for clean template composition with internal template loading
    indented_template_composer = providers.Singleton(
        "agentmap.services.indented_template_composer.IndentedTemplateComposer",
        app_config_service,
        logging_service
    )
    
    # GraphScaffoldService for service-aware scaffolding
    graph_scaffold_service = providers.Singleton(
        "agentmap.services.graph_scaffold_service.GraphScaffoldService",
        app_config_service,
        logging_service,
        function_resolution_service,
        agent_registry_service,
        indented_template_composer
    )
    



    
    # Additional utility providers for common transformations
    
    # LEVEL 5: Higher-level Services (depend on previous levels)
    
    # Agent factory service (coordinates between registry and features)
    agent_factory_service = providers.Singleton(
        "agentmap.services.agent_factory_service.AgentFactoryService",
        agent_registry_service,
        features_registry_service,
        logging_service
    )

    # Dependency checker service (with features registry coordination)
    dependency_checker_service = providers.Singleton(
        "agentmap.services.dependency_checker_service.DependencyCheckerService",
        logging_service,
        features_registry_service
    )

    # Application bootstrap service (coordinates agent registration and feature discovery)
    application_bootstrap_service = providers.Singleton(
        "agentmap.services.application_bootstrap_service.ApplicationBootstrapService",
        agent_registry_service,
        features_registry_service,
        dependency_checker_service,
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

     # Graph Runner Service - Simplified facade service for complete graph execution
    graph_runner_service = providers.Singleton(
        "agentmap.services.graph_runner_service.GraphRunnerService",
        graph_definition_service,
        graph_execution_service,
        compilation_service,
        graph_bundle_service,
        agent_factory_service,
        llm_service,
        storage_service_manager,
        node_registry_service,
        logging_service,
        app_config_service,
        execution_tracking_service,
        execution_policy_service,
        state_adapter_service,
        dependency_checker_service,
        graph_assembly_service,
        prompt_manager_service
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
