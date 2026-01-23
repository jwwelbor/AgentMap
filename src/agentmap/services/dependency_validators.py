"""Dependency validation utilities for DependencyCheckerService."""

import importlib
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from agentmap.builtin_definition_constants import BuiltinDefinitionConstants


class DependencyValidator:
    """Core dependency validation logic."""

    def __init__(self, logger):
        """Initialize with logger."""
        self.logger = logger

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
                                    f"[DependencyValidator] Package {name} version {mod.__version__} "
                                    f"is lower than required {version}"
                                )
                                return False
                    except ImportError:
                        return False
                else:
                    importlib.import_module(pkg_name)

            self.logger.debug(
                f"[DependencyValidator] Dependency check passed for: {pkg_name}"
            )
            return True

        except (ImportError, ModuleNotFoundError):
            self.logger.debug(
                f"[DependencyValidator] Dependency check failed for: {pkg_name}"
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
            f"[DependencyValidator] Validating {len(module_names)} imports"
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
                    f"[DependencyValidator] Error validating import for {module_name}: {e}"
                )
                invalid.append(module_name)

        success = len(invalid) == 0
        if success:
            self.logger.debug(
                f"[DependencyValidator] All {len(module_names)} imports validated successfully"
            )
        else:
            self.logger.debug(
                f"[DependencyValidator] {len(invalid)} imports failed: {invalid}"
            )

        return success, invalid


class ProviderValidator:
    """Provider-specific validation logic with cache integration."""

    def __init__(self, logger, dependency_validator: DependencyValidator, cache_helper):
        """Initialize with logger, dependency validator, and cache helper."""
        self.logger = logger
        self._dependency_validator = dependency_validator
        self._cache_helper = cache_helper

    def _validate_provider(
        self, provider_type: str, provider_name: str, force: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Common validation logic for both LLM and storage providers.

        Args:
            provider_type: Type of provider ("llm" or "storage")
            provider_name: Name of the provider
            force: Skip cache and force validation

        Returns:
            Tuple of (is_valid, missing_dependencies)
        """
        provider_lower = provider_name.lower()

        # Get dependencies based on provider type
        if provider_type == "llm":
            dependencies = BuiltinDefinitionConstants.get_provider_dependencies(
                provider_name
            )
            unknown_error = f"unknown-provider:{provider_name}"
        else:  # storage
            dependencies = BuiltinDefinitionConstants.get_storage_dependencies(
                provider_name
            )
            unknown_error = f"unknown-storage:{provider_name}"

        if not dependencies:
            self.logger.warning(
                f"[ProviderValidator] Unknown {provider_type} provider: {provider_name}"
            )
            return False, [unknown_error]

        # Try cache first
        if not force:
            self.logger.debug(
                f"[ProviderValidator] Checking cache for {provider_type} provider: {provider_name}"
            )
            cached_result = self._cache_helper.get_cached_availability(
                f"dependency.{provider_type}", provider_lower
            )
            if cached_result and cached_result.get("validation_passed"):
                self.logger.debug(
                    f"[ProviderValidator] Using cached result for {provider_type} provider: {provider_name}"
                )
                return True, []
            elif cached_result and not cached_result.get("validation_passed"):
                # Cache indicates failure - use cached error info if available
                error = cached_result.get(
                    "last_error", f"cached-failure:{provider_name}"
                )
                return False, [error]

            # Cache miss or invalid - perform validation and cache result
            self.logger.debug(
                f"[ProviderValidator] Cache miss for {provider_type} provider: {provider_name}, performing validation"
            )

        is_valid, missing = self._dependency_validator.validate_imports(dependencies)

        # Cache the result
        cache_result = {
            "validation_passed": is_valid,
            "enabled": is_valid,
            "last_error": missing[0] if missing else None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "dependencies_checked": dependencies,
            "missing_dependencies": missing,
        }
        self._cache_helper.set_cached_availability(
            f"dependency.{provider_type}", provider_lower, cache_result
        )

        return is_valid, missing

    def validate_llm_provider(
        self, provider: str, force: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Validate dependencies for a specific LLM provider with cache integration.

        Args:
            provider: Provider name (openai, anthropic, google)
            force: Skip cache and force validation

        Returns:
            Tuple of (is_valid, missing_dependencies)
        """
        return self._validate_provider("llm", provider, force)

    def validate_storage_type(
        self, storage_type: str, force: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Validate dependencies for a specific storage type with cache integration.

        Args:
            storage_type: Storage type name
            force: Skip cache and force validation

        Returns:
            Tuple of (is_valid, missing_dependencies)
        """
        return self._validate_provider("storage", storage_type, force)
