"""SSE streaming route for graph-progress events.

Adds a single HTTP endpoint that runs a workflow over the streaming path
(F04's run_workflow_stream_async) and returns a text/event-stream (Server-Sent
Events) response.  This module is purely additive; existing routes in
execute.py are byte-for-byte unchanged (REQ-F-008).

Design decisions (spec.md E06-F05):
  DEC-1  — Only graph-progress SSE; direct-LLM HTTP surface is deferred.
  DEC-2  — No GZip middleware (would buffer SSE, defeating incremental delivery).
  DEC-3  — No direct-LLM stream symbols imported (AC-9 / TD-026 structural isolation).
  DEC-4  — New module per-domain router (not edits to execute.py).
  DEC-6  — Module-level asyncio.Semaphore for concurrency admission.

T-002 scope: SSE framing helpers, concurrency semaphore, APIRouter declaration.
Route handler body is added in T-003/T-004/T-005.
"""

import asyncio
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-domain router (DEC-4: new module, not edits to execute.py)
# ---------------------------------------------------------------------------

router = APIRouter(tags=["Streaming"])

# ---------------------------------------------------------------------------
# Module-level concurrency semaphore (DEC-6)
#
# Sized from get_sse_config()["max_concurrent_streams"].  At import time we
# cannot call get_sse_config() because the DI container has not started yet;
# we use the documented default (100 per spec.md §A.4) so the semaphore is
# always ready.  The route handler reads the live config for other envelope
# values (duration cap, heartbeat cadence) at request time.
# ---------------------------------------------------------------------------

_DEFAULT_MAX_CONCURRENT_STREAMS = 100
_stream_semaphore: asyncio.Semaphore = asyncio.Semaphore(
    _DEFAULT_MAX_CONCURRENT_STREAMS
)


# ---------------------------------------------------------------------------
# SSE wire-format helpers (spec.md §A.3)
# ---------------------------------------------------------------------------


def _format_sse_event(event_name: str, data_dict: Dict[str, Any]) -> str:
    """Format a WorkflowProgressEvent projection as an SSE event block.

    Produces the exact SSE framing required by spec.md §A.3:

        event: <event_name>\\n
        data: <single-line compact JSON>\\n
        \\n

    Args:
        event_name: The SSE event-type name (e.g. "node_progress", "completed",
            "failed", "suspended", "cancelled").  Maps 1:1 from
            WorkflowProgressEvent.event_type for all F04-originated events;
            "cancelled" is F05-originated for client-disconnect / duration-cap.
        data_dict: The payload dict to serialize.  All values must already be
            JSON-serialisable (call _to_serializable() first if the dict
            contains dataclasses or datetimes).

    Returns:
        SSE-framed string ending with a blank line (\\n\\n).
    """
    data_json = json.dumps(data_dict)
    return f"event: {event_name}\ndata: {data_json}\n\n"


def _format_sse_heartbeat() -> str:
    """Return an SSE keepalive comment line.

    Produces the heartbeat format required by spec.md §A.3:

        :keepalive\\n\\n

    An SSE comment line (starts with ':') keeps the connection alive without
    appearing as a typed event to an EventSource consumer — it is never
    delivered to event handlers on the client side (AC-7).

    Returns:
        SSE comment string ':keepalive\\n\\n'.
    """
    return ":keepalive\n\n"


def _to_serializable(value: Any) -> Any:
    """Convert dataclasses, datetimes, and nested structures to JSON-friendly values.

    Mirrors the pattern at execute.py:130 so WorkflowProgressEvent payloads
    can be fed directly to _format_sse_event() without extra processing by
    the route handler.

    Args:
        value: Any Python value.

    Returns:
        A JSON-serialisable equivalent of value.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return _to_serializable(asdict(value))
    if isinstance(value, dict):
        return {key: _to_serializable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_serializable(item) for item in value]
    return value
