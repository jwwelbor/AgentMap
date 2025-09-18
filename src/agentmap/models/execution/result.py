"""
Execution result domain model for AgentMap.

This module contains the ExecutionResult model which is a pure data container
for holding the complete result of a graph execution.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .summary import ExecutionSummary


@dataclass
class ExecutionResult:
    """Pure data container for complete graph execution results.

    This model only holds data - all business logic belongs in GraphRunnerService.

    Attributes:
        graph_name: Name of the executed graph
        final_state: Final state dictionary from graph execution
        execution_summary: Optional[ExecutionSummary] containing detailed execution tracking
        success: Whether the overall execution was successful
        total_duration: Total execution time in seconds
        error: Optional error message if execution failed
    """

    graph_name: str
    final_state: Dict[str, Any]
    execution_summary: Optional[ExecutionSummary]
    success: bool
    total_duration: float
    error: Optional[str] = None
