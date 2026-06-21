"""SSE wire-format helpers and the concurrency limiter for the streaming route.

Split out of ``routes/stream.py`` so that module stays within the 350-line file
limit (CLAUDE.md ``max_file_lines``; spec.md E06-F05 §A.1 — "split out only if
stream.py would exceed the 350-line limit").  These are the small, pure, reusable
pieces of the SSE transport:

  * ``format_sse_event``      — frame an event block (``event:``/``data:``/blank).
  * ``format_sse_heartbeat``  — frame a ``:keepalive`` SSE comment line.
  * ``to_serializable``       — JSON-friendly projection of dataclasses/datetimes.
  * ``prime_upstream``        — pull F04's first event pre-open (§A.3 error contract).

The concurrency limiter (DEC-6 semaphore) lives in ``sse_concurrency.py`` (split out
to keep both modules under the 350-line limit).  ``routes/stream.py`` re-exports
these (private-aliased) so existing call sites and tests that reference them via the
route module continue to resolve unchanged.
"""

import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Iterable, Optional, Tuple

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)

# ---------------------------------------------------------------------------
# Pre-open priming (spec.md §A.3 — pre-open error contract; CR BLOCKER-2)
# ---------------------------------------------------------------------------


async def prime_upstream(
    upstream: AsyncGenerator[Any, None],
) -> Tuple[Optional[Any], bool]:
    """Pull the first upstream event so F04's prelude runs *before* the stream opens.

    ``run_workflow_stream_async`` is a lazy async generator: its prelude
    (``ensure_initialized`` / bundle resolution / graph lookup) does not execute
    until the first ``__anext__``, which — if iteration is deferred into
    ``StreamingResponse`` — happens only *after* Starlette has committed
    ``http.response.start`` (``200`` + ``text/event-stream``).  F04 raises
    ``GraphNotFound`` / ``InvalidInputs`` / ``AgentMapNotInitialized`` from that
    prelude "before any event", so deferring the first pull makes those pre-open
    errors surface as a broken mid-stream abort instead of the JSON HTTP error spec
    §A.3 requires.

    Priming the first event here — in the route handler, *before* the
    ``StreamingResponse`` is constructed — lets those three exceptions propagate to
    the caller, which maps them to ``404`` / ``400`` / ``503`` JSON pre-open (spec
    §A.3: "a failure to even start the run looks identical to the non-streaming
    endpoint").  The first event is returned so the route can replay it as the first
    SSE frame; the steady-state loop then drains the remaining events from the same
    ``upstream``, so cancellation / ``aclose()`` finalization (DEC-5) is unchanged.

    Args:
        upstream: The unstarted async generator from ``run_workflow_stream_async``.

    Returns:
        ``(first_event, exhausted)`` — ``first_event`` is the primed
        ``WorkflowProgressEvent`` (replay it before resuming iteration), or ``None``
        with ``exhausted=True`` if the generator ended without yielding any event
        (defensive; F04 always yields a terminal).

    Raises:
        GraphNotFound / InvalidInputs / AgentMapNotInitialized: propagated unchanged
            from F04's prelude so the route maps them to pre-open JSON.  (F04 already
            normalizes ``FileNotFoundError``/``ValueError`` to these before raising.)
    """
    try:
        first_event = await upstream.__anext__()
    except StopAsyncIteration:
        return None, True
    return first_event, False


async def aclose_upstream_and_release(
    pending: "Optional[asyncio.Future[Any]]",
    upstream: AsyncGenerator[Any, None],
    semaphore: Optional[asyncio.Semaphore],
) -> None:
    """Finalize the stream's upstream and release its concurrency slot (DEC-5/DEC-6).

    Closes ``upstream`` via ``aclose()`` so F04's finalizer runs (DEC-5 — no third
    finalize), then releases the ``semaphore`` slot exactly once.  An in-flight
    ``__anext__`` (e.g. the duration cap fired mid-await) is cancelled AND awaited
    first: ``aclose()`` raises "generator is already running" while a ``__anext__``
    for the same generator is still executing.  The release lives in its own
    ``finally`` so an ``aclose()`` failure can never leak the slot.  Intended to be
    called from the route generator's ``finally`` (every exit path: normal,
    disconnect, duration-cap, error).
    """
    try:
        if pending is not None and not pending.done():
            pending.cancel()
            try:
                await pending
            except (asyncio.CancelledError, StopAsyncIteration):
                pass
        await upstream.aclose()
    finally:
        if semaphore is not None:
            semaphore.release()


# Pre-open exception → HTTP status (spec §A.3; mirrors execute.py:270-277).
_PRE_OPEN_ERROR_STATUS = {
    GraphNotFound: 404,
    InvalidInputs: 400,
    AgentMapNotInitialized: 503,
}


def pre_open_error_response(exc: Exception) -> JSONResponse:
    """Map an F04 prelude exception to its pre-open JSON HTTP error (spec §A.3).

    ``GraphNotFound``→404, ``InvalidInputs``→400, ``AgentMapNotInitialized``→503,
    matching the non-streaming endpoint's mapping (``execute.py:270-277``) so a
    failure to even start the run looks identical on both endpoints.  Returned as a
    ``JSONResponse`` (not a raised ``HTTPException``) so the route can hand it back
    directly from the pre-open path, before the ``text/event-stream`` body opens.
    """
    status_code = _PRE_OPEN_ERROR_STATUS[type(exc)]
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


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


def format_duration_exceeded_terminal(error_code: str) -> str:
    """Frame the duration-cap terminal ``event: failed`` (spec §A.3/§A.4, AC-5).

    Server-enforced failure surfaced through the documented ``error_code``
    (``stream_duration_exceeded``) as a terminal ``failed`` event — not
    ``cancelled`` (DRIFT-03).  ``sequence`` is ``-1`` (server-originated, outside
    F04's sequence space) and ``is_terminal`` is True.
    """
    return format_sse_event(
        "failed",
        {
            "sequence": -1,
            "is_terminal": True,
            "error": error_code,
            "result": {"success": False, "error": error_code},
        },
    )


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


# ---------------------------------------------------------------------------
# Transport-boundary unsupported-mode validation (REQ-F-006 / AC-9 / DEC-3)
# ---------------------------------------------------------------------------

# Documented HTTP status for an out-of-shape streaming request (spec.md §A.6 maps
# unsupported-mode to 400/422; we use 422 — "the body parsed but its *shape* is
# not acceptable for this endpoint" — consistent with FastAPI's own model 422).
UNSUPPORTED_MODE_STATUS = 422


def validate_streaming_request_shape(
    raw_body: Any,
    allowed_fields: Iterable[str],
) -> None:
    """Reject a streaming request whose body carries an unsupported control field.

    The graph-progress streaming endpoint reuses ``ExecuteRequest`` verbatim (C6 —
    one canonical invocation shape), whose supported fields are exactly
    ``allowed_fields`` (``inputs``, ``execution_id``, ``force_create``).  Because
    ``ExecuteRequest`` is a Pydantic v2 model with the project-default
    ``extra='ignore'``, an unknown field (e.g. a batch-only ``batch_mode`` flag or a
    future explicit token-through-graph flag) is **silently dropped** by the model —
    it never raises.  AC-9 / REQ-F-006 require such out-of-shape requests to be
    rejected **explicitly** before the stream opens, with **no silent downgrade**.

    This helper therefore inspects the *raw* request body (the dict produced by
    ``await request.json()``), independently of the parsed model, and raises
    ``HTTPException(422)`` naming the offending parameter(s) if any key falls outside
    ``allowed_fields``.  The caller invokes this in the pre-open gate (after auth,
    before the concurrency acquire) so a rejected shape never opens a
    ``text/event-stream`` body and never holds a concurrency slot.

    Args:
        raw_body: The parsed JSON request body.  Only ``dict`` bodies are inspected;
            a non-dict body (array/scalar) is left to FastAPI's own model binding,
            which already rejects it with 422 before the handler runs.
        allowed_fields: The set of field names the endpoint supports — pass
            ``ExecuteRequest.model_fields`` so there is a single source of truth and
            no duplicated field list.

    Raises:
        HTTPException: status 422 with a documented ``detail`` naming the unsupported
            parameter(s) when ``raw_body`` carries any key outside ``allowed_fields``.
    """
    if not isinstance(raw_body, dict):
        # FastAPI's ExecuteRequest binding owns the non-object rejection.
        return

    allowed = set(allowed_fields)
    unsupported = sorted(key for key in raw_body if key not in allowed)
    if unsupported:
        raise HTTPException(
            status_code=UNSUPPORTED_MODE_STATUS,
            detail=(
                "Unsupported streaming request parameter(s): "
                f"{', '.join(unsupported)}. The streaming endpoint supports only "
                f"{', '.join(sorted(allowed))}; batch-only or non-streaming control "
                "parameters are rejected (no silent downgrade)."
            ),
        )


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


# Terminal ``event_type``s whose ``result`` is normalized through the SAME
# ``_build_execute_response`` the non-streaming endpoint applies, so the SSE wire
# shape == ExecuteResponse (spec §A.3 ``completed``/``failed`` rows; UAT HIGH-2).
# ``suspended`` is deliberately EXCLUDED: spec §A.3's ``suspended`` row requires the
# raw F04 shape (``interrupted: true``, ``thread_id``, ``interrupt_info``,
# ``metadata.checkpoint_available``) — fields ``ExecuteResponse`` does not model —
# so its result is forwarded unchanged.
_EXECUTE_RESPONSE_TERMINALS = frozenset({"completed", "failed"})


def _normalize_terminal_result(
    runtime_result: Dict[str, Any],
    graph_name: str,
) -> Dict[str, Any]:
    """Normalize an F04 terminal ``result`` into the ExecuteResponse wire shape.

    Reuses ``_build_execute_response`` (the ONE canonical path, imported from
    ``execute.py`` — no copy, no circular import since ``execute.py`` imports
    neither ``sse.py`` nor ``stream.py``) so the terminal ``completed``/``failed``
    SSE ``result`` carries the SAME derived ``status``/``message`` and sanitized
    ``outputs`` the non-streaming endpoint returns (spec §A.3; UAT HIGH-2).

    ``execution_id`` is ``None`` here — the streaming route's pre-open priming does
    not thread the client-supplied id into F04's result, exactly as the JSON path
    passes the request's ``execution_id`` (absent → ``None``).
    """
    # Local import keeps the module-import graph acyclic and explicit at the seam.
    from agentmap.deployment.http.api.routes.execute import _build_execute_response

    response = _build_execute_response(graph_name, runtime_result, execution_id=None)
    return response.model_dump()


def project_event_to_sse(event: Any, graph_name: str = "") -> str:
    """Project a WorkflowProgressEvent onto its SSE-framed wire string.

    Maps ``event.event_type`` directly to the SSE ``event:`` name (node_progress,
    completed, failed, suspended) and serialises only the populated fields as the
    compact ``data:`` JSON (spec.md §A.3).  ``to_serializable`` handles dataclasses
    and datetimes so the payload is always JSON-serialisable.

    For ``completed``/``failed`` terminal events the ``result`` is normalized
    through ``_build_execute_response`` so the wire shape matches the non-streaming
    ``ExecuteResponse`` (success/status/outputs/execution_summary/metadata/
    thread_id/error; spec §A.3, UAT HIGH-2).  ``suspended`` keeps its raw F04 shape
    (see ``_EXECUTE_RESPONSE_TERMINALS``); ``graph_name`` is used only to derive the
    ExecuteResponse ``message``.
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
        if event.is_terminal and event.event_type in _EXECUTE_RESPONSE_TERMINALS:
            payload["result"] = _normalize_terminal_result(event.result, graph_name)
        else:
            payload["result"] = to_serializable(event.result)
    if event.error is not None:
        payload["error"] = event.error

    return format_sse_event(event.event_type, payload)
