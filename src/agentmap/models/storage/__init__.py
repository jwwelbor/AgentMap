"""
Storage models for AgentMap.

This module exports pure data types used across storage implementations.
All models are data containers with minimal behavior - business logic belongs in services.
"""

from .types import (
    CollectionPath,
    DocumentID,
    DocumentResult,
    QueryFilter,
    StorageConfig,
    StorageData,
    StorageOperation,
    StorageResult,
    WriteMode,
)

__all__ = [
    # Enums
    "WriteMode",
    "StorageOperation",
    # Data classes
    "StorageResult",
    "StorageConfig",
    # Type aliases
    "CollectionPath",
    "DocumentID",
    "QueryFilter",
    "StorageData",
    # Backward compatibility
    "DocumentResult",
]
