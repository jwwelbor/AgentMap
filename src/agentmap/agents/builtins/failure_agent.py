# agentmap/agents/builtins/failure_agent.py
from typing import Any, Dict, Tuple
import logging

from agentmap.agents.base_agent import BaseAgent
from agentmap.models.execution_tracker import ExecutionTracker
from agentmap.services.state_adapter_service import StateAdapterService

class FailureAgent(BaseAgent):
    """
    Test agent that always fails by setting last_action_success to False.
    Useful for testing failure branches in workflows.
    """
    
    def __init__(self, name: str, prompt: str, logger: logging.Logger, execution_tracker: ExecutionTracker, context: dict = None):
        """Initialize the failure agent with the required dependencies."""
        super().__init__(name, prompt, context, logger=logger, execution_tracker=execution_tracker)
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and deliberately fail.
        
        Args:
            inputs: Dictionary containing input values from input_fields
            
        Returns:
            String confirming the failure path was taken
        """        
        # Include identifying information in the output
        message = f"{self.name} executed (will set last_action_success=False)"
        
        # If we have any inputs, include them in the output
        if inputs:
            input_str = ", ".join(f"{k}" for k, v in inputs.items())
            message += f" with inputs: {input_str}"
        
        # Include the prompt if available
        if self.prompt:
            message += f" with prompt: '{self.prompt}'"

        return message
    
    def _post_process(self, state: Any, inputs: Dict[str, Any], output: Any) -> Tuple[Any, Any]:
        """
        Override the post-processing hook to always set success flag to False.
        
        Args:
            state: Current state
            output: The output value from the process method
            
        Returns:
            Tuple of (state, output) with success flag set to False
        """
        # We'll set this flag now to make it available in the state, but BaseAgent will set it again
        state = StateAdapterService.set_value(state, "last_action_success", False)
        
        # We can modify the output if needed
        if output:
            output = f"{output} (Will force FAILURE branch)"
            
        return state, output