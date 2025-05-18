# agentmap/agents/builtins/default_agent.py
from sympy import false

from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger
import uuid
logger = get_logger(__name__, propagate = false)
from typing import Any, Dict


class DefaultAgent(BaseAgent):
    """Default agent implementation that simply logs its execution."""

    def process(self, inputs: Dict[str, Any]) -> str:
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
        logger.info(f"[{self.name}] [{process_id}] output: {base_message}")

        print(f"DefaultAgent.process [{process_id}] COMPLETE")

        return base_message