"""
Human agent for implementing human-in-the-loop functionality.

This agent pauses workflow execution for human interaction by saving checkpoints
and raising ExecutionInterruptedException.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import (
    CheckpointCapableAgent,
    GraphCheckpointServiceProtocol,
)
from agentmap.services.state_adapter_service import StateAdapterService


class HumanAgent(BaseAgent, CheckpointCapableAgent):
    """Agent that pauses execution for human interaction."""

    def __init__(
        self,
        name: str,
        prompt: str,
        interaction_type: str = "text_input",
        options: Optional[List[str]] = None,
        timeout_seconds: Optional[int] = None,
        default_action: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only
        logger: Optional[logging.Logger] = None,
        execution_tracker_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
    ):
        """
        Initialize the human agent.

        Args:
            name: Name of the agent node
            prompt: Prompt to show to the human
            interaction_type: Type of interaction (text_input, approval, choice, edit, conversation)
            options: Options for choice-based interactions
            timeout_seconds: Optional timeout for the interaction
            default_action: Default action if timeout occurs
            context: Additional context including input/output configuration
            logger: Logger instance
            execution_tracker_service: ExecutionTrackingService instance
            state_adapter_service: StateAdapterService instance
        """
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # Parse interaction type
        try:
            self.interaction_type = InteractionType(interaction_type.lower())
        except ValueError:
            # Default to text_input if invalid type provided
            self.interaction_type = InteractionType.TEXT_INPUT
            self.log_warning(
                f"Invalid interaction type '{interaction_type}', defaulting to 'text_input'"
            )

        # Store interaction configuration
        self.options = options or []
        self.timeout_seconds = timeout_seconds
        self.default_action = default_action

        # Services configured post-construction
        self._checkpoint_service: Optional[GraphCheckpointServiceProtocol] = None

    def configure_checkpoint_service(
        self, checkpoint_service: GraphCheckpointServiceProtocol
    ) -> None:
        """
        Configure graph checkpoint service for state persistence.

        Args:
            checkpoint_service: GraphCheckpointService instance
        """
        self._checkpoint_service = checkpoint_service
        self.log_debug("Graph checkpoint service configured")

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs by creating an interaction request and pausing execution.

        Args:
            inputs: Dictionary containing input values from input_fields

        Returns:
            Never returns - always raises ExecutionInterruptedException
        """
        self.log_info(f"[HumanAgent] {self.name} initiating human interaction")

        # Get thread ID from execution tracker or create new one
        thread_id = self._get_thread_id()

        # Format the prompt with any input values
        formatted_prompt = self._format_prompt_with_inputs(inputs)

        # Create human interaction request
        interaction_request = HumanInteractionRequest(
            thread_id=thread_id,
            node_name=self.name,
            interaction_type=self.interaction_type,
            prompt=formatted_prompt,
            context=inputs,  # Pass inputs as context for the interaction
            options=self.options,
            timeout_seconds=self.timeout_seconds,
        )

        # Prepare checkpoint data
        checkpoint_data = {
            "inputs": inputs,
            "node_name": self.name,
            "agent_context": self.context,
        }

        # Include serialized execution tracker if available
        if self.current_execution_tracker and self.execution_tracking_service:
            tracker_data = self.execution_tracking_service.serialize_tracker(
                self.current_execution_tracker
            )
            checkpoint_data["execution_tracker"] = tracker_data

        # Save checkpoint if service is configured
        if self._checkpoint_service:
            metadata = {
                "interaction_request": {
                    "id": str(interaction_request.id),
                    "type": interaction_request.interaction_type.value,
                    "prompt": interaction_request.prompt,
                    "options": interaction_request.options,
                    "timeout_seconds": interaction_request.timeout_seconds,
                },
                "agent_config": {
                    "name": self.name,
                    "interaction_type": self.interaction_type.value,
                    "default_action": self.default_action,
                },
            }

            result = self._checkpoint_service.save_checkpoint(
                thread_id=thread_id,
                node_name=self.name,
                checkpoint_type="human_intervention",
                metadata=metadata,
                execution_state=checkpoint_data,
            )

            if result.success:
                self.log_info(f"Checkpoint saved for thread {thread_id}")
            else:
                self.log_warning(f"Failed to save checkpoint: {result.error}")
        else:
            self.log_warning("No checkpoint service configured, checkpoint not saved")

        # Log the interruption
        self.log_info(
            f"[HumanAgent] Execution interrupted for human interaction. "
            f"Thread ID: {thread_id}, Request ID: {interaction_request.id}"
        )

        # Raise exception to pause execution
        raise ExecutionInterruptedException(
            thread_id=thread_id,
            interaction_request=interaction_request,
            checkpoint_data=checkpoint_data,
        )

    def _get_thread_id(self) -> str:
        """
        Get the current thread ID from execution tracker or create a new one.

        Returns:
            Thread ID string
        """
        # Try to get thread ID from execution tracker
        if self.current_execution_tracker:
            thread_id = getattr(self.current_execution_tracker, "thread_id", None)
            if thread_id:
                return thread_id

        # Generate new thread ID if none exists
        return str(uuid.uuid4())

    def _format_prompt_with_inputs(self, inputs: Dict[str, Any]) -> str:
        """
        Format the prompt with input values.

        Args:
            inputs: Input values dictionary

        Returns:
            Formatted prompt string
        """
        if not inputs:
            return self.prompt

        try:
            # Simple string formatting with inputs
            return self.prompt.format(**inputs)
        except (KeyError, ValueError):
            # If formatting fails, return original prompt
            self.log_debug("Prompt formatting failed, using original prompt")
            return self.prompt

    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """
        Provide HumanAgent-specific service information for debugging.

        Returns:
            Dictionary with human agent capabilities and configuration
        """
        return {
            "services": {
                "supports_human_interaction": True,
                "checkpoint_service_configured": self._checkpoint_service is not None,
                "checkpoint_persistence_enabled": self._checkpoint_service is not None,
            },
            "capabilities": {
                "interaction_types": [t.value for t in InteractionType],
                "current_interaction_type": self.interaction_type.value,
                "supports_timeout": self.timeout_seconds is not None,
                "supports_default_action": self.default_action is not None,
                "supports_choice_options": len(self.options) > 0,
            },
            "agent_behavior": {
                "execution_type": "interrupt_for_human",
                "checkpoint_enabled": self._checkpoint_service is not None,
                "interaction_method": self.interaction_type.value,
                "timeout_seconds": self.timeout_seconds,
                "default_action": self.default_action,
            },
        }
