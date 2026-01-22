"""
Provider management functionality for AgentMap.

This module handles provider availability, validation, and alias resolution.
Extracted from FeaturesRegistryService for better separation of concerns.
"""

from typing import List

from agentmap.models.features_registry import FeaturesRegistry
from agentmap.services.config.availability_cache_service import AvailabilityCacheService


class ProviderManager:
    """
    Manages provider availability and validation status.

    Handles all provider-related operations including:
    - Setting and checking provider availability
    - Setting and checking provider validation status
    - Resolving provider aliases
    - Caching provider status
    """

    # Provider alias mappings
    LLM_ALIASES = {
        "gpt": "openai",
        "claude": "anthropic",
        "gemini": "google",
    }

    # Known providers by category
    KNOWN_PROVIDERS = {
        "llm": ["openai", "anthropic", "google"],
        "storage": ["csv", "json", "file", "firebase", "vector", "blob"],
    }

    def __init__(
        self,
        features_registry: FeaturesRegistry,
        availability_cache_service: AvailabilityCacheService,
        logger,
    ):
        """
        Initialize provider manager.

        Args:
            features_registry: The features registry model
            availability_cache_service: Cache service for availability data
            logger: Logger instance
        """
        self.features_registry = features_registry
        self.availability_cache_service = availability_cache_service
        self.logger = logger

    def set_provider_available(
        self, category: str, provider: str, available: bool = True
    ) -> None:
        """
        Set availability for a specific provider.

        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name
            available: Availability status
        """
        category = category.lower()
        provider = provider.lower()

        # Get current validation status to preserve it
        current_available, current_validated = (
            self.features_registry.get_provider_status(category, provider)
        )

        # Update availability while preserving validation status
        self.features_registry.set_provider_status(
            category, provider, available, current_validated
        )

        # Invalidate cache entries for this provider
        self._invalidate_provider_cache_entries(category, provider)

        self.logger.debug(
            f"[ProviderManager] Provider '{provider}' in category '{category}' set to: {available}"
        )

    def set_provider_validated(
        self, category: str, provider: str, validated: bool = True
    ) -> None:
        """
        Set validation status for a specific provider.

        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name
            validated: Validation status - True if dependencies are confirmed working
        """
        category = category.lower()
        provider = provider.lower()

        # Get current availability status to preserve it
        current_available, current_validated = (
            self.features_registry.get_provider_status(category, provider)
        )

        # Update validation while preserving availability status
        self.features_registry.set_provider_status(
            category, provider, current_available, validated
        )

        # Invalidate cache entries for this provider
        self._invalidate_provider_cache_entries(category, provider)

        self.logger.debug(
            f"[ProviderManager] Provider '{provider}' in category '{category}' validation set to: {validated}"
        )

    def is_provider_available(self, category: str, provider: str) -> bool:
        """
        Check if a specific provider is available and validated.

        Provider is only truly available if it's both marked available AND validated.

        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name

        Returns:
            True if provider is available and validated, False otherwise
        """
        category = category.lower()
        provider = self.resolve_provider_alias(category, provider)

        # Check cache first
        cache_key = f"{category}.{provider}"
        cached = self.availability_cache_service.get_availability("provider", cache_key)
        if cached is not None:
            self.logger.trace(f"[ProviderManager] Cache hit for provider.{cache_key}")
            return cached.get("available", False)

        # Get from registry
        available, validated = self.features_registry.get_provider_status(
            category, provider
        )
        result = available and validated

        # Cache the result
        self.availability_cache_service.set_availability(
            "provider",
            cache_key,
            {"available": result, "category": category, "provider": provider},
        )
        self.logger.debug(
            f"[ProviderManager] Cache miss for provider.{cache_key}, cached result: {result}"
        )

        return result

    def is_provider_registered(self, category: str, provider: str) -> bool:
        """
        Check if a provider is registered (may not be validated).

        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name

        Returns:
            True if provider is registered, False otherwise
        """
        category = category.lower()
        provider = self.resolve_provider_alias(category, provider)

        available, _ = self.features_registry.get_provider_status(category, provider)
        return available

    def is_provider_validated(self, category: str, provider: str) -> bool:
        """
        Check if a provider's dependencies are validated.

        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name

        Returns:
            True if provider dependencies are validated, False otherwise
        """
        category = category.lower()
        provider = self.resolve_provider_alias(category, provider)

        # Check cache first
        cache_key = f"{category}.{provider}.validated"
        cached = self.availability_cache_service.get_availability("provider", cache_key)
        if cached is not None:
            self.logger.trace(f"[ProviderManager] Cache hit for provider.{cache_key}")
            return cached.get("validated", False)

        # Get from registry
        _, validated = self.features_registry.get_provider_status(category, provider)

        # Cache the result
        self.availability_cache_service.set_availability(
            "provider",
            cache_key,
            {"validated": validated, "category": category, "provider": provider},
        )
        self.logger.debug(
            f"[ProviderManager] Cache miss for provider.{cache_key}, cached result: {validated}"
        )

        return validated

    def get_available_providers(self, category: str) -> List[str]:
        """
        Get a list of available and validated providers in a category.

        Args:
            category: Provider category ('llm', 'storage')

        Returns:
            List of available and validated provider names
        """
        category = category.lower()
        available_providers = []

        # Check each known provider in the category
        known_providers = self.get_known_providers_for_category(category)
        for provider in known_providers:
            available, validated = self.features_registry.get_provider_status(
                category, provider
            )
            if available and validated:
                available_providers.append(provider)

        return available_providers

    def resolve_provider_alias(self, category: str, provider: str) -> str:
        """
        Resolve provider aliases to canonical names.

        Args:
            category: Provider category
            provider: Provider name (possibly an alias)

        Returns:
            Canonical provider name
        """
        provider = provider.lower()

        # Handle aliases for LLM providers
        if category == "llm" and provider in self.LLM_ALIASES:
            return self.LLM_ALIASES[provider]

        return provider

    def get_known_providers_for_category(self, category: str) -> List[str]:
        """
        Get list of known providers for a category.

        Args:
            category: Provider category

        Returns:
            List of known provider names for the category
        """
        return self.KNOWN_PROVIDERS.get(category, [])

    def invalidate_cache(self, category: str = None, provider: str = None) -> None:
        """
        Invalidate cached provider availability data.

        Args:
            category: Optional category to invalidate (e.g., 'llm', 'storage')
            provider: Optional specific provider to invalidate
                     If category is provided but provider is None, invalidates entire category
                     If both are None, invalidates all provider cache
        """
        if category and provider:
            # Invalidate specific provider
            self._invalidate_provider_cache_entries(category, provider)
            self.logger.debug(
                f"[ProviderManager] Invalidated cache for provider: {category}.{provider}"
            )
        elif category:
            # Invalidate entire category
            self.availability_cache_service.invalidate_cache("provider", category)
            self.logger.debug(
                f"[ProviderManager] Invalidated cache for category: {category}"
            )
        else:
            # Invalidate all provider cache
            self.availability_cache_service.invalidate_cache("provider")
            self.logger.debug("[ProviderManager] Invalidated all provider cache")

    def _invalidate_provider_cache_entries(self, category: str, provider: str) -> None:
        """
        Invalidate all cache entries for a specific provider.

        Args:
            category: Provider category
            provider: Provider name
        """
        self.availability_cache_service.invalidate_cache(
            "provider", f"{category}.{provider}"
        )
        self.availability_cache_service.invalidate_cache(
            "provider", f"{category}.{provider}.validated"
        )
