"""
FeaturesRegistryService for AgentMap.

Service containing business logic for feature management and provider availability.
This extracts and wraps the core functionality from the original FeatureRegistry singleton.
"""

from typing import Any, Dict, List, Optional

from agentmap.models.features_registry import FeaturesRegistry
from agentmap.services.config.availability_cache_service import AvailabilityCacheService
from agentmap.services.logging_service import LoggingService


class FeaturesRegistryService:
    """
    Service for managing feature flags and provider availability.

    Contains all business logic extracted from the original FeatureRegistry singleton.
    Uses dependency injection and manages state through the FeaturesRegistry model.
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
        self.availability_cache_service.invalidate_cache(
            "provider", f"{category}.{provider}"
        )
        self.availability_cache_service.invalidate_cache(
            "provider", f"{category}.{provider}.validated"
        )

        self.logger.debug(
            f"[FeaturesRegistryService] Provider '{provider}' in category '{category}' set to: {available}"
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
        self.availability_cache_service.invalidate_cache(
            "provider", f"{category}.{provider}"
        )
        self.availability_cache_service.invalidate_cache(
            "provider", f"{category}.{provider}.validated"
        )

        self.logger.debug(
            f"[FeaturesRegistryService] Provider '{provider}' in category '{category}' validation set to: {validated}"
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
        provider = self._resolve_provider_alias(category, provider)

        # Check cache first
        cache_key = f"{category}.{provider}"
        cached = self.availability_cache_service.get_availability("provider", cache_key)
        if cached is not None:
            self.logger.trace(
                f"[FeaturesRegistryService] Cache hit for provider.{cache_key}"
            )
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
            f"[FeaturesRegistryService] Cache miss for provider.{cache_key}, cached result: {result}"
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
        provider = self._resolve_provider_alias(category, provider)

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
        provider = self._resolve_provider_alias(category, provider)

        # Check cache first
        cache_key = f"{category}.{provider}.validated"
        cached = self.availability_cache_service.get_availability("provider", cache_key)
        if cached is not None:
            self.logger.trace(
                f"[FeaturesRegistryService] Cache hit for provider.{cache_key}"
            )
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
            f"[FeaturesRegistryService] Cache miss for provider.{cache_key}, cached result: {validated}"
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

        # Get all providers for this category from the registry
        all_missing = self.features_registry.get_missing_dependencies()
        all_missing.get(category, {})

        # Check each known provider in the category
        known_providers = self._get_known_providers_for_category(category)
        for provider in known_providers:
            available, validated = self.features_registry.get_provider_status(
                category, provider
            )
            if available and validated:
                available_providers.append(provider)

        return available_providers

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

    def _resolve_provider_alias(self, category: str, provider: str) -> str:
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
        if category == "llm":
            if provider == "gpt":
                return "openai"
            elif provider == "claude":
                return "anthropic"
            elif provider == "gemini":
                return "google"

        return provider

    def has_fuzzywuzzy(self) -> bool:
        """
        Check if fuzzywuzzy is available for fuzzy string matching.

        Returns:
            True if fuzzywuzzy is available, False otherwise
        """
        # Check cache first
        cached = self.availability_cache_service.get_availability(
            "capability.nlp", "fuzzywuzzy"
        )
        if cached is not None:
            self.logger.trace(
                "[FeaturesRegistryService] Cache hit for capability.nlp.fuzzywuzzy"
            )
            return cached.get("available", False)

        # Perform actual check
        try:
            import fuzzywuzzy
            from fuzzywuzzy import fuzz

            # Test basic functionality
            test_score = fuzz.ratio("test", "test")
            available = test_score == 100

            # Cache result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "fuzzywuzzy",
                {"available": available, "type": "nlp_library"},
            )

            if available:
                self.logger.debug(
                    "[FeaturesRegistryService] fuzzywuzzy is available (cached)"
                )
            else:
                self.logger.debug(
                    "[FeaturesRegistryService] fuzzywuzzy failed basic test (cached)"
                )
            return available

        except ImportError:
            # Cache negative result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "fuzzywuzzy",
                {"available": False, "type": "nlp_library", "reason": "ImportError"},
            )
            self.logger.debug(
                "[FeaturesRegistryService] fuzzywuzzy not available (cached)"
            )
            return False
        except Exception as e:
            # Cache negative result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "fuzzywuzzy",
                {"available": False, "type": "nlp_library", "reason": str(e)},
            )
            self.logger.debug(
                f"[FeaturesRegistryService] fuzzywuzzy error: {e} (cached)"
            )
            return False

    def has_spacy(self) -> bool:
        """
        Check if spaCy is available with English model.

        Returns:
            True if spaCy and en_core_web_sm model are available, False otherwise
        """
        # Check cache first
        cached = self.availability_cache_service.get_availability(
            "capability.nlp", "spacy"
        )
        if cached is not None:
            self.logger.trace(
                "[FeaturesRegistryService] Cache hit for capability.nlp.spacy"
            )
            return cached.get("available", False)

        # Perform actual check
        try:
            import spacy

            # Check if English model is available
            nlp = spacy.load("en_core_web_sm")

            # Test basic functionality
            doc = nlp("test sentence")
            available = len(doc) > 0

            # Cache result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "spacy",
                {
                    "available": available,
                    "type": "nlp_library",
                    "model": "en_core_web_sm",
                },
            )

            if available:
                self.logger.debug(
                    "[FeaturesRegistryService] spaCy with en_core_web_sm is available (cached)"
                )
            else:
                self.logger.debug(
                    "[FeaturesRegistryService] spaCy failed basic test (cached)"
                )
            return available

        except ImportError:
            # Cache negative result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "spacy",
                {"available": False, "type": "nlp_library", "reason": "ImportError"},
            )
            self.logger.debug(
                "[FeaturesRegistryService] spaCy or en_core_web_sm not available (cached)"
            )
            return False
        except OSError:
            # Cache negative result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "spacy",
                {
                    "available": False,
                    "type": "nlp_library",
                    "reason": "OSError - model not installed",
                },
            )
            self.logger.debug(
                "[FeaturesRegistryService] spaCy en_core_web_sm model not installed (cached)"
            )
            return False
        except Exception as e:
            # Cache negative result
            self.availability_cache_service.set_availability(
                "capability.nlp",
                "spacy",
                {"available": False, "type": "nlp_library", "reason": str(e)},
            )
            self.logger.debug(f"[FeaturesRegistryService] spaCy error: {e} (cached)")
            return False

    def get_nlp_capabilities(self) -> Dict[str, Any]:
        """
        Get available NLP capabilities summary.

        Returns:
            Dictionary with NLP library availability and capabilities
        """
        capabilities = {
            "fuzzywuzzy_available": self.has_fuzzywuzzy(),
            "spacy_available": self.has_spacy(),
            "enhanced_matching": False,
            "fuzzy_threshold_default": 80,
            "supported_features": [],
        }

        # Add supported features based on available libraries
        if capabilities["fuzzywuzzy_available"]:
            capabilities["supported_features"].append("fuzzy_string_matching")
            capabilities["supported_features"].append("typo_tolerance")

        if capabilities["spacy_available"]:
            capabilities["supported_features"].append("advanced_tokenization")
            capabilities["supported_features"].append("keyword_extraction")
            capabilities["supported_features"].append("lemmatization")

        # Enhanced matching available if either library is present
        capabilities["enhanced_matching"] = (
            capabilities["fuzzywuzzy_available"] or capabilities["spacy_available"]
        )

        self.logger.debug(f"[FeaturesRegistryService] NLP capabilities: {capabilities}")
        return capabilities

    def _get_known_providers_for_category(self, category: str) -> List[str]:
        """
        Get list of known providers for a category.

        Args:
            category: Provider category

        Returns:
            List of known provider names for the category
        """
        if category == "llm":
            return ["openai", "anthropic", "google"]
        elif category == "storage":
            return ["csv", "json", "file", "firebase", "vector", "blob"]
        else:
            return []

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
        if category and provider:
            # Invalidate specific provider
            self.availability_cache_service.invalidate_cache(
                "provider", f"{category}.{provider}"
            )
            self.availability_cache_service.invalidate_cache(
                "provider", f"{category}.{provider}.validated"
            )
            self.logger.debug(
                f"[FeaturesRegistryService] Invalidated cache for provider: {category}.{provider}"
            )
        elif category:
            # Invalidate entire category
            self.availability_cache_service.invalidate_cache("provider", category)
            self.logger.debug(
                f"[FeaturesRegistryService] Invalidated cache for category: {category}"
            )
        else:
            # Invalidate all provider cache
            self.availability_cache_service.invalidate_cache("provider")
            self.logger.debug(
                "[FeaturesRegistryService] Invalidated all provider cache"
            )

    def invalidate_capability_cache(self) -> None:
        """
        Invalidate all cached capability checks (NLP libraries, etc.).
        """
        self.availability_cache_service.invalidate_cache("capability")
        self.logger.debug("[FeaturesRegistryService] Invalidated all capability cache")
