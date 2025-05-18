# agentmap/agents/builtins/success_agent.py
from typing import Any, Dict

from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)

class SuccessAgent(BaseAgent):
    """
    Test agent that always succeeds and includes identifying information in the output.
    Useful for testing branching logic in workflows.
    """
    
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
        logger.info(f"[SuccessAgent] {self.name} executed with success")
        logger.debug(f"[SuccessAgent] Full output: {message}")
        logger.debug(f"[SuccessAgent] Input fields: {self.input_fields}")
        logger.debug(f"[SuccessAgent] Output field: {self.output_field}")
            
        return message