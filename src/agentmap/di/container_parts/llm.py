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
    telemetry_service = providers.Dependency()

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

    @staticmethod
    def _create_prompt_complexity_analyzer(app_config_service, logging_service):
        from agentmap.services.routing.complexity_analyzer import (
            PromptComplexityAnalyzer,
        )

        return PromptComplexityAnalyzer(app_config_service, logging_service)

    prompt_complexity_analyzer = providers.Singleton(
        _create_prompt_complexity_analyzer,
        app_config_service,
        logging_service,
    )

    @staticmethod
    def _create_routing_cache(logging_service):
        from agentmap.services.routing.cache import RoutingCache

        return RoutingCache(logging_service)

    routing_cache = providers.Singleton(
        _create_routing_cache,
        logging_service,
    )

    @staticmethod
    def _create_llm_routing_service(
        llm_routing_config_service,
        logging_service,
        routing_cache,
        prompt_complexity_analyzer,
    ):
        from agentmap.services.routing.routing_service import LLMRoutingService

        return LLMRoutingService(
            llm_routing_config_service,
            logging_service,
            routing_cache,
            prompt_complexity_analyzer,
        )

    llm_routing_service = providers.Singleton(
        _create_llm_routing_service,
        llm_routing_config_service,
        logging_service,
        routing_cache,
        prompt_complexity_analyzer,
    )

    @staticmethod
    def _create_anthropic_batch_adapter(app_config_service, logging_service):
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        api_key = app_config_service.get_llm_config("anthropic").get("api_key", "")
        logger = logging_service.get_class_logger(AnthropicBatchAdapter)
        return AnthropicBatchAdapter(api_key=api_key, logger=logger)

    anthropic_batch_adapter = providers.Singleton(
        _create_anthropic_batch_adapter,
        app_config_service,
        logging_service,
    )

    @staticmethod
    def _create_batch_handle_repository(app_config_service):
        from agentmap.services.llm_batch_repository import BatchHandleRepository

        batch_dir = app_config_service.get_value(
            "llm.batch_dir", "agentmap_data/llm_batches"
        )
        return BatchHandleRepository(batch_dir=batch_dir)

    batch_handle_repository = providers.Singleton(
        _create_batch_handle_repository,
        app_config_service,
    )

    @staticmethod
    def _create_llm_service(
        app_config_service,
        logging_service,
        llm_routing_service,
        llm_models_config_service,
        features_registry_service,
        llm_routing_config_service,
        telemetry_service,
        anthropic_batch_adapter=None,
        batch_handle_repository=None,
    ):
        from agentmap.services.llm_service import LLMService

        svc = LLMService(
            app_config_service,
            logging_service,
            llm_routing_service,
            llm_models_config_service,
            features_registry_service,
            llm_routing_config_service,
            telemetry_service,
            batch_adapter=anthropic_batch_adapter,
            batch_repo=batch_handle_repository,
        )

        # Wire content capture flags from telemetry config (T-E02-F04-003).
        # Flags are stored on the telemetry_service singleton by T-E02-F04-004
        # as ``_content_capture_flags``.  Default to False (privacy-safe).
        flags = getattr(telemetry_service, "_content_capture_flags", None) or {}
        svc._capture_llm_prompts = bool(flags.get("llm_prompts", False))
        svc._capture_llm_responses = bool(flags.get("llm_responses", False))

        return svc

    llm_service = providers.Singleton(
        _create_llm_service,
        app_config_service,
        logging_service,
        llm_routing_service,
        llm_models_config_service,
        features_registry_service,
        llm_routing_config_service,
        telemetry_service,
        anthropic_batch_adapter,
        batch_handle_repository,
    )
