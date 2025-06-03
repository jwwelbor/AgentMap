from agentmap.agents.base_agent import BaseAgent
import logging
from typing import Any, Dict, Tuple

from agentmap.models.execution_tracker import ExecutionTracker


class EchoAgent(BaseAgent):
    """Echo agent that simply returns input data unchanged."""
    
    def __init__(self, name: str, prompt: str, logger: logging.Logger, execution_tracker: ExecutionTracker, context: dict = None):
        """Initialize the echo agent with the required dependencies."""
        super().__init__(name, prompt, context, logger=logger, execution_tracker=execution_tracker)
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Echo back the input data unchanged.
        
        Args:
            inputs: Dictionary containing input values from input_fields
            
        Returns:
            The input data unchanged
        """
        self.log_info(f"received inputs: {inputs} and prompt: '{self.prompt}'")
        
        # If there are inputs, return the first one
        if inputs:
            # Return all inputs as a dictionary to maintain structure
            return inputs
        
        # Default return if no inputs
        return "No input provided to echo"
    