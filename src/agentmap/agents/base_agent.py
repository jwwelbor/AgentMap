"""
Base agent class for all AgentMap agents.
"""
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import logging
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.models.execution_tracker import ExecutionTracker

class BaseAgent:
    """Base class for all agents in AgentMap."""
    
    def __init__(
        self, 
        name: str, 
        prompt: str, 
        context: dict = None,
        logger: Optional[logging.Logger] = None,
        execution_tracker: Optional[ExecutionTracker] = None
    ):
        """
        Initialize the agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction for LLM-based agents
            context: Additional context including configuration
            logger: Logger instance (required for proper operation)
            execution_tracker: ExecutionTracker instance (required for proper operation)
        """
        self.name = name
        self.prompt = prompt
        self.context = context or {}
        self.prompt_template = prompt
        
        # Extract input_fields and output_field from context if available
        self.input_fields = self.context.get("input_fields", [])
        self.output_field = self.context.get("output_field", "output")
        self.description = self.context.get("description", "")
        
        # Store logger and tracker - these can be None initially
        self._logger = logger
        self._execution_tracker = execution_tracker
        self._log_prefix = f"[{self.__class__.__name__}:{self.name}]"
        

        
    def log(self, level: str, message: str, *args, **kwargs):
        """
        Log a message with the specified level and proper agent context.
        
        Args:
            level: Log level ('debug', 'info', 'warning', 'error', 'trace')
            message: Log message
            *args, **kwargs: Additional arguments passed to the logger
            
        Raises:
            ValueError: When logger is not provided to agent
        """
        if self._logger is None:
            raise ValueError(
                f"Logger not provided to agent '{self.name}'. "
                "Please inject logger dependency using DI fixtures in tests or provide logger in constructor."
            )
        logger_method = getattr(self._logger, level, self._logger.info)
        logger_method(f"{self._log_prefix} {message}", *args, **kwargs)
    
    def log_debug(self, message: str, *args, **kwargs):
        """Log a debug message with agent context."""
        self.log("debug", message, *args, **kwargs)
        
    def log_info(self, message: str, *args, **kwargs):
        """Log an info message with agent context."""
        self.log("info", message, *args, **kwargs)
        
    def log_warning(self, message: str, *args, **kwargs):
        """Log a warning message with agent context."""
        self.log("warning", message, *args, **kwargs)
        
    def log_error(self, message: str, *args, **kwargs):
        """Log an error message with agent context."""
        self.log("error", message, *args, **kwargs)
        
    def log_trace(self, message: str, *args, **kwargs):
        """Log a trace message with agent context."""
        self.log("trace", message, *args, **kwargs)
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and return an output value.
        Subclasses should implement this method.
        
        Args:
            inputs: Dictionary of input values
            
        Returns:
            Tuple of (output_value, success)
            Output value for the output_field, was the action successful
        """
        raise NotImplementedError("Subclasses must implement process()")

    def run(self, state: Any) -> Dict[str, Any]:
        """
        FIXED: Run the agent and return only the fields that need updating.
        This method now returns a partial state update instead of the full state.
        Works with dynamic state schemas.

        Args:
            state: Current state object

        Returns:
            Dictionary with only the fields that need to be updated
            
        Raises:
            ValueError: When execution_tracker is not provided to agent
        """
        # Generate a unique execution ID
        execution_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        self.log_trace(f"\n*** AGENT {self.name} RUN START [{execution_id}] at {start_time} ***")

        # Get execution tracker - must be provided via DI
        if self._execution_tracker is None:
            raise ValueError(
                f"ExecutionTracker not provided to agent '{self.name}'. "
                "Please inject execution_tracker dependency using DI fixtures in tests or provide execution_tracker in constructor."
            )
        tracker = self._execution_tracker

        # Extract inputs
        inputs = StateAdapterService.get_inputs(state, self.input_fields)

        # Record node start
        tracker.record_node_start(self.name, inputs)

        try:
            # Pre-processing hook for subclasses
            state, inputs = self._pre_process(state, inputs)
            
            # Process inputs to get output
            output = self.process(inputs)

            # Post-processing hook for subclasses
            state, output = self._post_process(state, inputs, output)

            # Get final success status
            tracker.record_node_result(self.name, success=True, result=output)

            # Set the final output if we have an output field
            if self.output_field and output is not None:
                state = StateAdapterService.set_value(state, self.output_field, output)
                self.log_debug(f"Set output field '{self.output_field}' = {output}")

            end_time = time.time()
            duration = end_time - start_time
            self.log_trace(f"\n*** AGENT {self.name} RUN COMPLETED [{execution_id}] in {duration:.4f}s ***")
            
            return state

        except Exception as e:
            # Handle errors
            error_msg = f"Error in {self.name}: {str(e)}"
            self.log_error(error_msg)

            # Record failure
            tracker.record_node_result(self.name, False, error=error_msg)
            graph_success = tracker.update_graph_success()

            # Prepare error updates - only the fields that changed
            error_updates = {
                "graph_success": graph_success,
                "last_action_success": False,
                "errors": [error_msg]  # This will be added to existing errors
            }

            # Try to run post-process
            try:
                state, output = self._post_process(state, inputs, error_updates)

            except Exception as post_error:
                self.log_error(f"Error in post-processing: {str(post_error)}")

            end_time = time.time()
            duration = end_time - start_time
            self.log_trace(f"\n*** AGENT {self.name} RUN FAILED [{execution_id}] in {duration:.4f}s ***")
            
            # Return the updated state
            return state
    
    def _pre_process(self, state: Any, inputs: Dict[str, Any]) -> Tuple[Any, Any]:
        """
        Pre-processing hook that can be overridden by subclasses.
        
        Args:
            state: Current state
            inputs: Extracted input values
            
        Returns:
            Tuple of (state, processed_inputs)
        """
        return state, inputs
    
    def _post_process(self, state: Any, inputs: Dict[str, Any], output) -> Tuple[Any, Any]:
        """
        Post-processing hook that can be overridden by subclasses.
        
        Args:
            state: The current state
            output: The output value from the process method
            current_updates: The current set of updates being applied
            
        Returns:
            Tuple of (state, modified_output)
        """
        return state, output
    
    def invoke(self, state: Any) -> Dict[str, Any]:
        """Alias for run() to maintain compatibility with LangGraph."""
        return self.run(state)