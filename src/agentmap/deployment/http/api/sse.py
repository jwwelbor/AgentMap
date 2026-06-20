"""SSE wire-format helpers and the concurrency limiter for the streaming route.

Split out of ``routes/stream.py`` so that module stays within the 350-line file
limit (CLAUDE.md ``max_file_lines``; spec.md E06-F05 §A.1 — "split out only if
stream.py would exceed the 350-line limit").  These are the small, pure, reusable
pieces of the SSE transport:

  * ``format_sse_event``      — frame an event block (``event:``/``data:``/blank).
  * ``format_sse_heartbeat``  — frame a ``:keepalive`` SSE comment line.
  * ``to_serializable``       — JSON-friendly projection of dataclasses/datetimes.
  * ``stream_semaphore``      — module-level concurrency-admission semaphore.

``routes/stream.py`` re-exports these (private-aliased) so existing call sites and
tests that reference them via the route module continue to resolve unchanged.
"""

import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Module-level concurrency semaphore (DEC-6)
#
# Sized from get_sse_config()["max_concurrent_streams"].  At import time we
# cannot call get_sse_config() because the DI container has not started yet;
# we use the documented default (100 per spec.md §A.4) so the semaphore is
# always ready.  The route handler reads the live config for other envelope
# values (duration cap, heartbeat cadence) at request time.
# ---------------------------------------------------------------------------

DEFAULT_MAX_CONCURRENT_STREAMS = 100
stream_semaphore: asyncio.Semaphore = asyncio.Semaphore(DEFAULT_MAX_CONCURRENT_STREAMS)


# ---------------------------------------------------------------------------
# SSE wire-format helpers (spec.md §A.3)
# ---------------------------------------------------------------------------


def format_sse_event(event_name: str, data_dict: Dict[str, Any]) -> str:
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
            JSON-serialisable (call to_serializable() first if the dict
            contains dataclasses or datetimes).

    Returns:
        SSE-framed string ending with a blank line (\\n\\n).
    """
    data_json = json.dumps(data_dict)
    return f"event: {event_name}\ndata: {data_json}\n\n"


def format_sse_heartbeat() -> str:
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


def to_serializable(value: Any) -> Any:
    """Convert dataclasses, datetimes, and nested structures to JSON-friendly values.

    Mirrors the pattern at execute.py:130 so WorkflowProgressEvent payloads
    can be fed directly to format_sse_event() without extra processing by
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
        return to_serializable(asdict(value))
    if isinstance(value, dict):
        return {key: to_serializable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_serializable(item) for item in value]
    return value


def project_event_to_sse(event: Any) -> str:
    """Project a WorkflowProgressEvent onto its SSE-framed wire string.

    Maps ``event.event_type`` directly to the SSE ``event:`` name (node_progress,
    completed, failed, suspended) and serialises only the populated fields as the
    compact ``data:`` JSON (spec.md §A.3).  ``to_serializable`` handles dataclasses
    and datetimes so the payload is always JSON-serialisable.
    """
    payload: Dict[str, Any] = {
        "sequence": event.sequence,
        "is_terminal": event.is_terminal,
    }

    if event.node_name is not None:
        payload["node_name"] = event.node_name
    if event.state_delta is not None:
        payload["state_delta"] = to_serializable(event.state_delta)
    if event.node_duration is not None:
        payload["node_duration"] = event.node_duration
    if event.result is not None:
        payload["result"] = to_serializable(event.result)
    if event.error is not None:
        payload["error"] = event.error

    return format_sse_event(event.event_type, payload)
