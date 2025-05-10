import time
from typing import Any, Callable

from agentmap.state.adapter import StateAdapter
from agentmap.logging import get_logger

logger = get_logger(__name__)

class TrackedNode:
    """
    Node wrapper that tracks execution steps in the state.
    
    This wrapper records each node execution in an execution_steps list
    within the state, providing trace-like functionality without relying
    on framework-specific tracing methods.
    """
    
    def __init__(self, node_name: str, node_function: Callable):
        """
        Initialize the tracked node.
        
        Args:
            node_name: Name of the node being tracked
            node_function: Original node function to call
        """
        self.node_name = node_name
        self.node_function = node_function
        
    def __call__(self, state: Any) -> Any:
        """
        Execute the node and track its execution.
        
        Args:
            state: Current state object
            
        Returns:
            Updated state with execution tracking
        """
        # Initialize execution_steps if it doesn't exist
        if not StateAdapter.get_value(state, "execution_steps"):
            state = StateAdapter.set_value(state, "execution_steps", [])
        
        try:
            # Record the start time
            start_time = time.time()
            
            # Call the original function
            result = self.node_function(state)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Record this execution step
            execution_steps = StateAdapter.get_value(result, "execution_steps", [])
            execution_steps.append({
                "node": self.node_name,
                "timestamp": start_time,
                "duration": execution_time,
                "success": True
            })
            
            logger.debug(f"[TrackedNode] Node '{self.node_name}' executed successfully in {execution_time:.3f}s")
            
            return StateAdapter.set_value(result, "execution_steps", execution_steps)
            
        except Exception as e:
            # Calculate execution time even for failures
            execution_time = time.time() - start_time
            
            # Record this execution step with error
            execution_steps = StateAdapter.get_value(state, "execution_steps", [])
            execution_steps.append({
                "node": self.node_name,
                "timestamp": start_time,
                "duration": execution_time,
                "success": False,
                "error": str(e)
            })
            
            logger.error(f"[TrackedNode] Node '{self.node_name}' failed in {execution_time:.3f}s: {str(e)}")
            
            # Re-raise the exception
            raise