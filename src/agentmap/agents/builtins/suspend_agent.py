"""
SuspendAgent: generic pause/suspend node for long-running or out-of-band work.

Uses LangGraph's interrupt() function to properly suspend execution.
- On first call: Raises GraphInterrupt, LangGraph saves checkpoint
- On resume: Returns the resume value, allowing node to complete
- HumanAgent should subclass this and use interrupt() with interaction metadata.
"""

import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from langgraph.types import interrupt

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import MessagingCapableAgent
from agentmap.services.state_adapter_service import StateAdapterService

if TYPE_CHECKING:
    from agentmap.services.messaging.messaging_service import MessagingService


class SuspendAgent(BaseAgent, MessagingCapableAgent):
    """
    Base agent that suspends workflow execution using LangGraph's interrupt() pattern.

    Use cases:
      - hand-off to an external process/service
      - long-running batch or subgraph
      - wait-until-some-state-is-mutated externally

    On first call: Raises GraphInterrupt, LangGraph saves checkpoint automatically
    On resume: interrupt() returns the resume value, node completes
    """

    def __init__(
        self,
        execution_tracking_service: ExecutionTrackingService,
        state_adapter_service: StateAdapterService,
        name: str,
        prompt: str = "suspend",
        *,
        context: Optional[Dict[str, Any]] = None,
        logger=None,
    ):
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracking_service,
            state_adapter_service=state_adapter_service,
        )
        self._messaging_service: Optional["MessagingService"] = None

    # --- Core execution ---
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Suspend execution using LangGraph's interrupt() pattern.

        On first call: Raises GraphInterrupt, LangGraph saves checkpoint
        On resume: Returns the resume value and completes normally

        This allows external processes or human interaction to resume execution.
        """
        thread_id = self._get_or_create_thread_id()

        self.log_info(f"[SuspendAgent] {self.name} suspending execution")

        # Use LangGraph's interrupt() - pass metadata about the suspension
        # On first call: This raises GraphInterrupt
        # On resume: This returns the resume_value from Command(resume=value)
        resume_value = interrupt(
            {
                "type": "suspend",
                "node_name": self.name,
                "thread_id": thread_id,
                "inputs": inputs,
                "context": self.context,
            }
        )

        # This code only runs on resume!
        self.log_info(
            f"[SuspendAgent] Resumed with value: {resume_value} "
            f"(type: {type(resume_value).__name__})"
        )

        # Return a marker indicating suspension completed
        return {
            "resume_value": resume_value,
            "node_name": self.name,
        }

    # Protocol implementation (MessagingCapableAgent)
    def configure_messaging_service(
        self, messaging_service: "MessagingService"
    ) -> None:
        self._messaging_service = messaging_service
        if self._logger:
            self.log_debug("Messaging service configured for SuspendAgent")

    @property
    def messaging_service(self) -> "MessagingService":
        if self._messaging_service is None:
            raise ValueError(
                f"Messaging service not configured for agent '{self.name}'"
            )
        return self._messaging_service

    # --- Helper methods ---

    def _get_or_create_thread_id(self) -> str:
        tracker = self.current_execution_tracker
        if tracker:
            tid = getattr(tracker, "thread_id", None)
            if tid:
                return tid
        return str(uuid.uuid4())

    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        return {
            "agent_behavior": {
                "execution_type": "langgraph_interrupt",
                "reason": self.reason,
                "external_ref": self.external_ref,
            },
            "interrupt_pattern": {
                "uses_langgraph_interrupt": True,
                "manual_checkpoint": False,
            },
        }

    def _format_prompt_with_inputs(self, inputs: Dict[str, Any]) -> str:
        if not inputs:
            return self.prompt
        try:
            return self.prompt.format(**inputs)
        except Exception:
            self.log_debug("Prompt formatting failed, using original prompt")
            return self.prompt
