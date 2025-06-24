"""
StateAdapterService for AgentMap.

Service that wraps existing StateAdapter functionality from agentmap.state.adapter.
Following YAGNI principle, this service only wraps the set_value method that is
actually used in the codebase. Additional methods can be added as needed.
"""

from typing import Any, Dict, List, TypeVar

# Type variable for state objects
StateType = TypeVar("StateType", Dict[str, Any], object)


class StateAdapterService:
    """
    Service for state format abstraction and manipulation.

    Wraps the existing StateAdapter functionality while providing clean dependency
    injection and service integration. Following YAGNI principle, only wraps
    the set_value method that is currently used in the codebase.
    """

    # def __init__(
    #     self,
    # ):
    #     """Initialize service with dependency injection."""
    #     pass

    @staticmethod
    def has_value(state: Any, key: Any) -> bool:
        """
        Check if a key exists in the state.

        Args:
            state: State object (dict, Pydantic model, etc.)
            key: Key to check (string for attributes/dict keys, int for list indices, etc.)

        Returns:
            True if key exists, False otherwise
        """
        if state is None:
            return False

        # Dictionary state
        if hasattr(state, "get") and callable(state.get):
            return key in state
        # Pydantic model or object with attributes (only for string keys)
        elif isinstance(key, str) and hasattr(state, key):
            return True
        # Support for __getitem__ access (lists, custom objects, etc.)
        elif hasattr(state, "__getitem__"):
            try:
                _ = state[key]
                return True
            except (KeyError, TypeError, IndexError):
                return False

        return False

    @staticmethod
    def get_value(state: Any, key: Any, default: Any = None) -> Any:
        """
        Get a value from the state.

        Args:
            state: State object (dict, Pydantic model, etc.)
            key: Key to retrieve (string for attributes/dict keys, int for list indices, etc.)
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
        # Pydantic model or object with attributes (only for string keys)
        elif isinstance(key, str) and hasattr(state, key):
            value = getattr(state, key, default)
        # Support for __getitem__ access (lists, custom objects, etc.)
        elif hasattr(state, "__getitem__"):
            try:
                value = state[key]
            except (KeyError, TypeError, IndexError):
                value = default
        else:
            value = default

        return value

    @staticmethod
    def set_value(state: StateType, key: Any, value: Any) -> StateType:
        """
        Set a value in the state, returning a new state object.

        Args:
            state: State object (dict, Pydantic model, etc.)
            key: Key to set (string for attributes/dict keys, int for list indices, etc.)
            value: Value to set

        Returns:
            New state object with updated value
        """
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
    def get_inputs(state: Any, input_fields: List[str]) -> Dict[str, Any]:
        """Extract all input fields from state."""
        inputs = {}
        for field in input_fields:
            inputs[field] = StateAdapterService.get_value(state, field)
        return inputs

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the state adapter service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "StateAdapterService",
            "config_available": False,
            "capabilities": {
                "state_manipulation": True,
                "immutable_updates": True,
                "multiple_state_types": True,
                "error_handling": True,
            },
            "methods": ["set_value", "get_inputs", "has_value", "get_value"],
            "available_state_types": [
                "dict",
                "pydantic_models",
                "objects_with_copy_method",
                "objects_with_attributes",
            ],
            "yagni_compliance": {
                "methods_wrapped": 1,
                "methods_available": 4,
                "reason": "Only set_value method is currently used in GraphRunnerService",
            },
        }

    # @staticmethod
    # def get_execution_data(state, field, default=None):
    #     """Get execution tracking data safely."""
    #     # Try the documented approach first
    #     if "__execution_summary" in state:
    #         summary = StateAdapter.get_value(state, "__execution_summary", {})
    #         return summary.get(field, default)

    #     # Fall back to the tracker if needed
    #     tracker = StateAdapter.get_value(state, "__execution_tracker")
    #     if tracker and hasattr(tracker, "get_summary"):
    #         summary = tracker.get_summary()
    #         return summary.get(field, default)

    #     # No tracking data available
    #     return default

    # @staticmethod
    # def merge_updates(state: StateType, updates: Dict[str, Any]) -> StateType:
    #     """
    #     Merge multiple updates into the state efficiently.
    #     This is useful for applying partial updates from agents.

    #     Args:
    #         state: Current state object
    #         updates: Dictionary of updates to apply

    #     Returns:
    #         New state object with all updates applied
    #     """
    #     if not updates:
    #         return state

    #     # For AgentMapState/TypedDict, merge efficiently
    #     if isinstance(state, dict):
    #         new_state = state.copy()
    #         new_state.update(updates)
    #         return new_state

    #     # Apply updates one by one for other state types
    #     current_state = state
    #     for key, value in updates.items():
    #         current_state = StateAdapter.set_value(current_state, key, value)

    #     return current_state
