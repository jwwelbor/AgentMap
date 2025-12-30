"""
Cache invalidation mixin for the availability cache service.
"""

from datetime import datetime, timezone
from typing import Optional


class CacheInvalidationMixin:
    """Mixin providing cache invalidation methods for AvailabilityCacheService."""

    def invalidate_cache(self, category: Optional[str] = None, key: Optional[str] = None) -> None:
        """Invalidate cache for specific category/key or all cache."""
        try:
            with self._invalidation_lock:
                if category is None and key is None:
                    self._clear_entire_cache()
                    self._stats["invalidations"] += 1
                    if self._logger:
                        self._logger.info("Invalidated entire availability cache")
                elif key is None:
                    self._invalidate_category(category)
                    self._stats["invalidations"] += 1
                    if self._logger:
                        self._logger.info(f"Invalidated cache category: {category}")
                else:
                    cache_key = f"{category}.{key}"
                    self._invalidate_specific_key(cache_key)
                    self._stats["invalidations"] += 1
                    if self._logger:
                        self._logger.info(f"Invalidated cache key: {cache_key}")
        except Exception as e:
            if self._logger:
                self._logger.error(f"Error during cache invalidation: {e}")

    def invalidate_environment_cache(self) -> None:
        """Manually invalidate environment cache."""
        try:
            self._env_detector.invalidate_environment_cache()
            self.invalidate_cache()
            self._stats["auto_invalidations"] += 1
            if self._logger:
                self._logger.info("Manually invalidated environment cache")
        except Exception as e:
            if self._logger:
                self._logger.error(f"Error invalidating environment cache: {e}")

    def _perform_auto_invalidation(self) -> None:
        """Perform automatic cache invalidation."""
        try:
            self._clear_entire_cache()
            self._last_env_hash = self._env_detector.get_environment_hash()
            self._config_detector.update_config_tracking()
            self._stats["auto_invalidations"] += 1
            if self._logger:
                self._logger.info("Performed automatic cache invalidation")
        except Exception as e:
            if self._logger:
                self._logger.error(f"Error during automatic invalidation: {e}")

    def _clear_entire_cache(self) -> None:
        """Clear entire cache file."""
        try:
            if self._cache_file_path.exists():
                self._cache_file_path.unlink()
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
            keys_to_remove = [key for key in availability_data.keys() if key.startswith(f"{category}.")]
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
