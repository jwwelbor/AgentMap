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
    """

    _base_directory: Optional[str]
    _file_path_service: Optional[FilePathService]
    _logger: Any
    provider_name: str
    configuration: Any

    @property
    def base_directory(self) -> Optional[str]:
        """Get the base directory for storage operations."""
        return self._base_directory

    def get_full_path(self, key: str) -> str:
        """Get the full path for a storage key."""
        if not key:
            raise ValueError("Storage key cannot be empty")

        if self._base_directory:
            return self._resolve_system_storage_path(key)
        return self._resolve_user_storage_path(key)

    def _resolve_system_storage_path(self, key: str) -> str:
        """Resolve path for system storage using injected base_directory."""
        full_path = str(Path(self._base_directory) / key)

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
        """Resolve path for user storage using StorageConfigService."""
        try:
            config_base_dir = self.configuration.get_base_directory()
            if not config_base_dir:
                raise ValueError("No base directory configured in StorageConfigService")

            full_path = str(Path(config_base_dir) / key)

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
