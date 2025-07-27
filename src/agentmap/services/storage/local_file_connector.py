"""
Local file system connector for JSON storage.

This module provides a local file system implementation of the BlobStorageConnector
interface, serving as a fallback when cloud storage is not specified.
"""

import os
from typing import Any, Dict

from agentmap.services.storage.base_connector import BlobStorageConnector


class LocalFileConnector(BlobStorageConnector):
    """
    Local file system connector for blob storage operations.

    This connector implements the BlobStorageConnector interface for
    local file system operations, used as a fallback when no cloud
    storage is specified.
    """

    URI_SCHEME = "file"

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the local file connector.

        Args:
            config: Configuration for local file storage including:
                - base_dir: Base directory for file operations
        """
        super().__init__(config)
        self.base_dir = config.get("base_dir", "") if config else ""

    def _initialize_client(self) -> None:
        """
        No client initialization needed for local files.

        This is a placeholder to satisfy the interface requirement.
        """
        self._client = True  # Just a placeholder

        # Create base directory if configured
        if self.base_dir and not os.path.exists(self.base_dir):
            try:
                os.makedirs(self.base_dir, exist_ok=True)
                self.log_debug(f"Created base directory: {self.base_dir}")
            except Exception as e:
                self.log_warning(
                    f"Failed to create base directory {self.base_dir}: {str(e)}"
                )

    def read_blob(self, uri: str) -> bytes:
        """
        Read file from local file system.

        Args:
            uri: Path to the file

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If the file doesn't exist
            StorageOperationError: For other file-related errors
        """
        path = ""
        try:
            path = self._resolve_path(uri)
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")

            with open(path, "rb") as f:
                return f.read()
        except FileNotFoundError as e:
            return self._handle_provider_error(
                "reading", path, e, raise_error=True, resource_type="file"
            )
        except PermissionError as e:
            return self._handle_provider_error(
                "reading", path, e, raise_error=True, resource_type="file"
            )
        except Exception as e:
            return self._handle_provider_error(
                "reading", uri, e, raise_error=True, resource_type="file"
            )

    def write_blob(self, uri: str, data: bytes) -> None:
        """
        Write to local file system.

        Args:
            uri: Path where the file should be written
            data: File contents as bytes

        Raises:
            StorageOperationError: If the write operation fails
        """
        try:
            path = self._resolve_path(uri)

            # Ensure directory exists
            directory = os.path.dirname(path)
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            # Write file
            with open(path, "wb") as f:
                f.write(data)

            self.log_debug(f"Successfully wrote {len(data)} bytes to {path}")
        except PermissionError as e:
            return self._handle_provider_error(
                "writing", path, e, raise_error=True, resource_type="file"
            )
        except Exception as e:
            return self._handle_provider_error(
                "writing", uri, e, raise_error=True, resource_type="file"
            )

    def blob_exists(self, uri: str) -> bool:
        """
        Check if a file exists.

        Args:
            uri: Path to check

        Returns:
            True if the file exists, False otherwise
        """
        try:
            path = self._resolve_path(uri)
            exists = os.path.exists(path) and os.path.isfile(path)
            if not exists:
                self.log_debug(f"File not found: {path}")
            return exists
        except Exception as e:
            self.log_warning(f"Error checking file existence {uri}: {str(e)}")
            return False

    def _resolve_path(self, uri: str) -> str:
        """
        Resolve URI to local file path.

        Args:
            uri: URI or path string

        Returns:
            Absolute file path
        """
        # Parse URI components
        if "://" in uri:
            parts = self.parse_uri(uri)
            path = parts["path"]
        else:
            path = uri

        # Apply base directory if configured
        if self.base_dir:
            path = os.path.join(self.base_dir, path)

        # Ensure path is absolute
        path = os.path.abspath(path)

        # Expand user directory if needed (e.g., ~/)
        path = os.path.expanduser(path)

        return path
