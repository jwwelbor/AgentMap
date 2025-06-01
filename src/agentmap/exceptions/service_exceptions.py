"""
LLM Service exceptions for AgentMap.
"""

from agentmap.exceptions.base_exceptions import AgentMapException, ConfigurationException


class LLMServiceError(AgentMapException):
    """Base exception for LLM service errors."""
    pass


class LLMProviderError(LLMServiceError):
    """Exception raised when there's an error with a specific LLM provider."""
    pass


class LLMConfigurationError(LLMServiceError):
    """Exception raised when there's a configuration error."""
    pass


class LLMDependencyError(LLMServiceError):
    """Exception raised when required dependencies are missing."""
    pass


class StorageConfigurationNotAvailableException(ConfigurationException):
    """Exception raised when storage configuration is not available or invalid."""
    pass


class LoggingNotConfiguredException(AgentMapException):
    """Exception raised when trying to use logging service before initialization."""
    pass