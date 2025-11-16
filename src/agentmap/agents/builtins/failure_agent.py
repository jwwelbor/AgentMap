# agentmap/agents/builtins/failure_agent.py
import logging
from typing import Any, Dict, Optional, Tuple

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class FailureAgent(BaseAgent):
    """
    Test agent that always fails by setting last_action_success to False.
    Useful for testing failure branches in workflows.
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
        """Initialize the failure agent with new protocol-based pattern."""
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and deliberately fail.

        Args:
            inputs: Dictionary containing input values from input_fields

        Returns:
            String confirming the failure path was taken
        """
        # Include identifying information in the output
        message = f"{self.name} executed (will set last_action_success=False)"

        # If we have any inputs, include them in the output
        if inputs:
            input_str = ", ".join(f"{k}" for k, v in inputs.items())
            message += f" with inputs: {input_str}"

        # Include the prompt if available
        if self.prompt:
            message += f" with prompt: '{self.prompt}'"

        return message

    def _post_process(
        self, state: Any, inputs: Dict[str, Any], output: Any
    ) -> Tuple[Any, Any]:
        """
        Override the post-processing hook to always set success flag to False.

        Args:
            state: Current state
            inputs: Input dictionary
            output: The output value from the process method

        Returns:
            Tuple of (state, output) with success flag set to False

        Note: For partial state update pattern (parallel execution), we return a dict
        with both the result message and the last_action_success flag.
        """
        # Modify the output message
        if output:
            result_message = f"{output} (Will force FAILURE branch)"
        else:
            result_message = output

        # Return a dict with state updates for parallel execution
        # BaseAgent will recognize the 'state_updates' key and merge all fields
        return state, {
            "state_updates": {
                self.output_field: result_message,
                "last_action_success": False,
            }
        }

    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """
        Provide FailureAgent-specific service information for debugging.

        Returns:
            Dictionary with failure agent capabilities and configuration
        """
        return {
            "services": {
                "supports_failure_simulation": True,
                "manipulates_success_flags": True,
                "modifies_post_processing": True,
            },
            "capabilities": {
                "failure_path_testing": True,
                "state_modification": True,
                "success_flag_override": True,
                "output_message_modification": True,
            },
            "agent_behavior": {
                "execution_type": "failure_simulation",
                "post_process_behavior": "sets_last_action_success_false",
                "testing_purpose": "validates_failure_branches",
                "state_manipulation": "forces_failure_state",
            },
        }
