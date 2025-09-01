class AgentMapException(Exception):
    """Base exception for all AgentMap exceptions."""


class ConfigurationException(AgentMapException):
    """Exception raised when there's a configuration error."""


class InvalidPathError(AgentMapException):
    """Exception raised when a path is invalid or unsafe."""


class PathTraversalError(InvalidPathError):
    """Exception raised when path traversal is detected."""


class SystemPathError(InvalidPathError):
    """Exception raised when attempting to access dangerous system paths."""
