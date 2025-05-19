# agentmap/agents/builtins/graph_agent.py
from typing import Any, Dict

from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger
from agentmap.runner import run_graph
from agentmap.utils.common import extract_func_ref, import_function

logger = get_logger(__name__, False)

class GraphAgent(BaseAgent):
    """
    Agent that executes a subgraph and returns its result.
    
    This agent allows for composing multiple graphs into larger workflows
    by running a subgraph as part of a parent graph's execution.
    """
    
    def __init__(self, name: str, prompt: str, context: dict = None):
        """
        Initialize the graph agent.
        
        Args:
            name: Name of the agent node
            prompt: Name of the subgraph to execute
            context: Additional context (optional CSV path)
        """
        super().__init__(name, prompt, context or {})
        
        # The subgraph name comes from the prompt field
        self.subgraph_name = prompt
        
        # The CSV path can be specified in the context field
        self.csv_path = context if isinstance(context, str) and context.strip() else None
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs by running the subgraph.
        
        Args:
            inputs: Dictionary containing input values from input_fields
            
        Returns:
            Output from the subgraph execution
        """
        self.log_info(f"[GraphAgent] Executing subgraph: {self.subgraph_name}")
        
        # Determine and prepare the initial state for the subgraph
        subgraph_state = self._prepare_subgraph_state(inputs)
        
        try:
            # Execute the subgraph
            result = run_graph(
                graph_name=self.subgraph_name, 
                initial_state=subgraph_state,
                csv_path=self.csv_path,
                autocompile_override=True
            )
            
            self.log_info(f"[GraphAgent] Subgraph execution completed successfully")
            
            # Process the result based on output field mapping
            if self.output_field and "=" in self.output_field:
                target_field, source_field = self.output_field.split("=", 1)
                if source_field in result:
                    return {target_field: result[source_field]}
            
            # By default, return the entire result
            return result
            
        except Exception as e:
            self.log_error(f"[GraphAgent] Error executing subgraph: {str(e)}")
            return {
                "error": f"Failed to execute subgraph '{self.subgraph_name}': {str(e)}",
                "last_action_success": False
            }
    
    def _prepare_subgraph_state(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare the initial state for the subgraph based on input mappings.
        
        Args:
            inputs: Input values from the parent graph
            
        Returns:
            Initial state for the subgraph
        """
        # Case 1: Function mapping
        if len(self.input_fields) == 1 and self.input_fields[0].startswith("func:"):
            return self._apply_function_mapping(inputs)
        
        # Case 2: Field mapping
        if any("=" in field for field in self.input_fields):
            return self._apply_field_mapping(inputs)
        
        # Case 3: No mapping or direct field passthrough
        if not self.input_fields:
            # Pass entire state
            return inputs.copy()
        else:
            # Pass only specified fields
            return {field: inputs.get(field) for field in self.input_fields if field in inputs}
    
    def _apply_field_mapping(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Apply field-to-field mapping."""
        subgraph_state = {}
        
        for field_spec in self.input_fields:
            if "=" in field_spec:
                # This is a mapping (target=source)
                target_field, source_field = field_spec.split("=", 1)
                if source_field in inputs:
                    subgraph_state[target_field] = inputs[source_field]
            else:
                # Direct passthrough
                if field_spec in inputs:
                    subgraph_state[field_spec] = inputs[field_spec]
        
        return subgraph_state
    
    def _apply_function_mapping(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Apply function-based mapping."""
        func_ref = extract_func_ref(self.input_fields[0])
        if not func_ref:
            self.log_warning(f"[GraphAgent] Invalid function reference: {self.input_fields[0]}")
            return inputs.copy()
        
        try:
            # Import the mapping function
            mapping_func = import_function(func_ref)
            
            # Execute the function to transform the state
            mapped_state = mapping_func(inputs)
            
            # Ensure we got a dictionary back
            if not isinstance(mapped_state, dict):
                self.log_warning(f"[GraphAgent] Mapping function {func_ref} returned non-dict: {type(mapped_state)}")
                return inputs.copy()
            
            return mapped_state
            
        except Exception as e:
            self.log_error(f"[GraphAgent] Error in mapping function: {str(e)}")
            return inputs.copy()