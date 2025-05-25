"""
Storage types and enums for AgentMap.

This module contains shared types, enums, and exceptions used across all storage
implementations. It breaks circular dependencies by providing a central location
for common storage-related types.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

# Generic type variable for storage data
T = TypeVar('T')


class WriteMode(str, Enum):
    """Storage write operation modes using string values."""
    WRITE = "write"    # Create or overwrite document
    UPDATE = "update"  # Update existing document fields
    MERGE = "merge"    # Merge with existing document
    DELETE = "delete"  # Delete document or field
    APPEND = "append"  # Append to existing document
    
    @classmethod
    def from_string(cls, mode: str) -> "WriteMode":
        """Convert string to enum value, case-insensitive."""
        try:
            return cls(mode.lower())
        except ValueError:
            valid_modes = ", ".join(m.value for m in cls)
            raise ValueError(f"Invalid write mode: {mode}. Valid modes: {valid_modes}")


class StorageOperation(str, Enum):
    """Storage operation types."""
    READ = "read"
    WRITE = "write"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    EXISTS = "exists"
    QUERY = "query"


@dataclass
class StorageResult(Generic[T]):
    """
    Structured result from storage operations.
    
    This class provides a standardized way to return results from storage operations,
    with metadata about the operation and its success.
    """
    # Required fields
    success: bool = False
    
    # Optional metadata fields
    operation: Optional[str] = None
    collection: Optional[str] = None
    document_id: Optional[str] = None
    mode: Optional[str] = None
    file_path: Optional[str] = None
    path: Optional[str] = None
    count: Optional[int] = None
    error: Optional[str] = None
    message: Optional[str] = None
    data: Optional[T] = None
    
    # Operation-specific fields
    created_new: Optional[bool] = None
    document_created: Optional[bool] = None
    file_deleted: Optional[bool] = None
    rows_written: Optional[int] = None
    rows_updated: Optional[int] = None
    rows_added: Optional[int] = None
    total_affected: Optional[int] = None
    updated_ids: Optional[List[str]] = None
    deleted_ids: Optional[List[str]] = None
    is_collection: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary, filtering out None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def __getitem__(self, key: str) -> Any:
        """
        Make the StorageResult subscriptable for backward compatibility.
        
        Args:
            key: The attribute name to access
            
        Returns:
            The value of the attribute
            
        Raises:
            KeyError: If the attribute doesn't exist
        """
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)


@dataclass
class StorageConfig:
    """Configuration for storage services."""
    provider: str
    connection_string: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None
    retry_attempts: Optional[int] = None
    
    def get_option(self, key: str, default: Any = None) -> Any:
        """Get a configuration option with fallback."""
        if self.options:
            return self.options.get(key, default)
        return default


# Storage-specific exception classes
class StorageError(Exception):
    """Base exception for storage operations."""
    def __init__(self, message: str, operation: Optional[str] = None, collection: Optional[str] = None):
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


# Type aliases for common patterns
CollectionPath = Union[str, List[str]]
DocumentID = Union[str, int]
QueryFilter = Dict[str, Any]
StorageData = Union[Dict[str, Any], List[Dict[str, Any]], Any]

# For backward compatibility, alias DocumentResult to StorageResult
DocumentResult = StorageResult
