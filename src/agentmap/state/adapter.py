"""
Adapter for working with different state formats (dict or Pydantic).
"""
from typing import Any, Dict, TypeVar

from agentmap.logging import get_logger

logger = get_logger(__name__)
StateType = TypeVar('StateType', Dict[str, Any], object)

# Add these imports at the top if needed
import importlib
from typing import Any, Dict, Optional

class StateAdapter:
    """Adapter for working with different state formats (dict or Pydantic)."""
    
    @staticmethod
    def get_value(state: Any, key: str, default: Any = None) -> Any:
        """
        Get a value from the state.
        
        Args:
            state: State object (dict, Pydantic model, etc.)
            key: Key to retrieve
            default: Default value if key not found
            
        Returns:
            Value from state or default
        """
        if state is None:
            return default
            
        # Extract value based on state type
        value = None
        
        # Dictionary state
        if hasattr(state, "get") and callable(state.get):
            value = state.get(key, default)
        # Pydantic model or object with attributes
        elif hasattr(state, key):
            value = getattr(state, key, default)
        # Support for __getitem__ access
        elif hasattr(state, "__getitem__"):
            try:
                value = state[key]
            except (KeyError, TypeError, IndexError):
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
    def set_value(state: StateType, key: str, value: Any) -> StateType:
        """
        Set a value in the state, returning a new state object.
        
        Args:
            state: State object (dict, Pydantic model, etc.)
            key: Key to set
            value: Value to set
            
        Returns:
            New state object with updated value
        """
        # Handle special case for memory objects
        if key.endswith("_memory") and hasattr(value, "chat_memory"):
            # Try to serialize memory
            try:
                # Import dynamically to avoid circular imports
                memory_utils = importlib.import_module("agentmap.agents.builtins.memory.utils")
                if hasattr(memory_utils, "serialize_memory"):
                    value = memory_utils.serialize_memory(value)
            except (ImportError, AttributeError) as e:
                logger.debug(f"Could not serialize memory: {e}")
        
        # Handle special case for execution tracker
        if key == "__execution_tracker" and hasattr(value, "get_summary"):
            # Also set the __execution_summary field with the dictionary
            try:
                summary = value.get_summary()
                
                # Dictionary state
                if isinstance(state, dict):
                    new_state = state.copy()
                    new_state[key] = value
                    new_state["__execution_summary"] = summary
                    return new_state
                    
                # Non-dictionary state with copy method (e.g. Pydantic)
                if hasattr(state, "copy") and callable(getattr(state, "copy")):
                    try:
                        # First set the tracker
                        temp_state = state.copy(update={key: value})
                        # Then set the summary
                        new_state = temp_state.copy(update={"__execution_summary": summary})
                        return new_state
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Error setting execution summary: {e}")
        
        # Dictionary state (most common case)
        if isinstance(state, dict):
            new_state = state.copy()
            new_state[key] = value
            return new_state
            
        # Pydantic model
        if hasattr(state, "copy") and callable(getattr(state, "copy")):
            try:
                # Create a copy with updated field
                update_dict = {key: value}
                new_state = state.copy(update=update_dict)
                return new_state
            except Exception:
                # Fall back to attribute setting if copy with update fails
                pass
                
        # Direct attribute setting (fallback)
        try:
            # Create a shallow copy
            import copy
            new_state = copy.copy(state)
            setattr(new_state, key, value)
            return new_state
        except Exception as e:
            logger.debug(f"Error setting value on state: {e}")
            # If all else fails, return original state
            return state
                
    @staticmethod
    def initialize_execution_tracker(state: Any, config: Optional[Dict[str, Any]] = None) -> Any:
        """
        Always initialize execution tracker in state (lightweight by default).
        
        Args:
            state: Current state
            config: Optional tracker configuration
            
        Returns:
            State with execution tracker initialized
        """
        from agentmap.logging.tracking.execution_tracker import ExecutionTracker
        
        if StateAdapter.get_value(state, "__execution_tracker") is None:
            # Default to minimal tracking if no config is provided
            if config is None:
                config = {
                    "tracking": {
                        "enabled": False,  # Minimal tracking by default
                        "track_outputs": False,
                        "track_inputs": False,
                    }
                }
            tracker = ExecutionTracker(config)
            state = StateAdapter.set_value(state, "__execution_tracker", tracker)
        return state

    @staticmethod
    def get_execution_tracker(state: Any):
        """
        Get the execution tracker from state.
        
        Args:
            state: Current state
            
        Returns:
            ExecutionTracker instance or None
        """
        return StateAdapter.get_value(state, "__execution_tracker")
    
    @staticmethod
    def get_execution_data(state, field, default=None):
        """Get execution tracking data safely."""
        # Try the documented approach first
        if "__execution_summary" in state:
            summary = StateAdapter.get_value(state, "__execution_summary", {})
            return summary.get(field, default)
        
        # Fall back to the tracker if needed
        tracker = StateAdapter.get_value(state, "__execution_tracker")
        if tracker and hasattr(tracker, "get_summary"):
            summary = tracker.get_summary()
            return summary.get(field, default)
        
        # No tracking data available
        return default
