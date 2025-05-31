class AgentMapException(Exception):
    """Base exception for all AgentMap exceptions."""
    pass

class ConfigurationException(AgentMapException):
    """Exception raised when there's a configuration error."""
    pass

