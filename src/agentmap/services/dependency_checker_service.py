"""
DependencyCheckerService for AgentMap.

Service containing business logic for dependency validation and checking.
This service coordinates with FeaturesRegistryService to provide comprehensive
dependency management that combines policy (feature enablement) with technical validation.
"""

from typing import Any, Dict, List, Optional, Tuple

from agentmap.builtin_definition_constants import BuiltinDefinitionConstants
from agentmap.services.cache_manager import CacheHelper
from agentmap.services.dependency_validators import DependencyValidator, ProviderValidator
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.installation_guides import InstallationGuideHelper
from agentmap.services.logging_service import LoggingService


class DependencyCheckerService:
    """
    Service for checking and validating dependencies for AgentMap.

    Coordinates with FeaturesRegistryService to provide unified dependency validation
    that combines feature policy (enabled/disabled) with technical validation (dependencies available).

    The service automatically updates the features registry with validation results,
    providing a single source of truth for dependency status.
    """

    def __init__(
        self,
        logging_service: LoggingService,
        features_registry_service: FeaturesRegistryService,
        availability_cache_service=None,
    ):
        """Initialize service with dependency injection."""
        self.logger = logging_service.get_class_logger(self)
        self.features_registry = features_registry_service
        self.availability_cache = availability_cache_service

        # Initialize helper classes
        self._cache_helper = CacheHelper(self.logger, availability_cache_service)
        self._dependency_validator = DependencyValidator(self.logger)
        self._provider_validator = ProviderValidator(
            self.logger, self._dependency_validator, self._cache_helper
        )
        self._installation_guide_helper = InstallationGuideHelper()

        self.logger.debug(
            "[DependencyCheckerService] Initialized with FeaturesRegistryService coordination and unified availability cache"
        )

    def check_dependency(self, pkg_name: str) -> bool:
        """
        Check if a single dependency is installed.

        Args:
            pkg_name: Package name to check, may include version requirements

        Returns:
            True if dependency is available, False otherwise
        """
        return self._dependency_validator.check_dependency(pkg_name)

    def validate_imports(self, module_names: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate that modules can be properly imported.

        Args:
            module_names: List of module names to validate

        Returns:
            Tuple of (all_valid, invalid_modules)
        """
        return self._dependency_validator.validate_imports(module_names)

    def check_llm_dependencies(
        self, provider: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Check LLM dependencies with features registry coordination.

        Args:
            provider: Optional specific provider to check (openai, anthropic, google)

        Returns:
            Tuple of (all_available, missing_packages)
        """
        if not self.features_registry.is_feature_enabled("llm"):
            self.logger.debug("[DependencyCheckerService] LLM feature not enabled")
            return False, ["llm feature not enabled"]

        if provider:
            result, missing = self._validate_llm_provider(provider)
            self.features_registry.set_provider_validated("llm", provider, result)
            self.features_registry.set_provider_available("llm", provider, result)
            if not result:
                self.features_registry.record_missing_dependencies(
                    f"llm.{provider}", missing
                )
            self.logger.debug(
                f"[DependencyCheckerService] LLM provider '{provider}' validation: {result}"
            )
            return result, missing
        else:
            available_providers = []
            all_missing = []

            for provider_name in ["openai", "anthropic", "google"]:
                available, missing = self._validate_llm_provider(provider_name)
                self.features_registry.set_provider_validated(
                    "llm", provider_name, available
                )
                self.features_registry.set_provider_available(
                    "llm", provider_name, available
                )

                if available:
                    available_providers.append(provider_name)
                else:
                    all_missing.extend(missing)

            if all_missing:
                unique_missing = list(set(all_missing))
                self.features_registry.record_missing_dependencies("llm", unique_missing)

            success = len(available_providers) > 0
            self.logger.debug(
                f"[DependencyCheckerService] LLM providers available: {available_providers}"
            )
            return success, list(set(all_missing)) if not success else []

    def check_storage_dependencies(
        self, storage_type: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Check storage dependencies with features registry coordination.

        Args:
            storage_type: Optional specific storage type to check

        Returns:
            Tuple of (all_available, missing_packages)
        """
        if not self.features_registry.is_feature_enabled("storage"):
            self.logger.debug("[DependencyCheckerService] Storage feature not enabled")
            return False, ["storage feature not enabled"]

        if storage_type:
            result, missing = self._validate_storage_type(storage_type)
            self.features_registry.set_provider_validated(
                "storage", storage_type, result
            )
            self.features_registry.set_provider_available(
                "storage", storage_type, result
            )
            if not result:
                self.features_registry.record_missing_dependencies(
                    f"storage.{storage_type}", missing
                )
            self.logger.debug(
                f"[DependencyCheckerService] Storage type '{storage_type}' validation: {result}"
            )
            return result, missing
        else:
            result, missing = self._validate_storage_type("csv")
            self.features_registry.set_provider_validated("storage", "csv", result)
            self.features_registry.set_provider_available("storage", "csv", result)
            if not result:
                self.features_registry.record_missing_dependencies("storage", missing)
            self.logger.debug(
                f"[DependencyCheckerService] Core storage dependencies validation: {result}"
            )
            return result, missing

    def can_use_provider(self, category: str, provider: str) -> bool:
        """
        Check if a specific provider is fully available (enabled + validated).

        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name

        Returns:
            True if provider is both enabled and technically validated
        """
        if not self.features_registry.is_feature_enabled(category):
            return False
        return self.features_registry.is_provider_validated(category, provider)

    def discover_and_validate_providers(
        self, category: str, force: bool = False
    ) -> Dict[str, bool]:
        """
        Discover available providers and update registry with validation results.

        Args:
            category: Category to discover ('llm' or 'storage')
            force: Force re-validation even if cached

        Returns:
            Dictionary of provider -> validation_status
        """
        category_lower = category.lower()
        self.features_registry.enable_feature(category_lower)
        self.logger.debug(
            f"[DependencyCheckerService] Enabled '{category_lower}' feature for provider discovery"
        )

        self.logger.debug(
            f"[DependencyCheckerService] Discovering providers for category: {category}"
        )

        results = {}

        if category_lower == "llm":
            supported_providers = (
                BuiltinDefinitionConstants.get_supported_llm_providers()
            )
            for provider in supported_providers:
                if provider == "langchain":
                    continue

                is_available, missing = self._validate_llm_provider(provider, force)
                results[provider] = is_available

                self.features_registry.set_provider_validated(
                    "llm", provider, is_available
                )
                self.features_registry.set_provider_available(
                    "llm", provider, is_available
                )
                if not is_available:
                    self.features_registry.record_missing_dependencies(
                        f"llm.{provider}", missing
                    )

        elif category_lower == "storage":
            supported_types = BuiltinDefinitionConstants.get_supported_storage_types()

            for storage_type in supported_types:
                is_available, missing = self._validate_storage_type(storage_type, force)
                results[storage_type] = is_available

                self.features_registry.set_provider_validated(
                    "storage", storage_type, is_available
                )
                self.features_registry.set_provider_available(
                    "storage", storage_type, is_available
                )
                if not is_available:
                    self.features_registry.record_missing_dependencies(
                        f"storage.{storage_type}", missing
                    )

        self.logger.debug(
            f"[DependencyCheckerService] Provider discovery results for {category}: {results}"
        )
        return results

    def _validate_llm_provider(
        self, provider: str, force: bool = False
    ) -> Tuple[bool, List[str]]:
        """Validate dependencies for a specific LLM provider with cache integration."""
        return self._provider_validator.validate_llm_provider(provider, force)

    def _validate_storage_type(
        self, storage_type: str, force: bool = False
    ) -> Tuple[bool, List[str]]:
        """Validate dependencies for a specific storage type with cache integration."""
        return self._provider_validator.validate_storage_type(storage_type, force)

    def clear_dependency_cache(self, dependency_group: Optional[str] = None):
        """
        Clear dependency cache for specific group or all dependencies.

        Args:
            dependency_group: Optional specific dependency group to clear
        """
        self._cache_helper.clear_dependency_cache(dependency_group)

    def invalidate_environment_cache(self):
        """
        Invalidate cache due to environment changes (e.g., new packages installed).
        Call this after installing new packages or changing Python environment.
        """
        self._cache_helper.invalidate_environment_cache()

    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get availability cache status and statistics.

        Returns:
            Dictionary with cache status information
        """
        return self._cache_helper.get_cache_status()

    def get_installation_guide(self, provider: str, category: str = "llm") -> str:
        """
        Get a friendly installation guide for dependencies.

        Args:
            provider: Provider name (e.g., "openai", "anthropic", "google")
            category: Category type ("llm" or "storage")

        Returns:
            Installation guide string
        """
        return self._installation_guide_helper.get_installation_guide(provider, category)

    def _get_llm_installation_guide(self, provider: Optional[str] = None) -> str:
        """Get a friendly installation guide for LLM dependencies."""
        return self._installation_guide_helper.get_llm_installation_guide(provider)

    def _get_storage_installation_guide(
        self, storage_type: Optional[str] = None
    ) -> str:
        """Get a friendly installation guide for storage dependencies."""
        return self._installation_guide_helper.get_storage_installation_guide(storage_type)

    def get_available_llm_providers(self) -> List[str]:
        """
        Get list of available LLM providers based on validation and feature enablement.

        Returns:
            List of provider names that are both enabled and validated
        """
        if not self.features_registry.is_feature_enabled("llm"):
            return []

        available = []
        for provider in BuiltinDefinitionConstants.get_supported_llm_providers():
            if provider == "langchain":
                continue

            if self.features_registry.is_provider_available("llm", provider):
                available.append(provider)

        self.logger.debug(
            f"[DependencyCheckerService] Available LLM providers: {available}"
        )
        return available

    def get_available_storage_types(self) -> List[str]:
        """
        Get list of available storage types based on validation and feature enablement.

        Returns:
            List of storage type names that are both enabled and validated
        """
        if not self.features_registry.is_feature_enabled("storage"):
            return []

        available = []
        for storage_type in BuiltinDefinitionConstants.get_supported_storage_types():
            if self.features_registry.is_provider_available("storage", storage_type):
                available.append(storage_type)

        self.logger.debug(
            f"[DependencyCheckerService] Available storage types: {available}"
        )
        return available

    def get_dependency_status_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of dependency status.

        Returns:
            Dictionary with complete dependency status information
        """
        return {
            "llm": {
                "feature_enabled": self.features_registry.is_feature_enabled("llm"),
                "available_providers": self.get_available_llm_providers(),
                "missing_dependencies": self.features_registry.get_missing_dependencies(
                    "llm"
                ),
            },
            "storage": {
                "feature_enabled": self.features_registry.is_feature_enabled("storage"),
                "available_types": self.get_available_storage_types(),
                "missing_dependencies": self.features_registry.get_missing_dependencies(
                    "storage"
                ),
            },
            "coordination": {
                "features_registry_available": self.features_registry is not None,
                "automatic_validation_updates": True,
                "policy_and_technical_validation": True,
            },
        }
