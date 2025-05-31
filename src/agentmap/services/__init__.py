"""
Services module for AgentMap.

Provides centralized services for common functionality like LLM calling and storage operations.
"""

from agentmap.services.llm_service import LLMService, LLMServiceUser
from agentmap.services.node_registry_service import NodeRegistryService, NodeRegistryUser
from agentmap.services.logging_service import LoggingService
from agentmap.services.config import AppConfigService, StorageConfigService, ConfigService

# Storage services and types
from agentmap.services.storage import (
    # Services
    BaseStorageService,
    StorageServiceManager,
    
    # Protocols
    StorageService,
    StorageServiceUser,
    StorageReader,
    StorageWriter,
    
    # Specific service user protocols
    CSVServiceUser,
    JSONServiceUser,
    FileServiceUser,
    VectorServiceUser,
    MemoryServiceUser,
    
    # Types
    WriteMode,
    StorageResult,
    StorageConfig,
    
    # Exceptions
    StorageError,
    StorageServiceError,
    
    # Backward compatibility
    DocumentResult,
)

# Storage service injection
from agentmap.services.storage.injection import (
    inject_storage_services,
    requires_storage_services,
    get_required_service_types,
    StorageServiceInjectionError
)

from agentmap.exceptions import (
    LLMServiceError,
    LLMProviderError, 
    LLMConfigurationError,
    LLMDependencyError
)

__all__ = [
    # Services
    'AppConfigService',
    'BaseStorageService',
    'LLMService',
    'LoggingService',
    'NodeRegistryService',
    'StorageConfigService',
    'StorageServiceManager',

    # Protocols
    'LLMServiceUser',
    'NodeRegistryUser',
    'StorageServiceUser',
    'StorageService',
    'StorageReader',
    'StorageWriter',
    
    # Specific service user protocols
    'CSVServiceUser',
    'JSONServiceUser',
    'FileServiceUser',
    'VectorServiceUser',
    'MemoryServiceUser',
    
    # Service injection
    'inject_storage_services',
    'requires_storage_services',
    'get_required_service_types',
    'StorageServiceInjectionError',

    # Storage types (convenience exports)
    'WriteMode',
    'StorageResult',
    'StorageConfig',
    'DocumentResult',
    'StorageError',
    'StorageServiceError',

    # LLM Errors
    'LLMServiceError',
    'LLMProviderError',
    'LLMConfigurationError', 
    'LLMDependencyError'
]