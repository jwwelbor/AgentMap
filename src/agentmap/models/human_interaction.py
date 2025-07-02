from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class InteractionType(Enum):
    """Types of human interactions supported by the system."""

    APPROVAL = "approval"
    EDIT = "edit"
    CHOICE = "choice"
    TEXT_INPUT = "text_input"
    CONVERSATION = "conversation"


@dataclass
class HumanInteractionRequest:
    """Represents a request for human interaction in a workflow."""

    id: UUID = field(default_factory=uuid4)
    thread_id: str = ""
    node_name: str = ""
    interaction_type: InteractionType = InteractionType.TEXT_INPUT
    prompt: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    options: List[str] = field(default_factory=list)
    timeout_seconds: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HumanInteractionResponse:
    """Represents a human's response to an interaction request."""

    request_id: UUID
    action: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
