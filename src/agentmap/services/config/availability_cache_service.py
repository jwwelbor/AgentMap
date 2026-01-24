"""Unified Availability Cache Service for AgentMap."""

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agentmap.services.config.availability_cache import ThreadSafeFileCache
from agentmap.services.config.cache_invalidation_mixin import CacheInvalidationMixin
from agentmap.services.config.cache_statistics_mixin import CacheStatisticsMixin
from agentmap.services.config.change_detectors import (
    ConfigChangeDetector,
    EnvironmentChangeDetector,
)

__all__ = [
    "AvailabilityCacheService",
]


class AvailabilityCacheService(CacheInvalidationMixin, CacheStatisticsMixin):
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
        self._cache_file_path = Path(cache_file_path)
        self._logger = logger
        self._file_cache = ThreadSafeFileCache(self._cache_file_path, logger)
        self._env_detector = EnvironmentChangeDetector()
        self._config_detector = ConfigChangeDetector()
        self._cache_lock = threading.RLock()
        self._invalidation_lock = threading.Lock()
        self._last_env_hash: Optional[str] = None
        self._auto_invalidation_enabled = False
        self._stats = self._initialize_stats()

    def get_availability(self, category: str, key: str) -> Optional[Dict[str, Any]]:
        cache_key = f"{category}.{key}"
        try:
            with self._cache_lock:
                if not self._cache_file_path.exists():
                    from agentmap.exceptions.service_exceptions import (
                        CacheNotFoundError,
                    )

                    raise CacheNotFoundError(
                        f"Availability cache not found at {self._cache_file_path}."
                    )
                cache_data = self._file_cache.load_cache()
                if not cache_data:
                    self._stats["cache_misses"] += 1
                    return None
                result = cache_data.get("availability", {}).get(cache_key)
                self._stats["cache_hits" if result else "cache_misses"] += 1
                return result
        except Exception:
            self._stats["cache_misses"] += 1
            return None

    def set_availability(self, category: str, key: str, result: Dict[str, Any]) -> bool:
        cache_key = f"{category}.{key}"
        try:
            with self._cache_lock:
                cache_data = (
                    self._file_cache.load_cache() or self._create_new_cache_structure()
                )
                if "availability" not in cache_data:
                    cache_data["availability"] = {}
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
                if self._file_cache.save_cache(cache_data):
                    self._stats["cache_sets"] += 1
                    return True
                return False
        except Exception:
            return False

    def register_config_file(self, config_file_path: Union[str, Path]) -> None:
        self._config_detector.register_config_file(config_file_path)

    def is_initialized(self) -> bool:
        return self._cache_file_path.exists()

    def refresh_cache(self, container) -> None:
        dependency_checker = container.dependency_checker_service()
        self.invalidate_cache()
        dependency_checker.discover_and_validate_providers("llm", force=True)
        dependency_checker.discover_and_validate_providers("storage", force=True)

    def enable_auto_invalidation(self, enabled: bool = True) -> None:
        self._auto_invalidation_enabled = enabled

    @property
    def _should_auto_invalidate(self) -> bool:
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

        except Exception:
            # If we can't check for invalidation, re-raise to prevent silent failures
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
        return {
            "cache_version": "2.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "environment_hash": self._env_detector.get_environment_hash(),
            "availability": {},
        }
