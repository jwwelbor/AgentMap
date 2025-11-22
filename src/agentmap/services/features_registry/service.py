"""
FeaturesRegistryService for AgentMap.

Service containing business logic for feature management and provider availability.
This extracts and wraps the core functionality from the original FeatureRegistry singleton.

Refactored to delegate specialized functionality to:
- ProviderManager: Provider availability and validation
- NLPCapabilityChecker: NLP library detection
"""

from typing import Any, Dict, List, Optional

from agentmap.models.features_registry import FeaturesRegistry
from agentmap.services.config.availability_cache_service import AvailabilityCacheService
from agentmap.services.logging_service import LoggingService

from .nlp_capability import NLPCapabilityChecker
from .provider_management import ProviderManager


class FeaturesRegistryService:
    """
    Service for managing feature flags and provider availability.

    Contains all business logic extracted from the original FeatureRegistry singleton.
    Uses dependency injection and manages state through the FeaturesRegistry model.

    Acts as a facade, delegating to specialized components:
    - ProviderManager: Handles provider availability, validation, and aliases
    - NLPCapabilityChecker: Handles NLP library detection and capabilities
    """

    def __init__(
        self,
        features_registry: FeaturesRegistry,
        logging_service: LoggingService,
        availability_cache_service: AvailabilityCacheService,
    ):
        """Initialize service with dependency injection."""
        self.features_registry = features_registry
        self.logger = logging_service.get_class_logger(self)
        self.availability_cache_service = availability_cache_service

        # Initialize specialized components
        self._provider_manager = ProviderManager(
            features_registry=features_registry,
            availability_cache_service=availability_cache_service,
            logger=self.logger,
        )

        self._nlp_checker = NLPCapabilityChecker(
            availability_cache_service=availability_cache_service,
            logger=self.logger,
        )

        # Initialize default provider configuration
        self._initialize_default_providers()

        self.logger.debug("[FeaturesRegistryService] Initialized")

    def _initialize_default_providers(self) -> None:
        """Initialize default provider availability and validation status."""
        # Set up default LLM providers (initially unavailable)
        self.features_registry.set_provider_status("llm", "openai", False, False)
        self.features_registry.set_provider_status("llm", "anthropic", False, False)
        self.features_registry.set_provider_status("llm", "google", False, False)

        # Set up default storage providers (core ones always available)
        self.features_registry.set_provider_status("storage", "csv", True, True)
        self.features_registry.set_provider_status("storage", "json", True, True)
        self.features_registry.set_provider_status("storage", "file", True, True)
        self.features_registry.set_provider_status("storage", "firebase", False, False)
        self.features_registry.set_provider_status("storage", "vector", False, False)
        self.features_registry.set_provider_status("storage", "blob", False, False)

        self.logger.debug("[FeaturesRegistryService] Default providers initialized")

    # =========================================================================
    # Feature Management
    # =========================================================================

    def enable_feature(self, feature_name: str) -> None:
        """
        Enable a specific feature.

        Args:
            feature_name: Name of the feature to enable
        """
        self.features_registry.add_feature(feature_name)
        self.logger.debug(f"[FeaturesRegistryService] Feature enabled: {feature_name}")

    def disable_feature(self, feature_name: str) -> None:
        """
        Disable a specific feature.

        Args:
            feature_name: Name of the feature to disable
        """
        self.features_registry.remove_feature(feature_name)
        self.logger.debug(f"[FeaturesRegistryService] Feature disabled: {feature_name}")

    def is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a feature is enabled.

        Args:
            feature_name: Name of the feature to check

        Returns:
            True if feature is enabled, False otherwise
        """
        return self.features_registry.has_feature(feature_name)

    # =========================================================================
    # Provider Management (delegated to ProviderManager)
    # =========================================================================

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
        self._provider_manager.set_provider_available(category, provider, available)

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
        self._provider_manager.set_provider_validated(category, provider, validated)

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
        return self._provider_manager.is_provider_available(category, provider)

    def is_provider_registered(self, category: str, provider: str) -> bool:
        """
        Check if a provider is registered (may not be validated).

        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name

        Returns:
            True if provider is registered, False otherwise
        """
        return self._provider_manager.is_provider_registered(category, provider)

    def is_provider_validated(self, category: str, provider: str) -> bool:
        """
        Check if a provider's dependencies are validated.

        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name

        Returns:
            True if provider dependencies are validated, False otherwise
        """
        return self._provider_manager.is_provider_validated(category, provider)

    def get_available_providers(self, category: str) -> List[str]:
        """
        Get a list of available and validated providers in a category.

        Args:
            category: Provider category ('llm', 'storage')

        Returns:
            List of available and validated provider names
        """
        return self._provider_manager.get_available_providers(category)

    def _resolve_provider_alias(self, category: str, provider: str) -> str:
        """
        Resolve provider aliases to canonical names.

        Args:
            category: Provider category
            provider: Provider name (possibly an alias)

        Returns:
            Canonical provider name
        """
        return self._provider_manager.resolve_provider_alias(category, provider)

    def _get_known_providers_for_category(self, category: str) -> List[str]:
        """
        Get list of known providers for a category.

        Args:
            category: Provider category

        Returns:
            List of known provider names for the category
        """
        return self._provider_manager.get_known_providers_for_category(category)

    def invalidate_provider_cache(
        self, category: Optional[str] = None, provider: Optional[str] = None
    ) -> None:
        """
        Invalidate cached provider availability data.

        Args:
            category: Optional category to invalidate (e.g., 'llm', 'storage')
            provider: Optional specific provider to invalidate
                     If category is provided but provider is None, invalidates entire category
                     If both are None, invalidates all provider cache
        """
        self._provider_manager.invalidate_cache(category, provider)

    # =========================================================================
    # NLP Capability Checking (delegated to NLPCapabilityChecker)
    # =========================================================================

    def has_fuzzywuzzy(self) -> bool:
        """
        Check if fuzzywuzzy is available for fuzzy string matching.

        Returns:
            True if fuzzywuzzy is available, False otherwise
        """
        return self._nlp_checker.has_fuzzywuzzy()

    def has_spacy(self) -> bool:
        """
        Check if spaCy is available with English model.

        Returns:
            True if spaCy and en_core_web_sm model are available, False otherwise
        """
        return self._nlp_checker.has_spacy()

    def get_nlp_capabilities(self) -> Dict[str, Any]:
        """
        Get available NLP capabilities summary.

        Returns:
            Dictionary with NLP library availability and capabilities
        """
        return self._nlp_checker.get_nlp_capabilities()

    def invalidate_capability_cache(self) -> None:
        """
        Invalidate all cached capability checks (NLP libraries, etc.).
        """
        self._nlp_checker.invalidate_cache()

    # =========================================================================
    # Dependency Management
    # =========================================================================

    def record_missing_dependencies(self, category: str, missing: List[str]) -> None:
        """
        Record missing dependencies for a category.

        Args:
            category: Category name
            missing: List of missing dependencies
        """
        self.features_registry.set_missing_dependencies(category, missing)

        if missing:
            self.logger.debug(
                f"[FeaturesRegistryService] Recorded missing dependencies for {category}: {missing}"
            )
        else:
            self.logger.debug(
                f"[FeaturesRegistryService] No missing dependencies for {category}"
            )

    def get_missing_dependencies(
        self, category: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Get missing dependencies.

        Args:
            category: Optional category to filter

        Returns:
            Dictionary of missing dependencies by category
        """
        return self.features_registry.get_missing_dependencies(category)
