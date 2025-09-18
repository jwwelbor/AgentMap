"""
Runtime API Exceptions

These exceptions provide clear domain errors for the AgentMap runtime API.
They inherit from the base AgentMap exception hierarchy for consistency.
"""

from typing import Optional

from agentmap.exceptions.base_exceptions import AgentMapException


class AgentMapError(AgentMapException):
    """Base class for all AgentMap domain errors in the runtime API."""


class AgentMapNotInitialized(AgentMapError):
    """Raised when the availability cache has not been created/validated."""

    def __init__(
        self,
        message: str = "AgentMap runtime is not initialized. Call ensure_initialized() first.",
    ):
        super().__init__(message)


class GraphNotFound(AgentMapError):
    """Raised when a requested graph cannot be located/resolved."""

    def __init__(self, graph_name: str, detail: Optional[str] = None):
        msg = f"Graph not found: {graph_name}"
        if detail:
            msg += f" ({detail})"
        super().__init__(msg)
        self.graph_name = graph_name


class InvalidInputs(AgentMapError):
    """Raised when provided inputs fail validation for a graph."""

    def __init__(self, reason: str):
        super().__init__(f"Invalid inputs: {reason}")
        self.reason = reason
