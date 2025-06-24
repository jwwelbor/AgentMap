"""
Execution result domain model for AgentMap.

This module contains the ExecutionResult model which is a pure data container
for holding the complete result of a graph execution.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .execution_summary import ExecutionSummary


@dataclass
class ExecutionResult:
    """Pure data container for complete graph execution results.

    This model only holds data - all business logic belongs in GraphRunnerService.

    Attributes:
        graph_name: Name of the executed graph
        final_state: Final state dictionary from graph execution
        execution_summary: ExecutionSummary containing detailed execution tracking
        success: Whether the overall execution was successful
        total_duration: Total execution time in seconds
        compiled_from: Source of the executed graph ("precompiled", "autocompiled", "memory")
        error: Optional error message if execution failed
    """

    graph_name: str
    final_state: Dict[str, Any]
    execution_summary: ExecutionSummary
    success: bool
    total_duration: float
    compiled_from: str
    error: Optional[str] = None
