# src/agentmap/exceptions/messaging_exceptions.py

from agentmap.exceptions.base_exceptions import AgentMapException


class MessagingServiceError(AgentMapException):
    """Base class for messaging service exceptions."""

    pass


class MessagingServiceUnavailableError(MessagingServiceError):
    """Raised when messaging service or provider is not available."""

    pass


class MessagingOperationError(MessagingServiceError):
    """Raised when a messaging operation fails."""

    pass


class MessagingConnectionError(MessagingServiceError):
    """Raised when connection to messaging provider fails."""

    pass
