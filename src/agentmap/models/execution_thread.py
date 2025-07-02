from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID


@dataclass
class ExecutionThread:
    """Represents a workflow execution thread that can be paused and resumed."""

    id: str = ""
    graph_name: str = ""
    status: str = ""
    current_node: str = ""
    state_snapshot: Dict[str, Any] = field(default_factory=dict)
    execution_tracker_data: Dict[str, Any] = field(default_factory=dict)
    interaction_request_id: Optional[UUID] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
