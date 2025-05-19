from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger

logger = get_logger(__name__, False)

from typing import Any, Dict


class InputAgent(BaseAgent):
    """Agent that prompts the user for input during execution."""
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Prompt the user for input and return their response.
        
        Args:
            inputs: Dictionary containing input values from input_fields
            
        Returns:
            The user's input as a string
        """
        # Log the execution
        self.log_info(f"[InputAgent] {self.name} prompting for user input")
        
        # Use the prompt from initialization or a default
        prompt_text = self.prompt or "Please provide input: "
        
        # Get input from the user
        user_input = input(prompt_text)
        
        return user_input