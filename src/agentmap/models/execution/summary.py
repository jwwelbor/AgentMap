"""
Execution summary domain models for AgentMap.

This module contains ExecutionSummary and NodeExecution models which are
pure data containers for tracking graph execution results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional


@dataclass
class NodeExecution:
    """Pure data container for individual node execution record.

    Attributes:
        node_name: Name of the executed node
        success: Whether the execution was successful
        start_time: When the node execution started
        end_time: When the node execution ended
        duration: Execution duration in seconds
        output: Optional output from the node execution
        error: Optional error message if execution failed
    """

    node_name: str
    success: bool
    start_time: datetime
    end_time: datetime
    duration: float
    output: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ExecutionSummary:
    """Pure data container for execution tracking.

    This model only holds data - all business logic belongs in ExecutionService.

    Attributes:
        graph_name: Name of the graph being executed
        start_time: When the graph execution started
        end_time: When the graph execution ended
        node_executions: List of individual node execution records
        final_output: Final output from the graph execution
        graph_success: Whether the overall graph execution was successful should be executed accoring to the configured execution_policy_service
        status: Current execution status
    """

    graph_name: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    node_executions: List[NodeExecution] = field(default_factory=list)
    final_output: Optional[Any] = None
    graph_success: Optional[bool] = None
    status: str = "pending"
