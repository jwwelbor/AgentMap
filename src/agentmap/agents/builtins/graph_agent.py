# agentmap/agents/builtins/graph_agent.py
from typing import Any, Dict, Optional, Tuple
import logging
from agentmap.agents.base_agent import BaseAgent
from agentmap.state.adapter import StateAdapter
from agentmap.utils.common import extract_func_ref, import_function
from agentmap.logging.tracking.execution_tracker import ExecutionTracker

class GraphAgent(BaseAgent):
    """
    Agent that executes a subgraph and returns its result.
    
    This agent allows for composing multiple graphs into larger workflows
    by running a subgraph as part of a parent graph's execution.
    
    Supports flexible input/output mapping and nested execution tracking.
    """
    
    def __init__(
            self, 
            name: str, 
            prompt: str, 
            logger: logging.Logger, 
            execution_tracker: ExecutionTracker, 
            context: dict = None
        ):
        """
        Initialize the graph agent.
        
        Args:
            name: Name of the agent node
            prompt: Name of the subgraph to execute
            context: Additional context (CSV path string or config dict)
        """
        super().__init__(name, prompt, context, logger=logger, execution_tracker=execution_tracker)
        
        # The subgraph name comes from the prompt field
        self.subgraph_name = prompt
        self._execution_tracker = execution_tracker
        
        # Handle context as either string (CSV path) or dict (config)
        if isinstance(context, str) and context.strip():
            self.csv_path = context.strip()
            self.execution_mode = "separate"  # Default: separate execution
        elif isinstance(context, dict):
            self.csv_path = context.get("csv_path")
            self.execution_mode = context.get("execution_mode", "separate")  # "separate" or "native"
        else:
            self.csv_path = None
            self.execution_mode = "separate"
    
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
            from agentmap.runner import run_graph

            # Execute the subgraph using run_graph (maintains your current approach)
            result = run_graph(
                graph_name=self.subgraph_name, 
                initial_state=subgraph_state,
                csv_path=self.csv_path,
                autocompile_override=True
            )
            
            self.log_info(f"[GraphAgent] Subgraph execution completed successfully")
            
            # Process the result based on output field mapping
            processed_result = self._process_subgraph_result(result)
            
            return processed_result
            
        except Exception as e:
            self.log_error(f"[GraphAgent] Error executing subgraph: {str(e)}")
            return {
                "error": f"Failed to execute subgraph '{self.subgraph_name}': {str(e)}",
                "last_action_success": False
            }
    
    def _post_process(self, state: Any, output: Any) -> Tuple[Any, Any]:
        """
        Enhanced post-processing to integrate subgraph execution tracking.
        
        Args:
            state: Current state
            output: Output from process method
            
        Returns:
            Tuple of (updated_state, processed_output)
        """
        # Get parent execution tracker
        parent_tracker = self._execution_tracker
        
        # If output contains execution summary from subgraph, record it
        if isinstance(output, dict) and "__execution_summary" in output:
            subgraph_summary = output["__execution_summary"]
            
            if parent_tracker and hasattr(parent_tracker, 'record_subgraph_execution'):
                parent_tracker.record_subgraph_execution(
                    self.subgraph_name, 
                    subgraph_summary
                )
                self.log_debug(f"[GraphAgent] Recorded subgraph execution in parent tracker")
            
            # Remove execution summary from output to avoid polluting final state
            if isinstance(output, dict) and "__execution_summary" in output:
                output = {k: v for k, v in output.items() if k != "__execution_summary"}
        
        # Set success based on subgraph result
        if isinstance(output, dict):
            graph_success = output.get("graph_success", output.get("last_action_success", True))
            state = StateAdapter.set_value(state, "last_action_success", graph_success)
        
        return state, output
    
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
                    self.log_debug(f"[GraphAgent] Mapped {source_field} -> {target_field}")
            else:
                # Direct passthrough
                if field_spec in inputs:
                    subgraph_state[field_spec] = inputs[field_spec]
                    self.log_debug(f"[GraphAgent] Passed through {field_spec}")
        
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
            
            self.log_debug(f"[GraphAgent] Applied function mapping: {func_ref}")
            return mapped_state
            
        except Exception as e:
            self.log_error(f"[GraphAgent] Error in mapping function: {str(e)}")
            return inputs.copy()
    
    def _process_subgraph_result(self, result: Dict[str, Any]) -> Any:
        """
        Process the subgraph result based on output field configuration.
        
        Args:
            result: Complete result from subgraph execution
            
        Returns:
            Processed result for parent graph
        """
        # Handle output field mapping
        if self.output_field and "=" in self.output_field:
            target_field, source_field = self.output_field.split("=", 1)
            if source_field in result:
                processed = {target_field: result[source_field]}
                self.log_debug(f"[GraphAgent] Output mapping: {source_field} -> {target_field}")
                return processed
        
        # Handle specific output field
        elif self.output_field and self.output_field in result:
            return result[self.output_field]
        
        # Default: return entire result (your current behavior)
        return result