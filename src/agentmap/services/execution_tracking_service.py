from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from datetime import datetime
from typing import Any, Dict, Optional

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.models.execution_tracker import ExecutionTracker, NodeExecution


class ExecutionTrackingService:
    def __init__(self, app_config_service: AppConfigService, logging_service: LoggingService):
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.logging_service = logging_service
        self.logger.info("[ExecutionTrackingService] Initialized")

    def create_tracker(self) -> ExecutionTracker:
        tracking_config = self.config.get_tracking_config()

        track_inputs=tracking_config.get("track_inputs", False)
        track_outputs=tracking_config.get("track_outputs", False)
        minimal_mode=not tracking_config.get("enabled", False)

        if minimal_mode:
            track_inputs = False
            track_outputs = False

        return ExecutionTracker(
            track_inputs=track_inputs,
            track_outputs=track_outputs,
            minimal_mode=minimal_mode
        )

    def record_node_start(self, tracker: ExecutionTracker, node_name: str, inputs: Optional[Dict[str, Any]] = None):
        tracker.node_execution_counts[node_name] = tracker.node_execution_counts.get(node_name, 0) + 1

        node = NodeExecution(
            node_name=node_name,
            start_time=datetime.utcnow(),
            inputs=inputs if tracker.track_inputs else None
        )
        tracker.node_executions.append(node)

    def record_node_result(self, tracker: ExecutionTracker, node_name: str, success: bool, result: Any = None, error: Optional[str] = None):
        for node in reversed(tracker.node_executions):
            if node.node_name == node_name and node.success is None:
                node.success = success
                node.end_time = datetime.utcnow()
                node.duration = (node.end_time - node.start_time).total_seconds() if node.start_time else None
                if tracker.track_outputs:
                    node.output = result
                node.error = error
                break

        if not success:
            tracker.overall_success = False

    def complete_execution(self, tracker: ExecutionTracker):
        tracker.end_time = datetime.utcnow()

    def record_subgraph_execution(self, tracker: ExecutionTracker, subgraph_name: str, subgraph_tracker: ExecutionTracker):
        for node in reversed(tracker.node_executions):
            if node.success is None:
                node.subgraph_execution_tracker = subgraph_tracker
                break

    def update_graph_success(self, tracker: ExecutionTracker) -> bool:
        """
        Update and return the current graph success status.
        
        Args:
            tracker: ExecutionTracker instance to update
            
        Returns:
            Boolean indicating overall graph success
        """
        return tracker.overall_success
    
    def to_summary(self, tracker: ExecutionTracker, graph_name: str, final_output: Any = None):
        from agentmap.models.execution_summary import ExecutionSummary, NodeExecution as SummaryNodeExecution

        summary_executions = []
        for node in tracker.node_executions:
            summary_executions.append(SummaryNodeExecution(
                node_name=node.node_name,
                success=node.success,
                start_time=node.start_time,
                end_time=node.end_time,
                duration=node.duration,
                output=node.output,
                error=node.error
            ))

        return ExecutionSummary(
            graph_name=graph_name,
            start_time=tracker.start_time,
            end_time=tracker.end_time,
            node_executions=summary_executions,
            final_output=final_output,  # Use the provided final_output instead of hardcoded None
            graph_success=tracker.overall_success,
            status="completed" if tracker.end_time else "in_progress"
        )
