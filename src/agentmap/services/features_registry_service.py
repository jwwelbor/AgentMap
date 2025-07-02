"""
FeaturesRegistryService for AgentMap.

Service containing business logic for feature management and provider availability.
This extracts and wraps the core functionality from the original FeatureRegistry singleton.
"""

from typing import Any, Dict, List, Optional

from agentmap.models.features_registry import FeaturesRegistry
from agentmap.services.logging_service import LoggingService


class FeaturesRegistryService:
    """
    Service for managing feature flags and provider availability.

    Contains all business logic extracted from the original FeatureRegistry singleton.
    Uses dependency injection and manages state through the FeaturesRegistry model.
    """

    def __init__(
        self, features_registry: FeaturesRegistry, logging_service: LoggingService
    ):
        """Initialize service with dependency injection."""
        self.features_registry = features_registry
        self.logger = logging_service.get_class_logger(self)

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

        available, validated = self.features_registry.get_provider_status(
            category, provider
        )
        return available and validated

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

        _, validated = self.features_registry.get_provider_status(category, provider)
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
        try:
            import fuzzywuzzy
            from fuzzywuzzy import fuzz

            # Test basic functionality
            test_score = fuzz.ratio("test", "test")
            if test_score == 100:  # Basic validation
                self.logger.debug("[FeaturesRegistryService] fuzzywuzzy is available")
                return True
            else:
                self.logger.debug(
                    "[FeaturesRegistryService] fuzzywuzzy failed basic test"
                )
                return False

        except ImportError:
            self.logger.debug("[FeaturesRegistryService] fuzzywuzzy not available")
            return False
        except Exception as e:
            self.logger.debug(f"[FeaturesRegistryService] fuzzywuzzy error: {e}")
            return False

    def has_spacy(self) -> bool:
        """
        Check if spaCy is available with English model.

        Returns:
            True if spaCy and en_core_web_sm model are available, False otherwise
        """
        try:
            import spacy

            # Check if English model is available
            nlp = spacy.load("en_core_web_sm")

            # Test basic functionality
            doc = nlp("test sentence")
            if len(doc) > 0:  # Basic validation
                self.logger.debug(
                    "[FeaturesRegistryService] spaCy with en_core_web_sm is available"
                )
                return True
            else:
                self.logger.debug("[FeaturesRegistryService] spaCy failed basic test")
                return False

        except ImportError:
            self.logger.debug(
                "[FeaturesRegistryService] spaCy or en_core_web_sm not available"
            )
            return False
        except OSError:
            self.logger.debug(
                "[FeaturesRegistryService] spaCy en_core_web_sm model not installed"
            )
            return False
        except Exception as e:
            self.logger.debug(f"[FeaturesRegistryService] spaCy error: {e}")
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
