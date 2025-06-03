# agentmap/agents/builtins/default_agent.py
from agentmap.agents.base_agent import BaseAgent
import uuid
import logging
from typing import Any, Dict, Tuple

from agentmap.models.execution_tracker import ExecutionTracker


class DefaultAgent(BaseAgent):
    """Default agent implementation that simply logs its execution."""

    def __init__(self, name: str, prompt: str, logger: logging.Logger, execution_tracker: ExecutionTracker, context: dict = None):
        """Initialize the default agent with the required dependencies."""
        super().__init__(name, prompt, context, logger=logger, execution_tracker=execution_tracker)

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

        print(f"DefaultAgent.process [{process_id}] START with inputs: {inputs}")

        # Return a message that includes the prompt
        base_message = f"[{self.name}] DefaultAgent executed"
        # Include the prompt if it's defined
        if self.prompt:
            base_message = f"{base_message} with prompt: '{self.prompt}'"

        # Log with process ID
        self.log_info(f"[{self.name}] [{process_id}] output: {base_message}")

        print(f"DefaultAgent.process [{process_id}] COMPLETE")

        return base_message