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
    BundleLoadError,
    GraphBuildingError,
    InvalidEdgeDefinitionError,
)
from agentmap.exceptions.messaaging_exceptions import (
    MessagingConnectionError,
    MessagingOperationError,
    MessagingServiceError,
    MessagingServiceUnavailableError,
)
from agentmap.exceptions.runtime_exceptions import (
    AgentMapError,
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
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
    StorageError,
    StorageNotFoundError,
    StorageOperationError,
    StoragePermissionError,
    StorageProviderError,
    StorageServiceConfigurationError,
    StorageServiceError,
    StorageServiceNotAvailableError,
    StorageValidationError,
)
from agentmap.exceptions.validation_exceptions import ValidationException

# Re-export at module level
__all__ = [
    "AgentError",
    "AgentNotFoundError",
    "AgentInitializationError",
    "BundleLoadError",
    "CollectionNotFoundError",
    "ConfigurationException",
    "DocumentNotFoundError",
    "FunctionResolutionException",
    "GraphBuildingError",
    "MessagingConnectionError",
    "MessagingOperationError",
    "MessagingServiceError",
    "MessagingServiceUnavailableError",
    "InvalidEdgeDefinitionError",
    "LLMServiceError",
    "LLMProviderError",
    "LLMConfigurationError",
    "LLMDependencyError",
    "StorageAuthenticationError",
    "StorageConnectionError",
    "StorageConfigurationError",
    "StorageError",
    "StorageNotFoundError",
    "StorageOperationError",
    "StoragePermissionError",
    "StorageProviderError",
    "StorageServiceConfigurationError",
    "StorageServiceError",
    "StorageServiceNotAvailableError",
    "StorageValidationError",
    "ValidationException",  # for backwards compatibility and consistency
    # Runtime API exceptions
    "AgentMapError",
    "AgentMapNotInitialized",
    "GraphNotFound",
    "InvalidInputs",
]
