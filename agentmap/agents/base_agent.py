from typing import Any, Dict, List, Optional

from agentmap.logging import get_logger

logger = get_logger(__name__)

# Add these imports at the top if needed
import importlib
from typing import Any, Dict, List, Optional
from agentmap.state.adapter import StateAdapter
from agentmap.state.manager import StateManager

class BaseAgent:
    """Base class for all agents in AgentMap."""
    
    def __init__(self, name: str, prompt: str, context: dict = None):
        """
        Initialize the agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction for LLM-based agents
            context: Additional context including configuration
        """
        self.name = name
        self.prompt = prompt
        self.context = context or {}
        self.prompt_template = prompt
        
        # Extract input_fields and output_field from context if available
        self.input_fields = self.context.get("input_fields", [])
        self.output_field = self.context.get("output_field", "output")
        
        # Create state manager
        self.state_manager = StateManager(self.input_fields, self.output_field)
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and return an output value.
        Subclasses should implement this method.
        
        Args:
            inputs: Dictionary of input values
            
        Returns:
            Output value for the output_field
        """
        raise NotImplementedError("Subclasses must implement process()")
    
    def run(self, state: Any) -> Any:
        """
        Run the agent on the state, extracting inputs and setting outputs.
        
        Args:
            state: Current state object (can be dict, Pydantic model, etc.)
            
        Returns:
            Updated state with output field and success flag
        """
        # Extract inputs
        inputs = self.state_manager.get_inputs(state)
        
        try:
            # Process inputs to get output
            output = self.process(inputs)
            
            # Update state with output
            return self.state_manager.set_output(state, output, success=True)
        except Exception as e:
            # Handle errors
            error_msg = f"Error in {self.name}: {str(e)}"
            logger.error(error_msg)
            
            # Set error in state
            error_state = StateAdapter.set_value(state, "error", error_msg)
            return self.state_manager.set_output(error_state, None, success=False)
    
    def invoke(self, state: Any) -> Any:
        """Alias for run() to maintain compatibility with LangGraph."""
        return self.run(state)
