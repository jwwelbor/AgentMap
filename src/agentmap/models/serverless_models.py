"""
Pure data containers for serverless request handling.

This module provides the data models used throughout the serverless
handler system without any business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class TriggerType(Enum):
    """Supported trigger types for serverless functions."""

    HTTP = "http"
    MESSAGE_QUEUE = "queue"
    DATABASE = "database"
    TIMER = "timer"
    STORAGE = "storage"


@dataclass(frozen=True)
class RequestContext:
    """Context information for a serverless request."""

    correlation_id: str
    trigger_type: TriggerType
    timestamp_utc: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass(frozen=True)
class ExecutionParams:
    """Parameters needed for graph execution."""

    graph: Optional[str] = None
    csv: Optional[str] = None
    state: Dict[str, Any] = field(default_factory=dict)
    execution_id: Optional[str] = None


@dataclass(frozen=True)
class ExecutionRequest:
    """Complete request information for execution."""

    context: RequestContext
    payload: Dict[str, Any]  # normalized payload (includes trigger_type/correlation_id)
    params: ExecutionParams  # minimal inputs ExecutionService needs


@dataclass(frozen=True)
class ExecutionResult:
    """Result of graph execution."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: int = 200
