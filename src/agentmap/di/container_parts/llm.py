"""LLM container part with routing and orchestration services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from dependency_injector import containers, providers

from agentmap.services.protocols.service_protocols import (
    BatchAdapterProtocol,
    LLMBudgetGuardProtocol,
)

if TYPE_CHECKING:
    from agentmap.services.config.llm_routing_config_service import (
        LLMRoutingConfigService,
    )
    from agentmap.services.llm_batch_repository import BatchHandleRepository
    from agentmap.services.llm_service import LLMService
    from agentmap.services.routing.cache import RoutingCache
    from agentmap.services.routing.complexity_analyzer import PromptComplexityAnalyzer
    from agentmap.services.routing.routing_service import LLMRoutingService


class LLMContainer(containers.DeclarativeContainer):
    """Provides LLM configuration, routing, and execution services."""

    # Dependency providers resolve these values dynamically at runtime.
    app_config_service: Any = providers.Dependency()
    logging_service: Any = providers.Dependency()
    availability_cache_service: Any = providers.Dependency()
    features_registry_service: Any = providers.Dependency()
    llm_models_config_service: Any = providers.Dependency()
    telemetry_service: Any = providers.Dependency()

    # E05-F06 REQ-F-003/REQ-F-004 (Component Change 10): the single canonical
    # registration path for an opt-in LLMBudgetGuardProtocol implementation.
    # Defaults to None (no guard-related code path executes). Hosts register
    # their guard by overriding this provider on the LLM sub-container, e.g.:
    #   from dependency_injector import providers
    #   container._llm.budget_guard.override(providers.Object(my_guard))
    # `llm_service` is a Singleton -- override budget_guard BEFORE the first
    # `llm_service()` resolution, or the override has no effect.
    # There is deliberately no competing per-call registration path
    # (Decision 4).
    budget_guard: Any = providers.Dependency()
    budget_guard.set_default(providers.Object(None))

    @staticmethod
    def _create_llm_routing_config_service(
        app_config_service: Any,
        logging_service: Any,
        llm_models_config_service: Any,
        availability_cache_service: Any,
    ) -> LLMRoutingConfigService:
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
    def _create_prompt_complexity_analyzer(
        app_config_service: Any, logging_service: Any
    ) -> PromptComplexityAnalyzer:
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
    def _create_routing_cache(logging_service: Any) -> RoutingCache:
        from agentmap.services.routing.cache import RoutingCache

        return RoutingCache(logging_service)

    routing_cache = providers.Singleton(
        _create_routing_cache,
        logging_service,
    )

    @staticmethod
    def _create_llm_routing_service(
        llm_routing_config_service: Any,
        logging_service: Any,
        routing_cache: Any,
        prompt_complexity_analyzer: Any,
    ) -> LLMRoutingService:
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
        provider_key: str,
        adapter_cls: Any,
        app_config_service: Any,
        logging_service: Any,
    ) -> Optional[BatchAdapterProtocol]:
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
            return cast(
                BatchAdapterProtocol,
                adapter_cls(api_key=api_key, logger=logger),
            )
        except LLMDependencyError as exc:
            logger.warning(
                "llm_batch.dependency_missing adapter=%s: %s",
                adapter_cls.__name__,
                exc,
            )
            return None

    @staticmethod
    def _create_anthropic_batch_adapter(
        app_config_service: Any, logging_service: Any
    ) -> Optional[BatchAdapterProtocol]:
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
    def _create_openai_batch_adapter(
        app_config_service: Any, logging_service: Any
    ) -> Optional[BatchAdapterProtocol]:
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
    def _create_gemini_batch_adapter(
        app_config_service: Any, logging_service: Any
    ) -> Optional[BatchAdapterProtocol]:
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
    def _create_batch_handle_repository(
        app_config_service: Any,
    ) -> BatchHandleRepository:
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
        app_config_service: Any,
        logging_service: Any,
        llm_routing_service: Any,
        llm_models_config_service: Any,
        features_registry_service: Any,
        llm_routing_config_service: Any,
        telemetry_service: Any,
        anthropic_batch_adapter: Optional[BatchAdapterProtocol] = None,
        openai_batch_adapter: Optional[BatchAdapterProtocol] = None,
        gemini_batch_adapter: Optional[BatchAdapterProtocol] = None,
        batch_handle_repository: Optional[BatchHandleRepository] = None,
        budget_guard: Optional[LLMBudgetGuardProtocol] = None,
        attempt_lifecycle: Any = None,
    ) -> LLMService:
        from agentmap.services.llm_service import LLMService

        # Build the provider→adapter registry; omit providers whose SDK is absent
        # (factory returns None when LLMDependencyError is raised at init time).
        batch_adapters: Dict[str, BatchAdapterProtocol] = {}
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
            budget_guard=budget_guard,
            attempt_lifecycle=attempt_lifecycle,
        )

        # Wire content capture flags from telemetry config (T-E02-F04-003).
        # Flags are stored on the telemetry_service singleton by T-E02-F04-004
        # as ``_content_capture_flags``.  Default to False (privacy-safe).
        flags = getattr(telemetry_service, "_content_capture_flags", None) or {}
        svc._capture_llm_prompts = bool(flags.get("llm_prompts", False))
        svc._capture_llm_responses = bool(flags.get("llm_responses", False))

        return svc

    @staticmethod
    def _create_attempt_file_logger(
        app_config_service: Any, logging_service: Any
    ) -> Any:
        from pathlib import Path

        from agentmap.services.llm_attempt_file_logger import LLMAttemptFileLogger

        config = app_config_service.get_llm_call_log_config()
        if not isinstance(config, dict) or not config.get("enabled", False):
            return None
        directory = Path(config.get("directory", "agentmap/llm_call_logs")).expanduser()
        return LLMAttemptFileLogger(directory, logging_service)

    attempt_file_logger = providers.Singleton(
        _create_attempt_file_logger,
        app_config_service,
        logging_service,
    )

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
        budget_guard,
        attempt_file_logger,
    )
