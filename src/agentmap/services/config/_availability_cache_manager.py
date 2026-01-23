# agentmap/services/config/_availability_cache_manager.py
"""
Internal module for managing availability caching in StorageConfigService.

This module provides a clean separation of concerns for cache management,
allowing the main service to delegate caching operations.
"""
import logging
from typing import Any, Dict, Optional


class AvailabilityCacheManager:
    """
    Manages availability caching for storage configuration.

    This class encapsulates all cache-related operations, providing a clean
    interface for the StorageConfigService to interact with the availability
    cache service.
    """

    def __init__(self, availability_cache_service=None, logger: Optional[logging.Logger] = None):
        """
        Initialize the cache manager.

        Args:
            availability_cache_service: Optional unified availability cache service
            logger: Logger instance for debug messages
        """
        self._availability_cache_service = availability_cache_service
        self._logger = logger or logging.getLogger(__name__)

    def set_logger(self, logger: logging.Logger):
        """
        Set the logger instance.

        Args:
            logger: Logger instance to use
        """
        self._logger = logger

    def get_cached_availability(self, storage_type: str) -> Optional[Dict[str, Any]]:
        """
        Get cached availability using unified cache service.

        Args:
            storage_type: Storage type to check ("csv", "vector", "kv", "json", "blob")

        Returns:
            Cached availability data or None if not found/invalid
        """
        if not self._availability_cache_service:
            return None

        try:
            return self._availability_cache_service.get_availability(
                "storage", storage_type.lower()
            )
        except Exception as e:
            self._logger.debug(f"Cache lookup failed for storage.{storage_type}: {e}")
            return None

    def set_cached_availability(
        self, storage_type: str, result: Dict[str, Any]
    ) -> bool:
        """
        Set cached availability using unified cache service.

        Args:
            storage_type: Storage type ("csv", "vector", "kv", "json", "blob")
            result: Availability result data to cache

        Returns:
            True if successfully cached, False otherwise
        """
        if not self._availability_cache_service:
            return False

        try:
            return self._availability_cache_service.set_availability(
                "storage", storage_type.lower(), result
            )
        except Exception as e:
            self._logger.debug(f"Cache set failed for storage.{storage_type}: {e}")
            return False

    def create_cache_result(
        self,
        enabled: bool,
        last_error: Optional[str] = None,
        config_present: bool = True,
        warnings: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Create a standardized cache result dictionary.

        Args:
            enabled: Whether the storage type is enabled
            last_error: Last error message if any
            config_present: Whether configuration is present
            warnings: List of warning messages

        Returns:
            Standardized cache result dictionary
        """
        return {
            "enabled": enabled,
            "validation_passed": enabled,
            "last_error": last_error,
            "checked_at": "direct_config_check",
            "warnings": warnings or [],
            "performance_metrics": {"validation_duration": 0.0},
            "validation_results": {"config_present": config_present},
        }
