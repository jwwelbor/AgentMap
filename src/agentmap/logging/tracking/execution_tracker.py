"""
Execution tracker for monitoring graph execution flow and results.
"""
import time
from typing import Any, Dict, List, Optional
from agentmap.services.logging_service import LoggingService
from agentmap.services.config.app_config_service import AppConfigService


class ExecutionTracker:
    """Track execution status and history through a graph execution."""
    def __init__(
        self, 
        app_config_service: AppConfigService,
        logging_service: LoggingService,
    ):
        """
        Initialize the execution tracker with optional configuration.
        
        Args:
            config: Tracking configuration dictionary
        """
        self.execution_config = app_config_service.get_execution_config() 
        self.tracking_config = app_config_service.get_tracking_config()
        self._logger = logging_service.get_class_logger(self)
        
        # Enhanced data structures for execution tracking
        self.execution_path = []  # List of execution records (dicts) in chronological order
        self.node_execution_counts = {}  # Track execution count per node
        self.start_time = time.time()
        self.end_time = None
        self.overall_success = True  # Default to success until a failure occurs
        self.graph_success = True    # Success according to policy, updated after each node
        
        # Only track these in full mode
        self.minimal_mode = not self.tracking_config.get("enabled", True)
        self.track_outputs = self.tracking_config.get("track_outputs", False) and not self.minimal_mode
        self.track_inputs = self.tracking_config.get("track_inputs", False) and not self.minimal_mode
        
    def record_node_start(self, node_name: str, inputs: Optional[Dict[str, Any]] = None) -> None:
        """
        Record the start of a node execution.
        
        Args:
            node_name: Name of the node being executed
            inputs: Optional inputs to the node (if track_inputs is True)
        """
        # Increment execution counter for this node
        self.node_execution_counts[node_name] = self.node_execution_counts.get(node_name, 0) + 1
        
        # Create rich execution record
        execution_record = {
            "node_name": node_name,
            "execution_index": len(self.execution_path),
            "node_execution_number": self.node_execution_counts[node_name],
            "start_time": time.time(),
            "end_time": None,
            "duration": None,
            "success": None,
            "result": None,
            "error": None
        }
        
        # Add inputs if tracking is enabled
        if self.track_inputs and inputs:
            execution_record["inputs"] = inputs
        
        # Append complete record to execution path
        self.execution_path.append(execution_record)
        
    def record_node_result(
            self, 
            node_name: str, 
            success: bool, 
            result: Any = None, 
            error: Optional[str] = None) -> None:
        """
        Record the result of a node execution.
        
        Args:
            node_name: Name of the node
            success: Whether the execution was successful
            result: Optional result of execution
            error: Optional error message if failed
        """
        end_time = time.time()
        
        # Find the most recent execution record for this node (iterate backwards)
        for i in range(len(self.execution_path) - 1, -1, -1):
            record = self.execution_path[i]
            if record["node_name"] == node_name and record["success"] is None:
                # Update the execution record with completion details
                record.update({
                    "success": success,
                    "error": error,
                    "end_time": end_time,
                    "duration": end_time - record["start_time"]
                })
                
                # Only store result if tracking outputs is enabled
                if self.track_outputs and result is not None:
                    record["result"] = result
                
                break
        
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
        self.graph_success = evaluate_success_policy(summary, self.execution_config, self._logger)
        
        return self.graph_success
        
    def complete_execution(self) -> None:
        """Mark the execution as complete."""
        self.end_time = time.time()
        
        # Final update of graph success
        self.update_graph_success()
        
    def record_subgraph_execution(self, subgraph_name: str, subgraph_summary: Dict[str, Any]):
        """
        Record execution of a subgraph as a nested execution.
        
        Args:
            subgraph_name: Name of the executed subgraph
            subgraph_summary: Complete execution summary from the subgraph
        """
        self._logger.debug(f"Recording subgraph execution: {subgraph_name}")
        
        # Find the most recent incomplete execution record (currently executing node)
        current_execution = None
        for i in range(len(self.execution_path) - 1, -1, -1):
            record = self.execution_path[i]
            if record["success"] is None:  # Incomplete execution
                current_execution = record
                break
        
        if current_execution:
            # Initialize subgraphs dict if not exists
            if "subgraphs" not in current_execution:
                current_execution["subgraphs"] = {}
            
            # Store the complete subgraph execution summary
            current_execution["subgraphs"][subgraph_name] = subgraph_summary
            
            self._logger.info(f"Recorded subgraph '{subgraph_name}' execution in node '{current_execution['node_name']}'")
        else:
            self._logger.warning(f"Cannot record subgraph '{subgraph_name}' - no current node context")
        
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive summary of the execution including subgraph details.
        
        Returns:
            Dictionary containing execution summary with nested subgraph details
        """ 
        
        # Add subgraph execution statistics
        subgraph_count = 0
        subgraph_details = {}
        
        for record in self.execution_path:
            if "subgraphs" in record:
                for subgraph_name, subgraph_summary in record["subgraphs"].items():
                    subgraph_count += 1
                    if subgraph_name not in subgraph_details:
                        subgraph_details[subgraph_name] = []
                    subgraph_details[subgraph_name].append({
                        "parent_node": record["node_name"],
                        "success": subgraph_summary.get("overall_success", False),
                        "node_count": len(subgraph_summary.get("nodes", {}))
                    })
        
        return {
            "overall_success": self.overall_success,  # Raw success (all nodes succeeded)
            "graph_success": self.graph_success,      # Policy-based success
            "execution_path": self.execution_path,    # Enhanced execution records
            "subgraph_executions": subgraph_count,
            "subgraph_details": subgraph_details,
            "total_duration": (self.end_time or time.time()) - self.start_time,
            "start_time": self.start_time,
            "end_time": self.end_time or time.time(),
        }