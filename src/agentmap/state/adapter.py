"""
Adapter for working with different state formats (dict or Pydantic).
"""
from typing import Any, Dict, TypeVar

StateType = TypeVar('StateType', Dict[str, Any], object)
from pydantic import BaseModel
from agentmap.logging.tracking.execution_tracker import ExecutionTracker

# Add these imports at the top if needed
import importlib
from typing import Any, Dict, Optional

class StateAdapter:
    """Adapter for working with different state formats (dict or Pydantic)."""
    
    @staticmethod
    def has_value(state: Any, key: str) -> bool:
        """
        Check if a key exists in the state.
        
        Args:
            state: State object (dict, Pydantic model, etc.)
            key: Key to check
            
        Returns:
            True if key exists, False otherwise
        """
        if state is None:
            return False
            
        # Dictionary state
        if hasattr(state, "get") and callable(state.get):
            return key in state
        # Pydantic model or object with attributes
        elif hasattr(state, key):
            return True
        # Support for __getitem__ access
        elif hasattr(state, "__getitem__"):
            try:
                _ = state[key]
                return True
            except (KeyError, TypeError, IndexError):
                return False
        
        return False
    
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
                raise e
                # logger.debug(f"Error setting execution summary: {e}")
        
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
            # logger.debug(f"Error setting value on state: {e}")
            # If all else fails, return original state
            raise e
            # return state

    
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


    @staticmethod
    def merge_updates(state: StateType, updates: Dict[str, Any]) -> StateType:
        """
        Merge multiple updates into the state efficiently.
        This is useful for applying partial updates from agents.
        
        Args:
            state: Current state object
            updates: Dictionary of updates to apply
            
        Returns:
            New state object with all updates applied
        """
        if not updates:
            return state
            
        # For AgentMapState/TypedDict, merge efficiently
        if isinstance(state, dict):
            new_state = state.copy()
            new_state.update(updates)
            return new_state
            
        # Apply updates one by one for other state types
        current_state = state
        for key, value in updates.items():
            current_state = StateAdapter.set_value(current_state, key, value)
        
        return current_state
