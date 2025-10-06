"""
DependencyCheckerService for AgentMap.

Service containing business logic for dependency validation and checking.
This service coordinates with FeaturesRegistryService to provide comprehensive
dependency management that combines policy (feature enablement) with technical validation.
"""

import asyncio
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agentmap.builtin_definition_constants import BuiltinDefinitionConstants
from agentmap.services.features_registry_service import FeaturesRegistryService
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

        self.logger.debug(
            "[DependencyCheckerService] Initialized with FeaturesRegistryService coordination and unified availability cache"
        )

    def _get_cached_availability(
        self, category: str, key: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached availability using unified cache service."""
        if not self.availability_cache:
            return None

        try:
            return self.availability_cache.get_availability(category, key)
        except Exception as e:
            self.logger.debug(
                f"[DependencyCheckerService] Cache lookup failed for {category}.{key}: {e}"
            )
            return None

    def _set_cached_availability(
        self, category: str, key: str, result: Dict[str, Any]
    ) -> bool:
        """Set cached availability using unified cache service."""
        if not self.availability_cache:
            return False

        try:
            return self.availability_cache.set_availability(category, key, result)
        except Exception as e:
            self.logger.debug(
                f"[DependencyCheckerService] Cache set failed for {category}.{key}: {e}"
            )
            return False

    def check_dependency(self, pkg_name: str) -> bool:
        """
        Check if a single dependency is installed.

        Args:
            pkg_name: Package name to check, may include version requirements

        Returns:
            True if dependency is available, False otherwise
        """
        try:
            # Handle special cases like google.generativeai
            if "." in pkg_name and ">=" not in pkg_name:
                parts = pkg_name.split(".")
                # Try to import the top-level package
                importlib.import_module(parts[0])
                # Then try the full path
                importlib.import_module(pkg_name)
            else:
                # Extract version requirement if present
                if ">=" in pkg_name:
                    name, version = pkg_name.split(">=")
                    try:
                        mod = importlib.import_module(name)
                        if hasattr(mod, "__version__"):
                            from packaging import version as pkg_version

                            if pkg_version.parse(mod.__version__) < pkg_version.parse(
                                version
                            ):
                                self.logger.debug(
                                    f"[DependencyCheckerService] Package {name} version {mod.__version__} "
                                    f"is lower than required {version}"
                                )
                                return False
                    except ImportError:
                        return False
                else:
                    importlib.import_module(pkg_name)

            self.logger.debug(
                f"[DependencyCheckerService] Dependency check passed for: {pkg_name}"
            )
            return True

        except (ImportError, ModuleNotFoundError):
            self.logger.debug(
                f"[DependencyCheckerService] Dependency check failed for: {pkg_name}"
            )
            return False

    def validate_imports(self, module_names: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate that modules can be properly imported.

        Args:
            module_names: List of module names to validate

        Returns:
            Tuple of (all_valid, invalid_modules)
        """
        invalid = []
        self.logger.debug(
            f"[DependencyCheckerService] Validating {len(module_names)} imports"
        )
        for module_name in module_names:
            try:
                # Special case for modules with version requirements
                if ">=" in module_name:
                    base_name = module_name.split(">=")[0]
                    if base_name in sys.modules:
                        # Module is already imported, consider it valid
                        continue

                    # Try to import with version check
                    if self.check_dependency(module_name):
                        continue
                    else:
                        invalid.append(module_name)
                else:
                    # Regular module import check
                    if module_name in sys.modules:
                        # Module is already imported
                        continue

                    # Try to import
                    if self.check_dependency(module_name):
                        continue
                    else:
                        invalid.append(module_name)
            except Exception as e:
                self.logger.debug(
                    f"[DependencyCheckerService] Error validating import for {module_name}: {e}"
                )
                invalid.append(module_name)

        success = len(invalid) == 0
        if success:
            self.logger.debug(
                f"[DependencyCheckerService] All {len(module_names)} imports validated successfully"
            )
        else:
            self.logger.debug(
                f"[DependencyCheckerService] {len(invalid)} imports failed: {invalid}"
            )

        return success, invalid

    def check_llm_dependencies(
        self, provider: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Check LLM dependencies with features registry coordination.

        Combines feature policy check (is LLM feature enabled) with technical validation.
        Automatically updates the features registry with validation results.

        Args:
            provider: Optional specific provider to check (openai, anthropic, google)

        Returns:
            Tuple of (all_available, missing_packages)
        """
        # # Step 1: Check feature policy first
        if not self.features_registry.is_feature_enabled("llm"):
            self.logger.debug("[DependencyCheckerService] LLM feature not enabled")
            return False, ["llm feature not enabled"]

        if provider:
            # Check specific provider
            result, missing = self._validate_llm_provider(provider)

            # Update registry with validation result AND availability
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
            # Check if any provider is available
            available_providers = []
            all_missing = []

            for provider_name in ["openai", "anthropic", "google"]:
                available, missing = self._validate_llm_provider(provider_name)

                # Update registry for each provider - SET BOTH validated AND available
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

            # Record missing dependencies
            if all_missing:
                unique_missing = list(set(all_missing))
                self.features_registry.record_missing_dependencies(
                    "llm", unique_missing
                )

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

        Combines feature policy check with technical validation.
        Automatically updates the features registry with validation results.

        Args:
            storage_type: Optional specific storage type to check

        Returns:
            Tuple of (all_available, missing_packages)
        """
        # Step 1: Check feature policy first
        if not self.features_registry.is_feature_enabled("storage"):
            self.logger.debug("[DependencyCheckerService] Storage feature not enabled")
            return False, ["storage feature not enabled"]

        if storage_type:
            # Check specific storage type
            result, missing = self._validate_storage_type(storage_type)

            # Update registry with validation result AND availability
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
            # Check core storage dependencies (CSV is always required)
            result, missing = self._validate_storage_type("csv")

            # Update registry - SET BOTH validated AND available
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

        This is the primary method for runtime checks to see if a provider can be used.
        Combines both policy (enabled) and technical validation (dependencies available).

        Args:
            category: Provider category ('llm', 'storage')
            provider: Provider name

        Returns:
            True if provider is both enabled and technically validated
        """
        # Check feature policy
        if not self.features_registry.is_feature_enabled(category):
            return False

        # Check technical validation
        return self.features_registry.is_provider_validated(category, provider)

    def discover_and_validate_providers(
        self, category: str, force: bool = False
    ) -> Dict[str, bool]:
        """
        Discover available providers and update registry with validation results.

        This method performs comprehensive discovery and updates the features registry
        with current validation status for all known providers in a category.

        Automatically enables the feature for the category before discovery, as discovery
        implies intent to use the feature if dependencies are available.

        Args:
            category: Category to discover ('llm' or 'storage')

        Returns:
            Dictionary of provider -> validation_status
        """
        # Auto-enable the feature for discovery (like ApplicationBootstrapService did)
        # This ensures we can actually discover and validate providers
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
                if provider == "langchain":  # Skip base langchain entry
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
        """
        Validate dependencies for a specific LLM provider with cache integration.

        Args:
            provider: Provider name (openai, anthropic, google)

        Returns:
            Tuple of (is_valid, missing_dependencies)
        """
        provider_lower = provider.lower()
        dependencies = BuiltinDefinitionConstants.get_provider_dependencies(provider)

        if not dependencies:
            self.logger.warning(
                f"[DependencyCheckerService] Unknown LLM provider: {provider}"
            )
            return False, [f"unknown-provider:{provider}"]

        # Try cache first
        if not force:
            self.logger.debug(
                f"[DependencyCheckerService] Checking cache for LLM provider: {provider}"
            )
            cached_result = self._get_cached_availability(
                "dependency.llm", provider_lower
            )
            if cached_result and cached_result.get("validation_passed"):
                self.logger.debug(
                    f"[DependencyCheckerService] Using cached result for LLM provider: {provider}"
                )
                return True, []
            elif cached_result and not cached_result.get("validation_passed"):
                # Cache indicates failure - use cached error info if available
                error = cached_result.get("last_error", f"cached-failure:{provider}")
                return False, [error]

            # Cache miss or invalid - perform validation and cache result
            self.logger.debug(
                f"[DependencyCheckerService] Cache miss for LLM provider: {provider}, performing validation"
            )

        is_valid, missing = self.validate_imports(dependencies)

        # Cache the result
        cache_result = {
            "validation_passed": is_valid,
            "enabled": is_valid,
            "last_error": missing[0] if missing else None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "dependencies_checked": dependencies,
            "missing_dependencies": missing,
        }
        self._set_cached_availability("dependency.llm", provider_lower, cache_result)

        return is_valid, missing

    def _validate_storage_type(
        self, storage_type: str, force: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Validate dependencies for a specific storage type with cache integration.

        Args:
            storage_type: Storage type name

        Returns:
            Tuple of (is_valid, missing_dependencies)
        """
        storage_lower = storage_type.lower()
        dependencies = BuiltinDefinitionConstants.get_storage_dependencies(storage_type)

        if not dependencies:
            self.logger.warning(
                f"[DependencyCheckerService] Unknown storage type: {storage_type}"
            )
            return False, [f"unknown-storage:{storage_type}"]

        if not force:
            self.logger.debug(
                f"[DependencyCheckerService] Checking cache for storage type: {storage_type}"
            )
            # Try cache first
            cached_result = self._get_cached_availability(
                "dependency.storage", storage_lower
            )
            if cached_result and cached_result.get("validation_passed"):
                self.logger.debug(
                    f"[DependencyCheckerService] Using cached result for storage type: {storage_type}"
                )
                return True, []
            elif cached_result and not cached_result.get("validation_passed"):
                # Cache indicates failure - use cached error info if available
                error = cached_result.get(
                    "last_error", f"cached-failure:{storage_type}"
                )
                return False, [error]

            # Cache miss or invalid - perform validation and cache result
            self.logger.debug(
                f"[DependencyCheckerService] Cache miss for storage type: {storage_type}, performing validation"
            )

        is_valid, missing = self.validate_imports(dependencies)

        # Cache the result
        cache_result = {
            "validation_passed": is_valid,
            "enabled": is_valid,
            "last_error": missing[0] if missing else None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "dependencies_checked": dependencies,
            "missing_dependencies": missing,
        }
        self._set_cached_availability("dependency.storage", storage_lower, cache_result)

        return is_valid, missing

    def clear_dependency_cache(self, dependency_group: Optional[str] = None):
        """
        Clear dependency cache for specific group or all dependencies.

        Args:
            dependency_group: Optional specific dependency group to clear (e.g., 'dependency.llm.openai', 'dependency.storage.csv')
                            If None, clears all dependency cache
        """
        if self.availability_cache:
            if dependency_group:
                # Parse the dependency group to extract category and key
                if "." in dependency_group:
                    parts = dependency_group.split(".", 2)
                    if len(parts) >= 3 and parts[0] == "dependency":
                        category = f"{parts[0]}.{parts[1]}"
                        key = parts[2]
                        self.availability_cache.invalidate_cache(category, key)
                    elif len(parts) >= 2 and parts[0] == "dependency":
                        category = f"{parts[0]}.{parts[1]}"
                        self.availability_cache.invalidate_cache(category)
                    else:
                        self.availability_cache.invalidate_cache(dependency_group)
                else:
                    self.availability_cache.invalidate_cache(dependency_group)
            else:
                # Clear all dependency-related cache
                self.availability_cache.invalidate_cache("dependency")

            self.logger.info(
                f"[DependencyCheckerService] Cleared dependency cache: {dependency_group or 'all'}"
            )
        else:
            self.logger.warning(
                "[DependencyCheckerService] No availability cache available to clear"
            )

    def invalidate_environment_cache(self):
        """
        Invalidate cache due to environment changes (e.g., new packages installed).
        Call this after installing new packages or changing Python environment.
        """
        if self.availability_cache:
            self.availability_cache.invalidate_environment_cache()
            self.logger.info(
                "[DependencyCheckerService] Invalidated availability cache due to environment changes"
            )
        else:
            self.logger.warning(
                "[DependencyCheckerService] No availability cache available to invalidate"
            )

    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get availability cache status and statistics.

        Returns:
            Dictionary with cache status information
        """
        if not self.availability_cache:
            return {
                "cache_available": False,
                "error": "Availability cache not initialized",
            }

        try:
            cache_stats = self.availability_cache.get_cache_stats()
            return {
                "cache_available": True,
                "cache_type": "unified_availability_cache",
                "cache_stats": cache_stats,
                "performance_benefits": {
                    "cache_hit_time": "<50ms",
                    "cache_miss_time": "<200ms (down from 500ms-2s)",
                    "unified_storage": True,
                    "automatic_invalidation": True,
                },
            }
        except Exception as e:
            return {
                "cache_available": True,
                "error": f"Failed to get cache stats: {str(e)}",
            }

    def get_installation_guide(self, provider: str, category: str = "llm") -> str:
        """
        Get a friendly installation guide for dependencies.

        Args:
            provider: Provider name (e.g., "openai", "anthropic", "google")
            category: Category type ("llm" or "storage")

        Returns:
            Installation guide string
        """
        if category.lower() == "llm":
            return self._get_llm_installation_guide(provider)
        elif category.lower() == "storage":
            return self._get_storage_installation_guide(provider)
        else:
            return f"pip install 'agentmap[{category}]' or install the specific package for {provider}"

    def _get_llm_installation_guide(self, provider: Optional[str] = None) -> str:
        """Get a friendly installation guide for LLM dependencies."""
        if provider:
            provider_lower = provider.lower()
            if provider_lower == "openai":
                return "pip install 'agentmap[openai]' or pip install openai>=1.0.0 langchain"
            elif provider_lower == "anthropic":
                return "pip install 'agentmap[anthropic]' or pip install anthropic langchain"
            elif provider_lower == "google" or provider_lower == "gemini":
                return "pip install 'agentmap[google]' or pip install google-generativeai langchain-google-genai"
            else:
                return f"pip install 'agentmap[llm]' or install the specific package for {provider}"
        else:
            return "pip install 'agentmap[llm]' for all LLM support"

    def _get_storage_installation_guide(
        self, storage_type: Optional[str] = None
    ) -> str:
        """Get a friendly installation guide for storage dependencies."""
        if storage_type:
            storage_lower = storage_type.lower()
            if storage_lower == "csv":
                return "pip install pandas"
            elif storage_lower == "vector":
                return (
                    "pip install 'agentmap[vector]' or pip install langchain chromadb"
                )
            elif storage_lower == "firebase":
                return "pip install 'agentmap[firebase]' or pip install firebase-admin"
            elif storage_lower == "azure_blob":
                return "pip install 'agentmap[azure]' or pip install azure-storage-blob"
            elif storage_lower == "aws_s3":
                return "pip install 'agentmap[aws]' or pip install boto3"
            elif storage_lower == "gcp_storage":
                return "pip install 'agentmap[gcp]' or pip install google-cloud-storage"
            else:
                return f"pip install 'agentmap[storage]' or install the specific package for {storage_type}"
        else:
            return "pip install 'agentmap[storage]' for all storage support"

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
            if provider == "langchain":  # Skip the base langchain entry
                continue

            # Check if provider is both available and validated in registry
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
            # Check if storage type is both available and validated in registry
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
