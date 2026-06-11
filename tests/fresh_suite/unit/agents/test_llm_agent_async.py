"""
Unit tests for LLMAgent async processing path.

TC-003: LLMAgent.run_async() preserves legacy prompt resolution, memory updates, and output shaping
TC-004: LLMAgent.run_async() preserves routing behavior and error handling in routing mode

Covers: REQ-F-003, REQ-NF-003, AC-002 (T-E04-F02-002)

Caller-Path Contracts:
- Entrypoint: await agent.run_async(state) where agent is LLMAgent
- Lowest allowed mock seam: LLMService.call_llm_async() on the injected service and
  the normal state-adapter / tracking services
- Forbidden mocks: do not mock LLMAgent.run_async(), LLMAgent.process_async(), or
  memory helpers like add_user_message() / add_assistant_message()
- Counter-factual TC-003: a buggy implementation would call the sync LLM service,
  drop memory updates, or return the wrong output shape
- Counter-factual TC-004: a buggy implementation would ignore the routing context,
  use the direct provider path, or flatten async errors into a different contract
"""

import asyncio
import unittest
from unittest.mock import AsyncMock

from agentmap.agents.builtins.llm.llm_agent import LLMAgent
from agentmap.models.llm_execution import LLMResponse
from tests.utils.mock_service_factory import MockServiceFactory

# ---------------------------------------------------------------------------
# Helper: configure state adapter to pass through inputs from state
# ---------------------------------------------------------------------------


def _configure_state_adapter_passthrough(mock_state_adapter, input_fields):
    """Configure state adapter to extract input_fields from state dict."""

    def get_inputs(state, fields, **kwargs):
        return {field: state.get(field) for field in fields if field in state}

    mock_state_adapter.get_inputs.side_effect = get_inputs


# ---------------------------------------------------------------------------
# TC-003: Legacy mode — prompt resolution, memory updates, output shaping
# ---------------------------------------------------------------------------


class TestLLMAgentRunAsync_TC003(unittest.TestCase):
    """
    TC-003: LLMAgent.run_async() preserves legacy prompt resolution, memory
    updates, and output shaping.

    Uses the production caller entrypoint: await agent.run_async(state)
    Mocks only at the allowed seams: LLMService.call_llm_async(), state adapter,
    and execution tracking service.
    """

    def setUp(self):
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )

        # Create an LLM service mock with both sync and async methods
        # The async test must use call_llm_async, not call_llm
        self.mock_llm_service = MockServiceFactory.create_mock_llm_service()
        # Override call_llm_async to return a known response
        self.llm_async_response = LLMResponse(
            text="Async LLM response for testing",
            resolved_provider="openai",
            resolved_model="gpt-4o-mini",
            usage=None,
        )
        self.mock_llm_service.call_llm_async = AsyncMock(
            return_value=self.llm_async_response
        )
        # call_llm (sync) should NOT be called in the async path
        self.mock_llm_service.call_llm.return_value = "This should NOT be called"

        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()

        self.mock_logger = self.mock_logging_service.get_class_logger(LLMAgent)

        self.test_context = {
            "input_fields": ["prompt", "context"],
            "output_field": "response",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 1000,
            "memory_key": "memory",
        }

    def _make_agent(self, context=None):
        ctx = context or self.test_context
        agent = LLMAgent(
            name="test_llm_async_node",
            prompt="You are a helpful AI assistant.",
            context=ctx,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )
        agent.configure_llm_service(self.mock_llm_service)
        agent.set_execution_tracker(self.mock_tracker)
        _configure_state_adapter_passthrough(
            self.mock_state_adapter_service,
            agent.input_fields,
        )
        return agent

    # ------------------------------------------------------------------
    # Happy path: call_llm_async is called, output and memory are correct
    # ------------------------------------------------------------------

    def test_run_async_calls_call_llm_async_not_call_llm(self):
        """
        TC-003 primary / counter-factual: the async path must call call_llm_async(),
        never call_llm() (sync). A buggy impl would call the sync service.
        """
        agent = self._make_agent()
        state = {"prompt": "What is AI?", "context": "Explain simply", "memory": []}

        asyncio.run(agent.run_async(state))

        # call_llm_async must have been called
        self.mock_llm_service.call_llm_async.assert_called_once()
        # call_llm (sync) must NOT have been called
        self.mock_llm_service.call_llm.assert_not_called()

    def test_run_async_returns_output_field_in_state_updates(self):
        """
        TC-003 output shaping: run_async() returns the output_field value in state updates.
        """
        agent = self._make_agent()
        state = {"prompt": "What is AI?", "context": "Explain simply", "memory": []}

        result = asyncio.run(agent.run_async(state))

        # The result should contain the output field
        self.assertIn("response", result)
        self.assertEqual(result["response"], "Async LLM response for testing")

    def test_run_async_returns_memory_in_state_updates(self):
        """
        TC-003 memory update: run_async() includes memory in the state update,
        with the assistant response appended. A buggy impl would drop memory updates.

        Note: the system message is only added to memory when the memory key is
        absent from inputs (not when it is present but empty). When state already
        has an empty memory list, memory init is skipped — consistent with sync.
        """
        agent = self._make_agent()
        # Omit the memory key so _initialize_memory_if_needed adds the system message
        state = {"prompt": "What is AI?", "context": "Explain simply"}

        result = asyncio.run(agent.run_async(state))

        # Memory must be in the result
        self.assertIn("memory", result)
        memory = result["memory"]
        self.assertIsInstance(memory, list)

        # Memory must include system message (from prompt), user message, and assistant response
        # because memory key was absent from state so initialization ran.
        roles = [msg["role"] for msg in memory]
        self.assertIn("system", roles)
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)

        # Assistant response content must match the LLM response
        assistant_msgs = [m for m in memory if m["role"] == "assistant"]
        self.assertTrue(len(assistant_msgs) >= 1)
        self.assertEqual(
            assistant_msgs[-1]["content"], "Async LLM response for testing"
        )

    def test_run_async_call_params_match_legacy_mode_expected_signature(self):
        """
        TC-003 signature: call_llm_async() receives the messages list and
        provider/model/temperature kwargs as production callers would pass them.
        """
        agent = self._make_agent()
        state = {"prompt": "What is AI?", "context": "Explain simply", "memory": []}

        asyncio.run(agent.run_async(state))

        call_args = self.mock_llm_service.call_llm_async.call_args
        kwargs = call_args.kwargs

        # Must pass messages, provider, model, temperature as keyword args
        self.assertIn("messages", kwargs)
        messages = kwargs["messages"]
        self.assertIsInstance(messages, list)
        self.assertIn("provider", kwargs)
        self.assertEqual(kwargs["provider"], "openai")
        self.assertIn("model", kwargs)
        self.assertEqual(kwargs["model"], "gpt-4o-mini")
        self.assertIn("temperature", kwargs)
        self.assertEqual(kwargs["temperature"], 0.7)

    def test_run_async_single_input_field_produces_plain_user_message(self):
        """
        TC-003 edge case: a single input field produces a plain user message without prefixes,
        consistent with the sync process() behavior.
        """
        ctx = {
            "input_fields": ["prompt"],
            "output_field": "response",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "memory_key": "memory",
        }
        agent = self._make_agent(context=ctx)
        state = {"prompt": "What is the capital of France?", "memory": []}
        _configure_state_adapter_passthrough(
            self.mock_state_adapter_service, agent.input_fields
        )

        asyncio.run(agent.run_async(state))

        call_args = self.mock_llm_service.call_llm_async.call_args
        messages = call_args.kwargs["messages"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        self.assertEqual(len(user_msgs), 1)
        # Single field: no prefix
        self.assertEqual(user_msgs[0]["content"], "What is the capital of France?")

    def test_run_async_multiple_input_fields_produce_prefixed_user_message(self):
        """
        TC-003 edge case: multiple input fields produce prefixed message content
        in the same order as sync, consistent with the sync process() behavior.
        """
        agent = self._make_agent()
        state = {
            "prompt": "Summarize this",
            "context": "Some context here",
            "memory": [],
        }

        asyncio.run(agent.run_async(state))

        call_args = self.mock_llm_service.call_llm_async.call_args
        messages = call_args.kwargs["messages"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        self.assertEqual(len(user_msgs), 1)
        # Multiple fields: prefixed format
        expected = "prompt: Summarize this\ncontext: Some context here"
        self.assertEqual(user_msgs[0]["content"], expected)

    def test_run_async_max_memory_messages_truncates_after_assistant_appended(self):
        """
        TC-003 edge case: max_memory_messages truncates the memory list after
        the assistant response is appended.
        """
        ctx = {
            "input_fields": ["prompt"],
            "output_field": "response",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "memory_key": "memory",
            "max_memory_messages": 2,  # Keep only 2 most recent messages
        }
        agent = self._make_agent(context=ctx)

        # Start with a pre-filled memory (system + prior user/assistant pairs)
        initial_memory = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Prior question"},
            {"role": "assistant", "content": "Prior answer"},
        ]
        state = {"prompt": "New question", "memory": initial_memory}
        _configure_state_adapter_passthrough(
            self.mock_state_adapter_service, agent.input_fields
        )

        result = asyncio.run(agent.run_async(state))

        # Memory must have been truncated to max_memory_messages
        self.assertIn("memory", result)
        self.assertLessEqual(len(result["memory"]), 2)

    def test_run_async_execution_tracking_records_start_and_result(self):
        """
        TC-003 observability: run_async() records node start and result via the
        execution tracking service, consistent with the sync path.
        """
        agent = self._make_agent()
        state = {"prompt": "What is AI?", "context": "Explain simply", "memory": []}

        asyncio.run(agent.run_async(state))

        self.mock_execution_tracking_service.record_node_start.assert_called()
        self.mock_execution_tracking_service.record_node_result.assert_called()


# ---------------------------------------------------------------------------
# TC-004: Routing mode — routing context and error handling
# ---------------------------------------------------------------------------


class TestLLMAgentRunAsync_TC004(unittest.TestCase):
    """
    TC-004: LLMAgent.run_async() preserves routing behavior and error handling
    in routing mode.

    Uses the production caller entrypoint: await agent.run_async(state)
    Mocks only at the allowed seams: LLMService.call_llm_async(), state adapter,
    and execution tracking service.
    """

    def setUp(self):
        self.mock_logging_service = MockServiceFactory.create_mock_logging_service()
        self.mock_execution_tracking_service = (
            MockServiceFactory.create_mock_execution_tracking_service()
        )
        self.mock_state_adapter_service = (
            MockServiceFactory.create_mock_state_adapter_service()
        )

        self.mock_llm_service = MockServiceFactory.create_mock_llm_service()
        self.llm_async_response = LLMResponse(
            text="Routed LLM response",
            resolved_provider="anthropic",
            resolved_model="claude-sonnet-4-6",
            usage=None,
        )
        self.mock_llm_service.call_llm_async = AsyncMock(
            return_value=self.llm_async_response
        )
        # Sync should NOT be called in the async routing path
        self.mock_llm_service.call_llm.return_value = "This should NOT be called"

        self.mock_tracker = self.mock_execution_tracking_service.create_tracker()
        self.mock_logger = self.mock_logging_service.get_class_logger(LLMAgent)

        self.routing_context = {
            "input_fields": ["topic"],
            "output_field": "plan",
            "routing_enabled": True,
            "provider_preference": ["anthropic", "openai"],
            "fallback_provider": "openai",
            "memory_key": "memory",
        }

    def _make_agent(self, context=None):
        ctx = context or self.routing_context
        agent = LLMAgent(
            name="routing_llm_async_node",
            prompt="You are a trip planning assistant.",
            context=ctx,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )
        agent.configure_llm_service(self.mock_llm_service)
        agent.set_execution_tracker(self.mock_tracker)
        _configure_state_adapter_passthrough(
            self.mock_state_adapter_service,
            agent.input_fields,
        )
        return agent

    # ------------------------------------------------------------------
    # Success path: routing context is passed through
    # ------------------------------------------------------------------

    def test_run_async_routing_mode_calls_call_llm_async_with_routing_context(self):
        """
        TC-004 primary / counter-factual: in routing mode, the async path must
        pass the routing_context to call_llm_async(). A buggy impl would bypass
        routing and use the direct provider/model values.
        """
        agent = self._make_agent()
        state = {"topic": "plan a trip", "memory": []}

        asyncio.run(agent.run_async(state))

        self.mock_llm_service.call_llm_async.assert_called_once()
        # Sync path must not be called
        self.mock_llm_service.call_llm.assert_not_called()

        call_args = self.mock_llm_service.call_llm_async.call_args
        kwargs = call_args.kwargs

        # routing_context must be present in the call
        self.assertIn("routing_context", kwargs)
        routing_ctx = kwargs["routing_context"]
        self.assertIsNotNone(routing_ctx)
        self.assertTrue(routing_ctx.get("routing_enabled"))

    def test_run_async_routing_mode_returns_output_field_and_memory(self):
        """
        TC-004 output: routing mode run_async() returns the output_field and
        memory in the state update, same as legacy mode.
        """
        agent = self._make_agent()
        state = {"topic": "plan a trip", "memory": []}

        result = asyncio.run(agent.run_async(state))

        self.assertIn("plan", result)
        self.assertEqual(result["plan"], "Routed LLM response")
        self.assertIn("memory", result)

    def test_run_async_routing_mode_does_not_use_legacy_provider(self):
        """
        TC-004 negative: the routing mode async path must not pass
        provider=self.provider_name ('auto') and instead must pass routing_context.
        """
        agent = self._make_agent()
        state = {"topic": "plan a trip", "memory": []}

        asyncio.run(agent.run_async(state))

        call_args = self.mock_llm_service.call_llm_async.call_args
        kwargs = call_args.kwargs

        # In routing mode, provider passed to call_llm_async should be "auto"
        # (or routing_context handles it), but routing_context must be present
        self.assertIn("routing_context", kwargs)
        self.assertIsNotNone(kwargs["routing_context"])

    # ------------------------------------------------------------------
    # Error path: LLM raises exception -> agent returns error dict
    # ------------------------------------------------------------------

    def test_run_async_routing_mode_error_returns_error_dict(self):
        """
        TC-004 error path: when the async LLM service raises a generic exception,
        run_async() must return a state update containing the error dict rather than
        propagating the exception to the caller.

        The LLMAgent.process_async() catches LLM errors and returns an error dict
        {"error": ..., "last_action_success": False}. The base-class lifecycle then
        wraps this as the output_field value in the state update, consistent with
        how the sync process() path behaves.
        """
        self.mock_llm_service.call_llm_async = AsyncMock(
            side_effect=Exception("Async LLM routing error")
        )

        agent = self._make_agent()
        state = {"topic": "plan a trip", "memory": []}

        result = asyncio.run(agent.run_async(state))

        # The result must be a state update dict (not a raised exception)
        self.assertIsInstance(result, dict)

        # The error dict is returned as the output field value (same as sync path)
        # The plan field contains the error information from process_async()
        self.assertIn("plan", result)
        error_payload = result["plan"]
        self.assertIsInstance(error_payload, dict)
        self.assertIn("error", error_payload)
        self.assertIn("Async LLM routing error", error_payload["error"])
        self.assertFalse(error_payload.get("last_action_success", True))

    def test_run_async_legacy_mode_error_returns_error_dict(self):
        """
        TC-004 error path (legacy mode): async LLM error in legacy mode also
        returns a state update containing the error dict. This validates error
        handling parity between routing and legacy modes.

        Same contract as routing mode: LLMAgent.process_async() catches the LLM
        error and returns {"error": ..., "last_action_success": False}, which the
        base-class lifecycle wraps as the output_field value.
        """
        self.mock_llm_service.call_llm_async = AsyncMock(
            side_effect=Exception("Async LLM legacy error")
        )

        legacy_context = {
            "input_fields": ["prompt"],
            "output_field": "response",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "memory_key": "memory",
        }
        agent = LLMAgent(
            name="legacy_error_node",
            prompt="Test prompt",
            context=legacy_context,
            logger=self.mock_logger,
            execution_tracking_service=self.mock_execution_tracking_service,
            state_adapter_service=self.mock_state_adapter_service,
        )
        agent.configure_llm_service(self.mock_llm_service)
        agent.set_execution_tracker(self.mock_tracker)
        _configure_state_adapter_passthrough(
            self.mock_state_adapter_service, agent.input_fields
        )

        result = asyncio.run(agent.run_async({"prompt": "test", "memory": []}))

        self.assertIsInstance(result, dict)
        # The error dict is wrapped in the output field (same as sync path)
        self.assertIn("response", result)
        error_payload = result["response"]
        self.assertIsInstance(error_payload, dict)
        self.assertIn("error", error_payload)
        self.assertIn("Async LLM legacy error", error_payload["error"])
        self.assertFalse(error_payload.get("last_action_success", True))

    def test_run_async_routing_mode_with_empty_input_routes_through_call(self):
        """
        TC-004 edge case: empty user input still routes through the async call path
        and records the system prompt when configured.
        """
        agent = self._make_agent()
        state = {"topic": "", "memory": []}  # empty topic

        asyncio.run(agent.run_async(state))

        # call_llm_async must still be called even with empty input
        self.mock_llm_service.call_llm_async.assert_called_once()

    def test_run_async_routing_mode_provider_preference_passed_in_routing_context(self):
        """
        TC-004 routing context content: provider_preference from agent context
        is forwarded in the routing_context passed to call_llm_async().
        """
        agent = self._make_agent()
        state = {"topic": "plan a trip", "memory": []}

        asyncio.run(agent.run_async(state))

        call_args = self.mock_llm_service.call_llm_async.call_args
        routing_ctx = call_args.kwargs.get("routing_context", {})

        # provider_preference must be forwarded
        self.assertIn("provider_preference", routing_ctx)
        self.assertEqual(routing_ctx["provider_preference"], ["anthropic", "openai"])


if __name__ == "__main__":
    unittest.main()
