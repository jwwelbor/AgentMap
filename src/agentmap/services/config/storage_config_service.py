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
    ):
        """
        Initialize StorageConfigService with storage configuration path.

        Args:
            config_service: ConfigService instance for infrastructure operations
            storage_config_path: Path to storage configuration file. Cannot be None.

        Raises:
            StorageConfigurationNotAvailableException: If config path is None,
                file doesn't exist, or file cannot be parsed.
        """
        self._config_service = config_service
        self._config_data = None
        self._logger = None

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
        for storage_type in ["csv", "vector", "kv"]:
            if storage_type in self._config_data:
                collections = self.list_collections(storage_type)
                summary[f"{storage_type}_collections"] = collections
                summary[f"{storage_type}_collection_count"] = len(collections)

        return summary

    def validate_storage_config(self) -> Dict[str, list[str]]:
        """
        Validate storage configuration and return any issues found.

        Returns:
            Dictionary with validation results:
            - 'warnings': List of non-critical issues
            - 'errors': List of critical issues
        """
        warnings = []
        errors = []

        # Check for expected storage types
        expected_types = ["csv", "vector", "kv"]
        for storage_type in expected_types:
            if storage_type not in self._config_data:
                warnings.append(f"Missing storage type configuration: {storage_type}")

        # Validate each configured storage type
        for storage_type, config in self._config_data.items():
            if not isinstance(config, dict):
                errors.append(
                    f"Storage type '{storage_type}' configuration must be a dictionary"
                )
                continue

            # Check for collections section
            if "collections" not in config:
                warnings.append(
                    f"Storage type '{storage_type}' has no collections configured"
                )
            elif not isinstance(config["collections"], dict):
                errors.append(
                    f"Storage type '{storage_type}' collections must be a dictionary"
                )

        self._logger.debug(
            f"[StorageConfigService] Validation completed: {len(warnings)} warnings, {len(errors)} errors"
        )

        return {"warnings": warnings, "errors": errors}
