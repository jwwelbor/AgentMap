"""
Path resolution mixin for storage services.

This module provides path resolution functionality that can be mixed into
storage services to handle path building and validation.
"""

from pathlib import Path
from typing import Any, Optional

from agentmap.services.file_path_service import FilePathService


class PathResolverMixin:
    """
    Mixin class providing path resolution functionality for storage services.

    This mixin handles:
    - Building full paths from storage keys
    - Path validation and security checks
    - Different path resolution strategies for system vs user storage

    Expected attributes on the class using this mixin:
    - _base_directory: Optional[str]
    - _file_path_service: Optional[FilePathService]
    - _logger: Logger instance
    - provider_name: str
    - configuration: StorageConfigService (for user storage)
    """

    # Type hints for attributes expected from the base class
    _base_directory: Optional[str]
    _file_path_service: Optional[FilePathService]
    _logger: Any
    provider_name: str
    configuration: Any

    @property
    def base_directory(self) -> Optional[str]:
        """
        Get the base directory for storage operations.

        Returns:
            Base directory path or None if not configured
        """
        return self._base_directory

    def get_full_path(self, key: str) -> str:
        """
        Get the full path for a storage key.

        Handles different path resolution strategies based on storage configuration:
        - For system storage (dict config): uses base_directory/key directly
        - For user storage (StorageConfigService): uses base_directory/storage_config_default_directory/key

        Args:
            key: Storage key/collection name

        Returns:
            Full resolved path for storage operations

        Raises:
            ValueError: If path cannot be resolved or is unsafe
        """
        if not key:
            raise ValueError("Storage key cannot be empty")

        # For system storage with base_directory injection (dict config)
        if self._base_directory:
            return self._resolve_system_storage_path(key)

        # For user storage (StorageConfigService) - use configuration's default directory
        return self._resolve_user_storage_path(key)

    def _resolve_system_storage_path(self, key: str) -> str:
        """
        Resolve path for system storage using injected base_directory.

        Args:
            key: Storage key/collection name

        Returns:
            Full resolved path

        Raises:
            ValueError: If path is unsafe
        """
        full_path = str(Path(self._base_directory) / key)

        # Validate path if file_path_service is available
        if self._file_path_service:
            try:
                self._file_path_service.validate_safe_path(
                    full_path, self._base_directory
                )
            except Exception as e:
                self._logger.error(
                    f"[{self.provider_name}] Path validation failed for {full_path}: {e}"
                )
                raise ValueError(f"Unsafe storage path: {e}")

        self._logger.trace(
            f"[{self.provider_name}] Resolved system storage path: {full_path}"
        )
        return full_path

    def _resolve_user_storage_path(self, key: str) -> str:
        """
        Resolve path for user storage using StorageConfigService.

        Args:
            key: Storage key/collection name

        Returns:
            Full resolved path

        Raises:
            ValueError: If path cannot be resolved or is unsafe
        """
        try:
            # Get base directory from configuration
            config_base_dir = self.configuration.get_base_directory()
            if not config_base_dir:
                raise ValueError("No base directory configured in StorageConfigService")

            # Combine with key
            full_path = str(Path(config_base_dir) / key)

            # Validate path if file_path_service is available
            if self._file_path_service:
                try:
                    self._file_path_service.validate_safe_path(
                        full_path, config_base_dir
                    )
                except Exception as e:
                    self._logger.error(
                        f"[{self.provider_name}] Path validation failed for {full_path}: {e}"
                    )
                    raise ValueError(f"Unsafe storage path: {e}")

            self._logger.trace(
                f"[{self.provider_name}] Resolved user storage path: {full_path}"
            )
            return full_path

        except Exception as e:
            self._logger.error(
                f"[{self.provider_name}] Failed to resolve storage path for key '{key}': {e}"
            )
            raise ValueError(f"Cannot resolve storage path: {e}")


__all__ = ["PathResolverMixin"]
