"""
Services module for AgentMap.

Provides centralized services for common functionality like LLM calling and storage operations.
"""

from agentmap.services.llm_service import LLMService, LLMServiceUser
from agentmap.services.node_registry_service import NodeRegistryService, NodeRegistryUser

# Storage types for convenience
from agentmap.services.storage import (
    WriteMode,
    StorageResult,
    StorageError,
    DocumentResult,  # Backward compatibility
)

from agentmap.exceptions import (
    LLMServiceError,
    LLMProviderError, 
    LLMConfigurationError,
    LLMDependencyError
)

__all__ = [
    #services
    'LLMService',
    'NodeRegistryService',

    #Protocols
    'LLMServiceUser',
    'NodeRegistryUser',

    # Storage types (convenience exports)
    'WriteMode',
    'StorageResult',
    'DocumentResult',
    'StorageError',

    #Errors
    'LLMServiceError',
    'LLMProviderError',
    'LLMConfigurationError', 
    'LLMDependencyError'
]