"""
Common exceptions for the AgentMap module.
"""

from agentmap.exceptions.agent_exceptions import (
    AgentError,
    AgentInitializationError,
    AgentNotFoundError,
)
from agentmap.exceptions.base_exceptions import ConfigurationException
from agentmap.exceptions.graph_exceptions import (
    GraphBuildingError,
    InvalidEdgeDefinitionError,
)
from agentmap.exceptions.service_exceptions import (
    FunctionResolutionException,
    LLMConfigurationError,
    LLMDependencyError,
    LLMProviderError,
    LLMServiceError,
)
from agentmap.exceptions.storage_exceptions import (
    CollectionNotFoundError,
    DocumentNotFoundError,
    StorageAuthenticationError,
    StorageConfigurationError,
    StorageConnectionError,
    StorageOperationError,
)
from agentmap.exceptions.validation_exceptions import ValidationException

# Re-export at module level
__all__ = [
    "AgentError",
    "AgentNotFoundError",
    "AgentInitializationError",
    "CollectionNotFoundError",
    "ConfigurationException",
    "DocumentNotFoundError",
    "FunctionResolutionException",
    "GraphBuildingError",
    "InvalidEdgeDefinitionError",
    "LLMServiceError",
    "LLMProviderError",
    "LLMConfigurationError",
    "LLMDependencyError",
    "StorageAuthenticationError",
    "StorageConnectionError",
    "StorageConfigurationError",
    "StorageOperationError",
    "ValidationException",  # for backwards compatibility and consistency
]
