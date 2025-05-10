# agentmap/agents/builtins/failure_agent.py
from typing import Any, Dict

from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger

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
    
    def run(self, state: Any) -> Any:
        """
        Override the run method to ensure failure by setting last_action_success to False.
        
        Args:
            state: Current state object (can be dict, Pydantic model, etc.)
            
        Returns:
            Updated state with output field and success flag set to False
        """
        # Get inputs and process as normal
        inputs = self.state_manager.get_inputs(state)
        output = self.process(inputs)
        
        # Update state with output
        updated_state = self.state_manager.set_output(state, output, success=True)
        
        # Force last_action_success to False to trigger failure paths
        from agentmap.state.adapter import StateAdapter
        return StateAdapter.set_value(updated_state, "last_action_success", False)