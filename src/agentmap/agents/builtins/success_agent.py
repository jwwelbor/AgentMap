# agentmap/agents/builtins/success_agent.py
import logging
from typing import Any, Dict

from agentmap.agents.base_agent import BaseAgent
from agentmap.models.execution_tracker import ExecutionTracker


class SuccessAgent(BaseAgent):
    """
    Test agent that always succeeds and includes identifying information in the output.
    Useful for testing branching logic in workflows.
    """
    
    def __init__(self, name: str, prompt: str, logger: logging.Logger, execution_tracker: ExecutionTracker, context: dict = None):
        """Initialize the success agent with the required dependencies."""
        super().__init__(name, prompt, context, logger=logger, execution_tracker=execution_tracker)
    
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
        self.log_info(f"[SuccessAgent] {self.name} executed with success")
        self.log_debug(f"[SuccessAgent] Full output: {message}")
        self.log_debug(f"[SuccessAgent] Input fields: {self.input_fields}")
        self.log_debug(f"[SuccessAgent] Output field: {self.output_field}")
            
        return message