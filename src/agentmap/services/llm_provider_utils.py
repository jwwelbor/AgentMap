"""
LLM Provider Utilities for configuration and provider management.

Handles provider normalization, configuration retrieval, API key management,
and provider availability checks.
"""

import os
from typing import Any, Dict, List, Optional

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.config import AppConfigService
from agentmap.services.config.llm_models_config_service import LLMModelsConfigService
from agentmap.services.logging_service import LoggingService


class LLMProviderUtils:
    """Utilities for managing LLM provider configuration and availability."""

    def __init__(
        self,
        configuration: AppConfigService,
        llm_models_config: LLMModelsConfigService,
        logging_service: LoggingService,
    ):
        """
        Initialize provider utilities.

        Args:
            configuration: Application configuration service
            llm_models_config: LLM models configuration service
            logging_service: Logging service
        """
        self.configuration = configuration
        self.llm_models_config = llm_models_config
        self._logger = logging_service.get_class_logger("agentmap.llm.provider")

    def normalize_provider(self, provider: str) -> str:
        """
        Normalize provider name and handle aliases.

        Args:
            provider: Provider name to normalize

        Returns:
            Normalized provider name
        """
        provider_lower = provider.lower()

        # Handle aliases
        aliases = {"gpt": "openai", "claude": "anthropic", "gemini": "google"}

        return aliases.get(provider_lower, provider_lower)

    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get configuration for the specified provider.

        Args:
            provider: Provider name

        Returns:
            Provider configuration dictionary

        Raises:
            LLMConfigurationError: If provider is not configured
        """
        config = self.configuration.get_llm_config(provider)

        if not config:
            raise LLMConfigurationError(
                f"No configuration found for provider: {provider}"
            )

        # Ensure required fields have defaults
        defaults = self.get_provider_defaults(provider)
        for key, default_value in defaults.items():
            if key not in config:
                config[key] = default_value

        return config

    def get_provider_defaults(self, provider: str) -> Dict[str, Any]:
        """
        Get default configuration values for a provider.

        Args:
            provider: Provider name

        Returns:
            Dictionary of default configuration values
        """
        default_model = self.llm_models_config.get_default_model(provider)

        if not default_model:
            return {}

        # Get API key environment variable name
        api_key_env_var = self.get_api_key_env_var(provider)

        return {
            "model": default_model,
            "temperature": 0.7,
            "api_key": os.environ.get(api_key_env_var, ""),
        }

    def get_available_providers(self) -> List[str]:
        """
        Get list of providers that are configured and have valid API keys.

        Returns:
            List of available provider names
        """
        available_providers = []

        # Check each provider for configuration and API key
        providers_to_check = ["openai", "anthropic", "google"]

        for provider in providers_to_check:
            try:
                config = self.configuration.get_llm_config(provider)
                if config:
                    # Check if API key is available
                    api_key = config.get("api_key") or os.environ.get(
                        self.get_api_key_env_var(provider)
                    )
                    if api_key:
                        available_providers.append(provider)
                        self._logger.debug(f"Provider {provider} is available")
                    else:
                        self._logger.debug(f"Provider {provider} missing API key")
                else:
                    self._logger.debug(f"Provider {provider} not configured")
            except Exception as e:
                self._logger.debug(f"Provider {provider} check failed: {e}")

        return available_providers

    def get_api_key_env_var(self, provider: str) -> str:
        """
        Get the environment variable name for a provider's API key.

        Args:
            provider: Provider name

        Returns:
            Environment variable name
        """
        env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        return env_vars.get(provider, f"{provider.upper()}_API_KEY")

    def get_default_model(self, provider: Optional[str] = None) -> str:
        """
        Get default model name for this provider.

        Args:
            provider: Provider name

        Returns:
            Default model name
        """
        if not provider:
            return self.llm_models_config.get_fallback_model()

        default_model = self.llm_models_config.get_default_model(provider)
        return default_model or self.llm_models_config.get_fallback_model()
