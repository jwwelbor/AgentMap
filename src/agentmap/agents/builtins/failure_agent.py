# agentmap/agents/builtins/failure_agent.py
from typing import Any, Dict, Tuple

from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger
from agentmap.state.adapter import StateAdapter

logger = get_logger(__name__)

class FailureAgent(BaseAgent):
    """
    Test agent that always fails by setting last_action_success to False.
    Useful for testing failure branches in workflows.
    """
    
    def process(self, inputs: Dict[str, Any]) -> str:
        """
        Process the inputs and deliberately fail.
        
        Args:
            inputs: Dictionary containing input values from input_fields
            
        Returns:
            String confirming the failure path was taken
        """        
        # Include identifying information in the output
        message = f"FAILURE: {self.name} executed (will set last_action_success=False)"
        
        # If we have any inputs, include them in the output
        if inputs:
            input_str = ", ".join(f"{k}" for k, v in inputs.items())
            message += f" with inputs: {input_str}"
        
        # Include the prompt if available
        if self.prompt:
            message += f" with prompt: '{self.prompt}'"

        # Log the execution with additional details for debugging
        logger.info(f"[FailureAgent] {self.name} executed with success")
        logger.debug(f"[FailureAgent] Full output: {message}")
        logger.debug(f"[FailureAgent] Input fields: {self.input_fields}")
        logger.debug(f"[FailureAgent] Output field: {self.output_field}")
            
        return message
    
    def _post_process(self, state: Any, output: Any) -> Tuple[Any, Any]:
        """
        Override the post-processing hook to always set success flag to False.
        
        Args:
            state: Current state
            output: The output value from the process method
            
        Returns:
            Tuple of (state, output) with success flag set to False
        """
        # We'll set this flag now to make it available in the state, but BaseAgent will set it again
        state = StateAdapter.set_value(state, "last_action_success", False)
        
        # We can modify the output if needed
        if output:
            output = f"{output} (Will force FAILURE branch)"
            
        return state, output