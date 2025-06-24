from agentmap.exceptions.base_exceptions import AgentMapException


class AgentError(AgentMapException):
    """Base class for agent-related exceptions."""



class AgentNotFoundError(AgentError):
    """Raised when an agent type is not found in the registry."""



class AgentInitializationError(AgentError):
    """Raised when an agent fails to initialize properly."""

