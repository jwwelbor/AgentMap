"""
FeaturesRegistry domain model for AgentMap.

Pure data container for feature flags and provider availability state.
All business logic belongs in services, not in this domain model.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class FeaturesRegistry:
    """
    Pure data container for feature registry state.

    This model only holds data - all business logic belongs in FeaturesRegistryService.

    Attributes:
        features_enabled: Set of enabled feature names (lowercase)
        providers_available: Nested dict of provider availability by category
        providers_validated: Nested dict of provider validation status by category
        missing_dependencies: Dict mapping categories to lists of missing dependencies
    """

    features_enabled: Set[str] = field(default_factory=set)
    providers_available: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    providers_validated: Dict[str, Dict[str, bool]] = field(default_factory=dict)
    missing_dependencies: Dict[str, List[str]] = field(default_factory=dict)

    def add_feature(self, feature_name: str) -> None:
        """
        Store a feature as enabled.

        Simple data storage method similar to Node.add_edge().

        Args:
            feature_name: Name of the feature to store as enabled
        """
        self.features_enabled.add(feature_name.lower())

    def remove_feature(self, feature_name: str) -> None:
        """
        Remove a feature from enabled features.

        Simple data removal method for feature state.

        Args:
            feature_name: Name of the feature to remove
        """
        self.features_enabled.discard(feature_name.lower())

    def has_feature(self, feature_name: str) -> bool:
        """
        Check if a feature is stored as enabled.

        Simple query method similar to Node.has_conditional_routing().

        Args:
            feature_name: Name of the feature to check

        Returns:
            True if feature is in enabled set, False otherwise
        """
        return feature_name.lower() in self.features_enabled

    def set_provider_status(
        self, category: str, provider: str, available: bool, validated: bool
    ) -> None:
        """
        Store provider availability and validation status.

        Simple data storage method for provider state.

        Args:
            category: Provider category (e.g., 'llm', 'storage')
            provider: Provider name (e.g., 'openai', 'anthropic')
            available: Whether provider is available
            validated: Whether provider dependencies are validated
        """
        category = category.lower()
        provider = provider.lower()

        # Initialize category if not exists
        if category not in self.providers_available:
            self.providers_available[category] = {}
        if category not in self.providers_validated:
            self.providers_validated[category] = {}

        # Store status
        self.providers_available[category][provider] = available
        self.providers_validated[category][provider] = validated

    def get_provider_status(self, category: str, provider: str) -> tuple[bool, bool]:
        """
        Get provider availability and validation status.

        Simple query method for provider state.

        Args:
            category: Provider category
            provider: Provider name

        Returns:
            Tuple of (available, validated) status
        """
        category = category.lower()
        provider = provider.lower()

        available = self.providers_available.get(category, {}).get(provider, False)
        validated = self.providers_validated.get(category, {}).get(provider, False)

        return available, validated

    def set_missing_dependencies(self, category: str, missing: List[str]) -> None:
        """
        Store missing dependencies for a category.

        Simple data storage method for dependency tracking.

        Args:
            category: Category name
            missing: List of missing dependency names
        """
        self.missing_dependencies[category] = missing.copy()

    def get_missing_dependencies(
        self, category: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Get missing dependencies by category.

        Simple query method for dependency information.

        Args:
            category: Optional category to filter by

        Returns:
            Dictionary of missing dependencies by category
        """
        if category:
            return {category: self.missing_dependencies.get(category, [])}
        return self.missing_dependencies.copy()

    def __repr__(self) -> str:
        """String representation of the features registry."""
        feature_count = len(self.features_enabled)
        provider_count = sum(
            len(providers) for providers in self.providers_available.values()
        )
        return (
            f"<FeaturesRegistry {feature_count} features, {provider_count} providers>"
        )
