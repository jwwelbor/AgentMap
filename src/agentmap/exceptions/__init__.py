"""
Common exceptions for the AgentMap module.
"""
from agentmap.exceptions.base_exceptions import ConfigurationException

from agentmap.exceptions.agent_exceptions import (
    AgentError,
    AgentInitializationError,
    AgentNotFoundError
)

from agentmap.exceptions.graph_exceptions import (
    GraphBuildingError,
    InvalidEdgeDefinitionError
)

from agentmap.exceptions.storage_exceptions import (
    CollectionNotFoundError,
    DocumentNotFoundError,
    StorageAuthenticationError,
    StorageConnectionError,
    StorageConfigurationError,
    StorageOperationError
)                                                

from agentmap.exceptions.service_exceptions import (
    LLMServiceError, 
    LLMProviderError, 
    LLMConfigurationError,
    LLMDependencyError
)


# Re-export at module level
__all__ = [
    'AgentError',
    'AgentNotFoundError', 
    'AgentInitializationError',
    'CollectionNotFoundError',
    'ConfigurationException',
    'DocumentNotFoundError',
    'GraphBuildingError',
    'InvalidEdgeDefinitionError',
    'LLMServiceError', 
    'LLMProviderError', 
    'LLMConfigurationError',
    'LLMDependencyError',   
    'StorageAuthenticationError',
    'StorageConnectionError',
    'StorageConfigurationError',
    'StorageOperationError',
]   