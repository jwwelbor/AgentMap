"""Core container part with configuration, logging, and shared cross-cutting services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from dependency_injector import containers, providers


class CoreContainer(containers.DeclarativeContainer):
    """Provides configuration, logging, and cache infrastructure."""

    config = providers.Configuration()

    # --- Configuration services -------------------------------------------------

    config_service = providers.Singleton(
        "agentmap.services.config.config_service.ConfigService"
    )

    app_config_service = providers.Singleton(
        "agentmap.services.config.app_config_service.AppConfigService",
        config_service,
        config.path,
    )

    # --- Logging ----------------------------------------------------------------

    @staticmethod
    def _create_and_initialize_logging_service(app_config_service):
        from agentmap.services.logging_service import LoggingService

        logging_config = app_config_service.get_logging_config()
        service = LoggingService(logging_config)
        service.initialize()
        return service

    logging_service = providers.Singleton(
        _create_and_initialize_logging_service,
        app_config_service,
    )

    # --- Availability cache -----------------------------------------------------

    @staticmethod
    def _create_availability_cache_service(app_config_service, logging_service):
        from agentmap.services.config.availability_cache_service import (
            AvailabilityCacheService,
        )

        logger = logging_service.get_logger("agentmap.availability_cache")
        try:
            cache_dir = app_config_service.get_cache_path() or "agentmap_data/cache"
            cache_path = Path(cache_dir) / "unified_availability.json"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            service = AvailabilityCacheService(
                cache_file_path=cache_path, logger=logger
            )
            try:
                config_files = [
                    app_config_service.get_config_file_path(),
                    app_config_service.get_storage_config_path(),
                ]
                for config_file in config_files:
                    if config_file and Path(config_file).exists():
                        service.register_config_file(config_file)
            except Exception:
                pass
            logger.info("Unified availability cache service initialized")
            return service
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.warning(f"Failed to initialize availability cache service: {exc}")
            return None

    availability_cache_service = providers.Singleton(
        _create_availability_cache_service,
        app_config_service,
        logging_service,
    )

    # --- Config convenience callables -------------------------------------------

    logging_config = providers.Callable(
        lambda svc: svc.get_logging_config(),
        app_config_service,
    )
    execution_config = providers.Callable(
        lambda svc: svc.get_execution_config(),
        app_config_service,
    )
    prompts_config = providers.Callable(
        lambda svc: svc.get_prompts_config(),
        app_config_service,
    )
    custom_agents_config = providers.Callable(
        lambda svc: svc.get_custom_agents_path(),
        app_config_service,
    )

    # --- Cross-cutting services --------------------------------------------------

    llm_models_config_service = providers.Singleton(
        "agentmap.services.config.llm_models_config_service.LLMModelsConfigService",
        app_config_service,
    )

    auth_service = providers.Singleton(
        "agentmap.services.auth_service.AuthService",
        providers.Callable(lambda svc: svc.get_auth_config(), app_config_service),
        logging_service,
    )

    file_path_service = providers.Singleton(
        "agentmap.services.file_path_service.FilePathService",
        app_config_service,
        logging_service,
    )

    prompt_manager_service = providers.Singleton(
        "agentmap.services.prompt_manager_service.PromptManagerService",
        app_config_service,
        logging_service,
    )

    def get_cache_status(self) -> Dict[str, Any]:
        cache_service = self.availability_cache_service()
        if cache_service and hasattr(cache_service, "get_cache_stats"):
            return {
                "unified_availability_cache": cache_service.get_cache_stats(),
                "cache_type": "unified_availability_cache",
                "cache_available": True,
            }
        return {
            "error": "Unified availability cache service not available",
            "cache_available": False,
        }

    def invalidate_all_caches(self) -> bool:
        cache_service = self.availability_cache_service()
        if cache_service and hasattr(cache_service, "invalidate_cache"):
            cache_service.invalidate_cache()
            return True
        try:  # pragma: no cover - defensive logging path
            self.logging_service().get_logger("agentmap.di.cache").error(
                "Failed to invalidate caches"
            )
        except Exception:
            pass
        return False
