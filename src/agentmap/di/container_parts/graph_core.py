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

    # --- Execution Services -----------------------------------------------------

    @staticmethod
    def _create_execution_formatter_service():
        from agentmap.services.execution_formatter_service import (
            ExecutionFormatterService,
        )

        return ExecutionFormatterService()

    execution_formatter_service = providers.Singleton(
        _create_execution_formatter_service
    )

    @staticmethod
    def _create_state_adapter_service():
        from agentmap.services.state_adapter_service import StateAdapterService

        return StateAdapterService()

    state_adapter_service = providers.Singleton(_create_state_adapter_service)

    @staticmethod
    def _create_execution_tracking_service(app_config_service, logging_service):
        from agentmap.services.execution_tracking_service import (
            ExecutionTrackingService,
        )

        return ExecutionTrackingService(app_config_service, logging_service)

    execution_tracking_service = providers.Singleton(
        _create_execution_tracking_service,
        app_config_service,
        logging_service,
    )

    @staticmethod
    def _create_execution_policy_service(app_config_service, logging_service):
        from agentmap.services.execution_policy_service import ExecutionPolicyService

        return ExecutionPolicyService(app_config_service, logging_service)

    execution_policy_service = providers.Singleton(
        _create_execution_policy_service,
        app_config_service,
        logging_service,
    )

    # --- Graph Factory & Assembly -----------------------------------------------

    @staticmethod
    def _create_graph_factory_service(logging_service):
        from agentmap.services.graph.graph_factory_service import GraphFactoryService

        return GraphFactoryService(logging_service)

    graph_factory_service = providers.Singleton(
        _create_graph_factory_service,
        logging_service,
    )

    @staticmethod
    def _create_graph_assembly_service(
        app_config_service,
        logging_service,
        state_adapter_service,
        features_registry_service,
        function_resolution_service,
        graph_factory_service,
        orchestrator_service,
    ):
        from agentmap.services.graph.graph_assembly_service import GraphAssemblyService

        return GraphAssemblyService(
            app_config_service,
            logging_service,
            state_adapter_service,
            features_registry_service,
            function_resolution_service,
            graph_factory_service,
            orchestrator_service,
        )

    graph_assembly_service = providers.Singleton(
        _create_graph_assembly_service,
        app_config_service,
        logging_service,
        state_adapter_service,
        features_registry_service,
        function_resolution_service,
        graph_factory_service,
        orchestrator_service,
    )

    # --- Protocol & Registry Services -------------------------------------------

    @staticmethod
    def _create_protocol_requirements_analyzer(
        csv_graph_parser_service, agent_factory_service_path, logging_service
    ):
        from agentmap.services.protocol_requirements_analyzer import (
            ProtocolBasedRequirementsAnalyzer,
        )

        return ProtocolBasedRequirementsAnalyzer(
            csv_graph_parser_service,
            agent_factory_service_path,
            logging_service,
        )

    protocol_requirements_analyzer = providers.Singleton(
        _create_protocol_requirements_analyzer,
        csv_graph_parser_service,
        "agentmap.services.agent.agent_factory_service.AgentFactoryService",
        logging_service,
    )

    @staticmethod
    def _create_graph_registry_service(
        system_storage_manager, app_config_service, logging_service
    ):
        from agentmap.services.graph.graph_registry_service import GraphRegistryService

        return GraphRegistryService(
            system_storage_manager, app_config_service, logging_service
        )

    graph_registry_service = providers.Singleton(
        _create_graph_registry_service,
        system_storage_manager,
        app_config_service,
        logging_service,
    )

    # --- Bundle Services --------------------------------------------------------

    @staticmethod
    def _create_graph_bundle_service(
        logging_service,
        protocol_requirements_analyzer,
        agent_factory_service_path,
        json_storage_service,
        csv_graph_parser_service,
        static_bundle_analyzer,
        app_config_service,
        declaration_registry_service,
        graph_registry_service,
        file_path_service,
        system_storage_manager,
    ):
        from agentmap.services.graph.graph_bundle_service import GraphBundleService

        return GraphBundleService(
            logging_service,
            protocol_requirements_analyzer,
            agent_factory_service_path,
            json_storage_service,
            csv_graph_parser_service,
            static_bundle_analyzer,
            app_config_service,
            declaration_registry_service,
            graph_registry_service,
            file_path_service,
            system_storage_manager,
        )

    graph_bundle_service = providers.Singleton(
        _create_graph_bundle_service,
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

    @staticmethod
    def _create_bundle_update_service(
        declaration_registry_service,
        custom_agent_declaration_manager,
        graph_bundle_service,
        file_path_service,
        logging_service,
    ):
        from agentmap.services.graph.bundle_update_service import BundleUpdateService

        return BundleUpdateService(
            declaration_registry_service,
            custom_agent_declaration_manager,
            graph_bundle_service,
            file_path_service,
            logging_service,
        )

    bundle_update_service = providers.Singleton(
        _create_bundle_update_service,
        declaration_registry_service,
        custom_agent_declaration_manager,
        graph_bundle_service,
        file_path_service,
        logging_service,
    )

    # --- Scaffold Service -------------------------------------------------------

    @staticmethod
    def _create_graph_scaffold_service(
        app_config_service,
        logging_service,
        function_resolution_service,
        agent_registry_service,
        indented_template_composer,
        custom_agent_declaration_manager,
        bundle_update_service,
    ):
        from agentmap.services.graph.graph_scaffold_service import GraphScaffoldService

        return GraphScaffoldService(
            app_config_service,
            logging_service,
            function_resolution_service,
            agent_registry_service,
            indented_template_composer,
            custom_agent_declaration_manager,
            bundle_update_service,
        )

    graph_scaffold_service = providers.Singleton(
        _create_graph_scaffold_service,
        app_config_service,
        logging_service,
        function_resolution_service,
        agent_registry_service,
        indented_template_composer,
        custom_agent_declaration_manager,
        bundle_update_service,
    )

    # --- Execution & Checkpoint Services ----------------------------------------

    @staticmethod
    def _create_graph_execution_service(
        execution_tracking_service,
        execution_policy_service,
        state_adapter_service,
        logging_service,
    ):
        from agentmap.services.graph.graph_execution_service import (
            GraphExecutionService,
        )

        return GraphExecutionService(
            execution_tracking_service,
            execution_policy_service,
            state_adapter_service,
            logging_service,
        )

    graph_execution_service = providers.Singleton(
        _create_graph_execution_service,
        execution_tracking_service,
        execution_policy_service,
        state_adapter_service,
        logging_service,
    )

    @staticmethod
    def _create_graph_checkpoint_service(system_storage_manager, logging_service):
        from agentmap.services.graph.graph_checkpoint_service import (
            GraphCheckpointService,
        )

        return GraphCheckpointService(system_storage_manager, logging_service)

    graph_checkpoint_service = providers.Singleton(
        _create_graph_checkpoint_service,
        system_storage_manager,
        logging_service,
    )

    # --- Interaction Handler ----------------------------------------------------

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

    # --- Bootstrap Service ------------------------------------------------------

    @staticmethod
    def _create_graph_bootstrap_service(
        agent_registry_service,
        features_registry_service,
        app_config_service,
        logging_service,
    ):
        from agentmap.services.graph.graph_bootstrap_service import (
            GraphBootstrapService,
        )

        return GraphBootstrapService(
            agent_registry_service,
            features_registry_service,
            app_config_service,
            logging_service,
        )

    graph_bootstrap_service = providers.Singleton(
        _create_graph_bootstrap_service,
        agent_registry_service,
        features_registry_service,
        app_config_service,
        logging_service,
    )
