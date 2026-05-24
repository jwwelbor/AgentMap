"""
Fan-out tests for LLMService.call_llm_many_async.

Covers AC-001 through AC-009 from the E05-F02 test plan:
  AC-001: Protocol surface (TC-AC1-01, TC-AC1-02)
  AC-002: One result per spec (TC-AC2-01, TC-AC2-02)
  AC-003: Stable ordering (TC-AC3-01, TC-AC3-02)
  AC-004: Submission validation (TC-AC4-01, TC-AC4-02, TC-AC4-03)
  AC-005: Concurrency cap (TC-AC5-01, TC-AC5-02)
  AC-006: Partial-failure completion (TC-AC6-01, TC-AC6-02)
  AC-007: Successful result normalization (TC-AC7-01, TC-AC7-02)
  AC-008: Failure result normalization (TC-AC8-01, TC-AC8-02)
  AC-009: Cache-aware request pass-through (TC-AC9-01, TC-AC9-02)
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, create_autospec, patch

from agentmap.exceptions import LLMServiceError
from agentmap.models.llm_execution import LLMCallResult, LLMCallSpec, LLMUsage
from agentmap.services.llm_service import LLMService
from agentmap.services.protocols import LLMServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_spec(spec_id: str, provider: str = "openai", **kwargs) -> LLMCallSpec:
    """Factory for minimal test LLMCallSpec instances."""
    return LLMCallSpec(
        spec_id=spec_id,
        messages=[{"role": "user", "content": f"prompt for {spec_id}"}],
        provider=provider,
        **kwargs,
    )


def _make_service() -> LLMService:
    """Construct a minimal LLMService with mock dependencies."""
    mock_logging = MockServiceFactory.create_mock_logging_service()
    mock_config = MockServiceFactory.create_mock_app_config_service()
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {
            "max_attempts": 1,
            "backoff_base": 2.0,
            "backoff_max": 30.0,
            "jitter": False,
        },
        "circuit_breaker": {"failure_threshold": 5, "reset_timeout": 60},
    }
    mock_config.get_llm_config.side_effect = lambda provider: {
        "model": f"{provider}-default-model",
        "api_key": "test-key",
    }
    mock_models = MockServiceFactory.create_mock_llm_models_config_service()
    mock_routing = Mock()

    return LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing,
        llm_models_config_service=mock_models,
    )


# ---------------------------------------------------------------------------
# AC-001  Protocol surface
# ---------------------------------------------------------------------------


class TestAC001ProtocolSurface(unittest.TestCase):
    """TC-AC1-01 and TC-AC1-02: protocol and concrete service surface."""

    def test_tc_ac1_01_protocol_autospec_exposes_fan_out_method(self):
        """TC-AC1-01: autospec exposes call_llm_many_async as an AsyncMock."""
        mock_service = create_autospec(LLMServiceProtocol, instance=True)

        self.assertTrue(hasattr(mock_service, "call_llm_many_async"))
        self.assertIsInstance(mock_service.call_llm_many_async, AsyncMock)

    def test_tc_ac1_01_protocol_autospec_preserves_existing_methods(self):
        """TC-AC1-01: existing protocol members are not removed."""
        mock_service = create_autospec(LLMServiceProtocol, instance=True)

        self.assertTrue(hasattr(mock_service, "call_llm"))
        self.assertTrue(hasattr(mock_service, "call_llm_async"))
        self.assertTrue(hasattr(mock_service, "ask_async"))
        self.assertTrue(hasattr(mock_service, "ask_vision"))

    def test_tc_ac1_02_concrete_service_exposes_fan_out_method(self):
        """TC-AC1-02: LLMService instance has callable call_llm_many_async."""
        service = _make_service()

        self.assertTrue(hasattr(service, "call_llm_many_async"))
        self.assertTrue(callable(service.call_llm_many_async))

    def test_tc_ac1_02_concrete_service_preserves_existing_public_methods(self):
        """TC-AC1-02: additive — existing public methods remain available."""
        service = _make_service()

        for method in ("call_llm", "call_llm_async", "ask_async", "ask", "ask_vision"):
            self.assertTrue(hasattr(service, method), f"missing method: {method}")


# ---------------------------------------------------------------------------
# AC-002  One result per spec
# ---------------------------------------------------------------------------


class TestAC002OneResultPerSpec(unittest.IsolatedAsyncioTestCase):
    """TC-AC2-01 and TC-AC2-02: exactly one terminal result per submitted spec."""

    def setUp(self):
        self.service = _make_service()

    async def test_tc_ac2_01_three_specs_return_three_results(self):
        """TC-AC2-01: 3 specs submitted yields exactly 3 terminal results."""
        specs = [_make_spec(f"spec-{i}") for i in range(3)]

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(return_value=("response", None)),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=2)

        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIsInstance(result, LLMCallResult)
            self.assertEqual(result.status, "succeeded")

    async def test_tc_ac2_01_single_spec_returns_single_result(self):
        """TC-AC2-01 edge: single-item submission returns one result."""
        specs = [_make_spec("only-one")]

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(return_value=("hello", None)),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].spec_id, "only-one")
        self.assertEqual(results[0].content, "hello")

    async def test_tc_ac2_02_large_submission_has_no_dropped_or_duplicated_results(
        self,
    ):
        """TC-AC2-02: 100 specs with concurrency=8 yield exactly 100 results."""
        specs = [_make_spec(f"bulk-{i}") for i in range(100)]

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(return_value=("ok", None)),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=8)

        self.assertEqual(len(results), 100)
        returned_ids = [r.spec_id for r in results]
        self.assertEqual(len(set(returned_ids)), 100)
        for spec in specs:
            self.assertIn(spec.spec_id, returned_ids)


# ---------------------------------------------------------------------------
# AC-003  Stable ordering
# ---------------------------------------------------------------------------


class TestAC003StableOrdering(unittest.IsolatedAsyncioTestCase):
    """TC-AC3-01 and TC-AC3-02: output order matches input order."""

    def setUp(self):
        self.service = _make_service()

    async def test_tc_ac3_01_results_preserve_input_order_despite_completion_delay(
        self,
    ):
        """TC-AC3-01: completion order B,C,A should not affect output order A,B,C."""
        call_count = [0]

        async def ordered_response(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            # Simulate: spec_b finishes quickly, spec_c next, spec_a last
            delays = [0.02, 0.00, 0.01]
            await asyncio.sleep(delays[idx])
            return f"response-{idx}", None

        specs = [_make_spec("spec-a"), _make_spec("spec-b"), _make_spec("spec-c")]

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=ordered_response),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=3)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].spec_id, "spec-a")
        self.assertEqual(results[1].spec_id, "spec-b")
        self.assertEqual(results[2].spec_id, "spec-c")

    async def test_tc_ac3_02_each_result_carries_original_spec_id(self):
        """TC-AC3-02: each result's spec_id matches its originating spec."""
        specs = [_make_spec("id-first"), _make_spec("id-second")]

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(return_value=("content", None)),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=2)

        self.assertEqual(results[0].spec_id, "id-first")
        self.assertEqual(results[1].spec_id, "id-second")


# ---------------------------------------------------------------------------
# AC-004  Submission validation
# ---------------------------------------------------------------------------


class TestAC004SubmissionValidation(unittest.IsolatedAsyncioTestCase):
    """TC-AC4-01, TC-AC4-02, TC-AC4-03: validation before execution."""

    def setUp(self):
        self.service = _make_service()

    async def test_tc_ac4_01_empty_call_specs_raises_before_execution(self):
        """TC-AC4-01: empty call_specs must raise LLMServiceError."""
        with patch.object(
            self.service, "_call_llm_async_with_response", new=AsyncMock()
        ) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async([], max_concurrency=1)

            mock_call.assert_not_called()

    async def test_tc_ac4_02_duplicate_spec_id_raises_before_execution(self):
        """TC-AC4-02: duplicate spec_id raises LLMServiceError before execution."""
        specs = [_make_spec("dup-1"), _make_spec("dup-1")]

        with patch.object(
            self.service, "_call_llm_async_with_response", new=AsyncMock()
        ) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async(specs, max_concurrency=2)

            mock_call.assert_not_called()

    async def test_tc_ac4_02_duplicate_spec_id_separated_in_large_list(self):
        """TC-AC4-02 edge: duplicates separated in a large list are still caught."""
        specs = [_make_spec(f"item-{i}") for i in range(20)]
        specs.append(_make_spec("item-5"))  # duplicate at the end

        with patch.object(
            self.service, "_call_llm_async_with_response", new=AsyncMock()
        ) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async(specs, max_concurrency=4)

            mock_call.assert_not_called()

    async def test_tc_ac4_03_zero_concurrency_raises_before_execution(self):
        """TC-AC4-03: max_concurrency=0 raises LLMServiceError."""
        specs = [_make_spec("one")]

        with patch.object(
            self.service, "_call_llm_async_with_response", new=AsyncMock()
        ) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async(specs, max_concurrency=0)

            mock_call.assert_not_called()

    async def test_tc_ac4_03_negative_concurrency_raises_before_execution(self):
        """TC-AC4-03 edge: max_concurrency=-1 raises LLMServiceError."""
        specs = [_make_spec("one")]

        with patch.object(
            self.service, "_call_llm_async_with_response", new=AsyncMock()
        ) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async(specs, max_concurrency=-1)

            mock_call.assert_not_called()

    async def test_tc_ac4_03_concurrency_of_one_is_accepted_boundary(self):
        """TC-AC4-03 BVA: max_concurrency=1 is the valid lower boundary."""
        specs = [_make_spec("solo")]

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(return_value=("ok", None)),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "succeeded")


# ---------------------------------------------------------------------------
# AC-005  Concurrency cap
# ---------------------------------------------------------------------------


class TestAC005ConcurrencyCap(unittest.IsolatedAsyncioTestCase):
    """TC-AC5-01 and TC-AC5-02: never exceed caller-supplied concurrency cap."""

    def setUp(self):
        self.service = _make_service()

    async def test_tc_ac5_01_observed_max_in_flight_never_exceeds_cap(self):
        """TC-AC5-01: real-time in-flight count never exceeds max_concurrency=2."""
        cap = 2
        in_flight = [0]
        max_observed = [0]

        async def probe(*args, **kwargs):
            in_flight[0] += 1
            max_observed[0] = max(max_observed[0], in_flight[0])
            await asyncio.sleep(0.01)
            in_flight[0] -= 1
            return "ok", None

        specs = [_make_spec(f"s{i}") for i in range(5)]

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=probe),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=cap)

        self.assertLessEqual(max_observed[0], cap)
        self.assertEqual(len(results), 5)

    async def test_tc_ac5_01_sequential_cap_is_enforced(self):
        """TC-AC5-01 edge: max_concurrency=1 ensures fully sequential execution."""
        call_order = []

        async def record_call(*args, **kwargs):
            spec_id = kwargs.get("messages", [{}])[0].get("content", "?")
            call_order.append(spec_id)
            return "ok", None

        specs = [_make_spec(f"seq-{i}") for i in range(3)]

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=record_call),
        ):
            await self.service.call_llm_many_async(specs, max_concurrency=1)

        # All 3 must have been called exactly once, sequentially
        self.assertEqual(len(call_order), 3)

    async def test_tc_ac5_02_different_caps_do_not_change_result_correctness(self):
        """TC-AC5-02: changing cap changes parallelism but not result content."""
        specs = [_make_spec(f"item-{i}") for i in range(4)]

        async def echo(*args, **kwargs):
            messages = kwargs.get("messages", [])
            text = messages[0]["content"] if messages else "?"
            return text, None

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=echo),
        ):
            results_1 = await self.service.call_llm_many_async(specs, max_concurrency=1)

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=echo),
        ):
            results_3 = await self.service.call_llm_many_async(specs, max_concurrency=3)

        ids_1 = [r.spec_id for r in results_1]
        ids_3 = [r.spec_id for r in results_3]
        self.assertEqual(ids_1, ids_3)


# ---------------------------------------------------------------------------
# AC-006  Partial-failure completion semantics
# ---------------------------------------------------------------------------


class TestAC006PartialFailure(unittest.IsolatedAsyncioTestCase):
    """TC-AC6-01 and TC-AC6-02: one failure must not abort siblings."""

    def setUp(self):
        self.service = _make_service()

    async def test_tc_ac6_01_mixed_success_and_failure_returns_all_results(self):
        """TC-AC6-01: 3 specs with middle failing returns 3 terminal records."""
        specs = [_make_spec("ok-a"), _make_spec("fail-b"), _make_spec("ok-c")]

        async def mixed_response(*args, **kwargs):
            messages = kwargs.get("messages", [])
            content = messages[0]["content"] if messages else ""
            if "fail-b" in content:
                raise RuntimeError("provider error")
            return "success", None

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=mixed_response),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=3)

        self.assertEqual(len(results), 3)
        statuses = {r.spec_id: r.status for r in results}
        self.assertEqual(statuses["ok-a"], "succeeded")
        self.assertEqual(statuses["fail-b"], "failed")
        self.assertEqual(statuses["ok-c"], "succeeded")

    async def test_tc_ac6_01_submission_does_not_raise_after_item_failure(self):
        """TC-AC6-01: call_llm_many_async itself must not re-raise item exceptions."""
        specs = [_make_spec("always-fail")]

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            # Must not raise — returns a failure result instead
            results = await self.service.call_llm_many_async(specs, max_concurrency=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "failed")

    async def test_tc_ac6_02_slow_sibling_completes_after_fast_failure(self):
        """TC-AC6-02: slow success sibling still completes after fast failure."""
        specs = [_make_spec("fast-fail"), _make_spec("slow-ok")]

        async def behavior(*args, **kwargs):
            messages = kwargs.get("messages", [])
            content = messages[0]["content"] if messages else ""
            if "fast-fail" in content:
                raise RuntimeError("fast error")
            await asyncio.sleep(0.02)
            return "slow result", None

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=behavior),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=2)

        self.assertEqual(len(results), 2)
        statuses = {r.spec_id: r.status for r in results}
        self.assertEqual(statuses["fast-fail"], "failed")
        self.assertEqual(statuses["slow-ok"], "succeeded")
        self.assertEqual(results[1].content, "slow result")


# ---------------------------------------------------------------------------
# AC-007  Successful result normalization
# ---------------------------------------------------------------------------


class TestAC007SuccessNormalization(unittest.IsolatedAsyncioTestCase):
    """TC-AC7-01 and TC-AC7-02: normalized fields on successful results."""

    def setUp(self):
        self.service = _make_service()

    async def test_tc_ac7_01_succeeded_result_has_spec_id_status_and_content(self):
        """TC-AC7-01: successful result carries spec_id, status=succeeded, content."""
        spec = _make_spec("result-check", provider="openai", model="gpt-4o-mini")

        # _execute_fan_out_item calls _call_llm_async_with_response (the lower seam)
        # rather than call_llm_async so that raw response usage is accessible.
        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(return_value=("great answer", None)),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.spec_id, "result-check")
        self.assertEqual(r.status, "succeeded")
        self.assertEqual(r.content, "great answer")

    async def test_tc_ac7_01_succeeded_result_carries_provider_and_model(self):
        """TC-AC7-01: provider and model from the spec appear on the result."""
        spec = _make_spec("prov-check", provider="anthropic", model="claude-3-haiku")

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(return_value=("reply", None)),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.provider, "anthropic")
        self.assertEqual(r.model, "claude-3-haiku")

    async def test_tc_ac7_01_full_usage_metadata_is_normalized_onto_result(self):
        """TC-AC7-01 end-to-end: result.usage carries all token fields from raw response.

        Counter-factual: with usage=None hardcoded, result.usage would be None and
        the assertions below would fail.  This test MUST fail before the B-1 fix.
        """
        spec = _make_spec("usage-full", provider="anthropic", model="claude-3-haiku")

        # Construct a fake raw response object that carries usage_metadata with all
        # four token fields — the same shape a real Anthropic response returns.
        fake_response = Mock()
        fake_response.content = "answer with usage"
        fake_response.usage_metadata = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 20,
            "cache_read_input_tokens": 10,
        }

        # Drive via the new _call_llm_async_with_response seam that returns
        # (text, raw_response).  _execute_fan_out_item calls this seam rather
        # than call_llm_async so that it can extract usage from the raw response.
        async def fake_with_response(**kwargs):
            return ("answer with usage", fake_response)

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=fake_with_response),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "succeeded")
        self.assertEqual(r.content, "answer with usage")
        self.assertIsNotNone(
            r.usage, "result.usage must not be None when usage_metadata is present"
        )
        self.assertIsInstance(r.usage, LLMUsage)
        self.assertEqual(r.usage.input_tokens, 100)
        self.assertEqual(r.usage.output_tokens, 50)
        self.assertEqual(r.usage.cache_creation_input_tokens, 20)
        self.assertEqual(r.usage.cache_read_input_tokens, 10)

    async def test_tc_ac7_02_partial_usage_metadata_leaves_absent_fields_as_none(self):
        """TC-AC7-02 end-to-end: absent cache fields remain None; available fields are set.

        Counter-factual: with usage=None hardcoded, result.usage would be None
        and this test would fail.  It MUST fail before the B-1 fix.
        """
        spec = _make_spec("usage-partial", provider="openai", model="gpt-4o")

        fake_response = Mock()
        fake_response.content = "partial usage answer"
        # Only the base token counts present; cache fields absent.
        fake_response.usage_metadata = {
            "input_tokens": 80,
            "output_tokens": 30,
        }

        async def fake_with_response(**kwargs):
            return ("partial usage answer", fake_response)

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=fake_with_response),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "succeeded")
        self.assertIsNotNone(
            r.usage, "result.usage must not be None when usage_metadata is present"
        )
        self.assertIsInstance(r.usage, LLMUsage)
        self.assertEqual(r.usage.input_tokens, 80)
        self.assertEqual(r.usage.output_tokens, 30)
        # Absent fields must remain None rather than being fabricated.
        self.assertIsNone(r.usage.cache_creation_input_tokens)
        self.assertIsNone(r.usage.cache_read_input_tokens)


# ---------------------------------------------------------------------------
# AC-008  Failure result normalization
# ---------------------------------------------------------------------------


class TestAC008FailureNormalization(unittest.IsolatedAsyncioTestCase):
    """TC-AC8-01 and TC-AC8-02: structured error payload on failed results."""

    def setUp(self):
        self.service = _make_service()

    async def test_tc_ac8_01_provider_exception_becomes_structured_failure(self):
        """TC-AC8-01: exception from async path yields structured LLMExecutionError."""
        spec = _make_spec("fail-me")

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=RuntimeError("Connection timeout")),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.spec_id, "fail-me")
        self.assertEqual(r.status, "failed")
        self.assertIsNotNone(r.error)
        self.assertIsInstance(r.error.error_type, str)
        self.assertIsInstance(r.error.message, str)
        self.assertIn("Connection timeout", r.error.message)

    async def test_tc_ac8_02_failed_result_spec_id_is_preserved(self):
        """TC-AC8-02: spec_id is always present on the failure record."""
        spec = _make_spec("id-must-survive")

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=ValueError("routing failed")),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        self.assertEqual(results[0].spec_id, "id-must-survive")

    async def test_tc_ac8_02_unknown_provider_failure_does_not_fabricate_provider(self):
        """TC-AC8-02: provider=None spec stays None on failure, not a placeholder."""
        spec = LLMCallSpec(
            spec_id="no-provider",
            messages=[{"role": "user", "content": "hi"}],
            provider=None,
            routing_context={"routing_enabled": True},
        )

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=RuntimeError("routing error")),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "failed")
        self.assertIsNone(r.provider)


# ---------------------------------------------------------------------------
# AC-009  Cache-aware request pass-through
# ---------------------------------------------------------------------------


class TestAC009CacheAwarePassThrough(unittest.IsolatedAsyncioTestCase):
    """TC-AC9-01 and TC-AC9-02: cache-aware fields survive the fan-out layer."""

    def setUp(self):
        self.service = _make_service()

    async def test_tc_ac9_01_messages_and_request_options_reach_call_llm_async(self):
        """TC-AC9-01: messages and request_options from spec are forwarded unchanged."""
        structured_messages = [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        ]
        cache_options = {"requires_prompt_caching": True, "cache_mode": "ephemeral"}
        spec = LLMCallSpec(
            spec_id="cache-spec",
            messages=structured_messages,
            provider="anthropic",
            request_options=cache_options,
        )

        captured_kwargs = {}

        async def capture_call(**kwargs):
            captured_kwargs.update(kwargs)
            return "cached response", None

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=capture_call),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        # messages passed through unchanged
        self.assertEqual(captured_kwargs.get("messages"), structured_messages)
        # cache-aware request_options are forwarded as kwargs
        self.assertTrue(captured_kwargs.get("requires_prompt_caching"))
        self.assertEqual(results[0].status, "succeeded")

    async def test_tc_ac9_02_unsupported_cache_failure_captured_as_item_error(self):
        """TC-AC9-02: unsupported cache mode error is captured as failure record."""
        specs = [
            _make_spec("ok-sibling"),
            LLMCallSpec(
                spec_id="bad-cache",
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
                request_options={"requires_prompt_caching": True},
            ),
        ]

        async def raise_for_cache(**kwargs):
            if kwargs.get("requires_prompt_caching"):
                raise LLMServiceError("Provider does not support prompt caching")
            return "ok", None

        with patch.object(
            self.service,
            "_call_llm_async_with_response",
            new=AsyncMock(side_effect=raise_for_cache),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=2)

        statuses = {r.spec_id: r.status for r in results}
        self.assertEqual(statuses["ok-sibling"], "succeeded")
        self.assertEqual(statuses["bad-cache"], "failed")


# ---------------------------------------------------------------------------
# _extract_llm_usage helper unit tests
# ---------------------------------------------------------------------------


class TestExtractLlmUsage(unittest.TestCase):
    """Unit tests for the _extract_llm_usage normalizer."""

    def test_returns_none_when_no_usage_metadata(self):
        response = Mock(spec=[])  # no usage_metadata attribute
        result = LLMService._extract_llm_usage(response)
        self.assertIsNone(result)

    def test_returns_llm_usage_with_all_fields_from_dict(self):
        response = Mock()
        response.usage_metadata = {
            "input_tokens": 10,
            "output_tokens": 20,
            "cache_creation_input_tokens": 5,
            "cache_read_input_tokens": 3,
        }
        result = LLMService._extract_llm_usage(response)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, LLMUsage)
        self.assertEqual(result.input_tokens, 10)
        self.assertEqual(result.output_tokens, 20)
        self.assertEqual(result.cache_creation_input_tokens, 5)
        self.assertEqual(result.cache_read_input_tokens, 3)

    def test_absent_cache_fields_remain_none(self):
        response = Mock()
        response.usage_metadata = {"input_tokens": 8, "output_tokens": 12}
        result = LLMService._extract_llm_usage(response)
        self.assertIsNotNone(result)
        self.assertEqual(result.input_tokens, 8)
        self.assertIsNone(result.cache_creation_input_tokens)
        self.assertIsNone(result.cache_read_input_tokens)

    def test_returns_llm_usage_from_object_with_attributes(self):
        usage = Mock()
        usage.input_tokens = 15
        usage.output_tokens = 25
        usage.cache_creation_input_tokens = None
        usage.cache_read_input_tokens = None
        response = Mock()
        response.usage_metadata = usage
        result = LLMService._extract_llm_usage(response)
        self.assertIsNotNone(result)
        self.assertEqual(result.input_tokens, 15)
        self.assertEqual(result.output_tokens, 25)


if __name__ == "__main__":
    unittest.main()
