# from typing import Any, Dict, List, Optional

# from agentmap.logging import get_logger
# from agentmap.state.adapter import StateAdapter

# logger = get_logger(__name__)

# class StateManager:
#     """
#     Manager for handling agent state inputs and outputs.
#     Centralizes the logic for reading inputs and accessing output field names.
#     """
    
#     def __init__(self, input_fields: List[str] = None, output_field: Optional[str] = None):
#         self.input_fields = input_fields or []
#         self.output_field = output_field
        
#     def get_inputs(self, state: Any) -> Dict[str, Any]:
#         """Extract all input fields from state."""
#         inputs = {}
#         for field in self.input_fields:
#             inputs[field] = StateAdapter.get_value(state, field)
#         return inputs