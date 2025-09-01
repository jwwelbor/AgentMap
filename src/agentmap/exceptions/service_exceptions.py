"""
LLM Service exceptions for AgentMap.
"""

from agentmap.exceptions.base_exceptions import (
    AgentMapException,
    ConfigurationException,
)


class LLMServiceError(AgentMapException):
    """Base exception for LLM service errors."""


class LLMProviderError(LLMServiceError):
    """Exception raised when there's an error with a specific LLM provider."""


class LLMConfigurationError(LLMServiceError):
    """Exception raised when there's a configuration error."""


class LLMDependencyError(LLMServiceError):
    """Exception raised when required dependencies are missing."""


class StorageConfigurationNotAvailableException(ConfigurationException):
    """Exception raised when storage configuration is not available or invalid."""


class LoggingNotConfiguredException(AgentMapException):
    """Exception raised when trying to use logging service before initialization."""


class FunctionResolutionException(AgentMapException):
    """Exception raised when a function cannot be resolved."""


class CacheNotFoundError(AgentMapException):
    """Exception raised when the availability cache file doesn't exist."""
