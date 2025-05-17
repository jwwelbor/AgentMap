"""
Adapter for working with different state formats (dict or Pydantic).
"""
from typing import Any, Dict, List, Optional

from agentmap.logging import get_logger

logger = get_logger(__name__)

# Add these imports at the top if needed
import importlib
from typing import Any, Dict, List, Optional

class StateAdapter:
    """Adapter for working with different state formats (dict or Pydantic)."""
    
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
