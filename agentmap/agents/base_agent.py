from typing import Any, Dict, List, Optional

from agentmap.logging import get_logger

logger = get_logger(__name__)

# Add these imports at the top if needed
import importlib
from typing import Any, Dict, List, Optional, Union

# In the StateAdapter class, update the get_value and set_value methods

@staticmethod
def get_value(state: Any, key: str, default: Any = None) -> Any:
    """Get a value from state regardless of its type."""
    value = None
    if hasattr(state, "get") and callable(state.get):
        value = state.get(key, default)
    elif hasattr(state, key):
        value = getattr(state, key, default)
    elif hasattr(state, "__getitem__"):
        try:
            value = state[key]
        except (KeyError, TypeError):
            value = default
    else:
        value = default

    # Special handling for memory objects
    if value is not None and key.endswith("_memory") and isinstance(value, dict) and value.get("_type") == "langchain_memory":
        # Try to deserialize memory
        try:
            # Import dynamically to avoid circular imports
            memory_utils = importlib.import_module("agentmap.agents.builtins.memory.utils")
            if hasattr(memory_utils, "deserialize_memory"):
                value = memory_utils.deserialize_memory(value)
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not deserialize memory: {e}")

    return value

@staticmethod
def set_value(state: Any, key: str, value: Any) -> Any:
    """Set a value in state, returning a new state object."""
    # Special handling for memory objects
    if key.endswith("_memory") and value is not None and not isinstance(value, dict):
        # Try to serialize memory object
        try:
            # Import dynamically to avoid circular imports
            memory_utils = importlib.import_module("agentmap.agents.builtins.memory.utils")
            if hasattr(memory_utils, "serialize_memory"):
                value = memory_utils.serialize_memory(value)
        except (ImportError, AttributeError) as e:
            logger.debug(f"Could not serialize memory: {e}")

    # Regular state handling
    if hasattr(state, "model_dump"):  # Pydantic v2
        data = state.model_dump()
        data[key] = value
        return state.__class__(**data)
    elif hasattr(state, "dict"):  # Pydantic v1
        data = state.dict()
        data[key] = value
        return state.__class__(**data)
    else:  # Regular dict or other
        if isinstance(state, dict):
            new_state = state.copy()
            new_state[key] = value
            return new_state
        else:
            # For other objects, try direct attribute setting
            import copy
            new_state = copy.copy(state)
            setattr(new_state, key, value)
            return new_state

class StateAdapter:
    """Adapter for working with different state formats (dict or Pydantic)."""
    
    @staticmethod
    def get_value(state: Any, key: str, default: Any = None) -> Any:
        """Get a value from state regardless of its type."""
        if hasattr(state, "get") and callable(state.get):
            return state.get(key, default)
        elif hasattr(state, key):
            return getattr(state, key, default)
        elif hasattr(state, "__getitem__"):
            try:
                return state[key]
            except (KeyError, TypeError):
                return default
        return default
    
    @staticmethod
    def set_value(state: Any, key: str, value: Any) -> Any:
        """Set a value in state, returning a new state object."""
        if hasattr(state, "model_dump"):  # Pydantic v2
            data = state.model_dump()
            data[key] = value
            return state.__class__(**data)
        elif hasattr(state, "dict"):  # Pydantic v1
            data = state.dict()
            data[key] = value
            return state.__class__(**data)
        else:  # Regular dict or other
            if isinstance(state, dict):
                new_state = state.copy()
                new_state[key] = value
                return new_state
            else:
                # For other objects, try direct attribute setting
                import copy
                new_state = copy.copy(state)
                setattr(new_state, key, value)
                return new_state


class AgentStateManager:
    """
    Manager for handling agent state inputs and outputs.
    Centralizes the logic for reading inputs and setting outputs.
    """
    
    def __init__(self, input_fields: List[str] = None, output_field: Optional[str] = None):
        self.input_fields = input_fields or []
        self.output_field = output_field
        
    def get_inputs(self, state: Any) -> Dict[str, Any]:
        """Extract all input fields from state."""
        inputs = {}
        for field in self.input_fields:
            inputs[field] = StateAdapter.get_value(state, field)
        return inputs
    
    def set_output(self, state: Any, output_value: Any, success: bool = True) -> Any:
        """Set the output field and success flag in state."""
        
        logger.debug(f"[StateManager:set_output] Setting output in field '{self.output_field}' with value: {output_value}")
        logger.debug(f"[StateManager:set_output] Original state: {state}")
        
        if self.output_field:
            new_state = StateAdapter.set_value(state, self.output_field, output_value)
            logger.debug(f"[StateManager:set_output] Updated state after setting {self.output_field}: {new_state}")
        else:
            logger.debug("[StateManager:set_output] No output_field defined, state unchanged")
            new_state = state
        
        final_state = StateAdapter.set_value(new_state, "last_action_success", success)
        logger.debug(f"[StateManager:set_output] Final state after setting last_action_success={success}: {final_state}")
        
        return final_state


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
        self.output_field = self.context.get("output_field")
        
        # Create state manager
        self.state_manager = AgentStateManager(self.input_fields, self.output_field)
    
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
