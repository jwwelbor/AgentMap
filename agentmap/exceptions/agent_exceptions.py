class AgentError(Exception):
    """Base class for agent-related exceptions."""
    pass

class AgentNotFoundError(AgentError):
    """Raised when an agent type is not found in the registry."""
    pass

class AgentInitializationError(AgentError):
    """Raised when an agent fails to initialize properly."""
    pass
