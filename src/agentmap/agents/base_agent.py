"""
Base agent class for all AgentMap agents.
"""
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from agentmap.logging import get_logger
from agentmap.state.adapter import StateAdapter
from agentmap.state.manager import StateManager

class BaseAgent:
    """Base class for all agents in AgentMap."""
    
    # Class-level logger for shared logging configuration
    _logger = get_logger("agentmap.agents")
    
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
        self.output_field = self.context.get("output_field", "output")
        
        # Create state manager
        self.state_manager = StateManager(self.input_fields, self.output_field)
        
        # Initialize logger with instance-specific prefix
        # We use the class-level logger but store the prefix
        self._log_prefix = f"[{self.__class__.__name__}:{self.name}]"
        
    def log(self, level: str, message: str, *args, **kwargs):
        """
        Log a message with the specified level and proper agent context.
        
        Args:
            level: Log level ('debug', 'info', 'warning', 'error', 'trace')
            message: Log message
            *args, **kwargs: Additional arguments passed to the logger
        """
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
            Output value for the output_field
        """
        raise NotImplementedError("Subclasses must implement process()")


    def run(self, state: Any) -> Any:
        """
        Run the agent on the state, extracting inputs and setting outputs.
        This is the standard execution flow that most agents should follow.

        Args:
            state: Current state object (can be dict, Pydantic model, etc.)

        Returns:
            Updated state with output field and success flag
        """
        # Generate a unique execution ID
        execution_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        self.log_trace(f"\n*** AGENT {self.name} RUN START [{execution_id}] at {start_time} ***")

        # Ensure execution tracker is present
        state = StateAdapter.initialize_execution_tracker(state)
        tracker = StateAdapter.get_execution_tracker(state)

        # Extract inputs
        inputs = self.state_manager.get_inputs(state)

        # Record node start
        tracker.record_node_start(self.name, inputs)

        try:
            # Pre-processing hook for subclasses
            state = self._pre_process(state, inputs)

            # Process inputs to get output
            self.log_trace(f"*** AGENT {self.name} CALLING PROCESS [{execution_id}] ***")
            output = self.process(inputs)
            self.log_trace(f"*** AGENT {self.name} PROCESS COMPLETE [{execution_id}] ***")

            # Set action success flag
            state = StateAdapter.set_value(state, "last_action_success", True)

            # Post-processing hook for subclasses - can modify both state and output
            state, output = self._post_process(state, output)

            # read last_action_success in case it was changed in post_process
            tracker.record_node_result(self.name, state.get("last_action_success", True), result=output)
            graph_success = tracker.update_graph_success()
            state = StateAdapter.set_value(state, "graph_success", graph_success)

            # Now set the final output and success flag
            if self.output_field:
                self.log_debug(f"[{self.name}] Setting output in field '{self.output_field}' with value: {output}")
                state = StateAdapter.set_value(state, self.output_field, output)

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

            # Update graph success based on policy
            graph_success = tracker.update_graph_success()

            # Store graph success in state
            state = StateAdapter.set_value(state, "graph_success", graph_success)

            # Set error in state
            state = StateAdapter.set_value(state, "error", error_msg)

            # Mark as failure
            state = StateAdapter.set_value(state, "last_action_success", False)

            # Try to run post-process but don't let its errors override the original error
            try:
                state, _ = self._post_process(state, None)
            except Exception as post_error:
                self.log_error(f"Error in post-processing: {str(post_error)}")

            end_time = time.time()
            duration = end_time - start_time
            self.log_trace(f"\n*** AGENT {self.name} RUN FAILED [{execution_id}] in {duration:.4f}s ***")
            return state
    
    def _pre_process(self, state: Any, inputs: Dict[str, Any]) -> Any:
        """
        Pre-processing hook that can be overridden by subclasses.
        
        Args:
            state: Current state
            inputs: Extracted input values
            
        Returns:
            Potentially modified state
        """
        return state
    
    def _post_process(self, state: Any, output: Any) -> Tuple[Any, Any]:
        """
        Post-processing hook that can be overridden by subclasses.
        Allows modification of both the state and output.
        
        Args:
            state: The current state
            output: The output value from the process method
            
        Returns:
            Tuple of (state, output) - both can be modified
        """
        return state, output
    
    def invoke(self, state: Any) -> Any:
        """Alias for run() to maintain compatibility with LangGraph."""
        return self.run(state)
