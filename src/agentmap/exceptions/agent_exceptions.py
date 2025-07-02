from typing import Any, Dict

from agentmap.exceptions.base_exceptions import AgentMapException


class AgentError(AgentMapException):
    """Base class for agent-related exceptions."""


class AgentNotFoundError(AgentError):
    """Raised when an agent type is not found in the registry."""


class AgentInitializationError(AgentError):
    """Raised when an agent fails to initialize properly."""


class ExecutionInterruptedException(AgentError):
    """Raised when execution is interrupted for human interaction."""

    def __init__(
        self, thread_id: str, interaction_request: Any, checkpoint_data: Dict[str, Any]
    ):
        self.thread_id = thread_id
        self.interaction_request = interaction_request
        self.checkpoint_data = checkpoint_data
        super().__init__(
            f"Execution interrupted for human interaction in thread: {thread_id}"
        )
