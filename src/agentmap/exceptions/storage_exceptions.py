"""
Storage service exceptions for AgentMap.

This module contains all exception classes for storage operations.
Consolidated from services/storage/exceptions.py to maintain unified exception hierarchy.
"""

from typing import Optional

from agentmap.exceptions.base_exceptions import AgentMapException


class StorageError(AgentMapException):
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


class StorageConfigurationError(StorageError):
    """Exception raised when storage configuration is invalid."""


class StorageNotFoundError(StorageError):
    """Exception raised when requested storage resource is not found."""


class StoragePermissionError(StorageError):
    """Exception raised when storage operation lacks permissions."""


class StorageValidationError(StorageError):
    """Exception raised when storage data validation fails."""


class StorageOperationError(StorageError):
    """Exception raised when there is an error performing a storage operation."""


class StorageAuthenticationError(StorageError):
    """Exception raised when there is an error authenticating with the storage system."""


# Collection and Document specific exceptions
class CollectionNotFoundError(StorageNotFoundError):
    """Exception raised when a collection is not found in the storage configuration."""


class DocumentNotFoundError(StorageNotFoundError):
    """Exception raised when a document is not found in the storage system."""


# Service-specific exceptions
class StorageServiceError(StorageError):
    """Base exception for storage service errors."""


class StorageProviderError(StorageServiceError):
    """Error from storage provider."""


class StorageServiceConfigurationError(StorageServiceError):
    """Storage service configuration error."""


class StorageServiceNotAvailableError(StorageServiceError):
    """Storage service is not available or not initialized."""
