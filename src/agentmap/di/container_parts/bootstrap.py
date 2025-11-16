"""Bootstrap container part: declarations, registries, and validation services."""

from __future__ import annotations

from dependency_injector import containers, providers


class BootstrapContainer(containers.DeclarativeContainer):
    """Provides registry, declaration, and validation services."""

    app_config_service = providers.Dependency()
    logging_service = providers.Dependency()
    availability_cache_service = providers.Dependency()
    custom_agents_config = providers.Dependency()
    llm_models_config_service = providers.Dependency()

    features_registry_model = providers.Singleton(
        "agentmap.models.features_registry.FeaturesRegistry"
    )
    agent_registry_model = providers.Singleton(
        "agentmap.models.agent_registry.AgentRegistry"
    )

    validation_cache_service = providers.Singleton(
        "agentmap.services.validation.validation_cache_service.ValidationCacheService"
    )

    csv_graph_parser_service = providers.Singleton(
        "agentmap.services.csv_graph_parser_service.CSVGraphParserService",
        logging_service,
    )

    function_resolution_service = providers.Singleton(
        "agentmap.services.function_resolution_service.FunctionResolutionService",
        providers.Callable(lambda svc: svc.get_functions_path(), app_config_service),
    )

    declaration_parser = providers.Singleton(
        "agentmap.services.declaration_parser.DeclarationParser",
        logging_service,
    )

    @staticmethod
    def _create_declaration_registry_service(app_config_service, logging_service):
        from agentmap.services.declaration_parser import DeclarationParser
        from agentmap.services.declaration_registry_service import (
            DeclarationRegistryService,
        )
        from agentmap.services.declaration_sources import (
            CustomAgentYAMLSource,
            PythonDeclarationSource,
        )

        registry = DeclarationRegistryService(app_config_service, logging_service)
        parser = DeclarationParser(logging_service)
        registry.add_source(PythonDeclarationSource(parser, logging_service))
        registry.add_source(
            CustomAgentYAMLSource(app_config_service, parser, logging_service)
        )
        logging_service.get_class_logger(registry).info(
            "Initialized declaration registry"
        )
        return registry

    declaration_registry_service = providers.Singleton(
        _create_declaration_registry_service,
        app_config_service,
        logging_service,
    )

    features_registry_service = providers.Singleton(
        "agentmap.services.features_registry_service.FeaturesRegistryService",
        features_registry_model,
        logging_service,
        availability_cache_service,
    )

    agent_registry_service = providers.Singleton(
        "agentmap.services.agent.agent_registry_service.AgentRegistryService",
        agent_registry_model,
        logging_service,
    )

    custom_agent_loader = providers.Singleton(
        "agentmap.services.custom_agent_loader.CustomAgentLoader",
        custom_agents_config,
        logging_service,
    )

    indented_template_composer = providers.Singleton(
        "agentmap.services.indented_template_composer.IndentedTemplateComposer",
        app_config_service,
        logging_service,
    )

    custom_agent_declaration_manager = providers.Singleton(
        "agentmap.services.custom_agent_declaration_manager.CustomAgentDeclarationManager",
        app_config_service,
        logging_service,
        indented_template_composer,
    )

    static_bundle_analyzer = providers.Singleton(
        "agentmap.services.static_bundle_analyzer.StaticBundleAnalyzer",
        declaration_registry_service,
        custom_agent_declaration_manager,
        csv_graph_parser_service,
        logging_service,
    )

    @staticmethod
    def _create_dependency_checker_service(
        logging_service,
        features_registry_service,
        availability_cache_service,
    ):
        from agentmap.services.dependency_checker_service import (
            DependencyCheckerService,
        )

        return DependencyCheckerService(
            logging_service,
            features_registry_service,
            availability_cache_service,
        )

    dependency_checker_service = providers.Singleton(
        _create_dependency_checker_service,
        logging_service,
        features_registry_service,
        availability_cache_service,
    )

    config_validation_service = providers.Singleton(
        "agentmap.services.validation.config_validation_service.ConfigValidationService",
        logging_service,
        llm_models_config_service,
    )

    csv_validation_service = providers.Singleton(
        "agentmap.services.validation.csv_validation_service.CSVValidationService",
        logging_service,
        function_resolution_service,
        agent_registry_service,
    )

    validation_service = providers.Singleton(
        "agentmap.services.validation.validation_service.ValidationService",
        app_config_service,
        logging_service,
        csv_validation_service,
        config_validation_service,
        validation_cache_service,
    )
