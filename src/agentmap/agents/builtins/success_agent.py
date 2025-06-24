# agentmap/agents/builtins/success_agent.py
import logging
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class SuccessAgent(BaseAgent):
    """
    Test agent that always succeeds and includes identifying information in the output.
    Useful for testing branching logic in workflows.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only
        logger: Optional[logging.Logger] = None,
        execution_tracker_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
    ):
        """Initialize the success agent with new protocol-based pattern."""
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

    def process(self, inputs: Dict[str, Any]) -> str:
        """
        Process the inputs and return a success message.

        Args:
            inputs: Dictionary containing input values from input_fields

        Returns:
            String confirming the success path was taken
        """
        # Include identifying information in the output
        message = f"SUCCESS: {self.name} executed"

        # If we have any inputs, include them in the output
        if inputs:
            input_str = ", ".join([f"{k}={v}" for k, v in inputs.items()])
            message += f" with inputs: {input_str}"

        # Include the prompt if available
        if self.prompt:
            message += f" with prompt: '{self.prompt}'"

        # Log the execution with additional details for debugging
        self.log_info(f"[SuccessAgent] {self.name} executed with success")
        self.log_debug(f"[SuccessAgent] Full output: {message}")
        self.log_debug(f"[SuccessAgent] Input fields: {self.input_fields}")
        self.log_debug(f"[SuccessAgent] Output field: {self.output_field}")

        return message

    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """
        Provide SuccessAgent-specific service information for debugging.

        Returns:
            Dictionary with success agent capabilities and configuration
        """
        return {
            "services": {
                "supports_success_simulation": True,
                "generates_success_messages": True,
            },
            "capabilities": {
                "success_path_testing": True,
                "detailed_success_reporting": True,
                "input_context_inclusion": True,
                "prompt_context_inclusion": True,
            },
            "agent_behavior": {
                "execution_type": "success_simulation",
                "output_format": "success_message_with_context",
                "testing_purpose": "validates_success_branches",
            },
        }
