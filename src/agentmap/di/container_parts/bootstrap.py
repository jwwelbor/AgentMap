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

    # --- Registry Models --------------------------------------------------------

    @staticmethod
    def _create_features_registry_model():
        from agentmap.models.features_registry import FeaturesRegistry

        return FeaturesRegistry()

    features_registry_model = providers.Singleton(_create_features_registry_model)

    @staticmethod
    def _create_agent_registry_model():
        from agentmap.models.agent_registry import AgentRegistry

        return AgentRegistry()

    agent_registry_model = providers.Singleton(_create_agent_registry_model)

    # --- Validation Services ----------------------------------------------------

    @staticmethod
    def _create_validation_cache_service():
        from agentmap.services.validation.validation_cache_service import (
            ValidationCacheService,
        )

        return ValidationCacheService()

    validation_cache_service = providers.Singleton(_create_validation_cache_service)

    @staticmethod
    def _create_csv_graph_parser_service(logging_service):
        from agentmap.services.csv_graph_parser_service import CSVGraphParserService

        return CSVGraphParserService(logging_service)

    csv_graph_parser_service = providers.Singleton(
        _create_csv_graph_parser_service,
        logging_service,
    )

    @staticmethod
    def _create_function_resolution_service(functions_path):
        from agentmap.services.function_resolution_service import (
            FunctionResolutionService,
        )

        return FunctionResolutionService(functions_path)

    function_resolution_service = providers.Singleton(
        _create_function_resolution_service,
        providers.Callable(lambda svc: svc.get_functions_path(), app_config_service),
    )

    @staticmethod
    def _create_declaration_parser(logging_service):
        from agentmap.services.declaration_parser import DeclarationParser

        return DeclarationParser(logging_service)

    declaration_parser = providers.Singleton(
        _create_declaration_parser,
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

    @staticmethod
    def _create_features_registry_service(
        features_registry_model, logging_service, availability_cache_service
    ):
        from agentmap.services.features_registry_service import FeaturesRegistryService

        return FeaturesRegistryService(
            features_registry_model, logging_service, availability_cache_service
        )

    features_registry_service = providers.Singleton(
        _create_features_registry_service,
        features_registry_model,
        logging_service,
        availability_cache_service,
    )

    @staticmethod
    def _create_agent_registry_service(agent_registry_model, logging_service):
        from agentmap.services.agent.agent_registry_service import AgentRegistryService

        return AgentRegistryService(agent_registry_model, logging_service)

    agent_registry_service = providers.Singleton(
        _create_agent_registry_service,
        agent_registry_model,
        logging_service,
    )

    @staticmethod
    def _create_custom_agent_loader(custom_agents_config, logging_service):
        from agentmap.services.custom_agent_loader import CustomAgentLoader

        return CustomAgentLoader(custom_agents_config, logging_service)

    custom_agent_loader = providers.Singleton(
        _create_custom_agent_loader,
        custom_agents_config,
        logging_service,
    )

    @staticmethod
    def _create_indented_template_composer(app_config_service, logging_service):
        from agentmap.services.indented_template_composer import (
            IndentedTemplateComposer,
        )

        return IndentedTemplateComposer(app_config_service, logging_service)

    indented_template_composer = providers.Singleton(
        _create_indented_template_composer,
        app_config_service,
        logging_service,
    )

    @staticmethod
    def _create_custom_agent_declaration_manager(
        app_config_service, logging_service, indented_template_composer
    ):
        from agentmap.services.custom_agent_declaration_manager import (
            CustomAgentDeclarationManager,
        )

        return CustomAgentDeclarationManager(
            app_config_service, logging_service, indented_template_composer
        )

    custom_agent_declaration_manager = providers.Singleton(
        _create_custom_agent_declaration_manager,
        app_config_service,
        logging_service,
        indented_template_composer,
    )

    @staticmethod
    def _create_static_bundle_analyzer(
        declaration_registry_service,
        custom_agent_declaration_manager,
        csv_graph_parser_service,
        logging_service,
    ):
        from agentmap.services.static_bundle_analyzer import StaticBundleAnalyzer

        return StaticBundleAnalyzer(
            declaration_registry_service,
            custom_agent_declaration_manager,
            csv_graph_parser_service,
            logging_service,
        )

    static_bundle_analyzer = providers.Singleton(
        _create_static_bundle_analyzer,
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

    @staticmethod
    def _create_config_validation_service(logging_service, llm_models_config_service):
        from agentmap.services.validation.config_validation_service import (
            ConfigValidationService,
        )

        return ConfigValidationService(logging_service, llm_models_config_service)

    config_validation_service = providers.Singleton(
        _create_config_validation_service,
        logging_service,
        llm_models_config_service,
    )

    @staticmethod
    def _create_csv_validation_service(
        logging_service, function_resolution_service, agent_registry_service
    ):
        from agentmap.services.validation.csv_validation_service import (
            CSVValidationService,
        )

        return CSVValidationService(
            logging_service, function_resolution_service, agent_registry_service
        )

    csv_validation_service = providers.Singleton(
        _create_csv_validation_service,
        logging_service,
        function_resolution_service,
        agent_registry_service,
    )

    @staticmethod
    def _create_validation_service(
        app_config_service,
        logging_service,
        csv_validation_service,
        config_validation_service,
        validation_cache_service,
    ):
        from agentmap.services.validation.validation_service import ValidationService

        return ValidationService(
            app_config_service,
            logging_service,
            csv_validation_service,
            config_validation_service,
            validation_cache_service,
        )

    validation_service = providers.Singleton(
        _create_validation_service,
        app_config_service,
        logging_service,
        csv_validation_service,
        config_validation_service,
        validation_cache_service,
    )
