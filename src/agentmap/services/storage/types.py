"""
Storage types compatibility module.

This module maintains backward compatibility by re-exporting types that have been
moved to their proper locations in the architecture.

Pure data types have been moved to models.storage.
Exceptions remain in services.storage.exceptions.
"""

# Import pure data types from models (where they belong)
from agentmap.models.storage import (
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

# Import exceptions from services (where they belong)
from agentmap.services.storage.exceptions import (
    StorageConfigurationError,
    StorageConnectionError,
    StorageError,
    StorageNotFoundError,
    StoragePermissionError,
    StorageProviderError,
    StorageServiceConfigurationError,
    StorageServiceError,
    StorageServiceNotAvailableError,
    StorageValidationError,
)

# Re-export everything for backward compatibility
__all__ = [
    # Pure data types (from models)
    "WriteMode",
    "StorageOperation",
    "StorageResult",
    "StorageConfig",
    "CollectionPath",
    "DocumentID",
    "QueryFilter",
    "StorageData",
    "DocumentResult",
    # Exceptions (from services)
    "StorageError",
    "StorageConnectionError",
    "StorageConfigurationError",
    "StorageNotFoundError",
    "StoragePermissionError",
    "StorageValidationError",
    "StorageServiceError",
    "StorageProviderError",
    "StorageServiceConfigurationError",
    "StorageServiceNotAvailableError",
]
