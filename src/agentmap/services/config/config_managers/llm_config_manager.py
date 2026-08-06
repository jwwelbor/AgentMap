"""LLM configuration manager."""

import re
from typing import Any, Dict

from agentmap.services.config.config_managers.base_config_manager import (
    BaseConfigManager,
)

# Only allow simple alphanumeric provider names (no dots, slashes, etc.)
_VALID_PROVIDER_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


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

        Raises:
            ValueError: If provider name contains invalid characters.
        """
        if not _VALID_PROVIDER_RE.match(provider):
            raise ValueError(
                f"Invalid provider name: {provider!r}. "
                "Provider names must be alphanumeric (with hyphens/underscores)."
            )
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

    def get_pricing_config(self) -> Dict[str, Any]:
        """
        Get the opt-in ``llm.pricing`` price-catalog configuration.

        Architecturally separate from ``routing.cost_optimization`` /
        ``max_cost_tier`` (Decision 6) -- this method loads a distinct
        config surface and does not touch routing config in any way.

        Unlike ``get_resilience_config()``, this method supplies **no rate
        defaults** -- only structural defaults (``currency: "USD"``,
        ``models: {}``). No prices ship as defaults (Out of Scope 8): an
        absent ``llm.pricing`` block yields an empty catalog with
        ``catalog_version`` of ``None``, never fabricated rates.

        Returns:
            Dictionary shaped ``{"catalog_version": ..., "currency": ...,
            "models": {...}}``.
        """
        pricing_config = self.get_value("llm.pricing", {})

        defaults = {
            "catalog_version": None,
            "currency": "USD",
            "models": {},
        }

        return self._merge_with_defaults(pricing_config, defaults)
