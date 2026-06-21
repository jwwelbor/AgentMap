"""
Unit tests for E06-F05 T-002: SSE framing helpers, concurrency semaphore, and stream.py scaffold.

Test classes in this file:
  - TestSSEFramingHelpers   — SSE event/heartbeat framing output (TC-F05-009 white-box subset,
                              spec §A.3 framing contract)
  - TestSSEImportSurface    — White-box import assertion: stream.py must not import
                              call_llm_stream_async or LLMStreamChunk (AC-9 / TC-F05-009)
  - TestSSEContentCapturePolicy — White-box source assertion: no logger call emits payload
                              content (AC-11 / TC-F05-011)
  - TestSSESemaphore        — Config-sized concurrency singleton + admission accessors
                              (DEC-6 / CR BLOCKER-1: config sizes the semaphore)

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
    ENTRYPOINT (internal): agentmap.deployment.http.api.sse_concurrency accessors
    (get_stream_semaphore / try_acquire_stream_slot / reset_stream_semaphore).
    Internal-only justification: the limiter is a config-sized process-wide singleton;
    testing its sizing/identity/acquire-release directly is the lowest-cost verification
    without needing a full HTTP test (TC-F05-006 covers the route gate).
    COUNTER-FACTUAL:
      A capacity that ignored the configured value (the shipped bug) would fail the
      capacity-matches-config assertion. A blocking try-acquire would hang the
      returns-None-when-full assertion.
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

    # Full AC-11 forbidden-keyword set (spec.md AC-11 / task spec line 43).
    # ``result`` and ``outputs`` are also asserted individually below because they
    # are common variable names an implementer might inadvertently log.
    _FORBIDDEN_IN_LOG_LINES = [
        "state_delta",
        "result",
        "outputs",
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

    def test_no_outputs_keyword_in_logger_lines(self):
        """'outputs' must not appear in any logger call in stream.py (AC-11).

        'outputs' is a forbidden payload keyword per AC-11 / TC-F05-011, asserted
        individually because — like 'result' — it is a common variable name an
        implementer might inadvertently interpolate into a log line.

        Counter-factual: logger.info(f"Run outputs: {outputs}") would fail here.
        """
        source = self._read_source()
        logger_lines = [
            line for line in source.splitlines() if "logger." in line or "log." in line
        ]
        for line in logger_lines:
            self.assertNotIn(
                "outputs",
                line,
                f"stream.py logger call references 'outputs' payload content: {line.strip()}",
            )


# ---------------------------------------------------------------------------
# TestSSESemaphore — config-sized concurrency singleton + admission (DEC-6)
# ---------------------------------------------------------------------------


class TestSSESemaphore(unittest.IsolatedAsyncioTestCase):
    """Tests the config-sized stream-admission semaphore primitive (DEC-6; CR BLOCKER-1).

    ENTRYPOINT (internal): the sse_concurrency accessors —
    ``get_stream_semaphore(max_concurrent_streams)``, ``try_acquire_stream_slot(...)``,
    and ``reset_stream_semaphore()``.

    Internal-only justification: DEC-6 specifies a process-wide asyncio.Semaphore
    SIZED FROM CONFIG (CR BLOCKER-1 — a hardcoded literal was the defect).  This test
    verifies the primitive's contract — config sizing, singleton identity, acquire/
    release semantics, and the non-blocking try-acquire — in isolation.  A full
    HTTP-layer test (TC-F05-006) exercises the gate through the route at request time.

    LOWEST ALLOWED MOCK SEAM: none — call the real accessors with a small cap.
    FORBIDDEN MOCKS: asyncio.Semaphore itself, and any rebinding of the singleton
    object (the binding under test is config → limit).
    COUNTER-FACTUAL:
      A capacity that ignored max_concurrent_streams (the shipped bug) would fail
      test_semaphore_capacity_matches_config (a cap-2 request would have _value 100).
      A try-acquire that blocked instead of returning None when full would hang
      test_try_acquire_returns_none_when_full.
    """

    def setUp(self):
        """Import the config-sized concurrency accessors; reset the singleton."""
        from agentmap.deployment.http.api.sse_concurrency import (
            get_stream_semaphore,
            reset_stream_semaphore,
            try_acquire_stream_slot,
        )

        self._get_stream_semaphore = get_stream_semaphore
        self._reset_stream_semaphore = reset_stream_semaphore
        self._try_acquire_stream_slot = try_acquire_stream_slot
        # Each test builds the singleton from its own cap; reset before/after.
        reset_stream_semaphore()
        self.addCleanup(reset_stream_semaphore)

    def test_get_stream_semaphore_returns_asyncio_semaphore(self):
        """The accessor must return an asyncio.Semaphore (DEC-6)."""
        self.assertIsInstance(
            self._get_stream_semaphore(5),
            asyncio.Semaphore,
            "get_stream_semaphore must return an asyncio.Semaphore",
        )

    def test_semaphore_is_a_singleton(self):
        """Repeat calls return the SAME object — one semaphore shared by all requests.

        Counter-factual: a per-request semaphore (new object each call) would limit
        nothing; ``assertIs`` fails if a fresh object is returned.
        """
        first = self._get_stream_semaphore(5)
        second = self._get_stream_semaphore(5)
        self.assertIs(first, second, "the admission semaphore must be a singleton")

    def test_semaphore_capacity_matches_config(self):
        """Capacity is sized from the configured value, NOT a hardcoded default.

        This is the unit-level binding proof for CR BLOCKER-1: a cap of 3 yields a
        semaphore whose initial _value is 3 (the shipped bug — hardcoded 100 — would
        give 100 here).
        """
        sem = self._get_stream_semaphore(3)
        self.assertEqual(
            sem._value, 3, "semaphore capacity must equal the configured limit"
        )

    def test_reset_rebuilds_from_new_config(self):
        """After reset, the next call re-sizes the pool from the new config value.

        Counter-factual: if reset did not clear the singleton, the second call would
        keep the cap-2 pool and _value would be 2, not 7.
        """
        self.assertEqual(self._get_stream_semaphore(2)._value, 2)
        self._reset_stream_semaphore()
        self.assertEqual(self._get_stream_semaphore(7)._value, 7)

    async def test_semaphore_acquire_release_roundtrip(self):
        """Acquire then release the semaphore; counter is restored (DEC-6 finally)."""
        sem = self._get_stream_semaphore(2)
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

    async def test_try_acquire_holds_slot_then_releases(self):
        """try_acquire_stream_slot returns the semaphore with a slot HELD (AC-6)."""
        sem = await self._try_acquire_stream_slot(2)
        self.assertIsNotNone(sem, "a free pool must admit (return the semaphore)")
        self.assertEqual(sem._value, 1, "an admitted request holds one slot")
        sem.release()
        self.assertEqual(sem._value, 2, "release restores the slot")

    async def test_try_acquire_returns_none_when_full(self):
        """try_acquire_stream_slot returns None (no block) when the pool is full (AC-6).

        Counter-factual: a blocking acquire would hang here instead of returning
        None — the bounded wait_for would trip.
        """
        sem = self._get_stream_semaphore(1)
        await sem.acquire()  # exhaust the only slot
        try:
            result = await asyncio.wait_for(self._try_acquire_stream_slot(1), timeout=1)
            self.assertIsNone(result, "a full pool must reject (return None)")
            self.assertEqual(sem._value, 0, "a rejected admission consumes no slot")
        finally:
            sem.release()


# ---------------------------------------------------------------------------
# TestSSEModuleScaffold — APIRouter and helper presence
# ---------------------------------------------------------------------------


class TestSSEModuleScaffold(unittest.TestCase):
    """Smoke tests that stream.py exports the expected public names.

    Verifies the module scaffold (DEC-4: per-domain router pattern):
      - `router` is an APIRouter
      - `_format_sse_event` and `_format_sse_heartbeat` are callable
      - `_to_serializable` exists (mirrors execute.py:130 pattern)
      - `_try_acquire_stream_slot` is wired (the config-sized admission seam, DEC-6)

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

    def test_concurrency_admission_seam_wired(self):
        """The config-sized admission helper must be wired into the route (DEC-6).

        The concurrency limiter moved to sse_concurrency.py (split for the 350-line
        limit); the route reaches it via _try_acquire_stream_slot.  A missing wiring
        would mean the concurrency gate could not source its config-sized semaphore.
        """
        self.assertTrue(
            hasattr(self._mod, "_try_acquire_stream_slot"),
            "stream module must wire _try_acquire_stream_slot (config-sized admission)",
        )
        self.assertTrue(callable(self._mod._try_acquire_stream_slot))


# ---------------------------------------------------------------------------
# UAT HIGH-1 — Deadline lapse AFTER the terminal yield must NOT emit a 2nd terminal
# ---------------------------------------------------------------------------


class TestSSEGeneratorNoSecondTerminalOnDeadline(unittest.IsolatedAsyncioTestCase):
    """UAT HIGH-1 (deadline branch): if the duration deadline lapses in the window
    AFTER F04's terminal event is yielded but BEFORE the next pull, the generator
    must NOT emit a second terminal (`failed`/`stream_duration_exceeded`).

    Driven at the generator entrypoint (_sse_generator) directly because the
    deadline-after-terminal window is a wall-clock race that the loop's monotonic
    clock controls; a deterministic test patches the running loop's `time()` so the
    deadline is fresh on the iteration that replays the primed terminal and lapsed
    on the (buggy) following iteration.

    COUNTER-FACTUAL: the pre-fix generator (no `return` after the replayed terminal)
    loops back, the deadline check fires, and it emits a SECOND terminal
    `failed`/`stream_duration_exceeded`. With the fix it returns after the terminal
    yield, so only the one `completed` frame is produced. (Verified: reverting the
    replay-path `return` makes this test see two terminals.)
    """

    async def test_deadline_after_primed_terminal_no_second_failed(self):
        import agentmap.deployment.http.api.routes.stream as stream_module
        from agentmap.models.execution.progress_event import WorkflowProgressEvent

        terminal = WorkflowProgressEvent(
            event_type="completed",
            sequence=0,
            is_terminal=True,
            result={"success": True, "outputs": {}},
        )

        async def _empty_upstream():
            # Exhausted upstream: the terminal arrives via the primed-replay path.
            return
            yield  # pragma: no cover (makes this an async generator)

        class _FakeRequest:
            async def is_disconnected(self) -> bool:
                return False

        loop = asyncio.get_running_loop()
        real_time = loop.time
        base = real_time()
        # Clock script: keep time at `base` until the terminal has been replayed,
        # then jump well past the (10s) cap so a buggy post-terminal loop would
        # see the deadline lapsed.  The replay path consumes the first few time()
        # reads (start, iter-1 remaining, last_event_time); only a SECOND loop
        # iteration (the bug) reads time() again — that read must be past-deadline.
        calls = {"n": 0}

        def _fake_time():
            calls["n"] += 1
            # First 3 reads (start + iter-1 remaining + last_event_time) stay at base;
            # any later read (only reached by the buggy 2nd iteration) is past cap.
            return base if calls["n"] <= 3 else base + 100.0

        loop.time = _fake_time  # type: ignore[assignment]
        try:
            gen = stream_module._sse_generator(
                upstream=_empty_upstream(),
                primed_first_event=terminal,
                primed_exhausted=False,
                graph_name="wf",
                request=_FakeRequest(),
                max_stream_duration_seconds=10.0,
                idle_timeout_seconds=1000.0,
                heartbeat_interval_seconds=1000.0,
                semaphore=None,
            )
            frames = [frame async for frame in gen]
        finally:
            loop.time = real_time  # type: ignore[assignment]

        body = "".join(frames)
        self.assertEqual(
            body.count("event: completed"),
            1,
            f"Exactly one terminal `completed` expected; got: {body!r}",
        )
        self.assertNotIn(
            "stream_duration_exceeded",
            body,
            "No duration-cap terminal may follow the F04 terminal (REQ-F-002/AC-5)",
        )
        # Total terminal frames (completed + any failed) must be exactly one.
        self.assertEqual(
            body.count("event: failed") + body.count("event: completed"),
            1,
            f"Exactly one terminal event expected; got: {body!r}",
        )


if __name__ == "__main__":
    unittest.main()
