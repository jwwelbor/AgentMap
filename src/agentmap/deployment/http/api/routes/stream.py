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

Pre-open gate ordering (spec §A.7): auth -> unsupported-mode (422) -> concurrency
(503) -> open.  In-stream: duration cap, disconnect cancel, idle heartbeat.
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from agentmap.deployment.http.api.dependencies import (
    get_app_config_service,
    requires_auth,
)
from agentmap.deployment.http.api.routes.execute import ExecuteRequest

# SSE wire helpers + projection + semaphore live in sse.py so this module stays
# under the 350-line limit (spec.md §A.1), re-aliased to the private names this
# module and the unit tests reference.  _to_serializable is a test-only re-export
# (TestSSEModuleScaffold) — the projection that used it now lives in sse.py.
from agentmap.deployment.http.api.sse import format_sse_event as _format_sse_event
from agentmap.deployment.http.api.sse import (
    format_sse_heartbeat as _format_sse_heartbeat,
)
from agentmap.deployment.http.api.sse import (
    project_event_to_sse as _project_event_to_sse,
)
from agentmap.deployment.http.api.sse import stream_semaphore as _stream_semaphore
from agentmap.deployment.http.api.sse import (  # noqa: F401
    to_serializable as _to_serializable,
)
from agentmap.deployment.http.api.sse import (
    validate_streaming_request_shape as _validate_streaming_request_shape,
)
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

# Duration-cap error code → terminal ``event: failed`` payload (spec §A.3/§A.4, AC-5).
_DURATION_EXCEEDED_ERROR = "stream_duration_exceeded"

# Max time the loop blocks on one upstream event before waking to re-check the
# disconnect flag, deadline, and heartbeat tick (the in-flight event is shielded).
_EVENT_POLL_INTERVAL_SECONDS = 1.0

# Floor for the per-iteration wait budget (heartbeat_interval may be 0 in tests);
# clamps ``asyncio.wait_for`` so it cannot busy-spin.
_MIN_WAIT_BUDGET_SECONDS = 0.01


def _normalize_graph_identifier(identifier: str) -> str:
    """Normalize graph identifier to standard :: format (mirrors execute.py)."""
    return identifier.replace("%3A%3A", "::").replace("/", "::")


async def _sse_generator(
    graph_name: str,
    request_body: ExecuteRequest,
    config_file: Optional[str],
    request: Request,
    max_stream_duration_seconds: float,
    idle_timeout_seconds: float,
    heartbeat_interval_seconds: float,
    semaphore: Optional["asyncio.Semaphore"] = None,
) -> AsyncGenerator[str, None]:
    """Drive run_workflow_stream_async and frame output as SSE, with envelope.

    Per-event timed-wait loop (LOW-1 / INT-F05-3): each upstream event is awaited
    under ``asyncio.wait_for`` (the in-flight ``__anext__`` is shielded so an idle
    wake never cancels it), so the loop wakes periodically to (1) check
    ``request.is_disconnected()`` and emit a best-effort ``cancelled`` (DRIFT-02:
    the hard contract is upstream cancel + F04 finalization via aclose(), not the
    wire event), (2) enforce the monotonic duration cap → terminal ``failed`` with
    ``stream_duration_exceeded`` (AC-5 / DRIFT-03: ``failed``, not ``cancelled``),
    and (3) emit an idle ``:keepalive`` SSE *comment* — never a typed event — at the
    ``heartbeat_interval_seconds`` cadence once ``idle_timeout_seconds`` elapses
    (AC-7); the duration deadline stays authoritative (heartbeats never extend it).

    ``CancelledError``/``GeneratorExit`` are re-raised after cleanup, never swallowed
    (F04-lesson).  The ``finally`` closes the upstream via ``aclose()`` so F04's
    finalizer runs (DEC-5; no third finalize) and releases the ``semaphore`` slot
    exactly once on every exit path (normal, disconnect, duration-cap, error) (DEC-6).
    """
    upstream = run_workflow_stream_async(
        graph_name=graph_name,
        inputs=request_body.inputs,
        force_create=request_body.force_create,
        config_file=config_file,
    )

    loop = asyncio.get_running_loop()
    start = loop.time()
    deadline = start + max_stream_duration_seconds
    pending: Optional["asyncio.Future[Any]"] = None

    # Heartbeat bookkeeping (AC-7): idle window is measured from the last event
    # (not stream start); last_heartbeat_time paces the keepalive cadence.
    last_event_time = start
    last_heartbeat_time = start

    try:
        while True:
            # (1) Disconnect gate — checked BEFORE pulling the next event so a
            #     disconnect stops the upstream, not one more node (no orphan, AC-2).
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

            # (3) Await the next event, bounded so we wake to re-check (1)/(2) and
            #     pace heartbeats.  ``pending`` is shielded so it survives a wake.
            if pending is None:
                pending = asyncio.ensure_future(upstream.__anext__())

            # Wake at the soonest of: the deadline, the poll interval, and the
            # next heartbeat tick (clamped to a positive floor for forward
            # progress when heartbeat_interval is 0).
            budget = min(remaining, _EVENT_POLL_INTERVAL_SECONDS)
            if heartbeat_interval_seconds > 0:
                budget = min(budget, heartbeat_interval_seconds)
            budget = max(budget, _MIN_WAIT_BUDGET_SECONDS)

            try:
                event = await asyncio.wait_for(asyncio.shield(pending), budget)
            except asyncio.TimeoutError:
                # Idle wake: emit a heartbeat comment if the idle window has
                # elapsed and the cadence is due, then re-loop (pending survives).
                now = loop.time()
                idle_elapsed = now - last_event_time
                since_last_heartbeat = now - last_heartbeat_time
                if (
                    idle_elapsed >= idle_timeout_seconds
                    and since_last_heartbeat >= heartbeat_interval_seconds
                ):
                    last_heartbeat_time = now
                    # AC-7: keepalive is an SSE *comment*, never a typed event.
                    yield _format_sse_heartbeat()
                continue
            except StopAsyncIteration:
                # Upstream exhausted — F04 already emitted its terminal event.
                pending = None
                return

            pending = None
            # Reset the idle/heartbeat window: a real event just flowed.
            last_event_time = loop.time()
            last_heartbeat_time = last_event_time
            yield _project_event_to_sse(event)

    except asyncio.CancelledError:
        # Task cancellation (e.g. client disconnect surfaced by the ASGI server).
        # Do NOT swallow — re-raise after the finally closes the upstream so F04
        # finalizes the tracker (F04-lesson / REQ-F-003).
        raise
    finally:
        # Close the upstream so F04 finalizes the tracker (DEC-5 — no third
        # finalize).  An in-flight ``__anext__`` (e.g. cap fired mid-await) must be
        # cancelled AND awaited first: aclose() raises "generator is already
        # running" while a __anext__ for the same generator is still executing.
        try:
            if pending is not None and not pending.done():
                pending.cancel()
                try:
                    await pending
                except (asyncio.CancelledError, StopAsyncIteration):
                    pass
            await upstream.aclose()
        finally:
            # Release the pre-open concurrency slot (DEC-6) exactly once, in its
            # own finally so an aclose() failure can never leak it.
            if semaphore is not None:
                semaphore.release()


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------


@router.post("/execute/{graph_id:path}/stream")
@requires_auth("execute")
async def stream_workflow(
    graph_id: str,
    request_body: ExecuteRequest,
    request: Request,
) -> Response:
    """Run a workflow over the streaming path; return a text/event-stream response.

    Mirrors POST /execute/{graph_id:path} (execute.py) by appending /stream,
    reusing the same auth decorator, ExecuteRequest body, and graph_id
    normalization (DEC-4); delegates to F04's run_workflow_stream_async.  Pre-open
    errors (auth 401/403, graph-not-found 404, invalid-inputs 400, not-initialized
    503, concurrency 503) are ordinary JSON HTTP errors — identical shape to the
    non-streaming endpoint (§A.3) — because the stream has not opened yet.

    Pre-open gate ordering (INT-F05-4 / spec §A.7): auth (the @requires_auth
    decorator, before this body) → unsupported-mode validation (422 on an
    out-of-shape body, REQ-F-006) → concurrency admission (semaphore 503) → open the
    stream.  A failed earlier gate never reaches a later one (a 401 never validates
    the shape; a rejected shape never attempts the acquire, so it never holds a
    slot; a 503 never opens a body).  The duration cap, disconnect cancel, and idle
    heartbeat live in the generator.
    """
    config_file = getattr(request.app.state, "config_file", None)
    graph_name = _normalize_graph_identifier(graph_id)

    # Validate graph identifier format (mirrors execute.py pre-flight check).
    if not graph_name or graph_name.count("::") > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid graph identifier format: {graph_name}",
        )

    # --- Unsupported-mode validation (T-006 / REQ-F-006 / AC-9 / DEC-3) --------
    # Reject out-of-shape requests (422) BEFORE the concurrency acquire, so a
    # rejected shape never holds a slot nor opens a body (spec §A.7).  Validate the
    # RAW body, NOT request_body: ExecuteRequest has extra='ignore' so an unknown
    # field (batch_mode) is silently dropped — relying on it would be a silent
    # downgrade (MED-1).  model_fields is the single source of allowed fields (AC-10).
    try:
        _validate_streaming_request_shape(
            await request.json(), ExecuteRequest.model_fields
        )
    except HTTPException:
        # Operational-only log (AC-11: no payload), then re-raise for the 422 JSON.
        logger.info("SSE request rejected: unsupported request shape")
        raise

    # Envelope read at request time (live DI), so get_sse_config() reflects
    # http.sse.* with §A.4 defaults applied.
    sse_config = get_app_config_service(request).get_sse_config()
    max_stream_duration_seconds = float(sse_config["max_stream_duration_seconds"])
    idle_timeout_seconds = float(sse_config["idle_timeout_seconds"])
    heartbeat_interval_seconds = float(sse_config["heartbeat_interval_seconds"])

    # --- Concurrency gate (DEC-6 / REQ-F-004 / AC-6) --------------------------
    # Non-blocking pre-open admission: a full pool → 503 JSON, NO slot consumed, NO
    # body.  Guard with locked() first (a blocking acquire would queue behind a held
    # slot — forbidden); in asyncio acquire() never suspends when a slot is free, so
    # there is no race between the locked() check and the acquire().
    if _stream_semaphore.locked():
        logger.warning("SSE stream rejected: max_concurrent_streams exceeded")
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Maximum concurrent streams reached; retry later "
                    "(max_concurrent_streams exceeded)"
                )
            },
        )
    await _stream_semaphore.acquire()

    logger.info("Opening SSE stream for graph: %s", graph_name)

    # Slot is now held and MUST be released on every exit path.  On success the
    # generator's finally owns the release; the ``handed_off`` flag + finally below
    # frees it if anything fails BEFORE the StreamingResponse is returned (so the
    # generator's finally would never run) — without a broad except-and-reraise.
    handed_off = False
    try:
        # Pre-open exception mapping — identical to execute.py:270-277; surfaces as
        # JSON HTTP errors (not SSE events) since the StreamingResponse isn't created.
        try:
            # Build the generator (lazy — no F04 calls until iteration starts).
            gen = _sse_generator(
                graph_name,
                request_body,
                config_file,
                request,
                max_stream_duration_seconds,
                idle_timeout_seconds,
                heartbeat_interval_seconds,
                semaphore=_stream_semaphore,
            )
        except GraphNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except InvalidInputs as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except AgentMapNotInitialized as exc:
            raise HTTPException(status_code=503, detail=str(exc))

        response = StreamingResponse(
            gen,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        # Ownership of the slot now belongs to the generator's finally.
        handed_off = True
        return response
    finally:
        if not handed_off:
            _stream_semaphore.release()
