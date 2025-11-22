# agentmap/services/config/_path_resolver.py
"""
Internal module for path resolution in StorageConfigService.

This module handles all path-related operations including base directory
resolution, storage type directory handling, and full path resolution.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional


class PathResolver:
    """
    Handles path resolution for storage configuration.

    This class encapsulates all path-related logic, including:
    - Base directory resolution
    - Storage type directory resolution
    - Full path resolution with hierarchy
    - Directory creation logic
    """

    def __init__(
        self,
        config_data: Dict[str, Any],
        config_service,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the path resolver.

        Args:
            config_data: The storage configuration data dictionary
            config_service: ConfigService instance for value lookups
            logger: Logger instance for debug messages
        """
        self._config_data = config_data
        self._config_service = config_service
        self._logger = logger or logging.getLogger(__name__)

    def get_base_directory(self) -> str:
        """
        Get the base storage directory that all storage types use as their root.

        Returns:
            Base directory path for all storage operations
        """
        # Check for core.base_directory first (proper YAML structure)
        base_dir = self._config_service.get_value_from_config(
            self._config_data, "core.base_directory", None
        )

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
        config = self._config_service.get_value_from_config(
            self._config_data, storage_type, {}
        )
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

    def ensure_directory_exists(self, path: Path, storage_type: str) -> bool:
        """
        Ensure a directory exists, creating it if necessary.

        Args:
            path: Path to ensure exists
            storage_type: Storage type name (for logging)

        Returns:
            True if directory exists or was created successfully, False otherwise
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
            self._logger.debug(
                f"[StorageConfigService] {storage_type} data path ensured: {path}"
            )
            return True
        except Exception as e:
            self._logger.warning(
                f"[StorageConfigService] Could not create {storage_type} data directory {path}: {e}"
            )
            return False

    def get_data_path(self, storage_type: str, ensure_exists: bool = True) -> Path:
        """
        Get the data directory path for a storage type.

        Args:
            storage_type: Type of storage ("csv", "vector", "kv", "json", "blob")
            ensure_exists: Whether to create the directory if it doesn't exist

        Returns:
            Path to storage type data directory
        """
        data_path = self.resolve_full_storage_path(storage_type)

        if ensure_exists:
            self.ensure_directory_exists(data_path, storage_type)

        return data_path

    def get_collection_file_path(
        self, storage_type: str, collection_name: str, extension: str = "csv"
    ) -> Path:
        """
        Get the full file path for a collection.

        Args:
            storage_type: Type of storage ("csv", "json", etc.)
            collection_name: Name of the collection
            extension: File extension (default: "csv")

        Returns:
            Path to the collection file
        """
        storage_path = self.get_data_path(storage_type, ensure_exists=True)
        collection_config = self._config_service.get_value_from_config(
            self._config_data,
            f"{storage_type}.collections.{collection_name}",
            {},
        )
        filename = collection_config.get("filename", f"{collection_name}.{extension}")
        return storage_path / filename
