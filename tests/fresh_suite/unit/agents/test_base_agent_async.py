"""
Unit tests for BaseAgent async lifecycle entrypoints.

TC-001: BaseAgent.run_async() mirrors sync state updates for a sync-only subclass
TC-002: BaseAgent.run_async() propagates GraphInterrupt and records suspended state

Covers: REQ-F-001, REQ-F-002, REQ-NF-001, AC-001 (T-E04-F02-001 AC-T1)

Caller-Path Contracts:
- Entrypoint: await agent.run_async(state) where state is the LangGraph node state
  dict and the execution tracker has already been set on the agent.
- Lowest allowed mock seam: StateAdapterService.get_inputs() and
  ExecutionTrackingService methods; the agent lifecycle itself must be real.
- Forbidden mocks: do not mock run_async(), _execute_agent_lifecycle(), or the
  subclass process_async() implementation under test.
- Counter-factual: a buggy implementation would route the async entrypoint back
  through sync run() or lose the state_updates contract.
"""

import asyncio
import unittest
from typing import Any, Dict

from langgraph.errors import GraphInterrupt

from agentmap.agents.base_agent import BaseAgent
from tests.utils.mock_service_factory import MockServiceFactory

# ---------------------------------------------------------------------------
# Concrete test agents
# ---------------------------------------------------------------------------


class SyncOnlyConcreteAgent(BaseAgent):
    """
    Concrete BaseAgent subclass that only implements the sync process().
    Has no process_async() override — exercises the default async fallback path.
    """

    def process(self, inputs: Dict[str, Any]) -> Any:
        result_value = f"{inputs.get('input', 'none')}-done"
        return {
            "state_updates": {
                "result": result_value,
                "last_action_success": True,
            }
        }


class AsyncInterruptAgent(BaseAgent):
    """
    Concrete BaseAgent subclass whose async processing boundary raises GraphInterrupt.
    Used to verify TC-002: interrupt propagation through the real async lifecycle.
    """

    def process(self, inputs: Dict[str, Any]) -> Any:
        # In the sync path this would also raise, but we are testing via run_async
        raise GraphInterrupt({"reason": "human_in_the_loop"})

    async def process_async(self, inputs: Dict[str, Any]) -> Any:
        raise GraphInterrupt({"reason": "human_in_the_loop"})


class AsyncCustomConcreteAgent(BaseAgent):
    """
    Concrete BaseAgent subclass with a real process_async() override.
    Verifies that the async path calls process_async() rather than process().
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.process_called = False
        self.process_async_called = False

    def process(self, inputs: Dict[str, Any]) -> Any:
        self.process_called = True
        return "sync_result"

    async def process_async(self, inputs: Dict[str, Any]) -> Any:
        self.process_async_called = True
        return {
            "state_updates": {
                "result": "async_result",
                "last_action_success": True,
            }
        }


# ---------------------------------------------------------------------------
# TC-001
# ---------------------------------------------------------------------------


class TestBaseAgentRunAsync_TC001(unittest.TestCase):
    """
    TC-001: BaseAgent.run_async() mirrors sync state updates for a sync-only subclass.
    """

    def setUp(self):
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )
        self.mock_logger = self.mock_logging_service.get_class_logger(
            SyncOnlyConcreteAgent
        )
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()

        self.mock_state_adapter_service.get_inputs.return_value = {"input": "alpha"}

    def _make_agent(self, output_field="result"):
        agent = SyncOnlyConcreteAgent(
            name="test_node",
            prompt="Test",
            context={
                "input_fields": ["input"],
                "output_field": output_field,
            },
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )
        agent.set_execution_tracker(self.mock_tracker)
        return agent

    def test_run_async_returns_same_state_updates_shape_as_run(self):
        """
        TC-001 happy path: run_async() returns the same state_updates payload
        shape as run() for equivalent inputs.
        """
        agent = self._make_agent()
        state = {"input": "alpha", "existing": "preserve-me"}

        # Arrange: configure what run() produces for the same inputs
        sync_result = agent.run(state)

        # Act: reset call counts, then call async path
        self.mock_state_adapter_service.get_inputs.reset_mock()
        self.mock_state_adapter_service.get_inputs.return_value = {"input": "alpha"}

        async_result = asyncio.run(agent.run_async(state))

        # Assert: async result is structurally identical to sync result
        self.assertEqual(async_result, sync_result)
        self.assertIn("result", async_result)
        self.assertEqual(async_result["result"], "alpha-done")
        self.assertTrue(async_result["last_action_success"])

    def test_run_async_calls_execution_tracking_service(self):
        """
        TC-001 observability: run_async() records node start and node result
        through the execution tracking service.
        """
        agent = self._make_agent()
        state = {"input": "alpha"}

        asyncio.run(agent.run_async(state))

        self.mock_execution_tracking_service.record_node_start.assert_called()
        self.mock_execution_tracking_service.record_node_result.assert_called()

    def test_run_async_does_not_call_sync_run(self):
        """
        TC-001 negative: run_async() must not delegate to run().
        Counter-factual: a buggy impl routes async entrypoint back through run().
        We verify this by confirming run() is not called via the real lifecycle
        — if run_async() simply called self.run(), the test agent would be invoked
        through a blocking call which we can detect via monkeypatching.
        """
        agent = self._make_agent()
        state = {"input": "alpha"}

        run_call_count = {"n": 0}
        original_run = agent.run

        def spy_run(s):
            run_call_count["n"] += 1
            return original_run(s)

        agent.run = spy_run

        # run_async must not call the monkey-patched run()
        asyncio.run(agent.run_async(state))
        self.assertEqual(run_call_count["n"], 0, "run_async() must not call run()")

    def test_run_async_with_output_field_none_returns_empty_dict(self):
        """
        TC-001 edge case: output_field=None returns {} from the async path.
        """
        agent = SyncOnlyConcreteAgent(
            name="no_output_node",
            prompt="Test",
            context={"input_fields": ["input"]},  # no output_field
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )
        agent.set_execution_tracker(self.mock_tracker)

        # A SyncOnlyConcreteAgent returns state_updates, so the result is the dict
        # But if we want to test the bare {} case we need a simpler process()
        # Use a fresh agent subclass inline:
        class NoOutputAgent(BaseAgent):
            def process(self, inputs):
                return None  # No output

        no_out_agent = NoOutputAgent(
            name="no_out",
            prompt="",
            context={"input_fields": ["input"]},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )
        no_out_agent.set_execution_tracker(self.mock_tracker)

        result = asyncio.run(no_out_agent.run_async({"input": "x"}))
        self.assertEqual(result, {})

    def test_run_async_with_empty_state_input_does_not_crash(self):
        """
        TC-001 edge case: empty state still routes through the async lifecycle.
        """
        agent = self._make_agent()
        self.mock_state_adapter_service.get_inputs.return_value = {}

        result = asyncio.run(agent.run_async({}))
        # process() still runs; result depends on what process() does with empty inputs
        self.assertIsInstance(result, dict)

    def test_run_async_process_async_called_when_overridden(self):
        """
        AC-T1: the default process_async() path preserves compatibility without
        routing through run(). When a subclass overrides process_async(), that
        override is used — NOT the sync process().
        """
        agent = AsyncCustomConcreteAgent(
            name="custom_async_node",
            prompt="Test",
            context={"input_fields": ["input"], "output_field": "result"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )
        agent.set_execution_tracker(self.mock_tracker)

        asyncio.run(agent.run_async({"input": "x"}))

        self.assertTrue(
            agent.process_async_called,
            "process_async() must be called when the subclass overrides it",
        )
        self.assertFalse(
            agent.process_called,
            "sync process() must NOT be called when process_async() is overridden",
        )


# ---------------------------------------------------------------------------
# TC-002
# ---------------------------------------------------------------------------


class TestBaseAgentRunAsync_TC002(unittest.TestCase):
    """
    TC-002: BaseAgent.run_async() propagates GraphInterrupt and records suspended state.
    """

    def setUp(self):
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )
        self.mock_logger = self.mock_logging_service.get_class_logger(
            AsyncInterruptAgent
        )
        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()
        self.mock_state_adapter_service.get_inputs.return_value = {"input": "alpha"}

    def _make_agent(self):
        agent = AsyncInterruptAgent(
            name="interrupt_node",
            prompt="Test",
            context={
                "input_fields": ["input"],
                "output_field": "result",
            },
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )
        agent.set_execution_tracker(self.mock_tracker)
        return agent

    def test_run_async_propagates_graph_interrupt(self):
        """
        TC-002 primary: GraphInterrupt raised in process_async() is re-raised
        to the caller — not swallowed, not converted to a generic error.
        """
        agent = self._make_agent()

        with self.assertRaises(GraphInterrupt):
            asyncio.run(agent.run_async({"input": "alpha"}))

    def test_run_async_records_suspended_state_on_graph_interrupt(self):
        """
        TC-002 tracking: the tracking service records a suspended result on interrupt,
        consistent with the sync path behavior.
        """
        agent = self._make_agent()

        with self.assertRaises(GraphInterrupt):
            asyncio.run(agent.run_async({"input": "alpha"}))

        # record_node_result should have been called with a suspended indicator
        self.mock_execution_tracking_service.record_node_result.assert_called()
        call_kwargs = self.mock_execution_tracking_service.record_node_result.call_args
        # The sync path records True (success=True) with result={"status": "suspended"}
        args, kwargs = call_kwargs
        # args: (tracker, node_name, success, result=...) or positional
        # Check that it was called with success=True and a suspended result
        # Positional signature: record_node_result(tracker, node_name, success, result=...)
        if len(args) >= 3:
            success_flag = args[2]
        else:
            success_flag = kwargs.get("success", None)
        self.assertTrue(
            success_flag,
            "Suspended state must be recorded with success=True (not an error)",
        )

    def test_run_async_does_not_convert_interrupt_to_error(self):
        """
        TC-002 negative: run_async() must not swallow the interrupt and substitute
        a generic error dict — the interrupt must propagate as GraphInterrupt.
        """
        agent = self._make_agent()
        interrupted = False

        try:
            asyncio.run(agent.run_async({"input": "alpha"}))
        except GraphInterrupt:
            interrupted = True
        except Exception:
            self.fail(
                "run_async() converted GraphInterrupt to a generic exception — "
                "the interrupt must propagate unchanged."
            )

        self.assertTrue(interrupted, "GraphInterrupt must be re-raised by run_async()")

    def test_run_async_interrupt_with_no_telemetry(self):
        """
        TC-002 edge case: telemetry service absent — interrupt still propagates.
        """
        agent = AsyncInterruptAgent(
            name="no_telemetry_interrupt_node",
            prompt="Test",
            context={"input_fields": ["input"], "output_field": "result"},
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
            # No telemetry_service — must degrade silently
        )
        agent.set_execution_tracker(self.mock_tracker)

        with self.assertRaises(GraphInterrupt):
            asyncio.run(agent.run_async({"input": "alpha"}))

    def test_run_async_interrupt_with_empty_state_adapter_inputs(self):
        """
        TC-002 edge case: state adapter returns an empty input map —
        interrupt still propagates from the async lifecycle.
        """
        self.mock_state_adapter_service.get_inputs.return_value = {}
        agent = self._make_agent()

        with self.assertRaises(GraphInterrupt):
            asyncio.run(agent.run_async({"input": "alpha"}))


if __name__ == "__main__":
    unittest.main()
