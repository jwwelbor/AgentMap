# src/agentmap/services/config/llm_models_config_service.py
"""
Centralized configuration service for LLM provider models.

Provides a single source of truth for:
- Default models for each provider (loaded from config)
- Emergency fallback defaults

Note: This service no longer validates model names against a hardcoded list.
Model validation is delegated to the provider APIs which return clear error messages.
"""
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from agentmap.services.config.app_config_service import AppConfigService


class LLMModelsConfigService:
    """
    Service for managing LLM provider model configurations.

    Centralizes model configuration loading from config files.
    No longer performs hardcoded model validation - provider APIs
    will validate model names and return clear error messages.
    """

    # Fallback constants - only used if config is completely missing
    _FALLBACK_DEFAULTS: Dict[str, str] = {
        "anthropic": "claude-3-5-sonnet-20241022",
        "openai": "gpt-4o-mini",
        "google": "gemini-1.5-flash",
    }

    def __init__(self, app_config_service: Optional["AppConfigService"] = None):
        """
        Initialize the LLM models config service.

        Args:
            app_config_service: Optional application config service to load
                default models from configuration. If None, uses fallback defaults.
        """
        self._app_config_service = app_config_service
        self._default_models_cache: Optional[Dict[str, str]] = None

    def _load_default_models(self) -> Dict[str, str]:
        """
        Load default models from configuration.

        Returns:
            Dictionary mapping provider to default model
        """
        if not self._app_config_service:
            return self._FALLBACK_DEFAULTS.copy()

        defaults = {}
        for provider in ["openai", "anthropic", "google"]:
            try:
                # Load from llm.{provider}.model in config
                model = self._app_config_service.get_value(f"llm.{provider}.model")
                if model:
                    defaults[provider] = model
                else:
                    # Use fallback if not configured
                    defaults[provider] = self._FALLBACK_DEFAULTS.get(
                        provider, self._FALLBACK_DEFAULTS["anthropic"]
                    )
            except Exception:
                # Use fallback on any error
                defaults[provider] = self._FALLBACK_DEFAULTS.get(
                    provider, self._FALLBACK_DEFAULTS["anthropic"]
                )

        return defaults

    def get_default_model(self, provider: str) -> Optional[str]:
        """
        Get the default model for a provider from configuration.

        Args:
            provider: Provider name (e.g., "openai", "anthropic", "google")

        Returns:
            Default model name from config, or fallback if not configured
        """
        # Cache default models to avoid repeated config lookups
        if self._default_models_cache is None:
            self._default_models_cache = self._load_default_models()

        return self._default_models_cache.get(provider.lower())

    def get_all_default_models(self) -> Dict[str, str]:
        """
        Get all default models for all providers from configuration.

        Returns:
            Dictionary mapping provider name to default model
        """
        if self._default_models_cache is None:
            self._default_models_cache = self._load_default_models()

        return self._default_models_cache.copy()

    def get_fallback_model(self) -> str:
        """
        Get the system-wide fallback model from configuration.

        Returns:
            Fallback model name - tries to load from routing.fallback.default_model
            in config, falls back to anthropic default if not configured.
        """
        if self._app_config_service:
            try:
                # Try to get from routing.fallback.default_model first
                fallback_model = self._app_config_service.get_value(
                    "routing.fallback.default_model"
                )
                if fallback_model:
                    return fallback_model
            except Exception:
                pass

        # Fall back to anthropic default
        return (
            self.get_default_model("anthropic") or self._FALLBACK_DEFAULTS["anthropic"]
        )
