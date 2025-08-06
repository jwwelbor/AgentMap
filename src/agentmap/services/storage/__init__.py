"""
Storage services module for AgentMap.

This module provides storage services and types for centralized storage operations.
Following the service-oriented architecture pattern, all storage-related functionality
is organized here.
"""

from typing import TYPE_CHECKING

from .base import BaseStorageService
from .csv_service import CSVStorageService
from .file_service import FileStorageService
from .json_service import JSONStorageService
from .manager import StorageServiceManager
from .memory_service import MemoryStorageService
from .protocols import (  # StorageServiceUser,; New capability protocols; Legacy service user protocols (for backward compatibility); CSVServiceUser,; JSONServiceUser,; FileServiceUser,; VectorServiceUser,; MemoryServiceUser,
    CSVCapableAgent,
    FileCapableAgent,
    JSONCapableAgent,
    MemoryCapableAgent,
    StorageReader,
    StorageService,
    StorageServiceFactory,
    StorageWriter,
    VectorCapableAgent,
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
from .vector_service import VectorStorageService

if TYPE_CHECKING:
    from agentmap.services.storage.manager import StorageServiceManager


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
    # 'StorageServiceUser',
    "StorageServiceFactory",
    # New capability protocols
    "CSVCapableAgent",
    "JSONCapableAgent",
    "FileCapableAgent",
    "VectorCapableAgent",
    "MemoryCapableAgent",
    # Legacy service user protocols (for backward compatibility)
    # 'CSVServiceUser',
    # 'JSONServiceUser',
    # 'FileServiceUser',
    # 'VectorServiceUser',
    # 'MemoryServiceUser',
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

# Import blob storage service for completeness
from .blob_storage_service import BlobStorageService

# Add blob storage service to exports
__all__.append("BlobStorageService")


def register_all_providers(manager: "StorageServiceManager") -> None:
    """
    Register all available storage service providers.

    This function auto-registers all concrete storage service implementations
    with the storage service manager.

    Args:
        manager: StorageServiceManager instance to register providers with
    """
    # Register services
    manager.register_provider("csv", CSVStorageService)
    manager.register_provider("json", JSONStorageService)
    manager.register_provider("memory", MemoryStorageService)
    manager.register_provider("file", FileStorageService)
    manager.register_provider("vector", VectorStorageService)
    # manager.register_provider("firebase", FirebaseStorageService)
