# agentmap/di/containers.py
"""
Dependency injection container with string-based providers for clean architecture.

Uses string-based providers to avoid circular dependencies and implements
graceful degradation for optional services like storage configuration.
"""
from typing import Any, Dict, List, Optional, Type

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
        config_path,
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
            from agentmap.services.config.storage_config_service import (
                StorageConfigService,
            )

            storage_config_path = app_config_service.get_storage_config_path()
            return StorageConfigService(config_service, storage_config_path)
        except Exception as e:
            # Import the specific exception to check for it
            from agentmap.exceptions.service_exceptions import (
                StorageConfigurationNotAvailableException,
            )

            if isinstance(e, StorageConfigurationNotAvailableException):
                # Return None for graceful degradation
                return None
            else:
                # Re-raise other exceptions as they indicate real problems
                raise

    storage_config_service = providers.Singleton(
        _create_storage_config_service, config_service, app_config_service
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
        _create_and_initialize_logging_service, app_config_service
    )

    # Domain layer: AppConfigService (main application configuration)
    llm_routing_config_service = providers.Singleton(
        "agentmap.services.config.llm_routing_config_service.LLMRoutingConfigService",
        app_config_service,
        logging_service,
    )

    # LLM Service using string-based provider
    prompt_complexity_analyzer = providers.Singleton(
        "agentmap.services.routing.complexity_analyzer.PromptComplexityAnalyzer",
        app_config_service,
        logging_service,
    )

    # LLM Service using string-based provider
    routing_cache = providers.Singleton(
        "agentmap.services.routing.cache.RoutingCache", logging_service
    )

    # LLM Service using string-based provider
    llm_routing_service = providers.Singleton(
        "agentmap.services.routing.routing_service.LLMRoutingService",
        llm_routing_config_service,
        logging_service,
        routing_cache,
        prompt_complexity_analyzer,
    )

    # LLM Service using string-based provider
    llm_service = providers.Singleton(
        "agentmap.services.llm_service.LLMService",
        app_config_service,
        logging_service,
        llm_routing_service,
    )

    # Authentication service for API security
    @staticmethod
    def _create_auth_service(app_config_service, logging_service):
        """
        Create authentication service with proper configuration injection.

        Returns auth service instance with loaded configuration.
        """
        from agentmap.services.auth_service import AuthService

        auth_config = app_config_service.get_auth_config()
        return AuthService(auth_config, logging_service)

    auth_service = providers.Singleton(
        _create_auth_service,
        app_config_service,
        logging_service,
    )

    # Node Registry Service using string-based provider
    node_registry_service = providers.Singleton(
        "agentmap.services.node_registry_service.NodeRegistryService",
        app_config_service,
        logging_service,
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
                logger.info(
                    "Storage configuration not available - storage services disabled"
                )
                return None

            from agentmap.services.storage.manager import StorageServiceManager

            return StorageServiceManager(storage_config_service, logging_service)
        except Exception as e:
            # Import the specific exception to check for it
            from agentmap.exceptions.service_exceptions import (
                StorageConfigurationNotAvailableException,
            )

            if isinstance(e, StorageConfigurationNotAvailableException):
                # Log the warning and return None for graceful degradation
                logger = logging_service.get_logger("agentmap.storage")
                logger.warning(f"Storage services disabled: {e}")
                return None
            else:
                # Re-raise other exceptions as they indicate real problems
                raise

    storage_service_manager = providers.Singleton(
        _create_storage_service_manager, storage_config_service, logging_service
    )

    # LEVEL 1: Utility Services (no business logic dependencies)

    # Function Resolution Service for dynamic function loading
    function_resolution_service = providers.Singleton(
        "agentmap.services.function_resolution_service.FunctionResolutionService",
        providers.Callable(
            lambda app_config: app_config.get_functions_path(), app_config_service
        ),
    )

    # Validation Cache Service for caching validation results
    validation_cache_service = providers.Singleton(
        "agentmap.services.validation.validation_cache_service.ValidationCacheService"
    )

    # LEVEL 2: Basic Services (no dependencies on other business services)

    # Config Validation Service for validating configuration files
    config_validation_service = providers.Singleton(
        "agentmap.services.validation.config_validation_service.ConfigValidationService",
        logging_service,
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
        logging_service,
    )

    # Agent registry service (operates on global agent model)
    agent_registry_service = providers.Singleton(
        "agentmap.services.agent_registry_service.AgentRegistryService",
        agent_registry_model,
        logging_service,
    )

    # CSV Validation Service for validating CSV structure and content
    # (moved from Level 2 to here since it depends on agent_registry_service)
    csv_validation_service = providers.Singleton(
        "agentmap.services.validation.csv_validation_service.CSVValidationService",
        logging_service,
        function_resolution_service,
        agent_registry_service,
    )

    # Main Validation Service (orchestrates all validation)
    validation_service = providers.Singleton(
        "agentmap.services.validation.validation_service.ValidationService",
        app_config_service,
        logging_service,
        csv_validation_service,
        config_validation_service,
        validation_cache_service,
    )

    # LEVEL 4: Advanced Services (depend on Level 1, 2 & 3)

    # CSV Graph Parser Service for pure CSV parsing functionality
    csv_graph_parser_service = providers.Singleton(
        "agentmap.services.csv_graph_parser_service.CSVGraphParserService",
        logging_service,
    )

    # Graph Factory Service for centralized graph creation (no dependencies except logging)
    graph_factory_service = providers.Singleton(
        "agentmap.services.graph_factory_service.GraphFactoryService",
        logging_service,
    )

    # Graph Assembly Service for assembling StateGraph instances
    graph_assembly_service = providers.Singleton(
        "agentmap.services.graph_assembly_service.GraphAssemblyService",
        app_config_service,
        logging_service,
        state_adapter_service,
        features_registry_service,
        function_resolution_service,
        graph_factory_service,
    )

    # Graph Definition Service (renamed from GraphBuilderService) for graph building with CSV parsing delegation
    graph_definition_service = providers.Singleton(
        "agentmap.services.graph_definition_service.GraphDefinitionService",
        logging_service,  # 1st: logging_service (correct order)
        app_config_service,  # 2nd: app_config_service
        csv_graph_parser_service,  # 3rd: csv_parser
        graph_factory_service,  # 4th: graph_factory
    )

    # Graph Bundle Service for graph bundle operations
    graph_bundle_service = providers.Singleton(
        "agentmap.services.graph_bundle_service.GraphBundleService",
        providers.Callable(
            lambda logging_service: logging_service.get_logger("agentmap.graph_bundle"),
            logging_service,
        ),
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
        function_resolution_service,
    )

    # Graph Output Service for exporting graphs in human-readable formats
    graph_output_service = providers.Singleton(
        "agentmap.services.graph_output_service.GraphOutputService",
        app_config_service,
        logging_service,
        function_resolution_service,
        agent_registry_service,
        compilation_service,
    )

    # ExecutionTrackingService for creating clean ExecutionTracker instances
    execution_tracking_service = providers.Singleton(
        "agentmap.services.execution_tracking_service.ExecutionTrackingService",
        app_config_service,
        logging_service,
    )

    # ExecutionPolicyService for policy evaluation (clean architecture)
    execution_policy_service = providers.Singleton(
        "agentmap.services.execution_policy_service.ExecutionPolicyService",
        app_config_service,
        logging_service,
    )

    # Graph Execution Service for clean execution orchestration
    graph_execution_service = providers.Singleton(
        "agentmap.services.graph_execution_service.GraphExecutionService",
        execution_tracking_service,
        execution_policy_service,
        state_adapter_service,
        graph_assembly_service,
        graph_bundle_service,
        graph_factory_service,
        logging_service,
    )

    # Execution Formatter Service for formatting graph execution results (development/testing)
    execution_formatter_service = providers.Singleton(
        "agentmap.services.execution_formatter_service.ExecutionFormatterService"
    )

    # PromptManagerService for external template management
    prompt_manager_service = providers.Singleton(
        "agentmap.services.prompt_manager_service.PromptManagerService",
        app_config_service,
        logging_service,
    )

    # OrchestratorService for node selection and orchestration business logic
    orchestrator_service = providers.Singleton(
        "agentmap.services.orchestrator_service.OrchestratorService",
        prompt_manager_service,
        logging_service,
        llm_service,
        features_registry_service,
    )

    # IndentedTemplateComposer for clean template composition with internal template loading
    indented_template_composer = providers.Singleton(
        "agentmap.services.indented_template_composer.IndentedTemplateComposer",
        app_config_service,
        logging_service,
    )

    # GraphScaffoldService for service-aware scaffolding
    graph_scaffold_service = providers.Singleton(
        "agentmap.services.graph_scaffold_service.GraphScaffoldService",
        app_config_service,
        logging_service,
        function_resolution_service,
        agent_registry_service,
        indented_template_composer,
    )

    # Additional utility providers for common transformations

    # LEVEL 5: Higher-level Services (depend on previous levels)

    # Agent factory service (coordinates between registry and features)
    agent_factory_service = providers.Singleton(
        "agentmap.services.agent_factory_service.AgentFactoryService",
        agent_registry_service,
        features_registry_service,
        logging_service,
    )

    # Dependency checker service (with features registry coordination)
    dependency_checker_service = providers.Singleton(
        "agentmap.services.dependency_checker_service.DependencyCheckerService",
        logging_service,
        features_registry_service,
    )

    # Host Service Registry for managing host service registration
    host_service_registry = providers.Singleton(
        "agentmap.services.host_service_registry.HostServiceRegistry", logging_service
    )

    # Host Protocol Configuration Service for configuring protocols on agents
    host_protocol_configuration_service = providers.Singleton(
        "agentmap.services.host_protocol_configuration_service.HostProtocolConfigurationService",
        host_service_registry,
        logging_service,
    )

    # Graph Checkpoint Service for managing workflow execution checkpoints
    graph_checkpoint_service = providers.Singleton(
        "agentmap.services.graph_checkpoint_service.GraphCheckpointService",
        providers.Callable(
            lambda storage_manager: (
                storage_manager.get_service("json") if storage_manager else None
            ),
            storage_service_manager,
        ),
        logging_service,
    )

    # Application bootstrap service (coordinates agent registration and feature discovery)
    application_bootstrap_service = providers.Singleton(
        "agentmap.services.application_bootstrap_service.ApplicationBootstrapService",
        agent_registry_service,
        features_registry_service,
        dependency_checker_service,
        app_config_service,
        logging_service,
        host_service_registry,
    )

    # Additional utility providers for common transformations

    # Provider for getting specific configuration sections
    logging_config = providers.Callable(
        lambda app_config: app_config.get_logging_config(), app_config_service
    )

    execution_config = providers.Callable(
        lambda app_config: app_config.get_execution_config(), app_config_service
    )

    prompts_config = providers.Callable(
        lambda app_config: app_config.get_prompts_config(), app_config_service
    )

    # Factory for GraphRunnerService that properly passes the container
    @staticmethod
    def _create_graph_runner_service(
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
        prompt_manager_service,
        orchestrator_service,
        host_protocol_configuration_service,
        graph_checkpoint_service,
    ):
        """Create GraphRunnerService with proper container injection."""
        from agentmap.services.graph_runner_service import GraphRunnerService

        return GraphRunnerService(
            graph_definition_service=graph_definition_service,
            graph_execution_service=graph_execution_service,
            compilation_service=compilation_service,
            graph_bundle_service=graph_bundle_service,
            agent_factory_service=agent_factory_service,
            llm_service=llm_service,
            storage_service_manager=storage_service_manager,
            node_registry_service=node_registry_service,
            logging_service=logging_service,
            app_config_service=app_config_service,
            execution_tracking_service=execution_tracking_service,
            execution_policy_service=execution_policy_service,
            state_adapter_service=state_adapter_service,
            dependency_checker_service=dependency_checker_service,
            graph_assembly_service=graph_assembly_service,
            prompt_manager_service=prompt_manager_service,
            orchestrator_service=orchestrator_service,
            host_protocol_configuration_service=host_protocol_configuration_service,  # Pass the service, not container
            graph_checkpoint_service=graph_checkpoint_service,
        )

    # Graph Runner Service - Simplified facade service for complete graph execution
    graph_runner_service = providers.Singleton(
        _create_graph_runner_service,
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
        prompt_manager_service,
        orchestrator_service,
        host_protocol_configuration_service,  # Pass the service provider
        graph_checkpoint_service,
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

    # ==========================================================================
    # HOST APPLICATION SERVICE INTEGRATION
    # ==========================================================================
    #
    # Host service registration and management through HostServiceRegistry.
    # All host service operations delegate to the registry service for clean
    # separation of concerns and maintainability.
    # ==========================================================================

    def register_host_service(
        self,
        service_name: str,
        service_class_path: str,
        dependencies: Optional[List[str]] = None,
        protocols: Optional[List[Type]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        singleton: bool = True,
    ) -> None:
        """
        Register a host application service using string-based provider pattern.

        Delegates to HostServiceRegistry for clean separation of concerns.

        Args:
            service_name: Unique name for the service
            service_class_path: String path to service class (e.g., "myapp.services.MyService")
            dependencies: List of dependency service names (from container)
            protocols: List of protocols this service implements
            metadata: Optional metadata about the service
            singleton: Whether to create as singleton (default: True)
        """
        if not service_name:
            raise ValueError("Service name cannot be empty")
        if not service_class_path:
            raise ValueError("Service class path cannot be empty")

        # Prevent overriding existing AgentMap services
        if hasattr(self, service_name):
            raise ValueError(
                f"Service '{service_name}' conflicts with existing AgentMap service"
            )

        try:
            # Get HostServiceRegistry
            registry = self.host_service_registry()

            # Check if service already registered
            if registry.is_service_registered(service_name):
                logger = self.logging_service().get_logger("agentmap.di.host")
                logger.warning(f"Overriding existing host service: {service_name}")

            # Create dependency providers
            dependency_providers = []
            if dependencies:
                for dep in dependencies:
                    if hasattr(self, dep):
                        # AgentMap service
                        dependency_providers.append(getattr(self, dep))
                    elif registry.is_service_registered(dep):
                        # Host service from registry
                        provider = registry.get_service_provider(dep)
                        if provider:
                            dependency_providers.append(provider)
                        else:
                            raise ValueError(
                                f"Host service '{dep}' is registered but provider not found"
                            )
                    else:
                        raise ValueError(
                            f"Dependency '{dep}' not found for service '{service_name}'"
                        )

            # Create provider using same pattern as AgentMap services
            if singleton:
                provider = providers.Singleton(
                    service_class_path, *dependency_providers
                )
            else:
                provider = providers.Factory(service_class_path, *dependency_providers)

            # Add to container as dynamic attribute for direct access
            setattr(self, service_name, provider)

            # Register with HostServiceRegistry
            registry.register_service_provider(
                service_name, provider, protocols=protocols, metadata=metadata
            )

        except Exception as e:
            # Clean up if registration failed
            if hasattr(self, service_name):
                delattr(self, service_name)
            raise ValueError(f"Failed to register host service '{service_name}': {e}")

    def register_host_factory(
        self,
        service_name: str,
        factory_function: callable,
        dependencies: Optional[List[str]] = None,
        protocols: Optional[List[Type]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a host service using a factory function.

        Delegates to HostServiceRegistry for clean separation of concerns.

        Args:
            service_name: Unique name for the service
            factory_function: Function that creates the service instance
            dependencies: List of dependency service names
            protocols: List of protocols this service implements
            metadata: Optional metadata about the service
        """
        if not service_name:
            raise ValueError("Service name cannot be empty")
        if not factory_function:
            raise ValueError("Factory function cannot be empty")

        # Prevent overriding existing AgentMap services
        if hasattr(self, service_name):
            raise ValueError(
                f"Service '{service_name}' conflicts with existing AgentMap service"
            )

        try:
            # Get HostServiceRegistry
            registry = self.host_service_registry()

            # Create dependency providers
            dependency_providers = []
            if dependencies:
                for dep in dependencies:
                    if hasattr(self, dep):
                        # AgentMap service
                        dependency_providers.append(getattr(self, dep))
                    elif registry.is_service_registered(dep):
                        # Host service from registry
                        provider = registry.get_service_provider(dep)
                        if provider:
                            dependency_providers.append(provider)
                        else:
                            raise ValueError(
                                f"Host service '{dep}' is registered but provider not found"
                            )
                    else:
                        raise ValueError(
                            f"Dependency '{dep}' not found for service '{service_name}'"
                        )

            # Create provider
            provider = providers.Singleton(factory_function, *dependency_providers)

            # Add to container as dynamic attribute for direct access
            setattr(self, service_name, provider)

            # Register with HostServiceRegistry
            registry.register_service_provider(
                service_name, provider, protocols=protocols, metadata=metadata
            )

        except Exception as e:
            # Clean up if registration failed
            if hasattr(self, service_name):
                delattr(self, service_name)
            raise ValueError(f"Failed to register host factory '{service_name}': {e}")

    def get_host_services(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all registered host services with metadata.

        Delegates to HostServiceRegistry for consistent data access.

        Returns:
            Dictionary with service information:
            - provider: The DI provider
            - metadata: Service metadata
            - protocols: List of protocol names implemented
        """
        try:
            registry = self.host_service_registry()
            result = {}

            # Get all services from registry
            for service_name in registry.list_registered_services():
                # Skip protocol placeholders
                if service_name.startswith("protocol:"):
                    continue

                provider = registry.get_service_provider(service_name)
                metadata = registry.get_service_metadata(service_name) or {}
                protocols = registry.get_service_protocols(service_name)

                result[service_name] = {
                    "provider": provider,
                    "metadata": metadata,
                    "protocols": [p.__name__ for p in protocols],
                }

            return result

        except Exception as e:
            logger = self.logging_service().get_logger("agentmap.di.host")
            logger.error(f"Failed to get host services: {e}")
            return {}

    def get_protocol_implementations(self) -> Dict[str, str]:
        """
        Get mapping of protocol names to service names.

        Delegates to HostServiceRegistry for consistent data access.

        Returns:
            Dictionary mapping protocol names to service names
        """
        try:
            registry = self.host_service_registry()
            implementations = {}

            # Build protocol to service mapping from registry data
            for service_name in registry.list_registered_services():
                if service_name.startswith("protocol:"):
                    continue

                protocols = registry.get_service_protocols(service_name)
                for protocol in protocols:
                    implementations[protocol.__name__] = service_name

            return implementations

        except Exception as e:
            logger = self.logging_service().get_logger("agentmap.di.host")
            logger.error(f"Failed to get protocol implementations: {e}")
            return {}

    def configure_host_protocols(self, agent: Any) -> int:
        """
        Configure host-defined protocols on an agent.

        Delegates to HostProtocolConfigurationService for clean separation of concerns.

        Args:
            agent: Agent instance to configure

        Returns:
            Number of host services configured
        """
        try:
            # Get the HostProtocolConfigurationService instance
            config_service = self.host_protocol_configuration_service()

            # Delegate to the service
            return config_service.configure_host_protocols(agent)

        except Exception as e:
            # Log error if possible
            try:
                logger = self.logging_service().get_logger("agentmap.di.host")
                logger.error(f"Failed to configure host protocols: {e}")
            except:
                pass

            # Return 0 on failure
            return 0

    def has_host_service(self, service_name: str) -> bool:
        """
        Check if a host service is registered.

        Delegates to HostServiceRegistry for consistent state.

        Args:
            service_name: Name of the service to check

        Returns:
            True if the service is registered
        """
        try:
            registry = self.host_service_registry()
            return registry.is_service_registered(service_name)
        except Exception:
            return False

    def get_host_service_instance(self, service_name: str) -> Optional[Any]:
        """
        Get a host service instance by name.

        Delegates to HostServiceRegistry for consistent access.

        Args:
            service_name: Name of the service

        Returns:
            Service instance or None if not found
        """
        try:
            registry = self.host_service_registry()
            service_provider = registry.get_service_provider(service_name)
            if service_provider and callable(service_provider):
                return service_provider()
            return service_provider
        except Exception:
            return None

    def clear_host_services(self) -> None:
        """
        Clear all registered host services.

        Warning: This removes all host service registrations.
        Used primarily for testing and cleanup.
        """
        try:
            registry = self.host_service_registry()

            # Get all services before clearing
            service_names = registry.list_registered_services()

            # Remove dynamic attributes from container
            for service_name in service_names:
                if not service_name.startswith("protocol:") and hasattr(
                    self, service_name
                ):
                    delattr(self, service_name)

            # Clear registry
            registry.clear_registry()

            logger = self.logging_service().get_logger("agentmap.di.host")
            logger.info("Cleared all host services")

        except Exception as e:
            try:
                logger = self.logging_service().get_logger("agentmap.di.host")
                logger.error(f"Failed to clear host services: {e}")
            except:
                pass


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
