"""
Base interfaces and utilities for cloud blob storage connectors.

This module provides a common interface for cloud storage operations,
allowing JSON agents to seamlessly work with various cloud providers.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse

from agentmap.exceptions import StorageConnectionError, StorageOperationError


class BlobStorageConnector(ABC):
    """
    Interface for cloud blob storage operations.

    This abstract class defines the contract that all cloud storage
    implementations must follow, with common utilities for parsing URIs,
    handling authentication, and performing basic blob operations.
    """

    # URI scheme handled by this connector
    URI_SCHEME = None

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the storage connector.

        Args:
            config: Configuration for this storage provider
        """
        self.config = config or {}
        self._client = None

    @property
    def client(self) -> Any:
        """
        Access the storage client connection.

        Returns:
            Storage client instance

        Note:
            This property will initialize the client on first access
            if it doesn't already exist.
        """
        if self._client is None:
            self._initialize_client()
        return self._client

    @abstractmethod
    def _initialize_client(self) -> None:
        """
        Initialize the storage client connection.

        Subclasses should implement this to set up their specific client connection.

        Raises:
            StorageConnectionError: If client initialization fails
        """

    @abstractmethod
    def read_blob(self, uri: str) -> bytes:
        """
        Read raw bytes from blob storage.

        Args:
            uri: URI of the blob to read

        Returns:
            Blob content as bytes

        Raises:
            FileNotFoundError: If the blob doesn't exist
            StorageOperationError: For other storage-related errors
        """

    @abstractmethod
    def write_blob(self, uri: str, data: bytes) -> None:
        """
        Write raw bytes to blob storage.

        Args:
            uri: URI where the blob should be written
            data: Blob content as bytes

        Raises:
            StorageOperationError: If the write operation fails
        """

    @abstractmethod
    def blob_exists(self, uri: str) -> bool:
        """
        Check if a blob exists at the specified URI.

        Args:
            uri: URI to check

        Returns:
            True if the blob exists, False otherwise
        """

    def list_blobs(self, prefix: str, **kwargs) -> list[str]:
        """
        List blobs with given prefix.

        Args:
            prefix: URI prefix to search
            **kwargs: Provider-specific parameters

        Returns:
            List of blob URIs

        Note:
            Default implementation returns empty list.
            Subclasses should override if they support listing.
        """
        self.log_warning(f"list_blobs not implemented for {self.__class__.__name__}")
        return []

    def delete_blob(self, uri: str) -> None:
        """
        Delete a blob.

        Args:
            uri: URI of the blob to delete

        Raises:
            StorageOperationError: If delete is not supported

        Note:
            Default implementation raises error.
            Subclasses should override if they support deletion.
        """
        raise StorageOperationError(
            f"delete_blob not implemented for {self.__class__.__name__}"
        )

    def parse_uri(self, uri: str) -> Dict[str, str]:
        """
        Parse a blob URI into components.

        Args:
            uri: Blob storage URI

        Returns:
            Dictionary with parsed components (scheme, bucket/container, path)

        Raises:
            ValueError: If the URI is invalid or not supported by this connector
        """
        if not uri:
            raise ValueError("Empty URI provided")

        if self.URI_SCHEME and not uri.startswith(f"{self.URI_SCHEME}://"):
            # If this is a named collection reference without scheme, let it through
            if "://" not in uri:
                return {"scheme": self.URI_SCHEME, "container": "", "path": uri}
            else:
                raise ValueError(f"URI scheme not supported by this connector: {uri}")

        parsed = urlparse(uri)

        # Extract scheme
        scheme = parsed.scheme or self.URI_SCHEME

        # Extract container/bucket name (netloc)
        container = parsed.netloc

        # Extract blob path (removing leading slash)
        path = unquote(parsed.path)
        if path.startswith("/"):
            path = path[1:]

        return {"scheme": scheme, "container": container, "path": path}

    def log_debug(self, message: str) -> None:
        """Log debug message."""
        # Default implementation does nothing
        # Subclasses can override to integrate with logging
        pass

    def log_info(self, message: str) -> None:
        """Log info message."""
        # Default implementation does nothing
        # Subclasses can override to integrate with logging
        pass

    def log_warning(self, message: str) -> None:
        """Log warning message."""
        # Default implementation does nothing
        # Subclasses can override to integrate with logging
        pass

    def log_error(self, message: str) -> None:
        """Log error message."""
        # Default implementation does nothing
        # Subclasses can override to integrate with logging
        pass

    def resolve_env_value(self, value: str) -> str:
        """
        Resolve environment variable references in config values.

        Args:
            value: Config value, possibly containing env: prefix

        Returns:
            Resolved value
        """
        if not isinstance(value, str):
            return value

        if value.startswith("env:"):
            env_var = value[4:]
            env_value = os.environ.get(env_var, "")
            if not env_value:
                self.log_warning(f"Environment variable not found: {env_var}")
            return env_value

        return value

    def _handle_provider_error(
        self,
        operation: str,
        uri: str,
        error: Exception,
        raise_error: bool = True,
        resource_type: str = "blob",
    ) -> Optional[Dict[str, Any]]:
        """
        Handle provider-specific errors with standardized formatting.

        Args:
            operation: Operation being performed (read, write, etc.)
            uri: URI being accessed
            error: The exception that occurred
            raise_error: Whether to raise an exception or return error info
            resource_type: Type of resource being accessed

        Returns:
            Error information dictionary if raise_error is False

        Raises:
            FileNotFoundError: If the resource doesn't exist
            StorageOperationError: For other storage-related errors
        """
        # Parse URI for better error messaging
        try:
            parts = self.parse_uri(uri)
            container = parts.get("container", "")
            path = parts.get("path", "")
            resource = f"{container}/{path}" if container else path
        except Exception:
            resource = uri

        # Handle different error types
        error_msg = f"Error {operation} {resource_type} at {resource}: {str(error)}"
        self.log_error(f"[{self.__class__.__name__}] {error_msg}")

        if not raise_error:
            return {
                "success": False,
                "operation": operation,
                "uri": uri,
                "error": error_msg,
            }

        # Convert to standard exceptions
        if "not found" in str(error).lower() or "404" in str(error):
            raise FileNotFoundError(
                f"{resource_type.capitalize()} not found: {resource}"
            )
        elif "permission" in str(error).lower() or "403" in str(error):
            raise StorageOperationError(f"Permission denied for {resource}")
        elif "connection" in str(error).lower():
            raise StorageConnectionError(f"Connection error: {str(error)}")
        else:
            raise StorageOperationError(error_msg)


def get_connector_for_uri(
    uri: str, config: Dict[str, Any] = None
) -> BlobStorageConnector:
    """
    Factory function to get the appropriate connector for a URI.

    Args:
        uri: Blob storage URI or collection name
        config: Configuration dictionary for storage providers

    Returns:
        Appropriate BlobStorageConnector instance

    Raises:
        ValueError: If no suitable connector is found
    """
    config = config or {}

    # Handle named collections that might not have URI scheme
    if "://" not in uri:
        # Check if this is a named collection in the config
        collections = config.get("collections", {})
        if uri in collections:
            # Resolve named collection to actual URI
            uri = collections[uri]

    # Lazy imports to avoid circular dependencies and allow optional installations
    if uri.startswith("azure://"):
        from agentmap.services.storage.azure_blob_connector import (
            AzureBlobConnector,
        )

        return AzureBlobConnector(config.get("providers", {}).get("azure", {}))
    elif uri.startswith("s3://"):
        from agentmap.services.storage.aws_s3_connector import (
            AWSS3Connector,
        )

        return AWSS3Connector(config.get("providers", {}).get("aws", {}))
    elif uri.startswith("gs://"):
        from agentmap.services.storage.gcp_storage_connector import (
            GCPStorageConnector,
        )

        return GCPStorageConnector(config.get("providers", {}).get("gcp", {}))
    else:
        # Default to local file connector if no scheme or unrecognized
        from agentmap.services.storage.local_file_connector import (
            LocalFileConnector,
        )

        return LocalFileConnector(config.get("providers", {}).get("local", {}))


def normalize_json_uri(uri: str) -> str:
    """
    Normalize a JSON URI to ensure consistent paths.

    Args:
        uri: URI or path to normalize

    Returns:
        Normalized URI
    """
    # Ensure path has .json extension
    if not uri.lower().endswith(".json"):
        # Preserve scheme and container if present
        if "://" in uri:
            scheme_parts = uri.split("://", 1)
            path_parts = scheme_parts[1].split("/", 1)

            if len(path_parts) > 1:
                container = path_parts[0]
                path = path_parts[1]
                # Add .json to path
                if not path.lower().endswith(".json"):
                    path += ".json"
                uri = f"{scheme_parts[0]}://{container}/{path}"
            else:
                # Just container, add empty path with .json
                uri = f"{uri}/data.json"
        else:
            uri = f"{uri}.json"

    return uri
