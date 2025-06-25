class AgentMapException(Exception):
    """Base exception for all AgentMap exceptions."""


class ConfigurationException(AgentMapException):
    """Exception raised when there's a configuration error."""
