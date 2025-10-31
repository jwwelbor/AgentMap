"""LLM container part with routing and orchestration services."""

from __future__ import annotations

from dependency_injector import containers, providers


class LLMContainer(containers.DeclarativeContainer):
    """Provides LLM configuration, routing, and execution services."""

    app_config_service = providers.Dependency()
    logging_service = providers.Dependency()
    availability_cache_service = providers.Dependency()
    features_registry_service = providers.Dependency()
    llm_models_config_service = providers.Dependency()

    @staticmethod
    def _create_llm_routing_config_service(
        app_config_service,
        logging_service,
        llm_models_config_service,
        availability_cache_service,
    ):
        from agentmap.services.config.llm_routing_config_service import (
            LLMRoutingConfigService,
        )

        return LLMRoutingConfigService(
            app_config_service,
            logging_service,
            llm_models_config_service,
            availability_cache_service,
        )

    llm_routing_config_service = providers.Singleton(
        _create_llm_routing_config_service,
        app_config_service,
        logging_service,
        llm_models_config_service,
        availability_cache_service,
    )

    prompt_complexity_analyzer = providers.Singleton(
        "agentmap.services.routing.complexity_analyzer.PromptComplexityAnalyzer",
        app_config_service,
        logging_service,
    )

    routing_cache = providers.Singleton(
        "agentmap.services.routing.cache.RoutingCache",
        logging_service,
    )

    llm_routing_service = providers.Singleton(
        "agentmap.services.routing.routing_service.LLMRoutingService",
        llm_routing_config_service,
        logging_service,
        routing_cache,
        prompt_complexity_analyzer,
    )

    llm_service = providers.Singleton(
        "agentmap.services.llm_service.LLMService",
        app_config_service,
        logging_service,
        llm_routing_service,
        llm_models_config_service,
        features_registry_service,
        llm_routing_config_service,
    )
