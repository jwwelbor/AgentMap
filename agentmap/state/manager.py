from typing import Any, Dict, List, Optional

from agentmap.logging import get_logger
from agentmap.state.adapter import StateAdapter

logger = get_logger(__name__)

# Add these imports at the top if needed
import importlib
from typing import Any, Dict, List, Optional

class StateManager:
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
