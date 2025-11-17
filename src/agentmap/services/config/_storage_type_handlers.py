# agentmap/services/config/_storage_type_handlers.py
"""
Internal module for storage type-specific logic in StorageConfigService.

This module handles storage type-specific operations including:
- Checking if storage types are enabled
- Retrieving storage type configurations
- Provider-specific configuration retrieval
"""
import logging
from typing import Any, Dict, Optional


class StorageTypeHandlers:
    """
    Handles storage type-specific logic and configuration retrieval.

    This class encapsulates logic for different storage types (CSV, Vector, KV,
    JSON, Blob, File) and provides a unified interface for checking availability
    and retrieving configurations.
    """

    def __init__(
        self,
        config_data: Dict[str, Any],
        config_service,
        cache_manager,
        path_resolver,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the storage type handlers.

        Args:
            config_data: The storage configuration data dictionary
            config_service: ConfigService instance for value lookups
            cache_manager: AvailabilityCacheManager instance for caching
            path_resolver: PathResolver instance for path operations
            logger: Logger instance for debug messages
        """
        self._config_data = config_data
        self._config_service = config_service
        self._cache_manager = cache_manager
        self._path_resolver = path_resolver
        self._logger = logger or logging.getLogger(__name__)

    def is_csv_storage_enabled(self) -> bool:
        """
        Check if CSV storage is configured and enabled.

        Returns:
            True if CSV storage is enabled and configured correctly.
        """
        # Try cache first
        cached_result = self._cache_manager.get_cached_availability("csv")
        if cached_result:
            self._logger.debug("Using cached availability for CSV storage")
            return cached_result.get("enabled", False)

        # Fallback to direct config check
        try:
            csv_config = self._config_data.get("csv", {})
            if not isinstance(csv_config, dict):
                enabled = False
            elif csv_config.get("enabled") is False:
                enabled = False
            else:
                # Check if we have either base_directory or default_directory configured
                has_base = bool(self._path_resolver.get_base_directory())
                has_default = bool(csv_config.get("default_directory"))
                enabled = has_base or has_default

            # Cache the result
            result = self._cache_manager.create_cache_result(
                enabled=enabled,
                last_error=(
                    None
                    if enabled
                    else "CSV storage not properly configured - missing base_directory or default_directory"
                ),
                config_present=isinstance(csv_config, dict),
            )
            self._cache_manager.set_cached_availability("csv", result)

            return enabled
        except Exception:
            return False

    def is_csv_auto_create_enabled(self) -> bool:
        """
        Check if CSV auto-creation is enabled for write operations.

        Returns:
            True if CSV auto-creation is enabled, False otherwise
        """
        csv_config = self._config_data.get("csv", {})
        return csv_config.get("auto_create_files", False)

    def is_vector_storage_enabled(self) -> bool:
        """
        Check if vector storage is available and enabled.

        Returns:
            True if vector storage is configured and enabled.
        """
        # Try cache first
        cached_result = self._cache_manager.get_cached_availability("vector")
        if cached_result:
            self._logger.debug("Using cached availability for vector storage")
            return cached_result.get("enabled", False)

        # Fallback to direct config check
        try:
            vector_config = self._config_data.get("vector", {})
            if not isinstance(vector_config, dict):
                enabled = False
            elif vector_config.get("enabled") is False:
                enabled = False
            elif not vector_config.get("default_directory"):
                enabled = False
            else:
                enabled = True

            # Cache the result
            result = self._cache_manager.create_cache_result(
                enabled=enabled,
                last_error=(
                    None if enabled else "Vector storage not properly configured"
                ),
                config_present=isinstance(vector_config, dict),
            )
            self._cache_manager.set_cached_availability("vector", result)

            return enabled
        except Exception:
            return False

    def is_kv_storage_enabled(self) -> bool:
        """
        Check if key-value storage is available and enabled.

        Returns:
            True if key-value storage is configured and enabled.
        """
        # Try cache first
        cached_result = self._cache_manager.get_cached_availability("kv")
        if cached_result:
            self._logger.debug("Using cached availability for KV storage")
            return cached_result.get("enabled", False)

        # Fallback to direct config check
        try:
            kv_config = self._config_data.get("kv", {})
            if not isinstance(kv_config, dict):
                enabled = False
            elif kv_config.get("enabled") is False:
                enabled = False
            elif not kv_config.get("default_directory"):
                enabled = False
            else:
                enabled = True

            # Cache the result
            result = self._cache_manager.create_cache_result(
                enabled=enabled,
                last_error=(
                    None if enabled else "KV storage not properly configured"
                ),
                config_present=isinstance(kv_config, dict),
            )
            self._cache_manager.set_cached_availability("kv", result)

            return enabled
        except Exception:
            return False

    def is_json_storage_enabled(self) -> bool:
        """
        Check if JSON storage is configured and enabled.

        JSON storage is always enabled for system usage but respects user configuration
        and follows caching pattern for consistency with other storage types.

        Returns:
            True if JSON storage is enabled (always True for system needs).
        """
        # Try cache first
        cached_result = self._cache_manager.get_cached_availability("json")
        if cached_result:
            self._logger.debug("Using cached availability for JSON storage")
            return cached_result.get("enabled", False)

        # Fallback to direct config check
        try:
            json_config = self._config_data.get("json", {})

            # For JSON storage: always enabled for system, but check user config
            if not isinstance(json_config, dict):
                enabled = True
                last_error = None
            elif json_config.get("enabled") is False:
                enabled = True  # Always True for system functionality
                last_error = None
            else:
                enabled = True
                last_error = None

            # Cache the result
            result = self._cache_manager.create_cache_result(
                enabled=enabled,
                last_error=last_error,
                config_present=isinstance(json_config, dict),
            )
            self._cache_manager.set_cached_availability("json", result)

            return enabled
        except Exception:
            # JSON storage must always be available for system functionality
            return True

    def is_blob_storage_enabled(self) -> bool:
        """
        Check if blob storage is available and enabled.

        Returns:
            True if blob storage is configured and enabled.
        """
        # Try cache first
        cached_result = self._cache_manager.get_cached_availability("blob")
        if cached_result:
            self._logger.debug("Using cached availability for blob storage")
            return cached_result.get("enabled", False)

        # Fallback to direct config check
        try:
            blob_config = self._config_data.get("blob", {})
            if not isinstance(blob_config, dict):
                enabled = False
            elif blob_config.get("enabled") is False:
                enabled = False
            elif not blob_config.get("default_directory"):
                enabled = False
            else:
                enabled = True

            # Cache the result
            result = self._cache_manager.create_cache_result(
                enabled=enabled,
                last_error=(
                    None if enabled else "Blob storage not properly configured"
                ),
                config_present=isinstance(blob_config, dict),
            )
            self._cache_manager.set_cached_availability("blob", result)

            return enabled
        except Exception:
            return False

    def is_provider_configured(self, provider: str) -> bool:
        """
        Check if a specific storage provider is configured.

        Args:
            provider: Storage provider name (e.g., "firebase", "mongodb", "local")

        Returns:
            True if provider is configured with valid settings
        """
        provider_config = self._config_data.get(provider, {})
        return bool(provider_config) and provider_config.get("enabled", True)

    def is_storage_type_enabled(self, storage_type: str) -> bool:
        """
        Check if a storage type is enabled.

        Args:
            storage_type: Type of storage ("csv", "vector", "kv", "json", "blob", "file")

        Returns:
            True if storage type is enabled
        """
        if storage_type == "csv":
            return self.is_csv_storage_enabled()
        elif storage_type == "vector":
            return self.is_vector_storage_enabled()
        elif storage_type == "kv":
            return self.is_kv_storage_enabled()
        elif storage_type == "json":
            return True  # required and must always be enabled for app to function
        elif storage_type == "blob":
            return self.is_blob_storage_enabled()
        elif storage_type == "file":
            # File storage follows same pattern as CSV/JSON
            try:
                config = self._config_data.get(storage_type, {})
                if not isinstance(config, dict):
                    return False
                # Check if explicitly disabled first
                if config.get("enabled") is False:
                    return False
                # Must have a default_directory to be considered configured
                if not config.get("default_directory"):
                    return False
                return True
            except Exception:
                return False
        else:
            # Generic storage types
            config = self._config_data.get(storage_type, {})
            if not isinstance(config, dict):
                return False
            # Check if explicitly disabled first
            if config.get("enabled") is False:
                return False
            # For other storage types, just check if config exists and not disabled
            return bool(config)
