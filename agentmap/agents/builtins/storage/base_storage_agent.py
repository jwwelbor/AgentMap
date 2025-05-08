"""
Base storage agent implementation.

This module provides the foundation for all storage agents in AgentMap,
with utilities for accessing data stores and handling operations.
"""
from __future__ import annotations

import functools
from dataclasses import asdict, dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, Union, cast

from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')  # Generic type for data storage
F = TypeVar('F', bound=Callable[..., Any])  # Type for callable functions


class WriteMode(str, Enum):
    """Document write operation modes using string values."""
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


@dataclass
class DocumentResult(Generic[T]):
    """
    Structured result from document operations.
    
    This class provides a standardized way to return results from storage operations,
    with metadata about the operation and its success.
    """
    # Required fields
    success: bool = False
    
    # Optional metadata fields
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
    updated_ids: Optional[list[str]] = None
    deleted_ids: Optional[list[str]] = None
    is_collection: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary, filtering out None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def __getitem__(self, key: str) -> Any:
        """
        Make the DocumentResult subscriptable for backward compatibility.
        
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


def log_operation(func: F) -> F:
    """
    Decorator to log storage operations with consistent formatting.
    
    Args:
        func: The function to decorate
        
    Returns:
        Wrapped function with logging
    """
    @functools.wraps(func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        class_name = self.__class__.__name__
        logger.debug(f"[{class_name}] Starting {func.__name__}")
        try:
            result = func(self, *args, **kwargs)
            logger.debug(f"[{class_name}] Completed {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"[{class_name}] Error in {func.__name__}: {str(e)}")
            raise
    return cast(F, wrapper)


class BaseStorageAgent(BaseAgent):
    """
    Base class for all storage agents in AgentMap.
    
    This abstract class defines the contract that all storage
    implementations must follow, with common utilities for
    error handling and connection management.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the storage agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including input/output field configuration
        """
        super().__init__(name, prompt, context or {})
        self._client: Any = None
    
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
    
    def _initialize_client(self) -> None:
        """
        Initialize the storage client connection.
        
        Subclasses should implement this to set up their specific client connection.
        """
        raise NotImplementedError("Subclasses must implement _initialize_client")
    
    def get_collection(self, inputs: Dict[str, Any]) -> str:
        """
        Get the collection name/path from inputs or configuration.
        
        Args:
            inputs: Dictionary of input values
            
        Returns:
            Collection identifier (typically a file path for CSV)
            
        Raises:
            ValueError: If no collection is specified
        """
        # Try to get the collection from inputs
        collection = inputs.get("collection")
        
        # If not in inputs, try to get from prompt (for backward compatibility)
        if collection is None and self.prompt:
            collection = self.prompt
            
        if collection is None:
            raise ValueError("No collection specified in inputs or prompt")
            
        # Resolve collection path through configuration
        return self._resolve_collection_path(collection)
    
    def _resolve_collection_path(self, collection: str) -> str:
        """
        Resolve a collection name to an actual storage path using configuration.
        
        Args:
            collection: Collection name or path
            
        Returns:
            Resolved path
        """
        # This is a basic implementation, subclasses may override
        return collection
    
    def _handle_error(
        self, 
        error_type: str, 
        message: str, 
        exception: Optional[Exception] = None,
        raise_error: bool = True
    ) -> None:
        """
        Handle errors with consistent logging.
        
        Args:
            error_type: Type of error
            message: Error message
            exception: Optional exception object
            raise_error: Whether to raise the error or just log it
            
        Raises:
            ValueError: For input/validation errors
            RuntimeError: For other errors
        """
        # Build complete error message
        error_msg = f"{error_type}: {message}"
        if exception is not None:
            error_msg += f" - {str(exception)}"
            
        logger.error(f"[{self.__class__.__name__}] {error_msg}")
        
        if not raise_error:
            return
            
        # Choose exception type based on the underlying error
        if isinstance(exception, (ValueError, TypeError)):
            raise ValueError(error_msg) from exception
        else:
            raise RuntimeError(error_msg) from exception
    
    def _normalize_document_id(self, document_id: Any) -> Optional[str]:
        """
        Normalize document ID to string format.
        
        Args:
            document_id: Document ID in any format
            
        Returns:
            String document ID or None
        """
        if document_id is None:
            return None
        return str(document_id)