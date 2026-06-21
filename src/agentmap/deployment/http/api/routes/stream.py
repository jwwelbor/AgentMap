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
  DEC-6  — Config-sized process-wide asyncio.Semaphore for concurrency admission.

Pre-open gate ordering (spec §A.7) is documented on ``stream_workflow``: auth ->
unsupported-mode -> concurrency -> prime upstream -> open.
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

# SSE wire helpers + projection live in sse.py and the concurrency limiter in
# sse_concurrency.py (both split out to keep modules under the 350-line limit,
# spec.md §A.1); re-aliased to the private names this module + the unit tests use.
from agentmap.deployment.http.api.sse import (
    aclose_upstream_and_release as _aclose_upstream_and_release,
)
from agentmap.deployment.http.api.sse import (
    format_duration_exceeded_terminal as _format_duration_exceeded_terminal,
)
from agentmap.deployment.http.api.sse import format_sse_event as _format_sse_event
from agentmap.deployment.http.api.sse import (
    format_sse_heartbeat as _format_sse_heartbeat,
)
from agentmap.deployment.http.api.sse import (
    pre_open_error_response as _pre_open_error_response,
)
from agentmap.deployment.http.api.sse import prime_upstream as _prime_upstream
from agentmap.deployment.http.api.sse import (
    project_event_to_sse as _project_event_to_sse,
)
from agentmap.deployment.http.api.sse import (
    validate_streaming_request_shape as _validate_streaming_request_shape,
)
from agentmap.deployment.http.api.sse_concurrency import (
    try_acquire_stream_slot as _try_acquire_stream_slot,
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
    upstream: AsyncGenerator[Any, None],
    primed_first_event: Optional[Any],
    primed_exhausted: bool,
    graph_name: str,
    request: Request,
    max_stream_duration_seconds: float,
    idle_timeout_seconds: float,
    heartbeat_interval_seconds: float,
    semaphore: Optional["asyncio.Semaphore"] = None,
) -> AsyncGenerator[str, None]:
    """Frame an already-primed run_workflow_stream_async as SSE, with envelope.

    The handler primes the first event *pre-open* (``_prime_upstream``; see its
    docstring for the spec §A.3 / CR BLOCKER-2 rationale), so this generator receives
    the already-built ``upstream`` plus that ``primed_first_event``
    (``primed_exhausted=True`` if the upstream yielded nothing), replays it as the
    first SSE frame, then drains the rest from the same ``upstream`` — so cancellation
    / ``aclose()`` finalization (DEC-5) still acts on the original generator.

    Per-event timed-wait loop (LOW-1 / INT-F05-3): each *subsequent* event is awaited
    under ``asyncio.wait_for`` (the in-flight ``__anext__`` is shielded so an idle wake
    never cancels it), so the loop wakes to (1) check ``request.is_disconnected()`` and
    emit a best-effort ``cancelled`` (DRIFT-02: the hard contract is upstream cancel +
    F04 finalization via aclose(), not the wire event), (2) enforce the monotonic
    duration cap → terminal ``failed`` with ``stream_duration_exceeded`` (AC-5 /
    DRIFT-03: ``failed``, not ``cancelled``), and (3) emit an idle ``:keepalive`` SSE
    *comment* — never a typed event — at ``heartbeat_interval_seconds`` once
    ``idle_timeout_seconds`` elapses (AC-7; the deadline stays authoritative).

    Exactly-one-terminal (UAT HIGH-1 / REQ-F-002 / AC-1 / AC-5): the loop ``return``s
    immediately after yielding any F04 terminal event, so a disconnect or deadline
    lapse in the post-terminal/pre-pull window cannot re-enter the (1)/(2) gates and
    emit a SECOND terminal (``cancelled``/``failed``).

    ``CancelledError``/``GeneratorExit`` are re-raised after cleanup, never swallowed
    (F04-lesson); the ``finally`` delegates upstream finalization + slot release to
    ``_aclose_upstream_and_release`` on every exit path (DEC-5/DEC-6).
    """
    loop = asyncio.get_running_loop()
    start = loop.time()
    deadline = start + max_stream_duration_seconds
    pending: Optional["asyncio.Future[Any]"] = None

    # Replay the pre-open-primed first event before resuming iteration (``None`` once
    # consumed; ``None`` from the start if the upstream yielded nothing).
    seeded_event: Optional[Any] = None if primed_exhausted else primed_first_event

    # Heartbeat bookkeeping (AC-7): idle window is measured from the last event
    # (not stream start); last_heartbeat_time paces the keepalive cadence.
    last_event_time = start
    last_heartbeat_time = start

    try:
        while True:
            # (1) Disconnect gate — checked BEFORE replaying/pulling the next event so
            #     a disconnect stops the upstream, not one more node, and so a client
            #     already gone at response.start never receives the primed event (AC-2).
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
                yield _format_duration_exceeded_terminal(_DURATION_EXCEEDED_ERROR)
                return

            # (3a) Replay the primed first event (no await — already in hand).
            if seeded_event is not None:
                event = seeded_event
                seeded_event = None
                last_event_time = loop.time()
                last_heartbeat_time = last_event_time
                yield _project_event_to_sse(event, graph_name)
                if event.is_terminal:
                    return  # exactly-one-terminal: never loop past an F04 terminal
                continue

            # (3b) Await the next event, bounded so we wake to re-check (1)/(2) and
            #     pace heartbeats.  ``pending`` is shielded so it survives a wake.
            if pending is None:
                pending = asyncio.ensure_future(upstream.__anext__())

            # Wake at the soonest of the deadline, the poll interval, and the next
            # heartbeat tick (clamped to a positive floor when heartbeat_interval=0).
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
            yield _project_event_to_sse(event, graph_name)
            if event.is_terminal:
                return  # exactly-one-terminal: never loop past an F04 terminal

    except asyncio.CancelledError:
        # Task cancellation (e.g. client disconnect surfaced by the ASGI server).
        # Do NOT swallow — re-raise after the finally closes the upstream so F04
        # finalizes the tracker (F04-lesson / REQ-F-003).
        raise
    finally:
        # Finalize the upstream (DEC-5) and release the concurrency slot (DEC-6) on
        # every exit path — see ``_aclose_upstream_and_release``.
        await _aclose_upstream_and_release(pending, upstream, semaphore)


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

    Mirrors POST /execute/{graph_id:path} (execute.py) by appending /stream, reusing
    the same auth decorator, ExecuteRequest body, and graph_id normalization (DEC-4);
    delegates to F04's run_workflow_stream_async.  Pre-open errors (auth 401/403,
    graph-not-found 404, invalid-inputs 400, not-initialized 503, concurrency 503) are
    ordinary JSON HTTP errors — identical shape to the non-streaming endpoint (§A.3) —
    because the stream has not opened yet.

    Pre-open gate ordering (INT-F05-4 / spec §A.7): auth (@requires_auth, before this
    body) → unsupported-mode validation (422) → concurrency admission (semaphore 503)
    → prime the upstream (404/400/503 from F04's prelude) → open the stream.  A failed
    earlier gate never reaches a later one.  Duration cap, disconnect cancel, and idle
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
    # http.sse.* with §A.4 defaults applied.  max_concurrent_streams is the ONE
    # canonical source of the concurrency limit (CR BLOCKER-1; see
    # try_acquire_stream_slot): the config value sizes the pool, int-coerced.
    sse_config = get_app_config_service(request).get_sse_config()
    max_stream_duration_seconds = float(sse_config["max_stream_duration_seconds"])
    idle_timeout_seconds = float(sse_config["idle_timeout_seconds"])
    heartbeat_interval_seconds = float(sse_config["heartbeat_interval_seconds"])
    max_concurrent_streams = int(sse_config["max_concurrent_streams"])

    # --- Concurrency gate (DEC-6 / REQ-F-004 / AC-6) --------------------------
    # Non-blocking pre-open admission sized from config: a held slot on success, or
    # None when the config-sized pool is full → 503 JSON, NO slot consumed, NO body.
    semaphore = await _try_acquire_stream_slot(max_concurrent_streams)
    if semaphore is None:
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

    logger.info("Opening SSE stream for graph: %s", graph_name)

    # Slot is held and MUST be released on every exit path.  On success the
    # generator's finally owns the release; the ``handed_off`` flag + finally below
    # frees it if anything fails (incl. a pre-open prelude error mapped to JSON)
    # BEFORE the StreamingResponse is returned — without a broad except-and-reraise.
    handed_off = False
    try:
        # Build the lazy upstream, then PRIME it one step (spec §A.3 / CR BLOCKER-2;
        # see ``_prime_upstream``) so F04's prelude exceptions map to pre-open JSON.
        upstream = run_workflow_stream_async(
            graph_name=graph_name,
            inputs=request_body.inputs,
            force_create=request_body.force_create,
            config_file=config_file,
        )
        try:
            primed_first_event, primed_exhausted = await _prime_upstream(upstream)
        except (GraphNotFound, InvalidInputs, AgentMapNotInitialized) as exc:
            # Pre-open JSON error (404/400/503) — _pre_open_error_response maps it
            # exactly like the non-streaming endpoint; the stream never opens.
            return _pre_open_error_response(exc)

        response = StreamingResponse(
            _sse_generator(
                upstream,
                primed_first_event,
                primed_exhausted,
                graph_name,
                request,
                max_stream_duration_seconds,
                idle_timeout_seconds,
                heartbeat_interval_seconds,
                semaphore=semaphore,
            ),
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
            semaphore.release()
