from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class NodeExecution:
    node_name: str
    success: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    subgraph_execution_tracker: Optional["ExecutionTracker"] = None
    inputs: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionTracker:
    node_executions: List[NodeExecution] = field(default_factory=list)
    node_execution_counts: Dict[str, int] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    overall_success: bool = True
    track_inputs: bool = False
    track_outputs: bool = False
    minimal_mode: bool = False
    thread_id: Optional[str] = None  # LangGraph thread ID for checkpoint support
