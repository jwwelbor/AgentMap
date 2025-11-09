"""Graph agent container part: orchestrator, agent factory, and instantiation."""

from __future__ import annotations

from dependency_injector import containers, providers


class GraphAgentContainer(containers.DeclarativeContainer):
    """Provides agent orchestration and injection services."""

    features_registry_service = providers.Dependency()
    logging_service = providers.Dependency()
    custom_agent_loader = providers.Dependency()
    llm_service = providers.Dependency()
    storage_service_manager = providers.Dependency()
    host_protocol_configuration_service = providers.Dependency()
    prompt_manager_service = providers.Dependency()
    graph_checkpoint_service = providers.Dependency()
    blob_storage_service = providers.Dependency()
    execution_tracking_service = providers.Dependency()
    state_adapter_service = providers.Dependency()
    graph_bundle_service = providers.Dependency()
    orchestrator_service = providers.Dependency()

    agent_factory_service = providers.Singleton(
        "agentmap.services.agent.agent_factory_service.AgentFactoryService",
        features_registry_service,
        logging_service,
        custom_agent_loader,
    )

    agent_service_injection_service = providers.Singleton(
        "agentmap.services.agent.agent_service_injection_service.AgentServiceInjectionService",
        llm_service,
        storage_service_manager,
        logging_service,
        host_protocol_configuration_service,
        prompt_manager_service,
        orchestrator_service,
        graph_checkpoint_service,
        blob_storage_service,
    )

    graph_agent_instantiation_service = providers.Singleton(
        "agentmap.services.graph.graph_agent_instantiation_service.GraphAgentInstantiationService",
        agent_factory_service,
        agent_service_injection_service,
        execution_tracking_service,
        state_adapter_service,
        logging_service,
        prompt_manager_service,
        graph_bundle_service,
    )
