"""
Storage services module for AgentMap.

This module provides storage services and types for centralized storage operations.
Following the service-oriented architecture pattern, all storage-related functionality
is organized here.
"""

from .types import (
    # Core types
    WriteMode,
    StorageOperation,
    StorageResult,
    StorageConfig,
    
    # Exceptions
    StorageError,
    StorageConnectionError,
    StorageConfigurationError,
    StorageNotFoundError,
    StoragePermissionError,
    StorageValidationError,
    
    # Type aliases
    CollectionPath,
    DocumentID,
    QueryFilter,
    StorageData,
    
    # Backward compatibility
    DocumentResult,
)

__all__ = [
    # Core types
    'WriteMode',
    'StorageOperation', 
    'StorageResult',
    'StorageConfig',
    
    # Exceptions
    'StorageError',
    'StorageConnectionError',
    'StorageConfigurationError',
    'StorageNotFoundError',
    'StoragePermissionError',
    'StorageValidationError',
    
    # Type aliases
    'CollectionPath',
    'DocumentID',
    'QueryFilter',
    'StorageData',
    
    # Backward compatibility
    'DocumentResult',
]
