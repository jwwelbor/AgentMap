# agentmap/agents/builtins/branching_agent.py
from typing import Any, Dict

from agentmap.agents.base_agent import BaseAgent, StateAdapter
from agentmap.logging import get_logger

logger = get_logger(__name__)

class BranchingAgent(BaseAgent):
    """
    Test agent that branches based on input parameters.
    The agent checks for a field named 'success' or 'should_succeed' in the inputs
    and uses it to determine whether to succeed or fail.
    """
    
    def process(self, inputs: Dict[str, Any]) -> str:
        """
        Process the inputs and decide success or failure based on inputs.
        
        Args:
            inputs: Dictionary containing input values from input_fields
            
        Returns:
            String describing the branching decision
        """
        logger.info(f"[BranchingAgent] {self.name} executed with inputs: {inputs} and prompt: {self.prompt}")
        
        # Check for success parameter in multiple possible input fields
        success = self._determine_success(inputs)
        action = "SUCCEED" if success else "FAIL"
        
        # Create descriptive message
        message = f"BRANCH: {self.name} will {action}"
        logger.info(f"[BranchingAgent] {message}")

        # If we have any inputs, include them in the output
        if inputs:
            input_str = ", ".join(f"{k}={v}" for k, v in inputs.items())
            message += f" based on inputs: [{input_str}]"
        
        # Include the prompt if available
        if self.prompt:
            message += f" with prompt: '{self.prompt}'"
            
        return message
    
    def _determine_success(self, inputs: Dict[str, Any]) -> bool:
        """
        Determine whether to succeed or fail based on inputs.
        Checks various possible field names for flexibility.
        
        Args:
            inputs: Dictionary of input values
            
        Returns:
            Boolean indicating success (True) or failure (False)
        """
        # Check multiple possible field names for the success flag
        for field in ['input', 'success', 'should_succeed', 'succeed', 'branch']:
            if field in inputs:
                value = inputs[field]
                # Handle various value types
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    return value.lower() in ['true', 'yes', 'success', 'succeed', '1', 't', 'y']
                elif isinstance(value, (int, float)):
                    return bool(value)
        
        # Default to True if no relevant fields found
        return True
    
    def run(self, state: Any) -> Any:
        """
        Override the run method to dynamically set last_action_success.
        
        Args:
            state: Current state object
            
        Returns:
            Updated state with output field and success flag based on inputs
        """
        # Get inputs and process as normal
        inputs = self.state_manager.get_inputs(state)
        output = self.process(inputs)
        
        # Determine success based on inputs
        success = self._determine_success(inputs)
        
        # Update state with output and dynamic success flag
        updated_state = self.state_manager.set_output(state, output, success=success)
        
        # Double-check that last_action_success is explicitly set to our desired value
        if StateAdapter.get_value(updated_state, "last_action_success") != success:
            updated_state = StateAdapter.set_value(updated_state, "last_action_success", success)
            
        return updated_state