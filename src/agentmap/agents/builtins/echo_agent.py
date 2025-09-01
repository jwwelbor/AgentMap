"""
Modernized Echo Agent demonstrating the new protocol-based pattern.
"""

import logging
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.prompt_manager_service import PromptManagerService
from agentmap.services.protocols import PromptCapableAgent
from agentmap.services.state_adapter_service import StateAdapterService


class EchoAgent(BaseAgent, PromptCapableAgent):
    """
    Echo agent that simply returns input data unchanged.

    Demonstrates the modernized protocol-based pattern where:
    - Infrastructure services are injected via constructor
    - Business services are configured post-construction via protocols
    - EchoAgent needs no business services, so implements no protocols
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
        """
        Initialize echo agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including input/output configuration
            logger: Logger instance for logging operations
            execution_tracker: ExecutionTrackingService instance for tracking
            state_adapter: StateAdapterService instance for state operations
        """
        # Call new BaseAgent constructor (infrastructure services only)
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

    def configure_prompt_service(self, prompt_service):
        self.prompt_service: PromptManagerService = prompt_service

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Echo back the input data unchanged.

        Args:
            inputs: Dictionary containing input values from input_fields

        Returns:
            The input data unchanged
        """
        if (
            self.prompt and self.prompt.find("{") != -1
        ):  # if there's a prompt with mustache
            result = self.prompt_service.format_prompt(self.prompt, inputs)
            self.log_info(result)
            return result

        # If there are inputs, return them
        self.log_info(f"received inputs: {inputs} and prompt: '{self.prompt}'")
        if inputs:
            # For multiple inputs, return all as a dictionary to maintain structure
            if len(inputs) > 1:
                return inputs
            # For single input, return just the value
            else:
                return next(iter(inputs.values()))

        # Default return if no inputs
        return "No input provided to echo"

    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """
        Provide EchoAgent-specific service information for debugging.

        Returns:
            Dictionary with echo agent capabilities and configuration
        """
        return {
            "services": {
                "supports_input_echoing": True,
                "handles_multiple_inputs": True,
            },
            "capabilities": {
                "data_passthrough": True,
                "input_preservation": True,
                "structure_maintenance": True,
            },
            "agent_behavior": {
                "execution_type": "echo_passthrough or populate prompt with input data",
                "output_format": "unchanged_input_data or formatted prompt",
                "data_transformation": "none",
            },
        }
