import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from agentmap.models.execution.tracker import ExecutionTracker, NodeExecution
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


class ExecutionTrackingService:
    def __init__(
        self, app_config_service: AppConfigService, logging_service: LoggingService
    ):
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.logging_service = logging_service
        self.logger.info("[ExecutionTrackingService] Initialized")

    def create_tracker(self, thread_id: Optional[str] = None) -> ExecutionTracker:
        tracking_config = self.config.get_tracking_config()

        track_inputs = tracking_config.get("track_inputs", False)
        track_outputs = tracking_config.get("track_outputs", False)
        minimal_mode = not tracking_config.get("enabled", False)

        if minimal_mode:
            track_inputs = False
            track_outputs = False

        return ExecutionTracker(
            track_inputs=track_inputs,
            track_outputs=track_outputs,
            minimal_mode=minimal_mode,
            # pass exeisting thread ID or Generate unique thread ID for checkpoint support
            thread_id=thread_id or str(uuid.uuid4()),
        )

    def record_node_start(
        self,
        tracker: ExecutionTracker,
        node_name: str,
        inputs: Optional[Dict[str, Any]] = None,
    ):
        tracker.node_execution_counts[node_name] = (
            tracker.node_execution_counts.get(node_name, 0) + 1
        )

        node = NodeExecution(
            node_name=node_name,
            start_time=datetime.utcnow(),
            inputs=inputs if tracker.track_inputs else None,
        )
        tracker.node_executions.append(node)

    def record_node_result(
        self,
        tracker: ExecutionTracker,
        node_name: str,
        success: bool,
        result: Any = None,
        error: Optional[str] = None,
    ):
        for node in reversed(tracker.node_executions):
            if node.node_name == node_name and node.success is None:
                node.success = success
                node.end_time = datetime.utcnow()
                node.duration = (
                    (node.end_time - node.start_time).total_seconds()
                    if node.start_time
                    else None
                )
                if tracker.track_outputs:
                    node.output = result
                node.error = error
                break

        if not success:
            tracker.overall_success = False

    def complete_execution(self, tracker: ExecutionTracker):
        tracker.end_time = datetime.utcnow()

    def record_subgraph_execution(
        self,
        tracker: ExecutionTracker,
        subgraph_name: str,
        subgraph_tracker: ExecutionTracker,
    ):
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

    def serialize_tracker(self, tracker: ExecutionTracker) -> Dict[str, Any]:
        """
        Serialize an ExecutionTracker to a dictionary for storage.

        Args:
            tracker: ExecutionTracker to serialize

        Returns:
            Serialized tracker data
        """
        try:
            # Serialize node executions
            serialized_executions = []
            for node in tracker.node_executions:
                exec_data = {
                    "node_name": node.node_name,
                    "start_time": (
                        node.start_time.isoformat() if node.start_time else None
                    ),
                    "end_time": node.end_time.isoformat() if node.end_time else None,
                    "success": node.success,
                    "duration": node.duration,
                    "error": node.error,
                }

                # Include inputs/outputs if tracking is enabled
                if tracker.track_inputs and node.inputs is not None:
                    exec_data["inputs"] = node.inputs
                if tracker.track_outputs and node.output is not None:
                    exec_data["output"] = node.output

                # Handle subgraph tracker recursively
                if (
                    hasattr(node, "subgraph_execution_tracker")
                    and node.subgraph_execution_tracker
                ):
                    exec_data["subgraph_tracker"] = self.serialize_tracker(
                        node.subgraph_execution_tracker
                    )

                serialized_executions.append(exec_data)

            return {
                "start_time": (
                    tracker.start_time.isoformat() if tracker.start_time else None
                ),
                "end_time": tracker.end_time.isoformat() if tracker.end_time else None,
                "node_executions": serialized_executions,
                "node_execution_counts": dict(tracker.node_execution_counts),
                "overall_success": tracker.overall_success,
                "track_inputs": tracker.track_inputs,
                "track_outputs": tracker.track_outputs,
                "minimal_mode": tracker.minimal_mode,
                "graph_name": getattr(tracker, "graph_name", None),
                "thread_id": getattr(tracker, "thread_id", None),
            }
        except Exception as e:
            self.logger.error(f"Error serializing tracker: {str(e)}")
            return {"error": f"Failed to serialize tracker: {str(e)}"}

    def deserialize_tracker(self, data: Dict[str, Any]) -> Optional[ExecutionTracker]:
        """
        Deserialize a dictionary back to an ExecutionTracker.

        Args:
            data: Serialized tracker data

        Returns:
            ExecutionTracker instance or None if deserialization fails
        """
        try:
            # Create tracker with tracking settings
            tracker = ExecutionTracker(
                track_inputs=data.get("track_inputs", False),
                track_outputs=data.get("track_outputs", False),
                minimal_mode=data.get("minimal_mode", False),
            )

            # Restore basic attributes
            if data.get("start_time"):
                tracker.start_time = datetime.fromisoformat(data["start_time"])
            if data.get("end_time"):
                tracker.end_time = datetime.fromisoformat(data["end_time"])

            tracker.overall_success = data.get("overall_success", True)
            tracker.node_execution_counts = data.get("node_execution_counts", {})

            # Set optional attributes if present
            if data.get("graph_name"):
                tracker.graph_name = data["graph_name"]
            if data.get("thread_id"):
                tracker.thread_id = data["thread_id"]

            # Restore node executions
            for exec_data in data.get("node_executions", []):
                node = NodeExecution(
                    node_name=exec_data["node_name"],
                    start_time=(
                        datetime.fromisoformat(exec_data["start_time"])
                        if exec_data.get("start_time")
                        else None
                    ),
                    inputs=exec_data.get("inputs") if tracker.track_inputs else None,
                )

                # Restore completion data
                node.success = exec_data.get("success")
                if exec_data.get("end_time"):
                    node.end_time = datetime.fromisoformat(exec_data["end_time"])
                node.duration = exec_data.get("duration")
                node.error = exec_data.get("error")

                if tracker.track_outputs:
                    node.output = exec_data.get("output")

                # Handle subgraph tracker recursively
                if "subgraph_tracker" in exec_data:
                    node.subgraph_execution_tracker = self.deserialize_tracker(
                        exec_data["subgraph_tracker"]
                    )

                tracker.node_executions.append(node)

            return tracker

        except Exception as e:
            self.logger.error(f"Error deserializing tracker: {str(e)}")
            return None

    def to_summary(
        self, tracker: ExecutionTracker, graph_name: str, final_output: Any = None
    ):
        from agentmap.models.execution.summary import (
            ExecutionSummary,
        )
        from agentmap.models.execution.summary import (
            NodeExecution as SummaryNodeExecution,
        )

        summary_executions = []
        for node in tracker.node_executions:
            summary_executions.append(
                SummaryNodeExecution(
                    node_name=node.node_name,
                    success=node.success,
                    start_time=node.start_time,
                    end_time=node.end_time,
                    duration=node.duration,
                    output=node.output,
                    error=node.error,
                )
            )

        return ExecutionSummary(
            graph_name=graph_name,
            start_time=tracker.start_time,
            end_time=tracker.end_time,
            node_executions=summary_executions,
            final_output=final_output,  # Use the provided final_output instead of hardcoded None
            graph_success=tracker.overall_success,
            status="completed" if tracker.end_time else "in_progress",
        )
