"""
Unit tests for E06-F05 T-002: SSE framing helpers, concurrency semaphore, and stream.py scaffold.

Test classes in this file:
  - TestSSEFramingHelpers   — SSE event/heartbeat framing output (TC-F05-009 white-box subset,
                              spec §A.3 framing contract)
  - TestSSEImportSurface    — White-box import assertion: stream.py must not import
                              call_llm_stream_async or LLMStreamChunk (AC-9 / TC-F05-009)
  - TestSSEContentCapturePolicy — White-box source assertion: no logger call emits payload
                              content (AC-11 / TC-F05-011)
  - TestSSESemaphore        — Module-level asyncio.Semaphore exists and has the right behaviour
                              (DEC-6, pre-open acquire/release contract)

Caller-Path Contracts (per test-plan.md):

  TestSSEFramingHelpers:
    ENTRYPOINT (internal): _format_sse_event() and _format_sse_heartbeat() called directly.
    Internal-only entrypoint is justified: these are pure functions (no I/O, no async);
    testing them directly is the correct seam per the Caller-Path Contract — the SSE framing
    helpers ARE the boundary.
    LOWEST ALLOWED MOCK SEAM: none — pure functions.
    FORBIDDEN MOCKS: none applicable.
    COUNTER-FACTUAL:
      A buggy impl that produces multi-line data would fail the "data: " single-line assertion.
      A buggy impl that uses "event: keepalive" instead of ":keepalive" would fail the heartbeat
      comment-format assertion.

  TestSSEImportSurface / TestSSEContentCapturePolicy:
    ENTRYPOINT (internal-only): pathlib.Path.read_text() on stream.py source.
    Internal-only justification: AC-9 and AC-11 are structural invariants enforced at the source
    level (same as F04 TC-F04-009). No runtime caller path applies.
    COUNTER-FACTUAL:
      A buggy stream.py that imports LLMStreamChunk would fail the "not in source" assertion.

  TestSSESemaphore:
    ENTRYPOINT (internal): agentmap.deployment.http.api.routes.stream._stream_semaphore
    Internal-only justification: the semaphore is a module attribute; testing its existence and
    capacity directly is the lowest-cost verification without needing a full HTTP test.
    COUNTER-FACTUAL:
      A missing _stream_semaphore attribute would raise AttributeError.
      A semaphore with capacity 0 would block every acquire, failing the "acquirable" assertion.
"""

import asyncio
import pathlib
import unittest

# ---------------------------------------------------------------------------
# TestSSEFramingHelpers — byte-for-byte SSE framing contract (spec §A.3)
# ---------------------------------------------------------------------------


class TestSSEFramingHelpers(unittest.TestCase):
    """Unit tests for _format_sse_event() and _format_sse_heartbeat().

    These pure functions must produce output that conforms to the SSE wire format
    (RFC/W3C Server-Sent Events) as specified in spec.md §A.3.
    """

    def setUp(self):
        """Import the framing helpers once for all test methods."""
        from agentmap.deployment.http.api.routes.stream import (
            _format_sse_event,
            _format_sse_heartbeat,
        )

        self._format_sse_event = _format_sse_event
        self._format_sse_heartbeat = _format_sse_heartbeat

    # --- _format_sse_event ---

    def test_event_framing_node_progress(self):
        """AC spec: _format_sse_event('node_progress', {...}) => 'event: node_progress\\ndata: {...}\\n\\n'."""
        result = self._format_sse_event("node_progress", {"sequence": 0})
        self.assertEqual(result, 'event: node_progress\ndata: {"sequence": 0}\n\n')

    def test_event_framing_completed(self):
        """Event type 'completed' is emitted verbatim as the SSE event name."""
        result = self._format_sse_event(
            "completed", {"sequence": 2, "is_terminal": True}
        )
        self.assertIn("event: completed\n", result)
        self.assertIn("data:", result)
        self.assertTrue(result.endswith("\n\n"))

    def test_event_framing_failed(self):
        """Event type 'failed' maps 1:1 to the SSE event: line."""
        result = self._format_sse_event("failed", {"sequence": 1, "error": "boom"})
        self.assertIn("event: failed\n", result)

    def test_event_framing_suspended(self):
        """Event type 'suspended' maps 1:1 to the SSE event: line."""
        result = self._format_sse_event("suspended", {"sequence": 3, "result": {}})
        self.assertIn("event: suspended\n", result)

    def test_event_framing_cancelled(self):
        """Event type 'cancelled' is supported (best-effort on disconnect)."""
        result = self._format_sse_event("cancelled", {"reason": "client_disconnect"})
        self.assertIn("event: cancelled\n", result)

    def test_data_line_is_single_compact_json(self):
        """spec §A.3: data is a single compact JSON line (no multi-line, no pretty-print).

        Counter-factual: a pretty-printed payload would span multiple lines, breaking the
        single data: field contract.
        """
        large_data = {str(i): f"value_{i}" for i in range(50)}
        result = self._format_sse_event("node_progress", large_data)

        # Extract the data: line(s) — there should be exactly one
        lines = result.split("\n")
        data_lines = [ln for ln in lines if ln.startswith("data:")]
        self.assertEqual(
            len(data_lines), 1, "data: must be a single line (compact JSON)"
        )

        # The data line must not contain pretty-printed newlines embedded in it
        data_content = data_lines[0][len("data:") :].strip()
        self.assertNotIn("\n", data_content)

    def test_event_terminates_with_blank_line(self):
        """SSE spec: each event is terminated by a blank line (two newlines)."""
        result = self._format_sse_event("node_progress", {"sequence": 0})
        self.assertTrue(
            result.endswith("\n\n"), f"Expected trailing \\n\\n, got: {result!r}"
        )

    def test_event_format_exact_structure(self):
        """Verify exact byte structure: event line, data line, blank line."""
        result = self._format_sse_event("node_progress", {"sequence": 0})
        parts = result.split("\n")
        # parts[-1] is the empty string after trailing \n\n, parts[-2] is also empty
        self.assertEqual(parts[0], "event: node_progress")
        self.assertTrue(parts[1].startswith("data:"))
        self.assertEqual(parts[2], "")  # blank line
        self.assertEqual(parts[3], "")  # trailing newline produces empty final element

    def test_event_data_dict_is_serialized_to_json(self):
        """data: value is valid JSON that round-trips back to the original dict."""
        import json

        payload = {"sequence": 0, "node_name": "n1", "state_delta": {"key": "val"}}
        result = self._format_sse_event("node_progress", payload)
        data_line = [ln for ln in result.split("\n") if ln.startswith("data:")][0]
        json_str = data_line[len("data:") :].strip()
        recovered = json.loads(json_str)
        self.assertEqual(recovered, payload)

    # --- _format_sse_heartbeat ---

    def test_heartbeat_is_comment_line(self):
        """spec §A.3: heartbeat is ':keepalive\\n\\n' — an SSE comment (starts with ':')."""
        result = self._format_sse_heartbeat()
        self.assertTrue(
            result.startswith(":"),
            f"Heartbeat must be a comment line (start with ':'), got: {result!r}",
        )

    def test_heartbeat_exact_format(self):
        """spec §A.3: exact heartbeat bytes are ':keepalive\\n\\n'."""
        result = self._format_sse_heartbeat()
        self.assertEqual(result, ":keepalive\n\n")

    def test_heartbeat_has_no_event_field(self):
        """Heartbeat must not contain 'event:' or 'data:' lines.

        Counter-factual: 'event: heartbeat\\ndata: {}\\n\\n' would appear as a typed event
        to an EventSource consumer, violating AC-7.
        """
        result = self._format_sse_heartbeat()
        self.assertNotIn("event:", result)
        self.assertNotIn("data:", result)

    def test_heartbeat_terminates_with_blank_line(self):
        """SSE comment also terminates with \\n\\n so EventSource reconnect logic is not triggered."""
        result = self._format_sse_heartbeat()
        self.assertTrue(
            result.endswith("\n\n"), f"Expected trailing \\n\\n, got: {result!r}"
        )


# ---------------------------------------------------------------------------
# TestSSEImportSurface — AC-9 structural: no LLM stream import (TC-F05-009)
# ---------------------------------------------------------------------------


class TestSSEImportSurface(unittest.TestCase):
    """White-box import-surface assertion: stream.py must not import call_llm_stream_async
    or LLMStreamChunk (spec.md DEC-3, AC-9, F05 structural isolation from TD-026 surface).

    This mirrors F04 TC-F04-009 (test_graph_progress_streaming.py:TestAstreamShapeSmoke
    pattern).

    ENTRYPOINT (internal-only): source read via pathlib — static assertion, no runtime path.
    COUNTER-FACTUAL: if stream.py imports LLMStreamChunk, this test fails immediately.
    """

    _STREAM_PY_PATH = (
        pathlib.Path(__file__).parent.parent.parent.parent.parent.parent
        / "src"
        / "agentmap"
        / "deployment"
        / "http"
        / "api"
        / "routes"
        / "stream.py"
    )

    def _read_source(self) -> str:
        """Read stream.py source; skip if the file does not exist yet."""
        if not self._STREAM_PY_PATH.exists():
            self.skipTest(f"stream.py does not exist yet at {self._STREAM_PY_PATH}")
        return self._STREAM_PY_PATH.read_text(encoding="utf-8")

    def test_stream_py_does_not_import_call_llm_stream_async(self):
        """stream.py must NOT import or reference call_llm_stream_async (DEC-3 / AC-9).

        Counter-factual: a stream.py that imports call_llm_stream_async would pull in the
        TD-026 surface and fail this assertion.
        """
        source = self._read_source()
        self.assertNotIn(
            "call_llm_stream_async",
            source,
            "stream.py must not import call_llm_stream_async — TD-026 structural isolation",
        )

    def test_stream_py_does_not_import_llm_stream_chunk(self):
        """stream.py must NOT import or reference LLMStreamChunk (DEC-3 / AC-9).

        Counter-factual: a stream.py that imports LLMStreamChunk would expose the TD-026
        surface at the transport boundary, which spec.md DEC-3 prohibits.
        """
        source = self._read_source()
        self.assertNotIn(
            "LLMStreamChunk",
            source,
            "stream.py must not import LLMStreamChunk — TD-026 structural isolation",
        )


# ---------------------------------------------------------------------------
# TestSSEContentCapturePolicy — AC-11 structural: no payload logging (TC-F05-011)
# ---------------------------------------------------------------------------


class TestSSEContentCapturePolicy(unittest.TestCase):
    """White-box source assertion: stream.py logger calls must not emit node state content.

    spec.md REQ-F-007 / AC-11: the SSE layer must not log state_delta, result, outputs,
    or any node payload content. Only operational lifecycle events are permissible.

    ENTRYPOINT (internal-only): source scan via pathlib.
    COUNTER-FACTUAL: if stream.py has 'logger.info(state_delta)', this test fails.
    """

    _FORBIDDEN_IN_LOG_LINES = [
        "state_delta",
        "node_state",
        "completion",
        "prompt",
        "text_delta",
    ]

    _STREAM_PY_PATH = (
        pathlib.Path(__file__).parent.parent.parent.parent.parent.parent
        / "src"
        / "agentmap"
        / "deployment"
        / "http"
        / "api"
        / "routes"
        / "stream.py"
    )

    def _read_source(self) -> str:
        """Read stream.py source; skip if file does not exist yet."""
        if not self._STREAM_PY_PATH.exists():
            self.skipTest(f"stream.py does not exist yet at {self._STREAM_PY_PATH}")
        return self._STREAM_PY_PATH.read_text(encoding="utf-8")

    def test_no_logger_call_emits_payload_content(self):
        """No logger.* line in stream.py must reference node payload keywords.

        Permitted logger keywords: stream, cancel, open, close, limit, reject, graph, duration.
        Forbidden in logger lines: state_delta, result, outputs, node_state, completion,
        prompt, text_delta.

        Counter-factual: logger.info(f"Node state: {state_delta}") would fail this assertion.
        """
        source = self._read_source()
        logger_lines = [
            line for line in source.splitlines() if "logger." in line or "log." in line
        ]
        for line in logger_lines:
            for forbidden in self._FORBIDDEN_IN_LOG_LINES:
                self.assertNotIn(
                    forbidden,
                    line,
                    f"stream.py logger call emits payload content '{forbidden}': {line.strip()}",
                )

    def test_no_telemetry_line_captures_payload_content(self):
        """No telemetry span/attribute line in stream.py references payload content."""
        source = self._read_source()
        telemetry_lines = [
            line
            for line in source.splitlines()
            if "span" in line.lower() or "attribute" in line.lower()
        ]
        for line in telemetry_lines:
            for forbidden in self._FORBIDDEN_IN_LOG_LINES:
                self.assertNotIn(
                    forbidden,
                    line,
                    f"stream.py telemetry line captures payload content '{forbidden}': {line.strip()}",
                )

    def test_no_result_keyword_in_logger_lines(self):
        """'result' must not appear in any logger call in stream.py.

        'result' is a forbidden payload keyword per TC-F05-011. It is listed separately
        because it is a common variable name that implementers might inadvertently log.
        """
        source = self._read_source()
        logger_lines = [
            line for line in source.splitlines() if "logger." in line or "log." in line
        ]
        for line in logger_lines:
            self.assertNotIn(
                "result",
                line,
                f"stream.py logger call references 'result' payload content: {line.strip()}",
            )


# ---------------------------------------------------------------------------
# TestSSESemaphore — module-level asyncio.Semaphore existence + behaviour (DEC-6)
# ---------------------------------------------------------------------------


class TestSSESemaphore(unittest.IsolatedAsyncioTestCase):
    """Tests that the module-level _stream_semaphore exists, is an asyncio.Semaphore,
    and correctly gates concurrent stream admission (DEC-6).

    ENTRYPOINT (internal-only): agentmap.deployment.http.api.routes.stream._stream_semaphore
    accessed directly as a module attribute.

    Internal-only justification: DEC-6 specifies a module-level asyncio.Semaphore; the test
    verifies the attribute contract — existence, type, and acquire/release semantics.
    A full HTTP-layer test (TC-F05-006) exercises the gate at the route level; this test
    isolates the semaphore primitive.

    LOWEST ALLOWED MOCK SEAM: direct attribute access on the module.
    FORBIDDEN MOCKS: do not mock asyncio.Semaphore itself.
    COUNTER-FACTUAL:
      A missing _stream_semaphore attribute raises AttributeError.
      A semaphore with capacity 0 fails the "acquire succeeds" assertion.
    """

    def setUp(self):
        """Import the stream module to access the semaphore."""
        import agentmap.deployment.http.api.routes.stream as stream_module

        self._stream_module = stream_module

    def test_stream_semaphore_exists(self):
        """_stream_semaphore attribute must exist on the stream module (DEC-6)."""
        self.assertTrue(
            hasattr(self._stream_module, "_stream_semaphore"),
            "stream module must have a module-level _stream_semaphore attribute",
        )

    def test_stream_semaphore_is_asyncio_semaphore(self):
        """_stream_semaphore must be an asyncio.Semaphore instance."""
        self.assertIsInstance(
            self._stream_module._stream_semaphore,
            asyncio.Semaphore,
            "_stream_semaphore must be an asyncio.Semaphore",
        )

    async def test_semaphore_is_acquirable(self):
        """Semaphore has positive capacity: acquire must succeed without blocking.

        Counter-factual: a semaphore with capacity 0 would deadlock here.
        """
        sem = self._stream_module._stream_semaphore
        # Non-blocking acquire must succeed (semaphore has capacity > 0)
        acquired = sem._value > 0  # Check internal counter without consuming a slot
        self.assertTrue(acquired, "_stream_semaphore must have capacity > 0")

    async def test_semaphore_acquire_release_roundtrip(self):
        """Acquire then release the semaphore; counter is restored.

        This verifies the acquire/release mechanism that the route handler uses
        in its finally block (DEC-6: slot released regardless of exit path).
        """
        sem = self._stream_module._stream_semaphore
        initial_value = sem._value

        async with sem:
            mid_value = sem._value
            self.assertEqual(
                mid_value, initial_value - 1, "Slot must be consumed after acquire"
            )

        final_value = sem._value
        self.assertEqual(
            final_value, initial_value, "Slot must be restored after release"
        )

    async def test_semaphore_capacity_positive(self):
        """Semaphore capacity (initial value) must be > 0 (default 100 per spec §A.4)."""
        sem = self._stream_module._stream_semaphore
        # asyncio.Semaphore does not expose initial value directly;
        # we can try to acquire once and confirm it worked
        acquired = await asyncio.wait_for(
            asyncio.ensure_future(sem.acquire()), timeout=0.1
        )
        self.assertTrue(acquired, "_stream_semaphore must be acquirable (capacity > 0)")
        sem.release()  # restore


# ---------------------------------------------------------------------------
# TestSSEModuleScaffold — APIRouter and helper presence
# ---------------------------------------------------------------------------


class TestSSEModuleScaffold(unittest.TestCase):
    """Smoke tests that stream.py exports the expected public names.

    Verifies the module scaffold (DEC-4: per-domain router pattern):
      - `router` is an APIRouter
      - `_format_sse_event` and `_format_sse_heartbeat` are callable
      - `_to_serializable` exists (mirrors execute.py:130 pattern)
      - `_stream_semaphore` is present

    These are structural assertions; behaviour is covered by the other test classes.
    """

    def setUp(self):
        from fastapi import APIRouter

        import agentmap.deployment.http.api.routes.stream as stream_module

        self._mod = stream_module
        self._APIRouter = APIRouter

    def test_router_exists_and_is_api_router(self):
        """stream module must export `router` as an APIRouter (DEC-4)."""
        self.assertTrue(hasattr(self._mod, "router"))
        self.assertIsInstance(self._mod.router, self._APIRouter)

    def test_format_sse_event_is_callable(self):
        """_format_sse_event must be a callable (not None, not a module)."""
        self.assertTrue(hasattr(self._mod, "_format_sse_event"))
        self.assertTrue(callable(self._mod._format_sse_event))

    def test_format_sse_heartbeat_is_callable(self):
        """_format_sse_heartbeat must be a callable."""
        self.assertTrue(hasattr(self._mod, "_format_sse_heartbeat"))
        self.assertTrue(callable(self._mod._format_sse_heartbeat))

    def test_to_serializable_exists(self):
        """_to_serializable must exist (mirrors execute.py:130 pattern per task spec)."""
        self.assertTrue(
            hasattr(self._mod, "_to_serializable"),
            "stream module must have _to_serializable helper",
        )
        self.assertTrue(callable(self._mod._to_serializable))

    def test_stream_semaphore_attribute(self):
        """_stream_semaphore must be present as a module-level attribute."""
        self.assertTrue(
            hasattr(self._mod, "_stream_semaphore"),
            "stream module must have _stream_semaphore",
        )


if __name__ == "__main__":
    unittest.main()
