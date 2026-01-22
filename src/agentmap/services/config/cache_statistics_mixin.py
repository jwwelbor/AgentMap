"""Cache statistics mixin for the availability cache service."""

from typing import Any, Dict


class CacheStatisticsMixin:
    def _initialize_stats(self) -> Dict[str, int]:
        return {
            "cache_hits": 0,
            "cache_misses": 0,
            "cache_sets": 0,
            "invalidations": 0,
            "auto_invalidations": 0,
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        try:
            cache_data = self._file_cache.load_cache()
            stats = {
                "cache_file_path": str(self._cache_file_path),
                "cache_exists": cache_data is not None,
                "auto_invalidation_enabled": self._auto_invalidation_enabled,
                "performance": self._stats.copy(),
            }
            if cache_data:
                availability_data = cache_data.get("availability", {})
                category_counts = {}
                for cache_key in availability_data.keys():
                    parts = cache_key.split(".", 1)
                    category = (
                        parts[0]
                        if len(parts) == 1
                        else (
                            f"{parts[0]}.{parts[1].split('.', 1)[0]}"
                            if "." in parts[1]
                            else parts[0]
                        )
                    )
                    category_counts[category] = category_counts.get(category, 0) + 1
                stats.update(
                    {
                        "cache_version": cache_data.get("cache_version"),
                        "last_updated": cache_data.get("last_updated"),
                        "total_entries": len(availability_data),
                        "categories": category_counts,
                        "environment_hash": self._env_detector.get_environment_hash(),
                    }
                )
            return stats
        except Exception as e:
            return {
                "error": str(e),
                "cache_file_path": str(self._cache_file_path),
                "performance": self._stats.copy(),
            }
