"""
Storage services module for AgentMap.

This module provides storage services and types for centralized storage operations.
Following the service-oriented architecture pattern, all storage-related functionality
is organized here.
"""

from typing import TYPE_CHECKING

from .base import BaseStorageService
# CSVStorageService is lazy-loaded to defer pandas import
from .file_service import FileStorageService
from .json_service import JSONStorageService
from .manager import StorageServiceManager
from .memory_service import MemoryStorageService
from .protocols import (
    StorageReader,
    StorageService,
    StorageServiceFactory,
    StorageWriter,
)
from .types import (  # Core types; Exceptions; Service-specific exceptions; Type aliases; Backward compatibility
    CollectionPath,
    DocumentID,
    DocumentResult,
    QueryFilter,
    StorageConfig,
    StorageConfigurationError,
    StorageConnectionError,
    StorageData,
    StorageError,
    StorageNotFoundError,
    StorageOperation,
    StoragePermissionError,
    StorageProviderError,
    StorageResult,
    StorageServiceConfigurationError,
    StorageServiceError,
    StorageServiceNotAvailableError,
    StorageValidationError,
    WriteMode,
)

# Lazy-loaded modules to avoid importing heavy dependencies at package import time
# CSVStorageService imports pandas
# VectorStorageService imports langchain vector dependencies
# BlobStorageService imports protocols which imports langchain_core.tools
_LAZY_IMPORTS = {
    "CSVStorageService": ("csv_service", "CSVStorageService"),
    "VectorStorageService": ("vector.service", "VectorStorageService"),
    "BlobStorageService": ("blob_storage_service", "BlobStorageService"),
}

if TYPE_CHECKING:
    from agentmap.services.storage.blob_storage_service import BlobStorageService
    from agentmap.services.storage.csv_service import CSVStorageService
    from agentmap.services.storage.manager import StorageServiceManager
    from agentmap.services.storage.vector.service import VectorStorageService


__all__ = [
    # Core types
    "WriteMode",
    "StorageOperation",
    "StorageResult",
    "StorageConfig",
    # Exceptions
    "StorageError",
    "StorageConnectionError",
    "StorageConfigurationError",
    "StorageNotFoundError",
    "StoragePermissionError",
    "StorageValidationError",
    # Service-specific exceptions
    "StorageServiceError",
    "StorageProviderError",
    "StorageServiceConfigurationError",
    "StorageServiceNotAvailableError",
    # Protocols
    "StorageReader",
    "StorageWriter",
    "StorageService",
    "StorageServiceFactory",
    # Classes
    "BaseStorageService",
    "StorageServiceManager",
    "CSVStorageService",
    "JSONStorageService",
    "VectorStorageService",
    "register_all_providers",
    # Type aliases
    "CollectionPath",
    "DocumentID",
    "QueryFilter",
    "StorageData",
    # Backward compatibility
    "DocumentResult",
]

# Import connector modules so they can be patched in tests
from . import (
    aws_s3_connector,
    azure_blob_connector,
    gcp_storage_connector,
    local_file_connector,
)

# BlobStorageService is lazy-loaded via __getattr__ to avoid importing langchain_core.tools
# Add to exports list
__all__.append("BlobStorageService")


def __getattr__(name: str):
    """Lazy import for heavy modules to improve startup performance."""
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        import importlib
        module = importlib.import_module(f".{module_name}", __package__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def register_all_providers(manager: "StorageServiceManager") -> None:
    """
    Register all available storage service providers.

    This function auto-registers all concrete storage service implementations
    with the storage service manager.

    Args:
        manager: StorageServiceManager instance to register providers with
    """
    # Import heavy services lazily when actually registering
    from .csv_service import CSVStorageService as _CSVStorageService
    from .vector.service import VectorStorageService as _VectorStorageService

    # Register services
    manager.register_provider("csv", _CSVStorageService)
    manager.register_provider("json", JSONStorageService)
    manager.register_provider("memory", MemoryStorageService)
    manager.register_provider("file", FileStorageService)
    manager.register_provider("vector", _VectorStorageService)
    # manager.register_provider("firebase", FirebaseStorageService)
