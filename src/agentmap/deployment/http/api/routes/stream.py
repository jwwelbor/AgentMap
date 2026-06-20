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
import logging
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from agentmap.deployment.http.api.dependencies import (
    get_app_config_service,
    requires_auth,
)
from agentmap.deployment.http.api.routes.execute import ExecuteRequest

# SSE wire helpers + concurrency limiter live in sse.py so this module stays
# under the 350-line limit (spec.md §A.1).  Re-aliased to the private names the
# rest of this module — and the T-002 unit tests — reference.  _format_sse_heartbeat
# and _stream_semaphore are re-exported here for the T-002 tests and T-005's
# heartbeat/concurrency wiring (noqa F401: re-export, not dead code).
from agentmap.deployment.http.api.sse import format_sse_event as _format_sse_event
from agentmap.deployment.http.api.sse import (  # noqa: F401
    format_sse_heartbeat as _format_sse_heartbeat,
)
from agentmap.deployment.http.api.sse import (  # noqa: F401
    stream_semaphore as _stream_semaphore,
)
from agentmap.deployment.http.api.sse import to_serializable as _to_serializable
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

# Documented duration-cap error code surfaced as a terminal ``event: failed``
# payload when the wall-clock cap is reached (spec.md §A.3 / §A.4, AC-5).
_DURATION_EXCEEDED_ERROR = "stream_duration_exceeded"

# Maximum time the read loop blocks on a single upstream event before waking to
# re-check the disconnect flag and the wall-clock deadline.  This bounds how
# promptly the duration cap and client-disconnect are observed; it is also the
# seam T-005's idle heartbeat composes into (LOW-1 / INT-F05-3): the same wake
# point that re-checks the deadline will emit a ``:keepalive`` comment when idle.
# A timeout here does NOT cancel the in-flight upstream event (it is shielded) —
# the loop simply wakes, re-checks, and resumes waiting on the same event.
_EVENT_POLL_INTERVAL_SECONDS = 1.0


# ---------------------------------------------------------------------------
# Graph identifier normalisation (mirrors execute.py pattern)
# ---------------------------------------------------------------------------


def _normalize_graph_identifier(identifier: str) -> str:
    """Normalize graph identifier to standard :: format."""
    return identifier.replace("%3A%3A", "::").replace("/", "::")


# ---------------------------------------------------------------------------
# SSE event-stream generator
# ---------------------------------------------------------------------------


def _project_event_to_sse(event: Any) -> str:
    """Project a WorkflowProgressEvent onto its SSE-framed wire string.

    Maps the WorkflowProgressEvent.event_type directly to the SSE ``event:``
    name (node_progress, completed, failed, suspended) and serialises the
    populated fields as the compact ``data:`` JSON (spec.md §A.3).

    _to_serializable handles dataclasses and datetime objects so the result
    dict can always be JSON-serialised without further processing.
    """
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

    return _format_sse_event(event.event_type, payload)


async def _sse_generator(
    graph_name: str,
    request_body: ExecuteRequest,
    config_file: Optional[str],
    request: Request,
    max_stream_duration_seconds: float,
) -> AsyncGenerator[str, None]:
    """Drive run_workflow_stream_async and frame output as SSE, with envelope.

    The read loop is structured as per-event timed waits (LOW-1 / INT-F05-3):
    each upstream event is awaited under ``asyncio.wait_for`` bounded by
    ``_EVENT_POLL_INTERVAL_SECONDS``, so the loop wakes periodically to:

      * check ``request.is_disconnected()`` — on client disconnect, stop pulling
        from the upstream and emit a best-effort ``event: cancelled`` (DRIFT-02:
        the hard contract is upstream cancellation + F04 tracker finalization,
        which the ``finally`` aclose() guarantees, NOT the wire event); and
      * enforce the wall-clock duration cap against a monotonic deadline
        (``loop.time()``-based, never wall-clock now()) — on exceed, emit a
        terminal ``event: failed`` with ``error: stream_duration_exceeded``
        (AC-5 / DRIFT-03: ``failed``, not ``cancelled``).

    A poll-interval timeout does NOT cancel the in-flight upstream event — the
    pending ``__anext__`` is shielded so an idle interval (and, in T-005, a
    heartbeat) never tears down the upstream generator.

    Cancellation propagation (client disconnect surfaced as task cancellation,
    or the StreamingResponse generator being closed) is re-raised after cleanup
    — ``CancelledError``/``GeneratorExit`` must NOT be swallowed (F04-lesson).
    On every exit path the ``finally`` block closes the upstream generator via
    ``aclose()`` so F04's existing finalizer runs (DEC-5); F05 adds no third
    finalization call.
    """
    upstream = run_workflow_stream_async(
        graph_name=graph_name,
        inputs=request_body.inputs,
        force_create=request_body.force_create,
        config_file=config_file,
    )

    loop = asyncio.get_running_loop()
    deadline = loop.time() + max_stream_duration_seconds
    pending: Optional["asyncio.Future[Any]"] = None

    try:
        while True:
            # (1) Client-disconnect gate — checked BEFORE pulling the next event
            #     so a disconnect stops the upstream rather than letting one more
            #     node start (no orphaned work — AC-2).
            if await request.is_disconnected():
                logger.info(
                    "SSE stream cancelled: %s reason=client_disconnect", graph_name
                )
                # Best-effort wire event; the socket may already be gone.
                yield _format_sse_event("cancelled", {"reason": "client_disconnect"})
                return

            # (2) Wall-clock duration cap against the monotonic deadline.
            remaining = deadline - loop.time()
            if remaining <= 0:
                logger.warning(
                    "SSE stream terminated: %s reason=%s",
                    graph_name,
                    _DURATION_EXCEEDED_ERROR,
                )
                yield _format_sse_event(
                    "failed",
                    {
                        "sequence": -1,
                        "is_terminal": True,
                        "error": _DURATION_EXCEEDED_ERROR,
                        "result": {
                            "success": False,
                            "error": _DURATION_EXCEEDED_ERROR,
                        },
                    },
                )
                return

            # (3) Await the next upstream event, bounded so we wake to re-check
            #     (1) and (2).  ``pending`` survives a timeout (shielded), so the
            #     in-flight event is never cancelled by an idle wake.
            if pending is None:
                pending = asyncio.ensure_future(upstream.__anext__())

            budget = min(remaining, _EVENT_POLL_INTERVAL_SECONDS)
            try:
                event = await asyncio.wait_for(asyncio.shield(pending), budget)
            except asyncio.TimeoutError:
                # Idle wake: re-loop to re-check disconnect + deadline. The
                # shielded ``pending`` keeps running. (T-005 emits a heartbeat
                # here when the idle window has elapsed.)
                continue
            except StopAsyncIteration:
                # Upstream exhausted — F04 already emitted its terminal event.
                pending = None
                return

            pending = None
            yield _project_event_to_sse(event)

    except asyncio.CancelledError:
        # Task cancellation (e.g. client disconnect surfaced by the ASGI server).
        # Do NOT swallow — re-raise after the finally closes the upstream so F04
        # finalizes the tracker (F04-lesson / REQ-F-003).
        raise
    finally:
        # Close the upstream generator so F04's existing handler finalizes the
        # execution tracker (DEC-5 — F05 adds no third finalize).
        #
        # If an event pull is still in flight (e.g. the duration cap fired while
        # ``__anext__`` was awaiting), it must be cancelled AND awaited to
        # completion first: aclose() raises "generator is already running" if a
        # __anext__ coroutine for the same generator is still executing. Awaiting
        # the cancelled future lets that __anext__ unwind (running the upstream's
        # finally) before we aclose().
        if pending is not None and not pending.done():
            pending.cancel()
            try:
                await pending
            except (asyncio.CancelledError, StopAsyncIteration):
                pass
        await upstream.aclose()


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

    The connection envelope's wall-clock duration cap and client-disconnect
    cancellation are enforced inside the SSE generator (T-004).  Concurrency
    admission (semaphore 503 gate) and the idle heartbeat are T-005.
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

    # Read the connection-envelope values at request time (not import time): the
    # DI container is live here, so get_sse_config() reflects http.sse.* config
    # with the §A.4 defaults applied.
    sse_config = get_app_config_service(request).get_sse_config()
    max_stream_duration_seconds = float(sse_config["max_stream_duration_seconds"])

    logger.info("Opening SSE stream for graph: %s", graph_name)

    # Pre-open exception mapping — identical to execute.py:270-277.
    # Errors raised here become JSON HTTP errors, not SSE events, because the
    # StreamingResponse has not been created yet.
    try:
        # Build the SSE generator (lazy — no F04 calls until iteration starts).
        gen = _sse_generator(
            graph_name,
            request_body,
            config_file,
            request,
            max_stream_duration_seconds,
        )
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
