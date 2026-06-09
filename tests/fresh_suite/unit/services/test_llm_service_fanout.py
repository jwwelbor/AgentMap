"""
Fan-out tests for LLMService.call_llm_many_async.

Covers AC-001 through AC-009 from the E05-F02 test plan:
  AC-001: Protocol surface (TC-AC1-01, TC-AC1-02)
  AC-002: One result per spec (TC-AC2-01, TC-AC2-02)
  AC-003: Stable ordering (TC-AC3-01, TC-AC3-02)
  AC-004: Submission validation (TC-AC4-01, TC-AC4-02, TC-AC4-03)
  AC-005: Concurrency cap (TC-AC5-01, TC-AC5-02)
  AC-006: Partial-failure completion (TC-AC6-01, TC-AC6-02)
  AC-007: Successful result normalization (TC-AC7-01 – TC-AC7-04)
  AC-008: Failure result normalization (TC-AC8-01, TC-AC8-02, TC-AC8-03, TC-AC8-04)
  AC-009: Cache-aware request pass-through (TC-AC9-01, TC-AC9-02)

Seam convention (post-rework):
  - Tests patch ``_invoke_with_resilience_async`` as the lowest allowed mock seam.
  - ``call_llm_async`` is the fan-out entry point; ``_call_llm_async_core`` is
    the single private seam both the public method and fan-out share.
  - The deleted ``_call_llm_async_with_response`` seam MUST NOT appear here.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, create_autospec, patch

from agentmap.exceptions import LLMServiceError
from agentmap.exceptions.service_exceptions import LLMResolvedCallError
from agentmap.models.llm_execution import (
    LLMFanoutResult,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)
from agentmap.services.llm_service import LLMService
from agentmap.services.protocols import LLMServiceProtocol
from tests.utils.mock_service_factory import MockServiceFactory

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_spec(request_id: str, provider: str = "openai", **kwargs) -> LLMRequest:
    """Factory for minimal test LLMRequest instances."""
    return LLMRequest(
        request_id=request_id,
        messages=[{"role": "user", "content": f"prompt for {request_id}"}],
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


def _llm_response(
    text: str,
    provider: str = "openai",
    model: str = "openai-default-model",
    usage: LLMUsage = None,
) -> LLMResponse:
    """Build a minimal LLMResponse for test stubs."""
    return LLMResponse(
        text=text,
        resolved_provider=provider,
        resolved_model=model,
        usage=usage,
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
            "call_llm_async",
            new=AsyncMock(return_value=_llm_response("response")),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=2)

        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIsInstance(result, LLMFanoutResult)
            self.assertEqual(result.status, "succeeded")

    async def test_tc_ac2_01_single_spec_returns_single_result(self):
        """TC-AC2-01 edge: single-item submission returns one result."""
        specs = [_make_spec("only-one")]

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(return_value=_llm_response("hello")),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].request_id, "only-one")
        self.assertEqual(results[0].text, "hello")

    async def test_tc_ac2_02_large_submission_has_no_dropped_or_duplicated_results(
        self,
    ):
        """TC-AC2-02: 100 specs with concurrency=8 yield exactly 100 results."""
        specs = [_make_spec(f"bulk-{i}") for i in range(100)]

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(return_value=_llm_response("ok")),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=8)

        self.assertEqual(len(results), 100)
        returned_ids = [r.request_id for r in results]
        self.assertEqual(len(set(returned_ids)), 100)
        for spec in specs:
            self.assertIn(spec.request_id, returned_ids)


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
            return _llm_response(f"response-{idx}")

        specs = [_make_spec("spec-a"), _make_spec("spec-b"), _make_spec("spec-c")]

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=ordered_response),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=3)

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].request_id, "spec-a")
        self.assertEqual(results[1].request_id, "spec-b")
        self.assertEqual(results[2].request_id, "spec-c")

    async def test_tc_ac3_02_each_result_carries_original_request_id(self):
        """TC-AC3-02: each result's request_id matches its originating spec."""
        specs = [_make_spec("id-first"), _make_spec("id-second")]

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(return_value=_llm_response("content")),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=2)

        self.assertEqual(results[0].request_id, "id-first")
        self.assertEqual(results[1].request_id, "id-second")


# ---------------------------------------------------------------------------
# AC-004  Submission validation
# ---------------------------------------------------------------------------


class TestAC004SubmissionValidation(unittest.IsolatedAsyncioTestCase):
    """TC-AC4-01, TC-AC4-02, TC-AC4-03: validation before execution."""

    def setUp(self):
        self.service = _make_service()

    async def test_tc_ac4_01_empty_requests_raises_before_execution(self):
        """TC-AC4-01: empty requests must raise LLMServiceError."""
        with patch.object(self.service, "call_llm_async", new=AsyncMock()) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async([], max_concurrency=1)

            mock_call.assert_not_called()

    async def test_tc_ac4_02_duplicate_request_id_raises_before_execution(self):
        """TC-AC4-02: duplicate request_id raises LLMServiceError before execution."""
        specs = [_make_spec("dup-1"), _make_spec("dup-1")]

        with patch.object(self.service, "call_llm_async", new=AsyncMock()) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async(specs, max_concurrency=2)

            mock_call.assert_not_called()

    async def test_tc_ac4_02_duplicate_request_id_separated_in_large_list(self):
        """TC-AC4-02 edge: duplicates separated in a large list are still caught."""
        specs = [_make_spec(f"item-{i}") for i in range(20)]
        specs.append(_make_spec("item-5"))  # duplicate at the end

        with patch.object(self.service, "call_llm_async", new=AsyncMock()) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async(specs, max_concurrency=4)

            mock_call.assert_not_called()

    async def test_tc_ac4_03_zero_concurrency_raises_before_execution(self):
        """TC-AC4-03: max_concurrency=0 raises LLMServiceError."""
        specs = [_make_spec("one")]

        with patch.object(self.service, "call_llm_async", new=AsyncMock()) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async(specs, max_concurrency=0)

            mock_call.assert_not_called()

    async def test_tc_ac4_03_negative_concurrency_raises_before_execution(self):
        """TC-AC4-03 edge: max_concurrency=-1 raises LLMServiceError."""
        specs = [_make_spec("one")]

        with patch.object(self.service, "call_llm_async", new=AsyncMock()) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async(specs, max_concurrency=-1)

            mock_call.assert_not_called()

    async def test_tc_ac4_03_concurrency_of_one_is_accepted_boundary(self):
        """TC-AC4-03 BVA: max_concurrency=1 is the valid lower boundary."""
        specs = [_make_spec("solo")]

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(return_value=_llm_response("ok")),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "succeeded")

    async def test_tc_ac4_03_bool_concurrency_is_rejected(self):
        """LOW-1: max_concurrency=True is rejected even though bool is int subclass."""
        specs = [_make_spec("one")]

        with patch.object(self.service, "call_llm_async", new=AsyncMock()) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async(specs, max_concurrency=True)

            mock_call.assert_not_called()

    async def test_tc_ac4_02_non_string_request_id_raises_before_execution(self):
        """MEDIUM-1: request_id=123 (non-string) raises LLMServiceError before execution."""
        spec = LLMRequest(
            request_id=123,  # type: ignore[arg-type]
            messages=[{"role": "user", "content": "hi"}],
        )
        with patch.object(self.service, "call_llm_async", new=AsyncMock()) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async([spec], max_concurrency=1)

            mock_call.assert_not_called()

    async def test_tc_ac4_02_empty_string_request_id_raises_before_execution(self):
        """MEDIUM-1: request_id="" (empty string) raises LLMServiceError before execution."""
        spec = LLMRequest(
            request_id="",
            messages=[{"role": "user", "content": "hi"}],
        )
        with patch.object(self.service, "call_llm_async", new=AsyncMock()) as mock_call:
            with self.assertRaises(LLMServiceError):
                await self.service.call_llm_many_async([spec], max_concurrency=1)

            mock_call.assert_not_called()


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
            return _llm_response("ok")

        specs = [_make_spec(f"s{i}") for i in range(5)]

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=probe),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=cap)

        self.assertLessEqual(max_observed[0], cap)
        self.assertEqual(len(results), 5)

    async def test_tc_ac5_01_sequential_cap_is_enforced(self):
        """TC-AC5-01 edge: max_concurrency=1 ensures fully sequential execution."""
        call_order = []

        async def record_call(*args, **kwargs):
            messages = kwargs.get("messages", [{}])
            content = messages[0].get("content", "?") if messages else "?"
            call_order.append(content)
            return _llm_response("ok")

        specs = [_make_spec(f"seq-{i}") for i in range(3)]

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=record_call),
        ):
            await self.service.call_llm_many_async(specs, max_concurrency=1)

        self.assertEqual(len(call_order), 3)

    async def test_tc_ac5_02_different_caps_do_not_change_result_correctness(self):
        """TC-AC5-02: changing cap changes parallelism but not result content."""
        specs = [_make_spec(f"item-{i}") for i in range(4)]

        async def echo(*args, **kwargs):
            messages = kwargs.get("messages", [])
            text = messages[0]["content"] if messages else "?"
            return _llm_response(text)

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=echo),
        ):
            results_1 = await self.service.call_llm_many_async(specs, max_concurrency=1)

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=echo),
        ):
            results_3 = await self.service.call_llm_many_async(specs, max_concurrency=3)

        ids_1 = [r.request_id for r in results_1]
        ids_3 = [r.request_id for r in results_3]
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
            return _llm_response("success")

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=mixed_response),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=3)

        self.assertEqual(len(results), 3)
        statuses = {r.request_id: r.status for r in results}
        self.assertEqual(statuses["ok-a"], "succeeded")
        self.assertEqual(statuses["fail-b"], "failed")
        self.assertEqual(statuses["ok-c"], "succeeded")

    async def test_tc_ac6_01_submission_does_not_raise_after_item_failure(self):
        """TC-AC6-01: call_llm_many_async itself must not re-raise item exceptions."""
        specs = [_make_spec("always-fail")]

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
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
            return _llm_response("slow result")

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=behavior),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=2)

        self.assertEqual(len(results), 2)
        statuses = {r.request_id: r.status for r in results}
        self.assertEqual(statuses["fast-fail"], "failed")
        self.assertEqual(statuses["slow-ok"], "succeeded")
        self.assertEqual(results[1].text, "slow result")


# ---------------------------------------------------------------------------
# AC-007  Successful result normalization
# ---------------------------------------------------------------------------


class TestAC007SuccessNormalization(unittest.IsolatedAsyncioTestCase):
    """TC-AC7-01 through TC-AC7-04: normalized fields on successful results."""

    def setUp(self):
        self.service = _make_service()

    async def test_tc_ac7_01_succeeded_result_has_request_id_status_and_content(self):
        """TC-AC7-01: successful result carries request_id, status=succeeded, content."""
        spec = _make_spec("result-check", provider="openai", model="gpt-4o-mini")

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(
                return_value=_llm_response(
                    "great answer", provider="openai", model="gpt-4o-mini"
                )
            ),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.request_id, "result-check")
        self.assertEqual(r.status, "succeeded")
        self.assertEqual(r.text, "great answer")

    async def test_tc_ac7_01_succeeded_result_carries_resolved_provider_and_model(self):
        """TC-AC7-01: result.provider/model carry resolved values from LLMResponse."""
        spec = _make_spec("prov-check", provider="anthropic", model="claude-3-haiku")

        # Return a response where the resolved provider/model match what was requested
        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(
                return_value=_llm_response(
                    "reply", provider="anthropic", model="claude-3-haiku"
                )
            ),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.resolved_provider, "anthropic")
        self.assertEqual(r.resolved_model, "claude-3-haiku")

    async def test_tc_ac7_01_full_usage_metadata_is_normalized_onto_result(self):
        """TC-AC7-01 end-to-end: result.usage carries all token fields.

        Counter-factual: if usage is not propagated from LLMResponse, result.usage
        would be None and the assertions below would fail.
        """
        spec = _make_spec("usage-full", provider="anthropic", model="claude-3-haiku")

        usage = LLMUsage(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=20,
            cache_read_input_tokens=10,
        )
        llm_resp = LLMResponse(
            text="answer with usage",
            resolved_provider="anthropic",
            resolved_model="claude-3-haiku",
            usage=usage,
        )

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(return_value=llm_resp),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "succeeded")
        self.assertEqual(r.text, "answer with usage")
        self.assertIsNotNone(
            r.usage, "result.usage must not be None when LLMResponse.usage is set"
        )
        self.assertIsInstance(r.usage, LLMUsage)
        self.assertEqual(r.usage.input_tokens, 100)
        self.assertEqual(r.usage.output_tokens, 50)
        self.assertEqual(r.usage.cache_creation_input_tokens, 20)
        self.assertEqual(r.usage.cache_read_input_tokens, 10)

    async def test_tc_ac7_02_partial_usage_metadata_leaves_absent_fields_as_none(self):
        """TC-AC7-02 end-to-end: absent cache fields remain None; available fields set.

        Counter-factual: if LLMResponse.usage is ignored, result.usage is None.
        """
        spec = _make_spec("usage-partial", provider="openai", model="gpt-4o")

        usage = LLMUsage(input_tokens=80, output_tokens=30)
        llm_resp = LLMResponse(
            text="partial usage answer",
            resolved_provider="openai",
            resolved_model="gpt-4o",
            usage=usage,
        )

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(return_value=llm_resp),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "succeeded")
        self.assertIsNotNone(r.usage)
        self.assertIsInstance(r.usage, LLMUsage)
        self.assertEqual(r.usage.input_tokens, 80)
        self.assertEqual(r.usage.output_tokens, 30)
        self.assertIsNone(r.usage.cache_creation_input_tokens)
        self.assertIsNone(r.usage.cache_read_input_tokens)

    async def test_tc_ac7_03_routed_success_returns_resolved_provider_model_and_usage(
        self,
    ):
        """TC-AC7-03: routed success result.provider/model/usage reflect routing decision.

        Counter-factual: if result echoes spec.provider/spec.model instead of resolved
        values, result.provider == "openai" and result.model == "gpt-4o-mini" would pass
        but result.provider == "anthropic" would fail.

        Lowest allowed mock seam: ``_invoke_with_resilience_async``.
        Forbidden: ``_call_llm_async_with_response`` (deleted).
        """
        # Spec requests openai/gpt-4o-mini but routing redirects to anthropic.
        spec = LLMRequest(
            request_id="routed-item",
            messages=[{"role": "user", "content": "hello"}],
            provider="openai",
            model="gpt-4o-mini",
            routing_context={"routing_enabled": True, "task_type": "general"},
        )

        # Mock the routing decision to select anthropic.
        mock_decision = Mock()
        mock_decision.provider = "anthropic"
        mock_decision.model = "claude-haiku"
        mock_decision.complexity = "low"
        mock_decision.confidence = 0.9
        mock_decision.max_tokens = None
        mock_decision.cache_hit = False
        mock_decision.fallback_used = False
        self.service.routing_service.route_request.return_value = mock_decision

        # Stub the provider utils so the direct call resolves.
        self.service._provider_utils.normalize_provider = Mock(side_effect=lambda p: p)
        self.service._provider_utils.get_provider_config = Mock(
            return_value={"model": "claude-haiku", "api_key": "test"}
        )
        self.service._provider_utils.get_available_providers = Mock(
            return_value=["openai", "anthropic"]
        )
        self.service._message_utils.extract_prompt_from_messages = Mock(
            return_value="hello"
        )
        self.service._message_utils.convert_messages_to_langchain = Mock(
            return_value=[Mock()]
        )

        # Build a fake raw response with usage_metadata.
        fake_raw_response = Mock()
        fake_raw_response.content = "routed answer"
        fake_raw_response.usage_metadata = {
            "input_tokens": 55,
            "output_tokens": 15,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 5,
        }
        fake_raw_response.response_metadata = {}

        # Stub _invoke_with_resilience_async — the lowest allowed mock seam.
        # It returns LLMResponse with the resolved provider/model/usage.
        expected_usage = LLMService._extract_llm_usage(fake_raw_response)
        expected_response = LLMResponse(
            text="routed answer",
            resolved_provider="anthropic",
            resolved_model="claude-haiku",
            usage=expected_usage,
        )

        with patch.object(
            self.service,
            "_invoke_with_resilience_async",
            new=AsyncMock(return_value=expected_response),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "succeeded")
        self.assertEqual(r.text, "routed answer")

        # Result must reflect the routing decision, NOT the spec values.
        self.assertEqual(
            r.resolved_provider,
            "anthropic",
            "provider must be the routed provider, not spec.provider='openai'",
        )
        self.assertEqual(
            r.resolved_model,
            "claude-haiku",
            "model must be the routed model, not spec.model='gpt-4o-mini'",
        )

        # Usage must be populated from the routed response.
        self.assertIsNotNone(r.usage, "usage must be populated for routed success")
        self.assertEqual(r.usage.input_tokens, 55)
        self.assertEqual(r.usage.output_tokens, 15)
        self.assertEqual(r.usage.cache_read_input_tokens, 5)

    async def test_tc_ac7_04_fallback_success_returns_fallback_tier_provider_model_usage(
        self,
    ):
        """TC-AC7-04: fallback success result.provider/model/usage reflect fallback tier.

        Counter-factual: if result echoes spec.provider/spec.model, assertions on
        the fallback provider/model would fail.

        Lowest allowed mock seam: ``_invoke_with_resilience_async``.
        Forbidden: ``_call_llm_async_with_response`` (deleted).
        """
        spec = _make_spec("fallback-item", provider="openai", model="gpt-4o-mini")

        # Set up fallback handler dependencies.
        mock_features_registry = Mock()
        mock_features_registry.is_provider_available.return_value = True
        mock_routing_config = Mock()
        mock_routing_config.fallback = {"default_provider": "anthropic"}
        mock_routing_config.routing_matrix = {
            "anthropic": {"low": "claude-haiku"},
            "openai": {"low": "gpt-3.5-turbo"},
        }

        service = LLMService(
            configuration=MockServiceFactory.create_mock_app_config_service(),
            logging_service=MockServiceFactory.create_mock_logging_service(),
            routing_service=Mock(),
            llm_models_config_service=MockServiceFactory.create_mock_llm_models_config_service(),
            features_registry_service=mock_features_registry,
            routing_config_service=mock_routing_config,
        )
        # Configure resilience to 1 attempt so the primary always fails.
        service._resilience_config = {
            "retry": {
                "max_attempts": 1,
                "backoff_base": 2.0,
                "backoff_max": 30.0,
                "jitter": False,
            },
            "circuit_breaker": {"failure_threshold": 5, "reset_timeout": 60},
        }

        service._provider_utils.normalize_provider = Mock(side_effect=lambda p: p)
        service._provider_utils.get_provider_config = Mock(
            side_effect=lambda p: {"model": f"{p}-default", "api_key": "test"}
        )
        service._message_utils.convert_messages_to_langchain = Mock(
            return_value=[Mock()]
        )
        service._client_factory.get_or_create_client = Mock(return_value=Mock())

        # _invoke_with_resilience_async fails for openai (primary), succeeds for
        # anthropic:claude-haiku (tier-1 fallback), returning LLMResponse.
        fallback_usage = LLMUsage(input_tokens=30, output_tokens=10)
        fallback_response = LLMResponse(
            text="fallback answer",
            resolved_provider="anthropic",
            resolved_model="claude-haiku",
            usage=fallback_usage,
        )

        call_count = [0]

        async def invoke_side_effect(client, msgs, provider, model):
            call_count[0] += 1
            if provider == "openai":
                raise RuntimeError("primary failed")
            return fallback_response

        with patch.object(
            service,
            "_invoke_with_resilience_async",
            new=AsyncMock(side_effect=invoke_side_effect),
        ):
            results = await service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "succeeded")
        self.assertEqual(r.text, "fallback answer")

        # Must reflect the fallback tier, not spec.provider.
        self.assertEqual(
            r.resolved_provider,
            "anthropic",
            "provider must be the fallback provider, not spec.provider='openai'",
        )
        self.assertEqual(
            r.resolved_model,
            "claude-haiku",
            "model must be the fallback model",
        )

        # Usage must be populated from the fallback tier response.
        self.assertIsNotNone(r.usage, "usage must be populated for fallback success")
        self.assertEqual(r.usage.input_tokens, 30)
        self.assertEqual(r.usage.output_tokens, 10)


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
            "call_llm_async",
            new=AsyncMock(side_effect=RuntimeError("Connection timeout")),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.request_id, "fail-me")
        self.assertEqual(r.status, "failed")
        self.assertIsNotNone(r.error)
        self.assertIsInstance(r.error.error_type, str)
        self.assertIsInstance(r.error.message, str)
        self.assertIn("Connection timeout", r.error.message)

    async def test_tc_ac8_02_failed_result_request_id_is_preserved(self):
        """TC-AC8-02: request_id is always present on the failure record."""
        spec = _make_spec("id-must-survive")

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=ValueError("routing failed")),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        self.assertEqual(results[0].request_id, "id-must-survive")

    async def test_tc_ac8_02_unknown_provider_failure_does_not_fabricate_provider(self):
        """TC-AC8-02: provider=None spec stays None on failure, not a placeholder."""
        spec = LLMRequest(
            request_id="no-provider",
            messages=[{"role": "user", "content": "hi"}],
            provider=None,
            routing_context={"routing_enabled": True},
        )

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=RuntimeError("routing error")),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "failed")
        self.assertIsNone(r.resolved_provider)

    async def test_tc_ac8_01_error_message_is_sanitized(self):
        """LOW-2: error message is sanitized — raw exception detail passed through
        _sanitize_error_message so any API key-like substring is redacted."""
        spec = _make_spec("sanitize-me")

        # _sanitize_error_message redacts long opaque token-looking strings.
        raw_exc = RuntimeError(
            "Error: sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        )
        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=raw_exc),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "failed")
        self.assertNotIn(
            "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            r.error.message,
            "API key-like token must be redacted from error message",
        )


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
        spec = LLMRequest(
            request_id="cache-spec",
            messages=structured_messages,
            provider="anthropic",
            request_options=cache_options,
        )

        captured_kwargs = {}

        async def capture_call(**kwargs):
            captured_kwargs.update(kwargs)
            return _llm_response("cached response", provider="anthropic")

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=capture_call),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        self.assertEqual(captured_kwargs.get("messages"), structured_messages)
        self.assertTrue(captured_kwargs.get("requires_prompt_caching"))
        self.assertEqual(results[0].status, "succeeded")

    async def test_tc_ac9_02_unsupported_cache_failure_captured_as_item_error(self):
        """TC-AC9-02: unsupported cache mode error is captured as failure record."""
        specs = [
            _make_spec("ok-sibling"),
            LLMRequest(
                request_id="bad-cache",
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
                request_options={"requires_prompt_caching": True},
            ),
        ]

        async def raise_for_cache(**kwargs):
            if kwargs.get("requires_prompt_caching"):
                raise LLMServiceError("Provider does not support prompt caching")
            return _llm_response("ok")

        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=raise_for_cache),
        ):
            results = await self.service.call_llm_many_async(specs, max_concurrency=2)

        statuses = {r.request_id: r.status for r in results}
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

    def test_malformed_usage_metadata_field_returns_none_for_that_field(self):
        """MEDIUM-2: non-numeric token value must not convert a success into a failure.

        Counter-factual: if int("not-a-number") raises and is not caught, _extract_llm_usage
        would raise instead of returning a partial LLMUsage, causing _execute_fan_out_item's
        broad except to classify the successful call as status='failed'.
        """
        response = Mock()
        response.usage_metadata = {
            "input_tokens": "not-a-number",
            "output_tokens": 20,
        }
        # Must NOT raise — malformed field returns None for that slot.
        result = LLMService._extract_llm_usage(response)
        self.assertIsNotNone(
            result, "LLMUsage must be returned even when a field is malformed"
        )
        self.assertIsNone(
            result.input_tokens,
            "malformed input_tokens must be None, not an exception",
        )
        self.assertEqual(result.output_tokens, 20)

    def test_malformed_usage_metadata_all_fields_returns_llm_usage_with_all_none(self):
        """MEDIUM-2: fully malformed metadata still returns LLMUsage (not None)."""
        response = Mock()
        response.usage_metadata = {
            "input_tokens": [1, 2],
            "output_tokens": {"key": "val"},
        }
        result = LLMService._extract_llm_usage(response)
        self.assertIsNotNone(result)
        self.assertIsNone(result.input_tokens)
        self.assertIsNone(result.output_tokens)


# ---------------------------------------------------------------------------
# AC-008  Failure result normalization — Round-2 addendum (TC-AC8-03/04)
# ---------------------------------------------------------------------------


class TestAC008FailureNormalizationRound2(unittest.IsolatedAsyncioTestCase):
    """TC-AC8-03 and TC-AC8-04: resolved identity preserved on failure after resolution.

    Round-2 UAT addendum: when routing or fallback selects a concrete
    (provider, model) before execution fails, the failure record must carry
    that resolved identity — not spec.provider/spec.model (which may be None).

    Seam: patch ``_invoke_with_resilience_async`` (same seam as TC-AC7-03/04).
    Forbidden: do NOT patch ``call_llm_async`` itself — that mocks out the
    routing/fallback layer where the resolved identity lives.
    """

    def _make_routed_service(
        self,
        routed_provider: str = "anthropic",
        routed_model: str = "claude-haiku",
    ) -> LLMService:
        """Build a service wired to route to the given provider/model."""
        service = _make_service()
        mock_decision = Mock()
        mock_decision.provider = routed_provider
        mock_decision.model = routed_model
        mock_decision.complexity = "low"
        mock_decision.confidence = 0.9
        mock_decision.max_tokens = None
        mock_decision.cache_hit = False
        mock_decision.fallback_used = False
        service.routing_service.route_request.return_value = mock_decision

        service._provider_utils.normalize_provider = Mock(side_effect=lambda p: p)
        service._provider_utils.get_provider_config = Mock(
            return_value={"model": routed_model, "api_key": "test"}
        )
        service._provider_utils.get_available_providers = Mock(
            return_value=["openai", routed_provider]
        )
        service._message_utils.extract_prompt_from_messages = Mock(return_value="hello")
        service._message_utils.convert_messages_to_langchain = Mock(
            return_value=[Mock()]
        )
        service._client_factory.get_or_create_client = Mock(return_value=Mock())
        return service

    async def test_tc_ac8_03_routed_failure_preserves_resolved_provider_and_model(self):
        """TC-AC8-03: when routing resolves to a provider before failure, the failure
        record reflects the resolved identity, not spec.provider/spec.model.

        Counter-factual: against the pre-round-2 code (no LLMResolvedCallError), the
        bare ``except Exception`` in ``_execute_fan_out_item`` populates
        ``provider=spec.provider=None`` and the assertion ``r.provider == "google"``
        FAILS.

        Discrimination fix (round-3 UAT): routed_provider="google" is deliberately
        DIFFERENT from the routing fallback default ("anthropic"). If the routing
        handler swallows LLMResolvedCallError and retries via fallback_provider, the
        assertion ``r.provider == "google"`` fails (it would be "anthropic" instead),
        exposing the bug. With routed_provider="anthropic" (the old value), the test
        passed coincidentally because both paths produce the same identity.

        Lowest allowed mock seam: ``_invoke_with_resilience_async``.
        Forbidden: ``call_llm_async`` (mocks out routing where identity is resolved).
        """
        # Spec with provider=None triggers routing; routing resolves to google:gemini-pro.
        # "google" is intentionally different from the routing fallback default "anthropic".
        spec = LLMRequest(
            request_id="routed-fail",
            messages=[{"role": "user", "content": "hello"}],
            provider=None,
            routing_context={"routing_enabled": True, "task_type": "general"},
        )
        service = self._make_routed_service(
            routed_provider="google", routed_model="gemini-pro"
        )

        from agentmap.exceptions.service_exceptions import LLMProviderError

        # _invoke_with_resilience_async raises — simulates a provider call that fails
        # after routing resolved the concrete provider/model.
        with patch.object(
            service,
            "_invoke_with_resilience_async",
            new=AsyncMock(
                side_effect=LLMProviderError("simulated timeout after routing")
            ),
        ):
            results = await service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.request_id, "routed-fail")
        self.assertEqual(r.status, "failed")
        self.assertEqual(
            r.resolved_provider,
            "google",
            "provider must be the routing-resolved provider 'google', not the "
            "fallback default 'anthropic' — if this is 'anthropic', the routing "
            "handler is swallowing LLMResolvedCallError and re-routing",
        )
        self.assertEqual(
            r.resolved_model,
            "gemini-pro",
            "model must be the routing-resolved model, not spec.model=None",
        )
        self.assertIsNotNone(r.error)
        self.assertEqual(r.error.error_type, "LLMProviderError")

    async def test_tc_ac8_04_fallback_exhaustion_preserves_last_tier_identity(self):
        """TC-AC8-04: when all fallback tiers fail, the result reflects the last-attempted
        tier's provider/model — not spec.provider/spec.model.

        Counter-factual: against the pre-round-2 code, the bare ``except Exception``
        block uses ``spec.provider`` (e.g., "openai") and the assertion
        ``r.provider == "google"`` FAILS (would be "openai" instead).

        Three-tier exhaustion (round-3 UAT fix): wires three providers so
        _try_tier3_fallback_async actually runs. The tier-3 helper skips
        original_provider ("openai") and configured_fallback_provider ("anthropic"),
        so "google" is the only provider tier-3 can select. Asserting
        r.provider == "google" proves tier 3 actually executed.

        Lowest allowed mock seam: ``_invoke_with_resilience_async``.
        Forbidden: ``call_llm_async`` (mocks out the fallback ladder).
        """
        mock_features_registry = Mock()
        mock_features_registry.is_provider_available.return_value = True
        # Three providers: openai (original), anthropic (tier-2 fallback), google (tier-3).
        mock_features_registry.get_available_providers.return_value = [
            "openai",
            "anthropic",
            "google",
        ]
        mock_routing_config = Mock()
        mock_routing_config.fallback = {"default_provider": "anthropic"}
        mock_routing_config.routing_matrix = {
            "anthropic": {"low": "claude-haiku"},
            "openai": {"low": "gpt-3.5-turbo"},
            "google": {"low": "gemini-flash"},
        }

        service = LLMService(
            configuration=MockServiceFactory.create_mock_app_config_service(),
            logging_service=MockServiceFactory.create_mock_logging_service(),
            routing_service=Mock(),
            llm_models_config_service=MockServiceFactory.create_mock_llm_models_config_service(),
            features_registry_service=mock_features_registry,
            routing_config_service=mock_routing_config,
        )
        service._resilience_config = {
            "retry": {
                "max_attempts": 1,
                "backoff_base": 2.0,
                "backoff_max": 30.0,
                "jitter": False,
            },
            "circuit_breaker": {"failure_threshold": 5, "reset_timeout": 60},
        }
        service._provider_utils.normalize_provider = Mock(side_effect=lambda p: p)
        service._provider_utils.get_provider_config = Mock(
            side_effect=lambda p: {"model": f"{p}-default", "api_key": "test"}
        )
        service._message_utils.convert_messages_to_langchain = Mock(
            return_value=[Mock()]
        )
        service._client_factory.get_or_create_client = Mock(return_value=Mock())

        spec = _make_spec("fallback-exhaust", provider="openai", model="gpt-4o")

        # All invocations fail — forces exhaustion through all tiers.
        # The last tier attempted through the fallback ladder will be the one
        # whose identity should appear in the failure record.
        with patch.object(
            service,
            "_invoke_with_resilience_async",
            new=AsyncMock(side_effect=RuntimeError("all providers down")),
        ):
            results = await service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.request_id, "fallback-exhaust")
        self.assertEqual(r.status, "failed")
        # Tier 3 is the last tier — it selects "google" (skipping "openai" and
        # "anthropic"). r.provider must be "google", not spec.provider="openai".
        # If this is "openai", the fallback ladder identity is not propagating.
        # If this is "anthropic", tier-3 isn't running (only 2-provider test issue).
        self.assertEqual(
            r.resolved_provider,
            "google",
            "provider must be 'google' (tier-3 provider) — not 'openai' (spec.provider) "
            "and not 'anthropic' (tier-2 provider). 'openai' means last_attempted is "
            "not propagating. 'anthropic' means tier-3 never executed.",
        )
        self.assertEqual(
            r.resolved_model,
            "gemini-flash",
            "model must be 'gemini-flash' (tier-3 google's fallback model from routing_matrix)",
        )
        self.assertIsNotNone(r.error)

    async def test_tc_ac8_06_routed_failure_must_not_rewrite_identity(self):
        """TC-AC8-06 (NEW — round-3): routed post-resolution failure MUST NOT be
        swallowed by routing's broad except-Exception and rewritten with the
        fallback-provider identity.

        Counter-factual: against pre-fix code, _call_llm_async_with_routing catches
        LLMResolvedCallError from the routed call (line 786 'except Exception'), logs
        it as "Routing failed", then re-attempts via fallback_provider="anthropic".
        That second attempt also raises (same mock), producing a NEW
        LLMResolvedCallError("anthropic", ...). The fan-out result would have
        r.provider == "anthropic" instead of the originally-routed "google", and
        this assertion FAILS.

        After fix (except LLMResolvedCallError: raise inserted before except Exception):
        the routed LLMResolvedCallError propagates intact with provider="google".

        Lowest allowed mock seam: ``_invoke_with_resilience_async``.
        Forbidden: ``call_llm_async`` (mocks out routing where identity is resolved).
        """
        # Spec with provider=None triggers routing; routing resolves to google:gemini-pro.
        # Crucially, "google" != routing fallback default "anthropic" — so the swallow-
        # and-retry path would produce a DIFFERENT provider identity.
        spec = LLMRequest(
            request_id="routed-fail-no-rewrite",
            messages=[{"role": "user", "content": "hello"}],
            provider=None,
            routing_context={"routing_enabled": True, "task_type": "general"},
        )
        service = self._make_routed_service(
            routed_provider="google", routed_model="gemini-pro"
        )

        from agentmap.exceptions.service_exceptions import LLMProviderError

        with patch.object(
            service,
            "_invoke_with_resilience_async",
            new=AsyncMock(
                side_effect=LLMProviderError("provider failure after routing resolved")
            ),
        ):
            results = await service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.request_id, "routed-fail-no-rewrite")
        self.assertEqual(r.status, "failed")
        self.assertEqual(
            r.resolved_provider,
            "google",
            "provider must be 'google' (the routing-resolved provider). "
            "If 'anthropic', the routing handler swallowed LLMResolvedCallError "
            "and re-routed to the fallback provider — fix #1 is not in place.",
        )
        self.assertEqual(
            r.resolved_model,
            "gemini-pro",
            "model must be the routing-resolved model 'gemini-pro'",
        )
        self.assertIsNotNone(r.error)
        self.assertEqual(
            r.error.error_type,
            "LLMProviderError",
            "error_type must preserve the original typed error discriminator",
        )

    async def test_tc_ac8_07_fallback_exhaustion_typed_cause_preserved(self):
        """TC-AC8-07 (new — codex MEDIUM-1 regression guard): when all fallback tiers
        fail with a typed error (e.g., LLMTimeoutError), the fan-out result's
        error_type must reflect the last tier's typed error, NOT a synthetic
        LLMServiceError wrapper.

        Counter-factual: against pre-fix code (exhaustion wraps with
        LLMServiceError(error_msg)), r.error.error_type == "LLMServiceError".
        After fix (.cause = last_error from the last tier's typed exception),
        r.error.error_type reflects the actual error class.

        Lowest allowed mock seam: ``_invoke_with_resilience_async``.
        """
        from agentmap.exceptions.service_exceptions import LLMTimeoutError

        mock_features_registry = Mock()
        mock_features_registry.is_provider_available.return_value = True
        mock_features_registry.get_available_providers.return_value = [
            "openai",
            "anthropic",
            "google",
        ]
        mock_routing_config = Mock()
        mock_routing_config.fallback = {"default_provider": "anthropic"}
        mock_routing_config.routing_matrix = {
            "anthropic": {"low": "claude-haiku"},
            "openai": {"low": "gpt-3.5-turbo"},
            "google": {"low": "gemini-flash"},
        }

        service = LLMService(
            configuration=MockServiceFactory.create_mock_app_config_service(),
            logging_service=MockServiceFactory.create_mock_logging_service(),
            routing_service=Mock(),
            llm_models_config_service=MockServiceFactory.create_mock_llm_models_config_service(),
            features_registry_service=mock_features_registry,
            routing_config_service=mock_routing_config,
        )
        service._resilience_config = {
            "retry": {
                "max_attempts": 1,
                "backoff_base": 2.0,
                "backoff_max": 30.0,
                "jitter": False,
            },
            "circuit_breaker": {"failure_threshold": 5, "reset_timeout": 60},
        }
        service._provider_utils.normalize_provider = Mock(side_effect=lambda p: p)
        service._provider_utils.get_provider_config = Mock(
            side_effect=lambda p: {"model": f"{p}-default", "api_key": "test"}
        )
        service._message_utils.convert_messages_to_langchain = Mock(
            return_value=[Mock()]
        )
        service._client_factory.get_or_create_client = Mock(return_value=Mock())

        spec = _make_spec("typed-cause-exhaust", provider="openai", model="gpt-4o")

        with patch.object(
            service,
            "_invoke_with_resilience_async",
            new=AsyncMock(side_effect=LLMTimeoutError("request timed out")),
        ):
            results = await service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "failed")
        self.assertIsNotNone(r.error)
        self.assertEqual(
            r.error.error_type,
            "LLMTimeoutError",
            "error_type must be 'LLMTimeoutError' (last tier's typed error). "
            "If 'LLMServiceError', the fallback exhaustion path wrapped with a "
            "synthetic LLMServiceError, losing the typed discriminator — "
            "fix MEDIUM-1 is not in place.",
        )

    async def test_tc_ac8_02_non_fabrication_invariant_preserved(self):
        """TC-AC8-02 invariant: when failure occurs before any resolution
        (call_llm_async raises immediately as a plain LLMServiceError with no
        LLMResolvedCallError wrap), provider=None is preserved — not fabricated.

        This verifies the bare ``except Exception`` branch in
        ``_execute_fan_out_item`` still handles pre-resolution failures correctly
        after the LLMResolvedCallError catch is added.
        """
        spec = LLMRequest(
            request_id="pre-resolution-fail",
            messages=[{"role": "user", "content": "hi"}],
            provider=None,
            routing_context={"routing_enabled": True},
        )

        # Plain LLMServiceError — no LLMResolvedCallError wrap — simulates a failure
        # before any provider was selected (e.g., routing service itself raises).
        with patch.object(
            self.service,
            "call_llm_async",
            new=AsyncMock(side_effect=LLMServiceError("routing service unavailable")),
        ):
            results = await self.service.call_llm_many_async([spec], max_concurrency=1)

        r = results[0]
        self.assertEqual(r.status, "failed")
        self.assertIsNone(
            r.resolved_provider, "provider must remain None — do not fabricate"
        )

    def setUp(self):
        self.service = _make_service()


# ---------------------------------------------------------------------------
# TC-AC8-08: LLMResolvedCallError propagation through telemetry wrapper
# ---------------------------------------------------------------------------


class TestLLMResolvedCallErrorTelemetryPropagation(unittest.IsolatedAsyncioTestCase):
    """TC-AC8-08 (new — codex LOW-2): LLMResolvedCallError propagates unchanged
    through the telemetry-wrapped call_llm_async path.

    Code review confirmed the telemetry wrapper re-raises LLMServiceError subclasses
    at llm_service.py:343-352. This test is a regression guard — if the isinstance
    check is accidentally removed or narrowed, this test will fail.

    Seam: patch ``_invoke_with_resilience_async`` (lowest allowed).
    Wires a real telemetry service stub so the telemetry path is exercised.
    """

    def _make_service_with_telemetry(self) -> LLMService:
        """Build a service with a stub telemetry service wired in."""
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

        # Minimal telemetry stub: start_span returns a context manager; metrics
        # return Mocks so _record_* helpers don't throw.
        mock_telemetry = Mock()
        mock_span = Mock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=False)
        mock_telemetry.start_span.return_value = mock_span
        mock_telemetry.create_histogram.return_value = Mock()
        mock_telemetry.create_counter.return_value = Mock()
        mock_telemetry.create_up_down_counter.return_value = Mock()

        service = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=mock_routing,
            llm_models_config_service=mock_models,
            telemetry_service=mock_telemetry,
        )
        service._provider_utils.normalize_provider = Mock(side_effect=lambda p: p)
        service._provider_utils.get_provider_config = Mock(
            return_value={"model": "claude-haiku", "api_key": "test"}
        )
        service._message_utils.convert_messages_to_langchain = Mock(
            return_value=[Mock()]
        )
        service._client_factory.get_or_create_client = Mock(return_value=Mock())
        return service

    async def test_tc_ac8_08_resolved_call_error_propagates_through_telemetry_wrapper(
        self,
    ):
        """TC-AC8-08: call_llm_async (telemetry path) propagates LLMResolvedCallError
        with all three attributes intact.

        Counter-factual: if the telemetry wrapper's except-clause catches
        LLMResolvedCallError and re-wraps or swallows it, callers cannot read
        .resolved_provider / .resolved_model / .cause — this assertion fails.

        Lowest allowed mock seam: ``_invoke_with_resilience_async``.
        """
        from agentmap.exceptions.service_exceptions import LLMProviderError

        service = self._make_service_with_telemetry()

        underlying = LLMProviderError("provider timeout")
        resolved_err = LLMResolvedCallError(
            resolved_provider="anthropic",
            resolved_model="claude-haiku",
            cause=underlying,
        )

        with patch.object(
            service,
            "_invoke_with_resilience_async",
            new=AsyncMock(side_effect=resolved_err),
        ):
            with self.assertRaises(LLMResolvedCallError) as ctx:
                await service.call_llm_async(
                    messages=[{"role": "user", "content": "hello"}],
                    provider="anthropic",
                    model="claude-haiku",
                )

        exc = ctx.exception
        self.assertIsInstance(exc, LLMResolvedCallError)
        self.assertIsInstance(exc, LLMServiceError)
        self.assertEqual(exc.resolved_provider, "anthropic")
        self.assertEqual(exc.resolved_model, "claude-haiku")
        self.assertIs(exc.cause, underlying)


# ---------------------------------------------------------------------------
# LLMResolvedCallError public API — single-call propagation
# ---------------------------------------------------------------------------


class TestLLMResolvedCallErrorPublicAPI(unittest.IsolatedAsyncioTestCase):
    """TC-AC8-05: call_llm_async propagates LLMResolvedCallError with resolved identity.

    Verifies the public API surface from Section 4 of the round-2 addendum:
    when _call_llm_async_direct raises LLMResolvedCallError, call_llm_async
    lets it propagate unchanged so single-call callers can read resolved_provider,
    resolved_model, and cause.
    """

    def setUp(self):
        self.service = _make_service()
        self.service._provider_utils.normalize_provider = Mock(side_effect=lambda p: p)
        self.service._provider_utils.get_provider_config = Mock(
            return_value={"model": "claude-haiku", "api_key": "test"}
        )
        self.service._message_utils.convert_messages_to_langchain = Mock(
            return_value=[Mock()]
        )
        self.service._client_factory.get_or_create_client = Mock(return_value=Mock())

    async def test_call_llm_async_propagates_llm_resolved_call_error_with_identity(
        self,
    ):
        """TC-AC8-05: call_llm_async lets LLMResolvedCallError escape unchanged.

        Counter-factual: if call_llm_async unwrapped the error, callers could not
        read .resolved_provider / .resolved_model / .cause from the exception.

        Lowest allowed mock seam: ``_invoke_with_resilience_async``.
        Forbidden: ``call_llm_async`` (we are testing its propagation behavior).
        """
        from agentmap.exceptions.service_exceptions import LLMProviderError

        underlying = LLMProviderError("provider timeout")
        resolved_err = LLMResolvedCallError(
            resolved_provider="anthropic",
            resolved_model="claude-haiku",
            cause=underlying,
        )

        with patch.object(
            self.service,
            "_invoke_with_resilience_async",
            new=AsyncMock(side_effect=resolved_err),
        ):
            with self.assertRaises(LLMResolvedCallError) as ctx:
                await self.service.call_llm_async(
                    messages=[{"role": "user", "content": "hello"}],
                    provider="anthropic",
                    model="claude-haiku",
                )

        exc = ctx.exception
        self.assertIsInstance(exc, LLMResolvedCallError)
        # LLMResolvedCallError is a LLMServiceError subclass — existing handlers match.
        self.assertIsInstance(exc, LLMServiceError)
        self.assertEqual(exc.resolved_provider, "anthropic")
        self.assertEqual(exc.resolved_model, "claude-haiku")
        self.assertIs(exc.cause, underlying)


if __name__ == "__main__":
    unittest.main()
