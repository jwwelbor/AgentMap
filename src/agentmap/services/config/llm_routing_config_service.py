"""
Routing configuration section for AgentMap LLM routing system.

This module provides configuration management for the matrix-based LLM routing
system, including provider x complexity matrix, task types, and routing policies.
"""

from typing import Any, Dict, List, Optional

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService

# Import helper modules for delegated functionality
from agentmap.services.config.llm_routing_matrix import (
    load_routing_matrix,
    get_model_for_complexity as _get_model_for_complexity,
    get_available_providers as _get_available_providers,
    is_provider_available as _is_provider_available,
)
from agentmap.services.config.llm_routing_task_types import (
    load_task_types,
    get_task_type_config as _get_task_type_config,
    get_provider_preference as _get_provider_preference,
    get_default_complexity as _get_default_complexity,
    get_complexity_keywords as _get_complexity_keywords,
    get_available_task_types as _get_available_task_types,
)
from agentmap.services.config.llm_routing_validators import (
    validate_routing_config,
    validate_provider_routing,
)
from agentmap.services.config.llm_routing_availability import (
    get_cached_availability,
    set_cached_availability,
    get_provider_availability as _get_provider_availability,
    validate_all_providers as _validate_all_providers,
    is_provider_available_async as _is_provider_available_async,
    clear_provider_cache as _clear_provider_cache,
    get_cache_stats as _get_cache_stats,
)


class LLMRoutingConfigService:
    """
    Configuration section for LLM routing.

    Handles loading, validation, and access to routing configuration including
    the provider x complexity matrix and task type definitions.
    """

    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
        llm_models_config_service,
        availability_cache_service=None,
    ):
        """
        Initialize routing configuration from dictionary.

        Args:
            app_config_service: Application configuration service
            logging_service: Logging service
            llm_models_config_service: LLM models configuration service
            availability_cache_service: Optional unified availability cache service
        """
        self._logger = logging_service.get_class_logger(self)
        self._app_config_service = app_config_service
        self._llm_models_config_service = llm_models_config_service
        self._availability_cache_service = availability_cache_service
        self.config_dict = app_config_service.get_routing_config()
        self.enabled = self.config_dict.get("enabled", False)
        self.routing_matrix = load_routing_matrix(self.config_dict, self._logger)
        self.task_types = load_task_types(self.config_dict, self._logger)
        self.complexity_analysis = self.config_dict.get("complexity_analysis", {})
        self.cost_optimization = self.config_dict.get("cost_optimization", {})
        self.fallback = self.config_dict.get("fallback", {})
        self.performance = self.config_dict.get("performance", {})

        # Validate configuration on load
        validation_errors = self.validate_AppConfigService()
        if validation_errors:
            self._logger.warning(
                f"Routing configuration validation errors: {validation_errors}"
            )

    def validate_AppConfigService(self) -> List[str]:
        """
        Validate the complete routing configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        return validate_routing_config(
            self.routing_matrix,
            self.task_types,
            self.complexity_analysis
        )

    def get_model_for_complexity(self, provider: str, complexity: str) -> Optional[str]:
        """
        Get the model for a given provider and complexity.

        Args:
            provider: Provider name (e.g., "anthropic", "openai")
            complexity: Complexity level (e.g., "low", "medium", "high", "critical")

        Returns:
            Model name or None if not found
        """
        return _get_model_for_complexity(self.routing_matrix, provider, complexity)

    def get_task_type_config(self, task_type: str) -> Dict[str, Any]:
        """
        Get configuration for a specific task type.

        Args:
            task_type: Task type name

        Returns:
            Task type configuration or general config if not found
        """
        return _get_task_type_config(self.task_types, task_type)

    def get_provider_preference(self, task_type: str) -> List[str]:
        """
        Get provider preference list for a task type.

        Args:
            task_type: Task type name

        Returns:
            List of preferred providers in order
        """
        return _get_provider_preference(self.task_types, task_type)

    def get_default_complexity(self, task_type: str) -> str:
        """
        Get default complexity for a task type.

        Args:
            task_type: Task type name

        Returns:
            Default complexity level
        """
        return _get_default_complexity(self.task_types, task_type)

    def get_complexity_keywords(self, task_type: str) -> Dict[str, List[str]]:
        """
        Get complexity keywords for a task type.

        Args:
            task_type: Task type name

        Returns:
            Dictionary mapping complexity levels to keyword lists
        """
        return _get_complexity_keywords(self.task_types, task_type)

    def get_available_providers(self) -> List[str]:
        """
        Get list of providers configured in the routing matrix.

        Returns:
            List of available provider names
        """
        return _get_available_providers(self.routing_matrix)

    def get_available_task_types(self) -> List[str]:
        """
        Get list of configured task types.

        Returns:
            List of available task type names
        """
        return _get_available_task_types(self.task_types)

    def is_provider_available(self, provider: str) -> bool:
        """
        Check if a provider is configured in the routing matrix.

        Args:
            provider: Provider name to check

        Returns:
            True if provider is available
        """
        return _is_provider_available(self.routing_matrix, provider)

    def get_fallback_provider(self) -> str:
        """
        Get the configured fallback provider.

        Returns:
            Fallback provider name
        """
        return self.fallback.get("default_provider", "anthropic")

    def get_fallback_model(self) -> str:
        """
        Get the configured fallback model from config or llm_models_config_service.

        Returns:
            Fallback model name from config, or system default if not configured
        """
        # Try to get from fallback config first
        config_model = self.fallback.get("default_model")
        if config_model:
            return config_model

        # Fall back to llm_models_config_service
        return self._llm_models_config_service.get_fallback_model()

    def is_cost_optimization_enabled(self) -> bool:
        """
        Check if cost optimization is enabled.

        Returns:
            True if cost optimization is enabled
        """
        return self.cost_optimization.get("enabled", True)

    def get_max_cost_tier(self) -> str:
        """
        Get the maximum cost tier allowed.

        Returns:
            Maximum cost tier (low, medium, high, critical)
        """
        return self.cost_optimization.get("max_cost_tier", "high")

    def is_routing_cache_enabled(self) -> bool:
        """
        Check if routing decision caching is enabled.

        Returns:
            True if caching is enabled
        """
        return self.performance.get("enable_routing_cache", True)

    def get_cache_ttl(self) -> int:
        """
        Get the cache time-to-live in seconds.

        Returns:
            Cache TTL in seconds
        """
        return self.performance.get("cache_ttl", 300)

    def _get_cached_availability(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get cached availability using unified cache service.

        Args:
            provider: Provider name to check

        Returns:
            Cached availability data or None if not found/invalid
        """
        return get_cached_availability(
            self._availability_cache_service, provider, self._logger
        )

    def _set_cached_availability(self, provider: str, result: Dict[str, Any]) -> bool:
        """
        Set cached availability using unified cache service.

        Args:
            provider: Provider name
            result: Availability result data to cache

        Returns:
            True if successfully cached, False otherwise
        """
        return set_cached_availability(
            self._availability_cache_service, provider, result, self._logger
        )

    async def get_provider_availability(self, provider: str) -> Dict[str, Any]:
        """
        Get availability status for a specific provider.

        Args:
            provider: Provider name to check

        Returns:
            Dictionary with availability status and metadata
        """
        return await _get_provider_availability(
            provider,
            self.routing_matrix,
            self._availability_cache_service,
            self._logger
        )

    async def validate_all_providers(self) -> Dict[str, Dict[str, Any]]:
        """
        Validate availability of all configured providers.

        Returns:
            Dictionary mapping provider names to availability status
        """
        return await _validate_all_providers(
            self.routing_matrix,
            self._availability_cache_service,
            self._logger
        )

    async def is_provider_available_async(self, provider: str) -> bool:
        """
        Async version of provider availability check with caching.

        Args:
            provider: Provider name to check

        Returns:
            True if provider is available and working
        """
        return await _is_provider_available_async(
            provider,
            self.routing_matrix,
            self._availability_cache_service,
            self._logger
        )

    def clear_provider_cache(self, provider: Optional[str] = None):
        """
        Clear availability cache for specific provider or all providers.

        Args:
            provider: Provider name to clear, or None for all providers
        """
        _clear_provider_cache(
            self._availability_cache_service, provider, self._logger
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get availability cache statistics and health information.

        Returns:
            Dictionary with cache statistics
        """
        return _get_cache_stats(
            self._availability_cache_service,
            self.routing_matrix,
            self._logger
        )

    def get_provider_routing_validation(self) -> List[str]:
        """
        Validate provider routing matrix configuration.

        Returns:
            List of validation error messages
        """
        return validate_provider_routing(
            self.routing_matrix,
            self._app_config_service,
            self._logger
        )
