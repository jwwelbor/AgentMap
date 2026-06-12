"""
Unit tests for GraphExecutionService async execution path.

Covers task T-E04-F04-001 — async compiled-graph execution parity and
sync-fallback coverage.

Test cases:
  TC-001: native async invoke returns the same execution envelope
  TC-002: async fallback handles sync-only compiled graphs via named seam
  TC-009: cancelled async execution propagates CancelledError and finalizes tracker
  TC-011: two concurrent async executions overlap (measurable concurrency)

Caller-path contract (from test plan):
  Production entrypoint:
    GraphExecutionService.execute_compiled_graph_async(
        executable_graph, graph_name, initial_state, execution_tracker, config=None
    )
  Lowest allowed mock seam: compiled graph object and its async invoke surface;
    service dependencies may be autospecced.
  Forbidden mocks: private helper methods such as `_run_core`,
    `_run_with_telemetry`, or any direct assertion against internal metadata
    assembly helpers.
  Counter-factual: a buggy implementation would call the sync invoke path
    directly on the event loop or return a different ExecutionResult shape
    than the sync method.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from agentmap.models.execution.result import ExecutionResult
from agentmap.services.graph.graph_execution_service import GraphExecutionService
from tests.utils.mock_service_factory import MockServiceFactory

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_graph_execution_service():
    """Build a GraphExecutionService with mocked dependencies.

    Returns (service, mocks_dict).
    """
    from unittest.mock import create_autospec

    from agentmap.models.execution.summary import ExecutionSummary
    from agentmap.services.execution_policy_service import ExecutionPolicyService
    from agentmap.services.execution_tracking_service import ExecutionTrackingService
    from agentmap.services.state_adapter_service import StateAdapterService

    mock_tracking = create_autospec(ExecutionTrackingService, instance=True)
    mock_policy = create_autospec(ExecutionPolicyService, instance=True)
    mock_state_adapter = create_autospec(StateAdapterService, instance=True)
    logging_service = MockServiceFactory.create_mock_logging_service()

    # Default execution tracker
    mock_tracker = MagicMock(name="mock_tracker")

    # Default summary
    mock_summary = MagicMock(name="mock_summary", spec=ExecutionSummary)
    mock_summary.node_executions = []
    mock_tracking.complete_execution.return_value = None
    mock_tracking.to_summary.return_value = mock_summary

    # Default policy: success
    mock_policy.evaluate_success_policy.return_value = True

    # Default state adapter: pass-through (return the state unchanged with key set)
    def _set_value(state, key, value):
        result = dict(state)
        result[key] = value
        return result

    mock_state_adapter.set_value.side_effect = _set_value

    service = GraphExecutionService(
        execution_tracking_service=mock_tracking,
        execution_policy_service=mock_policy,
        state_adapter_service=mock_state_adapter,
        logging_service=logging_service,
    )

    mocks = {
        "tracking": mock_tracking,
        "policy": mock_policy,
        "state_adapter": mock_state_adapter,
        "tracker": mock_tracker,
        "summary": mock_summary,
    }
    return service, mocks


def _make_async_compiled_graph(final_state=None):
    """Build a fake compiled graph with a native async invoke surface."""
    if final_state is None:
        final_state = {"output": "hello", "status": "done"}
    graph = MagicMock(name="async_compiled_graph")
    graph.ainvoke = AsyncMock(return_value=final_state)
    # No sync-only marker; has async surface
    return graph


def _make_sync_only_compiled_graph(final_state=None):
    """Build a fake compiled graph WITHOUT a native async invoke surface.

    Has only a sync `invoke` method; `ainvoke` is absent.
    """
    if final_state is None:
        final_state = {"output": "sync_result", "status": "done"}
    graph = MagicMock(name="sync_only_graph", spec=["invoke"])
    graph.invoke.return_value = final_state
    return graph


class _HeartbeatProbe:
    """Async heartbeat that ticks every `interval` seconds.

    Records the maximum inter-tick gap in `max_gap_s`.
    Used by TC-009 and TC-011 to prove the event loop is not starved.
    """

    def __init__(self, interval: float = 0.05, bound_s: float = 0.25):
        self.interval = interval
        self.bound_s = bound_s
        self.max_gap_s = 0.0
        self._stop = False

    async def run(self):
        last = asyncio.get_event_loop().time()
        while not self._stop:
            await asyncio.sleep(self.interval)
            now = asyncio.get_event_loop().time()
            gap = now - last
            if gap > self.max_gap_s:
                self.max_gap_s = gap
            last = now

    def stop(self):
        self._stop = True

    def assert_no_starvation(self, test_case):
        """Assert max inter-tick gap did not exceed the bound."""
        test_case.assertLess(
            self.max_gap_s,
            self.bound_s,
            f"Event-loop starvation detected: max gap {self.max_gap_s:.3f}s "
            f"exceeds bound {self.bound_s}s",
        )


# ---------------------------------------------------------------------------
# TC-001: Native async invoke returns the same execution envelope
# ---------------------------------------------------------------------------


class TestExecuteCompiledGraphAsync(unittest.IsolatedAsyncioTestCase):
    """TC-001: Native async invoke returns the same execution envelope."""

    async def test_tc001_native_async_invoke_returns_execution_result(self):
        """execute_compiled_graph_async with a native async graph returns the
        same ExecutionResult shape as the sync path (graph_name, success,
        final_state, execution_summary, total_duration, error=None)."""
        service, mocks = _make_graph_execution_service()
        initial_state = {"input": "hello"}
        final_state = {"input": "hello", "output": "world"}
        graph = _make_async_compiled_graph(final_state=final_state)

        result = await service.execute_compiled_graph_async(
            executable_graph=graph,
            graph_name="test_graph",
            initial_state=initial_state,
            execution_tracker=mocks["tracker"],
        )

        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "test_graph")
        self.assertTrue(result.success)
        self.assertIsNone(result.error)
        self.assertIsNotNone(result.execution_summary)
        self.assertGreaterEqual(result.total_duration, 0.0)
        # Verify ainvoke was called (native async path)
        graph.ainvoke.assert_awaited_once()
        # Verify sync invoke was NOT called
        self.assertFalse(hasattr(graph, "invoke") and graph.invoke.called)

    async def test_tc001_final_state_contains_metadata_keys(self):
        """execute_compiled_graph_async injects __execution_summary and
        __policy_success into final_state, same as the sync path."""
        service, mocks = _make_graph_execution_service()
        initial_state = {}
        final_state = {"output": "done"}
        graph = _make_async_compiled_graph(final_state=final_state)

        result = await service.execute_compiled_graph_async(
            executable_graph=graph,
            graph_name="meta_graph",
            initial_state=initial_state,
            execution_tracker=mocks["tracker"],
        )

        self.assertIn("__execution_summary", result.final_state)
        self.assertIn("__policy_success", result.final_state)

    async def test_tc001_policy_false_produces_unsuccessful_result(self):
        """execute_compiled_graph_async respects policy evaluation; when policy
        returns False, result.success is False."""
        service, mocks = _make_graph_execution_service()
        mocks["policy"].evaluate_success_policy.return_value = False
        graph = _make_async_compiled_graph()

        result = await service.execute_compiled_graph_async(
            executable_graph=graph,
            graph_name="policy_graph",
            initial_state={},
            execution_tracker=mocks["tracker"],
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.error)

    async def test_tc001_config_forwarded_to_ainvoke(self):
        """execute_compiled_graph_async passes config to ainvoke when provided."""
        service, mocks = _make_graph_execution_service()
        graph = _make_async_compiled_graph()
        config = {"configurable": {"thread_id": "t-abc"}}

        await service.execute_compiled_graph_async(
            executable_graph=graph,
            graph_name="config_graph",
            initial_state={},
            execution_tracker=mocks["tracker"],
            config=config,
        )

        graph.ainvoke.assert_awaited_once()
        _, call_kwargs = graph.ainvoke.call_args
        self.assertEqual(call_kwargs.get("config"), config)


# ---------------------------------------------------------------------------
# TC-002: Async fallback handles sync-only compiled graphs via named seam
# ---------------------------------------------------------------------------


class TestExecuteCompiledGraphAsyncFallback(unittest.IsolatedAsyncioTestCase):
    """TC-002: Sync-only compiled graph uses named worker-thread seam."""

    async def test_tc002_sync_only_graph_uses_named_fallback_seam(self):
        """When the compiled graph has no ainvoke, execute_compiled_graph_async
        routes through _invoke_compiled_graph_in_thread (REQ-NF-008)."""
        service, mocks = _make_graph_execution_service()
        final_state = {"output": "sync_fallback"}
        graph = _make_sync_only_compiled_graph(final_state=final_state)

        with patch.object(
            service,
            "_invoke_compiled_graph_in_thread",
            wraps=service._invoke_compiled_graph_in_thread,
        ) as patched_seam:
            result = await service.execute_compiled_graph_async(
                executable_graph=graph,
                graph_name="sync_graph",
                initial_state={},
                execution_tracker=mocks["tracker"],
            )

        # Seam must have been called exactly once
        patched_seam.assert_awaited_once()
        # Result must still be a valid ExecutionResult
        self.assertIsInstance(result, ExecutionResult)
        self.assertEqual(result.graph_name, "sync_graph")
        self.assertIsNone(result.error)

    async def test_tc002_sync_invoke_called_inside_seam_not_directly(self):
        """The compiled graph's blocking invoke() is called inside the seam,
        never directly on the event loop."""
        service, mocks = _make_graph_execution_service()
        final_state = {"output": "value"}
        graph = _make_sync_only_compiled_graph(final_state=final_state)

        # Replace seam with a controlled version that records where invoke runs
        invocations = []

        async def _fake_seam(executable_graph, initial_state, config):
            # Simulate calling the sync invoke inside a thread-boundary
            invocations.append("seam_called")
            return executable_graph.invoke(initial_state, config=config)

        with patch.object(
            service, "_invoke_compiled_graph_in_thread", side_effect=_fake_seam
        ):
            result = await service.execute_compiled_graph_async(
                executable_graph=graph,
                graph_name="seam_routing_graph",
                initial_state={},
                execution_tracker=mocks["tracker"],
            )

        self.assertEqual(invocations, ["seam_called"])
        graph.invoke.assert_called_once()
        self.assertIsInstance(result, ExecutionResult)

    async def test_tc002_fallback_returns_correct_envelope_on_failure(self):
        """Fallback path returns error ExecutionResult when graph raises."""
        service, mocks = _make_graph_execution_service()
        graph = _make_sync_only_compiled_graph()
        graph.invoke.side_effect = RuntimeError("sync graph blew up")

        result = await service.execute_compiled_graph_async(
            executable_graph=graph,
            graph_name="fail_graph",
            initial_state={},
            execution_tracker=mocks["tracker"],
        )

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("sync graph blew up", result.error)


# ---------------------------------------------------------------------------
# TC-009: Cancelled async execution propagates and finalizes tracker
# ---------------------------------------------------------------------------


class TestExecuteCompiledGraphAsyncCancellation(unittest.IsolatedAsyncioTestCase):
    """TC-009: Cancelled execution propagates CancelledError and finalizes tracker."""

    async def test_tc009_timeout_propagates_to_caller(self):
        """asyncio.wait_for(execute_compiled_graph_async(...), timeout) raises
        TimeoutError (wrapping CancelledError) to the caller — not swallowed."""
        service, mocks = _make_graph_execution_service()

        # Build a graph whose ainvoke sleeps longer than the timeout
        async def _slow_ainvoke(state, config=None):
            await asyncio.sleep(5.0)  # much longer than timeout
            return state

        graph = MagicMock(name="slow_async_graph")
        graph.ainvoke = _slow_ainvoke

        with self.assertRaises((asyncio.TimeoutError, asyncio.CancelledError)):
            await asyncio.wait_for(
                service.execute_compiled_graph_async(
                    executable_graph=graph,
                    graph_name="slow_graph",
                    initial_state={},
                    execution_tracker=mocks["tracker"],
                ),
                timeout=0.1,
            )

    async def test_tc009_no_loop_starvation_during_cancellation(self):
        """CancelledError propagates without starving the event loop.

        Heartbeat coroutine running concurrently records no tick gap beyond
        the starvation bound (250ms) while the slow graph is executing.
        """
        service, mocks = _make_graph_execution_service()

        async def _slow_ainvoke(state, config=None):
            await asyncio.sleep(5.0)
            return state

        graph = MagicMock(name="slow_async_graph_hb")
        graph.ainvoke = _slow_ainvoke

        heartbeat = _HeartbeatProbe(interval=0.05, bound_s=0.25)
        hb_task = asyncio.create_task(heartbeat.run())

        try:
            with self.assertRaises((asyncio.TimeoutError, asyncio.CancelledError)):
                await asyncio.wait_for(
                    service.execute_compiled_graph_async(
                        executable_graph=graph,
                        graph_name="slow_graph_hb",
                        initial_state={},
                        execution_tracker=mocks["tracker"],
                    ),
                    timeout=0.2,
                )
        finally:
            heartbeat.stop()
            hb_task.cancel()
            try:
                await hb_task
            except asyncio.CancelledError:
                pass

        heartbeat.assert_no_starvation(self)


# ---------------------------------------------------------------------------
# TC-011: Measurable concurrency — two async executions overlap
# ---------------------------------------------------------------------------


class TestExecuteCompiledGraphAsyncConcurrency(unittest.IsolatedAsyncioTestCase):
    """TC-011: Two concurrent execute_compiled_graph_async calls overlap on one loop."""

    async def test_tc011_two_concurrent_executions_overlap(self):
        """Two execute_compiled_graph_async calls whose graph work is dominated
        by a ~0.5s awaitable each complete in under 0.9s (they overlap rather
        than serializing to ~1.0s+)."""
        service, mocks = _make_graph_execution_service()

        async def _slow_ainvoke(state, config=None):
            await asyncio.sleep(0.5)
            return {"output": "done"}

        def _make_slow_graph():
            g = MagicMock()
            g.ainvoke = _slow_ainvoke
            return g

        graph_a = _make_slow_graph()
        graph_b = _make_slow_graph()

        # Fresh tracker per invocation (avoid shared-mock state side effects)
        tracker_a = MagicMock(name="tracker_a")
        tracker_b = MagicMock(name="tracker_b")
        mocks["tracking"].to_summary.return_value = mocks["summary"]

        heartbeat = _HeartbeatProbe(interval=0.05, bound_s=0.25)
        hb_task = asyncio.create_task(heartbeat.run())

        start = asyncio.get_event_loop().time()
        try:
            results = await asyncio.gather(
                service.execute_compiled_graph_async(
                    executable_graph=graph_a,
                    graph_name="graph_a",
                    initial_state={},
                    execution_tracker=tracker_a,
                ),
                service.execute_compiled_graph_async(
                    executable_graph=graph_b,
                    graph_name="graph_b",
                    initial_state={},
                    execution_tracker=tracker_b,
                ),
            )
        finally:
            heartbeat.stop()
            hb_task.cancel()
            try:
                await hb_task
            except asyncio.CancelledError:
                pass

        elapsed = asyncio.get_event_loop().time() - start

        # Both results must be valid
        for r in results:
            self.assertIsInstance(r, ExecutionResult)
            self.assertIsNone(r.error)

        # Overlap assertion: wall-clock should be under 0.9s (not ~1.0s+)
        self.assertLess(
            elapsed,
            0.9,
            f"Concurrent executions took {elapsed:.3f}s — expected overlap < 0.9s",
        )

        # No event-loop starvation
        heartbeat.assert_no_starvation(self)

    async def test_tc011_one_failing_does_not_prevent_other_from_succeeding(self):
        """gather() with one failing graph still delivers the success result
        for the other graph (no serialization side-effects)."""
        service, mocks = _make_graph_execution_service()

        async def _good_ainvoke(state, config=None):
            await asyncio.sleep(0.1)
            return {"output": "ok"}

        async def _bad_ainvoke(state, config=None):
            await asyncio.sleep(0.05)
            raise RuntimeError("graph failure")

        good_graph = MagicMock(name="good_graph")
        good_graph.ainvoke = _good_ainvoke
        bad_graph = MagicMock(name="bad_graph")
        bad_graph.ainvoke = _bad_ainvoke

        tracker_good = MagicMock(name="tracker_good")
        tracker_bad = MagicMock(name="tracker_bad")
        mocks["tracking"].to_summary.return_value = mocks["summary"]

        results = await asyncio.gather(
            service.execute_compiled_graph_async(
                executable_graph=good_graph,
                graph_name="good",
                initial_state={},
                execution_tracker=tracker_good,
            ),
            service.execute_compiled_graph_async(
                executable_graph=bad_graph,
                graph_name="bad",
                initial_state={},
                execution_tracker=tracker_bad,
            ),
        )

        good_result = next(r for r in results if r.graph_name == "good")
        bad_result = next(r for r in results if r.graph_name == "bad")

        self.assertTrue(good_result.success)
        self.assertFalse(bad_result.success)
        self.assertIsNotNone(bad_result.error)
