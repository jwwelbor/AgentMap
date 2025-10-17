# human_agent.py
import logging
from typing import Any, Dict, List, Optional

from langgraph.types import interrupt

from agentmap.agents.builtins.suspend_agent import SuspendAgent
from agentmap.models.human_interaction import InteractionType
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class HumanAgent(SuspendAgent):
    """
    Agent that pauses execution for human interaction using LangGraph's interrupt() pattern.

    On first call: Raises GraphInterrupt with interaction request
    On resume: Processes human response and returns appropriate value
    """

    def __init__(
        self,
        execution_tracking_service: ExecutionTrackingService,
        state_adapter_service: StateAdapterService,
        name: str,
        prompt: str,
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

        # interaction_type: str = "text_input",
        # options: Optional[List[str]] = None,
        # timeout_seconds: Optional[int] = None,
        # default_action: Optional[str] = None,

        interaction_type = context.get("interaction_type", "text_input")
        options = context.get("options")
        timeout_seconds = context.get("timeout_seconds")
        default_option = context.get("default_option")

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
        self.default_option = default_option

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Pause for human interaction using LangGraph's interrupt() pattern.

        On first call: Raises GraphInterrupt with interaction request
        On resume: Processes human response and returns appropriate value

        The interrupt metadata includes all information needed to display
        the interaction request to the user.
        """
        thread_id = self._get_or_create_thread_id()
        formatted_prompt = self._format_prompt_with_inputs(inputs)

        self.log_info(f"[HumanAgent] {self.name} initiating human interaction")

        # Use LangGraph's interrupt() - pass interaction request as metadata
        # On first call: This raises GraphInterrupt
        # On resume: This returns the human response from Command(resume=value)
        human_response = interrupt(
            {
                "type": "human_interaction",
                "thread_id": thread_id,
                "node_name": self.name,
                "interaction_type": self.interaction_type.value,
                "prompt": formatted_prompt,
                "options": self.options,
                "default_option": self.default_option,
                "timeout_seconds": self.timeout_seconds,
                "inputs": inputs,
                "context": self.context,
            }
        )

        # This code only runs on resume!
        self.log_info(f"[HumanAgent] Resuming with human response: {human_response}")

        # Process the response and return the appropriate value
        return self._process_human_response(human_response, inputs)

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
