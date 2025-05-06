from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)
from typing import Any, Dict


class EchoAgent(BaseAgent):
    """Echo agent that simply returns input data unchanged."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Echo back the input data unchanged.
        
        Args:
            inputs: Dictionary containing input values from input_fields
            
        Returns:
            The input data unchanged
        """
        logger.info(f"[EchoAgent] '{self.name}' received inputs: {inputs} and prompt: '{self.prompt}'")
        
        # If there are inputs, return the first one
        if inputs:
            # Return all inputs as a dictionary to maintain structure
            return inputs
        
        # Default return if no inputs
        return "No input provided to echo"
    