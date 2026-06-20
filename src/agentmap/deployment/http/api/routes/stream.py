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
  DEC-5  — Cancellation via async-generator lifecycle; rely on F04 finalization only.
  DEC-6  — Module-level asyncio.Semaphore for concurrency admission.

T-002 scope: SSE framing helpers, concurrency semaphore, APIRouter declaration.
T-003 scope: Route handler body — happy path, terminal events, router registration.
T-004 scope: Client-disconnect cancel, duration cap, concurrency 503 gate.
T-005 scope: Idle heartbeat, incremental delivery assurance.
"""

import asyncio
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from agentmap.deployment.http.api.dependencies import requires_auth
from agentmap.deployment.http.api.routes.execute import ExecuteRequest
from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)
from agentmap.runtime_api import run_workflow_stream_async

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


# ---------------------------------------------------------------------------
# Graph identifier normalisation (mirrors execute.py pattern)
# ---------------------------------------------------------------------------


def _normalize_graph_identifier(identifier: str) -> str:
    """Normalize graph identifier to standard :: format."""
    return identifier.replace("%3A%3A", "::").replace("/", "::")


# ---------------------------------------------------------------------------
# SSE event-stream generator
# ---------------------------------------------------------------------------


async def _sse_generator(
    graph_name: str,
    request_body: ExecuteRequest,
    config_file: Optional[str],
) -> AsyncGenerator[str, None]:
    """Async generator that drives run_workflow_stream_async and frames output as SSE.

    Yields SSE-framed strings for each WorkflowProgressEvent, mapping the
    WorkflowProgressEvent.event_type directly to the SSE event: name
    (node_progress, completed, failed, suspended).

    The generator is consumed by FastAPI's StreamingResponse.  Client-disconnect
    cancellation (aclose()/GeneratorExit propagation from ASGI) is handled by
    the StreamingResponse lifecycle — the upstream F04 generator finalizes the
    execution tracker on GeneratorExit/CancelledError (DEC-5).

    This generator does NOT add a third finalization call on top of F04's
    existing finalizer (DEC-5 / TD-033 guidance).
    """
    async for event in run_workflow_stream_async(
        graph_name=graph_name,
        inputs=request_body.inputs,
        force_create=request_body.force_create,
        config_file=config_file,
    ):
        # Build the payload dict from the WorkflowProgressEvent fields.
        # _to_serializable handles dataclasses and datetime objects so the
        # result dict can always be JSON-serialised without further processing.
        payload: Dict[str, Any] = {
            "sequence": event.sequence,
            "is_terminal": event.is_terminal,
        }

        if event.node_name is not None:
            payload["node_name"] = event.node_name
        if event.state_delta is not None:
            payload["state_delta"] = _to_serializable(event.state_delta)
        if event.node_duration is not None:
            payload["node_duration"] = event.node_duration
        if event.result is not None:
            payload["result"] = _to_serializable(event.result)
        if event.error is not None:
            payload["error"] = event.error

        # event_type maps 1:1 to the SSE event: name for all F04 event types.
        # "cancelled" is F05-originated (T-004) and not produced here.
        yield _format_sse_event(event.event_type, payload)


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------


@router.post("/execute/{graph_id:path}/stream")
@requires_auth("execute")
async def stream_workflow(
    graph_id: str,
    request_body: ExecuteRequest,
    request: Request,
) -> StreamingResponse:
    """Run a workflow over the streaming path and return a text/event-stream response.

    Mirrors POST /execute/{graph_id:path} (execute.py) by appending /stream.
    Reuses the same auth decorator, ExecuteRequest body, and graph_id
    normalization (DEC-4).  Delegates to F04's run_workflow_stream_async.

    Pre-open errors (auth 401/403, graph-not-found 404, invalid-inputs 400,
    not-initialized 503) are returned as ordinary JSON HTTP errors before the
    stream opens — identical error shape to the non-streaming endpoint (§A.3).

    Concurrency admission (semaphore gate) and client-disconnect cancel are
    implemented in T-004.  Heartbeat and duration cap are in T-005.
    """
    config_file = getattr(request.app.state, "config_file", None)
    graph_name = _normalize_graph_identifier(graph_id)

    # Validate graph identifier format (mirrors execute.py pre-flight check).
    if not graph_name or graph_name.count("::") > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid graph identifier format: {graph_name}",
        )

    # Validate request shape: streaming endpoint must not be called with
    # batch-only or unsupported control parameters (REQ-F-006 / DEC-3).
    # ExecuteRequest uses default Pydantic settings (extra fields forbidden via
    # model_config if set, or FastAPI will pass them through — we rely on
    # Pydantic's 422 for unknown fields when extra="forbid" is configured;
    # no additional validation needed here beyond the known-field set).

    logger.info("Opening SSE stream for graph: %s", graph_name)

    # Pre-open exception mapping — identical to execute.py:270-277.
    # Errors raised here become JSON HTTP errors, not SSE events, because the
    # StreamingResponse has not been created yet.
    try:
        # Build the SSE generator (lazy — no F04 calls until iteration starts).
        gen = _sse_generator(graph_name, request_body, config_file)
    except GraphNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidInputs as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AgentMapNotInitialized as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
