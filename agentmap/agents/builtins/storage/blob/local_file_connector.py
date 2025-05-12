"""
Local file system connector for JSON storage.

This module provides a local file system implementation of the BlobStorageConnector
interface, serving as a fallback when cloud storage is not specified.
"""
import os
from pathlib import Path
from typing import Any, Dict

from agentmap.agents.builtins.storage.blob.base_connector import BlobStorageConnector
from agentmap.exceptions import StorageOperationError
from agentmap.logging import get_logger

logger = get_logger(__name__)


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
            config: Configuration for local file storage
        """
        super().__init__(config)
        self.base_dir = config.get("base_dir", "")

    def _initialize_client(self) -> None:
        """No client initialization needed for local files."""
        self._client = True  # Just a placeholder

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
        try:
            path = self._resolve_path(uri)
            with open(path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"File not found: {path}")
            raise
        except Exception as e:
            logger.error(f"Error reading file {path}: {str(e)}")
            raise StorageOperationError(f"Failed to read file {path}: {str(e)}")

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
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:
            logger.error(f"Error writing to file {path}: {str(e)}")
            raise StorageOperationError(f"Failed to write to file {path}: {str(e)}")

    def blob_exists(self, uri: str) -> bool:
        """
        Check if a file exists.

        Args:
            uri: Path to check

        Returns:
            True if the file exists, False otherwise
        """
        path = self._resolve_path(uri)
        return os.path.exists(path)

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

        return path