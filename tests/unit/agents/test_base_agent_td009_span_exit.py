"""
Regression tests for TD-009.

Bug: ``_run_with_telemetry`` / ``_run_async_with_telemetry`` used to wrap the
lifecycle call in ``with self._telemetry_service.start_span(...) as span:``.
Because the ``with`` statement calls ``span.__exit__()`` even after the body
returns successfully, an exception raised by ``__exit__()`` *after* a
successful lifecycle return was indistinguishable from a *pre-execution*
telemetry failure -- both landed in the same ``except Exception as
telemetry_error`` handler, which re-ran the whole lifecycle via
``_run_core`` / ``_run_async_core``. That duplicated the agent's side
effects (process() invoked twice, tracking recorded twice, etc).

Fix: the span context manager is now driven manually so only a failure
*creating or entering* the span triggers the uninstrumented fallback re-run.
A failure from ``__exit__()`` after a successful lifecycle is logged and
discarded -- the agent body must not run a second time.

These tests must FAIL against the pre-fix code (process() called twice) and
PASS after the TD-009 fix, for both the sync and async paths.
"""

from unittest.mock import MagicMock, create_autospec

import pytest
from langgraph.errors import GraphInterrupt

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol


class _ExitFailsSpanCM:
    """A span context manager whose __exit__ always raises.

    Unlike a @contextmanager-based generator CM, this is a plain class so
    __enter__/__exit__ semantics are unambiguous when driven manually.
    """

    def __init__(self, span):
        self._span = span

    def __enter__(self):
        return self._span

    def __exit__(self, exc_type, exc, tb):
        raise RuntimeError("span exit boom")


class CountingAgent(BaseAgent):
    """Agent that records how many times process()/process_async() run."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.process_call_count = 0

    def process(self, inputs):
        self.process_call_count += 1
        return "test_output"

    async def process_async(self, inputs):
        self.process_call_count += 1
        return "test_output"


class SuspendingCountingAgent(BaseAgent):
    """Agent that raises GraphInterrupt and counts process() invocations."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.process_call_count = 0

    def process(self, inputs):
        self.process_call_count += 1
        raise GraphInterrupt("suspended")

    async def process_async(self, inputs):
        self.process_call_count += 1
        raise GraphInterrupt("suspended")


def _make_runnable_agent(agent_class, telemetry_service):
    mock_tracking = create_autospec(ExecutionTrackingService, instance=True)
    mock_state_adapter = create_autospec(StateAdapterService, instance=True)
    mock_tracker = MagicMock(name="mock_tracker")
    mock_logger = MagicMock(name="mock_logger")
    for method_name in ["debug", "info", "warning", "error", "trace"]:
        setattr(mock_logger, method_name, MagicMock())

    ctx = {
        "input_fields": ["input1"],
        "output_field": "output1",
        "graph_name": "test_graph",
    }

    agent = agent_class(
        name="test_agent",
        prompt="test prompt",
        context=ctx,
        logger=mock_logger,
        execution_tracking_service=mock_tracking,
        state_adapter_service=mock_state_adapter,
        telemetry_service=telemetry_service,
    )
    agent.set_execution_tracker(mock_tracker)
    mock_state_adapter.get_inputs.return_value = {"input1": "value1"}
    mock_tracking.update_graph_success.return_value = False
    return agent, mock_tracking, mock_state_adapter, mock_tracker


def _make_exit_fails_telemetry():
    mock_span = MagicMock(name="mock_span")
    svc = create_autospec(TelemetryServiceProtocol, instance=True)
    svc.start_span.return_value = _ExitFailsSpanCM(mock_span)
    return svc, mock_span


class TestSyncSpanExitFailureAfterSuccess:
    """TD-009 sync: __exit__() failure after success must not re-run process()."""

    def test_process_invoked_exactly_once(self):
        mock_svc, _ = _make_exit_fails_telemetry()
        agent, _, _, _ = _make_runnable_agent(CountingAgent, mock_svc)

        agent.run({"input1": "val"})

        assert agent.process_call_count == 1, (
            "process() ran "
            f"{agent.process_call_count} times; span.__exit__() failure "
            "after a successful lifecycle must not trigger a re-run"
        )

    def test_result_is_the_real_result_not_a_fallback_rerun(self):
        mock_svc, _ = _make_exit_fails_telemetry()
        agent, _, _, _ = _make_runnable_agent(CountingAgent, mock_svc)

        result = agent.run({"input1": "val"})

        assert result["output1"] == "test_output"

    def test_warning_logged_for_exit_failure(self):
        mock_svc, _ = _make_exit_fails_telemetry()
        agent, _, _, _ = _make_runnable_agent(CountingAgent, mock_svc)

        agent.run({"input1": "val"})

        warning_calls = agent._logger.warning.call_args_list
        warning_text = " ".join(str(c) for c in warning_calls)
        assert "span exit" in warning_text.lower()

    def test_graph_interrupt_exit_failure_does_not_rerun_process(self):
        """__exit__() failure while handling a GraphInterrupt also must not re-run."""
        mock_svc, _ = _make_exit_fails_telemetry()
        agent, _, _, _ = _make_runnable_agent(SuspendingCountingAgent, mock_svc)

        with pytest.raises(GraphInterrupt):
            agent.run({"input1": "val"})

        assert agent.process_call_count == 1


class TestAsyncSpanExitFailureAfterSuccess:
    """TD-009 async: __exit__() failure after success must not re-run process_async()."""

    def test_process_async_invoked_exactly_once(self):
        import asyncio

        mock_svc, _ = _make_exit_fails_telemetry()
        agent, _, _, _ = _make_runnable_agent(CountingAgent, mock_svc)

        asyncio.run(agent.run_async({"input1": "val"}))

        assert agent.process_call_count == 1, (
            "process_async() ran "
            f"{agent.process_call_count} times; span.__exit__() failure "
            "after a successful lifecycle must not trigger a re-run"
        )

    def test_result_is_the_real_result_not_a_fallback_rerun(self):
        import asyncio

        mock_svc, _ = _make_exit_fails_telemetry()
        agent, _, _, _ = _make_runnable_agent(CountingAgent, mock_svc)

        result = asyncio.run(agent.run_async({"input1": "val"}))

        assert result["output1"] == "test_output"

    def test_warning_logged_for_exit_failure(self):
        import asyncio

        mock_svc, _ = _make_exit_fails_telemetry()
        agent, _, _, _ = _make_runnable_agent(CountingAgent, mock_svc)

        asyncio.run(agent.run_async({"input1": "val"}))

        warning_calls = agent._logger.warning.call_args_list
        warning_text = " ".join(str(c) for c in warning_calls)
        assert "span exit" in warning_text.lower()

    def test_graph_interrupt_exit_failure_does_not_rerun_process(self):
        import asyncio

        mock_svc, _ = _make_exit_fails_telemetry()
        agent, _, _, _ = _make_runnable_agent(SuspendingCountingAgent, mock_svc)

        with pytest.raises(GraphInterrupt):
            asyncio.run(agent.run_async({"input1": "val"}))

        assert agent.process_call_count == 1


class TestPreExecutionSpanFailureStillFallsBack:
    """TD-009 guard: a genuine pre-execution span-creation failure still
    falls back to an uninstrumented re-run (the intended, non-buggy path)."""

    def test_start_span_raising_still_falls_back_sync(self):
        mock_svc = create_autospec(TelemetryServiceProtocol, instance=True)
        mock_svc.start_span.side_effect = RuntimeError("cannot create span")
        agent, _, _, _ = _make_runnable_agent(CountingAgent, mock_svc)

        result = agent.run({"input1": "val"})

        assert agent.process_call_count == 1
        assert result["output1"] == "test_output"

    def test_start_span_raising_still_falls_back_async(self):
        import asyncio

        mock_svc = create_autospec(TelemetryServiceProtocol, instance=True)
        mock_svc.start_span.side_effect = RuntimeError("cannot create span")
        agent, _, _, _ = _make_runnable_agent(CountingAgent, mock_svc)

        result = asyncio.run(agent.run_async({"input1": "val"}))

        assert agent.process_call_count == 1
        assert result["output1"] == "test_output"

    def test_span_enter_raising_still_falls_back_sync(self):
        class _EnterFailsSpanCM:
            def __enter__(self):
                raise RuntimeError("cannot enter span")

            def __exit__(self, exc_type, exc, tb):
                return False

        mock_svc = create_autospec(TelemetryServiceProtocol, instance=True)
        mock_svc.start_span.return_value = _EnterFailsSpanCM()
        agent, _, _, _ = _make_runnable_agent(CountingAgent, mock_svc)

        result = agent.run({"input1": "val"})

        assert agent.process_call_count == 1
        assert result["output1"] == "test_output"
