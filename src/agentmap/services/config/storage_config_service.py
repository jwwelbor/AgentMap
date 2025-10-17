# agentmap/config/storage_config.py
"""
Domain service for storage configuration with exception-based failure handling.

Provides business logic layer for storage configuration, using ConfigService
for infrastructure concerns while implementing graceful degradation through
exception-based failure when storage configuration is unavailable.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from agentmap.exceptions.service_exceptions import (
    StorageConfigurationNotAvailableException,
)
from agentmap.services.config.config_service import ConfigService


class StorageConfigService:
    """
    Domain service for storage configuration with business logic and exception handling.

    This service provides business logic for storage configuration:
    - Loads storage config file via ConfigService
    - Validates storage config availability and raises exceptions on failure
    - Provides storage-specific business logic methods
    - Implements bootstrap logging pattern with logger replacement
    - Enables graceful degradation when storage config is unavailable

    Unlike AppConfigService which always works with defaults, this service
    fails fast with exceptions when storage configuration is missing.
    """

    def __init__(
        self,
        config_service: ConfigService,
        storage_config_path: Optional[Union[str, Path]],
        availability_cache_service=None,
    ):
        """
        Initialize StorageConfigService with storage configuration path.

        Args:
            config_service: ConfigService instance for infrastructure operations
            storage_config_path: Path to storage configuration file. Cannot be None.
            availability_cache_service: Optional unified availability cache service

        Raises:
            StorageConfigurationNotAvailableException: If config path is None,
                file doesn't exist, or file cannot be parsed.
        """
        self._config_service = config_service
        self._config_data = None
        self._logger = None
        self._storage_config_path = storage_config_path
        self._availability_cache_service = availability_cache_service

        # Setup bootstrap logging - will be replaced later by DI
        self._setup_bootstrap_logging()

        # Validate and load storage configuration (fail fast on any issue)
        self._validate_and_load_config(storage_config_path)

    def _setup_bootstrap_logging(self):
        """Set up bootstrap logger for config loading before real logging is available."""
        # Only set up basic config if no handlers exist to avoid conflicts
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=os.environ.get("AGENTMAP_CONFIG_LOG_LEVEL", "INFO").upper(),
                format="(STORAGE-CONFIG-BOOTSTRAP) [%(asctime)s] %(levelname)s: %(message)s",
            )
        self._logger = logging.getLogger("bootstrap.storage_config")
        self._logger.debug("[StorageConfigService] Bootstrap logger initialized")

    def _validate_and_load_config(
        self, storage_config_path: Optional[Union[str, Path]]
    ):
        """Validate storage config path and load configuration."""
        # Fail if no storage config path provided
        if storage_config_path is None:
            error_msg = "Storage config path not specified. Add 'storage_config_path: path/to/storage.yaml' to your main configuration."
            self._logger.error(f"[StorageConfigService] {error_msg}")
            raise StorageConfigurationNotAvailableException(error_msg)

        storage_path = Path(storage_config_path)
        self._logger.info(
            f"[StorageConfigService] Loading storage configuration from: {storage_path}"
        )

        # Fail if storage config file doesn't exist
        if not storage_path.exists():
            error_msg = f"Storage config file not found: {storage_path}"
            self._logger.error(f"[StorageConfigService] {error_msg}")
            raise StorageConfigurationNotAvailableException(error_msg)

        # Try to load storage config file
        try:
            self._config_data = self._config_service.load_config(storage_config_path)
            self._logger.info(
                "[StorageConfigService] Storage configuration loaded successfully"
            )

            # Log available storage sections for visibility
            if self._config_data:
                sections = list(self._config_data.keys())
                self._logger.info(
                    f"[StorageConfigService] Available storage sections: {sections}"
                )

        except Exception as e:
            error_msg = f"Failed to load storage config from {storage_path}: {e}"
            self._logger.error(f"[StorageConfigService] {error_msg}")
            raise StorageConfigurationNotAvailableException(error_msg) from e

    def replace_logger(self, logger: logging.Logger):
        """
        Replace bootstrap logger with real logger once logging service is online.

        Args:
            logger: Real logger instance from LoggingService
        """
        if logger and self._logger:
            # Clean up bootstrap logger handlers
            for handler in list(self._logger.handlers):
                self._logger.removeHandler(handler)
            self._logger.propagate = False

            # Switch to real logger
            self._logger = logger
            self._logger.debug(
                "[StorageConfigService] Replaced bootstrap logger with real logger"
            )

    # Storage-specific business logic methods
    def get_csv_config(self) -> Dict[str, Any]:
        """
        Get CSV storage configuration.

        Returns:
            Dictionary containing CSV storage configuration
        """
        return self._config_data.get("csv", {})

    def get_vector_config(self) -> Dict[str, Any]:
        """
        Get vector storage configuration.

        Returns:
            Dictionary containing vector storage configuration
        """
        return self._config_data.get("vector", {})

    def get_kv_config(self) -> Dict[str, Any]:
        """
        Get key-value storage configuration.

        Returns:
            Dictionary containing key-value storage configuration
        """
        return self._config_data.get("kv", {})

    def get_json_config(self) -> Dict[str, Any]:
        """
        Get JSON storage configuration.

        Returns:
            Dictionary containing JSON storage configuration
        """
        return self._config_data.get("json", {})

    def get_blob_config(self) -> Dict[str, Any]:
        """
        Get blob storage configuration.

        Returns:
            Dictionary containing blob storage configuration
        """
        return self._config_data.get("blob", {})

    def get_file_config(self) -> Dict[str, Any]:
        """
        Get file storage configuration.

        Returns:
            Dictionary containing file storage configuration
        """
        return self._config_data.get("file", {})

    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get configuration for a specific storage provider.

        Args:
            provider: Storage provider name (e.g., "csv", "vector", "firebase", "mongodb")

        Returns:
            Dictionary containing provider-specific configuration
        """
        return self._config_data.get(provider, {})

    def get_value(self, path: str, default: Any = None) -> Any:
        """
        Get value by dot notation from storage configuration.

        Args:
            path: Dot-separated path to configuration value (e.g., "csv.collections.users")
            default: Default value to return if path not found

        Returns:
            Configuration value or default if not found
        """
        return self._config_service.get_value_from_config(
            self._config_data, path, default
        )

    def get_collection_config(
        self, storage_type: str, collection_name: str
    ) -> Dict[str, Any]:
        """
        Get configuration for a specific collection within a storage type.

        Args:
            storage_type: Type of storage ("csv", "vector", "kv")
            collection_name: Name of the collection

        Returns:
            Dictionary containing collection-specific configuration
        """
        return self.get_value(f"{storage_type}.collections.{collection_name}", {})

    def get_default_directory(self, storage_type: str) -> str:
        """
        Get default directory for a storage type.

        Args:
            storage_type: Type of storage ("csv", "vector", "kv")

        Returns:
            Default directory path for the storage type
        """
        return self.get_value(
            f"{storage_type}.default_directory", f"data/{storage_type}"
        )

    def get_default_provider(self, storage_type: str) -> str:
        """
        Get default provider for a storage type.

        Args:
            storage_type: Type of storage ("vector", "kv")

        Returns:
            Default provider name for the storage type
        """
        return self.get_value(f"{storage_type}.default_provider", "local")

    def list_collections(self, storage_type: str) -> list[str]:
        """
        List all configured collections for a storage type.

        Args:
            storage_type: Type of storage ("csv", "vector", "kv")

        Returns:
            List of collection names
        """
        collections_config = self.get_value(f"{storage_type}.collections", {})
        return list(collections_config.keys())

    def has_collection(self, storage_type: str, collection_name: str) -> bool:
        """
        Check if a collection is configured for a storage type.

        Args:
            storage_type: Type of storage ("csv", "vector", "kv")
            collection_name: Name of the collection

        Returns:
            True if collection is configured, False otherwise
        """
        return collection_name in self.list_collections(storage_type)

    def get_storage_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the loaded storage configuration for debugging.

        Returns:
            Dictionary with storage configuration summary
        """
        if self._config_data is None:
            return {"status": "not_loaded"}

        summary = {
            "status": "loaded",
            "storage_types": list(self._config_data.keys()),
            "storage_type_count": len(self._config_data),
        }

        # Add collection counts for each storage type
        for storage_type in ["csv", "vector", "kv", "json"]:
            if storage_type in self._config_data:
                collections = self.list_collections(storage_type)
                summary[f"{storage_type}_collections"] = collections
                summary[f"{storage_type}_collection_count"] = len(collections)

        # Add blob storage information if configured
        if "blob" in self._config_data:
            blob_config = self._config_data["blob"]
            if isinstance(blob_config, dict):
                providers = blob_config.get("providers", {})
                summary["blob_providers"] = (
                    list(providers.keys()) if isinstance(providers, dict) else []
                )
                summary["blob_provider_count"] = (
                    len(providers) if isinstance(providers, dict) else 0
                )
                summary["blob_default_provider"] = blob_config.get("default_provider")

        return summary

    # Provider-specific named methods following configuration patterns
    def get_firebase_config(self) -> Dict[str, Any]:
        """
        Get Firebase storage configuration.

        Returns:
            Dictionary containing Firebase storage configuration
        """
        return self.get_provider_config("firebase")

    def get_mongodb_config(self) -> Dict[str, Any]:
        """
        Get MongoDB storage configuration.

        Returns:
            Dictionary containing MongoDB storage configuration
        """
        return self.get_provider_config("mongodb")

    def get_supabase_config(self) -> Dict[str, Any]:
        """
        Get Supabase storage configuration.

        Returns:
            Dictionary containing Supabase storage configuration
        """
        return self.get_provider_config("supabase")

    def get_local_config(self) -> Dict[str, Any]:
        """
        Get local storage configuration.

        Returns:
            Dictionary containing local storage configuration
        """
        return self.get_provider_config("local")

    def get_json_provider_config(self) -> Dict[str, Any]:
        """
        Get JSON provider configuration.

        Returns:
            Dictionary containing JSON provider configuration
        """
        return self.get_provider_config("json")

    def get_blob_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get blob storage provider configuration for specific providers.

        Args:
            provider: Blob storage provider name ("azure", "s3", "gcs", "file")

        Returns:
            Dictionary containing blob provider-specific configuration
        """
        blob_config = self.get_blob_config()
        return blob_config.get("providers", {}).get(provider, {})

    def _get_cached_availability(self, storage_type: str) -> Optional[Dict[str, Any]]:
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

    def _set_cached_availability(
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

    # Configuration hierarchy helper methods
    def get_base_directory(self) -> str:
        """
        Get the base storage directory that all storage types use as their root.

        Returns:
            Base directory path for all storage operations
        """
        # Check for core.base_directory first (proper YAML structure)
        base_dir = self.get_value("core.base_directory")

        # Ultimate fallback
        return base_dir or "agentmap_data/data"

    def get_storage_type_directory(self, storage_type: str) -> str:
        """
        Get the directory name for a specific storage type within the base directory.

        Args:
            storage_type: Type of storage ("csv", "json", "vector", etc.)

        Returns:
            Directory name for the storage type (defaults to storage_type name)
        """
        config = self.get_value(storage_type, {})
        if isinstance(config, dict):
            # Check for explicit default_directory
            default_dir = config.get("default_directory")
            if default_dir:
                # If it's an absolute path, extract just the directory name
                if os.path.isabs(default_dir):
                    return Path(default_dir).name
                # If it's a relative path with base_directory prefix, extract the suffix
                base_dir = self.get_base_directory()
                if default_dir.startswith(base_dir):
                    return str(Path(default_dir).relative_to(Path(base_dir)))
                return default_dir

        # Default to storage type name
        return storage_type

    def resolve_full_storage_path(self, storage_type: str) -> Path:
        """
        Resolve the full path for a storage type using base_directory/default_directory hierarchy.

        Args:
            storage_type: Type of storage ("csv", "json", "vector", etc.)

        Returns:
            Full resolved path: base_directory/storage_type_directory
        """
        base_dir = self.get_base_directory()
        storage_dir = self.get_storage_type_directory(storage_type)
        return Path(base_dir) / storage_dir

    # Boolean accessor methods following configuration patterns
    def is_csv_storage_enabled(self) -> bool:
        """
        Check if CSV storage is configured and enabled.

        Returns:
            True if CSV storage is enabled and configured correctly.
        """
        # Try cache first
        cached_result = self._get_cached_availability("csv")
        if cached_result:
            self._logger.debug("Using cached availability for CSV storage")
            return cached_result.get("enabled", False)

        # Fallback to direct config check
        try:
            csv_config = self.get_csv_config()
            if not isinstance(csv_config, dict):
                enabled = False
            elif csv_config.get("enabled") is False:
                # Check if explicitly disabled first
                enabled = False
            else:
                # Check if we have either base_directory or default_directory configured
                has_base = bool(self.get_base_directory())
                has_default = bool(csv_config.get("default_directory"))
                enabled = has_base or has_default

            # Cache the result
            result = {
                "enabled": enabled,
                "validation_passed": enabled,
                "last_error": (
                    None
                    if enabled
                    else "CSV storage not properly configured - missing base_directory or default_directory"
                ),
                "checked_at": "direct_config_check",
                "warnings": [],
                "performance_metrics": {"validation_duration": 0.0},
                "validation_results": {"config_present": isinstance(csv_config, dict)},
            }
            self._set_cached_availability("csv", result)

            return enabled
        except Exception:
            return False

    def is_csv_auto_create_enabled(self) -> bool:
        """
        Check if CSV auto-creation is enabled for write operations.

        Returns:
            True if CSV auto-creation is enabled, False otherwise
        """
        csv_config = self.get_csv_config()
        return csv_config.get("auto_create_files", False)

    def is_vector_storage_enabled(self) -> bool:
        """
        Check if vector storage is available and enabled.

        Returns:
            True if vector storage is configured and enabled.
        """
        # Try cache first
        cached_result = self._get_cached_availability("vector")
        if cached_result:
            self._logger.debug("Using cached availability for vector storage")
            return cached_result.get("enabled", False)

        # Fallback to direct config check
        try:
            vector_config = self.get_vector_config()
            if not isinstance(vector_config, dict):
                enabled = False
            elif vector_config.get("enabled") is False:
                # Check if explicitly disabled first
                enabled = False
            elif not vector_config.get("default_directory"):
                # Must have a default_directory to be considered configured
                enabled = False
            else:
                enabled = True

            # Cache the result
            result = {
                "enabled": enabled,
                "validation_passed": enabled,
                "last_error": (
                    None if enabled else "Vector storage not properly configured"
                ),
                "checked_at": "direct_config_check",
                "warnings": [],
                "performance_metrics": {"validation_duration": 0.0},
                "validation_results": {
                    "config_present": isinstance(vector_config, dict)
                },
            }
            self._set_cached_availability("vector", result)

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
        cached_result = self._get_cached_availability("kv")
        if cached_result:
            self._logger.debug("Using cached availability for KV storage")
            return cached_result.get("enabled", False)

        # Fallback to direct config check
        try:
            kv_config = self.get_kv_config()
            if not isinstance(kv_config, dict):
                enabled = False
            elif kv_config.get("enabled") is False:
                # Check if explicitly disabled first
                enabled = False
            elif not kv_config.get("default_directory"):
                # Must have a default_directory to be considered configured
                enabled = False
            else:
                enabled = True

            # Cache the result
            result = {
                "enabled": enabled,
                "validation_passed": enabled,
                "last_error": (
                    None if enabled else "KV storage not properly configured"
                ),
                "checked_at": "direct_config_check",
                "warnings": [],
                "performance_metrics": {"validation_duration": 0.0},
                "validation_results": {"config_present": isinstance(kv_config, dict)},
            }
            self._set_cached_availability("kv", result)

            return enabled
        except Exception:
            return False

    def is_json_storage_enabled(self) -> bool:
        """
        Check if JSON storage is configured and enabled.

        JSON storage is always enabled for system usage but respects user configuration
        and follows caching pattern for consistency with other storage types.

        Returns:
            True if JSON storage is enabled (always True for system needs, but
            may respect user configuration for user-facing operations).
        """
        # Try cache first
        cached_result = self._get_cached_availability("json")
        if cached_result:
            self._logger.debug("Using cached availability for JSON storage")
            return cached_result.get("enabled", False)

        # Fallback to direct config check
        try:
            json_config = self.get_json_config()

            # For JSON storage: always enabled for system, but check user config
            if not isinstance(json_config, dict):
                # No config present - use system default (enabled)
                enabled = True
                last_error = None
            elif json_config.get("enabled") is False:
                # User explicitly disabled - but system still needs JSON, so True
                # Note: This could be handled differently at service layer if needed
                enabled = True  # Always True for system functionality
                last_error = None
            else:
                # Normal case - JSON storage is configured and enabled
                enabled = True
                last_error = None

            # Cache the result
            result = {
                "enabled": enabled,
                "validation_passed": enabled,
                "last_error": last_error,
                "checked_at": "direct_config_check",
                "warnings": [],
                "performance_metrics": {"validation_duration": 0.0},
                "validation_results": {"config_present": isinstance(json_config, dict)},
            }
            self._set_cached_availability("json", result)

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
        cached_result = self._get_cached_availability("blob")
        if cached_result:
            self._logger.debug("Using cached availability for blob storage")
            return cached_result.get("enabled", False)

        # Fallback to direct config check
        try:
            blob_config = self.get_blob_config()
            if not isinstance(blob_config, dict):
                enabled = False
            elif blob_config.get("enabled") is False:
                # Check if explicitly disabled first
                enabled = False
            elif not blob_config.get("default_directory"):
                # Must have a default_directory to be considered configured
                enabled = False
            else:
                enabled = True

            # Cache the result
            result = {
                "enabled": enabled,
                "validation_passed": enabled,
                "last_error": (
                    None if enabled else "Blob storage not properly configured"
                ),
                "checked_at": "direct_config_check",
                "warnings": [],
                "performance_metrics": {"validation_duration": 0.0},
                "validation_results": {"config_present": isinstance(blob_config, dict)},
            }
            self._set_cached_availability("blob", result)

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
        provider_config = self.get_provider_config(provider)
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
            return True  # required and must always enabled for app to function
        elif storage_type == "blob":
            return self.is_blob_storage_enabled()
        elif storage_type == "file":
            # File storage follows same pattern as CSV/JSON
            try:
                config = self.get_value(storage_type, {})
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
            config = self.get_value(storage_type, {})
            if not isinstance(config, dict):
                return False
            # Check if explicitly disabled first
            if config.get("enabled") is False:
                return False
            # For other storage types, just check if config exists and not disabled
            return bool(config)

    # Path accessor methods following configuration patterns
    def get_csv_data_path(self) -> Path:
        """
        Get the CSV data directory path using base_directory/default_directory hierarchy.

        Returns:
            Path to CSV data directory
        """
        data_path = self.resolve_full_storage_path("csv")

        # Business logic: ensure directory exists if enabled
        if self.is_csv_storage_enabled():
            try:
                data_path.mkdir(parents=True, exist_ok=True)
                self._logger.debug(
                    f"[StorageConfigService] CSV data path ensured: {data_path}"
                )
            except Exception as e:
                self._logger.warning(
                    f"[StorageConfigService] Could not create CSV data directory {data_path}: {e}"
                )

        return data_path

    def get_collection_file_path(self, collection_name: str) -> Path:
        """
        Get the full file path for a CSV collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Path to the collection file
        """
        csv_path = self.get_csv_data_path()
        collection_config = self.get_collection_config("csv", collection_name)
        filename = collection_config.get("filename", f"{collection_name}.csv")
        return csv_path / filename

    def get_vector_data_path(self) -> Path:
        """
        Get the vector data directory path using base_directory/default_directory hierarchy.

        Returns:
            Path to vector data directory
        """
        data_path = self.resolve_full_storage_path("vector")

        # Business logic: ensure directory exists if enabled
        if self.is_vector_storage_enabled():
            try:
                data_path.mkdir(parents=True, exist_ok=True)
                self._logger.debug(
                    f"[StorageConfigService] Vector data path ensured: {data_path}"
                )
            except Exception as e:
                self._logger.warning(
                    f"[StorageConfigService] Could not create vector data directory {data_path}: {e}"
                )

        return data_path

    def get_kv_data_path(self) -> Path:
        """
        Get the key-value data directory path using base_directory/default_directory hierarchy.

        Returns:
            Path to key-value data directory
        """
        data_path = self.resolve_full_storage_path("kv")

        # Business logic: ensure directory exists if enabled
        if self.is_kv_storage_enabled():
            try:
                data_path.mkdir(parents=True, exist_ok=True)
                self._logger.debug(
                    f"[StorageConfigService] KV data path ensured: {data_path}"
                )
            except Exception as e:
                self._logger.warning(
                    f"[StorageConfigService] Could not create KV data directory {data_path}: {e}"
                )

        return data_path

    def get_json_data_path(self) -> Path:
        """
        Get the JSON data directory path using base_directory/default_directory hierarchy.

        Returns:
            Path to JSON data directory
        """
        data_path = self.resolve_full_storage_path("json")

        # Business logic: ensure directory exists if enabled
        if self.is_json_storage_enabled():
            try:
                data_path.mkdir(parents=True, exist_ok=True)
                self._logger.debug(
                    f"[StorageConfigService] JSON data path ensured: {data_path}"
                )
            except Exception as e:
                self._logger.warning(
                    f"[StorageConfigService] Could not create JSON data directory {data_path}: {e}"
                )

        return data_path

    def get_json_collection_file_path(self, collection_name: str) -> Path:
        """
        Get the full file path for a JSON collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Path to the collection file
        """
        json_path = self.get_json_data_path()
        collection_config = self.get_collection_config("json", collection_name)
        filename = collection_config.get("filename", f"{collection_name}.json")
        return json_path / filename

    def get_blob_data_path(self) -> Path:
        """
        Get the blob data directory path using base_directory/default_directory hierarchy.

        Returns:
            Path to blob data directory
        """
        data_path = self.resolve_full_storage_path("blob")

        # Business logic: ensure directory exists if enabled
        if self.is_blob_storage_enabled():
            try:
                data_path.mkdir(parents=True, exist_ok=True)
                self._logger.debug(
                    f"[StorageConfigService] Blob data path ensured: {data_path}"
                )
            except Exception as e:
                self._logger.warning(
                    f"[StorageConfigService] Could not create blob data directory {data_path}: {e}"
                )

        return data_path

    # Enhanced validation methods following configuration patterns
    def validate_csv_config(self) -> Dict[str, Any]:
        """
        Validate CSV storage configuration.

        Returns:
            Dictionary with validation status similar to AppConfigService pattern
        """
        warnings = []
        errors = []

        try:
            csv_config = self.get_csv_config()

            # Skip validation if CSV config is not a dictionary (handled by parent validation)
            if not isinstance(csv_config, dict):
                return {
                    "valid": False,
                    "warnings": warnings,
                    "errors": ["CSV configuration is not properly structured"],
                    "summary": {
                        "collections_count": 0,
                        "csv_enabled": False,
                        "data_path": "unknown",
                    },
                }

            # Validate CSV storage is properly enabled
            if not self.is_csv_storage_enabled():
                if csv_config.get("enabled") is False:
                    warnings.append("CSV storage is explicitly disabled")
                elif not csv_config.get("default_directory"):
                    errors.append(
                        "CSV storage requires a default_directory to be configured"
                    )
                else:
                    warnings.append("CSV storage configuration may be incomplete")
            else:
                # Validate directory exists if CSV is enabled
                try:
                    data_path = self.get_csv_data_path()
                    if not data_path.exists():
                        warnings.append(
                            f"CSV data directory does not exist: {data_path}"
                        )
                except Exception as e:
                    warnings.append(f"Could not validate CSV data path: {e}")

            # Validate collections configuration (collections are optional - can be created dynamically)
            collections = csv_config.get("collections", {})
            if isinstance(collections, dict):
                for collection_name, collection_config in collections.items():
                    if not isinstance(collection_config, dict):
                        errors.append(
                            f"CSV collection '{collection_name}' configuration must be a dictionary"
                        )

                    # Check for required filename if file-based
                    if isinstance(collection_config, dict):
                        filename = collection_config.get("filename")
                        if not filename:
                            # Log the auto-generation but don't modify the original config
                            self._logger.debug(
                                f"[StorageConfigService] Would auto-generate filename for collection '{collection_name}': {collection_name}.csv"
                            )
                            # Note: We don't modify the original config to avoid side effects
            elif collections:
                errors.append("CSV collections configuration must be a dictionary")

            # Note: Empty collections is fine - collections can be created dynamically

            return {
                "valid": len(errors) == 0,
                "warnings": warnings,
                "errors": errors,
                "summary": {
                    "collections_count": (
                        len(collections) if isinstance(collections, dict) else 0
                    ),
                    "csv_enabled": self.is_csv_storage_enabled(),
                    "data_path": (
                        str(self.get_csv_data_path())
                        if self.is_csv_storage_enabled()
                        else "not configured"
                    ),
                },
            }
        except Exception as e:
            return {
                "valid": False,
                "warnings": warnings,
                "errors": [f"Error validating CSV configuration: {e}"],
                "summary": {
                    "collections_count": 0,
                    "csv_enabled": False,
                    "data_path": "validation error",
                },
            }

    #         csv_config = self.get_csv_config()

    #         # Skip validation if CSV config is not a dictionary (handled by parent validation)
    #         if not isinstance(csv_config, dict):
    #             return {
    #                 "valid": False,
    #                 "warnings": warnings,
    #                 "errors": ["CSV configuration is not properly structured"],
    #                 "summary": {
    #                     "collections_count": 0,
    #                     "csv_enabled": False,
    #                     "data_path": "unknown",
    #                 },
    #             }

    #         # Validate CSV storage is properly enabled
    #         if not self.is_csv_storage_enabled():
    #             if csv_config.get("enabled") is False:
    #                 warnings.append("CSV storage is explicitly disabled")
    #             elif not csv_config.get("default_directory"):
    #                 errors.append(
    #                     "CSV storage requires a default_directory to be configured"
    #                 )
    #             else:
    #                 warnings.append("CSV storage configuration may be incomplete")
    #         else:
    #             # Validate directory exists if CSV is enabled
    #             try:
    #                 data_path = self.get_csv_data_path()
    #                 if not data_path.exists():
    #                     warnings.append(
    #                         f"CSV data directory does not exist: {data_path}"
    #                     )
    #             except Exception as e:
    #                 warnings.append(f"Could not validate CSV data path: {e}")

    #         # Validate collections configuration (collections are optional - can be created dynamically)
    #         collections = csv_config.get("collections", {})
    #         if isinstance(collections, dict):
    #             for collection_name, collection_config in collections.items():
    #                 if not isinstance(collection_config, dict):
    #                     errors.append(
    #                         f"CSV collection '{collection_name}' configuration must be a dictionary"
    #                     )

    #                 # Check for required filename if file-based
    #                 if isinstance(collection_config, dict):
    #                     filename = collection_config.get("filename")
    #                     if not filename:
    #                         # Log the auto-generation but don't modify the original config
    #                         self._logger.debug(
    #                             f"[StorageConfigService] Would auto-generate filename for collection '{collection_name}': {collection_name}.csv"
    #                         )
    #                         # Note: We don't modify the original config to avoid side effects
    #         elif collections:
    #             errors.append("CSV collections configuration must be a dictionary")

    #         # Note: Empty collections is fine - collections can be created dynamically

    #         return {
    #             "valid": len(errors) == 0,
    #             "warnings": warnings,
    #             "errors": errors,
    #             "summary": {
    #                 "collections_count": (
    #                     len(collections) if isinstance(collections, dict) else 0
    #                 ),
    #                 "csv_enabled": self.is_csv_storage_enabled(),
    #                 "data_path": (
    #                     str(self.get_csv_data_path())
    #                     if self.is_csv_storage_enabled()
    #                     else "not configured"
    #                 ),
    #             },
    #         }
    #     except Exception as e:
    #         return {
    #             "valid": False,
    #             "warnings": warnings,
    #             "errors": [f"Error validating CSV configuration: {e}"],
    #             "summary": {
    #                 "collections_count": 0,
    #                 "csv_enabled": False,
    #                 "data_path": "validation error",
    #             },
    #         }

    # def validate_vector_config(self) -> Dict[str, Any]:
    #     """
    #     Validate vector storage configuration.

    #     Returns:
    #         Dictionary with validation status
    #     """
    #     warnings = []
    #     errors = []

    #     vector_config = self.get_vector_config()

    #     if self.is_vector_storage_enabled():
    #         # Check for provider configuration
    #         provider = vector_config.get("default_provider")
    #         if not provider:
    #             warnings.append("Vector storage has no default provider configured")

    #         # Validate data path
    #         data_path = self.get_vector_data_path()
    #         if not data_path.exists():
    #             warnings.append(f"Vector data directory does not exist: {data_path}")

    #         # Check collections
    #         collections = vector_config.get("collections", {})
    #         if not collections:
    #             warnings.append("Vector storage has no collections configured")

    #     return {
    #         "valid": len(errors) == 0,
    #         "warnings": warnings,
    #         "errors": errors,
    #         "summary": {
    #             "vector_enabled": self.is_vector_storage_enabled(),
    #             "provider": vector_config.get("default_provider"),
    #             "collections_count": len(vector_config.get("collections", {})),
    #         },
    #     }

    # def validate_kv_config(self) -> Dict[str, Any]:
    #     """
    #     Validate key-value storage configuration.

    #     Returns:
    #         Dictionary with validation status
    #     """
    #     warnings = []
    #     errors = []

    #     kv_config = self.get_kv_config()

    #     if self.is_kv_storage_enabled():
    #         # Check for provider configuration
    #         provider = kv_config.get("default_provider")
    #         if not provider:
    #             warnings.append("KV storage has no default provider configured")

    #         # Validate data path
    #         data_path = self.get_kv_data_path()
    #         if not data_path.exists():
    #             warnings.append(f"KV data directory does not exist: {data_path}")

    #     return {
    #         "valid": len(errors) == 0,
    #         "warnings": warnings,
    #         "errors": errors,
    #         "summary": {
    #             "kv_enabled": self.is_kv_storage_enabled(),
    #             "provider": kv_config.get("default_provider"),
    #             "data_path": str(self.get_kv_data_path()),
    #         },
    #     }

    # def validate_json_config(self) -> Dict[str, Any]:
    #     """
    #     Validate JSON storage configuration.

    #     Returns:
    #         Dictionary with validation status similar to AppConfigService pattern
    #     """
    #     warnings = []
    #     errors = []

    #     try:
    #         json_config = self.get_json_config()

    #         # Skip validation if JSON config is not a dictionary (handled by parent validation)
    #         if not isinstance(json_config, dict):
    #             return {
    #                 "valid": False,
    #                 "warnings": warnings,
    #                 "errors": ["JSON configuration is not properly structured"],
    #                 "summary": {
    #                     "collections_count": 0,
    #                     "json_enabled": False,
    #                     "data_path": "unknown",
    #                 },
    #             }

    #         # Validate JSON storage is properly enabled
    #         if not self.is_json_storage_enabled():
    #             if json_config.get("enabled") is False:
    #                 warnings.append("JSON storage is explicitly disabled")
    #             elif not json_config.get("default_directory"):
    #                 errors.append(
    #                     "JSON storage requires a default_directory to be configured"
    #                 )
    #             else:
    #                 warnings.append("JSON storage configuration may be incomplete")
    #         else:
    #             # Validate directory exists if JSON is enabled
    #             try:
    #                 data_path = self.get_json_data_path()
    #                 if not data_path.exists():
    #                     warnings.append(
    #                         f"JSON data directory does not exist: {data_path}"
    #                     )
    #             except Exception as e:
    #                 warnings.append(f"Could not validate JSON data path: {e}")

    #         # Validate collections configuration (collections are optional - can be created dynamically)
    #         collections = json_config.get("collections", {})
    #         if isinstance(collections, dict):
    #             for collection_name, collection_config in collections.items():
    #                 if not isinstance(collection_config, dict):
    #                     errors.append(
    #                         f"JSON collection '{collection_name}' configuration must be a dictionary"
    #                     )

    #                 # Check for required filename if file-based
    #                 if isinstance(collection_config, dict):
    #                     filename = collection_config.get("filename")
    #                     if not filename:
    #                         # Log the auto-generation but don't modify the original config
    #                         self._logger.debug(
    #                             f"[StorageConfigService] Would auto-generate filename for collection '{collection_name}': {collection_name}.json"
    #                         )
    #                         # Note: We don't modify the original config to avoid side effects
    #         elif collections:
    #             errors.append("JSON collections configuration must be a dictionary")

    #         # Note: Empty collections is fine - collections can be created dynamically

    #         return {
    #             "valid": len(errors) == 0,
    #             "warnings": warnings,
    #             "errors": errors,
    #             "summary": {
    #                 "collections_count": (
    #                     len(collections) if isinstance(collections, dict) else 0
    #                 ),
    #                 "json_enabled": self.is_json_storage_enabled(),
    #                 "data_path": (
    #                     str(self.get_json_data_path())
    #                     if self.is_json_storage_enabled()
    #                     else "not configured"
    #                 ),
    #             },
    #         }
    #     except Exception as e:
    #         return {
    #             "valid": False,
    #             "warnings": warnings,
    #             "errors": [f"Error validating JSON configuration: {e}"],
    #             "summary": {
    #                 "collections_count": 0,
    #                 "json_enabled": False,
    #                 "data_path": "validation error",
    #             },
    #         }

    # def validate_blob_config(self) -> Dict[str, Any]:
    #     """
    #     Validate blob storage configuration.

    #     Returns:
    #         Dictionary with validation status similar to other validation methods
    #     """
    #     warnings = []
    #     errors = []

    #     try:
    #         blob_config = self.get_blob_config()

    #         # Skip validation if blob config is not a dictionary (handled by parent validation)
    #         if not isinstance(blob_config, dict):
    #             return {
    #                 "valid": False,
    #                 "warnings": warnings,
    #                 "errors": ["Blob configuration is not properly structured"],
    #                 "summary": {
    #                     "blob_enabled": False,
    #                     "providers_count": 0,
    #                     "data_path": "unknown",
    #                 },
    #             }

    #         # Validate blob storage is available
    #         if not self.is_blob_storage_enabled():
    #             if blob_config.get("enabled") is False:
    #                 warnings.append("Blob storage is explicitly disabled")
    #             else:
    #                 warnings.append("Blob storage configuration may be incomplete")
    #         else:
    #             # Validate directory exists if blob is enabled
    #             try:
    #                 data_path = self.get_blob_data_path()
    #                 if not data_path.exists():
    #                     warnings.append(
    #                         f"Blob data directory does not exist: {data_path}"
    #                     )
    #             except Exception as e:
    #                 warnings.append(f"Could not validate blob data path: {e}")

    #         # Validate providers configuration
    #         providers = blob_config.get("providers", {})
    #         if isinstance(providers, dict):
    #             for provider_name, provider_config in providers.items():
    #                 if not isinstance(provider_config, dict):
    #                     errors.append(
    #                         f"Blob provider '{provider_name}' configuration must be a dictionary"
    #                     )
    #                 elif provider_name not in ["azure", "s3", "gcs", "file"]:
    #                     warnings.append(
    #                         f"Unknown blob provider '{provider_name}'. Supported providers: azure, s3, gcs, file"
    #                     )
    #         elif providers:
    #             errors.append("Blob providers configuration must be a dictionary")

    #         # Validate default provider if specified
    #         default_provider = blob_config.get("default_provider")
    #         if default_provider and default_provider not in providers:
    #             errors.append(
    #                 f"Default blob provider '{default_provider}' is not configured in providers section"
    #             )

    #         return {
    #             "valid": len(errors) == 0,
    #             "warnings": warnings,
    #             "errors": errors,
    #             "summary": {
    #                 "blob_enabled": self.is_blob_storage_enabled(),
    #                 "providers_count": (
    #                     len(providers) if isinstance(providers, dict) else 0
    #                 ),
    #                 "default_provider": default_provider,
    #                 "data_path": (
    #                     str(self.get_blob_data_path())
    #                     if self.is_blob_storage_enabled()
    #                     else "not configured"
    #                 ),
    #             },
    #         }
    #     except Exception as e:
    #         return {
    #             "valid": False,
    #             "warnings": warnings,
    #             "errors": [f"Error validating blob configuration: {e}"],
    #             "summary": {
    #                 "blob_enabled": False,
    #                 "providers_count": 0,
    #                 "data_path": "validation error",
    #             },
    #         }

    # def validate_all_storage_config(self) -> Dict[str, Any]:
    #     """
    #     Validate all storage configuration sections.

    #     Returns:
    #         Dictionary with comprehensive validation status
    #     """
    #     all_warnings = []
    #     all_errors = []

    #     # First check for missing storage types (for backward compatibility)
    #     expected_types = ["csv", "vector", "kv", "json", "blob"]
    #     for storage_type in expected_types:
    #         if storage_type not in self._config_data:
    #             all_warnings.append(
    #                 f"Missing storage type configuration: {storage_type}"
    #             )

    #     # Validate each configured storage type for basic structure
    #     for storage_type, config in self._config_data.items():
    #         if not isinstance(config, dict):
    #             all_errors.append(
    #                 f"Storage type '{storage_type}' configuration must be a dictionary"
    #             )
    #             continue

    #         # Check for collections section
    #         if "collections" not in config:
    #             all_warnings.append(
    #                 f"Storage type '{storage_type}' has no collections configured"
    #             )
    #         elif not isinstance(config["collections"], dict):
    #             all_errors.append(
    #                 f"Storage type '{storage_type}' collections must be a dictionary"
    #             )

    #     # Add detailed validation for each storage type (only if basic structure is valid)
    #     # Only validate storage types that are actually configured (opt-in approach)
    #     if len(all_errors) == 0:  # Only run detailed validation if no structural errors
    #         if "csv" in self._config_data:
    #             csv_result = self.validate_csv_config()
    #             all_warnings.extend(csv_result.get("warnings", []))
    #             all_errors.extend(csv_result.get("errors", []))

    #         if "vector" in self._config_data:
    #             vector_result = self.validate_vector_config()
    #             all_warnings.extend(vector_result.get("warnings", []))
    #             all_errors.extend(vector_result.get("errors", []))

    #         if "kv" in self._config_data:
    #             kv_result = self.validate_kv_config()
    #             all_warnings.extend(kv_result.get("warnings", []))
    #             all_errors.extend(kv_result.get("errors", []))

    #         if "json" in self._config_data:
    #             json_result = self.validate_json_config()
    #             all_warnings.extend(json_result.get("warnings", []))
    #             all_errors.extend(json_result.get("errors", []))

    #         if "blob" in self._config_data:
    #             blob_result = self.validate_blob_config()
    #             all_warnings.extend(blob_result.get("warnings", []))
    #             all_errors.extend(blob_result.get("errors", []))

    #     return {
    #         "valid": len(all_errors) == 0,
    #         "warnings": all_warnings,
    #         "errors": all_errors,
    #         "summary": {
    #             "total_storage_types": len(
    #                 [
    #                     t
    #                     for t in ["csv", "vector", "kv", "json", "blob"]
    #                     if t in self._config_data
    #                     and isinstance(self._config_data[t], dict)
    #                 ]
    #             ),
    #             "csv": (
    #                 self.validate_csv_config().get("summary", {})
    #                 if "csv" in self._config_data
    #                 and isinstance(self._config_data.get("csv"), dict)
    #                 else {
    #                     "csv_enabled": False,
    #                     "collections_count": 0,
    #                     "data_path": "not configured",
    #                 }
    #             ),
    #             "vector": (
    #                 self.validate_vector_config().get("summary", {})
    #                 if "vector" in self._config_data
    #                 and isinstance(self._config_data.get("vector"), dict)
    #                 else {
    #                     "vector_enabled": False,
    #                     "collections_count": 0,
    #                     "provider": "not configured",
    #                 }
    #             ),
    #             "kv": (
    #                 self.validate_kv_config().get("summary", {})
    #                 if "kv" in self._config_data
    #                 and isinstance(self._config_data.get("kv"), dict)
    #                 else {
    #                     "kv_enabled": False,
    #                     "provider": "not configured",
    #                     "data_path": "not configured",
    #                 }
    #             ),
    #             "json": (
    #                 self.validate_json_config().get("summary", {})
    #                 if "json" in self._config_data
    #                 and isinstance(self._config_data.get("json"), dict)
    #                 else {
    #                     "json_enabled": False,
    #                     "collections_count": 0,
    #                     "data_path": "not configured",
    #                 }
    #             ),
    #             "blob": (
    #                 self.validate_blob_config().get("summary", {})
    #                 if "blob" in self._config_data
    #                 and isinstance(self._config_data.get("blob"), dict)
    #                 else {
    #                     "blob_enabled": False,
    #                     "providers_count": 0,
    #                     "data_path": "not configured",
    #                 }
    #             ),
    #             "overall_status": self.get_storage_summary(),
    #         },
    #     }

    def validate_storage_config(self) -> Dict[str, list[str]]:
        """
        Validate storage configuration and return any issues found.

        Returns:
            Dictionary with validation results:
            - 'warnings': List of non-critical issues
            - 'errors': List of critical issues

        Note: This method provides basic validation for test compatibility.
        """
        warnings = []
        errors = []

        try:
            # Basic validation - check if config data exists and is valid
            if self._config_data is None:
                errors.append("Storage configuration data is not loaded")
                return {"warnings": warnings, "errors": errors}

            if not isinstance(self._config_data, dict):
                errors.append("Storage configuration must be a dictionary")
                return {"warnings": warnings, "errors": errors}

            # Validate each storage type if configured
            storage_types = ["csv", "vector", "kv", "json", "blob"]

            for storage_type in storage_types:
                if storage_type in self._config_data:
                    config = self._config_data[storage_type]

                    # Basic structure validation
                    if not isinstance(config, dict):
                        errors.append(
                            f"{storage_type} configuration must be a dictionary"
                        )
                        continue

                    # Check collections structure
                    collections = config.get("collections")
                    if collections is not None and not isinstance(collections, dict):
                        errors.append(
                            f"{storage_type} collections must be a dictionary"
                        )

                    # Check for proper configuration based on storage type
                    if storage_type in ["csv", "vector", "kv", "blob"]:
                        if (
                            not config.get("default_directory")
                            and not self.get_base_directory()
                        ):
                            warnings.append(
                                f"{storage_type} storage has no default_directory configured"
                            )

            # Check if at least one storage type is properly configured
            has_valid_storage = False
            for storage_type in storage_types:
                if storage_type == "json" or self.is_storage_type_enabled(storage_type):
                    has_valid_storage = True
                    break

            if not has_valid_storage:
                warnings.append("No storage types appear to be properly configured")

        except Exception as e:
            errors.append(f"Error during storage config validation: {e}")

        return {"warnings": warnings, "errors": errors}
