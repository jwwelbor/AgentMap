"""
Default agent implementation using the modernized protocol-based pattern.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class DefaultAgent(BaseAgent):
    """
    Default agent that simply logs execution and returns basic information.

    Demonstrates the modernized protocol-based pattern where:
    - Infrastructure services are injected via constructor
    - No business services needed, so no protocol implementation required
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
        Initialize default agent with new protocol-based pattern.

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

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process inputs and return a message that includes the prompt.

        Args:
            inputs: Input values dictionary

        Returns:
            Message including the agent prompt
        """
        # Generate unique process ID
        process_id = str(uuid.uuid4())[:8]

        self.log_debug(
            f"DefaultAgent.process [{process_id}] START with inputs: {inputs}"
        )

        # Return a message that includes the prompt
        base_message = f"[{self.name}] DefaultAgent executed"
        # Include the prompt if it's defined
        if self.prompt:
            base_message = f"{base_message} with prompt: '{self.prompt}'"

        # Log with process ID
        self.log_info(f"[{self.name}] [{process_id}] output: {base_message}")

        self.log_debug(f"DefaultAgent.process [{process_id}] COMPLETE")

        return base_message

    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """
        Provide DefaultAgent-specific service information for debugging.

        Returns:
            Dictionary with default agent capabilities and configuration
        """
        return {
            "services": {
                "supports_default_processing": True,
                "generates_process_ids": True,
            },
            "capabilities": {
                "default_message_generation": True,
                "prompt_inclusion": True,
                "uuid_tracking": True,
            },
            "agent_behavior": {
                "execution_type": "default_processing",
                "output_format": "formatted_message_with_prompt",
                "logging_level": "debug_and_info",
            },
        }
