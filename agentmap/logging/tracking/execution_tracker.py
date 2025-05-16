"""
Execution tracker for monitoring graph execution flow and results.
"""
import time
from typing import Any, Dict, List, Optional

from agentmap.logging import get_logger

logger = get_logger(__name__)

class ExecutionTracker:
    """Track execution status and history through a graph execution."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the execution tracker with optional configuration.
        
        Args:
            config: Tracking configuration dictionary
        """
        self.config = config or {}
        tracking_config = self.config.get("tracking", {})
        self.minimal_mode = not tracking_config.get("enabled", True)
        
        self.node_results = {}  # node_name -> {success, result, error, time}
        self.execution_path = []  # List of nodes in execution order
        self.start_time = time.time()
        self.end_time = None
        self.overall_success = True  # Default to success until a failure occurs
        self.graph_success = True    # Success according to policy, updated after each node
        
        # Only track these in full mode
        self.track_outputs = tracking_config.get("track_outputs", False) and not self.minimal_mode
        self.track_inputs = tracking_config.get("track_inputs", False) and not self.minimal_mode
        
    def record_node_start(self, node_name: str, inputs: Optional[Dict[str, Any]] = None) -> None:
        """
        Record the start of a node execution.
        
        Args:
            node_name: Name of the node being executed
            inputs: Optional inputs to the node (if track_inputs is True)
        """
        self.execution_path.append(node_name)
        
        node_info = {
            "start_time": time.time(),
            "success": None,
            "result": None,
            "error": None,
            "end_time": None,
            "duration": None,
        }
        
        # Add inputs if tracking is enabled
        if self.track_inputs and inputs:
            node_info["inputs"] = inputs
            
        self.node_results[node_name] = node_info
        
    def record_node_result(self, node_name: str, success: bool, 
                          result: Any = None, error: Optional[str] = None) -> None:
        """
        Record the result of a node execution.
        
        Args:
            node_name: Name of the node
            success: Whether the execution was successful
            result: Optional result of execution
            error: Optional error message if failed
        """
        end_time = time.time()
        if node_name in self.node_results:
            update_dict = {
                "success": success,
                "error": error,
                "end_time": end_time,
                "duration": end_time - self.node_results[node_name]["start_time"]
            }
            
            # Only store result if tracking outputs is enabled
            if self.track_outputs and result is not None:
                update_dict["result"] = result
                
            self.node_results[node_name].update(update_dict)
        
        # Update overall success if this node failed
        if not success:
            self.overall_success = False
            
    def update_graph_success(self) -> bool:
        """
        Update the graph_success flag based on the current policy.
        
        Returns:
            Current graph success status
        """
        from agentmap.logging.tracking.policy import evaluate_success_policy
        
        # Get current summary and evaluate policy
        summary = self.get_summary()
        self.graph_success = evaluate_success_policy(summary)
        
        return self.graph_success
        
    def complete_execution(self) -> None:
        """Mark the execution as complete."""
        self.end_time = time.time()
        
        # Final update of graph success
        self.update_graph_success()
        
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the execution.
        
        Returns:
            Dictionary containing execution summary
        """
        return {
            "overall_success": self.overall_success,  # Raw success (all nodes succeeded)
            "graph_success": self.graph_success,      # Policy-based success
            "execution_path": self.execution_path,
            "node_results": self.node_results,
            "total_duration": (self.end_time or time.time()) - self.start_time,
            "start_time": self.start_time,
            "end_time": self.end_time or time.time(),
        }
