"""Graph agent container part: orchestrator, agent factory, and instantiation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dependency_injector import containers, providers

if TYPE_CHECKING:
    from agentmap.services.agent.agent_service_injection_service import (
        AgentServiceInjectionService,
    )
    from agentmap.services.graph.graph_agent_instantiation_service import (
        GraphAgentInstantiationService,
    )


class GraphAgentContainer(containers.DeclarativeContainer):
    """Provides agent orchestration and injection services."""

    # Dependency providers resolve these values dynamically at runtime.
    features_registry_service: Any = providers.Dependency()
    logging_service: Any = providers.Dependency()
    app_config_service: Any = providers.Dependency()
    agent_factory_service: Any = providers.Dependency()
    llm_service: Any = providers.Dependency()
    storage_service_manager: Any = providers.Dependency()
    host_protocol_configuration_service: Any = providers.Dependency()
    prompt_manager_service: Any = providers.Dependency()
    graph_checkpoint_service: Any = providers.Dependency()
    blob_storage_service: Any = providers.Dependency()
    execution_tracking_service: Any = providers.Dependency()
    state_adapter_service: Any = providers.Dependency()
    graph_bundle_service: Any = providers.Dependency()
    orchestrator_service: Any = providers.Dependency()
    declaration_registry_service: Any = providers.Dependency()
    telemetry_service: Any = providers.Dependency()
    file_path_service: Any = providers.Dependency()

    @staticmethod
    def _create_agent_service_injection_service(
        llm_service: Any,
        storage_service_manager: Any,
        logging_service: Any,
        host_protocol_configuration_service: Any,
        prompt_manager_service: Any,
        orchestrator_service: Any,
        graph_checkpoint_service: Any,
        blob_storage_service: Any,
    ) -> AgentServiceInjectionService:
        from agentmap.services.agent.agent_service_injection_service import (
            AgentServiceInjectionService,
        )

        return AgentServiceInjectionService(
            llm_service,
            storage_service_manager,
            logging_service,
            host_protocol_configuration_service,
            prompt_manager_service,
            orchestrator_service,
            graph_checkpoint_service,
            blob_storage_service,
        )

    agent_service_injection_service = providers.Singleton(
        _create_agent_service_injection_service,
        llm_service,
        storage_service_manager,
        logging_service,
        host_protocol_configuration_service,
        prompt_manager_service,
        orchestrator_service,
        graph_checkpoint_service,
        blob_storage_service,
    )

    @staticmethod
    def _create_graph_agent_instantiation_service(
        agent_factory_service: Any,
        agent_service_injection_service: Any,
        execution_tracking_service: Any,
        state_adapter_service: Any,
        logging_service: Any,
        prompt_manager_service: Any,
        graph_bundle_service: Any,
        declaration_registry_service: Any,
        telemetry_service: Any,
        file_path_service: Any,
    ) -> GraphAgentInstantiationService:
        from agentmap.services.graph.graph_agent_instantiation_service import (
            GraphAgentInstantiationService,
        )

        return GraphAgentInstantiationService(
            agent_factory_service,
            agent_service_injection_service,
            execution_tracking_service,
            state_adapter_service,
            logging_service,
            prompt_manager_service,
            graph_bundle_service,
            declaration_registry_service,
            telemetry_service,
            file_path_service=file_path_service,
        )

    graph_agent_instantiation_service = providers.Singleton(
        _create_graph_agent_instantiation_service,
        agent_factory_service,
        agent_service_injection_service,
        execution_tracking_service,
        state_adapter_service,
        logging_service,
        prompt_manager_service,
        graph_bundle_service,
        declaration_registry_service,
        telemetry_service,
        file_path_service,
    )
