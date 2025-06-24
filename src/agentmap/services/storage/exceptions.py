"""
Storage service exceptions for AgentMap.

This module contains exception classes for storage operations.
These are kept in services as they relate to service-level operations and errors.
"""

from typing import Optional


class StorageError(Exception):
    """Base exception for storage operations."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        collection: Optional[str] = None,
    ):
        super().__init__(message)
        self.operation = operation
        self.collection = collection


class StorageConnectionError(StorageError):
    """Exception raised when storage connection fails."""

    pass


class StorageConfigurationError(StorageError):
    """Exception raised when storage configuration is invalid."""

    pass


class StorageNotFoundError(StorageError):
    """Exception raised when requested storage resource is not found."""

    pass


class StoragePermissionError(StorageError):
    """Exception raised when storage operation lacks permissions."""

    pass


class StorageValidationError(StorageError):
    """Exception raised when storage data validation fails."""

    pass


# Service-specific exceptions
class StorageServiceError(StorageError):
    """Base exception for storage service errors."""

    pass


class StorageProviderError(StorageServiceError):
    """Error from storage provider."""

    pass


class StorageServiceConfigurationError(StorageServiceError):
    """Storage service configuration error."""

    pass


class StorageServiceNotAvailableError(StorageServiceError):
    """Storage service is not available or not initialized."""

    pass
