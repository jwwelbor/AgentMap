"""
Unit tests for async workflow facade migration: T-E04-F04-004

Verifies that run_workflow_async and resume_workflow_async directly await
GraphRunnerService.run_async / resume_from_checkpoint_async rather than
wrapping the sync facade in asyncio.to_thread.

Acceptance criteria tested:
- No asyncio.to_thread wraps the graph-invocation path in the async facade.
- A heartbeat test that would fail under blocking execution passes for the
  async path.
- Facade response envelopes unchanged vs. E04-F03 (regression suite green).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentmap.models.execution.result import ExecutionResult
from agentmap.models.execution.summary import ExecutionSummary
from agentmap.runtime.workflow_ops import (
    resume_workflow_async,
    run_workflow_async,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_execution_result(graph_name="test_graph", success=True, error=None):
    """Build a minimal ExecutionResult for testing."""
    return ExecutionResult(
        graph_name=graph_name,
        final_state={"result": "done", "output": "test_output"},
        execution_summary=ExecutionSummary(graph_name=graph_name),
        success=success,
        total_duration=0.1,
        error=error,
    )


def _make_interrupted_result(thread_id="thread-interrupt-001"):
    """Build an ExecutionResult that looks like a LangGraph interrupt."""
    return ExecutionResult(
        graph_name="test_graph",
        final_state={
            "__interrupted": True,
            "__thread_id": thread_id,
            "__interrupt_info": {"type": "human", "node_name": "approve_node"},
        },
        execution_summary=None,
        success=False,
        total_duration=0.1,
    )


def _make_mock_container(run_result, bundle=None):
    """Build a mock DI container that can service run_workflow_async."""
    if bundle is None:
        bundle = MagicMock()
        bundle.graph_name = "test_graph"
        bundle.nodes = {}

    container = MagicMock()

    # app_config_service
    app_config = MagicMock()
    csv_repo = MagicMock()
    csv_repo.__truediv__ = lambda self, x: MagicMock(exists=lambda: False)
    app_config.get_csv_repository_path.return_value = csv_repo
    container.app_config_service.return_value = app_config

    # logging_service
    logging_service = MagicMock()
    logger = MagicMock()
    logging_service.get_logger.return_value = logger
    container.logging_service.return_value = logging_service

    # graph_bundle_service
    graph_bundle_service = MagicMock()
    graph_bundle_service.get_or_create_bundle.return_value = (bundle, True)
    container.graph_bundle_service.return_value = graph_bundle_service

    # graph_runner_service — the key async mock
    graph_runner = MagicMock()
    graph_runner.run_async = AsyncMock(return_value=run_result)
    container.graph_runner_service.return_value = graph_runner

    return container, graph_runner


def _make_mock_container_for_resume(resume_result):
    """Build a mock DI container for resume_workflow_async."""
    container = MagicMock()

    # interaction_handler
    interaction_handler = MagicMock()
    thread_data = {
        "graph_name": "test_graph",
        "bundle_info": {"csv_path": "/fake/path.csv"},
        "checkpoint_data": {"state": "paused"},
        "pending_interaction_id": None,  # SuspendAgent path
        "node_name": "resume_node",
    }
    interaction_handler.get_thread_metadata.return_value = thread_data
    interaction_handler.mark_thread_resuming.return_value = True
    container.interaction_handler_service.return_value = interaction_handler

    # graph_bundle_service
    bundle = MagicMock()
    bundle.graph_name = "test_graph"
    graph_bundle_service = MagicMock()
    graph_bundle_service.get_or_create_bundle.return_value = (bundle, False)
    container.graph_bundle_service.return_value = graph_bundle_service

    # graph_runner_service — the key async mock
    graph_runner = MagicMock()
    graph_runner.resume_from_checkpoint_async = AsyncMock(return_value=resume_result)
    container.graph_runner_service.return_value = graph_runner

    return container, graph_runner, bundle


# ---------------------------------------------------------------------------
# TC-F04-004-001: run_workflow_async uses native run_async, not to_thread
# ---------------------------------------------------------------------------


class TestRunWorkflowAsyncUsesNativeRunner:
    """AC: run_workflow_async awaits graph_runner.run_async directly."""

    @pytest.mark.asyncio
    async def test_run_workflow_async_calls_run_async_not_to_thread(self):
        """Counter-factual: if to_thread were still used, run_async would never be awaited."""
        run_result = _make_execution_result(success=True)
        container, graph_runner = _make_mock_container(run_result)

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
            patch(
                "agentmap.runtime.workflow_ops._resolve_csv_path",
                return_value=(MagicMock(), "test_graph"),
            ),
        ):
            result = await run_workflow_async("test_graph", {"input": "value"})

        # The native async runner must have been awaited
        graph_runner.run_async.assert_awaited_once()

        # Result envelope must match the sync facade contract
        assert result["success"] is True
        assert "outputs" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_run_workflow_async_response_envelope_matches_sync(self):
        """Regression: response envelope shape is identical to run_workflow sync contract."""
        run_result = _make_execution_result(success=True)
        container, graph_runner = _make_mock_container(run_result)

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
            patch(
                "agentmap.runtime.workflow_ops._resolve_csv_path",
                return_value=(MagicMock(), "test_graph"),
            ),
        ):
            result = await run_workflow_async(
                "test_graph", {"input": "value"}, profile="dev"
            )

        # Envelope fields required by sync contract
        assert result["success"] is True
        assert result["outputs"] == run_result.final_state
        assert "execution_id" in result
        assert "execution_summary" in result
        assert result["metadata"]["graph_name"] == "test_graph"
        assert result["metadata"]["profile"] == "dev"

    @pytest.mark.asyncio
    async def test_run_workflow_async_handles_graph_interrupt(self):
        """Interrupt scenario: interrupted result maps to the expected interrupt envelope."""
        thread_id = "thread-interrupt-001"
        run_result = _make_interrupted_result(thread_id=thread_id)
        container, graph_runner = _make_mock_container(run_result)

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
            patch(
                "agentmap.runtime.workflow_ops._resolve_csv_path",
                return_value=(MagicMock(), "test_graph"),
            ),
        ):
            result = await run_workflow_async("test_graph", {})

        # The async path must produce the same interrupt envelope as the sync path
        assert result["success"] is False
        assert result["interrupted"] is True
        assert result["thread_id"] == thread_id
        assert "interrupt_info" in result
        graph_runner.run_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_workflow_async_forwards_force_create(self):
        """force_create is forwarded to get_or_create_bundle."""
        run_result = _make_execution_result(success=True)
        container, graph_runner = _make_mock_container(run_result)

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
            patch(
                "agentmap.runtime.workflow_ops._resolve_csv_path",
                return_value=(MagicMock(), "test_graph"),
            ),
        ):
            await run_workflow_async("test_graph", {}, force_create=True)

        # get_or_create_bundle must see force_create=True
        call_kwargs = container.graph_bundle_service().get_or_create_bundle.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("force_create") is True

    @pytest.mark.asyncio
    async def test_run_workflow_async_passes_validate_agents_for_new_bundle(self):
        """validate_agents=True is forwarded to run_async when it's a new bundle."""
        run_result = _make_execution_result(success=True)
        container, graph_runner = _make_mock_container(run_result)
        # new_bundle=True triggers validate_agents=True
        container.graph_bundle_service().get_or_create_bundle.return_value = (
            MagicMock(),
            True,  # new_bundle
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
            patch(
                "agentmap.runtime.workflow_ops._resolve_csv_path",
                return_value=(MagicMock(), "test_graph"),
            ),
        ):
            await run_workflow_async("test_graph", {})

        # run_async must have been called with validate_agents=True
        call_kwargs = graph_runner.run_async.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("validate_agents") is True


# ---------------------------------------------------------------------------
# TC-F04-004-002: run_workflow_async does NOT use asyncio.to_thread for graph
# ---------------------------------------------------------------------------


class TestRunWorkflowAsyncNoToThread:
    """AC: no asyncio.to_thread remains around the graph-invocation path."""

    @pytest.mark.asyncio
    async def test_run_workflow_async_no_to_thread_on_graph_invocation(self):
        """
        Counter-factual: if to_thread were still the implementation, patching
        asyncio.to_thread to raise would cause this test to fail.  Now that
        run_async is called natively, to_thread must NOT be triggered for the
        graph invocation path.
        """
        run_result = _make_execution_result(success=True)
        container, graph_runner = _make_mock_container(run_result)

        # If to_thread is called on the graph path this will record the call
        to_thread_calls = []

        async def _spy_to_thread(func, *args, **kwargs):
            # Allow to_thread only for non-graph-invocation work (if any)
            to_thread_calls.append(func)
            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: func(*args, **kwargs)
            )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
            patch(
                "agentmap.runtime.workflow_ops._resolve_csv_path",
                return_value=(MagicMock(), "test_graph"),
            ),
            patch("agentmap.runtime.workflow_ops.asyncio.to_thread", _spy_to_thread),
        ):
            result = await run_workflow_async("test_graph", {})

        # run_async must have been awaited (native async path)
        graph_runner.run_async.assert_awaited_once()

        # to_thread must NOT have been called with the sync run_workflow function
        from agentmap.runtime.workflow_ops import run_workflow

        assert run_workflow not in to_thread_calls, (
            "run_workflow_async is still routing through asyncio.to_thread(run_workflow) — "
            "the graph-invocation path has not been migrated to native async."
        )

        assert result["success"] is True


# ---------------------------------------------------------------------------
# TC-F04-004-003: Heartbeat test — event loop not blocked by async facade
# ---------------------------------------------------------------------------


class TestRunWorkflowAsyncHeartbeat:
    """AC: heartbeat/ticker test that would fail under blocking execution passes."""

    @pytest.mark.asyncio
    async def test_event_loop_heartbeat_not_blocked_during_run_workflow_async(self):
        """
        A 100ms awaitable graph run must not block a 20ms heartbeat ticker.
        Under the old to_thread shim this would also pass (thread does not block
        the loop), but if someone re-introduced a blocking call inline the heartbeat
        gap would exceed the 200ms bound.
        """
        heartbeat_gaps = []
        heartbeat_running = True
        last_tick = asyncio.get_event_loop().time()

        async def _heartbeat():
            nonlocal last_tick
            while heartbeat_running:
                await asyncio.sleep(0.02)  # 20ms tick
                now = asyncio.get_event_loop().time()
                heartbeat_gaps.append(now - last_tick)
                last_tick = now

        async def _slow_run_async(*args, **kwargs):
            # Simulate a 100ms awaitable graph run
            await asyncio.sleep(0.1)
            return _make_execution_result(success=True)

        container = MagicMock()
        app_config = MagicMock()
        csv_repo = MagicMock()
        csv_repo.__truediv__ = lambda self, x: MagicMock(exists=lambda: False)
        app_config.get_csv_repository_path.return_value = csv_repo
        container.app_config_service.return_value = app_config

        logging_service = MagicMock()
        logging_service.get_logger.return_value = MagicMock()
        container.logging_service.return_value = logging_service

        bundle = MagicMock()
        bundle.graph_name = "test_graph"
        graph_bundle_service = MagicMock()
        graph_bundle_service.get_or_create_bundle.return_value = (bundle, False)
        container.graph_bundle_service.return_value = graph_bundle_service

        graph_runner = MagicMock()
        graph_runner.run_async = _slow_run_async
        container.graph_runner_service.return_value = graph_runner

        hb_task = asyncio.ensure_future(_heartbeat())

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
            patch(
                "agentmap.runtime.workflow_ops._resolve_csv_path",
                return_value=(MagicMock(), "test_graph"),
            ),
        ):
            result = await run_workflow_async("test_graph", {})

        heartbeat_running = False
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass

        assert result["success"] is True

        # Max inter-tick gap must be under 200ms (4x the 20ms tick interval)
        # This would exceed the bound if blocking code ran inline on the loop
        if heartbeat_gaps:
            max_gap = max(heartbeat_gaps)
            assert max_gap < 0.2, (
                f"Heartbeat gap {max_gap:.3f}s exceeded 200ms — "
                "the async facade may be blocking the event loop."
            )


# ---------------------------------------------------------------------------
# TC-F04-004-004: resume_workflow_async uses native resume_from_checkpoint_async
# ---------------------------------------------------------------------------


class TestResumeWorkflowAsyncUsesNativeRunner:
    """AC: resume_workflow_async awaits graph_runner.resume_from_checkpoint_async."""

    @pytest.mark.asyncio
    async def test_resume_workflow_async_calls_resume_from_checkpoint_async(self):
        """Counter-factual: if to_thread were still used, resume_from_checkpoint_async would never be awaited."""
        import json

        resume_result = _make_execution_result(graph_name="test_graph", success=True)
        container, graph_runner, bundle = _make_mock_container_for_resume(resume_result)

        resume_token = json.dumps(
            {"thread_id": "thread-resume-001", "response_action": "continue"}
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            (
                patch(
                    "agentmap.runtime.workflow_ops._resume_workflow_async_core",
                    wraps=None,
                )
                if False
                else _noop_context()
            ),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
        ):
            result = await resume_workflow_async(resume_token)

        # The async resume must have been called
        graph_runner.resume_from_checkpoint_async.assert_awaited_once()

        # Result envelope must match the sync contract
        assert result["success"] is True
        assert "outputs" in result
        assert "metadata" in result

    @pytest.mark.asyncio
    async def test_resume_workflow_async_response_envelope_matches_sync(self):
        """Regression: resume envelope shape identical to resume_workflow sync contract."""
        import json

        resume_result = _make_execution_result(graph_name="resume_graph", success=True)
        resume_result.graph_name = "resume_graph"
        container, graph_runner, bundle = _make_mock_container_for_resume(resume_result)

        resume_token = json.dumps(
            {"thread_id": "thread-resume-002", "response_action": "approve"}
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
        ):
            result = await resume_workflow_async(resume_token, profile="staging")

        # All envelope fields from the sync facade must be present
        assert result["success"] is True
        assert "outputs" in result
        assert "execution_summary" in result
        assert "metadata" in result
        assert result["metadata"]["thread_id"] == "thread-resume-002"
        assert result["metadata"]["profile"] == "staging"

    @pytest.mark.asyncio
    async def test_resume_workflow_async_no_to_thread_on_graph_invocation(self):
        """AC: asyncio.to_thread must not wrap the resume graph-invocation path."""
        import json

        resume_result = _make_execution_result(graph_name="test_graph", success=True)
        container, graph_runner, bundle = _make_mock_container_for_resume(resume_result)

        to_thread_calls = []

        async def _spy_to_thread(func, *args, **kwargs):
            to_thread_calls.append(func)
            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: func(*args, **kwargs)
            )

        resume_token = json.dumps(
            {"thread_id": "thread-resume-003", "response_action": "continue"}
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
            patch("agentmap.runtime.workflow_ops.asyncio.to_thread", _spy_to_thread),
        ):
            result = await resume_workflow_async(resume_token)

        graph_runner.resume_from_checkpoint_async.assert_awaited_once()

        from agentmap.runtime.workflow_ops import resume_workflow

        assert resume_workflow not in to_thread_calls, (
            "resume_workflow_async is still routing through asyncio.to_thread(resume_workflow) — "
            "the graph-invocation path has not been migrated to native async."
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_resume_workflow_async_human_response_path(self):
        """Human-response (HumanAgent) path: pending_interaction_id triggers response saving."""
        import json
        from uuid import uuid4

        resume_result = _make_execution_result(graph_name="test_graph", success=True)
        container, graph_runner, bundle = _make_mock_container_for_resume(resume_result)

        # Override interaction handler to simulate human-interaction pending
        request_id = str(uuid4())
        interaction_handler = container.interaction_handler_service()
        thread_data = {
            "graph_name": "test_graph",
            "bundle_info": {"csv_path": "/fake/path.csv"},
            "checkpoint_data": {"state": "paused"},
            "pending_interaction_id": request_id,  # HumanAgent path
            "node_name": "approve_node",
        }
        interaction_handler.get_thread_metadata.return_value = thread_data
        interaction_handler.save_interaction_response.return_value = True
        interaction_handler.mark_thread_resuming.return_value = True

        resume_token = json.dumps(
            {
                "thread_id": "thread-human-001",
                "response_action": "approve",
                "response_data": {"reason": "looks good"},
            }
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
        ):
            result = await resume_workflow_async(resume_token)

        # resume_from_checkpoint_async must still be called for human-response path
        graph_runner.resume_from_checkpoint_async.assert_awaited_once()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_resume_workflow_async_error_produces_error_envelope(self):
        """Error path: exception in resume produces error envelope like sync facade."""
        import json

        container = MagicMock()

        # interaction_handler raises
        interaction_handler = MagicMock()
        interaction_handler.get_thread_metadata.return_value = None  # Thread not found
        container.interaction_handler_service.return_value = interaction_handler

        resume_token = json.dumps(
            {"thread_id": "thread-missing-999", "response_action": "continue"}
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
        ):
            result = await resume_workflow_async(resume_token)

        # Error path must produce the same error envelope as the sync facade
        assert result["success"] is False
        assert "error" in result
        assert "metadata" in result
        assert result["metadata"]["resume_token"] == resume_token


# ---------------------------------------------------------------------------
# TC-F04-004-005: B-1 cancellation window — thread must not be wedged
# ---------------------------------------------------------------------------


class TestResumeWorkflowAsyncCancelledErrorNotWedged:
    """AC-008 — B-1 fix: CancelledError at ANY point during resume leaves
    the thread re-resumable (never wedged in `resuming`).

    Counter-factual: without the fix, a CancelledError raised BEFORE the
    checkpoint manager sets its own `marked_resuming` flag is never caught by
    the facade's ``except Exception`` handler (CancelledError is not an
    Exception subclass in Python 3.8+), so the thread stays in `resuming` and
    a subsequent resume call cannot proceed.
    """

    def _make_resume_container(self, graph_runner):
        """Build a minimal DI container wired for resume_workflow_async."""
        container = MagicMock()

        interaction_handler = MagicMock()
        thread_data = {
            "graph_name": "test_graph",
            "bundle_info": {"csv_path": "/fake/path.csv"},
            "checkpoint_data": {"state": "paused"},
            "pending_interaction_id": None,  # SuspendAgent path
            "node_name": "resume_node",
        }
        interaction_handler.get_thread_metadata.return_value = thread_data
        interaction_handler.mark_thread_resuming.return_value = True
        interaction_handler.unmark_thread_resuming.return_value = True
        container.interaction_handler_service.return_value = interaction_handler

        bundle = MagicMock()
        bundle.graph_name = "test_graph"
        graph_bundle_service = MagicMock()
        graph_bundle_service.get_or_create_bundle.return_value = (bundle, False)
        container.graph_bundle_service.return_value = graph_bundle_service

        container.graph_runner_service.return_value = graph_runner

        return container, interaction_handler

    @pytest.mark.asyncio
    async def test_cancelled_error_in_pre_manager_window_unmarks_thread(self):
        """CancelledError raised by resume_from_checkpoint_async must not leave
        the thread wedged in `resuming`.

        Counter-factual: before the fix, the facade only had ``except Exception``
        which does not catch CancelledError, so the thread stayed in `resuming`
        and a subsequent resume would fail.

        The test drives ``resume_workflow_async`` at the production caller
        signature, injects a CancelledError from the delegate, and asserts that:
        1. CancelledError propagates out of the facade (re-raised, not swallowed).
        2. ``unmark_thread_resuming`` is called exactly once — the facade-level
           mark made before the delegate is undone.
        """
        import json

        # Make resume_from_checkpoint_async raise CancelledError
        # (simulating cancellation in the pre-manager-mark window)
        graph_runner = MagicMock()
        graph_runner.resume_from_checkpoint_async = AsyncMock(
            side_effect=asyncio.CancelledError("cancelled in pre-mark window")
        )

        container, interaction_handler = self._make_resume_container(graph_runner)

        resume_token = json.dumps(
            {"thread_id": "thread-cancel-001", "response_action": "continue"}
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
        ):
            with pytest.raises(asyncio.CancelledError):
                await resume_workflow_async(resume_token)

        # The facade must have attempted to unmark the thread it marked
        interaction_handler.unmark_thread_resuming.assert_called_once_with(
            thread_id="thread-cancel-001"
        )

    @pytest.mark.asyncio
    async def test_second_resume_succeeds_after_first_is_cancelled(self):
        """After a cancelled resume, a subsequent resume must succeed.

        This is the AC-008 liveness proof: the thread is never permanently
        wedged in `resuming`.

        Counter-factual: without the fix the second resume_workflow_async call
        would either fail validation (thread in wrong state) or return an error
        envelope instead of success.
        """
        import json

        cancel_error = asyncio.CancelledError("first attempt cancelled")

        call_count = 0
        resume_result = _make_execution_result(graph_name="test_graph", success=True)

        async def _resume_once_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise cancel_error
            return resume_result

        graph_runner = MagicMock()
        graph_runner.resume_from_checkpoint_async = _resume_once_then_succeed

        container, interaction_handler = self._make_resume_container(graph_runner)

        resume_token = json.dumps(
            {"thread_id": "thread-cancel-002", "response_action": "continue"}
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
        ):
            # First attempt — cancelled
            with pytest.raises(asyncio.CancelledError):
                await resume_workflow_async(resume_token)

            # Second attempt — must succeed
            result = await resume_workflow_async(resume_token)

        assert result["success"] is True, (
            "Second resume failed after first was cancelled — "
            "thread may have been wedged in `resuming`"
        )

    @pytest.mark.asyncio
    async def test_cancelled_error_is_not_swallowed_as_error_envelope(self):
        """CancelledError must propagate (re-raised), never converted to an
        error envelope by ``except Exception``.

        Counter-factual: the old code had only ``except Exception`` at the
        bottom of the function; adding a bare ``except BaseException`` that
        returns an error dict would be wrong — cancellation must propagate so
        asyncio can honour it.
        """
        import json

        graph_runner = MagicMock()
        graph_runner.resume_from_checkpoint_async = AsyncMock(
            side_effect=asyncio.CancelledError("must propagate")
        )

        container, interaction_handler = self._make_resume_container(graph_runner)

        resume_token = json.dumps(
            {"thread_id": "thread-cancel-003", "response_action": "continue"}
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
        ):
            result_or_raise = None
            try:
                result_or_raise = await resume_workflow_async(resume_token)
            except asyncio.CancelledError:
                result_or_raise = "RAISED_AS_EXPECTED"

        assert result_or_raise == "RAISED_AS_EXPECTED", (
            "resume_workflow_async swallowed CancelledError instead of re-raising it. "
            "Cancellation must propagate so asyncio task machinery works correctly."
        )


# ---------------------------------------------------------------------------
# TC-F04-004-006: sync facade methods remain callable (regression gate)
# ---------------------------------------------------------------------------


class TestSyncFacadeRemainsAvailable:
    """AC: sync methods remain as compatibility shims after async migration."""

    def test_run_workflow_sync_callable(self):
        from agentmap.runtime.workflow_ops import run_workflow

        assert callable(run_workflow)

    def test_resume_workflow_sync_callable(self):
        from agentmap.runtime.workflow_ops import resume_workflow

        assert callable(resume_workflow)

    def test_list_graphs_sync_callable(self):
        from agentmap.runtime.workflow_ops import list_graphs

        assert callable(list_graphs)

    def test_inspect_graph_sync_callable(self):
        from agentmap.runtime.workflow_ops import inspect_graph

        assert callable(inspect_graph)

    def test_validate_workflow_sync_callable(self):
        from agentmap.runtime.workflow_ops import validate_workflow

        assert callable(validate_workflow)

    def test_all_async_siblings_callable(self):
        from agentmap.runtime.workflow_ops import (
            inspect_graph_async,
            list_graphs_async,
            resume_workflow_async,
            run_workflow_async,
            validate_workflow_async,
        )

        for fn in (
            run_workflow_async,
            resume_workflow_async,
            list_graphs_async,
            inspect_graph_async,
            validate_workflow_async,
        ):
            assert callable(fn)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _noop_context:
    """No-op context manager placeholder."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# TC-F04-004-007: B-3 — facade must not race with manager's deferred unmark
# ---------------------------------------------------------------------------


class TestResumeWorkflowAsyncB3FacadeDefersUnmarkToManager:
    """UAT B-3 fix: facade CancelledError handler must not call unmark_thread_resuming
    when the manager has already claimed ownership via _cancel_unmark_claimed.

    Background (B-3): T-E04-F04-006 introduced a deferred-unmark background task
    in the to_thread path of resume_from_checkpoint_async.  The manager only calls
    unmark AFTER the OS worker thread settles.  If the facade's CancelledError
    handler also calls unmark (when _facade_marked=True), the two paths race.
    The fix: the manager sets a threading.Event (_cancel_unmark_claimed) immediately
    after its own mark_thread_resuming(), signalling to the facade that it must
    not touch unmark.

    Counter-factual: without the fix, unmark_thread_resuming would be called by
    the facade even when the manager has claimed ownership, causing a double-unmark
    (or a race against the deferred background task).
    """

    def _make_resume_container_b3(self, graph_runner):
        """Build a minimal DI container wired for the B-3 cancel scenario."""
        container = MagicMock()

        interaction_handler = MagicMock()
        thread_data = {
            "graph_name": "test_graph",
            "bundle_info": {"csv_path": "/fake/path.csv"},
            "checkpoint_data": {"state": "paused"},
            "pending_interaction_id": None,
            "node_name": "resume_node",
        }
        interaction_handler.get_thread_metadata.return_value = thread_data
        interaction_handler.mark_thread_resuming.return_value = True
        interaction_handler.unmark_thread_resuming.return_value = True
        container.interaction_handler_service.return_value = interaction_handler

        bundle = MagicMock()
        bundle.graph_name = "test_graph"
        graph_bundle_service = MagicMock()
        graph_bundle_service.get_or_create_bundle.return_value = (bundle, False)
        container.graph_bundle_service.return_value = graph_bundle_service
        container.graph_runner_service.return_value = graph_runner

        return container, interaction_handler

    @pytest.mark.asyncio
    async def test_facade_does_not_unmark_when_manager_claimed_ownership(self):
        """B-3: when the manager sets _cancel_unmark_claimed before raising
        CancelledError, the facade's cancel handler must NOT call unmark.

        Counter-factual: without the B-3 guard in workflow_ops.py the facade
        would call unmark_thread_resuming even after the manager claimed it,
        creating a double-unmark race with the deferred background task.
        """
        import json

        async def _manager_claims_then_cancels(
            bundle,
            thread_id,
            checkpoint_state,
            resume_node=None,
            _cancel_unmark_claimed=None,
        ):
            # Simulate the manager claiming unmark ownership immediately after
            # its own mark_thread_resuming() (mirrors the real code path).
            if _cancel_unmark_claimed is not None:
                _cancel_unmark_claimed.set()
            raise asyncio.CancelledError("cancelled after manager claimed unmark")

        graph_runner = MagicMock()
        graph_runner.resume_from_checkpoint_async = _manager_claims_then_cancels
        container, interaction_handler = self._make_resume_container_b3(graph_runner)

        resume_token = json.dumps(
            {"thread_id": "thread-b3-001", "response_action": "continue"}
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
        ):
            with pytest.raises(asyncio.CancelledError):
                await resume_workflow_async(resume_token)

        # Facade must NOT have called unmark — the manager claimed ownership.
        interaction_handler.unmark_thread_resuming.assert_not_called()

    @pytest.mark.asyncio
    async def test_facade_still_unmarks_when_manager_did_not_claim(self):
        """B-1 regression guard: when manager cancels WITHOUT claiming ownership,
        the facade's handler MUST still call unmark (B-1 fix remains intact).
        """
        import json

        graph_runner = MagicMock()
        # Manager raises CancelledError WITHOUT setting _cancel_unmark_claimed
        graph_runner.resume_from_checkpoint_async = AsyncMock(
            side_effect=asyncio.CancelledError("cancelled before manager mark")
        )
        container, interaction_handler = self._make_resume_container_b3(graph_runner)

        resume_token = json.dumps(
            {"thread_id": "thread-b3-002", "response_action": "continue"}
        )

        with (
            patch("agentmap.runtime.workflow_ops.ensure_initialized"),
            patch(
                "agentmap.runtime.workflow_ops.RuntimeManager.get_container",
                return_value=container,
            ),
        ):
            with pytest.raises(asyncio.CancelledError):
                await resume_workflow_async(resume_token)

        # B-1 contract: facade MUST call unmark when manager hasn't claimed it
        interaction_handler.unmark_thread_resuming.assert_called_once_with(
            thread_id="thread-b3-002"
        )


# ---------------------------------------------------------------------------
# F-5 / NB-C: Size-boundary tests for _parse_resume_token
# ---------------------------------------------------------------------------


class TestParseResumeTokenSizeBoundary:
    """Verify _parse_resume_token enforces the 64 KiB size limit (BLOCKER-1 fix).

    The guard is security-relevant (prevents memory exhaustion via oversized
    payloads). These tests cover the exact boundary conditions.
    """

    def _make_token(self, thread_id: str, response_data=None) -> str:
        import json

        payload: dict = {"thread_id": thread_id, "response_action": "continue"}
        if response_data is not None:
            payload["response_data"] = response_data
        return json.dumps(payload)

    def test_token_at_exact_limit_passes(self):
        """A token whose byte-length equals _RESUME_PAYLOAD_MAX_BYTES must pass."""
        import json

        from agentmap.runtime.workflow_ops import (
            _RESUME_PAYLOAD_MAX_BYTES,
            _parse_resume_token,
        )

        # Build a token whose raw UTF-8 encoding is exactly at the limit.
        # We pad thread_id with 'a' characters to hit the boundary.
        base = json.dumps({"thread_id": "", "response_action": "continue"})
        overhead = len(base.encode("utf-8"))
        padding_len = _RESUME_PAYLOAD_MAX_BYTES - overhead
        padded_id = "a" * padding_len
        token = json.dumps({"thread_id": padded_id, "response_action": "continue"})
        assert len(token.encode("utf-8")) == _RESUME_PAYLOAD_MAX_BYTES

        thread_id, action, data = _parse_resume_token(token)
        assert thread_id == padded_id
        assert action == "continue"

    def test_token_one_byte_over_limit_raises(self):
        """A token one byte over the limit must raise InvalidInputs."""
        import json

        from agentmap.exceptions import InvalidInputs
        from agentmap.runtime.workflow_ops import (
            _RESUME_PAYLOAD_MAX_BYTES,
            _parse_resume_token,
        )

        base = json.dumps({"thread_id": "", "response_action": "continue"})
        overhead = len(base.encode("utf-8"))
        padding_len = _RESUME_PAYLOAD_MAX_BYTES - overhead + 1  # one byte over
        padded_id = "a" * padding_len
        token = json.dumps({"thread_id": padded_id, "response_action": "continue"})
        assert len(token.encode("utf-8")) == _RESUME_PAYLOAD_MAX_BYTES + 1

        with pytest.raises(InvalidInputs, match="maximum allowed size"):
            _parse_resume_token(token)

    def test_token_with_response_data_within_limit_passes(self):
        """A token containing response_data that fits within the overall limit must pass."""
        from agentmap.runtime.workflow_ops import _parse_resume_token

        # Use a small response_data dict — well inside the 64 KiB limit.
        data = {"action": "submit", "form_id": "f001", "values": {"answer": "yes"}}
        token = self._make_token("thread-size-003", response_data=data)
        thread_id, action, response_data = _parse_resume_token(token)
        assert thread_id == "thread-size-003"
        assert action == "continue"
        assert response_data == data

    def test_non_string_token_raises(self):
        """Non-string resume token must raise InvalidInputs."""
        from agentmap.exceptions import InvalidInputs
        from agentmap.runtime.workflow_ops import _parse_resume_token

        with pytest.raises(InvalidInputs, match="must be a string"):
            _parse_resume_token({"thread_id": "t1"})  # dict, not str

    def test_malformed_json_treated_as_thread_id(self):
        """A non-JSON string is treated as a raw thread_id with action='continue'."""
        from agentmap.runtime.workflow_ops import _parse_resume_token

        thread_id, action, data = _parse_resume_token("plain-thread-id-001")
        assert thread_id == "plain-thread-id-001"
        assert action == "continue"
        assert data is None


# ---------------------------------------------------------------------------
# F-5 / NB-C: Size-boundary tests for _validate_resume_payload
# ---------------------------------------------------------------------------


class TestValidateResumePayloadSizeBoundary:
    """Verify _validate_resume_payload enforces the 64 KiB size limit (BLOCKER-1 fix).

    This function guards the payload before it is forwarded to LangGraph's
    Command(resume=...).  Tests cover pass, fail, and non-serialisable cases.
    """

    def test_payload_at_exact_limit_passes(self):
        """A payload whose JSON encoding equals _RESUME_PAYLOAD_MAX_BYTES must pass."""
        import json

        from agentmap.services.graph.runner.checkpoint_manager import (
            _RESUME_PAYLOAD_MAX_BYTES,
            _validate_resume_payload,
        )

        base_overhead = len(json.dumps({"k": ""}).encode("utf-8"))
        padding_len = _RESUME_PAYLOAD_MAX_BYTES - base_overhead
        payload = {"k": "a" * padding_len}
        assert len(json.dumps(payload).encode("utf-8")) == _RESUME_PAYLOAD_MAX_BYTES

        _validate_resume_payload(payload)  # must not raise

    def test_payload_one_byte_over_limit_raises(self):
        """A payload one byte over the limit must raise ValueError."""
        import json

        from agentmap.services.graph.runner.checkpoint_manager import (
            _RESUME_PAYLOAD_MAX_BYTES,
            _validate_resume_payload,
        )

        base_overhead = len(json.dumps({"k": ""}).encode("utf-8"))
        padding_len = _RESUME_PAYLOAD_MAX_BYTES - base_overhead + 1
        payload = {"k": "a" * padding_len}
        assert len(json.dumps(payload).encode("utf-8")) == _RESUME_PAYLOAD_MAX_BYTES + 1

        with pytest.raises(ValueError, match="maximum allowed size"):
            _validate_resume_payload(payload)

    def test_non_serialisable_payload_raises(self):
        """A payload that cannot be JSON-serialised must raise ValueError."""
        from agentmap.services.graph.runner.checkpoint_manager import (
            _validate_resume_payload,
        )

        with pytest.raises(ValueError, match="not JSON-serialisable"):
            _validate_resume_payload({"bad": object()})
