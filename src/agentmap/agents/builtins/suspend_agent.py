"""
SuspendAgent: generic pause/suspend node for long-running or out-of-band work.

- Saves a checkpoint (if configured) with minimal metadata.
- Raises ExecutionInterruptedException WITHOUT a HumanInteractionRequest.
- HumanAgent should subclass this and pass an interaction_request to _interrupt().
"""

import uuid
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import (
    CheckpointCapableAgent,
    GraphCheckpointServiceProtocol,
)
from agentmap.services.state_adapter_service import StateAdapterService


class SuspendAgent(BaseAgent, CheckpointCapableAgent):
    """
    Base agent that suspends workflow execution.

    Use cases:
      - hand-off to an external process/service
      - long-running batch or subgraph
      - wait-until-some-state-is-mutated externally
    """

    def __init__(
        self,
        execution_tracking_service: ExecutionTrackingService,
        state_adapter_service: StateAdapterService,
        name: str,
        prompt: str = "suspend",
        *,
        reason: Optional[str] = None,
        external_ref: Optional[str] = None,
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
        self.reason = reason
        self.external_ref = external_ref
        self._checkpoint_service: Optional[GraphCheckpointServiceProtocol] = None

    # CheckpointCapableAgent
    def configure_checkpoint_service(
        self, checkpoint_service: GraphCheckpointServiceProtocol
    ) -> None:
        """Inject the checkpoint service."""
        self._checkpoint_service = checkpoint_service
        self.log_debug("Graph checkpoint service configured (SuspendAgent)")

    # --- Core execution ---
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Suspend execution. Always raises ExecutionInterruptedException.

        Contract:
          - Build checkpoint_data with inputs, agent_context and (if present) execution_tracker
          - Persist checkpoint (if service configured)
          - Raise ExecutionInterruptedException(thread_id=..., interaction_request=None, checkpoint_data=...)
        """
        self.log_info(f"[SuspendAgent] {self.name} suspending execution")

        thread_id = self._get_or_create_thread_id()
        checkpoint_data = self._build_checkpoint_data(inputs)

        metadata = {
            "agent_config": {
                "name": self.name,
                "reason": self.reason,
                "external_ref": self.external_ref,
            },
            "suspend_kind": "external_or_long_running",
        }

        self._save_checkpoint(
            thread_id=thread_id,
            node_name=self.name,
            checkpoint_type="suspend",
            metadata=metadata,
            execution_state=checkpoint_data,
        )

        self._interrupt(
            thread_id=thread_id,
            checkpoint_data=checkpoint_data,
            interaction_request=None,
        )

    # --- Protected helpers for subclasses (HumanAgent will reuse these) ---
    def _interrupt(
        self,
        *,
        thread_id: str,
        checkpoint_data: Dict[str, Any],
        interaction_request: Optional[Any],
    ) -> None:
        """Raise the standardized interruption exception."""
        self.log_info(
            f"[SuspendAgent] Raising interrupt (thread={thread_id}, human_request={interaction_request is not None})"
        )
        raise ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

    def _save_checkpoint(
        self,
        *,
        thread_id: str,
        node_name: str,
        checkpoint_type: str,
        metadata: Dict[str, Any],
        execution_state: Dict[str, Any],
    ) -> None:
        if not self._checkpoint_service:
            self.log_debug("No checkpoint service configured; skipping checkpoint save")
            raise RuntimeError("No checkpoint service configured")
        result = self._checkpoint_service.save_checkpoint(
            thread_id=thread_id,
            node_name=node_name,
            checkpoint_type=checkpoint_type,
            metadata=metadata,
            execution_state=execution_state,
        )
        if result.success:
            self.log_info(f"Checkpoint saved for thread {thread_id}")
        else:
            self.log_warning(f"Failed to save checkpoint: {result.error}")

    def _build_checkpoint_data(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        data = {
            "inputs": inputs,
            "node_name": self.name,
            "agent_context": self.context,
        }
        if self.current_execution_tracker and self.execution_tracking_service:
            tracker = self.current_execution_tracker
            data["execution_tracker"] = (
                self.execution_tracking_service.serialize_tracker(tracker)
            )
        return data

    def _get_or_create_thread_id(self) -> str:
        tracker = self.current_execution_tracker
        if tracker:
            tid = getattr(tracker, "thread_id", None)
            if tid:
                return tid
        return str(uuid.uuid4())

    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        return {
            "services": {
                "checkpoint_service_configured": self._checkpoint_service is not None,
            },
            "agent_behavior": {
                "execution_type": "interrupt_suspend",
                "reason": self.reason,
                "external_ref": self.external_ref,
            },
            "protocols": {
                "implements_checkpoint_capable": True,
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
