"""Integration tests for the SSE streaming execute endpoint.

Tests the POST /execute/{graph_id:path}/stream handler added in T-E06-F05-003.
Uses an async HTTP client (httpx.AsyncClient + ASGITransport) so incremental
SSE delivery is observable, per the test-plan caller-path contracts.

Test classes:
  TestSSEStreamHappyPath           — TC-F05-001 (normal stream: 200 + events + terminal)
  TestSSEStreamTerminalStates      — TC-F05-003 (failed), TC-F05-004 (suspended)
  TestSSEStreamRegressionNonStreaming — TC-F05-010 (existing endpoint unchanged)

T-003 scope: happy path, terminal events, router registration.
TC-F05-002 (disconnect cancel), TC-F05-005 (duration cap), TC-F05-006/007
(concurrency/heartbeat), TC-F05-008 (auth), TC-F05-009 (unsupported mode), and
TC-F05-012 (incremental delivery) belong to T-004/T-005.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI

from agentmap.deployment.http.api.routes.execute import router as execution_router
from agentmap.deployment.http.api.routes.stream import router as stream_router
from agentmap.deployment.http.api.sse_concurrency import (
    get_stream_semaphore,
    reset_stream_semaphore,
)
from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)
from agentmap.models.execution.progress_event import WorkflowProgressEvent
from agentmap.services.auth_service import AuthContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class SseEvent:
    """Parsed SSE event (event name + JSON-decoded data dict)."""

    event_name: str
    data: Dict[str, Any]


def parse_sse_bytes(raw_bytes: bytes) -> List[SseEvent]:
    """Parse raw SSE bytes into a list of SseEvent objects.

    Handles the framing:
        event: <name>\\n
        data: <json>\\n
        \\n

    Comment lines (starting with ':') are ignored here.  Returns only
    typed events (those with an 'event:' field).
    """
    events: List[SseEvent] = []
    current_event_name: Optional[str] = None
    current_data: Optional[str] = None

    for raw_line in raw_bytes.split(b"\n"):
        line = raw_line.decode("utf-8", errors="replace").rstrip("\r")

        if line.startswith("event:"):
            current_event_name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current_data = line[len("data:") :].strip()
        elif line == "":
            # Blank line — emit the accumulated event if we have both fields
            if current_event_name is not None and current_data is not None:
                try:
                    data_dict = json.loads(current_data)
                except json.JSONDecodeError:
                    data_dict = {"_raw": current_data}
                events.append(SseEvent(event_name=current_event_name, data=data_dict))
            # Reset for next event
            current_event_name = None
            current_data = None

    return events


async def _make_fake_stream(*events: WorkflowProgressEvent):
    """Async generator factory — yields scripted WorkflowProgressEvents in order."""
    for event in events:
        yield event


# Default SSE envelope (matches AppConfigService.get_sse_config() §A.4 defaults).
# Individual tests override entries (e.g. a tiny max_stream_duration_seconds for
# the duration-cap BVA) via the sse_config kwarg on _make_test_app.
_DEFAULT_SSE_CONFIG: Dict[str, Any] = {
    "max_stream_duration_seconds": 1800,
    "idle_timeout_seconds": 30,
    "heartbeat_interval_seconds": 15,
    "max_concurrent_streams": 100,
}


def _make_cancellable_stream(
    events: List[WorkflowProgressEvent],
    *,
    gate_after: int,
    n2_gate: "asyncio.Event",
    flags: Dict[str, Any],
):
    """Gated, cancellation-recording fake for ``run_workflow_stream_async``.

    Yields the first ``gate_after`` events, then sets ``flags['n2_entered']`` and
    blocks on ``n2_gate`` (this is where the "next node" would run).  When the
    consumer cancels (client disconnect or duration cap → route calls
    ``aclose()`` / the StreamingResponse generator is closed → GeneratorExit /
    CancelledError propagates into this generator), the ``finally`` block records
    ``flags['cancellation_received'] = True``.

    This mirrors the F04 TC-F04-006 cancellation gate (``test_graph_progress_
    streaming.py``) at the HTTP transport layer: the hard contract asserted is the
    upstream generator's ``finally`` ran (proxy for F04's tracker finalization on
    GeneratorExit) and the next node was never entered (no orphaned work) —
    DRIFT-02.
    """

    async def _gen():
        try:
            for index, event in enumerate(events):
                yield event
                flags["last_yielded_seq"] = event.sequence
                if index + 1 == gate_after:
                    # Reached the gate point: the "next node" begins here.
                    flags["n2_entered"] = True
                    await n2_gate.wait()
        finally:
            # Runs on GeneratorExit / CancelledError when the consumer cancels.
            flags["cancellation_received"] = True

    return _gen()


def _make_blocking_stream(
    first_events: List[WorkflowProgressEvent],
    *,
    block_gate: "asyncio.Event",
    flags: Dict[str, Any],
):
    """Fake that yields ``first_events`` then blocks forever on ``block_gate``.

    Used for the duration-cap BVA (TC-F05-005 sub-case A): the upstream never
    completes on its own, so the only thing that can terminate the stream is the
    route's wall-clock cap firing.  Records ``cancellation_received`` in
    ``finally`` so the test can assert the upstream was cancelled when the cap
    fires (the route called ``aclose()``).
    """

    async def _gen():
        try:
            for event in first_events:
                yield event
            await block_gate.wait()  # never set → upstream cannot self-terminate
        finally:
            flags["cancellation_received"] = True

    return _gen()


def _make_test_app(
    auth_enabled: bool = False,
    sse_config: Optional[Dict[str, Any]] = None,
    auth_context: Optional[Any] = None,
    public_endpoints: Optional[List[str]] = None,
) -> FastAPI:
    """Create a minimal FastAPI app with both execute and stream routers.

    Auth is disabled by default so tests can focus on the streaming contract.
    The mock auth service is attached via app.state.container.

    The container's ``app_config_service().get_sse_config()`` returns the §A.4
    envelope defaults merged with any ``sse_config`` override, so the route can
    read ``max_stream_duration_seconds`` (duration cap) at request time.

    stream_router must be registered before execution_router: the execute router
    has a greedy {graph_id:path} parameter that would otherwise match
    POST /execute/{graph_id}/stream before the stream router can.

    Auth wiring (TC-F05-008): ``requires_auth("execute")`` runs against the REAL
    decorator (never mocked — DRIFT-05).  It calls ``auth_service``'s
    ``is_authentication_enabled()``, ``get_public_endpoints()`` and one of the
    ``validate_*`` token methods.  When ``auth_enabled`` is True the test injects
    the ``auth_context`` that token validation should return (so the decorator's
    real 401/403 logic exercises), and ``public_endpoints`` (default empty so the
    stream path is NOT public — a no-token request is a genuine 401).
    """
    app = FastAPI()
    app.include_router(stream_router)
    app.include_router(execution_router)

    merged_sse = dict(_DEFAULT_SSE_CONFIG)
    if sse_config:
        merged_sse.update(sse_config)

    mock_container = MagicMock()
    mock_auth_service = MagicMock()
    mock_auth_service.is_authentication_enabled.return_value = auth_enabled
    # get_public_endpoints() must return a real list — the decorator iterates it.
    mock_auth_service.get_public_endpoints.return_value = public_endpoints or []
    # All token-validation paths return the injected auth_context (or an
    # unauthenticated context if none supplied → real 401 from the decorator).
    if auth_context is not None:
        mock_auth_service.validate_api_key.return_value = auth_context
        mock_auth_service.validate_jwt.return_value = auth_context
        mock_auth_service.validate_supabase_token.return_value = auth_context
    mock_container.auth_service.return_value = mock_auth_service
    mock_container.app_config_service.return_value.get_sse_config.return_value = (
        merged_sse
    )
    app.state.container = mock_container

    return app


async def _collect_sse_response(
    app: FastAPI,
    path: str,
    body: Optional[Dict[str, Any]] = None,
) -> tuple[int, Dict[str, str], bytes]:
    """Drive a POST request to *path* on *app* and collect the full SSE body.

    Returns (status_code, headers_dict, raw_body_bytes).
    Uses httpx.AsyncClient with ASGITransport.  NOTE: httpx's ASGITransport runs
    the ASGI app to completion and buffers the body, so this helper is suitable
    only for streams that terminate on their own (happy path, terminal states,
    and the duration-cap path which self-terminates when the cap fires).  Tests
    that must observe a chunk mid-stream or inject a client disconnect use
    ``SseAsgiDriver`` instead, which drives the ASGI app directly.
    """
    if body is None:
        body = {"inputs": {}}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(path, json=body)
        return response.status_code, dict(response.headers), response.content


class SseAsgiDriver:
    """Drive a FastAPI app's SSE route directly over ASGI for streaming control.

    httpx's ``ASGITransport`` buffers the whole response (it runs the app to
    completion before returning), so it cannot observe an event mid-stream or
    abort a connection between events.  This driver speaks the ASGI protocol
    directly against the real app: it sends the request body, then captures each
    ``http.response.body`` message as the route emits it, and can inject an
    ``http.disconnect`` at a chosen point.  The route handler, StreamingResponse
    lifecycle, SSE framing, and disconnect→cancel chain all execute for real;
    only ``run_workflow_stream_async`` is mocked (the allowed seam).

    ``on_body`` is invoked with each non-empty body chunk; returning ``True``
    requests a client disconnect (the next ``receive()`` yields
    ``http.disconnect`` synchronously, so ``Request.is_disconnected()`` — which
    does a non-blocking receive — observes it).
    """

    def __init__(
        self,
        app: FastAPI,
        path: str,
        *,
        body: Optional[Dict[str, Any]] = None,
        spec_version: str = "2.4",
    ) -> None:
        self._app = app
        self._path = path
        self._body_bytes = json.dumps(body if body is not None else {"inputs": {}})
        self._body_bytes_enc = self._body_bytes.encode("utf-8")
        self._spec_version = spec_version
        self.status_code: Optional[int] = None
        self.headers: Dict[str, str] = {}
        self.body_chunks: List[bytes] = []
        self.disconnect_on_start = False
        self._disconnect = False
        self._request_sent = False

    @property
    def raw_body(self) -> bytes:
        return b"".join(self.body_chunks)

    def _scope(self) -> Dict[str, Any]:
        return {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": self._spec_version},
            "http_version": "1.1",
            "method": "POST",
            "path": self._path,
            "raw_path": self._path.encode("utf-8"),
            "query_string": b"",
            "root_path": "",
            "scheme": "http",
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(self._body_bytes_enc)).encode()),
            ],
            "server": ("testserver", 80),
            "client": ("testclient", 12345),
        }

    async def run(self, on_body) -> None:
        """Run the request to completion (or disconnect), invoking on_body.

        on_body(chunk: bytes) -> bool: return True to trigger a client
        disconnect after this chunk.
        """

        async def receive():
            if not self._request_sent:
                self._request_sent = True
                return {
                    "type": "http.request",
                    "body": self._body_bytes_enc,
                    "more_body": False,
                }
            if self._disconnect:
                # Synchronous return: Request.is_disconnected() uses an
                # immediately-cancelled scope around receive(), so the message
                # must be ready without awaiting to be observed.
                return {"type": "http.disconnect"}
            # Connection stays open until the test triggers a disconnect or the
            # route finishes on its own.
            await asyncio.sleep(3600)

        async def send(message):
            mtype = message["type"]
            if mtype == "http.response.start":
                self.status_code = message["status"]
                self.headers = {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in message.get("headers", [])
                }
                if self.disconnect_on_start:
                    self._disconnect = True
            elif mtype == "http.response.body":
                chunk = message.get("body", b"")
                if chunk:
                    self.body_chunks.append(chunk)
                    if on_body(chunk):
                        self._disconnect = True

        await self._app(self._scope(), receive, send)


# ---------------------------------------------------------------------------
# TC-F05-001 — Normal stream: 200, node_progress events, completed terminal
# ---------------------------------------------------------------------------


class TestSSEStreamHappyPath(IsolatedAsyncioTestCase):
    """TC-F05-001: authorized client + 2-node fake workflow → 3 events + completed."""

    def _make_events(self):
        node1 = WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
            node_name="n1",
            state_delta={"output": "result-n1"},
            node_duration=0.1,
        )
        node2 = WorkflowProgressEvent(
            event_type="node_progress",
            sequence=1,
            is_terminal=False,
            node_name="n2",
            state_delta={"output": "result-n2"},
            node_duration=0.2,
        )
        terminal = WorkflowProgressEvent(
            event_type="completed",
            sequence=2,
            is_terminal=True,
            result={
                "success": True,
                "outputs": {"n1": "result-n1", "n2": "result-n2"},
                "execution_summary": {"status": "completed"},
                "metadata": {"graph_name": "test-workflow"},
            },
        )
        return node1, node2, terminal

    async def test_happy_path_returns_200_and_text_event_stream(self):
        """HTTP status must be 200 with Content-Type: text/event-stream (AC-1)."""
        node1, node2, terminal = self._make_events()
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, node2, terminal),
        ):
            status, headers, _ = await _collect_sse_response(
                app, "/execute/test-workflow/stream"
            )

        self.assertEqual(status, 200)
        self.assertIn("text/event-stream", headers.get("content-type", ""))

    async def test_happy_path_sse_response_headers(self):
        """Cache-Control and X-Accel-Buffering headers must be set (spec §A.3)."""
        node1, node2, terminal = self._make_events()
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, node2, terminal),
        ):
            _, headers, _ = await _collect_sse_response(
                app, "/execute/test-workflow/stream"
            )

        self.assertEqual(headers.get("cache-control"), "no-cache")
        self.assertEqual(headers.get("x-accel-buffering"), "no")

    async def test_happy_path_exactly_three_events(self):
        """Fake 2-node workflow must produce exactly 3 SSE events (AC-1)."""
        node1, node2, terminal = self._make_events()
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, node2, terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/test-workflow/stream"
            )

        events = parse_sse_bytes(body)
        self.assertEqual(len(events), 3, f"Expected 3 events, got: {events}")

    async def test_happy_path_node_progress_event_names(self):
        """First two events must have event_name == 'node_progress' (AC-1)."""
        node1, node2, terminal = self._make_events()
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, node2, terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/test-workflow/stream"
            )

        events = parse_sse_bytes(body)
        self.assertEqual(events[0].event_name, "node_progress")
        self.assertEqual(events[1].event_name, "node_progress")

    async def test_happy_path_terminal_event_is_completed(self):
        """Last event must have event_name == 'completed' and is_terminal == true (AC-1)."""
        node1, node2, terminal = self._make_events()
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, node2, terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/test-workflow/stream"
            )

        events = parse_sse_bytes(body)
        terminal_event = events[-1]
        self.assertEqual(terminal_event.event_name, "completed")
        self.assertTrue(terminal_event.data.get("is_terminal"))

    async def test_happy_path_strictly_increasing_sequence(self):
        """Sequence numbers in node_progress events must be strictly increasing (AC-1)."""
        node1, node2, terminal = self._make_events()
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, node2, terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/test-workflow/stream"
            )

        events = parse_sse_bytes(body)
        sequences = [e.data["sequence"] for e in events]
        for i in range(len(sequences) - 1):
            self.assertLess(sequences[i], sequences[i + 1])

    async def test_happy_path_terminal_result_fields(self):
        """Completed terminal data.result must carry success/outputs/metadata (AC-1)."""
        node1, node2, terminal = self._make_events()
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, node2, terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/test-workflow/stream"
            )

        events = parse_sse_bytes(body)
        terminal_data = events[-1].data
        result = terminal_data.get("result", {})
        self.assertTrue(result.get("success"))
        self.assertIsInstance(result.get("outputs"), dict)
        self.assertEqual(result.get("metadata", {}).get("graph_name"), "test-workflow")

    async def test_happy_path_exactly_one_terminal_event(self):
        """Exactly one event must have is_terminal == true (AC-1)."""
        node1, node2, terminal = self._make_events()
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, node2, terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/test-workflow/stream"
            )

        events = parse_sse_bytes(body)
        terminals = [e for e in events if e.data.get("is_terminal")]
        self.assertEqual(len(terminals), 1)

    async def test_happy_path_node_progress_events_not_terminal(self):
        """No node_progress event must have is_terminal == true (counter-factual)."""
        node1, node2, terminal = self._make_events()
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, node2, terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/test-workflow/stream"
            )

        events = parse_sse_bytes(body)
        for event in events:
            if event.event_name == "node_progress":
                self.assertFalse(
                    event.data.get("is_terminal"),
                    f"node_progress event must not be terminal: {event}",
                )

    async def test_happy_path_caller_shape_graph_name_normalization(self):
        """run_workflow_stream_async must be called with normalized graph_name (INT-F05-1)."""
        node1, _, terminal = self._make_events()
        app = _make_test_app()

        captured_kwargs: dict = {}

        async def fake_stream(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield node1
            yield terminal

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=fake_stream,
        ):
            await _collect_sse_response(
                app,
                "/execute/test_workflow/TestGraph/stream",
                body={"inputs": {"k": "v"}, "force_create": True},
            )

        # Path separator / must be normalized to ::
        self.assertEqual(captured_kwargs.get("graph_name"), "test_workflow::TestGraph")
        self.assertEqual(captured_kwargs.get("inputs"), {"k": "v"})
        self.assertTrue(captured_kwargs.get("force_create"))


# ---------------------------------------------------------------------------
# TC-F05-003 — Failed terminal event
# TC-F05-004 — Suspended terminal event
# ---------------------------------------------------------------------------


class TestSSEStreamTerminalStates(IsolatedAsyncioTestCase):
    """TC-F05-003 sub-cases A/B/C (failed) and TC-F05-004 (suspended)."""

    # --- TC-F05-003-A: fail before any node ---

    async def test_failed_terminal_before_any_node(self):
        """Fail before first node: single event: failed with non-empty error (AC-3 sub-A)."""
        terminal = WorkflowProgressEvent(
            event_type="failed",
            sequence=0,
            is_terminal=True,
            error="immediate failure",
            result={"success": False, "error": "immediate failure"},
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            status, _, body = await _collect_sse_response(
                app, "/execute/failing-workflow/stream"
            )

        self.assertEqual(status, 200)
        events = parse_sse_bytes(body)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_name, "failed")
        self.assertTrue(events[0].data.get("is_terminal"))
        self.assertIsNotNone(events[0].data.get("error"))
        self.assertNotEqual(events[0].data.get("error"), "")

    # --- TC-F05-003-B: fail after first node ---

    async def test_failed_terminal_after_first_node(self):
        """Fail after n1: 2 events, last is event: failed (AC-3 sub-B)."""
        node1 = WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
            node_name="n1",
            state_delta={"x": "y"},
            node_duration=0.05,
        )
        terminal = WorkflowProgressEvent(
            event_type="failed",
            sequence=1,
            is_terminal=True,
            error="Node n2 raised: RuntimeError",
            result={"success": False, "error": "Node n2 raised: RuntimeError"},
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/failing-workflow/stream"
            )

        events = parse_sse_bytes(body)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].event_name, "node_progress")
        self.assertEqual(events[1].event_name, "failed")
        self.assertFalse(events[0].data.get("is_terminal"))
        self.assertTrue(events[1].data.get("is_terminal"))
        self.assertNotEqual(events[1].data.get("error"), "")

    # --- TC-F05-003-C: fail at last node (3-node workflow, fail at n3) ---

    async def test_failed_terminal_at_last_node(self):
        """Fail at n3 (last): 3 events, last is event: failed (AC-3 sub-C)."""
        n1 = WorkflowProgressEvent(
            event_type="node_progress", sequence=0, is_terminal=False, node_name="n1"
        )
        n2 = WorkflowProgressEvent(
            event_type="node_progress", sequence=1, is_terminal=False, node_name="n2"
        )
        terminal = WorkflowProgressEvent(
            event_type="failed",
            sequence=2,
            is_terminal=True,
            error="n3 error",
            result={"success": False, "error": "n3 error"},
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(n1, n2, terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/failing-workflow/stream"
            )

        events = parse_sse_bytes(body)
        self.assertEqual(len(events), 3)
        progress_events = [e for e in events if e.event_name == "node_progress"]
        terminal_events = [e for e in events if e.event_name == "failed"]
        self.assertEqual(len(progress_events), 2)
        self.assertEqual(len(terminal_events), 1)
        # Terminal must be last
        self.assertEqual(events[-1].event_name, "failed")

    # --- TC-F05-003: general invariants ---

    async def test_failed_event_name_is_exactly_failed_not_error(self):
        """event_type 'failed' must produce wire event 'event: failed', NOT 'event: error'.

        Counter-factual: a buggy impl mapping 'failed' to 'error' would fail this.
        """
        terminal = WorkflowProgressEvent(
            event_type="failed",
            sequence=0,
            is_terminal=True,
            error="test failure",
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            _, _, body = await _collect_sse_response(app, "/execute/any/stream")

        events = parse_sse_bytes(body)
        self.assertEqual(
            events[-1].event_name, "failed", "Wire event name must be 'failed'"
        )

    async def test_failed_error_field_is_non_empty(self):
        """data.error in the failed terminal must not be null or empty string."""
        terminal = WorkflowProgressEvent(
            event_type="failed",
            sequence=0,
            is_terminal=True,
            error="non-empty error",
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            _, _, body = await _collect_sse_response(app, "/execute/any/stream")

        events = parse_sse_bytes(body)
        last = events[-1]
        error_val = last.data.get("error")
        self.assertIsNotNone(error_val, "data.error must not be null")
        self.assertNotEqual(error_val, "", "data.error must not be empty string")

    # --- TC-F05-004: suspended ---

    async def test_suspended_terminal_event_name_is_suspended(self):
        """event_type 'suspended' must produce wire event 'event: suspended' (AC-4)."""
        terminal = WorkflowProgressEvent(
            event_type="suspended",
            sequence=2,
            is_terminal=True,
            result={
                "success": False,
                "interrupted": True,
                "thread_id": "thread-abc-123",
                "interrupt_info": {"type": "human_input", "node_name": "n1"},
                "metadata": {"checkpoint_available": True},
            },
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            status, _, body = await _collect_sse_response(
                app, "/execute/interruptible-workflow/stream"
            )

        self.assertEqual(status, 200)
        events = parse_sse_bytes(body)
        self.assertEqual(events[-1].event_name, "suspended")

    async def test_suspended_result_has_thread_id(self):
        """data.result.thread_id must be present and non-empty (AC-4)."""
        terminal = WorkflowProgressEvent(
            event_type="suspended",
            sequence=2,
            is_terminal=True,
            result={
                "success": False,
                "interrupted": True,
                "thread_id": "thread-abc-123",
                "interrupt_info": {"type": "human_input", "node_name": "n1"},
                "metadata": {"checkpoint_available": True},
            },
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/interruptible-workflow/stream"
            )

        events = parse_sse_bytes(body)
        result = events[-1].data.get("result", {})
        self.assertEqual(result.get("thread_id"), "thread-abc-123")

    async def test_suspended_result_has_interrupt_info(self):
        """data.result.interrupt_info must be present as a dict (AC-4).

        Counter-factual: a buggy impl that drops interrupt_info would fail assertIn.
        """
        terminal = WorkflowProgressEvent(
            event_type="suspended",
            sequence=2,
            is_terminal=True,
            result={
                "success": False,
                "interrupted": True,
                "thread_id": "thread-abc-123",
                "interrupt_info": {"type": "human_input", "node_name": "n1"},
                "metadata": {"checkpoint_available": True},
            },
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/interruptible-workflow/stream"
            )

        events = parse_sse_bytes(body)
        result = events[-1].data.get("result", {})
        self.assertIn("interrupt_info", result)
        self.assertIsInstance(result["interrupt_info"], dict)

    async def test_suspended_result_has_metadata_checkpoint_available(self):
        """data.result.metadata.checkpoint_available must be present (AC-4)."""
        terminal = WorkflowProgressEvent(
            event_type="suspended",
            sequence=2,
            is_terminal=True,
            result={
                "success": False,
                "interrupted": True,
                "thread_id": "thread-abc-123",
                "interrupt_info": {"type": "human_input", "node_name": "n1"},
                "metadata": {"checkpoint_available": True},
            },
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/interruptible-workflow/stream"
            )

        events = parse_sse_bytes(body)
        result = events[-1].data.get("result", {})
        metadata = result.get("metadata", {})
        self.assertTrue(metadata.get("checkpoint_available"))

    async def test_suspended_result_has_interrupted_flag(self):
        """data.result.interrupted must be True in the suspended terminal (AC-4)."""
        terminal = WorkflowProgressEvent(
            event_type="suspended",
            sequence=2,
            is_terminal=True,
            result={
                "success": False,
                "interrupted": True,
                "thread_id": "thread-abc-123",
                "interrupt_info": {"type": "human_input", "node_name": "n1"},
                "metadata": {"checkpoint_available": True},
            },
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/interruptible-workflow/stream"
            )

        events = parse_sse_bytes(body)
        result = events[-1].data.get("result", {})
        self.assertTrue(result.get("interrupted"))

    async def test_suspended_exactly_one_terminal_event(self):
        """Exactly one terminal event must be emitted for a suspended run (AC-4)."""
        node1 = WorkflowProgressEvent(
            event_type="node_progress", sequence=0, is_terminal=False, node_name="n1"
        )
        terminal = WorkflowProgressEvent(
            event_type="suspended",
            sequence=1,
            is_terminal=True,
            result={
                "success": False,
                "interrupted": True,
                "thread_id": "th-999",
                "interrupt_info": {},
                "metadata": {"checkpoint_available": False},
            },
        )
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, terminal),
        ):
            _, _, body = await _collect_sse_response(
                app, "/execute/interruptible-workflow/stream"
            )

        events = parse_sse_bytes(body)
        terminals = [e for e in events if e.data.get("is_terminal")]
        self.assertEqual(len(terminals), 1)
        self.assertEqual(terminals[0].event_name, "suspended")


# ---------------------------------------------------------------------------
# TC-F05-002 — Client disconnect cancels upstream work; tracker finalized
# ---------------------------------------------------------------------------


class TestSSEStreamClientCancellation(IsolatedAsyncioTestCase):
    """TC-F05-002: client disconnect cancels the upstream generator.

    Caller-path contract (test-plan.md TC-F05-002 / INT-F05-2):
      ENTRYPOINT: POST /execute/{graph_id}/stream via httpx.AsyncClient +
        ASGITransport; client reads the first node_progress event, then aborts
        the connection (exits the client.stream() context).
      LOWEST ALLOWED MOCK SEAM: a fake run_workflow_stream_async that gates
        before "n2", records n2_entered, and records cancellation_received in its
        finally block (proxy for F04's tracker finalization on GeneratorExit).
      FORBIDDEN MOCKS: request.is_disconnected(), aclose(), the asyncio cancel
        propagation — the real disconnect→cancel chain executes.
      HARD CONTRACT (DRIFT-02): cancellation_received == True and
        n2_entered == False.  The `cancelled` wire event is best-effort only and
        is NOT asserted (the socket may already be closed).
      COUNTER-FACTUAL: an impl that ignores disconnect (no is_disconnected poll,
        no aclose) never sets cancellation_received and eventually enters n2 —
        these assertions would fail.
    """

    def _make_n1(self) -> WorkflowProgressEvent:
        return WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
            node_name="n1",
            state_delta={"output": "result-n1"},
            node_duration=0.01,
        )

    def _make_n2(self) -> WorkflowProgressEvent:
        return WorkflowProgressEvent(
            event_type="node_progress",
            sequence=1,
            is_terminal=False,
            node_name="n2",
            state_delta={"output": "result-n2"},
            node_duration=0.01,
        )

    async def _drive_disconnect(
        self,
        gate_after: int,
        spec_version: str = "2.4",
    ) -> Dict[str, Any]:
        """Open the stream, disconnect after the first chunk, return fake's flags.

        gate_after: number of events the fake yields before blocking on n2_gate.
            1 = disconnect after n1 (sub-case B); 2 = disconnect after both nodes
            but before the (gated) terminal (sub-case C).
        """
        app = _make_test_app()
        n2_gate = asyncio.Event()
        flags: Dict[str, Any] = {
            "n2_entered": False,
            "cancellation_received": False,
        }

        def _factory(*_a, **_kw):
            return _make_cancellable_stream(
                [self._make_n1(), self._make_n2()],
                gate_after=gate_after,
                n2_gate=n2_gate,
                flags=flags,
            )

        driver = SseAsgiDriver(
            app, "/execute/slow-workflow/stream", spec_version=spec_version
        )

        def _on_body(_chunk: bytes) -> bool:
            # Disconnect as soon as the route delivers the first chunk.
            return True

        try:
            with patch(
                "agentmap.deployment.http.api.routes.stream."
                "run_workflow_stream_async",
                side_effect=_factory,
            ):
                # Bound the whole drive so a regression that ignores disconnect
                # (and would otherwise wait on the gate forever) fails loudly
                # rather than hanging the suite.
                await asyncio.wait_for(driver.run(_on_body), timeout=5)
        finally:
            n2_gate.set()  # cleanup: unblock any non-cancelled coroutine
            await asyncio.sleep(0)

        return flags

    async def test_disconnect_after_n1_cancels_upstream(self):
        """Sub-case B: disconnect after n1 → upstream finally ran (tracker final)."""
        flags = await self._drive_disconnect(gate_after=1)
        self.assertTrue(
            flags["cancellation_received"],
            "Upstream generator's finally must run on disconnect (proxy for F04 "
            "tracker finalization) — route must aclose() the upstream generator",
        )

    async def test_disconnect_after_n1_does_not_enter_n2(self):
        """Sub-case B counter-factual: no orphaned work past the cancel point."""
        flags = await self._drive_disconnect(gate_after=1)
        self.assertFalse(
            flags["n2_entered"],
            "n2 must NOT be entered after client disconnect — the graph must not "
            "continue running once the client is gone",
        )

    async def test_disconnect_cancels_upstream_under_taskgroup_path(self):
        """Sub-case B under ASGI spec<2.4 (StreamingResponse disconnect-listener).

        Two disconnect mechanisms exist depending on asgi.spec_version: the
        is_disconnected() poll (>=2.4) and StreamingResponse's task-group
        listener (<2.4) which cancels the body generator. The route must finalize
        the upstream under BOTH; this covers the task-group cancel path.
        """
        flags = await self._drive_disconnect(gate_after=1, spec_version="2.3")
        self.assertTrue(
            flags["cancellation_received"],
            "Upstream must be finalized even when disconnect arrives as a "
            "task-cancellation (spec<2.4 StreamingResponse listener path)",
        )
        self.assertFalse(
            flags["n2_entered"],
            "No orphaned work on the task-group cancel path either",
        )

    async def test_disconnect_before_first_event_no_node_work(self):
        """Sub-case A: client closes at response.start, before any event.

        When the disconnect is observable before the route pulls the first event,
        the route must stop without entering any node work and without hanging.
        The upstream generator is never advanced (its body never runs), so there
        is no tracker to leak — the correct post-condition here is "no node work
        + clean completion + no n2", not the upstream finally (which only runs if
        the generator was started).
        """
        app = _make_test_app()
        started = {"flag": False}

        def _factory(*_a, **_kw):
            async def _gen():
                started["flag"] = True
                yield self._make_n1()
                yield self._make_n2()

            return _gen()

        driver = SseAsgiDriver(app, "/execute/slow-workflow/stream")
        driver.disconnect_on_start = True

        with patch(
            "agentmap.deployment.http.api.routes.stream." "run_workflow_stream_async",
            side_effect=_factory,
        ):
            # Must complete promptly (no hang) and not raise.
            await asyncio.wait_for(driver.run(lambda _c: False), timeout=5)

        # The route observed the disconnect before pulling; no events delivered.
        events = parse_sse_bytes(driver.raw_body)
        node_events = [e for e in events if e.event_name == "node_progress"]
        self.assertEqual(
            node_events,
            [],
            "No node_progress event must be delivered when the client is already "
            "disconnected before the first pull",
        )

    async def test_disconnect_after_all_nodes_before_terminal_cancels(self):
        """Sub-case C: disconnect after both nodes but before the terminal.

        The fake yields n1 + n2 then gates before the terminal; the client
        disconnects after the first delivered chunk, so the upstream is cancelled
        while it is blocked waiting to emit the terminal.
        """
        flags = await self._drive_disconnect(gate_after=2)
        self.assertTrue(
            flags["cancellation_received"],
            "Disconnect while the upstream is blocked before its terminal must "
            "still finalize the upstream (no leak)",
        )


# ---------------------------------------------------------------------------
# TC-F05-005 — Duration cap terminates with event: failed / stream_duration_exceeded
# ---------------------------------------------------------------------------


class TestSSEStreamEnvelope(IsolatedAsyncioTestCase):
    """TC-F05-005 (BVA A/B): wall-clock duration cap enforcement.

    Caller-path contract (test-plan.md TC-F05-005 / INT-F05-3):
      ENTRYPOINT: POST /execute/{graph_id}/stream with max_stream_duration_seconds
        injected small via get_sse_config(); fake upstream blocks indefinitely.
      LOWEST ALLOWED MOCK SEAM: get_sse_config() returns the small cap; the fake
        run_workflow_stream_async yields n1 then blocks on a never-set Event.
      FORBIDDEN MOCKS: the terminal event production (event: failed +
        error: stream_duration_exceeded) and asyncio.wait_for / the timeout — the
        route must produce the terminal through the real framing path with a real
        (small) timeout.
      COUNTER-FACTUAL: an impl that kills the connection abruptly (no terminal)
        leaves zero terminal events → the len(terminal)==1 / failed assertions
        fail.  An impl that emits event: cancelled instead of failed (DRIFT-03)
        fails the event-name assertion.
    """

    def _make_n1(self) -> WorkflowProgressEvent:
        return WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
            node_name="n1",
            state_delta={"output": "result-n1"},
            node_duration=0.01,
        )

    async def _run_capped_stream(self) -> tuple[List[SseEvent], Dict[str, Any]]:
        """Sub-case A: tiny cap + never-completing upstream → cap fires."""
        app = _make_test_app(
            sse_config={
                "max_stream_duration_seconds": 0.1,
                # Disable heartbeat for this test (out of scope for T-004).
                "heartbeat_interval_seconds": 1000,
                "idle_timeout_seconds": 1000,
            }
        )
        block_gate = asyncio.Event()  # never set
        flags: Dict[str, Any] = {"cancellation_received": False}

        def _factory(*_a, **_kw):
            return _make_blocking_stream(
                [self._make_n1()], block_gate=block_gate, flags=flags
            )

        try:
            with patch(
                "agentmap.deployment.http.api.routes.stream."
                "run_workflow_stream_async",
                side_effect=_factory,
            ):
                # Bound generously above the 0.1s cap: a working cap terminates
                # well within this; a broken cap (upstream blocks forever) trips
                # the bound and fails the test loudly instead of hanging.
                status, _, body = await asyncio.wait_for(
                    _collect_sse_response(app, "/execute/slow-workflow/stream"),
                    timeout=5,
                )
            self.assertEqual(status, 200)
            events = parse_sse_bytes(body)
        finally:
            block_gate.set()
            await asyncio.sleep(0)

        return events, flags

    async def test_duration_cap_emits_failed_terminal(self):
        """Sub-case A: cap reached → exactly one terminal event: failed."""
        events, _ = await self._run_capped_stream()
        terminal_events = [e for e in events if e.data.get("is_terminal")]
        self.assertEqual(
            len(terminal_events),
            1,
            f"Duration cap must emit exactly one terminal event, got: {events}",
        )
        self.assertEqual(
            terminal_events[-1].event_name,
            "failed",
            "Duration cap terminal must be 'failed', NOT 'cancelled' (DRIFT-03)",
        )

    async def test_duration_cap_error_code_is_stream_duration_exceeded(self):
        """Sub-case A: terminal data carries error 'stream_duration_exceeded'."""
        events, _ = await self._run_capped_stream()
        terminal = [e for e in events if e.event_name == "failed"][-1]
        # Documented code may live at data.error or data.result.error.
        error_code = terminal.data.get("error")
        if error_code is None:
            error_code = terminal.data.get("result", {}).get("error")
        self.assertEqual(
            error_code,
            "stream_duration_exceeded",
            "Duration-cap terminal must carry the documented error code",
        )

    async def test_duration_cap_cancels_upstream(self):
        """Sub-case A: hitting the cap cancels the upstream generator (finally ran)."""
        _, flags = await self._run_capped_stream()
        self.assertTrue(
            flags["cancellation_received"],
            "On duration cap the route must aclose() the upstream generator so "
            "F04 finalizes the tracker (DEC-5)",
        )

    async def test_duration_cap_n1_delivered_before_termination(self):
        """Sub-case A: n1 still reaches the client before the cap terminal."""
        events, _ = await self._run_capped_stream()
        self.assertGreaterEqual(len(events), 2, f"Expected n1 + terminal: {events}")
        self.assertEqual(events[0].event_name, "node_progress")
        self.assertEqual(events[-1].event_name, "failed")

    async def test_under_cap_completes_normally(self):
        """Sub-case B: a stream finishing within the cap is NOT cap-terminated."""
        app = _make_test_app(sse_config={"max_stream_duration_seconds": 1800})
        node1 = self._make_n1()
        terminal = WorkflowProgressEvent(
            event_type="completed",
            sequence=1,
            is_terminal=True,
            result={"success": True, "outputs": {"n1": "result-n1"}},
        )

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(node1, terminal),
        ):
            status, _, body = await _collect_sse_response(
                app, "/execute/fast-workflow/stream"
            )

        self.assertEqual(status, 200)
        events = parse_sse_bytes(body)
        self.assertEqual(events[-1].event_name, "completed")
        # No duration-cap failure injected.
        self.assertNotIn(
            "stream_duration_exceeded",
            body.decode("utf-8", errors="replace"),
            "A stream completing within the cap must not emit a duration-cap error",
        )

    # ------------------------------------------------------------------
    # TC-F05-007 — Idle heartbeat is an SSE comment, never a typed event
    # ------------------------------------------------------------------
    #
    # Caller-path contract (test-plan.md TC-F05-007 / INT-F05-3):
    #   ENTRYPOINT: POST /execute/{graph_id}/stream with idle_timeout_seconds=0
    #     (heartbeat engages immediately) and a small heartbeat_interval; the fake
    #     upstream yields n1 then holds (gated) before the terminal so the route is
    #     idle and must emit keepalive comments.
    #   LOWEST ALLOWED MOCK SEAM: get_sse_config() injects the heartbeat envelope;
    #     the fake run_workflow_stream_async yields n1, waits on a gate, then yields
    #     the terminal.  Timing is made DETERMINISTIC by the gate (no real sleep):
    #     the driver releases the gate only AFTER it has observed a ':keepalive'
    #     comment chunk, so at least one heartbeat is guaranteed without racing the
    #     wall clock.
    #   FORBIDDEN MOCKS: the heartbeat emission itself — the route must produce the
    #     real ':keepalive\\n\\n' comment through the real StreamingResponse.
    #   COUNTER-FACTUAL: an impl that emits 'event: heartbeat\\ndata: ...' (a typed
    #     event) instead of a comment would add a third typed event between n1 and
    #     the terminal → the "exactly 2 typed events" assertion fails. An impl that
    #     never emits a heartbeat would hang on the gate (the driver only releases
    #     after seeing a keepalive) → the bounded run trips its timeout and fails.

    def _heartbeat_app(self) -> FastAPI:
        return _make_test_app(
            sse_config={
                # Heartbeat engages immediately (no idle grace) and fires fast so
                # at least one keepalive is produced while the upstream is gated.
                "idle_timeout_seconds": 0,
                "heartbeat_interval_seconds": 0.05,
                "max_stream_duration_seconds": 1800,
            }
        )

    async def _run_heartbeat_stream(self) -> bytes:
        """Yield n1, idle (gated) until a heartbeat is observed, then terminal.

        Returns the full raw SSE body.  The gate is released by the driver the
        moment a ':keepalive' comment chunk is seen, so the heartbeat path is
        exercised deterministically and the stream then completes promptly.
        """
        app = self._heartbeat_app()
        terminal_gate = asyncio.Event()
        n1 = self._make_n1()
        terminal = WorkflowProgressEvent(
            event_type="completed",
            sequence=1,
            is_terminal=True,
            result={"success": True, "outputs": {"n1": "result-n1"}},
        )

        def _factory(*_a, **_kw):
            async def _gen():
                yield n1
                # Idle window: the route has no upstream event to forward, so it
                # must emit heartbeat comments until the gate releases.
                await terminal_gate.wait()
                yield terminal

            return _gen()

        driver = SseAsgiDriver(app, "/execute/slow-workflow/stream")

        def _on_body(chunk: bytes) -> bool:
            if b":keepalive" in chunk and not terminal_gate.is_set():
                terminal_gate.set()
            return False  # never disconnect

        try:
            with patch(
                "agentmap.deployment.http.api.routes.stream."
                "run_workflow_stream_async",
                side_effect=_factory,
            ):
                # A working heartbeat releases the gate quickly; a missing
                # heartbeat hangs on the gate and trips this bound (loud failure,
                # not a suite hang).
                await asyncio.wait_for(driver.run(_on_body), timeout=5)
        finally:
            terminal_gate.set()
            await asyncio.sleep(0)

        return driver.raw_body

    async def test_heartbeat_emits_keepalive_comment(self):
        """Raw SSE bytes must contain at least one ':keepalive' comment (AC-7)."""
        raw = await self._run_heartbeat_stream()
        comment_lines = [line for line in raw.split(b"\n") if line.startswith(b":")]
        self.assertTrue(
            any(b":keepalive" in line for line in comment_lines),
            f"Expected a ':keepalive' comment line in the stream, got: {raw!r}",
        )

    async def test_heartbeat_is_not_a_typed_event(self):
        """Only node_progress + completed are typed events; heartbeat is not (AC-7).

        Counter-factual: an impl emitting 'event: heartbeat' would make this 3.
        """
        raw = await self._run_heartbeat_stream()
        events = parse_sse_bytes(raw)
        event_names = [e.event_name for e in events]
        self.assertEqual(
            event_names,
            ["node_progress", "completed"],
            f"Heartbeat must not appear as a typed event; got: {event_names}",
        )

    async def test_heartbeat_has_no_data_line(self):
        """Heartbeat is a bare comment — it must not carry a 'data:' field (AC-7)."""
        raw = await self._run_heartbeat_stream()
        # Find the keepalive comment and confirm the surrounding framing carries
        # no 'data:' for it (a comment block is just ':keepalive\n\n').
        text = raw.decode("utf-8", errors="replace")
        self.assertIn(":keepalive", text)
        # No typed event named 'heartbeat'/'keepalive' may exist.
        self.assertNotIn("event: heartbeat", text)
        self.assertNotIn("event: keepalive", text)

    async def test_heartbeat_stream_completes_with_terminal(self):
        """The connection stays alive through the idle window and then terminates.

        The heartbeat is a keepalive, NOT a kill switch: after the idle window the
        terminal still arrives and the stream closes cleanly.
        """
        raw = await self._run_heartbeat_stream()
        events = parse_sse_bytes(raw)
        self.assertEqual(events[-1].event_name, "completed")
        self.assertTrue(events[-1].data.get("is_terminal"))

    # ------------------------------------------------------------------
    # TC-F05-006 — Concurrency limit: 503 JSON pre-open; slot not consumed
    # ------------------------------------------------------------------
    #
    # Caller-path contract (test-plan.md TC-F05-006 / DRIFT-04 / INT-F05-4):
    #   ENTRYPOINT: POST /execute/{graph_id}/stream when the config-sized
    #     asyncio.Semaphore has no free slot (one stream already holds the only
    #     slot with max_concurrent_streams=1).
    #   LOWEST ALLOWED MOCK SEAM: set max_concurrent_streams=1 via get_sse_config()
    #     (the test-plan-PREFERRED seam) and hold the single slot by keeping one real
    #     stream open (a gated, never-completing fake) during the second request — the
    #     real pre-open semaphore check, sized from config, executes.  The singleton
    #     is reset per test so it rebuilds from the injected config.
    #   FORBIDDEN MOCKS: the semaphore logic, and rebinding the semaphore object —
    #     the limit MUST come from config (CR BLOCKER-1: object-rebinding masked the
    #     inert-config bug, so these tests now drive the limit through config only).
    #   COUNTER-FACTUAL: an impl that opens the SSE body THEN checks concurrency
    #     cannot return 503 (status is fixed once the body starts) → the rejected
    #     response would be text/event-stream, not application/json. An impl using
    #     a BLOCKING acquire would make the second request hang waiting for the
    #     held slot instead of returning 503 → the bounded wait_for trips.

    def setUp(self) -> None:
        # The concurrency limit is a process-wide singleton sized from config on
        # first use; reset before/after each test so the injected
        # max_concurrent_streams takes effect and does not leak (CR BLOCKER-1).
        reset_stream_semaphore()
        self.addCleanup(reset_stream_semaphore)

    @staticmethod
    def _capacity_one_app() -> FastAPI:
        """App whose get_sse_config() reports max_concurrent_streams=1 (the seam).

        Driving the limit through config (not an object rebind) is what proves the
        config→limit binding the CR demanded; the singleton (reset in setUp) is
        built from this value on the first request.
        """
        return _make_test_app(sse_config={"max_concurrent_streams": 1})

    async def test_concurrency_limit_returns_503_json_pre_open(self):
        """Second concurrent stream over the configured limit → 503 JSON (AC-6)."""
        app = self._capacity_one_app()

        held_open = asyncio.Event()  # keeps the first stream occupying the slot
        first_started = asyncio.Event()

        def _holding_factory(*_a, **_kw):
            async def _gen():
                first_started.set()
                yield self._make_n1()
                await held_open.wait()  # hold the slot until the test releases it

            return _gen()

        async def _completing_factory_call(*_a, **_kw):
            # Second request's upstream should never be reached (rejected pre-open)
            async def _gen():
                yield self._make_n1()

            return _gen()

        first_driver = SseAsgiDriver(app, "/execute/wf-a/stream")
        first_task = None
        try:
            with patch(
                "agentmap.deployment.http.api.routes.stream."
                "run_workflow_stream_async",
                side_effect=_holding_factory,
            ):
                # Open the first stream and keep it open (it holds the only slot).
                first_task = asyncio.ensure_future(first_driver.run(lambda _c: False))
                await asyncio.wait_for(first_started.wait(), timeout=5)
                # Sanity: the config-sized (cap 1) pool now has its slot consumed.
                self.assertEqual(get_stream_semaphore(1)._value, 0)

                # Second request must be rejected pre-open with 503 JSON.
                with patch(
                    "agentmap.deployment.http.api.routes.stream."
                    "run_workflow_stream_async",
                    side_effect=_completing_factory_call,
                ) as second_upstream:
                    status, headers, body = await asyncio.wait_for(
                        _collect_sse_response(app, "/execute/wf-b/stream"),
                        timeout=5,
                    )

                self.assertEqual(status, 503)
                self.assertIn("application/json", headers.get("content-type", ""))
                self.assertNotIn("text/event-stream", headers.get("content-type", ""))
                self.assertNotIn(b"event:", body)
                # Pre-open rejection: the upstream facade is never invoked.
                second_upstream.assert_not_called()
        finally:
            held_open.set()
            if first_task is not None:
                await asyncio.wait_for(first_task, timeout=5)

    async def test_concurrency_rejection_does_not_consume_slot(self):
        """After a 503, the held slot is unchanged and a later stream succeeds (AC-6).

        This proves the rejection consumed no slot: once the holder releases, the
        single slot is free again and a fresh request opens normally.
        """
        app = self._capacity_one_app()

        held_open = asyncio.Event()
        first_started = asyncio.Event()

        def _holding_factory(*_a, **_kw):
            async def _gen():
                first_started.set()
                yield self._make_n1()
                await held_open.wait()

            return _gen()

        first_driver = SseAsgiDriver(app, "/execute/wf-a/stream")
        first_task = None
        try:
            with patch(
                "agentmap.deployment.http.api.routes.stream."
                "run_workflow_stream_async",
                side_effect=_holding_factory,
            ):
                first_task = asyncio.ensure_future(first_driver.run(lambda _c: False))
                await asyncio.wait_for(first_started.wait(), timeout=5)

                value_before = get_stream_semaphore(1)._value
                status, _, _ = await asyncio.wait_for(
                    _collect_sse_response(app, "/execute/wf-b/stream"),
                    timeout=5,
                )
                self.assertEqual(status, 503)
                value_after = get_stream_semaphore(1)._value
                self.assertEqual(
                    value_before,
                    value_after,
                    "A rejected (503) request must not consume a stream slot",
                )
        finally:
            held_open.set()
            if first_task is not None:
                await asyncio.wait_for(first_task, timeout=5)

        # Holder released → slot free → a fresh stream must succeed (200).
        self.assertEqual(get_stream_semaphore(1)._value, 1)
        terminal = WorkflowProgressEvent(
            event_type="completed",
            sequence=0,
            is_terminal=True,
            result={"success": True},
        )
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            status2, headers2, _ = await _collect_sse_response(
                app, "/execute/wf-c/stream"
            )
        self.assertEqual(status2, 200)
        self.assertIn("text/event-stream", headers2.get("content-type", ""))

    async def test_under_limit_request_succeeds(self):
        """Sub-case A (N-1=0 active): a request with a free slot opens normally."""
        app = self._capacity_one_app()
        terminal = WorkflowProgressEvent(
            event_type="completed",
            sequence=0,
            is_terminal=True,
            result={"success": True},
        )
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            status, headers, _ = await _collect_sse_response(app, "/execute/wf/stream")
        self.assertEqual(status, 200)
        self.assertIn("text/event-stream", headers.get("content-type", ""))

    async def test_slot_released_after_normal_completion(self):
        """The slot is released in finally after a normal stream completes (AC-6 maint).

        Two sequential streams on a capacity-1 pool both succeed: if the first did
        not release its slot, the second would 503.
        """
        app = self._capacity_one_app()
        terminal = WorkflowProgressEvent(
            event_type="completed",
            sequence=0,
            is_terminal=True,
            result={"success": True},
        )
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(terminal),
        ):
            status1, _, _ = await _collect_sse_response(app, "/execute/wf1/stream")
            self.assertEqual(status1, 200)
            self.assertEqual(
                get_stream_semaphore(1)._value,
                1,
                "Slot must be released after the first stream completes",
            )
            status2, _, _ = await _collect_sse_response(app, "/execute/wf2/stream")
            self.assertEqual(
                status2,
                200,
                "Second sequential stream must succeed (slot was released)",
            )


# ---------------------------------------------------------------------------
# TC-F05-006 (config binding) — max_concurrent_streams config DRIVES the limit
# ---------------------------------------------------------------------------


class TestSSEStreamConcurrencyConfigBinding(IsolatedAsyncioTestCase):
    """TC-F05-006 (CR BLOCKER-1): the limit is sourced from config, not hardcoded.

    The sibling ``TestSSEStreamEnvelope`` concurrency tests prove the 503 *mechanism*
    by configuring the limit through ``get_sse_config()['max_concurrent_streams']``.
    This class adds the specific binding proof the code review demanded: that the
    *configured value* is the *enforced value*, exercised purely through the config
    seam — never by rebinding the semaphore object.

    Caller-path contract (test-plan.md TC-F05-006 — "set max_concurrent_streams=N in
    config and hold one connection open"; the preferred seam, not the object-rebind
    fallback):
      ENTRYPOINT: POST /execute/{graph_id}/stream with ``max_concurrent_streams=N``
        injected via ``_make_test_app(sse_config=...)`` (i.e. through
        ``get_sse_config()``), the process-wide singleton reset so the route builds it
        from that live config value on the first request.
      LOWEST ALLOWED MOCK SEAM: ``get_sse_config()`` returns the small cap (via
        ``_make_test_app``); N real streams are held open (gated, never-completing
        fakes) so the real pre-open semaphore admission executes.
      FORBIDDEN MOCKS: the semaphore object/logic, and ANY rebinding of
        ``stream._stream_semaphore`` — the binding under test is config → limit, so a
        test that sets the limit by swapping the object would not exercise it.
      COUNTER-FACTUAL: the shipped bug — a hardcoded ``Semaphore(100)`` that ignores
        ``max_concurrent_streams`` — admits the (N+1)th concurrent stream (200
        text/event-stream) instead of rejecting it (503 JSON) for any N < 100, so
        ``test_config_value_drives_concurrency_limit`` and
        ``test_different_config_value_changes_threshold`` both FAIL on the old code.
    """

    def setUp(self) -> None:
        # Each test builds the singleton from its own injected config; reset before
        # and after so neither a prior test's pool nor this one's leaks (the
        # singleton is process-wide).
        reset_stream_semaphore()
        self.addCleanup(reset_stream_semaphore)

    @staticmethod
    def _make_n1() -> WorkflowProgressEvent:
        return WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
            node_name="n1",
            state_delta={"output": "result-n1"},
            node_duration=0.01,
        )

    async def _hold_n_streams_then_probe(
        self, *, max_concurrent_streams: int
    ) -> tuple[int, Dict[str, str], bytes, List[asyncio.Task], asyncio.Event]:
        """Open ``max_concurrent_streams`` gated streams, then probe one more.

        Returns ``(probe_status, probe_headers, probe_body, holder_tasks,
        release_gate)``.  The caller MUST set ``release_gate`` and await
        ``holder_tasks`` to tear the held streams down.  The held streams each
        occupy one slot via a never-completing gated fake; the probe is the
        (N+1)th concurrent request, which must be rejected pre-open if (and only
        if) the configured ``max_concurrent_streams`` actually sized the pool.
        """
        app = _make_test_app(
            sse_config={"max_concurrent_streams": max_concurrent_streams}
        )
        release_gate = asyncio.Event()
        started_events = [asyncio.Event() for _ in range(max_concurrent_streams)]

        def _holding_factory(index: int):
            def _factory(*_a, **_kw):
                async def _gen():
                    started_events[index].set()
                    yield self._make_n1()
                    await release_gate.wait()  # hold the slot until released

                return _gen()

            return _factory

        holder_tasks: List[asyncio.Task] = []
        # Open exactly N concurrent streams, each holding one slot.
        for index in range(max_concurrent_streams):
            driver = SseAsgiDriver(app, f"/execute/holder-{index}/stream")
            with patch(
                "agentmap.deployment.http.api.routes.stream."
                "run_workflow_stream_async",
                side_effect=_holding_factory(index),
            ):
                holder_tasks.append(asyncio.ensure_future(driver.run(lambda _c: False)))
                await asyncio.wait_for(started_events[index].wait(), timeout=5)

        # Probe the (N+1)th request: with the pool full it must be a pre-open 503.
        def _probe_factory(*_a, **_kw):
            async def _gen():
                yield self._make_n1()

            return _gen()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=_probe_factory,
        ):
            status, headers, body = await asyncio.wait_for(
                _collect_sse_response(app, "/execute/probe/stream"), timeout=5
            )

        return status, headers, body, holder_tasks, release_gate

    async def test_config_value_drives_concurrency_limit(self):
        """max_concurrent_streams=1 → the 2nd concurrent request is rejected 503.

        Drives the limit ONLY through config (no object rebind).  On the shipped
        bug (hardcoded Semaphore(100)) the 2nd stream is admitted (200), so this
        assertion FAILS on the old code.
        """
        status, headers, body, tasks, gate = await self._hold_n_streams_then_probe(
            max_concurrent_streams=1
        )
        try:
            self.assertEqual(
                status,
                503,
                "With max_concurrent_streams=1 configured, the 2nd concurrent "
                "stream must be rejected 503 — the configured value must be the "
                "enforced value (CR BLOCKER-1)",
            )
            self.assertIn("application/json", headers.get("content-type", ""))
            self.assertNotIn("text/event-stream", headers.get("content-type", ""))
            self.assertNotIn(b"event:", body)
        finally:
            gate.set()
            for task in tasks:
                await asyncio.wait_for(task, timeout=5)

    async def test_different_config_value_changes_threshold(self):
        """max_concurrent_streams=2 admits 2 concurrent streams; the 3rd is 503.

        The threshold tracks the configured value (2 here vs 1 above): the pool
        admits exactly N and rejects N+1.  On the shipped bug the threshold is
        always 100 regardless of config, so a config of 2 would still admit a 3rd
        stream — this assertion FAILS on the old code.
        """
        status, headers, body, tasks, gate = await self._hold_n_streams_then_probe(
            max_concurrent_streams=2
        )
        try:
            self.assertEqual(
                status,
                503,
                "With max_concurrent_streams=2 configured, the 3rd concurrent "
                "stream must be rejected 503 (threshold tracks the config value)",
            )
            self.assertIn("application/json", headers.get("content-type", ""))
            self.assertNotIn(b"event:", body)
        finally:
            gate.set()
            for task in tasks:
                await asyncio.wait_for(task, timeout=5)


# ---------------------------------------------------------------------------
# TC-F05-012 — First node event reaches client BEFORE workflow completes
# ---------------------------------------------------------------------------


class TestSSEStreamIncrementalDelivery(IsolatedAsyncioTestCase):
    """TC-F05-012: no transport buffering — n1 observed before the terminal.

    Caller-path contract (test-plan.md TC-F05-012):
      ENTRYPOINT: POST /execute/{graph_id}/stream via httpx.AsyncClient + ASGI
        transport, reading SSE events incrementally.
      LOWEST ALLOWED MOCK SEAM: fake run_workflow_stream_async with an
        asyncio.Event gate: yields n1, waits on n2_gate, then yields the terminal.
      FORBIDDEN MOCKS: the HTTP transport (must use a real async client) and
        asyncio.sleep as the gate.
      COUNTER-FACTUAL: a buffering impl (GZip, missing X-Accel-Buffering,
        full-response accumulation) never delivers n1 until after n2_gate.set() —
        the "n1 received while gate still unset" assertion fails.
    """

    async def test_first_event_arrives_before_gate_released(self):
        """n1 must reach the client while n2/terminal is still gated (no buffering).

        The fake yields n1, then blocks on n2_gate before the terminal. The
        SseAsgiDriver observes each http.response.body the route emits; when the
        n1 chunk arrives we record whether n2_gate is still unset (it must be) and
        THEN release the gate so the terminal is produced. A buffering transport
        (GZip / full-response accumulation) would not deliver n1 until the whole
        stream finished, so n2_gate would already be set — the assertion fails.
        """
        app = _make_test_app()
        n2_gate = asyncio.Event()
        n1 = WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
            node_name="n1",
            state_delta={"output": "result-n1"},
            node_duration=0.01,
        )
        terminal = WorkflowProgressEvent(
            event_type="completed",
            sequence=1,
            is_terminal=True,
            result={"success": True, "outputs": {"n1": "result-n1"}},
        )

        def _factory(*_a, **_kw):
            async def _gen():
                yield n1
                await n2_gate.wait()
                yield terminal

            return _gen()

        gate_set_when_n1_seen: Dict[str, Any] = {"value": None}
        driver = SseAsgiDriver(app, "/execute/gate-workflow/stream")

        def _on_body(chunk: bytes) -> bool:
            if gate_set_when_n1_seen["value"] is None and b"node_progress" in chunk:
                # n1 reached the client. Capture gate state, then release it.
                gate_set_when_n1_seen["value"] = n2_gate.is_set()
                n2_gate.set()
            return False  # never disconnect

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=_factory,
        ):
            await asyncio.wait_for(driver.run(_on_body), timeout=5)

        self.assertEqual(driver.status_code, 200)
        self.assertIs(
            gate_set_when_n1_seen["value"],
            False,
            "n1 must reach the client BEFORE n2_gate is released — a buffering "
            "transport would only deliver n1 after the whole stream completes",
        )
        events = parse_sse_bytes(driver.raw_body)
        self.assertEqual(events[0].event_name, "node_progress")
        self.assertEqual(events[-1].event_name, "completed")

    async def test_first_event_chunk_is_separate_from_terminal(self):
        """n1 is flushed as its own ASGI body message, not coalesced with terminal.

        Counter-factual: a buffering impl would emit a single body chunk
        containing both events; incremental delivery requires n1 to be sent before
        the terminal exists.
        """
        app = _make_test_app()
        n2_gate = asyncio.Event()
        n1 = WorkflowProgressEvent(
            event_type="node_progress", sequence=0, is_terminal=False, node_name="n1"
        )
        terminal = WorkflowProgressEvent(
            event_type="completed",
            sequence=1,
            is_terminal=True,
            result={"success": True},
        )

        def _factory(*_a, **_kw):
            async def _gen():
                yield n1
                await n2_gate.wait()
                yield terminal

            return _gen()

        first_chunk_had_terminal: Dict[str, Any] = {"value": None}
        driver = SseAsgiDriver(app, "/execute/gate-workflow/stream")

        def _on_body(chunk: bytes) -> bool:
            if first_chunk_had_terminal["value"] is None:
                # Inspect the very first delivered chunk: it must carry n1 but NOT
                # the terminal (which is still gated and does not yet exist).
                first_chunk_had_terminal["value"] = b"completed" in chunk
                n2_gate.set()
            return False

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=_factory,
        ):
            await asyncio.wait_for(driver.run(_on_body), timeout=5)

        self.assertIs(
            first_chunk_had_terminal["value"],
            False,
            "The first delivered chunk must contain n1 only — the terminal must "
            "not be coalesced into it (no transport buffering)",
        )

    async def test_incremental_delivery_content_type_is_event_stream(self):
        """The incremental path keeps Content-Type: text/event-stream (no GZip)."""
        app = _make_test_app()
        n1 = WorkflowProgressEvent(
            event_type="node_progress", sequence=0, is_terminal=False, node_name="n1"
        )
        terminal = WorkflowProgressEvent(
            event_type="completed",
            sequence=1,
            is_terminal=True,
            result={"success": True},
        )

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(n1, terminal),
        ):
            _, headers, _ = await _collect_sse_response(
                app, "/execute/gate-workflow/stream"
            )

        self.assertIn("text/event-stream", headers.get("content-type", ""))
        self.assertNotIn("gzip", headers.get("content-encoding", ""))


# ---------------------------------------------------------------------------
# TC-F05-008 — Auth rejection: 401/403 pre-open, parity with non-streaming
# ---------------------------------------------------------------------------


class TestSSEStreamAuth(IsolatedAsyncioTestCase):
    """TC-F05-008 (EP classes A-E) + INT-F05-4 gate ordering (auth before concurrency).

    Caller-path contract (test-plan.md TC-F05-008 / DRIFT-05 / INT-F05-4):
      ENTRYPOINT: POST /execute/{graph_id}/stream with varying auth headers; the
        REAL @requires_auth("execute") decorator must run and reject BEFORE the
        handler body (and before the concurrency acquire).
      LOWEST ALLOWED MOCK SEAM: a fake AuthService on app.state.container whose
        is_authentication_enabled() / validate_* / get_public_endpoints() drive
        the real decorator logic per sub-case.
      FORBIDDEN MOCKS: requires_auth itself (it must execute the real 401/403
        branches).
      COUNTER-FACTUAL: an impl missing the decorator (or applying auth inside the
        generator) would return 200 + text/event-stream instead of 401/403 → the
        status assertions fail.  An impl that acquires a concurrency slot before
        auth would let a 503 win over a 401 in the ordering test.
    """

    @staticmethod
    def _terminal_factory(*_a, **_kw):
        """Upstream that should run only when auth passes (sub-cases D/E)."""

        async def _gen():
            yield WorkflowProgressEvent(
                event_type="completed",
                sequence=0,
                is_terminal=True,
                result={"success": True, "outputs": {}},
            )

        return _gen()

    async def _post(
        self,
        app: FastAPI,
        *,
        headers: Optional[Dict[str, str]] = None,
        path: str = "/execute/any-graph/stream",
        body: Optional[Dict[str, Any]] = None,
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.post(path, json=body or {"inputs": {}}, headers=headers)

    # --- Sub-case A: no token, auth enabled → 401 ---

    async def test_no_token_returns_401_pre_open(self):
        """Auth enabled + no token → 401 application/json, no SSE opened (AC-8 A)."""
        app = _make_test_app(auth_enabled=True)
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._terminal_factory,
        ) as upstream:
            response = await self._post(app)
        self.assertEqual(response.status_code, 401)
        self.assertIn("application/json", response.headers.get("content-type", ""))
        self.assertNotIn("text/event-stream", response.headers.get("content-type", ""))
        self.assertNotIn(b"event:", response.content)
        upstream.assert_not_called()

    async def test_no_token_sets_www_authenticate_header(self):
        """401 must carry WWW-Authenticate: Bearer (AC-8 A)."""
        app = _make_test_app(auth_enabled=True)
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._terminal_factory,
        ):
            response = await self._post(app)
        self.assertEqual(response.headers.get("www-authenticate"), "Bearer")

    # --- Sub-case B: invalid token → 401 ---

    async def test_invalid_token_returns_401(self):
        """Auth enabled + invalid API key (unauthenticated context) → 401 (AC-8 B)."""
        invalid_ctx = AuthContext(authenticated=False, auth_method="api_key")
        app = _make_test_app(auth_enabled=True, auth_context=invalid_ctx)
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._terminal_factory,
        ) as upstream:
            response = await self._post(app, headers={"X-API-Key": "bad-key"})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("text/event-stream", response.headers.get("content-type", ""))
        upstream.assert_not_called()

    # --- Sub-case C: valid token, no execute permission → 403 ---

    async def test_valid_token_without_execute_permission_returns_403(self):
        """Auth enabled + valid token lacking 'execute' → 403, no stream (AC-8 C)."""
        ctx = AuthContext(
            authenticated=True,
            auth_method="api_key",
            user_id="u1",
            permissions=["read"],  # no 'execute', no 'admin'
        )
        app = _make_test_app(auth_enabled=True, auth_context=ctx)
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._terminal_factory,
        ) as upstream:
            response = await self._post(app, headers={"X-API-Key": "valid-key"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("application/json", response.headers.get("content-type", ""))
        self.assertNotIn("text/event-stream", response.headers.get("content-type", ""))
        upstream.assert_not_called()

    # --- Sub-case D: auth disabled → 200 stream ---

    async def test_auth_disabled_opens_stream_200(self):
        """Auth disabled → stream opens 200 text/event-stream (AC-8 D)."""
        app = _make_test_app(auth_enabled=False)
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._terminal_factory,
        ):
            response = await self._post(app)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))

    # --- Sub-case E: valid token + execute permission → 200 stream ---

    async def test_valid_token_with_execute_permission_opens_stream(self):
        """Auth enabled + valid token with 'execute' → 200 stream (AC-8 E)."""
        ctx = AuthContext(
            authenticated=True,
            auth_method="api_key",
            user_id="u1",
            permissions=["execute"],
        )
        app = _make_test_app(auth_enabled=True, auth_context=ctx)
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._terminal_factory,
        ):
            response = await self._post(app, headers={"X-API-Key": "valid-key"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))

    # --- Parity with the non-streaming endpoint ---

    async def test_401_parity_with_non_streaming_endpoint(self):
        """The streaming 401 status + WWW-Authenticate must match /execute (AC-8)."""
        app = _make_test_app(auth_enabled=True)
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._terminal_factory,
        ):
            stream_resp = await self._post(app)
        # Same app, same auth config, non-streaming endpoint, no token.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            exec_resp = await client.post("/execute/any-graph", json={"inputs": {}})

        self.assertEqual(stream_resp.status_code, exec_resp.status_code)
        self.assertEqual(stream_resp.status_code, 401)
        self.assertEqual(
            stream_resp.headers.get("www-authenticate"),
            exec_resp.headers.get("www-authenticate"),
        )

    # --- INT-F05-4: gate ordering — auth runs before the concurrency gate ---

    async def test_auth_checked_before_concurrency_gate(self):
        """A request with BOTH bad auth AND a full pool returns 401, not 503.

        INT-F05-4 ordering guarantee: auth → concurrency.  We exhaust the pool by
        configuring max_concurrent_streams=0 (via get_sse_config(), not an object
        rebind — CR BLOCKER-1) AND send no token; the auth decorator must reject
        with 401 before the handler ever attempts the (failing) concurrency acquire
        that would otherwise yield 503.

        Counter-factual: an impl that acquires the slot before running auth would
        return 503 here (the pool is empty), failing the 401 assertion.
        """
        # Empty config-sized pool: every acquire fails.  Reset the singleton so it
        # rebuilds from this injected value, and again after so it does not leak.
        reset_stream_semaphore()
        self.addCleanup(reset_stream_semaphore)

        app = _make_test_app(
            auth_enabled=True, sse_config={"max_concurrent_streams": 0}
        )
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._terminal_factory,
        ) as upstream:
            response = await self._post(app)  # no token

        self.assertEqual(
            response.status_code,
            401,
            "Auth must be evaluated before the concurrency gate (401 wins over 503)",
        )
        upstream.assert_not_called()


# ---------------------------------------------------------------------------
# TC-F05-009 — Unsupported-mode request rejected pre-open; no silent downgrade
# ---------------------------------------------------------------------------


class TestSSEStreamUnsupportedMode(IsolatedAsyncioTestCase):
    """TC-F05-009 (AC-9 / REQ-F-006): a streaming request whose shape is unsupported
    for graph-progress streaming (e.g. carrying a batch-only / unsupported control
    parameter) is rejected with HTTP 400/422 + application/json BEFORE the stream
    opens, with no silent downgrade to the non-streaming facade.

    Caller-Path Contract (test-plan.md TC-F05-009):
      ENTRYPOINT: POST /execute/{graph_id}/stream with an unsupported request shape.
      LOWEST ALLOWED MOCK SEAM: spy on run_workflow_stream_async (and, for the
        no-downgrade sub-case, run_workflow_async) to confirm NEITHER is called on
        rejection; the route handler's own request-shape validation runs for real.
      FORBIDDEN MOCKS: the validation logic itself must NOT be mocked.
      COUNTER-FACTUAL: a buggy impl that strips the unsupported parameter (or relies
        on the Pydantic model, which with the project-default extra='ignore' silently
        DROPS unknown fields) and calls run_workflow_stream_async anyway would set
        the spy's call_count to 1, failing assert_not_called().

    MED-1: ExecuteRequest is a Pydantic v2 model with the default extra='ignore', so
    an unknown field like ``batch_mode`` is silently dropped (NOT rejected) by the
    model.  These tests therefore prove the rejection comes from the handler reading
    the RAW request body — see test_pydantic_alone_would_not_reject_batch_mode.
    """

    @staticmethod
    def _stream_factory(*_a, **_kw):
        """Upstream that must run ONLY when the request shape is accepted."""

        async def _gen():
            yield WorkflowProgressEvent(
                event_type="completed",
                sequence=0,
                is_terminal=True,
                result={"success": True, "outputs": {}},
            )

        return _gen()

    async def _post(
        self,
        app: FastAPI,
        body: Dict[str, Any],
        *,
        path: str = "/execute/any-graph/stream",
        headers: Optional[Dict[str, str]] = None,
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.post(path, json=body, headers=headers)

    # --- MED-1 premise: the model alone cannot reject the unsupported field -----

    def test_pydantic_alone_would_not_reject_batch_mode(self):
        """ExecuteRequest silently drops batch_mode (extra='ignore') — the gate is
        NOT the model.

        This locks the MED-1 premise the rest of the suite depends on: a handler
        that validated only via ExecuteRequest would accept this body and open the
        stream.  The behavioural sub-cases below prove the route rejects it anyway,
        which is only possible via the raw-body check.
        """
        from agentmap.deployment.http.api.routes.execute import ExecuteRequest

        model = ExecuteRequest(**{"inputs": {}, "batch_mode": True})
        # Pydantic did NOT raise, and the unknown field is gone from the model.
        self.assertFalse(hasattr(model, "batch_mode"))
        self.assertEqual(
            set(model.model_dump().keys()),
            {"inputs", "execution_id", "force_create"},
        )

    # --- Sub-case A: batch-only parameter in the body → 400/422, no stream ------

    async def test_batch_mode_param_rejected_pre_open(self):
        """{"inputs": {}, "batch_mode": true} → 400/422 application/json, no stream.

        Counter-factual: a handler that opens the stream on this body returns 200 +
        text/event-stream and calls the upstream spy → both assertions fail.
        """
        app = _make_test_app()
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._stream_factory,
        ) as upstream:
            response = await self._post(app, {"inputs": {}, "batch_mode": True})

        self.assertIn(
            response.status_code,
            (400, 422),
            f"unsupported shape must be 400/422, got {response.status_code}",
        )
        self.assertIn("application/json", response.headers.get("content-type", ""))
        self.assertNotIn("text/event-stream", response.headers.get("content-type", ""))
        self.assertNotIn(b"event:", response.content)
        # No silent downgrade to the streaming facade.
        upstream.assert_not_called()

    async def test_rejection_body_documents_the_error(self):
        """The 400/422 body is JSON carrying a documented error message (spec §A.3)."""
        app = _make_test_app()
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._stream_factory,
        ):
            response = await self._post(app, {"inputs": {}, "batch_mode": True})

        payload = response.json()
        self.assertIn("detail", payload)
        # The documented message names the offending control parameter so the
        # client learns WHY the shape was rejected (no silent behaviour).
        self.assertIn("batch_mode", json.dumps(payload))

    async def test_rejection_log_line_carries_no_input_payload(self):
        """The reject log line is operational only — no input payload content (AC-11).

        test-plan line 117: 'log line contains no input payload content'.  We send a
        recognisably-sensitive input value alongside the unsupported flag and assert
        it never appears in the captured logs.
        """
        import logging

        app = _make_test_app()
        with self.assertLogs(
            "agentmap.deployment.http.api.routes.stream", level=logging.INFO
        ) as captured:
            with patch(
                "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
                side_effect=self._stream_factory,
            ):
                await self._post(
                    app,
                    {"inputs": {"secret": "SENSITIVE-INPUT"}, "batch_mode": True},
                )

        joined = "\n".join(captured.output)
        self.assertNotIn("SENSITIVE-INPUT", joined)

    async def test_future_unsupported_flag_also_rejected(self):
        """Attack-class enumeration: a future explicit token-through-graph flag is
        likewise rejected (any out-of-shape control parameter, not just batch_mode).

        Counter-factual: a gate that allow-lists ONLY batch_mode would let this
        through, opening the stream and calling the upstream spy.
        """
        app = _make_test_app()
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._stream_factory,
        ) as upstream:
            response = await self._post(app, {"inputs": {}, "stream_llm_tokens": True})

        self.assertIn(response.status_code, (400, 422))
        self.assertNotIn("text/event-stream", response.headers.get("content-type", ""))
        upstream.assert_not_called()

    # --- Sub-case B: no silent downgrade to the non-streaming facade ------------

    async def test_valid_request_never_calls_non_streaming_facade(self):
        """A valid streaming request opens the stream and NEVER calls run_workflow_async.

        Counter-factual: an impl that falls back to the buffered run would call
        run_workflow_async (the non-streaming facade), failing assert_not_called().
        """
        app = _make_test_app()
        with (
            patch(
                "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
                side_effect=self._stream_factory,
            ) as stream_upstream,
            patch(
                "agentmap.deployment.http.api.routes.execute.run_workflow_async",
                new_callable=AsyncMock,
            ) as non_streaming,
        ):
            response = await self._post(app, {"inputs": {}})

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))
        stream_upstream.assert_called_once()
        non_streaming.assert_not_called()

    async def test_rejection_calls_neither_facade(self):
        """On an unsupported-mode rejection, NEITHER facade is called (no downgrade)."""
        app = _make_test_app()
        with (
            patch(
                "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
                side_effect=self._stream_factory,
            ) as stream_upstream,
            patch(
                "agentmap.deployment.http.api.routes.execute.run_workflow_async",
                new_callable=AsyncMock,
            ) as non_streaming,
        ):
            response = await self._post(app, {"inputs": {}, "batch_mode": True})

        self.assertIn(response.status_code, (400, 422))
        stream_upstream.assert_not_called()
        non_streaming.assert_not_called()

    # --- Sub-case: a valid, supported body is still accepted (no over-rejection) -

    async def test_supported_body_with_known_fields_opens_stream(self):
        """The supported ExecuteRequest fields (inputs/execution_id/force_create) are
        accepted — the gate rejects unsupported shapes only, never valid ones.

        Counter-factual: a gate that rejected any field beyond ``inputs`` would 422
        this legitimate request, failing the 200 assertion.
        """
        app = _make_test_app()
        body = {
            "inputs": {"x": 1},
            "execution_id": "client-123",
            "force_create": True,
        }
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._stream_factory,
        ) as upstream:
            response = await self._post(app, body)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))
        upstream.assert_called_once()

    # --- INT-F05-4: ordering — auth → concurrency → unsupported-mode -----------

    async def test_bad_auth_with_batch_mode_returns_401_not_422(self):
        """A request with BOTH bad auth AND batch_mode returns 401, not 422.

        INT-F05-4 ordering guarantee: auth runs first.  An unauthenticated request
        must be rejected by the auth decorator (401) before the handler body ever
        reaches the unsupported-mode validation (which would otherwise yield 422).

        Counter-factual: an impl that validates the request shape BEFORE auth would
        return 422 here, failing the 401 assertion.
        """
        app = _make_test_app(auth_enabled=True)  # no token supplied → 401
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._stream_factory,
        ) as upstream:
            response = await self._post(app, {"inputs": {}, "batch_mode": True})

        self.assertEqual(
            response.status_code,
            401,
            "Auth must be evaluated before the unsupported-mode gate (401 over 422)",
        )
        upstream.assert_not_called()

    async def test_unsupported_shape_rejected_before_concurrency_acquire(self):
        """An unsupported shape is rejected BEFORE the concurrency acquire, so a
        rejected request never holds a stream slot.

        Canonical pre-open order (stream.py slot comment + spec §A.7 sequence):
        auth → unsupported-mode validation → concurrency acquire → open.  Even with
        the pool exhausted (max_concurrent_streams=0 via config, NOT an object
        rebind — CR BLOCKER-1), an unsupported shape returns 400/422 — the
        validation runs first — and no slot is consumed.

        Counter-factual: an impl that placed the validation AFTER the acquire would
        either 503 here (pool full, never reaching the validation) or consume/leak a
        slot — failing the 400/422 assertion or the untouched-counter assertion.
        """
        # Empty config-sized pool; reset the singleton so it rebuilds from this
        # injected value (and again after, so a 0-slot pool does not leak).
        reset_stream_semaphore()
        self.addCleanup(reset_stream_semaphore)

        app = _make_test_app(sse_config={"max_concurrent_streams": 0})
        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._stream_factory,
        ) as upstream:
            response = await self._post(app, {"inputs": {}, "batch_mode": True})

        self.assertIn(
            response.status_code,
            (400, 422),
            "unsupported shape must be rejected before the concurrency acquire "
            "(a rejected shape never holds a slot)",
        )
        upstream.assert_not_called()
        # The slot must NOT have been consumed by a rejected request (cap-0 pool
        # stays at 0 — validation rejected before any acquire).
        self.assertEqual(get_stream_semaphore(0)._value, 0)


# ---------------------------------------------------------------------------
# TC-F05-010 — Existing non-streaming endpoints unchanged after F05 registration
# ---------------------------------------------------------------------------


class TestSSEStreamPreOpenErrors(IsolatedAsyncioTestCase):
    """Pre-open error mapping for F04 startup exceptions (spec §A.3, CR BLOCKER-2).

    ``run_workflow_stream_async`` is a LAZY async generator: its prelude
    (``ensure_initialized`` / bundle resolution / graph lookup) does not run until
    the first ``__anext__``.  F04 raises ``GraphNotFound`` / ``InvalidInputs`` /
    ``AgentMapNotInitialized`` from that prelude *before any event*
    (``workflow_ops.py`` docstring "raised before any event").  Spec §A.3 requires
    these to surface as ordinary JSON HTTP errors (404 / 400 / 503) **before** the
    ``text/event-stream`` body opens — "a failure to even start the run looks
    identical to the non-streaming endpoint".

    The original handler wrapped only the *lazy generator construction* in the
    ``except`` clauses, so no prelude code ran inside the ``try`` and the mapping was
    dead code: a nonexistent graph returned ``200 text/event-stream`` and then a
    broken mid-stream abort.  The fix primes the upstream one step **pre-open** so the
    prelude exception is mapped to JSON before the response is committed.

    Caller-path contract:
      ENTRYPOINT: ``POST /execute/{graph_id}/stream`` via the real ASGI app.
      LOWEST ALLOWED MOCK SEAM: ``run_workflow_stream_async`` replaced with a fake
        async generator that RAISES the F04 prelude exception on its first
        ``__anext__`` — exactly what the real facade does for a missing graph /
        invalid inputs / uninitialized runtime (raised before any event).
      FORBIDDEN MOCKS: the SSE framing / StreamingResponse path, the
        ``StreamingResponse`` status machinery — the route must decide the status
        pre-open.
      COUNTER-FACTUAL: if the validation lives INSIDE the lazy generator (the old
        code), Starlette commits ``200`` + ``text/event-stream`` at
        ``http.response.start`` BEFORE the first ``__anext__`` runs, so the response
        is ``200 text/event-stream`` (then aborts mid-stream).  These tests assert
        ``application/json`` + the documented status + NO ``event:`` bytes, so they
        FAIL on the old (validation-in-generator) code and PASS only when the
        prelude exception is surfaced pre-open.
    """

    @staticmethod
    def _raising_stream_factory(exc: Exception):
        """Return a side_effect that yields an async generator raising *exc* first.

        Mirrors ``run_workflow_stream_async``'s shape (``async def`` + ``yield``)
        and F04's "raised before any event" contract: the prelude raises on the
        first ``__anext__`` before any ``WorkflowProgressEvent`` is yielded.
        """

        def _factory(*_a, **_kw):
            async def _gen():
                raise exc
                yield  # pragma: no cover — unreachable; makes this an async gen

            return _gen()

        return _factory

    async def test_unknown_graph_returns_404_json_pre_open(self):
        """Nonexistent graph → pre-open 404 JSON, never a text/event-stream 200.

        This is the headline BLOCKER-2 case: ``GraphNotFound`` from F04's prelude
        must map to a 404 JSON error before the stream opens (spec §A.3).
        """
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._raising_stream_factory(
                GraphNotFound("missing-workflow::missing-graph")
            ),
        ):
            status, headers, body = await asyncio.wait_for(
                _collect_sse_response(app, "/execute/missing-graph/stream"),
                timeout=5,
            )

        # Pre-open contract (§A.3): JSON error, NOT a streaming response.
        self.assertEqual(
            status,
            404,
            "A nonexistent graph must map to a pre-open 404 (GraphNotFound), not a "
            "200 text/event-stream that aborts mid-stream",
        )
        self.assertIn("application/json", headers.get("content-type", ""))
        self.assertNotIn("text/event-stream", headers.get("content-type", ""))
        # The stream must NOT have opened: no SSE framing in the body.
        self.assertNotIn(b"event:", body)
        self.assertNotIn(b"data:", body)
        # Error detail surfaces, identical-shaped to the non-streaming endpoint.
        detail = json.loads(body).get("detail", "")
        self.assertIn("not found", detail.lower())

    async def test_invalid_inputs_returns_400_json_pre_open(self):
        """InvalidInputs from F04's prelude → pre-open 400 JSON (spec §A.3)."""
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._raising_stream_factory(
                InvalidInputs("bad input payload")
            ),
        ):
            status, headers, body = await asyncio.wait_for(
                _collect_sse_response(app, "/execute/some-graph/stream"),
                timeout=5,
            )

        self.assertEqual(status, 400)
        self.assertIn("application/json", headers.get("content-type", ""))
        self.assertNotIn("text/event-stream", headers.get("content-type", ""))
        self.assertNotIn(b"event:", body)

    async def test_not_initialized_returns_503_json_pre_open(self):
        """AgentMapNotInitialized from F04's prelude → pre-open 503 JSON (spec §A.3)."""
        app = _make_test_app()

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._raising_stream_factory(AgentMapNotInitialized()),
        ):
            status, headers, body = await asyncio.wait_for(
                _collect_sse_response(app, "/execute/some-graph/stream"),
                timeout=5,
            )

        self.assertEqual(status, 503)
        self.assertIn("application/json", headers.get("content-type", ""))
        self.assertNotIn("text/event-stream", headers.get("content-type", ""))
        self.assertNotIn(b"event:", body)

    async def test_pre_open_error_does_not_consume_concurrency_slot(self):
        """A pre-open prelude failure must release the concurrency slot (no leak).

        The slot is acquired before priming; if priming raises, the handler's
        pre-existing release path must free it so the next request is admitted.
        """
        # Small config-sized pool (cap 2) so a leaked slot would be observable;
        # reset the singleton so it rebuilds from this value (and after, no leak).
        reset_stream_semaphore()
        self.addCleanup(reset_stream_semaphore)

        app = _make_test_app(sse_config={"max_concurrent_streams": 2})
        # Build the pool now so value_before reflects the configured capacity.
        value_before = get_stream_semaphore(2)._value

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=self._raising_stream_factory(
                GraphNotFound("missing-workflow::missing-graph")
            ),
        ):
            status, _, _ = await asyncio.wait_for(
                _collect_sse_response(app, "/execute/missing-graph/stream"),
                timeout=5,
            )

        self.assertEqual(status, 404)
        self.assertEqual(
            get_stream_semaphore(2)._value,
            value_before,
            "A pre-open prelude failure (404) must not consume a stream slot",
        )


class TestSSEStreamRegressionNonStreaming(IsolatedAsyncioTestCase):
    """TC-F05-010: POST /execute/{graph_id} still returns application/json after stream_router."""

    async def test_existing_execute_returns_json_200(self):
        """Non-streaming route must return 200 + application/json after stream router added (AC-10).

        Counter-factual: a route conflict that shadows the execute endpoint via the
        stream router would change the response shape or status code.
        """
        mock_result = {
            "success": True,
            "outputs": {"result": "test_output"},
            "metadata": {"graph_name": "any-graph"},
        }

        app = _make_test_app()

        with (
            patch("agentmap.deployment.http.api.routes.execute.ensure_initialized"),
            patch(
                "agentmap.deployment.http.api.routes.execute.run_workflow_async",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/execute/any-graph",
                    json={"inputs": {"input": "hello"}},
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.headers.get("content-type", ""))
        data = response.json()
        self.assertIn("success", data)
        self.assertTrue(data["success"])

    async def test_existing_execute_response_has_no_sse_bytes(self):
        """Non-streaming route response body must NOT contain SSE event lines (AC-10)."""
        mock_result = {
            "success": True,
            "outputs": {},
            "metadata": {"graph_name": "any-graph"},
        }

        app = _make_test_app()

        with (
            patch("agentmap.deployment.http.api.routes.execute.ensure_initialized"),
            patch(
                "agentmap.deployment.http.api.routes.execute.run_workflow_async",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/execute/any-graph",
                    json={"inputs": {}},
                )

        # No SSE event lines in the response body
        self.assertNotIn(b"event:", response.content)
        self.assertNotIn(b"text/event-stream", response.content)

    async def test_stream_route_does_not_conflict_with_execute_route(self):
        """POST /execute/any-graph must not be captured by the /stream route (AC-10)."""
        mock_result = {
            "success": True,
            "outputs": {"k": "v"},
            "metadata": {"graph_name": "any-graph"},
        }

        app = _make_test_app()

        with (
            patch("agentmap.deployment.http.api.routes.execute.ensure_initialized"),
            patch(
                "agentmap.deployment.http.api.routes.execute.run_workflow_async",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
            patch(
                "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            ) as mock_stream,
        ):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/execute/any-graph",
                    json={"inputs": {}},
                )

        # The streaming facade must NOT have been called for a non-streaming request
        mock_stream.assert_not_called()
        self.assertEqual(response.status_code, 200)

    async def test_execute_py_source_unmodified_marker(self):
        """execute.py must not contain any stream-specific imports (AC-10 additive-only check).

        This is a structural assertion: we confirm execute.py does NOT import
        run_workflow_stream_async, which would indicate an unintended edit.
        """
        import pathlib

        execute_py = pathlib.Path(
            "src/agentmap/deployment/http/api/routes/execute.py"
        ).read_text()
        self.assertNotIn(
            "run_workflow_stream_async",
            execute_py,
            "execute.py must not reference run_workflow_stream_async (must be additive-only)",
        )
        self.assertNotIn(
            "stream_router",
            execute_py,
            "execute.py must not reference stream_router (router registration belongs in server.py)",
        )


# ---------------------------------------------------------------------------
# UAT HIGH-1 — No SECOND terminal event after F04's terminal (REQ-F-002 / AC-1 / AC-5)
# ---------------------------------------------------------------------------


class TestSSENoDuplicateTerminalAfterDisconnect(IsolatedAsyncioTestCase):
    """UAT HIGH-1: a client disconnect (or deadline lapse) in the window AFTER F04's
    terminal event but BEFORE the generator's next pull must NOT emit a second
    terminal event.

    Caller-path contract:
      ENTRYPOINT: POST /execute/{graph_id}/stream via SseAsgiDriver; the client
        disconnects the moment it receives the terminal chunk (on_body returns
        True on the terminal frame), so the generator's NEXT loop iteration would
        observe is_disconnected()==True.
      LOWEST ALLOWED MOCK SEAM: a fake run_workflow_stream_async yielding the
        scripted node/terminal events; the real disconnect→is_disconnected chain,
        StreamingResponse lifecycle, and SSE framing all execute.
      FORBIDDEN MOCKS: request.is_disconnected(), the terminal-event production,
        the SSE framing — all real.
      HARD CONTRACT (REQ-F-002 / AC-1 / AC-5): exactly ONE terminal event; it is
        last; no second `cancelled` follows the F04 terminal.
      COUNTER-FACTUAL: the pre-fix generator (no `return` after the terminal yield)
        loops back, sees is_disconnected()==True, and emits a SECOND terminal
        `cancelled` — these assertions then fail. (Verified: reverting the two
        `return` statements makes test_a/test_c emit two terminals.)
    """

    @staticmethod
    def _terminal_event() -> WorkflowProgressEvent:
        return WorkflowProgressEvent(
            event_type="completed",
            sequence=1,
            is_terminal=True,
            result={"success": True, "outputs": {"n1": "result-n1"}},
        )

    @staticmethod
    def _node_event() -> WorkflowProgressEvent:
        return WorkflowProgressEvent(
            event_type="node_progress",
            sequence=0,
            is_terminal=False,
            node_name="n1",
            state_delta={"output": "result-n1"},
            node_duration=0.01,
        )

    async def _drive_disconnect_on_terminal(
        self, *events: WorkflowProgressEvent
    ) -> List[SseEvent]:
        """Drive the stream, disconnecting the instant the terminal chunk arrives."""
        app = _make_test_app()
        driver = SseAsgiDriver(app, "/execute/wf/stream")

        def _on_body(chunk: bytes) -> bool:
            # Disconnect as soon as the terminal frame is delivered, so the next
            # generator iteration (if any) observes the disconnect.
            return b"event: completed" in chunk or b"event: failed" in chunk

        with patch(
            "agentmap.deployment.http.api.routes.stream.run_workflow_stream_async",
            side_effect=lambda *a, **kw: _make_fake_stream(*events),
        ):
            await asyncio.wait_for(driver.run(_on_body), timeout=5)

        return parse_sse_bytes(driver.raw_body)

    async def test_a_disconnect_after_terminal_no_second_cancelled(self):
        """Disconnect after the completed terminal → no second `cancelled`."""
        events = await self._drive_disconnect_on_terminal(
            self._node_event(), self._terminal_event()
        )
        terminals = [e for e in events if e.data.get("is_terminal")]
        self.assertEqual(
            len(terminals),
            1,
            f"Exactly one terminal expected; got {[e.event_name for e in events]}",
        )
        self.assertEqual(events[-1].event_name, "completed")
        cancelled = [e for e in events if e.event_name == "cancelled"]
        self.assertEqual(
            cancelled,
            [],
            "No `cancelled` event may follow the F04 terminal (REQ-F-002)",
        )

    async def test_c_primed_terminal_then_disconnect_one_terminal(self):
        """The primed FIRST event is itself terminal, then client disconnects.

        Exercises the replay path: F04 yields a terminal as its very first (and
        only) event; the route primes + replays it, then the client disconnects.
        The replay path must `return` so no second `cancelled` is emitted.
        """
        events = await self._drive_disconnect_on_terminal(self._terminal_event())
        terminals = [e for e in events if e.data.get("is_terminal")]
        self.assertEqual(
            len(terminals),
            1,
            f"Exactly one terminal expected; got {[e.event_name for e in events]}",
        )
        self.assertEqual(events[0].event_name, "completed")
        cancelled = [e for e in events if e.event_name == "cancelled"]
        self.assertEqual(
            cancelled,
            [],
            "No `cancelled` event may follow a primed terminal (REQ-F-002)",
        )
