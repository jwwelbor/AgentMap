"""
Execution tracker for monitoring graph execution flow and results.
"""
import time
from typing import Any, Dict, List, Optional
from dependency_injector.wiring import inject, Provide
import logging
class ExecutionTracker:
    """Track execution status and history through a graph execution."""
    def __init__(
        self, 
        tracking_config: Dict[str, Any],
        execution_config: Dict[str, Any],
        logger: logging.Logger
    ):
        """
        Initialize the execution tracker with optional configuration.
        
        Args:
            config: Tracking configuration dictionary
        """
        self.minimal_mode = not tracking_config.get("enabled", True)
        self.execution_config = execution_config
        self.tracking_config = tracking_config
        self.logger = logger
        
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
        self.graph_success = evaluate_success_policy(summary, self.execution_config, self.logger)
        
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

    def record_subgraph_execution(self, subgraph_name: str, subgraph_summary: Dict[str, Any]):
        """
        Record execution of a subgraph as a nested execution.
        
        Args:
            subgraph_name: Name of the executed subgraph
            subgraph_summary: Complete execution summary from the subgraph
        """
        self.logger.debug(f"Recording subgraph execution: {subgraph_name}")
        
        # Ensure current node exists in results
        if self.current_node and self.current_node in self.node_results:
            # Initialize subgraphs dict if not exists
            if "subgraphs" not in self.node_results[self.current_node]:
                self.node_results[self.current_node]["subgraphs"] = {}
            
            # Store the complete subgraph execution summary
            self.node_results[self.current_node]["subgraphs"][subgraph_name] = subgraph_summary
            
            self.logger.info(f"Recorded subgraph '{subgraph_name}' execution in node '{self.current_node}'")
        else:
            self.logger.warning(f"Cannot record subgraph '{subgraph_name}' - no current node context")

    def get_summary(self) -> Dict[str, Any]:
        """
        Enhanced summary including subgraph executions.
        
        Returns:
            Dictionary containing execution summary with nested subgraph details
        """
        # Get the base summary (call existing method)
        summary = super().get_summary() if hasattr(super(), 'get_summary') else self._get_base_summary()
        
        # Add subgraph execution statistics
        subgraph_count = 0
        subgraph_details = {}
        
        for node_name, node_result in self.node_results.items():
            if "subgraphs" in node_result:
                for subgraph_name, subgraph_summary in node_result["subgraphs"].items():
                    subgraph_count += 1
                    if subgraph_name not in subgraph_details:
                        subgraph_details[subgraph_name] = []
                    subgraph_details[subgraph_name].append({
                        "parent_node": node_name,
                        "success": subgraph_summary.get("overall_success", False),
                        "node_count": len(subgraph_summary.get("nodes", {}))
                    })
        
        # Add subgraph information to summary
        summary["subgraph_executions"] = subgraph_count
        summary["subgraph_details"] = subgraph_details
        
        return summary

    def _get_base_summary(self) -> Dict[str, Any]:
        """
        Fallback method to get base summary if super().get_summary() doesn't exist.
        This maintains compatibility with the existing ExecutionTracker implementation.
        """
        return {
            "overall_success": self.overall_success,
            "graph_success": self.graph_success, 
            "nodes": dict(self.node_results),
            "execution_time": getattr(self, 'execution_time', 0),
            "node_count": len(self.node_results)
        }