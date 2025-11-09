"""Composable dependency-injection container built from modular parts."""

from __future__ import annotations

from dependency_injector import containers, providers

from .container_parts.bootstrap import BootstrapContainer
from .container_parts.core import CoreContainer
from .container_parts.graph_agent import GraphAgentContainer
from .container_parts.graph_core import GraphCoreContainer
from .container_parts.host_registry import HostRegistryContainer
from .container_parts.llm import LLMContainer
from .container_parts.storage import StorageContainer
from .utils import create_optional_service, safe_get_service


def _expose(
    container_provider: providers.Provider, attribute: str
) -> providers.Callable:
    """Return a provider that resolves an attribute from a nested container."""

    return providers.Callable(
        lambda container: getattr(container, attribute)(), container_provider
    )


class ApplicationContainer(containers.DeclarativeContainer):
    """Main AgentMap application container composed from container parts."""

    config = providers.Configuration()

    # --- Container parts -------------------------------------------------------

    _core = providers.Container(CoreContainer, config=config)

    _storage = providers.Container(
        StorageContainer,
        config_service=_expose(_core, "config_service"),
        app_config_service=_expose(_core, "app_config_service"),
        availability_cache_service=_expose(_core, "availability_cache_service"),
        logging_service=_expose(_core, "logging_service"),
        file_path_service=_expose(_core, "file_path_service"),
    )

    _bootstrap = providers.Container(
        BootstrapContainer,
        app_config_service=_expose(_core, "app_config_service"),
        logging_service=_expose(_core, "logging_service"),
        availability_cache_service=_expose(_core, "availability_cache_service"),
        custom_agents_config=_expose(_core, "custom_agents_config"),
        llm_models_config_service=_expose(_core, "llm_models_config_service"),
    )

    _llm = providers.Container(
        LLMContainer,
        app_config_service=_expose(_core, "app_config_service"),
        logging_service=_expose(_core, "logging_service"),
        availability_cache_service=_expose(_core, "availability_cache_service"),
        features_registry_service=_expose(_bootstrap, "features_registry_service"),
        llm_models_config_service=_expose(_core, "llm_models_config_service"),
    )

    _host_registry = providers.Container(
        HostRegistryContainer,
        logging_service=_expose(_core, "logging_service"),
    )

    # Create orchestrator_service early to avoid circular dependency
    # (GraphCoreContainer needs it, but GraphAgentContainer is defined later)
    _orchestrator_service = providers.Singleton(
        "agentmap.services.orchestrator_service.OrchestratorService",
        _expose(_core, "prompt_manager_service"),
        _expose(_core, "logging_service"),
        _expose(_llm, "llm_service"),
        _expose(_bootstrap, "features_registry_service"),
    )

    _graph_core = providers.Container(
        GraphCoreContainer,
        app_config_service=_expose(_core, "app_config_service"),
        logging_service=_expose(_core, "logging_service"),
        features_registry_service=_expose(_bootstrap, "features_registry_service"),
        function_resolution_service=_expose(_bootstrap, "function_resolution_service"),
        agent_registry_service=_expose(_bootstrap, "agent_registry_service"),
        csv_graph_parser_service=_expose(_bootstrap, "csv_graph_parser_service"),
        static_bundle_analyzer=_expose(_bootstrap, "static_bundle_analyzer"),
        declaration_registry_service=_expose(
            _bootstrap, "declaration_registry_service"
        ),
        custom_agent_declaration_manager=_expose(
            _bootstrap, "custom_agent_declaration_manager"
        ),
        indented_template_composer=_expose(_bootstrap, "indented_template_composer"),
        json_storage_service=_expose(_storage, "json_storage_service"),
        system_storage_manager=_expose(_storage, "system_storage_manager"),
        file_path_service=_expose(_core, "file_path_service"),
        orchestrator_service=_orchestrator_service,
    )

    _graph_agent = providers.Container(
        GraphAgentContainer,
        features_registry_service=_expose(_bootstrap, "features_registry_service"),
        logging_service=_expose(_core, "logging_service"),
        custom_agent_loader=_expose(_bootstrap, "custom_agent_loader"),
        llm_service=_expose(_llm, "llm_service"),
        storage_service_manager=_expose(_storage, "storage_service_manager"),
        host_protocol_configuration_service=_expose(
            _host_registry, "host_protocol_configuration_service"
        ),
        prompt_manager_service=_expose(_core, "prompt_manager_service"),
        graph_checkpoint_service=_expose(_graph_core, "graph_checkpoint_service"),
        blob_storage_service=_expose(_storage, "blob_storage_service"),
        execution_tracking_service=_expose(_graph_core, "execution_tracking_service"),
        state_adapter_service=_expose(_graph_core, "state_adapter_service"),
        graph_bundle_service=_expose(_graph_core, "graph_bundle_service"),
        orchestrator_service=_orchestrator_service,
    )

    # --- Core re-exports --------------------------------------------------------

    config_service = _expose(_core, "config_service")
    app_config_service = _expose(_core, "app_config_service")
    logging_service = _expose(_core, "logging_service")
    availability_cache_service = _expose(_core, "availability_cache_service")
    logging_config = _expose(_core, "logging_config")
    execution_config = _expose(_core, "execution_config")
    prompts_config = _expose(_core, "prompts_config")
    custom_agents_config = _expose(_core, "custom_agents_config")
    auth_service = _expose(_core, "auth_service")
    file_path_service = _expose(_core, "file_path_service")
    prompt_manager_service = _expose(_core, "prompt_manager_service")
    llm_models_config_service = _expose(_core, "llm_models_config_service")

    # --- Storage re-exports -----------------------------------------------------

    storage_config_service = _expose(_storage, "storage_config_service")
    blob_storage_service = _expose(_storage, "blob_storage_service")
    json_storage_service = _expose(_storage, "json_storage_service")
    storage_service_manager = _expose(_storage, "storage_service_manager")
    system_storage_manager = _expose(_storage, "system_storage_manager")
    storage_available = _expose(_storage, "storage_available")

    # --- Bootstrap re-exports ---------------------------------------------------

    features_registry_model = _expose(_bootstrap, "features_registry_model")
    agent_registry_model = _expose(_bootstrap, "agent_registry_model")
    validation_cache_service = _expose(_bootstrap, "validation_cache_service")
    csv_graph_parser_service = _expose(_bootstrap, "csv_graph_parser_service")
    function_resolution_service = _expose(_bootstrap, "function_resolution_service")
    declaration_parser = _expose(_bootstrap, "declaration_parser")
    declaration_registry_service = _expose(_bootstrap, "declaration_registry_service")
    features_registry_service = _expose(_bootstrap, "features_registry_service")
    agent_registry_service = _expose(_bootstrap, "agent_registry_service")
    custom_agent_loader = _expose(_bootstrap, "custom_agent_loader")
    indented_template_composer = _expose(_bootstrap, "indented_template_composer")
    custom_agent_declaration_manager = _expose(
        _bootstrap, "custom_agent_declaration_manager"
    )
    static_bundle_analyzer = _expose(_bootstrap, "static_bundle_analyzer")
    dependency_checker_service = _expose(_bootstrap, "dependency_checker_service")
    config_validation_service = _expose(_bootstrap, "config_validation_service")
    csv_validation_service = _expose(_bootstrap, "csv_validation_service")
    validation_service = _expose(_bootstrap, "validation_service")

    # --- LLM re-exports ---------------------------------------------------------

    llm_routing_config_service = _expose(_llm, "llm_routing_config_service")
    prompt_complexity_analyzer = _expose(_llm, "prompt_complexity_analyzer")
    routing_cache = _expose(_llm, "routing_cache")
    llm_routing_service = _expose(_llm, "llm_routing_service")
    llm_service = _expose(_llm, "llm_service")

    # --- Host registry re-exports ----------------------------------------------

    host_service_registry = _expose(_host_registry, "host_service_registry")
    host_protocol_configuration_service = _expose(
        _host_registry, "host_protocol_configuration_service"
    )

    # --- Graph core re-exports --------------------------------------------------

    execution_formatter_service = _expose(_graph_core, "execution_formatter_service")
    state_adapter_service = _expose(_graph_core, "state_adapter_service")
    execution_tracking_service = _expose(_graph_core, "execution_tracking_service")
    execution_policy_service = _expose(_graph_core, "execution_policy_service")
    graph_factory_service = _expose(_graph_core, "graph_factory_service")
    graph_assembly_service = _expose(_graph_core, "graph_assembly_service")
    protocol_requirements_analyzer = _expose(
        _graph_core, "protocol_requirements_analyzer"
    )
    graph_registry_service = _expose(_graph_core, "graph_registry_service")
    graph_bundle_service = _expose(_graph_core, "graph_bundle_service")
    bundle_update_service = _expose(_graph_core, "bundle_update_service")
    graph_scaffold_service = _expose(_graph_core, "graph_scaffold_service")
    graph_execution_service = _expose(_graph_core, "graph_execution_service")
    graph_output_service = _expose(_graph_core, "graph_output_service")
    graph_checkpoint_service = _expose(_graph_core, "graph_checkpoint_service")
    interaction_handler_service = _expose(_graph_core, "interaction_handler_service")
    graph_bootstrap_service = _expose(_graph_core, "graph_bootstrap_service")

    # --- Graph agent re-exports -------------------------------------------------

    orchestrator_service = _orchestrator_service
    agent_factory_service = _expose(_graph_agent, "agent_factory_service")
    agent_service_injection_service = _expose(
        _graph_agent, "agent_service_injection_service"
    )
    graph_agent_instantiation_service = _expose(
        _graph_agent, "graph_agent_instantiation_service"
    )

    graph_runner_service = providers.Singleton(
        "agentmap.services.graph.graph_runner_service.GraphRunnerService",
        app_config_service,
        graph_bootstrap_service,
        graph_agent_instantiation_service,
        graph_assembly_service,
        graph_execution_service,
        execution_tracking_service,
        logging_service,
        interaction_handler_service,
        graph_checkpoint_service,
        graph_bundle_service,
    )

    # --- Delegated helper methods ----------------------------------------------

    def get_cache_status(self):
        return self._core().get_cache_status()

    def invalidate_all_caches(self) -> bool:
        return self._core().invalidate_all_caches()

    def register_host_service(self, *args, **kwargs):
        return self._host_registry().register_host_service(*args, **kwargs)

    def register_host_factory(self, *args, **kwargs):
        return self._host_registry().register_host_factory(*args, **kwargs)

    def get_host_services(self):
        return self._host_registry().get_host_services()

    def get_protocol_implementations(self):
        return self._host_registry().get_protocol_implementations()

    def configure_host_protocols(self, agent):
        return self._host_registry().configure_host_protocols(agent)

    def has_host_service(self, service_name: str) -> bool:
        return self._host_registry().has_host_service(service_name)

    def get_host_service_instance(self, service_name: str):
        return self._host_registry().get_host_service_instance(service_name)

    def clear_host_services(self) -> None:
        self._host_registry().clear_host_services()


__all__ = [
    "ApplicationContainer",
    "create_optional_service",
    "safe_get_service",
]
