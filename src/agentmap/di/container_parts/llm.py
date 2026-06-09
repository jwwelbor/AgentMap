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
    def _make_batch_adapter(
        provider_key, adapter_cls, app_config_service, logging_service
    ):
        from agentmap.exceptions import LLMDependencyError

        api_key = app_config_service.get_llm_config(provider_key).get("api_key", "")
        logger = logging_service.get_class_logger(adapter_cls)
        if not api_key:
            logger.debug(
                "llm_batch.adapter_skipped adapter=%s reason=no_api_key",
                adapter_cls.__name__,
            )
            return None
        try:
            return adapter_cls(api_key=api_key, logger=logger)
        except LLMDependencyError as exc:
            logger.warning(
                "llm_batch.dependency_missing adapter=%s: %s",
                adapter_cls.__name__,
                exc,
            )
            return None

    @staticmethod
    def _create_anthropic_batch_adapter(app_config_service, logging_service):
        from agentmap.services.llm.anthropic_batch_adapter import AnthropicBatchAdapter

        return LLMContainer._make_batch_adapter(
            "anthropic",
            AnthropicBatchAdapter,
            app_config_service,
            logging_service,
        )

    anthropic_batch_adapter = providers.Singleton(
        _create_anthropic_batch_adapter,
        app_config_service,
        logging_service,
    )

    @staticmethod
    def _create_openai_batch_adapter(app_config_service, logging_service):
        from agentmap.services.llm.openai_batch_adapter import OpenAIBatchAdapter

        return LLMContainer._make_batch_adapter(
            "openai",
            OpenAIBatchAdapter,
            app_config_service,
            logging_service,
        )

    openai_batch_adapter = providers.Singleton(
        _create_openai_batch_adapter,
        app_config_service,
        logging_service,
    )

    @staticmethod
    def _create_gemini_batch_adapter(app_config_service, logging_service):
        from agentmap.services.llm.gemini_batch_adapter import GeminiBatchAdapter

        return LLMContainer._make_batch_adapter(
            "google",
            GeminiBatchAdapter,
            app_config_service,
            logging_service,
        )

    gemini_batch_adapter = providers.Singleton(
        _create_gemini_batch_adapter,
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
        openai_batch_adapter=None,
        gemini_batch_adapter=None,
        batch_handle_repository=None,
    ):
        from agentmap.services.llm_service import LLMService

        # Build the provider→adapter registry; omit providers whose SDK is absent
        # (factory returns None when LLMDependencyError is raised at init time).
        batch_adapters = {}
        if anthropic_batch_adapter is not None:
            batch_adapters["anthropic"] = anthropic_batch_adapter
        if openai_batch_adapter is not None:
            batch_adapters["openai"] = openai_batch_adapter
        if gemini_batch_adapter is not None:
            batch_adapters["google"] = gemini_batch_adapter

        svc = LLMService(
            app_config_service,
            logging_service,
            llm_routing_service,
            llm_models_config_service,
            features_registry_service,
            llm_routing_config_service,
            telemetry_service,
            batch_adapters=batch_adapters,
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
        openai_batch_adapter,
        gemini_batch_adapter,
        batch_handle_repository,
    )
