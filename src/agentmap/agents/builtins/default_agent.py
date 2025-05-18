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
        base_message = f"[{self.name}] DefaultAgent executed"        
        # Include the prompt if it's defined
        if self.prompt:
            base_message = f"{base_message} with prompt: '{self.prompt}'"

        # Use a single log message with a custom key to ensure we don't log duplicates
        log_key = f"{self.name}_{id(inputs)}"
        if not hasattr(self, '_logged_executions'):
            self._logged_executions = set()
            
        if log_key not in self._logged_executions:
            logger.info(f"[{self.name}] output: {base_message}")
            self._logged_executions.add(log_key)

        return base_message
    
    