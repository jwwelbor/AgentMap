from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)
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

        # Return a message that includes the prompt
        base_message = f"DefaultAgent '{self.name}' executed"        
        # Include the prompt if it's defined
        if self.prompt:
            base_message = f"{base_message} with prompt: '{self.prompt}'"
        logger.info(f"[DefaultAgent] output: {base_message}")
        return base_message