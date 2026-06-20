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


def _make_test_app(auth_enabled: bool = False) -> FastAPI:
    """Create a minimal FastAPI app with both execute and stream routers.

    Auth is disabled by default so tests can focus on the streaming contract.
    The mock auth service is attached via app.state.container.

    stream_router must be registered before execution_router: the execute router
    has a greedy {graph_id:path} parameter that would otherwise match
    POST /execute/{graph_id}/stream before the stream router can.
    """
    app = FastAPI()
    app.include_router(stream_router)
    app.include_router(execution_router)

    mock_container = MagicMock()
    mock_auth_service = MagicMock()
    mock_auth_service.is_authentication_enabled.return_value = auth_enabled
    mock_container.auth_service.return_value = mock_auth_service
    app.state.container = mock_container

    return app


async def _collect_sse_response(
    app: FastAPI,
    path: str,
    body: Optional[Dict[str, Any]] = None,
) -> tuple[int, Dict[str, str], bytes]:
    """Drive a POST request to *path* on *app* and collect the full SSE body.

    Returns (status_code, headers_dict, raw_body_bytes).
    Uses httpx.AsyncClient with ASGITransport so headers are readable before
    the full body arrives (true async streaming transport).
    """
    if body is None:
        body = {"inputs": {}}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(path, json=body)
        return response.status_code, dict(response.headers), response.content


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
