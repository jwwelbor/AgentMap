"""
SuspendAgent: generic pause/suspend node for long-running or out-of-band work.

Uses LangGraph's interrupt() function to properly suspend execution.
- On first call: Raises GraphInterrupt, LangGraph saves checkpoint
- On resume: Returns the resume value, allowing node to complete
- HumanAgent should subclass this and use interrupt() with interaction metadata.

Enhanced with optional messaging capabilities:
- Publishes suspension messages when workflow suspends
- Publishes resume messages when workflow resumes
- Publishes graph messages to trigger external processes
- Returns raw resume values without wrapper structure
"""

import asyncio
import time
import uuid
from datetime import datetime
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

        Enhanced with optional messaging and flexible return values.

        On first call:
          - Publishes graph message (if configured)
          - Publishes suspension message (if configured)
          - Raises GraphInterrupt, LangGraph saves checkpoint

        On resume:
          - Returns the resume value from interrupt()
          - Publishes resume message (if configured)
          - Returns raw resume value (not wrapped)

        This allows external processes or human interaction to resume execution.
        """
        thread_id = self._get_or_create_thread_id()
        suspend_timestamp = time.time()

        # Publish graph message before suspension (if configured)
        self._publish_graph_message(thread_id, inputs, suspend_timestamp)

        # Publish suspension message (if configured)
        self._publish_suspension_message(thread_id, inputs)

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

        # Publish resume message (if configured)
        self._publish_resume_message(thread_id, resume_value, suspend_timestamp)

        # Return raw resume value (not wrapped in dict)
        return resume_value

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

    # --- Messaging methods ---

    def _publish_suspension_message(
        self, thread_id: str, inputs: Dict[str, Any]
    ) -> None:
        """
        Publish suspension message if configured.

        Args:
            thread_id: Thread identifier for suspended workflow
            inputs: Original inputs to the suspended node

        Raises:
            ValueError: If messaging requested but service not configured

        Note: Messaging failures (not config errors) are logged but don't prevent suspension.
        """
        if "send_suspend_message" not in self.context:
            return

        # Configuration error - must raise
        if self._messaging_service is None:
            self.log_error(
                f"Cannot send suspend message: messaging service not configured for '{self.name}'"
            )
            raise ValueError(
                f"Messaging service required but not configured for agent '{self.name}'"
            )

        # Messaging failures - log but don't raise
        try:
            payload = self._build_suspension_payload(thread_id, inputs)
            template_name = self.context.get(
                "suspend_message_template", "default_suspend"
            )

            # Apply template with variables
            message_data = self._messaging_service.apply_template(
                template_name, payload
            )

            # Publish message asynchronously
            topic = self.context.get("suspend_message_topic", "workflow_events")
            asyncio.create_task(
                self._messaging_service.publish_message(
                    topic=topic,
                    message_type="workflow_suspended",
                    payload=message_data,
                    thread_id=thread_id,
                )
            )

            self.log_info(f"Published suspension message for thread {thread_id}")

        except Exception as e:
            self.log_error(f"Failed to publish suspension message: {e}")
            # Don't raise - messaging failure should not prevent suspension

    def _publish_resume_message(
        self, thread_id: str, resume_value: Any, suspend_timestamp: float
    ) -> None:
        """
        Publish resume message if configured.

        Args:
            thread_id: Thread identifier for resumed workflow
            resume_value: Value returned from interrupt()
            suspend_timestamp: Timestamp when suspension occurred

        Raises:
            ValueError: If messaging requested but service not configured

        Note: Messaging failures (not config errors) are logged but don't prevent resume.
        """
        if "send_resume_message" not in self.context:
            return

        # Configuration error - must raise
        if self._messaging_service is None:
            self.log_error(
                f"Cannot send resume message: messaging service not configured for '{self.name}'"
            )
            raise ValueError(
                f"Messaging service required but not configured for agent '{self.name}'"
            )

        # Messaging failures - log but don't raise
        try:
            resume_timestamp = time.time()
            duration = resume_timestamp - suspend_timestamp

            payload = self._build_resume_payload(thread_id, resume_value, duration)
            template_name = self.context.get(
                "resume_message_template", "default_resume"
            )

            message_data = self._messaging_service.apply_template(
                template_name, payload
            )

            topic = self.context.get("resume_message_topic", "workflow_events")
            asyncio.create_task(
                self._messaging_service.publish_message(
                    topic=topic,
                    message_type="workflow_resumed",
                    payload=message_data,
                    thread_id=thread_id,
                )
            )

            self.log_info(
                f"Published resume message for thread {thread_id} (duration: {duration:.2f}s)"
            )

        except Exception as e:
            self.log_error(f"Failed to publish resume message: {e}")
            # Don't raise - messaging failure should not prevent resume

    def _publish_graph_message(
        self, thread_id: str, inputs: Dict[str, Any], suspend_timestamp: float
    ) -> None:
        """
        Publish graph message if configured.

        Args:
            thread_id: Thread identifier for workflow
            inputs: Original inputs to the node
            suspend_timestamp: Timestamp when suspension will occur

        Raises:
            ValueError: If messaging requested but service not configured

        Note: Messaging failures (not config errors) are logged but don't prevent suspension.
        """
        if "send_graph_message" not in self.context:
            return

        # Configuration error - must raise
        if self._messaging_service is None:
            self.log_error(
                f"Cannot send graph message: messaging service not configured for '{self.name}'"
            )
            raise ValueError(
                f"Messaging service required but not configured for agent '{self.name}'"
            )

        # Messaging failures - log but don't raise
        try:
            payload = self._build_graph_payload(thread_id, inputs)
            template_name = self.context.get("graph_message_template", "default_graph")

            # Apply template with variables
            message_data = self._messaging_service.apply_template(
                template_name, payload
            )

            # Publish message asynchronously
            topic = self.context.get("graph_message_topic", "workflow_events")
            asyncio.create_task(
                self._messaging_service.publish_message(
                    topic=topic,
                    message_type="workflow_graph_event",
                    payload=message_data,
                    thread_id=thread_id,
                )
            )

            self.log_info(f"Published graph message for thread {thread_id}")

        except Exception as e:
            self.log_error(f"Failed to publish graph message: {e}")
            # Don't raise - messaging failure should not prevent suspension

    def _build_suspension_payload(
        self, thread_id: str, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build payload for suspension message.

        Args:
            thread_id: Thread identifier
            inputs: Original inputs to the node

        Returns:
            Dictionary with suspension event data
        """
        tracker = self.current_execution_tracker
        workflow_name = (
            getattr(tracker, "workflow_name", "unknown") if tracker else "unknown"
        )
        graph_name = getattr(tracker, "graph_name", "unknown") if tracker else "unknown"

        return {
            "event_type": "workflow_suspended",
            "thread_id": thread_id,
            "node_name": self.name,
            "workflow": workflow_name,
            "graph": graph_name,
            "timestamp": datetime.utcnow().isoformat(),
            "inputs": inputs,
            "context": self.context,
        }

    def _build_resume_payload(
        self, thread_id: str, resume_value: Any, duration: float
    ) -> Dict[str, Any]:
        """
        Build payload for resume message (auto-resume via serverless).

        Args:
            thread_id: Thread identifier
            resume_value: Value returned from interrupt()
            duration: Duration of suspension in seconds

        Returns:
            Dictionary with resume event data for serverless auto-resume
        """
        tracker = self.current_execution_tracker
        workflow_name = (
            getattr(tracker, "workflow_name", "unknown") if tracker else "unknown"
        )
        graph_name = getattr(tracker, "graph_name", "unknown") if tracker else "unknown"

        return {
            "event_type": "workflow_resumed",
            "action": "resume",  # Tells serverless handler to resume
            "thread_id": thread_id,
            "resume_value": resume_value,
            "node_name": self.name,
            "workflow": workflow_name,
            "graph": graph_name,
            "timestamp": datetime.utcnow().isoformat(),
            "suspension_duration_seconds": duration,
            "context": self.context,
        }

    def _build_graph_payload(
        self, thread_id: str, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build payload for graph message (triggers another AgentMap graph).

        Args:
            thread_id: Thread identifier
            inputs: Original inputs to the node

        Returns:
            Dictionary with graph event data for serverless consumption
        """
        tracker = self.current_execution_tracker
        workflow_name = (
            getattr(tracker, "workflow_name", "unknown") if tracker else "unknown"
        )
        graph_name = getattr(tracker, "graph_name", "unknown") if tracker else "unknown"

        return {
            "event_type": "workflow_graph_trigger",
            "graph": graph_name,  # Which graph to execute (serverless uses this)
            "state": inputs,  # Renamed to 'state' for serverless handler compatibility
            "thread_id": thread_id,
            "node_name": self.name,
            "workflow": workflow_name,
            "timestamp": datetime.utcnow().isoformat(),
            "context": self.context,
        }

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
