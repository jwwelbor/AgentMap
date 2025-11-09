"""Graph core container part: graph assembly, bundle management, and execution."""

from __future__ import annotations

from dependency_injector import containers, providers


class GraphCoreContainer(containers.DeclarativeContainer):
    """Provides core graph services used across runtime orchestration."""

    app_config_service = providers.Dependency()
    logging_service = providers.Dependency()
    features_registry_service = providers.Dependency()
    function_resolution_service = providers.Dependency()
    agent_registry_service = providers.Dependency()
    csv_graph_parser_service = providers.Dependency()
    static_bundle_analyzer = providers.Dependency()
    declaration_registry_service = providers.Dependency()
    custom_agent_declaration_manager = providers.Dependency()
    indented_template_composer = providers.Dependency()
    json_storage_service = providers.Dependency()
    system_storage_manager = providers.Dependency()
    file_path_service = providers.Dependency()
    orchestrator_service = providers.Dependency()

    execution_formatter_service = providers.Singleton(
        "agentmap.services.execution_formatter_service.ExecutionFormatterService"
    )

    state_adapter_service = providers.Singleton(
        "agentmap.services.state_adapter_service.StateAdapterService"
    )

    execution_tracking_service = providers.Singleton(
        "agentmap.services.execution_tracking_service.ExecutionTrackingService",
        app_config_service,
        logging_service,
    )

    execution_policy_service = providers.Singleton(
        "agentmap.services.execution_policy_service.ExecutionPolicyService",
        app_config_service,
        logging_service,
    )

    graph_factory_service = providers.Singleton(
        "agentmap.services.graph.graph_factory_service.GraphFactoryService",
        logging_service,
    )

    graph_assembly_service = providers.Singleton(
        "agentmap.services.graph.graph_assembly_service.GraphAssemblyService",
        app_config_service,
        logging_service,
        state_adapter_service,
        features_registry_service,
        function_resolution_service,
        graph_factory_service,
        orchestrator_service,
    )

    protocol_requirements_analyzer = providers.Singleton(
        "agentmap.services.protocol_requirements_analyzer.ProtocolBasedRequirementsAnalyzer",
        csv_graph_parser_service,
        "agentmap.services.agent.agent_factory_service.AgentFactoryService",
        logging_service,
    )

    graph_registry_service = providers.Singleton(
        "agentmap.services.graph.graph_registry_service.GraphRegistryService",
        system_storage_manager,
        app_config_service,
        logging_service,
    )

    graph_bundle_service = providers.Singleton(
        "agentmap.services.graph.graph_bundle_service.GraphBundleService",
        logging_service,
        protocol_requirements_analyzer,
        "agentmap.services.agent.agent_factory_service.AgentFactoryService",
        json_storage_service,
        csv_graph_parser_service,
        static_bundle_analyzer,
        app_config_service,
        declaration_registry_service,
        graph_registry_service,
        file_path_service,
        system_storage_manager,
    )

    bundle_update_service = providers.Singleton(
        "agentmap.services.graph.bundle_update_service.BundleUpdateService",
        declaration_registry_service,
        custom_agent_declaration_manager,
        graph_bundle_service,
        file_path_service,
        logging_service,
    )

    graph_scaffold_service = providers.Singleton(
        "agentmap.services.graph.graph_scaffold_service.GraphScaffoldService",
        app_config_service,
        logging_service,
        function_resolution_service,
        agent_registry_service,
        indented_template_composer,
        custom_agent_declaration_manager,
        bundle_update_service,
    )

    graph_execution_service = providers.Singleton(
        "agentmap.services.graph.graph_execution_service.GraphExecutionService",
        execution_tracking_service,
        execution_policy_service,
        state_adapter_service,
        logging_service,
    )

    graph_output_service = providers.Singleton(
        "agentmap.services.graph.graph_output_service.GraphOutputService",
        app_config_service,
        logging_service,
        function_resolution_service,
        agent_registry_service,
    )

    graph_checkpoint_service = providers.Singleton(
        "agentmap.services.graph.graph_checkpoint_service.GraphCheckpointService",
        system_storage_manager,
        logging_service,
    )

    @staticmethod
    def _create_interaction_handler_service(system_storage_manager, logging_service):
        if system_storage_manager is None:
            logging_service.get_logger("agentmap.interaction").info(
                "System storage manager not available - interaction handler disabled",
            )
            return None
        try:
            from agentmap.services.interaction_handler_service import (
                InteractionHandlerService,
            )

            return InteractionHandlerService(
                system_storage_manager=system_storage_manager,
                logging_service=logging_service,
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            logging_service.get_logger("agentmap.interaction").warning(
                f"Interaction handler service disabled: {exc}"
            )
            return None

    interaction_handler_service = providers.Singleton(
        _create_interaction_handler_service,
        system_storage_manager,
        logging_service,
    )

    graph_bootstrap_service = providers.Singleton(
        "agentmap.services.graph.graph_bootstrap_service.GraphBootstrapService",
        agent_registry_service,
        features_registry_service,
        app_config_service,
        logging_service,
    )
