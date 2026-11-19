"""Cache invalidation mixin for the availability cache service."""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from agentmap.services.config.availability_cache import ThreadSafeFileCache
    from agentmap.services.config.change_detectors import (
        ConfigChangeDetector,
        EnvironmentChangeDetector,
    )


class CacheInvalidationMixin:
    _cache_file_path: Path
    _config_detector: ConfigChangeDetector
    _env_detector: EnvironmentChangeDetector
    _file_cache: ThreadSafeFileCache
    _invalidation_lock: AbstractContextManager[Any]
    _last_env_hash: Optional[str]
    _logger: Optional[logging.Logger]
    _stats: Dict[str, int]

    def invalidate_cache(
        self, category: Optional[str] = None, key: Optional[str] = None
    ) -> None:
        try:
            with self._invalidation_lock:
                if key is None:
                    if category is None:
                        self._clear_entire_cache()
                    else:
                        self._invalidate_category(category)
                else:
                    self._invalidate_specific_key(f"{category}.{key}")
                self._stats["invalidations"] += 1
        except Exception as e:
            if self._logger:
                self._logger.error(f"Error during cache invalidation: {e}")

    def invalidate_environment_cache(self) -> None:
        self._env_detector.invalidate_environment_cache()
        self.invalidate_cache()
        self._stats["auto_invalidations"] += 1

    def _perform_auto_invalidation(self) -> None:
        self._clear_entire_cache()
        self._last_env_hash = self._env_detector.get_environment_hash()
        self._config_detector.update_config_tracking()
        self._stats["auto_invalidations"] += 1

    def _clear_entire_cache(self) -> None:
        if self._cache_file_path.exists():
            self._cache_file_path.unlink()
        self._file_cache._memory_cache = None

    def _invalidate_category(self, category: str) -> None:
        cache_data = self._file_cache.load_cache()
        if not cache_data:
            return
        availability_data = cache_data.get("availability", {})
        for key in [
            k for k in availability_data.keys() if k.startswith(f"{category}.")
        ]:
            del availability_data[key]
        cache_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._file_cache.save_cache(cache_data)

    def _invalidate_specific_key(self, cache_key: str) -> None:
        cache_data = self._file_cache.load_cache()
        if cache_data and cache_key in cache_data.get("availability", {}):
            del cache_data["availability"][cache_key]
            cache_data["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._file_cache.save_cache(cache_data)
