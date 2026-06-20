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
from agentmap.models.execution.progress_event import WorkflowProgressEvent

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
# TC-F05-010 — Existing non-streaming endpoints unchanged after F05 registration
# ---------------------------------------------------------------------------


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
