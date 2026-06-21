# src/agentmap/models/execution/__init__.py
"""
Execution domain models for AgentMap.

Exports the primary execution-related data models so that consumers can import
them from ``agentmap.models.execution`` (e.g.
``from agentmap.models.execution import WorkflowProgressEvent``).

Existing callers that import directly from the submodule paths (e.g.
``from agentmap.models.execution.result import ExecutionResult``) continue to
work unchanged — this __init__ does NOT alter the submodule layout.
"""

from .progress_event import WorkflowProgressEvent
from .result import ExecutionResult
from .summary import ExecutionSummary, NodeExecution
from .tracker import ExecutionTracker

__all__ = [
    "ExecutionResult",
    "ExecutionSummary",
    "ExecutionTracker",
    "NodeExecution",
    "WorkflowProgressEvent",
]
