"""LLM configuration manager."""

from typing import Any, Dict

from agentmap.services.config.config_managers.base_config_manager import (
    BaseConfigManager,
)


class LLMConfigManager(BaseConfigManager):
    """
    Configuration manager for LLM provider and resilience settings.

    Handles the ``llm:`` section of agentmap_config.yaml, including
    per-provider configuration and the ``resilience`` sub-section
    (retry + circuit breaker).
    """

    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get configuration for a specific LLM provider.

        Args:
            provider: Provider name (e.g. "openai", "anthropic", "google").

        Returns:
            Dictionary containing provider-specific configuration.
        """
        return self.get_value(f"llm.{provider}", {})

    def get_resilience_config(self) -> Dict[str, Any]:
        """
        Get LLM resilience configuration (retry + circuit breaker) with defaults.

        Returns:
            Dictionary containing resilience configuration.
        """
        resilience_config = self.get_value("llm.resilience", {})

        defaults = {
            "retry": {
                "max_attempts": 3,
                "backoff_base": 2.0,
                "backoff_max": 30.0,
                "jitter": True,
            },
            "circuit_breaker": {
                "failure_threshold": 5,
                "reset_timeout": 60,
            },
        }

        return self._merge_with_defaults(resilience_config, defaults)
