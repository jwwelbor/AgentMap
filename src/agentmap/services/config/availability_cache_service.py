"""
Unified Availability Cache Service for AgentMap.

Provides a single, centralized cache service for storing and retrieving boolean
availability results across all categories (dependencies, LLM providers, storage, etc.).
This service replaces separate cache implementations and provides automatic
invalidation on config and environment changes.

Key Features:
- Unified storage with categorized keys (dependency.llm.openai, storage.csv, etc.)
- Pure storage layer - never performs actual validation work
- Thread-safe with proper locking
- Automatic invalidation on config file changes and environment changes
- Manual invalidation support
- Graceful degradation on errors
"""

import hashlib
import json
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agentmap.services.config.availability_cache import ThreadSafeFileCache


class EnvironmentChangeDetector:
    """Detects environment changes for automatic cache invalidation."""

    def __init__(self):
        self._env_lock = threading.Lock()
        self._cached_env_hash: Optional[str] = None
        self._last_check_time: float = 0
        self._check_interval: float = 60.0  # Check environment every 60 seconds

    def get_environment_hash(self) -> str:
        """Get current environment hash, with caching to avoid expensive operations."""
        with self._env_lock:
            current_time = time.time()

            # Use cached hash if within check interval
            if (
                self._cached_env_hash is not None
                and current_time - self._last_check_time < self._check_interval
            ):
                return self._cached_env_hash

            # Compute fresh environment hash
            self._cached_env_hash = self._compute_environment_hash()
            self._last_check_time = current_time
            return self._cached_env_hash

    def invalidate_environment_cache(self):
        """Force recomputation of environment hash on next access."""
        with self._env_lock:
            self._cached_env_hash = None
            self._last_check_time = 0

    def _compute_environment_hash(self) -> str:
        """Compute hash representing current environment state."""
        try:
            environment_data = {
                "python_version": sys.version,
                "platform": platform.platform(),
                "python_path": sys.path[:5],  # First 5 paths to avoid excessive data
                "installed_packages": self._get_packages_hash(),
            }

            env_str = json.dumps(environment_data, sort_keys=True)
            return hashlib.sha256(env_str.encode("utf-8")).hexdigest()[:16]

        except Exception:
            raise

    def _get_packages_hash(self) -> str:
        """Get hash of installed packages for change detection."""
        try:
            # Try pip freeze with timeout
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                timeout=5,  # Reduced timeout for faster response
            )
            if result.returncode == 0:
                packages = sorted(result.stdout.strip().split("\n"))
                packages_str = "\n".join(packages)
                return hashlib.sha256(packages_str.encode("utf-8")).hexdigest()[:12]
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ):
            pass

        # Fallback to sys.modules hash
        modules = sorted(
            list(sys.modules.keys())[:100]
        )  # Limit to first 100 for performance
        modules_str = "\n".join(modules)
        return hashlib.sha256(modules_str.encode("utf-8")).hexdigest()[:12]


class ConfigChangeDetector:
    """Detects configuration file changes for automatic cache invalidation."""

    def __init__(self):
        self._config_lock = threading.Lock()
        self._config_mtimes: Dict[str, float] = {}
        self._config_hashes: Dict[str, str] = {}

    def register_config_file(self, config_path: Union[str, Path]):
        """Register a configuration file for change monitoring."""
        config_path = Path(config_path)
        if not config_path.exists():
            return

        with self._config_lock:
            path_str = str(config_path)
            try:
                mtime = config_path.stat().st_mtime
                self._config_mtimes[path_str] = mtime

                # Store hash for content-based comparison
                with open(config_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[
                        :16
                    ]
                    self._config_hashes[path_str] = content_hash
            except:
                raise

    def has_config_changed(self) -> bool:
        """Check if any registered config files have changed."""
        with self._config_lock:
            for path_str, stored_mtime in self._config_mtimes.items():
                try:
                    config_path = Path(path_str)
                    if not config_path.exists():
                        # File was deleted - consider it changed
                        return True

                    current_mtime = config_path.stat().st_mtime
                    if abs(current_mtime - stored_mtime) > 1.0:  # 1 second tolerance
                        return True

                    # Also check content hash for more reliable detection
                    with open(config_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        current_hash = hashlib.sha256(
                            content.encode("utf-8")
                        ).hexdigest()[:16]
                        stored_hash = self._config_hashes.get(path_str, "")
                        if current_hash != stored_hash:
                            return True

                except Exception:
                    # If we can't check, assume no change to avoid false positives
                    raise

            return False

    def update_config_tracking(self):
        """Update tracking data for all registered config files."""
        with self._config_lock:
            for path_str in list(self._config_mtimes.keys()):
                try:
                    config_path = Path(path_str)
                    if config_path.exists():
                        mtime = config_path.stat().st_mtime
                        self._config_mtimes[path_str] = mtime

                        with open(config_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            content_hash = hashlib.sha256(
                                content.encode("utf-8")
                            ).hexdigest()[:16]
                            self._config_hashes[path_str] = content_hash
                except Exception:
                    raise


class AvailabilityCacheService:
    """
    Unified availability cache service for storing and retrieving boolean availability results.

    This service provides a clean interface for caching availability checks across all
    categories (dependencies, LLM providers, storage, etc.) using categorized keys.
    It's a pure storage layer that never performs actual validation work.

    Key Categories and Examples:
    - dependency.llm.openai
    - dependency.storage.csv
    - llm_provider.anthropic
    - llm_provider.openai
    - storage.csv
    - storage.vector
    """

    def __init__(self, cache_file_path: Union[str, Path], logger=None):
        """
        Initialize the unified availability cache service.

        Args:
            cache_file_path: Path to cache file for persistent storage
            logger: Optional logger for error reporting and debugging
        """
        self._cache_file_path = Path(cache_file_path)
        self._logger = logger

        # Core cache storage
        self._file_cache = ThreadSafeFileCache(self._cache_file_path, logger)

        # Change detection
        self._env_detector = EnvironmentChangeDetector()
        self._config_detector = ConfigChangeDetector()

        # Thread safety
        self._cache_lock = threading.RLock()
        self._invalidation_lock = threading.Lock()

        # Automatic invalidation tracking
        self._last_env_hash: Optional[str] = None
        self._auto_invalidation_enabled = False

        # Performance statistics
        self._stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_sets": 0,
            "invalidations": 0,
            "auto_invalidations": 0,
        }

        if self._logger:
            self._logger.debug(
                f"AvailabilityCacheService initialized with cache file: {self._cache_file_path}"
            )

    def get_availability(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached availability data for a categorized key.

        Args:
            category: Category of the availability check (e.g., 'dependency.llm', 'storage')
            key: Specific key within the category (e.g., 'openai', 'csv')

        Returns:
            Cached availability data or None if not found/invalid

        Raises:
            CacheNotFoundError: If cache file doesn't exist
        """
        cache_key = f"{category}.{key}"

        try:
            with self._cache_lock:
                # Check if cache file exists first
                if not self._cache_file_path.exists():
                    from agentmap.exceptions.service_exceptions import (
                        CacheNotFoundError,
                    )

                    raise CacheNotFoundError(
                        f"Availability cache not found at {self._cache_file_path}. "
                        "Please run 'agentmap refresh' to initialize the provider cache."
                    )

                # # Check for automatic invalidation triggers
                # if self._should_auto_invalidate():
                #     self._perform_auto_invalidation()

                cache_data = self._file_cache.load_cache()
                if not cache_data:
                    self._stats["cache_misses"] += 1
                    return None

                availability_data = cache_data.get("availability", {})
                result = availability_data.get(cache_key)

                if result is not None:
                    self._stats["cache_hits"] += 1
                    if self._logger:
                        self._logger.trace(f"Cache hit for {cache_key}")
                else:
                    self._stats["cache_misses"] += 1
                    if self._logger:
                        self._logger.debug(f"Cache miss for {cache_key}")

                return result

        except Exception as e:
            if self._logger:
                self._logger.warning(f"Error getting availability for {cache_key}: {e}")
            self._stats["cache_misses"] += 1
            return None

    def set_availability(self, category: str, key: str, result: Dict[str, Any]) -> bool:
        """
        Set availability data for a categorized key.

        Args:
            category: Category of the availability check (e.g., 'dependency.llm', 'storage')
            key: Specific key within the category (e.g., 'openai', 'csv')
            result: Availability result data to cache

        Returns:
            True if successfully cached, False otherwise
        """
        cache_key = f"{category}.{key}"

        try:
            with self._cache_lock:
                cache_data = self._file_cache.load_cache()
                if not cache_data:
                    cache_data = self._create_new_cache_structure()

                # Update availability data
                if "availability" not in cache_data:
                    cache_data["availability"] = {}

                # Add metadata to result
                enhanced_result = result.copy()
                enhanced_result.update(
                    {
                        "cached_at": datetime.now(timezone.utc).isoformat(),
                        "cache_key": cache_key,
                        "environment_hash": self._env_detector.get_environment_hash(),
                    }
                )

                cache_data["availability"][cache_key] = enhanced_result
                cache_data["last_updated"] = datetime.now(timezone.utc).isoformat()

                # Save to persistent storage
                success = self._file_cache.save_cache(cache_data)

                if success:
                    self._stats["cache_sets"] += 1
                    if self._logger:
                        self._logger.debug(f"Cached availability for {cache_key}")
                else:
                    if self._logger:
                        self._logger.warning(
                            f"Failed to cache availability for {cache_key}"
                        )

                return success

        except Exception as e:
            if self._logger:
                self._logger.warning(f"Error setting availability for {cache_key}: {e}")
            return False

    def invalidate_cache(
        self, category: Optional[str] = None, key: Optional[str] = None
    ) -> None:
        """
        Invalidate cache for specific category/key or all cache.

        Args:
            category: Optional category to invalidate (e.g., 'dependency.llm')
            key: Optional specific key within category (e.g., 'openai')
                If category is provided but key is None, invalidates entire category
                If both are None, invalidates entire cache
        """
        try:
            with self._invalidation_lock:
                if category is None and key is None:
                    # Invalidate entire cache
                    self._clear_entire_cache()
                    self._stats["invalidations"] += 1
                    if self._logger:
                        self._logger.info("Invalidated entire availability cache")

                elif key is None:
                    # Invalidate entire category
                    self._invalidate_category(category)
                    self._stats["invalidations"] += 1
                    if self._logger:
                        self._logger.info(f"Invalidated cache category: {category}")

                else:
                    # Invalidate specific key
                    cache_key = f"{category}.{key}"
                    self._invalidate_specific_key(cache_key)
                    self._stats["invalidations"] += 1
                    if self._logger:
                        self._logger.info(f"Invalidated cache key: {cache_key}")

        except Exception as e:
            if self._logger:
                self._logger.error(f"Error during cache invalidation: {e}")

    def register_config_file(self, config_file_path: Union[str, Path]) -> None:
        """
        Register a configuration file for automatic invalidation monitoring.

        Args:
            config_file_path: Path to configuration file to monitor
        """
        try:
            self._config_detector.register_config_file(config_file_path)
            if self._logger:
                self._logger.debug(
                    f"Registered config file for monitoring: {config_file_path}"
                )
        except Exception as e:
            if self._logger:
                self._logger.warning(
                    f"Failed to register config file {config_file_path}: {e}"
                )

    def invalidate_environment_cache(self) -> None:
        """
        Manually invalidate environment cache to trigger fresh environment detection.
        Call this after installing new packages or changing Python environment.
        """
        try:
            self._env_detector.invalidate_environment_cache()
            self.invalidate_cache()  # Clear all cached data
            self._stats["auto_invalidations"] += 1
            if self._logger:
                self._logger.info("Manually invalidated environment cache")
        except Exception as e:
            if self._logger:
                self._logger.error(f"Error invalidating environment cache: {e}")

    def is_initialized(self) -> bool:
        """
        Lightweight check if the cache has been initialized.

        Simply checks if the cache file exists without validating contents.
        This is much faster than full validation and suitable for runtime checks.

        Returns:
            True if cache file exists, False otherwise
        """
        return self._cache_file_path.exists()

    def refresh_cache(self, container) -> None:
        """
        Refresh the availability cache by discovering and validating all providers.

        This delegates to the DependencyCheckerService to do the heavy lifting
        of discovery and validation, then stores results in the cache.

        Args:
            container: DI container to get services from

        Raises:
            Exception: If refresh fails
        """
        try:
            dependency_checker = container.dependency_checker_service()

            # Clear existing cache first
            self.invalidate_cache()

            # Discover and validate LLM providers
            dependency_checker.discover_and_validate_providers("llm", force=True)

            # Discover and validate storage providers
            dependency_checker.discover_and_validate_providers("storage", force=True)

            if self._logger:
                self._logger.info("Successfully refreshed availability cache")

        except Exception as e:
            if self._logger:
                self._logger.error(f"Failed to refresh availability cache: {e}")
            raise

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics and status information.

        Returns:
            Dictionary with cache statistics and health info
        """
        try:
            cache_data = self._file_cache.load_cache()

            basic_stats = {
                "cache_file_path": str(self._cache_file_path),
                "cache_exists": cache_data is not None,
                "auto_invalidation_enabled": self._auto_invalidation_enabled,
                "performance": self._stats.copy(),
            }

            if cache_data:
                availability_data = cache_data.get("availability", {})

                # Count entries by category
                category_counts = {}
                for cache_key in availability_data.keys():
                    parts = cache_key.split(".", 1)
                    if len(parts) >= 1:
                        category = parts[0]
                        if len(parts) >= 2 and "." in parts[1]:
                            # Handle nested categories like dependency.llm
                            subcategory = parts[1].split(".", 1)[0]
                            category = f"{category}.{subcategory}"

                        category_counts[category] = category_counts.get(category, 0) + 1

                basic_stats.update(
                    {
                        "cache_version": cache_data.get("cache_version"),
                        "last_updated": cache_data.get("last_updated"),
                        "total_entries": len(availability_data),
                        "categories": category_counts,
                        "environment_hash": self._env_detector.get_environment_hash(),
                    }
                )

            return basic_stats

        except Exception as e:
            return {
                "error": str(e),
                "cache_file_path": str(self._cache_file_path),
                "performance": self._stats.copy(),
            }

    def enable_auto_invalidation(self, enabled: bool = True) -> None:
        """
        Enable or disable automatic cache invalidation.

        Args:
            enabled: True to enable automatic invalidation, False to disable
        """
        self._auto_invalidation_enabled = enabled
        if self._logger:
            status = "enabled" if enabled else "disabled"
            self._logger.info(f"Automatic cache invalidation {status}")

    # Private helper methods

    @property
    def _should_auto_invalidate(self) -> bool:
        """Check if automatic invalidation should be triggered."""
        if not self._auto_invalidation_enabled:
            return False

        try:
            # Check environment changes
            current_env_hash = self._env_detector.get_environment_hash()
            if (
                self._last_env_hash is not None
                and current_env_hash != self._last_env_hash
            ):
                return True

            # Check config file changes
            if self._config_detector.has_config_changed():
                return True

            return False

        except:
            raise

    def _perform_auto_invalidation(self) -> None:
        """Perform automatic cache invalidation."""
        try:
            self._clear_entire_cache()

            # Update tracking
            self._last_env_hash = self._env_detector.get_environment_hash()
            self._config_detector.update_config_tracking()

            self._stats["auto_invalidations"] += 1
            if self._logger:
                self._logger.info(
                    "Performed automatic cache invalidation due to environment/config changes"
                )

        except Exception as e:
            if self._logger:
                self._logger.error(f"Error during automatic invalidation: {e}")

    def _create_new_cache_structure(self) -> Dict[str, Any]:
        """Create new cache data structure."""
        return {
            "cache_version": "2.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "environment_hash": self._env_detector.get_environment_hash(),
            "availability": {},
        }

    def _clear_entire_cache(self) -> None:
        """Clear entire cache file."""
        try:
            if self._cache_file_path.exists():
                self._cache_file_path.unlink()

            # Clear memory cache
            self._file_cache._memory_cache = None

        except Exception as e:
            if self._logger:
                self._logger.warning(f"Error clearing cache file: {e}")

    def _invalidate_category(self, category: str) -> None:
        """Invalidate all entries in a specific category."""
        try:
            cache_data = self._file_cache.load_cache()
            if not cache_data:
                return

            availability_data = cache_data.get("availability", {})

            # Remove all keys that start with the category
            keys_to_remove = [
                key
                for key in availability_data.keys()
                if key.startswith(f"{category}.")
            ]

            for key in keys_to_remove:
                del availability_data[key]

            cache_data["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._file_cache.save_cache(cache_data)

        except Exception as e:
            if self._logger:
                self._logger.warning(f"Error invalidating category {category}: {e}")

    def _invalidate_specific_key(self, cache_key: str) -> None:
        """Invalidate a specific cache key."""
        try:
            cache_data = self._file_cache.load_cache()
            if not cache_data:
                return

            availability_data = cache_data.get("availability", {})

            if cache_key in availability_data:
                del availability_data[cache_key]
                cache_data["last_updated"] = datetime.now(timezone.utc).isoformat()
                self._file_cache.save_cache(cache_data)

        except Exception as e:
            if self._logger:
                self._logger.warning(f"Error invalidating key {cache_key}: {e}")
