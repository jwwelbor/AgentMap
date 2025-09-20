# human_agent.py
import logging
from typing import Any, Dict, List, Optional

from agentmap.agents.builtins.suspend_agent import SuspendAgent
from agentmap.models.human_interaction import HumanInteractionRequest, InteractionType
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import (
    GraphCheckpointServiceProtocol,
)
from agentmap.services.state_adapter_service import StateAdapterService


class HumanAgent(SuspendAgent):  # inherited CheckpointCapableAgent
    """Agent that pauses execution for human interaction."""

    def __init__(
        self,
        execution_tracking_service: ExecutionTrackingService,
        state_adapter_service: StateAdapterService,
        name: str,
        prompt: str,
        interaction_type: str = "text_input",
        options: Optional[List[str]] = None,
        timeout_seconds: Optional[int] = None,
        default_action: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(  # call into SuspendAgent
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracking_service,
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

    def process(self, inputs: Dict[str, Any]) -> Any:
        self.log_info(f"[HumanAgent] {self.name} initiating human interaction")
        thread_id = self._get_or_create_thread_id()
        formatted_prompt = self._format_prompt_with_inputs(inputs)

        if "__human_response" in inputs:
            human_response = inputs.pop("__human_response")
            resuming_flag = inputs.pop("__resuming_from_human_interaction", False)

            self.log_info(
                f"[HumanAgent] Resuming with human response: "
                f"action={human_response['action']}, "
                f"from_node={human_response.get('responded_at_node', 'unknown')}"
            )

            # Process the human response and return appropriate output
            return self._process_human_response(human_response, inputs)

        # Otherwise, initiate interruption as normal
        self.log_info(f"[HumanAgent] {self.name} initiating human interaction")

        interaction_request = HumanInteractionRequest(
            thread_id=thread_id,
            node_name=self.name,
            interaction_type=self.interaction_type,
            prompt=formatted_prompt,
            context=inputs,
            options=self.options,
            timeout_seconds=self.timeout_seconds,
        )

        checkpoint_data = self._build_checkpoint_data(inputs)

        # Save a checkpoint (reuses parent's method)
        self._save_checkpoint(
            thread_id=thread_id,
            node_name=self.name,
            checkpoint_type="human_intervention",
            metadata={
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
            },
            execution_state=checkpoint_data,
        )

        # Raise the standardized interrupt with a HumanInteractionRequest
        self._interrupt(
            thread_id=thread_id,
            checkpoint_data=checkpoint_data,
            interaction_request=interaction_request,
        )

    def _process_human_response(
        self, human_response: Dict[str, Any], inputs: Dict[str, Any]
    ) -> Any:
        """
        NEW METHOD: Process the human response and return appropriate output.

        Args:
            human_response: Dict with action, data, request_id, etc.
            inputs: Original inputs to the node

        Returns:
            Processed response based on interaction type and action
        """
        action = human_response.get("action", "unknown")
        data = human_response.get("data", {})

        self.log_debug(f"Processing human response: action={action}, data={data}")

        # Handle different interaction types
        if self.interaction_type == InteractionType.APPROVAL:
            # Return boolean for approval/rejection
            return action == "approve"

        elif self.interaction_type == InteractionType.CHOICE:
            # Return the chosen option
            choice_index = data.get("choice", 1) - 1  # Convert to 0-based
            if 0 <= choice_index < len(self.options):
                return self.options[choice_index]
            else:
                return self.options[0] if self.options else None

        elif self.interaction_type == InteractionType.TEXT_INPUT:
            # Return the text response
            return data.get("text", "")

        elif self.interaction_type == InteractionType.EDIT:
            # Return the edited content
            return data.get("edited", inputs.get("original", ""))

        else:
            # Default: return the entire response data
            return data
