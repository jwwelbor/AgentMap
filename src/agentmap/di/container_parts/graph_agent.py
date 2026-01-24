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

    @staticmethod
    def _create_agent_factory_service(
        features_registry_service, logging_service, custom_agent_loader
    ):
        from agentmap.services.agent.agent_factory_service import AgentFactoryService

        return AgentFactoryService(
            features_registry_service, logging_service, custom_agent_loader
        )

    agent_factory_service = providers.Singleton(
        _create_agent_factory_service,
        features_registry_service,
        logging_service,
        custom_agent_loader,
    )

    @staticmethod
    def _create_agent_service_injection_service(
        llm_service,
        storage_service_manager,
        logging_service,
        host_protocol_configuration_service,
        prompt_manager_service,
        orchestrator_service,
        graph_checkpoint_service,
        blob_storage_service,
    ):
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
        agent_factory_service,
        agent_service_injection_service,
        execution_tracking_service,
        state_adapter_service,
        logging_service,
        prompt_manager_service,
        graph_bundle_service,
    ):
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
    )
