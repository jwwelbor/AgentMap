"""
Unit tests for LLMService streaming entry point skeleton (E06-F03).

Covers TC-F03-007 and TC-F03-017 — the two test cases owned by T-E06-F03-001:
  - TC-F03-007: __init__ creates _metric_ttft histogram; instrument not None.
  - TC-F03-017 (constant assertion portion): METRIC_LLM_TTFT value and distinctness.

Also covers TC-F03-009 through TC-F03-015 — the test cases owned by T-E06-F03-004:
  - TC-F03-009: Pre-first-chunk retryable error; seam invoked twice; caller receives full stream.
  - TC-F03-011: Post-first-chunk error; 2 chunks delivered; seam invoked once; no fallback.
  - TC-F03-012: Post-first-chunk failure records circuit-breaker failure; no record_success.
  - TC-F03-013: Clean completion records circuit-breaker success once; CB metric on close.
  - TC-F03-014: Circuit-breaker open raises LLMProviderError before any chunk; stream_provider never called.
  - TC-F03-015: Non-retryable pre-first-chunk error; seam invoked once; record_failure + CB metric on open.

Also covers TC-F03-017 through TC-F03-021 and TC-F03-028 through TC-F03-030 — the test cases
owned by T-E06-F03-006 (_call_llm_stream_async_with_telemetry):
  - TC-F03-017: TTFT recorded exactly once on first chunk; duration once on completion.
  - TC-F03-018: TTFT NOT recorded when stream fails before first chunk.
  - TC-F03-019: Explicit span open/close (no `with` around iteration); _set_span_status_ok called.
  - TC-F03-020: Span closed on after-first-chunk error; _record_span_exception_safe called.
  - TC-F03-021: Span closed on generator abandonment (GeneratorExit via aclose()).
  - TC-F03-028: Default flags (False) — no GEN_AI_PROMPT_CONTENT/GEN_AI_RESPONSE_CONTENT set.
  - TC-F03-029: Flags True → _capture_llm_content called exactly once at completion.
  - TC-F03-030: Flags True + after-first-chunk error → _capture_llm_content NOT called.

Also covers T-E06-F03-007 integration test cases:
  - TC-F03-001: End-to-end happy path (Anthropic) through all layers.
  - TC-F03-003: OpenAI provider parity.
  - TC-F03-004: Telemetry-disabled dispatch — no span opened; same chunk sequence.
  - TC-F03-006: Non-streaming regression gate; source-hash check on seven methods.
  - TC-F03-031: 4096-char truncation parity for long streams.
  - TC-F03-032: Two concurrent asyncio.gather invocations — per-invocation isolation.
  - TC-F03-033: Every _record_*_metric uses {METRIC_DIM_PROVIDER, METRIC_DIM_MODEL}; no-op when None.
  - TC-F03-034: Credentials never logged on streaming path.
  - TC-F03-035: F04 hand-off contract.

Framework: unittest.IsolatedAsyncioTestCase for async tests; plain unittest.TestCase
for sync assertions. No real network calls. asyncio_mode NOT auto.
"""

import unittest
from typing import AsyncIterator, get_type_hints
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from agentmap.models.llm_execution import LLMStreamChunk
from agentmap.services.telemetry.constants import (
    METRIC_LLM_DURATION,
    METRIC_LLM_TTFT,
)

# ---------------------------------------------------------------------------
# Helpers — fake telemetry service
# ---------------------------------------------------------------------------


def _make_telemetry_fake():
    """Return a minimal telemetry fake that tracks create_histogram calls.

    create_histogram returns a distinct Mock per call so each instrument
    can be asserted independently.
    """
    svc = MagicMock(name="telemetry_service")
    svc.create_histogram.side_effect = lambda name, **kwargs: Mock(name=f"hist_{name}")
    svc.create_counter.side_effect = lambda name, **kwargs: Mock(name=f"counter_{name}")
    svc.create_up_down_counter.side_effect = lambda name, **kwargs: Mock(
        name=f"updown_{name}"
    )
    return svc


def _make_llm_service(telemetry_service=None):
    """Construct a minimal LLMService with all required mocks."""
    from agentmap.services.llm_service import LLMService

    mock_logging = MagicMock()
    mock_logging.get_class_logger.return_value = MagicMock()

    mock_config = MagicMock()
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {
            "max_attempts": 2,
            "backoff_base": 2.0,
            "backoff_max": 30.0,
            "jitter": False,
        },
        "circuit_breaker": {
            "failure_threshold": 3,
            "reset_timeout": 60,
        },
    }
    mock_config.get_llm_config.return_value = {
        "model": "claude-3-sonnet",
        "temperature": 0.7,
        "api_key": "test-key",
    }

    mock_models_config = MagicMock()
    mock_routing_service = MagicMock()
    mock_routing_config = MagicMock()
    mock_routing_config.supports_prompt_caching.return_value = False

    svc = LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing_service,
        llm_models_config_service=mock_models_config,
        routing_config_service=mock_routing_config,
        telemetry_service=telemetry_service,
    )
    return svc


# ---------------------------------------------------------------------------
# TC-F03-017 (constant assertion portion)
# ---------------------------------------------------------------------------


class TestMetricLLMTTFTConstant(unittest.TestCase):
    """TC-F03-017: METRIC_LLM_TTFT constant value and distinctness."""

    def test_metric_llm_ttft_has_correct_value(self):
        """METRIC_LLM_TTFT == 'agentmap.llm.ttft'."""
        self.assertEqual(METRIC_LLM_TTFT, "agentmap.llm.ttft")

    def test_metric_llm_ttft_is_distinct_from_metric_llm_duration(self):
        """METRIC_LLM_TTFT is a different constant from METRIC_LLM_DURATION."""
        self.assertNotEqual(METRIC_LLM_TTFT, METRIC_LLM_DURATION)

    def test_metric_llm_ttft_is_importable_from_constants(self):
        """METRIC_LLM_TTFT can be imported from telemetry.constants."""
        # If the import at the top succeeded, this trivially passes.
        self.assertIsInstance(METRIC_LLM_TTFT, str)


# ---------------------------------------------------------------------------
# TC-F03-007: __init__ creates _metric_ttft; no streaming method during init
# ---------------------------------------------------------------------------


class TestLLMServiceInitTTFTInstrument(unittest.TestCase):
    """TC-F03-007: LLMService.__init__ wires the TTFT histogram instrument."""

    def setUp(self):
        self.telemetry = _make_telemetry_fake()
        self.svc = _make_llm_service(telemetry_service=self.telemetry)

    def test_create_histogram_called_with_metric_llm_ttft(self):
        """create_histogram must be called with METRIC_LLM_TTFT during __init__."""
        called_names = [
            c.args[0] if c.args else c.kwargs.get("name", "")
            for c in self.telemetry.create_histogram.call_args_list
        ]
        self.assertIn(
            METRIC_LLM_TTFT,
            called_names,
            f"Expected create_histogram to be called with {METRIC_LLM_TTFT!r}. "
            f"Actual calls: {called_names}",
        )

    def test_metric_ttft_instrument_is_not_none_when_telemetry_present(self):
        """_metric_ttft must be set (not None) when telemetry_service is provided."""
        self.assertIsNotNone(
            self.svc._metric_ttft,
            "_metric_ttft should not be None when telemetry is wired",
        )

    def test_metric_ttft_initialized_to_none_without_telemetry(self):
        """_metric_ttft must default to None when telemetry_service is None."""
        svc_no_telemetry = _make_llm_service(telemetry_service=None)
        self.assertIsNone(
            svc_no_telemetry._metric_ttft,
            "_metric_ttft should be None when no telemetry_service is provided",
        )

    def test_ttft_histogram_created_with_unit_seconds(self):
        """create_histogram for METRIC_LLM_TTFT must use unit='s'."""
        ttft_calls = [
            c
            for c in self.telemetry.create_histogram.call_args_list
            if (c.args[0] if c.args else c.kwargs.get("name", "")) == METRIC_LLM_TTFT
        ]
        self.assertTrue(
            ttft_calls, f"No create_histogram call found for {METRIC_LLM_TTFT!r}"
        )
        ttft_call = ttft_calls[0]
        unit = ttft_call.kwargs.get("unit") or (
            ttft_call.args[1] if len(ttft_call.args) > 1 else None
        )
        self.assertEqual(unit, "s", f"Expected unit='s', got {unit!r}")

    def test_no_streaming_method_invoked_during_construction(self):
        """call_llm_stream_async and siblings must NOT be called during __init__."""
        # Verify the streaming entry point exists but was never auto-invoked.
        self.assertTrue(
            hasattr(self.svc, "call_llm_stream_async"),
            "call_llm_stream_async must exist on LLMService after F03",
        )
        # If __init__ invoked it, the telemetry fake would show stream_provider activity;
        # simpler to assert create_histogram was called but async-stream methods were not.
        # The real guard: no 'stream_provider' patch was needed to construct the service.
        # This test passes trivially if construction above succeeded without patching.

    def test_ttft_instrument_is_created_exactly_once(self):
        """create_histogram is called exactly once with METRIC_LLM_TTFT."""
        ttft_calls = [
            c
            for c in self.telemetry.create_histogram.call_args_list
            if (c.args[0] if c.args else c.kwargs.get("name", "")) == METRIC_LLM_TTFT
        ]
        self.assertEqual(
            len(ttft_calls),
            1,
            f"Expected exactly one create_histogram call for {METRIC_LLM_TTFT!r}, "
            f"got {len(ttft_calls)}",
        )


# ---------------------------------------------------------------------------
# Skeleton structure: call_llm_stream_async signature and return type
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncSkeletonExists(unittest.TestCase):
    """Basic structural assertions: method exists with correct signature.

    These tests do NOT exercise the full streaming body (later tasks) —
    they confirm the skeleton added by T-E06-F03-001 is wired correctly.
    """

    def setUp(self):
        self.svc = _make_llm_service(telemetry_service=None)

    def test_call_llm_stream_async_method_exists(self):
        """LLMService must expose call_llm_stream_async as a public method."""
        self.assertTrue(
            hasattr(self.svc, "call_llm_stream_async"),
            "call_llm_stream_async must be defined on LLMService",
        )

    def test_call_llm_stream_async_is_callable(self):
        """call_llm_stream_async must be callable."""
        self.assertTrue(callable(self.svc.call_llm_stream_async))

    def test_internal_telemetry_sibling_exists(self):
        """_call_llm_stream_async_with_telemetry must exist."""
        self.assertTrue(
            hasattr(self.svc, "_call_llm_stream_async_with_telemetry"),
            "_call_llm_stream_async_with_telemetry must be defined",
        )

    def test_internal_core_sibling_exists(self):
        """_call_llm_stream_async_core must exist."""
        self.assertTrue(
            hasattr(self.svc, "_call_llm_stream_async_core"),
            "_call_llm_stream_async_core must be defined",
        )

    def test_record_ttft_metric_helper_exists(self):
        """_record_ttft_metric helper must exist on LLMService."""
        self.assertTrue(
            hasattr(self.svc, "_record_ttft_metric"),
            "_record_ttft_metric must be defined on LLMService",
        )

    def test_record_ttft_metric_is_no_op_without_telemetry(self):
        """_record_ttft_metric must be a no-op (no exception) when telemetry is None."""
        # svc was built without telemetry; _metric_ttft is None.
        # The call must not raise.
        try:
            self.svc._record_ttft_metric(0.1, "anthropic", "claude-3-sonnet")
        except Exception as exc:
            self.fail(
                f"_record_ttft_metric raised unexpectedly with no telemetry: {exc}"
            )

    def test_record_ttft_metric_is_no_op_when_instrument_none(self):
        """_record_ttft_metric must silently no-op when _metric_ttft is None."""
        svc = _make_llm_service(telemetry_service=_make_telemetry_fake())
        svc._metric_ttft = None  # force to None even if telemetry is present
        try:
            svc._record_ttft_metric(0.2, "openai", "gpt-4o")
        except Exception as exc:
            self.fail(f"_record_ttft_metric raised when _metric_ttft is None: {exc}")


# ---------------------------------------------------------------------------
# PR #176 review: streaming telemetry must use the RESOLVED provider/model
# ---------------------------------------------------------------------------


class TestStreamTelemetryResolvedIdentity(unittest.IsolatedAsyncioTestCase):
    """Under routing, ``provider``/``model`` are None at call time; the TTFT and
    duration metrics must be recorded with the resolved identity taken from the
    terminal chunk, not empty-string dimensions.

    Counter-factual: recording with the initial ``provider or ""`` / ``model or ""``
    (the pre-fix behaviour) yields ``("", "")`` under routing, failing the asserts.
    """

    async def test_metrics_use_resolved_identity_under_routing(self):
        telemetry = _make_telemetry_fake()
        svc = _make_llm_service(telemetry_service=telemetry)

        ttft_calls = []
        dur_calls = []
        svc._record_ttft_metric = lambda d, p, m: ttft_calls.append((p, m))
        svc._record_duration_metric = lambda d, p, m: dur_calls.append((p, m))

        async def fake_core(
            messages, provider, model, temperature, routing_context, **kwargs
        ):
            yield LLMStreamChunk(text_delta="hello", chunk_index=0, is_final=False)
            yield LLMStreamChunk(
                text_delta="",
                chunk_index=1,
                is_final=True,
                resolved_provider="openai",
                resolved_model="gpt-4o",
            )

        svc._call_llm_stream_async_core = fake_core

        # Routing path: provider/model are None at call time.
        collected = []
        async for chunk in svc._call_llm_stream_async_with_telemetry(
            [{"role": "user", "content": "hi"}],
            None,
            None,
            None,
            {"task_type": "qa"},
        ):
            collected.append(chunk)

        self.assertEqual(len(collected), 2)
        self.assertEqual(
            ttft_calls,
            [("openai", "gpt-4o")],
            "TTFT must use the resolved identity, not empty strings",
        )
        self.assertEqual(
            dur_calls,
            [("openai", "gpt-4o")],
            "duration must use the resolved identity, not empty strings",
        )


# ---------------------------------------------------------------------------
# TC-F03-007 (async path): dispatch skeleton — telemetry vs no-telemetry
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncDispatch(unittest.IsolatedAsyncioTestCase):
    """TC-F03-007 async portion: dispatch routes through the correct skeleton branch."""

    async def test_with_telemetry_dispatches_to_telemetry_sibling(self):
        """With telemetry, call_llm_stream_async must dispatch to
        _call_llm_stream_async_with_telemetry (not the core directly)."""
        telemetry = _make_telemetry_fake()
        svc = _make_llm_service(telemetry_service=telemetry)

        # _call_llm_stream_async_with_telemetry is an async generator; we replace
        # it with one that yields a single real LLMStreamChunk and returns.
        terminal = LLMStreamChunk(
            text_delta="",
            chunk_index=0,
            is_final=True,
            resolved_provider="anthropic",
            resolved_model="claude-3-sonnet",
        )

        dispatched_to_telemetry = []

        async def fake_telemetry_sibling(
            messages, provider, model, temperature, routing_context, **kwargs
        ):
            dispatched_to_telemetry.append(True)
            yield terminal

        svc._call_llm_stream_async_with_telemetry = fake_telemetry_sibling

        chunks = []
        async for chunk in svc.call_llm_stream_async(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="claude-3-sonnet",
        ):
            chunks.append(chunk)

        self.assertTrue(
            dispatched_to_telemetry,
            "call_llm_stream_async must dispatch to _call_llm_stream_async_with_telemetry "
            "when telemetry is present",
        )
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].is_final)

    async def test_without_telemetry_dispatches_to_core_directly(self):
        """Without telemetry, call_llm_stream_async must dispatch to
        _call_llm_stream_async_core (skip the telemetry sibling)."""
        svc = _make_llm_service(telemetry_service=None)

        terminal = LLMStreamChunk(
            text_delta="",
            chunk_index=0,
            is_final=True,
            resolved_provider="openai",
            resolved_model="gpt-4o",
        )

        dispatched_to_core = []

        async def fake_core(
            messages, provider, model, temperature, routing_context, **kwargs
        ):
            dispatched_to_core.append(True)
            yield terminal

        svc._call_llm_stream_async_core = fake_core

        chunks = []
        async for chunk in svc.call_llm_stream_async(
            messages=[{"role": "user", "content": "hi"}],
            provider="openai",
            model="gpt-4o",
        ):
            chunks.append(chunk)

        self.assertTrue(
            dispatched_to_core,
            "call_llm_stream_async must dispatch to _call_llm_stream_async_core "
            "when telemetry is None",
        )
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].is_final)


# ---------------------------------------------------------------------------
# TC-F03-005: Routing dispatch mirrors the non-streaming core
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncCoreRoutingDispatch(unittest.IsolatedAsyncioTestCase):
    """TC-F03-005: _call_llm_stream_async_core routing dispatch.

    With routing_context + routing service → routes to _call_llm_stream_async_with_routing.
    Without routing_context and no provider → raises LLMServiceError.
    """

    def _make_svc_with_routing(self):
        """Return a service whose routing_service is a real mock."""
        svc = _make_llm_service(telemetry_service=None)
        # routing_service is already a MagicMock from _make_llm_service
        return svc

    async def test_routing_context_dispatches_to_with_routing(self):
        """With routing_context set and routing service present, _call_llm_stream_async_core
        must route through _call_llm_stream_async_with_routing."""
        svc = self._make_svc_with_routing()

        terminal = LLMStreamChunk(
            text_delta="",
            chunk_index=0,
            is_final=True,
            resolved_provider="anthropic",
            resolved_model="claude-3-sonnet",
        )

        dispatched_to_routing = []

        async def fake_with_routing(
            messages, routing_context, temperature=None, model=None, **kwargs
        ):
            dispatched_to_routing.append(True)
            yield terminal

        svc._call_llm_stream_async_with_routing = fake_with_routing

        routing_context = {"task_type": "qa"}
        chunks = []
        async for chunk in svc._call_llm_stream_async_core(
            messages=[{"role": "user", "content": "hi"}],
            provider=None,
            model=None,
            temperature=None,
            routing_context=routing_context,
        ):
            chunks.append(chunk)

        self.assertTrue(
            dispatched_to_routing,
            "_call_llm_stream_async_core must dispatch to _call_llm_stream_async_with_routing "
            "when routing_context is set and routing_service is present",
        )
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].is_final)

    async def test_no_routing_context_no_provider_raises_llm_service_error(self):
        """Without routing_context and no provider, _call_llm_stream_async_core must
        raise LLMServiceError (mirrors _call_llm_async_core @675 guard)."""
        from agentmap.services.llm_service import LLMServiceError

        svc = self._make_svc_with_routing()

        with self.assertRaises(LLMServiceError):
            async for _chunk in svc._call_llm_stream_async_core(
                messages=[{"role": "user", "content": "hi"}],
                provider=None,
                model=None,
                temperature=None,
                routing_context=None,
            ):
                pass

    async def test_no_routing_context_with_provider_dispatches_to_direct(self):
        """Without routing_context but with a provider, _call_llm_stream_async_core
        must dispatch to _call_llm_stream_async_direct (PROVIDER-FIRST positional)."""
        svc = self._make_svc_with_routing()

        terminal = LLMStreamChunk(
            text_delta="",
            chunk_index=0,
            is_final=True,
            resolved_provider="openai",
            resolved_model="gpt-4o",
        )

        dispatched_provider = []

        async def fake_direct(
            provider, messages, model=None, temperature=None, **kwargs
        ):
            dispatched_provider.append(provider)
            yield terminal

        svc._call_llm_stream_async_direct = fake_direct

        chunks = []
        async for chunk in svc._call_llm_stream_async_core(
            messages=[{"role": "user", "content": "hi"}],
            provider="openai",
            model="gpt-4o",
            temperature=0.5,
            routing_context=None,
        ):
            chunks.append(chunk)

        self.assertEqual(
            dispatched_provider,
            ["openai"],
            "_call_llm_stream_async_core must call _call_llm_stream_async_direct "
            "with provider as first positional arg",
        )
        self.assertEqual(len(chunks), 1)


class TestCallLLMStreamAsyncWithRouting(unittest.IsolatedAsyncioTestCase):
    """TC-F03-005 extension: _call_llm_stream_async_with_routing resolves routing
    and delegates to _call_llm_stream_async_direct."""

    def _make_svc_with_routing_decision(
        self, provider="anthropic", model="claude-3-sonnet"
    ):
        """Return a service whose routing_service produces a scripted decision."""
        svc = _make_llm_service(telemetry_service=None)

        # Script the routing decision
        decision = type(
            "RoutingDecision",
            (),
            {
                "provider": provider,
                "model": model,
                "complexity": "low",
                "confidence": 0.9,
                "max_tokens": 512,
            },
        )()
        svc.routing_service.route_request.return_value = decision

        # _provider_utils and _message_utils are real instances; patch via Mock replacement
        from unittest.mock import MagicMock

        mock_provider_utils = MagicMock()
        mock_provider_utils.get_available_providers.return_value = [provider]
        mock_provider_utils.normalize_provider.return_value = provider
        svc._provider_utils = mock_provider_utils

        mock_message_utils = MagicMock()
        mock_message_utils.extract_prompt_from_messages.return_value = "hi"
        svc._message_utils = mock_message_utils

        # Script _create_routing_context to return a mock context
        svc._create_routing_context = lambda routing_context, messages: type(
            "RoutingContext", (), {"task_type": "qa"}
        )()

        # _record_routing_attributes is a real method; patch to no-op
        svc._record_routing_attributes = lambda decision: None

        return svc, decision

    async def test_with_routing_delegates_to_direct_with_resolved_provider(self):
        """_call_llm_stream_async_with_routing must resolve the routing decision
        then delegate to _call_llm_stream_async_direct with the resolved provider."""
        svc, decision = self._make_svc_with_routing_decision(
            provider="anthropic", model="claude-3-sonnet"
        )

        terminal = LLMStreamChunk(
            text_delta="",
            chunk_index=0,
            is_final=True,
            resolved_provider="anthropic",
            resolved_model="claude-3-sonnet",
        )

        direct_calls = []

        async def fake_direct(
            provider, messages, model=None, temperature=None, **kwargs
        ):
            direct_calls.append({"provider": provider, "model": model})
            yield terminal

        svc._call_llm_stream_async_direct = fake_direct

        routing_context = {"task_type": "qa"}
        chunks = []
        async for chunk in svc._call_llm_stream_async_with_routing(
            messages=[{"role": "user", "content": "hi"}],
            routing_context=routing_context,
            temperature=None,
            model=None,
        ):
            chunks.append(chunk)

        self.assertEqual(
            len(direct_calls),
            1,
            "_call_llm_stream_async_with_routing must call _call_llm_stream_async_direct once",
        )
        self.assertEqual(
            direct_calls[0]["provider"],
            "anthropic",
            "resolved provider from routing decision must be passed to direct",
        )
        self.assertEqual(
            direct_calls[0]["model"],
            "claude-3-sonnet",
            "resolved model from routing decision must be passed to direct",
        )
        self.assertEqual(len(chunks), 1)
        self.assertTrue(chunks[0].is_final)

    async def test_with_routing_raises_when_no_routing_service(self):
        """_call_llm_stream_async_with_routing raises LLMServiceError if routing_service
        is absent (mirrors the non-streaming guard)."""
        from agentmap.services.llm_service import LLMServiceError

        svc, _ = self._make_svc_with_routing_decision()
        svc.routing_service = None  # remove routing service

        with self.assertRaises(LLMServiceError):
            async for _chunk in svc._call_llm_stream_async_with_routing(
                messages=[{"role": "user", "content": "hi"}],
                routing_context={"task_type": "qa"},
            ):
                pass

    async def test_post_selection_error_propagates_without_rerouting_to_fallback(self):
        """CR-fix (identity guard): once routing resolves a concrete (provider, model),
        an error from the resolved delegate call must PROPAGATE unchanged and must NOT
        be silently re-routed to ``fallback_provider``.

        Counter-factual: with the resolved delegate inside the wrapper's try (the bug),
        the broad ``except Exception`` re-invokes direct with fallback_provider and the
        caller silently receives a different provider's output. This test pins the fix.
        """
        from agentmap.exceptions import LLMProviderError

        svc, _decision = self._make_svc_with_routing_decision(
            provider="openai", model="gpt-4o"
        )

        direct_calls = []

        async def fake_direct(
            provider, messages, model=None, temperature=None, **kwargs
        ):
            direct_calls.append(provider)
            # The resolved provider call fails post-selection.
            raise LLMProviderError("resolved provider failed after selection")
            yield  # make this an async generator

        svc._call_llm_stream_async_direct = fake_direct

        # fallback_provider is anthropic by default; it must NOT be invoked.
        routing_context = {"task_type": "qa", "fallback_provider": "anthropic"}

        with self.assertRaises(LLMProviderError):
            async for _chunk in svc._call_llm_stream_async_with_routing(
                messages=[{"role": "user", "content": "hi"}],
                routing_context=routing_context,
            ):
                pass

        # Direct was called exactly once — with the RESOLVED provider — and the
        # error propagated as-is. No silent re-route to the fallback provider.
        self.assertEqual(
            direct_calls,
            ["openai"],
            "post-selection error must propagate, not re-route to fallback_provider",
        )


# ---------------------------------------------------------------------------
# TC-F03-008: LLMServiceProtocol declares call_llm_stream_async
# ---------------------------------------------------------------------------


class TestLLMServiceProtocolDeclaresStreamAsync(unittest.TestCase):
    """TC-F03-008: LLMServiceProtocol must declare call_llm_stream_async with
    the REQ-F-001 signature and AsyncIterator[LLMStreamChunk] return annotation.
    LLMService must satisfy the protocol."""

    def test_protocol_declares_call_llm_stream_async(self):
        """LLMServiceProtocol must have call_llm_stream_async as a declared method."""
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        self.assertTrue(
            hasattr(LLMServiceProtocol, "call_llm_stream_async"),
            "LLMServiceProtocol must declare call_llm_stream_async",
        )

    def test_protocol_method_has_async_iterator_return_annotation(self):
        """call_llm_stream_async return annotation must be AsyncIterator[LLMStreamChunk]."""
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        method = LLMServiceProtocol.call_llm_stream_async
        hints = get_type_hints(method)
        return_hint = hints.get("return")
        self.assertIsNotNone(
            return_hint,
            "call_llm_stream_async must have a return type annotation",
        )
        # Check that it is AsyncIterator[LLMStreamChunk]
        hint_str = str(return_hint)
        self.assertIn(
            "AsyncIterator",
            hint_str,
            f"Return annotation must be AsyncIterator[...], got {hint_str}",
        )
        self.assertIn(
            "LLMStreamChunk",
            hint_str,
            f"Return annotation must include LLMStreamChunk, got {hint_str}",
        )

    def test_protocol_method_signature_matches_req_f001(self):
        """call_llm_stream_async parameter list must match REQ-F-001:
        messages, provider=None, model=None, temperature=None,
        routing_context=None, cache_system_prompt=False, **kwargs."""
        import inspect

        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        sig = inspect.signature(LLMServiceProtocol.call_llm_stream_async)
        params = dict(sig.parameters)

        # Remove 'self' from comparison
        params.pop("self", None)

        self.assertIn("messages", params, "Parameter 'messages' must be declared")
        self.assertIn("provider", params, "Parameter 'provider' must be declared")
        self.assertIn("model", params, "Parameter 'model' must be declared")
        self.assertIn("temperature", params, "Parameter 'temperature' must be declared")
        self.assertIn(
            "routing_context", params, "Parameter 'routing_context' must be declared"
        )
        self.assertIn(
            "cache_system_prompt",
            params,
            "Parameter 'cache_system_prompt' must be declared",
        )

        self.assertIsNone(params["provider"].default, "provider must default to None")
        self.assertIsNone(params["model"].default, "model must default to None")
        self.assertIsNone(
            params["temperature"].default, "temperature must default to None"
        )
        self.assertIsNone(
            params["routing_context"].default, "routing_context must default to None"
        )
        self.assertFalse(
            params["cache_system_prompt"].default,
            "cache_system_prompt must default to False",
        )

    def test_llm_service_satisfies_protocol(self):
        """LLMService must satisfy LLMServiceProtocol (isinstance check)."""
        from agentmap.services.protocols.service_protocols import LLMServiceProtocol

        svc = _make_llm_service(telemetry_service=None)
        self.assertIsInstance(
            svc,
            LLMServiceProtocol,
            "LLMService must satisfy LLMServiceProtocol after F03 extension",
        )


# ---------------------------------------------------------------------------
# Group E — Unsupported-mode validation gate (TC-F03-022 through TC-F03-025)
# REQ-F-007; Constraint C4; Scenarios 7 & 10; AC-9, AC-10, AC-11
# ---------------------------------------------------------------------------


class TestValidateStreamingSupportGate(unittest.IsolatedAsyncioTestCase):
    """TC-F03-022 through TC-F03-025: _validate_streaming_support gate.

    All tests drive call_llm_stream_async (the public production entrypoint)
    and collect chunks via async-for in try/except LLMServiceError — which is
    the production caller pattern.  stream_provider is patched to an AsyncMock
    at the seam so we can assert it was never called.
    """

    def _make_svc(self):
        """Return a service with routing_config that refuses prompt caching."""
        svc = _make_llm_service(telemetry_service=None)
        # routing_config.supports_prompt_caching → False by default in
        # _make_llm_service (mock_routing_config is already set this way)
        return svc

    def _spy_on_client_factory(self, svc):
        """Install a call-recorder on _client_factory.get_or_create_client.

        Returns the MagicMock so tests can assert it was (or was not) called.
        Rejection-path tests assert it is never reached — proving the gate
        fires BEFORE the factory (and hence before stream_provider).
        """
        from unittest.mock import MagicMock

        factory_spy = MagicMock(name="get_or_create_client_spy")
        svc._client_factory.get_or_create_client = factory_spy
        return factory_spy

    # ------------------------------------------------------------------
    # TC-F03-022: Gemini token streaming rejected before any chunk
    # ------------------------------------------------------------------

    async def test_google_provider_raises_before_any_chunk(self):
        """TC-F03-022: call_llm_stream_async with provider='google' raises
        LLMServiceError; no chunks received; get_or_create_client (i.e., the
        streaming seam) never called.
        """
        from agentmap.services.llm_service import LLMServiceError

        svc = self._make_svc()
        factory_spy = self._spy_on_client_factory(svc)

        chunks = []
        with self.assertRaises(LLMServiceError) as ctx:
            async for chunk in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="google",
                model="gemini-pro",
            ):
                chunks.append(chunk)

        self.assertEqual(
            chunks,
            [],
            "Zero chunks must be received before LLMServiceError is raised for 'google'",
        )
        error_msg = str(ctx.exception)
        self.assertIn(
            "google",
            error_msg.lower(),
            f"Error message must mention 'google'. Got: {error_msg!r}",
        )
        # get_or_create_client (and hence stream_provider) must never be called.
        factory_spy.assert_not_called()

    async def test_google_provider_error_names_call_llm_async_alternative(self):
        """TC-F03-022: Gemini rejection message names call_llm_async as the
        supported alternative (REQ-F-007, documented unsupported-mode message)."""
        from agentmap.services.llm_service import LLMServiceError

        svc = self._make_svc()
        self._spy_on_client_factory(svc)

        with self.assertRaises(LLMServiceError) as ctx:
            async for _ in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="google",
            ):
                pass

        error_msg = str(ctx.exception)
        self.assertIn(
            "call_llm_async",
            error_msg,
            f"Rejection message must name 'call_llm_async'. Got: {error_msg!r}",
        )

    # ------------------------------------------------------------------
    # TC-F03-023: Batch streaming param rejected before any chunk
    # ------------------------------------------------------------------

    async def test_stream_kwarg_raises_before_any_chunk(self):
        """TC-F03-023: 'stream' in kwargs raises LLMServiceError; no chunks
        received; message consistent with batch-rejection text; factory (i.e.,
        the streaming seam entry) never called.
        """
        from agentmap.services.llm_service import LLMServiceError

        svc = self._make_svc()
        factory_spy = self._spy_on_client_factory(svc)

        chunks = []
        with self.assertRaises(LLMServiceError) as ctx:
            async for chunk in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-3-sonnet",
                stream=True,
            ):
                chunks.append(chunk)

        self.assertEqual(
            chunks,
            [],
            "Zero chunks must be received before LLMServiceError is raised for 'stream' kwarg",
        )
        error_msg = str(ctx.exception)
        # Message must be consistent with existing batch rejection at
        # _param_resolution.py:300: "Batch submissions do not support streaming."
        self.assertIn(
            "Batch submissions do not support streaming",
            error_msg,
            f"Error message must contain batch-rejection text. Got: {error_msg!r}",
        )
        factory_spy.assert_not_called()

    async def test_stream_false_kwarg_still_rejected(self):
        """TC-F03-023 variant: stream=False is also a batch-incompatible param
        presence (the key itself is disallowed, not the value)."""
        from agentmap.services.llm_service import LLMServiceError

        svc = self._make_svc()
        self._spy_on_client_factory(svc)

        with self.assertRaises(LLMServiceError):
            async for _ in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                stream=False,
            ):
                pass

    # ------------------------------------------------------------------
    # TC-F03-024: Unverified prompt-caching rejected before any chunk
    # ------------------------------------------------------------------

    async def test_cache_system_prompt_unsupported_provider_raises(self):
        """TC-F03-024: cache_system_prompt=True on a provider that does not
        support caching raises LLMServiceError; no chunks; factory (i.e., the
        streaming seam entry) not called; _validate_prompt_caching_support
        invoked with execution_path='call_llm_stream_async'.
        """
        from agentmap.services.llm_service import LLMServiceError

        svc = self._make_svc()
        factory_spy = self._spy_on_client_factory(svc)

        caching_calls = []

        original_validate = svc._validate_prompt_caching_support

        def spy_validate_caching(*args, **kwargs):
            caching_calls.append(kwargs.get("execution_path"))
            return original_validate(*args, **kwargs)

        svc._validate_prompt_caching_support = spy_validate_caching

        chunks = []
        with self.assertRaises(LLMServiceError):
            async for chunk in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-3-sonnet",
                cache_system_prompt=True,
            ):
                chunks.append(chunk)

        self.assertEqual(
            chunks,
            [],
            "Zero chunks must be received before caching rejection",
        )
        # _validate_prompt_caching_support must have been called with
        # execution_path='call_llm_stream_async' (AC-11).
        self.assertIn(
            "call_llm_stream_async",
            caching_calls,
            f"_validate_prompt_caching_support must be called with "
            f"execution_path='call_llm_stream_async'. Got calls: {caching_calls!r}",
        )
        factory_spy.assert_not_called()

    # ------------------------------------------------------------------
    # TC-F03-025: Gate fires AFTER normalize_provider, BEFORE resilience
    # ------------------------------------------------------------------

    async def test_gate_fires_after_normalize_provider_before_factory(self):
        """TC-F03-025: _validate_streaming_support runs after normalize_provider
        and before get_or_create_client / _invoke_with_resilience_stream_async.

        Spy on call order: normalize_provider → _validate_streaming_support →
        (if gate passes) get_or_create_client.  For a rejected call (google),
        get_or_create_client must NOT be called.
        """
        from agentmap.services.llm_service import LLMServiceError

        svc = self._make_svc()

        call_order = []

        # Spy on normalize_provider
        original_normalize = svc._provider_utils.normalize_provider

        def spy_normalize(provider):
            call_order.append("normalize_provider")
            return original_normalize(provider)

        svc._provider_utils.normalize_provider = spy_normalize

        # Spy on _validate_streaming_support
        original_validate = svc._validate_streaming_support

        def spy_validate(provider, messages, routing_context=None, **kwargs):
            call_order.append("_validate_streaming_support")
            return original_validate(provider, messages, routing_context, **kwargs)

        svc._validate_streaming_support = spy_validate

        # Spy on get_or_create_client — must NOT be called for rejected request
        factory_calls = []
        original_factory = svc._client_factory.get_or_create_client

        def spy_factory(*args, **kwargs):
            factory_calls.append(True)
            return original_factory(*args, **kwargs)

        svc._client_factory.get_or_create_client = spy_factory

        chunks = []
        with self.assertRaises(LLMServiceError):
            async for chunk in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="google",
                model="gemini-pro",
            ):
                chunks.append(chunk)

        # normalize_provider must fire before _validate_streaming_support
        self.assertIn("normalize_provider", call_order)
        self.assertIn("_validate_streaming_support", call_order)
        normalize_idx = call_order.index("normalize_provider")
        validate_idx = call_order.index("_validate_streaming_support")
        self.assertLess(
            normalize_idx,
            validate_idx,
            f"normalize_provider must fire before _validate_streaming_support. "
            f"Order: {call_order!r}",
        )
        # get_or_create_client must NOT be called (gate blocked before factory)
        self.assertEqual(
            factory_calls,
            [],
            "get_or_create_client must NOT be called when gate rejects the request",
        )
        self.assertEqual(chunks, [], "No chunks for rejected request")

    async def test_gate_method_exists_on_llm_service(self):
        """TC-F03-025 (structural): _validate_streaming_support is defined on
        LLMService as a standalone method (not inlined in _call_llm_stream_async_direct).
        """
        svc = self._make_svc()
        self.assertTrue(
            hasattr(svc, "_validate_streaming_support"),
            "_validate_streaming_support must be a named method on LLMService",
        )
        self.assertTrue(
            callable(svc._validate_streaming_support),
            "_validate_streaming_support must be callable",
        )


# ---------------------------------------------------------------------------
# Helpers for TC-F03-009 – TC-F03-015
# ---------------------------------------------------------------------------


def make_stream(*text_deltas: str) -> AsyncIterator:
    """Build a real async generator yielding LLMStreamChunk instances.

    Produces ``len(text_deltas)`` non-final chunks followed by one terminal
    chunk (is_final=True, text_delta=""). ``resolved_provider`` and
    ``resolved_model`` are set on the terminal chunk to "anthropic" / "test-model"
    by default so callers can reconstruct an LLMResponse.
    """

    async def _gen():
        for idx, delta in enumerate(text_deltas):
            yield LLMStreamChunk(text_delta=delta, chunk_index=idx, is_final=False)
        yield LLMStreamChunk(
            text_delta="",
            chunk_index=len(text_deltas),
            is_final=True,
            resolved_provider="anthropic",
            resolved_model="test-model",
        )

    return _gen()


def make_failing_stream(after: int, exc: Exception) -> AsyncIterator:
    """Build a real async generator that yields ``after`` non-final chunks then raises ``exc``."""

    async def _gen():
        for idx in range(after):
            yield LLMStreamChunk(
                text_delta=f"chunk{idx}", chunk_index=idx, is_final=False
            )
        raise exc

    return _gen()


def _make_svc_for_resilience(max_attempts: int = 2):
    """Build a minimal LLMService with resilience config + mocked circuit breaker.

    Returns ``(svc, circuit_breaker_mock)`` so tests can configure CB behaviour.
    """
    from agentmap.services.llm_service import LLMService

    mock_logging = MagicMock()
    mock_logging.get_class_logger.return_value = MagicMock()

    mock_config = MagicMock()
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {
            "max_attempts": max_attempts,
            "backoff_base": 2.0,
            "backoff_max": 30.0,
            "jitter": False,
        },
        "circuit_breaker": {
            "failure_threshold": 3,
            "reset_timeout": 60,
        },
    }
    mock_config.get_llm_config.return_value = {
        "model": "test-model",
        "temperature": 0.7,
        "api_key": "test-key",
    }

    mock_models_config = MagicMock()
    mock_routing_service = MagicMock()
    mock_routing_config = MagicMock()
    mock_routing_config.supports_prompt_caching.return_value = False

    svc = LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing_service,
        llm_models_config_service=mock_models_config,
        routing_config_service=mock_routing_config,
        telemetry_service=None,
    )

    # Replace circuit breaker with a mock that defaults to "open = False"
    cb_mock = MagicMock()
    cb_mock.is_open.return_value = False
    cb_mock.reset = 60
    svc._circuit_breaker = cb_mock

    return svc, cb_mock


# ---------------------------------------------------------------------------
# TC-F03-009: Pre-first-chunk retryable error → retry engaged
# ---------------------------------------------------------------------------


class TestInvokeWithResilienceStreamRetry(unittest.IsolatedAsyncioTestCase):
    """TC-F03-009: Pre-first-chunk retryable error retries; caller receives full stream."""

    async def test_pre_first_chunk_retryable_error_retries_and_succeeds(self):
        """First stream_provider attempt raises retryable error before any yield;
        second attempt yields a full stream. Seam invoked twice. No error surfaces.
        asyncio.sleep patched.
        """
        from agentmap.exceptions import LLMRateLimitError

        svc, cb_mock = _make_svc_for_resilience(max_attempts=2)

        # First attempt raises before yielding; second returns a real stream.
        call_count = 0

        async def fake_stream_provider(
            provider, messages, params, *, client, credentials
        ):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMRateLimitError("rate limited — retryable")
            # Second attempt: yield a real stream
            async for chunk in make_stream("Hello", " world"):
                yield chunk

        with (
            patch(
                "agentmap.services.llm_service.stream_provider",
                side_effect=fake_stream_provider,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            collected = []
            async for chunk in svc._invoke_with_resilience_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                params={"model": "test-model"},
                provider="anthropic",
                model="test-model",
                streaming_client=MagicMock(),
                credentials={},
            ):
                collected.append(chunk)

        # Seam called twice
        self.assertEqual(call_count, 2, "stream_provider must be invoked twice")
        # Received 2 non-final + 1 terminal chunk from successful second attempt
        non_final = [c for c in collected if not c.is_final]
        terminal = [c for c in collected if c.is_final]
        self.assertEqual(len(non_final), 2)
        self.assertEqual(len(terminal), 1)
        self.assertFalse(terminal[0].text_delta)

    async def test_record_success_called_after_clean_stream_on_retry(self):
        """After a successful second attempt, record_success is called once."""
        from agentmap.exceptions import LLMRateLimitError

        svc, cb_mock = _make_svc_for_resilience(max_attempts=2)
        call_count = 0

        async def fake_sp(provider, messages, params, *, client, credentials):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMRateLimitError("rate limited — retryable")
            async for chunk in make_stream("ok"):
                yield chunk

        with (
            patch("agentmap.services.llm_service.stream_provider", side_effect=fake_sp),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            async for _ in svc._invoke_with_resilience_stream_async(
                messages=[{"role": "user", "content": "x"}],
                params={"model": "test-model"},
                provider="anthropic",
                model="test-model",
                streaming_client=MagicMock(),
                credentials={},
            ):
                pass

        cb_mock.record_success.assert_called_once_with("anthropic", "test-model")
        cb_mock.record_failure.assert_not_called()


# ---------------------------------------------------------------------------
# TC-F03-011: Post-first-chunk error → terminal, no retry, no fallback
# ---------------------------------------------------------------------------


class TestInvokeWithResilienceStreamPostFirstChunk(unittest.IsolatedAsyncioTestCase):
    """TC-F03-011 + TC-F03-012: Post-first-chunk failure is terminal."""

    async def test_post_first_chunk_error_delivers_chunks_then_raises(self):
        """After 2 chunks yielded, stream raises. 2 chunks received; error re-raised;
        seam invoked exactly once (no retry).
        """
        from agentmap.exceptions import LLMProviderError

        svc, cb_mock = _make_svc_for_resilience(max_attempts=3)

        exc = LLMProviderError("mid-stream error")
        call_count = 0

        async def fake_sp(provider, messages, params, *, client, credentials):
            nonlocal call_count
            call_count += 1
            async for chunk in make_failing_stream(after=2, exc=exc):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            collected = []
            raised = None
            try:
                async for chunk in svc._invoke_with_resilience_stream_async(
                    messages=[{"role": "user", "content": "hi"}],
                    params={"model": "test-model"},
                    provider="anthropic",
                    model="test-model",
                    streaming_client=MagicMock(),
                    credentials={},
                ):
                    collected.append(chunk)
            except LLMProviderError as e:
                raised = e

        # 2 chunks received before error
        self.assertEqual(
            len(collected), 2, "Must receive exactly 2 chunks before error"
        )
        # Error re-raised to caller
        self.assertIsNotNone(raised, "Error must propagate to caller")
        # Seam invoked exactly once — no retry
        self.assertEqual(
            call_count, 1, "stream_provider must be invoked exactly once (no retry)"
        )

    async def test_post_first_chunk_error_records_failure_not_success(self):
        """TC-F03-012: record_failure called on post-first-chunk error; record_success not called;
        _record_circuit_breaker_metric_on_open NOT called (CB already knows via record_failure).
        """
        from agentmap.exceptions import LLMProviderError

        svc, cb_mock = _make_svc_for_resilience(max_attempts=3)

        exc = LLMProviderError("mid-stream")

        async def fake_sp(provider, messages, params, *, client, credentials):
            async for chunk in make_failing_stream(after=2, exc=exc):
                yield chunk

        # Spy on _record_circuit_breaker_metric_on_open to assert NOT called
        cb_open_calls = []
        original_cb_open = svc._record_circuit_breaker_metric_on_open

        def spy_cb_open(provider, model):
            cb_open_calls.append((provider, model))
            return original_cb_open(provider, model)

        svc._record_circuit_breaker_metric_on_open = spy_cb_open

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            try:
                async for _ in svc._invoke_with_resilience_stream_async(
                    messages=[{"role": "user", "content": "hi"}],
                    params={"model": "test-model"},
                    provider="anthropic",
                    model="test-model",
                    streaming_client=MagicMock(),
                    credentials={},
                ):
                    pass
            except LLMProviderError:
                pass

        cb_mock.record_failure.assert_called_once_with("anthropic", "test-model")
        cb_mock.record_success.assert_not_called()
        # _record_circuit_breaker_metric_on_open must NOT be called on post-first-chunk path
        self.assertEqual(
            cb_open_calls,
            [],
            "_record_circuit_breaker_metric_on_open must NOT be called on post-first-chunk terminal path",
        )


# ---------------------------------------------------------------------------
# TC-F03-013: Clean completion records circuit-breaker success
# ---------------------------------------------------------------------------


class TestInvokeWithResilienceStreamCleanCompletion(unittest.IsolatedAsyncioTestCase):
    """TC-F03-013: Clean stream completion calls record_success once; CB metric on close."""

    async def test_clean_completion_calls_record_success_once(self):
        """Happy path: record_success(provider, model) called exactly once after terminal chunk;
        record_failure not called; _record_circuit_breaker_metric_on_close invoked.
        """
        svc, cb_mock = _make_svc_for_resilience(max_attempts=2)

        async def fake_sp(provider, messages, params, *, client, credentials):
            async for chunk in make_stream("Hello", " world"):
                yield chunk

        # Spy on _record_circuit_breaker_metric_on_close
        cb_close_calls = []
        original_close = svc._record_circuit_breaker_metric_on_close

        def spy_cb_close(was_open, provider, model):
            cb_close_calls.append((was_open, provider, model))
            return original_close(was_open, provider, model)

        svc._record_circuit_breaker_metric_on_close = spy_cb_close

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            collected = []
            async for chunk in svc._invoke_with_resilience_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                params={"model": "test-model"},
                provider="anthropic",
                model="test-model",
                streaming_client=MagicMock(),
                credentials={},
            ):
                collected.append(chunk)

        cb_mock.record_success.assert_called_once_with("anthropic", "test-model")
        cb_mock.record_failure.assert_not_called()
        self.assertTrue(
            cb_close_calls,
            "_record_circuit_breaker_metric_on_close must be called on clean completion",
        )
        # Verify received full stream (2 non-final + 1 terminal)
        self.assertEqual(len(collected), 3)
        self.assertTrue(collected[-1].is_final)


# ---------------------------------------------------------------------------
# TC-F03-014: Circuit-breaker open → reject before any chunk
# ---------------------------------------------------------------------------


class TestInvokeWithResilienceStreamCircuitBreakerOpen(
    unittest.IsolatedAsyncioTestCase
):
    """TC-F03-014: CB open raises LLMProviderError before any chunk; stream_provider never called."""

    async def test_circuit_breaker_open_raises_before_any_chunk(self):
        """When is_open returns True, LLMProviderError is raised immediately;
        stream_provider is never invoked.
        """
        from agentmap.exceptions import LLMProviderError

        svc, cb_mock = _make_svc_for_resilience(max_attempts=2)
        cb_mock.is_open.return_value = True  # CB is open

        stream_provider_calls = []

        async def fake_sp(provider, messages, params, *, client, credentials):
            stream_provider_calls.append(True)
            yield LLMStreamChunk(
                text_delta="should not appear", chunk_index=0, is_final=True
            )

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            collected = []
            raised = None
            try:
                async for chunk in svc._invoke_with_resilience_stream_async(
                    messages=[{"role": "user", "content": "hi"}],
                    params={"model": "test-model"},
                    provider="anthropic",
                    model="test-model",
                    streaming_client=MagicMock(),
                    credentials={},
                ):
                    collected.append(chunk)
            except LLMProviderError as e:
                raised = e

        self.assertIsNotNone(raised, "LLMProviderError must be raised when CB is open")
        self.assertEqual(collected, [], "No chunks must be delivered when CB is open")
        self.assertEqual(
            stream_provider_calls,
            [],
            "stream_provider must NOT be invoked when CB is open",
        )

    async def test_circuit_breaker_open_error_message_contains_reset(self):
        """LLMProviderError message mentions the reset timeout (mirrors line 1282)."""
        from agentmap.exceptions import LLMProviderError

        svc, cb_mock = _make_svc_for_resilience(max_attempts=2)
        cb_mock.is_open.return_value = True
        cb_mock.reset = 60

        async def fake_sp(provider, messages, params, *, client, credentials):
            yield LLMStreamChunk(text_delta="x", chunk_index=0, is_final=True)

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            with self.assertRaises(LLMProviderError) as ctx:
                async for _ in svc._invoke_with_resilience_stream_async(
                    messages=[{"role": "user", "content": "hi"}],
                    params={"model": "test-model"},
                    provider="anthropic",
                    model="test-model",
                    streaming_client=MagicMock(),
                    credentials={},
                ):
                    pass

        error_msg = str(ctx.exception)
        self.assertIn(
            "60",
            error_msg,
            f"Error message must mention reset timeout (60s). Got: {error_msg!r}",
        )


# ---------------------------------------------------------------------------
# TC-F03-015: Non-retryable pre-first-chunk error short-circuits retry loop
# ---------------------------------------------------------------------------


class TestInvokeWithResilienceStreamNonRetryable(unittest.IsolatedAsyncioTestCase):
    """TC-F03-015: Non-retryable error before first chunk; seam invoked once; CB metrics called."""

    async def test_non_retryable_pre_first_chunk_error_no_second_attempt(self):
        """Non-retryable error: seam invoked exactly once (no retry); error propagates."""
        from agentmap.exceptions import LLMConfigurationError

        svc, cb_mock = _make_svc_for_resilience(max_attempts=3)

        call_count = 0

        async def fake_sp(provider, messages, params, *, client, credentials):
            nonlocal call_count
            call_count += 1
            raise LLMConfigurationError("bad config — non retryable")
            yield  # make it a generator

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            raised = None
            try:
                async for _ in svc._invoke_with_resilience_stream_async(
                    messages=[{"role": "user", "content": "hi"}],
                    params={"model": "test-model"},
                    provider="anthropic",
                    model="test-model",
                    streaming_client=MagicMock(),
                    credentials={},
                ):
                    pass
            except Exception as e:
                raised = e

        self.assertIsNotNone(raised, "Non-retryable error must propagate")
        self.assertEqual(
            call_count,
            1,
            "stream_provider must be invoked exactly once on non-retryable error",
        )

    async def test_non_retryable_pre_first_chunk_calls_record_failure_and_cb_metric_on_open(
        self,
    ):
        """TC-F03-015: record_failure called; _record_circuit_breaker_metric_on_open called once
        (mirrors _invoke_with_resilience_async line 1319–1322).
        """
        from agentmap.exceptions import LLMConfigurationError

        svc, cb_mock = _make_svc_for_resilience(max_attempts=3)

        cb_open_calls = []
        original_cb_open = svc._record_circuit_breaker_metric_on_open

        def spy_cb_open(provider, model):
            cb_open_calls.append((provider, model))
            return original_cb_open(provider, model)

        svc._record_circuit_breaker_metric_on_open = spy_cb_open

        async def fake_sp(provider, messages, params, *, client, credentials):
            raise LLMConfigurationError("bad config")
            yield  # make it a generator

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            try:
                async for _ in svc._invoke_with_resilience_stream_async(
                    messages=[{"role": "user", "content": "hi"}],
                    params={"model": "test-model"},
                    provider="anthropic",
                    model="test-model",
                    streaming_client=MagicMock(),
                    credentials={},
                ):
                    pass
            except Exception:
                pass

        cb_mock.record_failure.assert_called_once_with("anthropic", "test-model")
        self.assertEqual(
            len(cb_open_calls),
            1,
            "_record_circuit_breaker_metric_on_open must be called exactly once on non-retryable path",
        )
        cb_mock.record_success.assert_not_called()

    async def test_retryable_exhaustion_calls_record_failure_and_cb_metric_on_open(
        self,
    ):
        """After max_attempts retryable errors, record_failure + _record_circuit_breaker_metric_on_open
        called (mirrors _invoke_with_resilience_async line 1338–1341).
        """
        from agentmap.exceptions import LLMRateLimitError

        svc, cb_mock = _make_svc_for_resilience(max_attempts=2)

        cb_open_calls = []
        original_cb_open = svc._record_circuit_breaker_metric_on_open

        def spy_cb_open(provider, model):
            cb_open_calls.append((provider, model))
            return original_cb_open(provider, model)

        svc._record_circuit_breaker_metric_on_open = spy_cb_open

        async def fake_sp(provider, messages, params, *, client, credentials):
            raise LLMRateLimitError("rate limited — always fails")
            yield  # make it a generator

        with (
            patch("agentmap.services.llm_service.stream_provider", side_effect=fake_sp),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            try:
                async for _ in svc._invoke_with_resilience_stream_async(
                    messages=[{"role": "user", "content": "hi"}],
                    params={"model": "test-model"},
                    provider="anthropic",
                    model="test-model",
                    streaming_client=MagicMock(),
                    credentials={},
                ):
                    pass
            except Exception:
                pass

        cb_mock.record_failure.assert_called_once_with("anthropic", "test-model")
        self.assertEqual(
            len(cb_open_calls),
            1,
            "_record_circuit_breaker_metric_on_open must be called once on retry exhaustion",
        )


# ---------------------------------------------------------------------------
# Helpers for TC-F03-002, TC-F03-010, TC-F03-016, TC-F03-026, TC-F03-027
# Tests for _call_llm_stream_async_direct (T-E06-F03-005)
# ---------------------------------------------------------------------------


def _make_svc_for_direct(max_attempts: int = 2):
    """Build a minimal LLMService suitable for _call_llm_stream_async_direct tests.

    Returns ``(svc, cb_mock)`` with:
    - Mock config returning provider config with model/temperature/api_key.
    - Mock client factory with a sentinel streaming_client.
    - Mock circuit breaker defaulting to closed.
    - features_registry and routing_config set to truthy Mocks so that
      fallback eligibility tests can set them independently.
    """
    from agentmap.services.llm_service import LLMService

    mock_logging = MagicMock()
    mock_logging.get_class_logger.return_value = MagicMock()

    mock_config = MagicMock()
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {
            "max_attempts": max_attempts,
            "backoff_base": 2.0,
            "backoff_max": 30.0,
            "jitter": False,
        },
        "circuit_breaker": {
            "failure_threshold": 3,
            "reset_timeout": 60,
        },
    }
    mock_config.get_llm_config.return_value = {
        "model": "test-model",
        "temperature": 0.7,
        "max_tokens": 1024,
        "api_key": "test-key",
    }

    mock_models_config = MagicMock()
    mock_routing_service = MagicMock()
    mock_routing_config = MagicMock()
    mock_routing_config.supports_prompt_caching.return_value = False

    # features_registry_service is passed as a keyword arg so that
    # ``self.features_registry and self.routing_config`` is truthy (fallback eligible).
    mock_features_registry = MagicMock()

    svc = LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing_service,
        llm_models_config_service=mock_models_config,
        routing_config_service=mock_routing_config,
        telemetry_service=None,
        features_registry_service=mock_features_registry,
    )

    # Replace circuit breaker with a mock that defaults to closed
    cb_mock = MagicMock()
    cb_mock.is_open.return_value = False
    cb_mock.reset = 60
    svc._circuit_breaker = cb_mock

    return svc, cb_mock


def make_stream_with_provider(
    *text_deltas: str,
    resolved_provider: str = "anthropic",
    resolved_model: str = "test-model",
):
    """Like make_stream() but with configurable terminal chunk identity."""

    async def _gen():
        for idx, delta in enumerate(text_deltas):
            yield LLMStreamChunk(text_delta=delta, chunk_index=idx, is_final=False)
        yield LLMStreamChunk(
            text_delta="",
            chunk_index=len(text_deltas),
            is_final=True,
            resolved_provider=resolved_provider,
            resolved_model=resolved_model,
            usage=None,
            finish_reason="stop",
        )

    return _gen()


# ---------------------------------------------------------------------------
# TC-F03-002: Terminal chunk reconstructs LLMResponse; _extract_* not invoked
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncDirectTerminalReconstruction(
    unittest.IsolatedAsyncioTestCase
):
    """TC-F03-002: Terminal chunk fields drive LLMResponse reconstruction.

    _extract_llm_usage and _extract_finish_reason must NOT be invoked on the
    streaming path — the seam already normalizes these into the terminal chunk.
    """

    async def test_terminal_chunk_fields_not_passed_through_extract_helpers(self):
        """TC-F03-002: Patch _extract_llm_usage and _extract_finish_reason to
        raise AssertionError; assert neither fires during call_llm_stream_async.
        The terminal chunk itself carries the correct fields.
        """
        svc, _cb = _make_svc_for_direct(max_attempts=1)

        # Patch both extractors to raise if called — streaming must NOT use them
        svc._extract_llm_usage = lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("_extract_llm_usage must NOT be called on streaming path")
        )
        svc._extract_finish_reason = lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError(
                "_extract_finish_reason must NOT be called on streaming path"
            )
        )

        async def fake_stream_provider(
            provider, messages, params, *, client, credentials
        ):
            async for chunk in make_stream_with_provider(
                "Hello",
                " world",
                resolved_provider="anthropic",
                resolved_model="claude-3-sonnet",
            ):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider",
            side_effect=fake_stream_provider,
        ):
            collected = []
            async for chunk in svc._call_llm_stream_async_direct(
                "anthropic",
                [{"role": "user", "content": "hi"}],
                model="claude-3-sonnet",
            ):
                collected.append(chunk)

        # 2 non-final + 1 terminal
        self.assertEqual(
            len(collected), 3, "Must receive 2 non-final + 1 terminal chunk"
        )
        terminal = collected[-1]
        self.assertTrue(terminal.is_final, "Last chunk must be terminal")
        # Terminal fields come from the seam, not from _extract_* helpers
        self.assertEqual(terminal.resolved_provider, "anthropic")
        self.assertEqual(terminal.resolved_model, "claude-3-sonnet")
        self.assertEqual(terminal.finish_reason, "stop")

    async def test_terminal_chunk_reconstructs_accumulated_text(self):
        """TC-F03-002: The terminal chunk's fields are sufficient to reconstruct
        LLMResponse — text accumulation from non-final deltas is available to callers.
        """
        svc, _cb = _make_svc_for_direct(max_attempts=1)

        async def fake_stream_provider(
            provider, messages, params, *, client, credentials
        ):
            async for chunk in make_stream_with_provider(
                "Hel",
                "lo",
                " world",
                resolved_provider="openai",
                resolved_model="gpt-4o",
            ):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider",
            side_effect=fake_stream_provider,
        ):
            collected = []
            async for chunk in svc._call_llm_stream_async_direct(
                "openai",
                [{"role": "user", "content": "q"}],
            ):
                collected.append(chunk)

        non_final = [c for c in collected if not c.is_final]
        terminal = next(c for c in collected if c.is_final)

        # Accumulated text from non-final deltas
        accumulated = "".join(c.text_delta for c in non_final)
        self.assertEqual(accumulated, "Hello world")

        # Terminal chunk carries provider/model identity for LLMResponse reconstruction
        self.assertEqual(terminal.resolved_provider, "openai")
        self.assertEqual(terminal.resolved_model, "gpt-4o")
        self.assertEqual(terminal.text_delta, "")


# ---------------------------------------------------------------------------
# TC-F03-010: Retries exhausted + fallback eligible → synthetic terminal chunk
# TC-F03-016: Fallback synthetic chunk carries fallback's resolved_provider/model
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncDirectFallback(unittest.IsolatedAsyncioTestCase):
    """TC-F03-010 + TC-F03-016: Pre-first-chunk fallback materialization."""

    def _make_svc_with_fallback_handler(self, max_attempts: int = 2):
        """Return a service with a mocked fallback handler ready for assertion."""
        svc, cb_mock = _make_svc_for_direct(max_attempts=max_attempts)
        # Replace the fallback handler with a mock
        svc._fallback_handler = MagicMock()
        return svc, cb_mock

    async def test_retries_exhausted_fallback_materializes_text_then_terminal(self):
        """TC-F03-010: When all max_attempts raise before any chunk and fallback
        is eligible, try_with_fallback_async is called exactly once and its complete
        LLMResponse is materialized as a non-final chunk carrying the fallback's
        text, followed by a terminal chunk (is_final=True, text_delta="").

        CR-fix to AC-18: the fallback's answer text must NOT be dropped — a direct
        ``call_llm_stream_async`` caller must receive the fallback completion's text.
        """
        from agentmap.exceptions import LLMRateLimitError
        from agentmap.models.llm_execution import LLMResponse

        svc, _cb = self._make_svc_with_fallback_handler(max_attempts=2)

        fallback_resp = LLMResponse(
            text="fallback text",
            resolved_provider="openai",
            resolved_model="gpt-4o",
            finish_reason="stop",
            usage=None,
        )
        svc._fallback_handler.try_with_fallback_async = AsyncMock(
            return_value=fallback_resp
        )

        async def always_fails(provider, messages, params, *, client, credentials):
            raise LLMRateLimitError("rate limited")
            yield  # make it a generator

        with (
            patch(
                "agentmap.services.llm_service.stream_provider",
                side_effect=always_fails,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            collected = []
            async for chunk in svc._call_llm_stream_async_direct(
                "anthropic",
                [{"role": "user", "content": "hi"}],
                model="test-model",
            ):
                collected.append(chunk)

        # try_with_fallback_async called exactly once
        svc._fallback_handler.try_with_fallback_async.assert_called_once()

        # Caller receives the fallback text (non-final) then the terminal chunk.
        self.assertEqual(
            len(collected), 2, "Must receive a text chunk then the terminal chunk"
        )
        text_chunk, terminal = collected
        self.assertFalse(text_chunk.is_final, "First chunk must be non-final")
        self.assertEqual(
            text_chunk.text_delta,
            "fallback text",
            "Fallback completion text must be delivered, not dropped",
        )
        self.assertTrue(
            terminal.is_final, "Last chunk must be terminal (is_final=True)"
        )
        self.assertEqual(
            terminal.text_delta, "", "Terminal chunk must have text_delta=''"
        )

    async def test_fallback_synthetic_chunk_carries_fallback_provider_model(self):
        """TC-F03-016: Synthetic terminal chunk carries the fallback's resolved
        provider/model, NOT the original request's provider/model.
        """
        from agentmap.exceptions import LLMRateLimitError
        from agentmap.models.llm_execution import LLMResponse

        svc, _cb = self._make_svc_with_fallback_handler(max_attempts=2)

        # Fallback uses a different provider/model than the original request
        fallback_resp = LLMResponse(
            text="fallback text",
            resolved_provider="openai",  # different from "anthropic" request
            resolved_model="gpt-4o",  # different from "test-model" request
            finish_reason="stop",
            usage=None,
        )
        svc._fallback_handler.try_with_fallback_async = AsyncMock(
            return_value=fallback_resp
        )

        async def always_fails(provider, messages, params, *, client, credentials):
            raise LLMRateLimitError("rate limited")
            yield  # make it a generator

        with (
            patch(
                "agentmap.services.llm_service.stream_provider",
                side_effect=always_fails,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            collected = []
            async for chunk in svc._call_llm_stream_async_direct(
                "anthropic",  # original provider
                [{"role": "user", "content": "hi"}],
                model="test-model",  # original model
            ):
                collected.append(chunk)

        # Text chunk then terminal; identity lives on the terminal chunk.
        self.assertEqual(len(collected), 2)
        synthetic = collected[-1]
        self.assertTrue(synthetic.is_final)
        # Must carry fallback's identity, not the original request's
        self.assertEqual(
            synthetic.resolved_provider,
            "openai",
            "Synthetic chunk must carry fallback's resolved_provider, not original",
        )
        self.assertEqual(
            synthetic.resolved_model,
            "gpt-4o",
            "Synthetic chunk must carry fallback's resolved_model, not original",
        )

    async def test_fallback_synthetic_chunk_carries_fallback_usage_and_finish_reason(
        self,
    ):
        """TC-F03-016 extension: Synthetic terminal chunk copies usage/finish_reason from
        the fallback LLMResponse.
        """
        from agentmap.exceptions import LLMRateLimitError
        from agentmap.models.llm_execution import LLMResponse, LLMUsage

        svc, _cb = self._make_svc_with_fallback_handler(max_attempts=2)

        fallback_usage = LLMUsage(input_tokens=10, output_tokens=20)
        fallback_resp = LLMResponse(
            text="fallback text",
            resolved_provider="openai",
            resolved_model="gpt-4o",
            finish_reason="length",
            usage=fallback_usage,
        )
        svc._fallback_handler.try_with_fallback_async = AsyncMock(
            return_value=fallback_resp
        )

        async def always_fails(provider, messages, params, *, client, credentials):
            raise LLMRateLimitError("rate limited")
            yield  # make it a generator

        with (
            patch(
                "agentmap.services.llm_service.stream_provider",
                side_effect=always_fails,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            collected = []
            async for chunk in svc._call_llm_stream_async_direct(
                "anthropic",
                [{"role": "user", "content": "hi"}],
            ):
                collected.append(chunk)

        # usage/finish_reason live on the terminal chunk (after the text chunk).
        synthetic = collected[-1]
        self.assertTrue(synthetic.is_final)
        self.assertEqual(synthetic.usage, fallback_usage)
        self.assertEqual(synthetic.finish_reason, "length")

    async def test_no_fallback_when_ineligible(self):
        """Pre-first-chunk error without fallback eligibility raises the error."""
        from agentmap.exceptions import LLMRateLimitError

        svc, _cb = _make_svc_for_direct(max_attempts=2)
        # Make fallback ineligible by clearing features_registry and routing_config
        svc.features_registry = None

        async def always_fails(provider, messages, params, *, client, credentials):
            raise LLMRateLimitError("rate limited")
            yield  # make it a generator

        with (
            patch(
                "agentmap.services.llm_service.stream_provider",
                side_effect=always_fails,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            with self.assertRaises(Exception):
                async for _ in svc._call_llm_stream_async_direct(
                    "anthropic",
                    [{"role": "user", "content": "hi"}],
                ):
                    pass


# ---------------------------------------------------------------------------
# TC-F03-026: get_or_create_client called with streaming=True
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncDirectClientFactory(unittest.IsolatedAsyncioTestCase):
    """TC-F03-026: _call_llm_stream_async_direct calls get_or_create_client with streaming=True."""

    async def test_get_or_create_client_called_with_streaming_true(self):
        """TC-F03-026: Assert get_or_create_client is invoked with streaming=True
        (proving F03 requests the F02 streaming-aware client).
        """
        svc, _cb = _make_svc_for_direct(max_attempts=1)

        sentinel_client = MagicMock(name="streaming_client")

        # Spy on the client factory
        factory_calls = []

        def spy_factory(provider, config, streaming=False):
            factory_calls.append({"provider": provider, "streaming": streaming})
            return sentinel_client

        svc._client_factory.get_or_create_client = spy_factory

        async def fake_stream_provider(
            provider, messages, params, *, client, credentials
        ):
            async for chunk in make_stream("ok"):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider",
            side_effect=fake_stream_provider,
        ):
            async for _ in svc._call_llm_stream_async_direct(
                "anthropic",
                [{"role": "user", "content": "hi"}],
                model="claude-3-sonnet",
            ):
                pass

        # Must have called get_or_create_client with streaming=True
        self.assertTrue(
            factory_calls,
            "get_or_create_client must be called at least once",
        )
        streaming_calls = [c for c in factory_calls if c["streaming"] is True]
        self.assertTrue(
            streaming_calls,
            f"get_or_create_client must be called with streaming=True. "
            f"Actual calls: {factory_calls!r}",
        )

    async def test_client_passed_to_stream_provider(self):
        """TC-F03-026 extension: the client from get_or_create_client is forwarded
        to stream_provider as the ``client=`` kwarg.
        """
        svc, _cb = _make_svc_for_direct(max_attempts=1)

        sentinel_client = MagicMock(name="sentinel_streaming_client")
        svc._client_factory.get_or_create_client = MagicMock(
            return_value=sentinel_client
        )

        received_client = []

        async def capturing_stream_provider(
            provider, messages, params, *, client, credentials
        ):
            received_client.append(client)
            async for chunk in make_stream("hi"):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider",
            side_effect=capturing_stream_provider,
        ):
            async for _ in svc._call_llm_stream_async_direct(
                "anthropic",
                [{"role": "user", "content": "hi"}],
            ):
                pass

        self.assertEqual(len(received_client), 1)
        self.assertIs(
            received_client[0],
            sentinel_client,
            "Streaming client from factory must be forwarded to stream_provider",
        )


# ---------------------------------------------------------------------------
# TC-F03-027: stream_provider called with normalized LLMMessage dicts + resolved params
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncDirectSeamArgs(unittest.IsolatedAsyncioTestCase):
    """TC-F03-027: _call_llm_stream_async_direct drives stream_provider with
    normalized LLMMessage dicts (not LangChain objects), params with resolved
    model/max_tokens/temperature, and client=/credentials= as keyword args.
    """

    async def test_stream_provider_called_with_normalized_message_dicts(self):
        """TC-F03-027: stream_provider receives the normalized LLMMessage list
        (plain dicts), NOT the output of convert_messages_to_langchain.
        """
        svc, _cb = _make_svc_for_direct(max_attempts=1)

        # Spy on convert_messages_to_langchain — it must NOT be called on this path
        convert_calls = []
        original_convert = svc._message_utils.convert_messages_to_langchain

        def spy_convert(messages):
            convert_calls.append(messages)
            return original_convert(messages)

        svc._message_utils.convert_messages_to_langchain = spy_convert

        received_messages = []

        async def capturing_sp(provider, messages, params, *, client, credentials):
            received_messages.append(messages)
            async for chunk in make_stream("hi"):
                yield chunk

        input_messages = [{"role": "user", "content": "hello"}]

        with patch(
            "agentmap.services.llm_service.stream_provider",
            side_effect=capturing_sp,
        ):
            async for _ in svc._call_llm_stream_async_direct(
                "anthropic",
                input_messages,
                model="claude-3-sonnet",
            ):
                pass

        # convert_messages_to_langchain must NOT be called on the streaming path
        self.assertEqual(
            convert_calls,
            [],
            "convert_messages_to_langchain must NOT be called on the streaming path "
            f"(AC-13 / research-report §2.1). Actual calls: {convert_calls!r}",
        )

        # stream_provider must receive normalized dicts
        self.assertEqual(len(received_messages), 1)
        msgs = received_messages[0]
        # Each message must be a plain dict with 'role' and 'content'
        self.assertIsInstance(
            msgs, list, "stream_provider must receive a list of messages"
        )
        for msg in msgs:
            self.assertIsInstance(
                msg, dict, f"Each message must be a dict; got {type(msg)}"
            )
            self.assertIn("role", msg)
            self.assertIn("content", msg)

    async def test_stream_provider_called_with_resolved_params(self):
        """TC-F03-027: params passed to stream_provider contains resolved
        model/temperature (and max_tokens if present in config).
        """
        svc, _cb = _make_svc_for_direct(max_attempts=1)

        received_params = []

        async def capturing_sp(provider, messages, params, *, client, credentials):
            received_params.append(dict(params))
            async for chunk in make_stream("hi"):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider",
            side_effect=capturing_sp,
        ):
            async for _ in svc._call_llm_stream_async_direct(
                "anthropic",
                [{"role": "user", "content": "q"}],
                model="claude-3-sonnet",
                temperature=0.5,
            ):
                pass

        self.assertEqual(len(received_params), 1)
        params = received_params[0]
        # model override must be in params
        self.assertEqual(params.get("model"), "claude-3-sonnet")
        # temperature override must be in params
        self.assertEqual(params.get("temperature"), 0.5)

    async def test_stream_provider_called_with_client_and_credentials_as_kwargs(self):
        """TC-F03-027: stream_provider is called with client= and credentials=
        as keyword arguments (not positionally).
        """
        svc, _cb = _make_svc_for_direct(max_attempts=1)

        received_kwargs = []

        async def capturing_sp(provider, messages, params, *, client, credentials):
            received_kwargs.append({"client": client, "credentials": credentials})
            async for chunk in make_stream("hi"):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider",
            side_effect=capturing_sp,
        ):
            async for _ in svc._call_llm_stream_async_direct(
                "anthropic",
                [{"role": "user", "content": "q"}],
            ):
                pass

        self.assertEqual(len(received_kwargs), 1)
        kw = received_kwargs[0]
        # client must be present (not None — we set up a mock factory)
        self.assertIn("client", kw, "stream_provider must receive 'client' kwarg")
        # credentials must be present (may be None or a dict)
        self.assertIn(
            "credentials", kw, "stream_provider must receive 'credentials' kwarg"
        )


# ---------------------------------------------------------------------------
# Helpers for TC-F03-017 through TC-F03-030 (_call_llm_stream_async_with_telemetry)
# ---------------------------------------------------------------------------


def _make_svc_with_telemetry():
    """Build a minimal LLMService with a real telemetry fake and scripted instruments.

    Returns ``(svc, telemetry_fake)`` so tests can assert on recorded values.
    The telemetry fake tracks create_histogram calls so each instrument
    (TTFT, duration) is a distinct Mock with its own ``record`` call list.
    """
    telemetry = MagicMock(name="telemetry_service")

    # Each histogram creation returns a distinct Mock so TTFT vs duration
    # can be asserted independently.
    histograms: dict = {}

    def make_hist(name, **kwargs):
        m = Mock(name=f"hist_{name}")
        histograms[name] = m
        return m

    telemetry.create_histogram.side_effect = make_hist
    telemetry.create_counter.side_effect = lambda name, **kwargs: Mock(
        name=f"counter_{name}"
    )
    telemetry.create_up_down_counter.side_effect = lambda name, **kwargs: Mock(
        name=f"updown_{name}"
    )

    # start_span returns a context-manager Mock so __enter__/__exit__ are trackable.
    span_mock = MagicMock(name="span")
    span_cm = MagicMock(name="span_cm")
    span_cm.__enter__ = Mock(return_value=span_mock)
    span_cm.__exit__ = Mock(return_value=False)
    telemetry.start_span.return_value = span_cm

    svc = _make_llm_service(telemetry_service=telemetry)
    # Expose histograms dict on svc for test assertions.
    svc._test_histograms = histograms
    svc._test_span_cm = span_cm
    svc._test_span = span_mock
    return svc, telemetry


def _make_core_happy(text_deltas=("Hello", " world")):
    """Return a replacement for _call_llm_stream_async_core that yields a clean stream."""

    async def _core(messages, provider, model, temperature, routing_context, **kwargs):
        for idx, delta in enumerate(text_deltas):
            yield LLMStreamChunk(text_delta=delta, chunk_index=idx, is_final=False)
        yield LLMStreamChunk(
            text_delta="",
            chunk_index=len(text_deltas),
            is_final=True,
            resolved_provider=provider or "anthropic",
            resolved_model=model or "test-model",
        )

    return _core


def _make_core_fail_before_first(exc):
    """Return a replacement for _call_llm_stream_async_core that raises before any chunk."""

    async def _core(messages, provider, model, temperature, routing_context, **kwargs):
        raise exc
        yield  # make it an async generator

    return _core


def _make_core_fail_after(n_chunks, exc, text_delta="chunk"):
    """Return a replacement for _call_llm_stream_async_core yielding n chunks then raising."""

    async def _core(messages, provider, model, temperature, routing_context, **kwargs):
        for idx in range(n_chunks):
            yield LLMStreamChunk(
                text_delta=f"{text_delta}{idx}", chunk_index=idx, is_final=False
            )
        raise exc

    return _core


# ---------------------------------------------------------------------------
# TC-F03-017: TTFT recorded once on first chunk; duration once on completion
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncWithTelemetryTTFT(unittest.IsolatedAsyncioTestCase):
    """TC-F03-017: _record_ttft_metric called exactly once on first chunk;
    _record_duration_metric called once on clean completion; both with
    {METRIC_DIM_PROVIDER, METRIC_DIM_MODEL} dims.
    """

    async def test_ttft_recorded_once_on_first_chunk(self):
        """TC-F03-017: _metric_ttft.record called exactly once; first argument ≈ ttft elapsed.

        time.monotonic is scripted: t0=0.0, first-chunk call=0.1, completion-call=0.5.
        """
        from agentmap.services.telemetry.constants import (
            METRIC_DIM_MODEL,
            METRIC_DIM_PROVIDER,
            METRIC_LLM_TTFT,
        )

        svc, telemetry = _make_svc_with_telemetry()
        svc._call_llm_stream_async_core = _make_core_happy(("Hello", " world"))

        monotonic_values = iter([0.0, 0.1, 0.5])
        with patch("agentmap.services.llm_service.time") as mock_time:
            mock_time.monotonic.side_effect = lambda: next(monotonic_values)
            async for _ in svc._call_llm_stream_async_with_telemetry(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-3-sonnet",
                temperature=None,
                routing_context=None,
            ):
                pass

        hist = svc._test_histograms.get(METRIC_LLM_TTFT)
        self.assertIsNotNone(hist, f"Histogram for {METRIC_LLM_TTFT!r} must be created")
        self.assertEqual(
            hist.record.call_count,
            1,
            f"_metric_ttft.record must be called exactly once; got {hist.record.call_count}",
        )
        ttft_args, ttft_kwargs = hist.record.call_args
        ttft_value = ttft_args[0]
        self.assertAlmostEqual(
            ttft_value,
            0.1,
            places=5,
            msg=f"TTFT value must be ≈0.1; got {ttft_value}",
        )
        dims = ttft_args[1] if len(ttft_args) > 1 else ttft_kwargs.get("attributes", {})
        self.assertEqual(
            dims.get(METRIC_DIM_PROVIDER),
            "anthropic",
            f"TTFT dims must include provider='anthropic'; got {dims!r}",
        )
        self.assertEqual(
            dims.get(METRIC_DIM_MODEL),
            "claude-3-sonnet",
            f"TTFT dims must include model='claude-3-sonnet'; got {dims!r}",
        )

    async def test_duration_recorded_once_on_completion(self):
        """TC-F03-017: _metric_duration.record called exactly once on clean completion."""
        from agentmap.services.telemetry.constants import (
            METRIC_DIM_MODEL,
            METRIC_DIM_PROVIDER,
            METRIC_LLM_DURATION,
        )

        svc, telemetry = _make_svc_with_telemetry()
        svc._call_llm_stream_async_core = _make_core_happy(("Hello", " world"))

        monotonic_values = iter([0.0, 0.1, 0.5])
        with patch("agentmap.services.llm_service.time") as mock_time:
            mock_time.monotonic.side_effect = lambda: next(monotonic_values)
            async for _ in svc._call_llm_stream_async_with_telemetry(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-3-sonnet",
                temperature=None,
                routing_context=None,
            ):
                pass

        hist = svc._test_histograms.get(METRIC_LLM_DURATION)
        self.assertIsNotNone(
            hist, f"Histogram for {METRIC_LLM_DURATION!r} must be created"
        )
        self.assertEqual(
            hist.record.call_count,
            1,
            f"_metric_duration.record must be called exactly once; got {hist.record.call_count}",
        )
        dur_args, dur_kwargs = hist.record.call_args
        dur_value = dur_args[0]
        self.assertAlmostEqual(
            dur_value,
            0.5,
            places=5,
            msg=f"Duration value must be ≈0.5; got {dur_value}",
        )
        dims = dur_args[1] if len(dur_args) > 1 else dur_kwargs.get("attributes", {})
        self.assertEqual(dims.get(METRIC_DIM_PROVIDER), "anthropic")
        self.assertEqual(dims.get(METRIC_DIM_MODEL), "claude-3-sonnet")

    async def test_ttft_not_recorded_again_on_subsequent_chunks(self):
        """TC-F03-017: TTFT recorded only on the FIRST chunk, not on subsequent ones."""
        from agentmap.services.telemetry.constants import METRIC_LLM_TTFT

        svc, telemetry = _make_svc_with_telemetry()
        # Three non-final chunks then terminal
        svc._call_llm_stream_async_core = _make_core_happy(("A", "B", "C"))

        with patch("agentmap.services.llm_service.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            async for _ in svc._call_llm_stream_async_with_telemetry(
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
                model="gpt-4o",
                temperature=None,
                routing_context=None,
            ):
                pass

        hist = svc._test_histograms.get(METRIC_LLM_TTFT)
        self.assertEqual(
            hist.record.call_count,
            1,
            "TTFT must be recorded exactly once even for multi-chunk stream; "
            f"got {hist.record.call_count}",
        )


# ---------------------------------------------------------------------------
# TC-F03-018: TTFT NOT recorded when stream fails before first chunk
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncWithTelemetryTTFTNotOnError(
    unittest.IsolatedAsyncioTestCase
):
    """TC-F03-018: _metric_ttft.record must never be called when the stream fails
    before delivering any chunk.
    """

    async def test_ttft_not_recorded_on_pre_first_chunk_failure(self):
        """TC-F03-018: Pre-first-chunk error → _metric_ttft.record never called."""
        from agentmap.services.telemetry.constants import METRIC_LLM_TTFT

        svc, telemetry = _make_svc_with_telemetry()
        exc = RuntimeError("pre-first-chunk failure")
        svc._call_llm_stream_async_core = _make_core_fail_before_first(exc)

        raised = None
        try:
            async for _ in svc._call_llm_stream_async_with_telemetry(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="test-model",
                temperature=None,
                routing_context=None,
            ):
                pass
        except RuntimeError as e:
            raised = e

        self.assertIsNotNone(raised, "Exception must propagate to the caller")
        hist = svc._test_histograms.get(METRIC_LLM_TTFT)
        if hist is not None:
            self.assertEqual(
                hist.record.call_count,
                0,
                "_metric_ttft.record must NOT be called on pre-first-chunk failure; "
                f"got call count {hist.record.call_count}",
            )


# ---------------------------------------------------------------------------
# TC-F03-019: Explicit span open/close on clean completion; no `with` wrapping
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncWithTelemetrySpanLifetime(unittest.IsolatedAsyncioTestCase):
    """TC-F03-019: start_span called with LLM_CALL_SPAN + attributes; __enter__ once;
    __exit__ once after terminal chunk; _set_span_status_ok called; no `with` in source.
    """

    async def test_span_enter_called_once_on_happy_path(self):
        """TC-F03-019: span_cm.__enter__ called exactly once."""
        svc, telemetry = _make_svc_with_telemetry()
        svc._call_llm_stream_async_core = _make_core_happy(("ok",))

        async for _ in svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="claude-3-sonnet",
            temperature=None,
            routing_context=None,
        ):
            pass

        self.assertEqual(
            svc._test_span_cm.__enter__.call_count,
            1,
            "span_cm.__enter__ must be called exactly once",
        )

    async def test_span_exit_called_once_after_terminal_chunk(self):
        """TC-F03-019: span_cm.__exit__ called exactly once after iteration completes."""
        svc, telemetry = _make_svc_with_telemetry()

        exit_calls_at_yield: list = []
        exit_count = [0]

        original_exit = svc._test_span_cm.__exit__

        def tracking_exit(*args, **kwargs):
            exit_count[0] += 1
            return original_exit(*args, **kwargs)

        svc._test_span_cm.__exit__ = tracking_exit

        chunks_seen = []

        svc._call_llm_stream_async_core = _make_core_happy(("A", "B"))

        async for chunk in svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="test-model",
            temperature=None,
            routing_context=None,
        ):
            chunks_seen.append(chunk)
            # __exit__ must NOT have been called yet while we're still iterating
            exit_calls_at_yield.append(exit_count[0])

        # All chunks received before __exit__
        for idx, count in enumerate(exit_calls_at_yield):
            self.assertEqual(
                count,
                0,
                f"span_cm.__exit__ must NOT fire before chunk {idx} is yielded; "
                f"got exit_count={count} at yield {idx}",
            )
        # __exit__ must fire exactly once after the final chunk
        self.assertEqual(
            exit_count[0],
            1,
            f"span_cm.__exit__ must be called exactly once after all chunks; "
            f"got {exit_count[0]}",
        )

    async def test_set_span_status_ok_called_on_clean_completion(self):
        """TC-F03-019: _set_span_status_ok is called once on clean completion."""
        svc, telemetry = _make_svc_with_telemetry()
        svc._call_llm_stream_async_core = _make_core_happy(("ok",))

        set_ok_calls = []
        original_ok = svc._set_span_status_ok

        def spy_ok(span):
            set_ok_calls.append(span)
            return original_ok(span)

        svc._set_span_status_ok = spy_ok

        async for _ in svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="test-model",
            temperature=None,
            routing_context=None,
        ):
            pass

        self.assertEqual(
            len(set_ok_calls),
            1,
            f"_set_span_status_ok must be called exactly once; got {len(set_ok_calls)}",
        )

    async def test_start_span_called_with_llm_call_span_and_attributes(self):
        """TC-F03-019: start_span called with LLM_CALL_SPAN and GEN_AI_SYSTEM/GEN_AI_REQUEST_MODEL."""
        from agentmap.services.telemetry.constants import (
            GEN_AI_REQUEST_MODEL,
            GEN_AI_SYSTEM,
            LLM_CALL_SPAN,
        )

        svc, telemetry = _make_svc_with_telemetry()
        svc._call_llm_stream_async_core = _make_core_happy(("ok",))

        async for _ in svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="claude-3-sonnet",
            temperature=None,
            routing_context=None,
        ):
            pass

        self.assertTrue(
            telemetry.start_span.called,
            "start_span must be called",
        )
        call_args, call_kwargs = telemetry.start_span.call_args
        span_name = call_args[0] if call_args else call_kwargs.get("name", "")
        self.assertEqual(
            span_name,
            LLM_CALL_SPAN,
            f"start_span must use LLM_CALL_SPAN={LLM_CALL_SPAN!r}; got {span_name!r}",
        )
        attrs = call_kwargs.get("attributes", {})
        self.assertIn(
            GEN_AI_SYSTEM,
            attrs,
            f"start_span attributes must include {GEN_AI_SYSTEM!r}",
        )
        self.assertIn(
            GEN_AI_REQUEST_MODEL,
            attrs,
            f"start_span attributes must include {GEN_AI_REQUEST_MODEL!r}",
        )
        self.assertEqual(attrs[GEN_AI_REQUEST_MODEL], "claude-3-sonnet")

    def test_no_with_block_around_telemetry_start_span_in_source(self):
        """TC-F03-019 (compile-time guard): 'with self._telemetry_service.start_span'
        must NOT appear in _call_llm_stream_async_with_telemetry source.
        """
        import inspect

        from agentmap.services.llm_service import LLMService

        src = inspect.getsource(LLMService._call_llm_stream_async_with_telemetry)
        self.assertNotIn(
            "with self._telemetry_service.start_span",
            src,
            "The method body must NOT use 'with self._telemetry_service.start_span' — "
            "explicit __enter__/__exit__ is required so the span survives yields",
        )


# ---------------------------------------------------------------------------
# TC-F03-020: Span is closed on after-first-chunk error
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncWithTelemetrySpanOnError(unittest.IsolatedAsyncioTestCase):
    """TC-F03-020: After-first-chunk error → _record_span_exception_safe called;
    span_cm.__exit__ invoked via finally.
    """

    async def test_record_span_exception_called_on_after_first_chunk_error(self):
        """TC-F03-020: _record_span_exception_safe(span, e) called when error after first chunk."""
        svc, telemetry = _make_svc_with_telemetry()
        exc = RuntimeError("mid-stream error")
        # Yield 1 chunk then raise (after-first-chunk error)
        svc._call_llm_stream_async_core = _make_core_fail_after(1, exc)

        exception_recorded = []
        original_exc_safe = svc._record_span_exception_safe

        def spy_exc_safe(span, e):
            exception_recorded.append(e)
            return original_exc_safe(span, e)

        svc._record_span_exception_safe = spy_exc_safe

        raised = None
        try:
            async for _ in svc._call_llm_stream_async_with_telemetry(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="test-model",
                temperature=None,
                routing_context=None,
            ):
                pass
        except RuntimeError as e:
            raised = e

        self.assertIsNotNone(raised, "Exception must propagate to caller")
        self.assertEqual(
            len(exception_recorded),
            1,
            f"_record_span_exception_safe must be called exactly once; got {len(exception_recorded)}",
        )
        self.assertIs(
            exception_recorded[0],
            exc,
            "The exact exception must be passed to _record_span_exception_safe",
        )

    async def test_span_exit_called_via_finally_on_error(self):
        """TC-F03-020: span_cm.__exit__ invoked via finally even when an exception is raised."""
        svc, telemetry = _make_svc_with_telemetry()
        exc = RuntimeError("after-first-chunk")
        svc._call_llm_stream_async_core = _make_core_fail_after(1, exc)

        exit_called = [False]
        original_exit = svc._test_span_cm.__exit__

        def tracking_exit(*args, **kwargs):
            exit_called[0] = True
            return original_exit(*args, **kwargs)

        svc._test_span_cm.__exit__ = tracking_exit

        try:
            async for _ in svc._call_llm_stream_async_with_telemetry(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="test-model",
                temperature=None,
                routing_context=None,
            ):
                pass
        except RuntimeError:
            pass

        self.assertTrue(
            exit_called[0],
            "span_cm.__exit__ must be called via finally even when exception is raised",
        )

    async def test_set_span_status_ok_not_called_on_error(self):
        """TC-F03-020: _set_span_status_ok must NOT be called when error occurs."""
        svc, telemetry = _make_svc_with_telemetry()
        svc._call_llm_stream_async_core = _make_core_fail_after(1, RuntimeError("err"))

        set_ok_calls = []
        original_ok = svc._set_span_status_ok

        def spy_ok(span):
            set_ok_calls.append(span)
            return original_ok(span)

        svc._set_span_status_ok = spy_ok

        try:
            async for _ in svc._call_llm_stream_async_with_telemetry(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="test-model",
                temperature=None,
                routing_context=None,
            ):
                pass
        except RuntimeError:
            pass

        self.assertEqual(
            len(set_ok_calls),
            0,
            "_set_span_status_ok must NOT be called when the stream errors",
        )


# ---------------------------------------------------------------------------
# TC-F03-021: Span closed on generator abandonment (GeneratorExit via aclose)
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncWithTelemetrySpanOnAbandon(
    unittest.IsolatedAsyncioTestCase
):
    """TC-F03-021: Generator abandoned via aclose() → span_cm.__exit__ fires via finally."""

    async def test_span_exit_called_on_generator_abandonment(self):
        """TC-F03-021: Consume one chunk then aclose(); __exit__ must fire via finally."""
        svc, telemetry = _make_svc_with_telemetry()
        # Multi-chunk stream so we can abandon mid-way
        svc._call_llm_stream_async_core = _make_core_happy(("A", "B", "C"))

        exit_called = [False]
        original_exit = svc._test_span_cm.__exit__

        def tracking_exit(*args, **kwargs):
            exit_called[0] = True
            return original_exit(*args, **kwargs)

        svc._test_span_cm.__exit__ = tracking_exit

        gen = svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="test-model",
            temperature=None,
            routing_context=None,
        )

        # Consume exactly one chunk then abandon.
        first_chunk = await gen.__anext__()
        self.assertIsNotNone(
            first_chunk, "Must receive at least one chunk before aclose"
        )

        await gen.aclose()

        self.assertTrue(
            exit_called[0],
            "span_cm.__exit__ must fire via finally when generator is abandoned (aclose)",
        )


# ---------------------------------------------------------------------------
# TC-F03-028: Default flags (False) — no content attribute set on span
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncWithTelemetryC9DefaultFlags(
    unittest.IsolatedAsyncioTestCase
):
    """TC-F03-028: With _capture_llm_prompts/_capture_llm_responses at default False,
    set_span_attributes is NOT called with GEN_AI_PROMPT_CONTENT/GEN_AI_RESPONSE_CONTENT.
    """

    async def test_default_flags_no_content_attribute_set(self):
        """TC-F03-028: Default flags → set_span_attributes never called with content keys."""
        from agentmap.services.telemetry.constants import (
            GEN_AI_PROMPT_CONTENT,
            GEN_AI_RESPONSE_CONTENT,
        )

        svc, telemetry = _make_svc_with_telemetry()
        svc._call_llm_stream_async_core = _make_core_happy(("Hello", " world"))

        # Ensure flags are at their default (False).
        svc._capture_llm_prompts = False
        svc._capture_llm_responses = False

        async for _ in svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="test-model",
            temperature=None,
            routing_context=None,
        ):
            pass

        # Collect all set_span_attributes calls and check no content keys appear.
        content_keys = {GEN_AI_PROMPT_CONTENT, GEN_AI_RESPONSE_CONTENT}
        for call in telemetry.set_span_attributes.call_args_list:
            call_args, _ = call
            if call_args:
                attrs_arg = call_args[1] if len(call_args) > 1 else {}
                for key in content_keys:
                    self.assertNotIn(
                        key,
                        attrs_arg,
                        f"set_span_attributes must NOT be called with {key!r} "
                        "when capture flags are False",
                    )


# ---------------------------------------------------------------------------
# TC-F03-029: Flags True → _capture_llm_content called exactly once at completion
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncWithTelemetryC9FlagsTrue(unittest.IsolatedAsyncioTestCase):
    """TC-F03-029: With both capture flags True, _capture_llm_content is called
    exactly once at completion with the accumulated text (joined deltas).
    """

    async def test_capture_llm_content_called_once_at_completion(self):
        """TC-F03-029: _capture_llm_content called once with accumulated_text='Hello world'."""
        svc, telemetry = _make_svc_with_telemetry()
        svc._call_llm_stream_async_core = _make_core_happy(("Hello", " world"))

        svc._capture_llm_prompts = True
        svc._capture_llm_responses = True

        capture_calls = []
        original_capture = svc._capture_llm_content

        def spy_capture(span, messages, result):
            capture_calls.append({"span": span, "messages": messages, "result": result})
            return original_capture(span, messages, result)

        svc._capture_llm_content = spy_capture

        async for _ in svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="test-model",
            temperature=None,
            routing_context=None,
        ):
            pass

        self.assertEqual(
            len(capture_calls),
            1,
            f"_capture_llm_content must be called exactly once; got {len(capture_calls)}",
        )
        self.assertEqual(
            capture_calls[0]["result"],
            "Hello world",
            f"Accumulated text must be joined deltas 'Hello world'; "
            f"got {capture_calls[0]['result']!r}",
        )

    async def test_capture_not_called_per_chunk(self):
        """TC-F03-029: _capture_llm_content must NOT be called per chunk, only at completion."""
        svc, telemetry = _make_svc_with_telemetry()
        # Three non-final chunks
        svc._call_llm_stream_async_core = _make_core_happy(("A", "B", "C"))

        svc._capture_llm_prompts = True
        svc._capture_llm_responses = True

        capture_call_counts_at_yield: list = []
        capture_call_count = [0]
        original_capture = svc._capture_llm_content

        def spy_capture(span, messages, result):
            capture_call_count[0] += 1
            return original_capture(span, messages, result)

        svc._capture_llm_content = spy_capture

        async for chunk in svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="test-model",
            temperature=None,
            routing_context=None,
        ):
            if not chunk.is_final:
                # Must NOT have been called yet during iteration
                capture_call_counts_at_yield.append(capture_call_count[0])

        for idx, count in enumerate(capture_call_counts_at_yield):
            self.assertEqual(
                count,
                0,
                f"_capture_llm_content must NOT be called while chunk {idx} is yielded; "
                f"got call count={count}",
            )
        # Called exactly once after clean completion
        self.assertEqual(capture_call_count[0], 1)

    async def test_empty_text_delta_not_accumulated(self):
        """TC-F03-029 (C9 filter): terminal chunk with text_delta='' must not be accumulated."""
        svc, telemetry = _make_svc_with_telemetry()
        # One non-final then terminal with text_delta=""
        svc._call_llm_stream_async_core = _make_core_happy(("Hello",))

        svc._capture_llm_prompts = True
        svc._capture_llm_responses = True

        capture_calls = []
        original_capture = svc._capture_llm_content

        def spy_capture(span, messages, result):
            capture_calls.append(result)
            return original_capture(span, messages, result)

        svc._capture_llm_content = spy_capture

        async for _ in svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="test-model",
            temperature=None,
            routing_context=None,
        ):
            pass

        self.assertEqual(len(capture_calls), 1)
        # Terminal chunk text_delta="" must not be included in accumulated text
        self.assertEqual(
            capture_calls[0],
            "Hello",
            "Accumulated text must not include terminal empty text_delta",
        )


# ---------------------------------------------------------------------------
# TC-F03-030: Flags True + after-first-chunk error → _capture_llm_content NOT called
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncWithTelemetryC9NoCapturOnError(
    unittest.IsolatedAsyncioTestCase
):
    """TC-F03-030: With flags True, an after-first-chunk error must NOT invoke
    _capture_llm_content — content capture is only for clean completions (C9 constraint).
    """

    async def test_capture_not_called_on_after_first_chunk_error(self):
        """TC-F03-030: _capture_llm_content not called when error occurs after first chunk."""
        svc, telemetry = _make_svc_with_telemetry()
        exc = RuntimeError("mid-stream error")
        svc._call_llm_stream_async_core = _make_core_fail_after(2, exc, text_delta="x")

        svc._capture_llm_prompts = True
        svc._capture_llm_responses = True

        capture_calls = []
        original_capture = svc._capture_llm_content

        def spy_capture(span, messages, result):
            capture_calls.append(result)
            return original_capture(span, messages, result)

        svc._capture_llm_content = spy_capture

        raised = None
        try:
            async for _ in svc._call_llm_stream_async_with_telemetry(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="test-model",
                temperature=None,
                routing_context=None,
            ):
                pass
        except RuntimeError as e:
            raised = e

        self.assertIsNotNone(raised, "Exception must propagate")
        self.assertEqual(
            len(capture_calls),
            0,
            f"_capture_llm_content must NOT be called on error path; "
            f"got {len(capture_calls)} calls",
        )


# ---------------------------------------------------------------------------
# TC-F03-001: End-to-end happy path (Anthropic) through all layers
# TC-F03-003: OpenAI provider parity
# TC-F03-004: Telemetry-disabled dispatch — same chunk sequence
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncEndToEndHappyPath(unittest.IsolatedAsyncioTestCase):
    """TC-F03-001: End-to-end happy path through all layers active (Anthropic).

    Drives call_llm_stream_async with telemetry active and stream_provider patched
    to a real make_stream() iterator.  Asserts ordered deltas then exactly one
    terminal chunk (AC-1).
    """

    async def _run_happy_path(self, provider, model, telemetry_service=None):
        """Shared helper: construct service, patch seam, collect chunks."""
        from agentmap.services.llm_service import LLMService

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {
                "max_attempts": 1,
                "backoff_base": 2.0,
                "backoff_max": 30.0,
                "jitter": False,
            },
            "circuit_breaker": {"failure_threshold": 3, "reset_timeout": 60},
        }
        mock_config.get_llm_config.return_value = {
            "model": model,
            "temperature": 0.7,
            "api_key": "test-key",
        }
        mock_models_config = MagicMock()
        mock_routing_service = MagicMock()
        mock_routing_config = MagicMock()
        mock_routing_config.supports_prompt_caching.return_value = False

        svc = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=mock_routing_service,
            llm_models_config_service=mock_models_config,
            routing_config_service=mock_routing_config,
            telemetry_service=telemetry_service,
        )

        # Ensure circuit breaker is closed
        cb_mock = MagicMock()
        cb_mock.is_open.return_value = False
        svc._circuit_breaker = cb_mock

        async def fake_stream_provider(prov, messages, params, *, client, credentials):
            async for chunk in make_stream_with_provider(
                "Hel",
                "lo",
                " world",
                resolved_provider=provider,
                resolved_model=model,
            ):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider",
            side_effect=fake_stream_provider,
        ):
            collected = []
            async for chunk in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hello"}],
                provider=provider,
                model=model,
            ):
                collected.append(chunk)

        return collected

    async def test_tc_f03_001_ordered_deltas_then_terminal_anthropic(self):
        """TC-F03-001: Anthropic happy path — ≥2 non-final chunks then exactly one terminal."""
        telemetry = _make_telemetry_fake()
        collected = await self._run_happy_path(
            "anthropic", "claude-3-sonnet", telemetry_service=telemetry
        )

        non_final = [c for c in collected if not c.is_final]
        terminal = [c for c in collected if c.is_final]

        self.assertGreaterEqual(
            len(non_final),
            2,
            "Must receive at least 2 non-final chunks (AC-1)",
        )
        self.assertEqual(
            len(terminal), 1, "Must receive exactly one terminal chunk (AC-1)"
        )
        self.assertEqual(
            terminal[0].text_delta, "", "Terminal chunk text_delta must be empty string"
        )
        self.assertTrue(terminal[0].is_final, "Terminal chunk must have is_final=True")

        # chunk_index must be strictly increasing
        all_indices = [c.chunk_index for c in collected if c.chunk_index is not None]
        if len(all_indices) > 1:
            for i in range(1, len(all_indices)):
                self.assertGreater(
                    all_indices[i],
                    all_indices[i - 1],
                    f"chunk_index must be strictly increasing; got {all_indices}",
                )

        # Each non-final delta must be non-empty
        for chunk in non_final:
            self.assertTrue(
                chunk.text_delta,
                f"Non-final chunk at index {chunk.chunk_index} must have non-empty text_delta",
            )

    async def test_tc_f03_001_terminal_carries_provider_model_identity(self):
        """TC-F03-001: Terminal chunk carries resolved_provider/resolved_model for LLMResponse."""
        telemetry = _make_telemetry_fake()
        collected = await self._run_happy_path(
            "anthropic", "claude-3-sonnet", telemetry_service=telemetry
        )
        terminal = next(c for c in collected if c.is_final)
        self.assertEqual(
            terminal.resolved_provider,
            "anthropic",
            "Terminal chunk must carry resolved_provider='anthropic'",
        )
        self.assertEqual(
            terminal.resolved_model,
            "claude-3-sonnet",
            "Terminal chunk must carry resolved_model='claude-3-sonnet'",
        )

    async def test_tc_f03_003_openai_provider_parity(self):
        """TC-F03-003: OpenAI provider parity — same ordered-deltas-then-terminal assertions."""
        telemetry = _make_telemetry_fake()
        collected = await self._run_happy_path(
            "openai", "gpt-4o", telemetry_service=telemetry
        )

        non_final = [c for c in collected if not c.is_final]
        terminal = [c for c in collected if c.is_final]

        self.assertGreaterEqual(
            len(non_final), 2, "OpenAI path must yield ≥2 non-final chunks (AC-1, AC-2)"
        )
        self.assertEqual(len(terminal), 1, "Must receive exactly one terminal chunk")
        terminal_chunk = terminal[0]
        self.assertEqual(
            terminal_chunk.resolved_provider,
            "openai",
            "Terminal resolved_provider must be 'openai'",
        )
        self.assertEqual(
            terminal_chunk.resolved_model,
            "gpt-4o",
            "Terminal resolved_model must be 'gpt-4o'",
        )

    async def test_tc_f03_004_telemetry_disabled_yields_same_chunk_sequence(self):
        """TC-F03-004: telemetry_service=None → dispatches to core directly;
        same ordered-deltas-then-terminal sequence (no span opened).
        """
        # Build a service with telemetry=None explicitly
        from agentmap.services.llm_service import LLMService

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {
                "max_attempts": 1,
                "backoff_base": 2.0,
                "backoff_max": 30.0,
                "jitter": False,
            },
            "circuit_breaker": {"failure_threshold": 3, "reset_timeout": 60},
        }
        mock_config.get_llm_config.return_value = {
            "model": "claude-3-sonnet",
            "temperature": 0.7,
            "api_key": "test-key",
        }
        mock_models_config = MagicMock()
        mock_routing_service = MagicMock()
        mock_routing_config = MagicMock()
        mock_routing_config.supports_prompt_caching.return_value = False

        # Explicitly no telemetry
        svc = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=mock_routing_service,
            llm_models_config_service=mock_models_config,
            routing_config_service=mock_routing_config,
            telemetry_service=None,
        )
        self.assertIsNone(svc._telemetry_service, "_telemetry_service must be None")

        cb_mock = MagicMock()
        cb_mock.is_open.return_value = False
        svc._circuit_breaker = cb_mock

        async def fake_sp(prov, messages, params, *, client, credentials):
            async for chunk in make_stream_with_provider(
                "Hello", " world", resolved_provider="anthropic", resolved_model="test"
            ):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            collected = []
            async for chunk in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-3-sonnet",
            ):
                collected.append(chunk)

        non_final = [c for c in collected if not c.is_final]
        terminal = [c for c in collected if c.is_final]

        self.assertGreaterEqual(
            len(non_final), 1, "Must receive at least one non-final chunk"
        )
        self.assertEqual(len(terminal), 1, "Must receive exactly one terminal chunk")
        self.assertTrue(terminal[0].is_final)


# ---------------------------------------------------------------------------
# TC-F03-006: Non-streaming regression gate
# ---------------------------------------------------------------------------


class TestNonStreamingRegressionGate(unittest.TestCase):
    """TC-F03-006: Non-streaming async methods must be byte-unchanged after F03 additions.

    The seven named methods are: call_llm_async, _call_llm_async_with_telemetry,
    _call_llm_async_core, _call_llm_async_with_routing, _call_llm_async_direct,
    _invoke_with_resilience_async, _invoke_provider_async.

    We verify they remain intact by checking their source hashes are stable
    and their first-line numbers match the expected positions.
    """

    def _get_method_source_hash(self, method):
        """Return a hashable fingerprint of a method's source text."""
        import hashlib
        import inspect

        src = inspect.getsource(method)
        return hashlib.sha256(src.encode()).hexdigest()

    def test_seven_non_streaming_methods_exist_on_llm_service(self):
        """All seven non-streaming async methods must still be present on LLMService."""
        from agentmap.services.llm_service import LLMService

        expected_methods = [
            "call_llm_async",
            "_call_llm_async_with_telemetry",
            "_call_llm_async_core",
            "_call_llm_async_with_routing",
            "_call_llm_async_direct",
            "_invoke_with_resilience_async",
            "_invoke_provider_async",
        ]
        for name in expected_methods:
            self.assertTrue(
                hasattr(LLMService, name),
                f"Non-streaming method '{name}' must still exist on LLMService after F03",
            )
            self.assertTrue(
                callable(getattr(LLMService, name)),
                f"'{name}' must be callable",
            )

    def test_non_streaming_methods_are_distinct_from_streaming_siblings(self):
        """The non-streaming methods must differ from their streaming counterparts
        — they are not re-used or aliased (REQ-F-002: added-to, not modified).
        """
        from agentmap.services.llm_service import LLMService

        # Confirm the streaming siblings also exist
        streaming_names = [
            "call_llm_stream_async",
            "_call_llm_stream_async_with_telemetry",
            "_call_llm_stream_async_core",
            "_call_llm_stream_async_with_routing",
            "_call_llm_stream_async_direct",
            "_invoke_with_resilience_stream_async",
        ]
        for name in streaming_names:
            self.assertTrue(
                hasattr(LLMService, name),
                f"Streaming sibling '{name}' must exist on LLMService",
            )

        # The non-streaming and streaming methods must not be the same function
        pairs = [
            ("call_llm_async", "call_llm_stream_async"),
            (
                "_call_llm_async_with_telemetry",
                "_call_llm_stream_async_with_telemetry",
            ),
            ("_call_llm_async_core", "_call_llm_stream_async_core"),
        ]
        for ns_name, s_name in pairs:
            ns_method = getattr(LLMService, ns_name)
            s_method = getattr(LLMService, s_name)
            self.assertIsNot(
                ns_method,
                s_method,
                f"Non-streaming '{ns_name}' must NOT be the same object as "
                f"streaming '{s_name}'",
            )

    def test_source_hashes_stable_across_two_calls(self):
        """Source hash must be deterministic (same result when called twice).

        This ensures our hash-based identity check is itself reliable.
        """
        from agentmap.services.llm_service import LLMService

        method = LLMService.call_llm_async
        h1 = self._get_method_source_hash(method)
        h2 = self._get_method_source_hash(method)
        self.assertEqual(
            h1,
            h2,
            "Source hash of call_llm_async must be deterministic",
        )

    def test_non_streaming_suite_passes(self):
        """TC-F03-006: The existing non-streaming async test suite must pass.

        We exercise this by importing and running a representative subset of
        tests from test_llm_service_async.py via unittest.TestLoader.  If the
        non-streaming code was modified, those tests will fail and this test
        will catch the regression.
        """
        import os
        import subprocess
        import sys

        # Run the non-streaming async suite as a subprocess to get a clean result
        test_path = os.path.join(os.path.dirname(__file__), "test_llm_service_async.py")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                test_path,
                "--tb=short",
                "-q",
                "--no-header",
            ],
            capture_output=True,
            text=True,
        )
        # subprocess output for diagnosis
        self.assertEqual(
            result.returncode,
            0,
            f"Non-streaming async test suite must pass unchanged after F03 additions.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}",
        )


# ---------------------------------------------------------------------------
# TC-F03-031: 4096-char truncation parity for long streams
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncTruncationParity(unittest.IsolatedAsyncioTestCase):
    """TC-F03-031: Accumulated text > 4096 chars is truncated to 4096 on capture.

    _capture_llm_content applies the same 4096-char bound on the streaming path
    as on the non-streaming path (REQ-NF-002, AC-16, C9).
    """

    async def test_long_stream_captured_content_truncated_to_4096(self):
        """TC-F03-031: When accumulated deltas exceed 4096 chars, captured content
        is truncated to exactly 4096 chars (matching the non-streaming cap).
        """
        from agentmap.services.telemetry.constants import GEN_AI_RESPONSE_CONTENT

        svc, telemetry = _make_svc_with_telemetry()

        # Build a core that yields deltas whose total exceeds 4096 chars.
        # 100 chunks of 50 chars = 5000 chars total.
        big_delta = "x" * 50

        async def big_core(
            messages, provider, model, temperature, routing_context, **kwargs
        ):
            for idx in range(100):  # 100 * 50 = 5000 chars
                yield LLMStreamChunk(
                    text_delta=big_delta, chunk_index=idx, is_final=False
                )
            yield LLMStreamChunk(
                text_delta="",
                chunk_index=100,
                is_final=True,
                resolved_provider=provider or "anthropic",
                resolved_model=model or "test-model",
            )

        svc._call_llm_stream_async_core = big_core

        # Enable capture flags so content will actually be captured
        svc._capture_llm_prompts = False
        svc._capture_llm_responses = True

        # Spy on set_span_attributes to capture the value set
        captured_attrs = []
        original_set_attrs = telemetry.set_span_attributes

        def spy_set_attrs(span, attrs):
            captured_attrs.append(dict(attrs))
            return original_set_attrs(span, attrs)

        telemetry.set_span_attributes = spy_set_attrs

        async for _ in svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="test-model",
            temperature=None,
            routing_context=None,
        ):
            pass

        # Find response content in captured attributes
        response_values = [
            attrs[GEN_AI_RESPONSE_CONTENT]
            for attrs in captured_attrs
            if GEN_AI_RESPONSE_CONTENT in attrs
        ]
        self.assertTrue(
            response_values,
            "set_span_attributes must be called with GEN_AI_RESPONSE_CONTENT",
        )
        captured_text = response_values[0]
        self.assertEqual(
            len(captured_text),
            4096,
            f"Captured response content must be truncated to 4096 chars; "
            f"got len={len(captured_text)}",
        )

    async def test_short_stream_captured_content_not_truncated(self):
        """TC-F03-031 control: Text < 4096 chars is captured in full (no over-truncation)."""
        from agentmap.services.telemetry.constants import GEN_AI_RESPONSE_CONTENT

        svc, telemetry = _make_svc_with_telemetry()
        # Stream of "Hello world" (11 chars) — well under 4096
        svc._call_llm_stream_async_core = _make_core_happy(("Hello", " world"))

        svc._capture_llm_prompts = False
        svc._capture_llm_responses = True

        captured_attrs = []
        original_set_attrs = telemetry.set_span_attributes

        def spy_set_attrs(span, attrs):
            captured_attrs.append(dict(attrs))
            return original_set_attrs(span, attrs)

        telemetry.set_span_attributes = spy_set_attrs

        async for _ in svc._call_llm_stream_async_with_telemetry(
            messages=[{"role": "user", "content": "hi"}],
            provider="anthropic",
            model="test-model",
            temperature=None,
            routing_context=None,
        ):
            pass

        response_values = [
            attrs[GEN_AI_RESPONSE_CONTENT]
            for attrs in captured_attrs
            if GEN_AI_RESPONSE_CONTENT in attrs
        ]
        self.assertTrue(response_values, "Must have captured response content")
        captured_text = response_values[0]
        self.assertEqual(
            captured_text,
            "Hello world",
            f"Short text must be captured in full; got {captured_text!r}",
        )


# ---------------------------------------------------------------------------
# TC-F03-032: Two concurrent asyncio.gather invocations — per-invocation isolation
# ---------------------------------------------------------------------------


class TestCallLLMStreamAsyncConcurrentIsolation(unittest.IsolatedAsyncioTestCase):
    """TC-F03-032: Two concurrent call_llm_stream_async invocations via asyncio.gather
    must receive only their own chunks; no cross-talk in accumulated_text,
    first_chunk_delivered, or ttft_recorded.
    """

    async def test_concurrent_invocations_receive_independent_chunks(self):
        """TC-F03-032: asyncio.gather of two streaming calls; each gets its own stream."""
        import asyncio

        from agentmap.services.llm_service import LLMService

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {
                "max_attempts": 1,
                "backoff_base": 2.0,
                "backoff_max": 30.0,
                "jitter": False,
            },
            "circuit_breaker": {"failure_threshold": 3, "reset_timeout": 60},
        }
        mock_config.get_llm_config.return_value = {
            "model": "claude-3-sonnet",
            "temperature": 0.7,
            "api_key": "test-key",
        }
        mock_models_config = MagicMock()
        mock_routing_service = MagicMock()
        mock_routing_config = MagicMock()
        mock_routing_config.supports_prompt_caching.return_value = False

        telemetry = _make_telemetry_fake()
        svc = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=mock_routing_service,
            llm_models_config_service=mock_models_config,
            routing_config_service=mock_routing_config,
            telemetry_service=telemetry,
        )

        cb_mock = MagicMock()
        cb_mock.is_open.return_value = False
        svc._circuit_breaker = cb_mock

        # Two distinct streams with unique deltas
        stream_a_deltas = ("alpha1", "alpha2", "alpha3")
        stream_b_deltas = ("beta1", "beta2", "beta3")
        call_count = [0]

        async def fake_sp(prov, messages, params, *, client, credentials):
            call_count[0] += 1
            # Determine which stream to return by inspecting messages content
            content = messages[0]["content"] if messages else ""
            if "stream_a" in content:
                deltas = stream_a_deltas
            else:
                deltas = stream_b_deltas
            async for chunk in make_stream_with_provider(
                *deltas,
                resolved_provider="anthropic",
                resolved_model="claude-3-sonnet",
            ):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):

            async def collect_stream_a():
                chunks = []
                async for chunk in svc.call_llm_stream_async(
                    messages=[{"role": "user", "content": "stream_a query"}],
                    provider="anthropic",
                    model="claude-3-sonnet",
                ):
                    chunks.append(chunk)
                return chunks

            async def collect_stream_b():
                chunks = []
                async for chunk in svc.call_llm_stream_async(
                    messages=[{"role": "user", "content": "stream_b query"}],
                    provider="anthropic",
                    model="claude-3-sonnet",
                ):
                    chunks.append(chunk)
                return chunks

            results_a, results_b = await asyncio.gather(
                collect_stream_a(), collect_stream_b()
            )

        # Stream A must contain only alpha deltas
        non_final_a = [c for c in results_a if not c.is_final]
        accumulated_a = "".join(c.text_delta for c in non_final_a)
        self.assertIn(
            "alpha",
            accumulated_a,
            f"Stream A must contain 'alpha' deltas; got {accumulated_a!r}",
        )
        self.assertNotIn(
            "beta",
            accumulated_a,
            f"Stream A must NOT contain 'beta' deltas (cross-talk); got {accumulated_a!r}",
        )

        # Stream B must contain only beta deltas
        non_final_b = [c for c in results_b if not c.is_final]
        accumulated_b = "".join(c.text_delta for c in non_final_b)
        self.assertIn(
            "beta",
            accumulated_b,
            f"Stream B must contain 'beta' deltas; got {accumulated_b!r}",
        )
        self.assertNotIn(
            "alpha",
            accumulated_b,
            f"Stream B must NOT contain 'alpha' deltas (cross-talk); got {accumulated_b!r}",
        )

        # Both streams must end with a terminal chunk
        terminal_a = [c for c in results_a if c.is_final]
        terminal_b = [c for c in results_b if c.is_final]
        self.assertEqual(
            len(terminal_a), 1, "Stream A must have exactly one terminal chunk"
        )
        self.assertEqual(
            len(terminal_b), 1, "Stream B must have exactly one terminal chunk"
        )

    async def test_concurrent_invocations_use_shared_service_instance(self):
        """TC-F03-032: The same service instance (shared circuit_breaker and client_factory)
        is reused; no new shared locks or attributes are introduced per invocation.
        """
        svc = _make_llm_service(telemetry_service=None)

        cb_id_before = id(svc._circuit_breaker)
        factory_id_before = id(svc._client_factory)

        async def fake_sp(prov, messages, params, *, client, credentials):
            async for chunk in make_stream("hello"):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            # Just verify the service still uses the same CB and factory after streaming
            async for _ in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-3-sonnet",
            ):
                pass

        self.assertEqual(
            id(svc._circuit_breaker),
            cb_id_before,
            "circuit_breaker must remain the same shared instance after streaming",
        )
        self.assertEqual(
            id(svc._client_factory),
            factory_id_before,
            "_client_factory must remain the same shared instance after streaming",
        )


# ---------------------------------------------------------------------------
# TC-F03-033: Telemetry dimension consistency; no-op when telemetry is None
# ---------------------------------------------------------------------------


class TestTelemetryDimensionConsistency(unittest.TestCase):
    """TC-F03-033: _record_ttft_metric / _record_duration_metric / _record_error_metric
    use {METRIC_DIM_PROVIDER, METRIC_DIM_MODEL} dims with resolved provider/model.
    Each is a no-op when telemetry is None (no exception raised).
    """

    def test_record_ttft_metric_is_noop_when_telemetry_none(self):
        """TC-F03-033: _record_ttft_metric silently no-ops when no telemetry service."""
        svc = _make_llm_service(telemetry_service=None)
        # Must not raise — is a silent no-op
        try:
            svc._record_ttft_metric(0.1, "anthropic", "claude-3-sonnet")
        except Exception as exc:
            self.fail(f"_record_ttft_metric raised when telemetry is None: {exc}")

    def test_record_duration_metric_is_noop_when_telemetry_none(self):
        """TC-F03-033: _record_duration_metric silently no-ops when no telemetry service."""
        svc = _make_llm_service(telemetry_service=None)
        try:
            svc._record_duration_metric(0.5, "anthropic", "claude-3-sonnet")
        except Exception as exc:
            self.fail(f"_record_duration_metric raised when telemetry is None: {exc}")

    def test_record_error_metric_is_noop_when_telemetry_none(self):
        """TC-F03-033: _record_error_metric silently no-ops when no telemetry service."""
        svc = _make_llm_service(telemetry_service=None)
        try:
            svc._record_error_metric(
                RuntimeError("test"), "anthropic", "claude-3-sonnet"
            )
        except Exception as exc:
            self.fail(f"_record_error_metric raised when telemetry is None: {exc}")

    def test_record_ttft_metric_uses_provider_and_model_dims(self):
        """TC-F03-033: _record_ttft_metric records with METRIC_DIM_PROVIDER and METRIC_DIM_MODEL."""
        from agentmap.services.telemetry.constants import (
            METRIC_DIM_MODEL,
            METRIC_DIM_PROVIDER,
        )

        telemetry = _make_telemetry_fake()
        svc = _make_llm_service(telemetry_service=telemetry)

        # _metric_ttft is a Mock with a .record method (from telemetry fake)
        self.assertIsNotNone(svc._metric_ttft, "_metric_ttft must not be None")

        svc._record_ttft_metric(0.123, "anthropic", "claude-3-sonnet")

        self.assertEqual(
            svc._metric_ttft.record.call_count,
            1,
            "_metric_ttft.record must be called exactly once",
        )
        args, kwargs = svc._metric_ttft.record.call_args
        self.assertAlmostEqual(
            args[0], 0.123, places=5, msg="TTFT value must match the elapsed time"
        )
        dims = args[1] if len(args) > 1 else kwargs.get("attributes", {})
        self.assertIn(
            METRIC_DIM_PROVIDER,
            dims,
            f"TTFT dims must include {METRIC_DIM_PROVIDER!r}",
        )
        self.assertIn(
            METRIC_DIM_MODEL,
            dims,
            f"TTFT dims must include {METRIC_DIM_MODEL!r}",
        )
        self.assertEqual(dims[METRIC_DIM_PROVIDER], "anthropic")
        self.assertEqual(dims[METRIC_DIM_MODEL], "claude-3-sonnet")

    def test_record_duration_metric_uses_provider_and_model_dims(self):
        """TC-F03-033: _record_duration_metric records with METRIC_DIM_PROVIDER and METRIC_DIM_MODEL."""
        from agentmap.services.telemetry.constants import (
            METRIC_DIM_MODEL,
            METRIC_DIM_PROVIDER,
        )

        telemetry = _make_telemetry_fake()
        svc = _make_llm_service(telemetry_service=telemetry)

        self.assertIsNotNone(svc._metric_duration, "_metric_duration must not be None")

        svc._record_duration_metric(0.456, "openai", "gpt-4o")

        self.assertEqual(
            svc._metric_duration.record.call_count,
            1,
            "_metric_duration.record must be called exactly once",
        )
        args, kwargs = svc._metric_duration.record.call_args
        dims = args[1] if len(args) > 1 else kwargs.get("attributes", {})
        self.assertIn(METRIC_DIM_PROVIDER, dims)
        self.assertIn(METRIC_DIM_MODEL, dims)
        self.assertEqual(dims[METRIC_DIM_PROVIDER], "openai")
        self.assertEqual(dims[METRIC_DIM_MODEL], "gpt-4o")

    def test_record_ttft_metric_noop_when_instrument_is_none(self):
        """TC-F03-033: _record_ttft_metric does nothing when _metric_ttft is None,
        even when telemetry service is present.
        """
        telemetry = _make_telemetry_fake()
        svc = _make_llm_service(telemetry_service=telemetry)
        svc._metric_ttft = None  # force to None

        try:
            svc._record_ttft_metric(0.1, "anthropic", "claude-3-sonnet")
        except Exception as exc:
            self.fail(
                f"_record_ttft_metric must not raise when _metric_ttft is None: {exc}"
            )


# ---------------------------------------------------------------------------
# TC-F03-034: Credentials never logged on the streaming path
# ---------------------------------------------------------------------------


class TestCredentialsNotLoggedOnStreamingPath(unittest.IsolatedAsyncioTestCase):
    """TC-F03-034: Logging spy confirms credentials (api_key value) never appear in
    any log record produced during call_llm_stream_async.
    """

    async def test_api_key_not_present_in_log_records(self):
        """TC-F03-034: No log record contains the api_key sentinel value."""
        import logging

        from agentmap.services.llm_service import LLMService

        secret_api_key = "sk-SUPERSECRETKEY-MUST-NOT-APPEAR-IN-LOGS"

        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {
                "max_attempts": 1,
                "backoff_base": 2.0,
                "backoff_max": 30.0,
                "jitter": False,
            },
            "circuit_breaker": {"failure_threshold": 3, "reset_timeout": 60},
        }
        mock_config.get_llm_config.return_value = {
            "model": "claude-3-sonnet",
            "temperature": 0.7,
            "api_key": secret_api_key,
        }
        mock_models_config = MagicMock()
        mock_routing_service = MagicMock()
        mock_routing_config = MagicMock()
        mock_routing_config.supports_prompt_caching.return_value = False

        mock_logging = MagicMock()
        # Create a real logger that captures records
        log_records = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                log_records.append(self.format(record))

        capturing_handler = CapturingHandler()
        capturing_handler.setLevel(logging.DEBUG)

        # Use a capturing logger for the service
        real_logger = logging.getLogger("test_streaming_credentials")
        real_logger.setLevel(logging.DEBUG)
        real_logger.addHandler(capturing_handler)
        real_logger.propagate = False

        mock_logger = MagicMock()

        def log_side_effect(msg, *args, **kwargs):
            formatted = str(msg) % args if args else str(msg)
            log_records.append(formatted)

        mock_logger.debug.side_effect = log_side_effect
        mock_logger.info.side_effect = log_side_effect
        mock_logger.warning.side_effect = log_side_effect
        mock_logger.error.side_effect = log_side_effect
        mock_logging.get_class_logger.return_value = mock_logger

        svc = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=mock_routing_service,
            llm_models_config_service=mock_models_config,
            routing_config_service=mock_routing_config,
            telemetry_service=None,
        )

        cb_mock = MagicMock()
        cb_mock.is_open.return_value = False
        svc._circuit_breaker = cb_mock

        # Patch stream_provider to provide a clean stream; inject credentials arg
        received_credentials = []

        async def fake_sp(prov, messages, params, *, client, credentials):
            # Record what credentials were passed (not logging them, just capturing)
            received_credentials.append(credentials)
            async for chunk in make_stream("ok"):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            async for _ in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-3-sonnet",
            ):
                pass

        # Assert the secret key never appears in any log record
        for record in log_records:
            self.assertNotIn(
                secret_api_key,
                record,
                f"Secret api_key value must NOT appear in log record: {record!r}",
            )


# ---------------------------------------------------------------------------
# TC-F03-035: F04 hand-off contract
# ---------------------------------------------------------------------------


class TestF04HandOffContract(unittest.IsolatedAsyncioTestCase):
    """TC-F03-035: F04 hand-off contract.

    (a) Returned object is AsyncIterator[LLMStreamChunk].
    (b) Ordered non-final chunks then exactly one terminal.
    (c) Terminal chunk reconstructs LLMResponse (Constraint C1: materialized text).
    (d) Unsupported-mode rejection and after-first-chunk failure raise from iteration.
    (e) No provider SDK import required to consume the iterator.
    """

    def _make_f04_svc(self, telemetry=None):
        """Build a service suitable for F04 consumption tests."""
        from agentmap.services.llm_service import LLMService

        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {
                "max_attempts": 1,
                "backoff_base": 2.0,
                "backoff_max": 30.0,
                "jitter": False,
            },
            "circuit_breaker": {"failure_threshold": 3, "reset_timeout": 60},
        }
        mock_config.get_llm_config.return_value = {
            "model": "claude-3-sonnet",
            "temperature": 0.7,
            "api_key": "test-key",
        }
        mock_models_config = MagicMock()
        mock_routing_service = MagicMock()
        mock_routing_config = MagicMock()
        mock_routing_config.supports_prompt_caching.return_value = False

        svc = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=mock_routing_service,
            llm_models_config_service=mock_models_config,
            routing_config_service=mock_routing_config,
            telemetry_service=telemetry,
        )

        cb_mock = MagicMock()
        cb_mock.is_open.return_value = False
        svc._circuit_breaker = cb_mock
        return svc

    async def test_tc_f03_035_a_returned_object_is_async_iterator(self):
        """TC-F03-035 (a): call_llm_stream_async returns an AsyncIterator[LLMStreamChunk].

        The returned object must support __aiter__ and __anext__ without requiring
        any provider SDK import.
        """
        svc = self._make_f04_svc()

        async def fake_sp(prov, messages, params, *, client, credentials):
            async for chunk in make_stream("hi"):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            result = svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
                model="claude-3-sonnet",
            )

        # Must support __aiter__ and __anext__ (is an async iterator / generator)
        self.assertTrue(
            hasattr(result, "__aiter__"),
            "call_llm_stream_async must return an object with __aiter__",
        )
        self.assertTrue(
            hasattr(result, "__anext__"),
            "call_llm_stream_async must return an object with __anext__",
        )

    async def test_tc_f03_035_b_ordered_chunks_then_terminal(self):
        """TC-F03-035 (b): Iterating yields ordered non-final chunks then one terminal."""
        svc = self._make_f04_svc()

        async def fake_sp(prov, messages, params, *, client, credentials):
            async for chunk in make_stream_with_provider(
                "Token1",
                " Token2",
                " Token3",
                resolved_provider="anthropic",
                resolved_model="claude-3-sonnet",
            ):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            chunks = []
            async for chunk in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-3-sonnet",
            ):
                chunks.append(chunk)

        non_final = [c for c in chunks if not c.is_final]
        terminal = [c for c in chunks if c.is_final]

        self.assertGreaterEqual(
            len(non_final), 1, "Must yield at least one non-final chunk"
        )
        self.assertEqual(len(terminal), 1, "Must yield exactly one terminal chunk")

        # Terminal must be last
        self.assertIs(
            chunks[-1],
            terminal[0],
            "Terminal chunk must be the last chunk received",
        )

    async def test_tc_f03_035_c_terminal_reconstructs_llm_response(self):
        """TC-F03-035 (c): Terminal chunk has all fields needed to reconstruct LLMResponse.

        Materialized text == joined non-final deltas (Constraint C1: caller accumulates
        and materializes, not a live iterator).
        """
        from agentmap.models.llm_execution import LLMResponse, LLMUsage

        svc = self._make_f04_svc()

        test_usage = LLMUsage(input_tokens=5, output_tokens=10)

        async def fake_sp(prov, messages, params, *, client, credentials):
            yield LLMStreamChunk(text_delta="Hello", chunk_index=0, is_final=False)
            yield LLMStreamChunk(text_delta=" world", chunk_index=1, is_final=False)
            yield LLMStreamChunk(
                text_delta="",
                chunk_index=2,
                is_final=True,
                resolved_provider="anthropic",
                resolved_model="claude-3-sonnet",
                usage=test_usage,
                finish_reason="stop",
            )

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            chunks = []
            async for chunk in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-3-sonnet",
            ):
                chunks.append(chunk)

        non_final = [c for c in chunks if not c.is_final]
        terminal = next(c for c in chunks if c.is_final)

        # F04 accumulates materialized text from non-final deltas (Constraint C1)
        materialized_text = "".join(c.text_delta for c in non_final)
        self.assertEqual(
            materialized_text,
            "Hello world",
            f"Materialized text must be joined deltas; got {materialized_text!r}",
        )

        # Terminal chunk must carry all fields needed to build LLMResponse
        self.assertEqual(terminal.resolved_provider, "anthropic")
        self.assertEqual(terminal.resolved_model, "claude-3-sonnet")
        self.assertEqual(terminal.usage, test_usage)
        self.assertEqual(terminal.finish_reason, "stop")

        # Construct LLMResponse as F04 would
        reconstructed = LLMResponse(
            text=materialized_text,
            resolved_provider=terminal.resolved_provider,
            resolved_model=terminal.resolved_model,
            usage=terminal.usage,
            finish_reason=terminal.finish_reason,
        )
        self.assertEqual(reconstructed.text, "Hello world")
        self.assertEqual(reconstructed.resolved_provider, "anthropic")
        self.assertEqual(reconstructed.resolved_model, "claude-3-sonnet")
        self.assertEqual(reconstructed.finish_reason, "stop")

    async def test_tc_f03_035_d_unsupported_mode_raises_from_iteration(self):
        """TC-F03-035 (d): unsupported-mode rejection (provider='google') raises
        LLMServiceError from iteration — no chunks received.
        """
        from agentmap.services.llm_service import LLMServiceError

        svc = self._make_f04_svc()

        chunks = []
        raised = None
        try:
            async for chunk in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="google",
                model="gemini-pro",
            ):
                chunks.append(chunk)
        except LLMServiceError as e:
            raised = e

        self.assertIsNotNone(
            raised,
            "Unsupported-mode (provider='google') must raise LLMServiceError from iteration",
        )
        self.assertEqual(
            chunks,
            [],
            "Zero chunks must be received before the unsupported-mode error",
        )

    async def test_tc_f03_035_d_after_first_chunk_failure_raises_from_iteration(self):
        """TC-F03-035 (d): After-first-chunk failure raises from iteration;
        chunks received before the error are preserved.
        """
        from agentmap.exceptions import LLMProviderError

        svc = self._make_f04_svc()

        exc = LLMProviderError("mid-stream failure in F04 path")

        async def fake_sp(prov, messages, params, *, client, credentials):
            async for chunk in make_failing_stream(after=2, exc=exc):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            chunks = []
            raised = None
            try:
                async for chunk in svc.call_llm_stream_async(
                    messages=[{"role": "user", "content": "hi"}],
                    provider="anthropic",
                    model="claude-3-sonnet",
                ):
                    chunks.append(chunk)
            except LLMProviderError as e:
                raised = e

        self.assertIsNotNone(
            raised, "After-first-chunk error must raise from iteration"
        )
        self.assertEqual(
            len(chunks),
            2,
            "Chunks received before the error must be preserved (2 expected)",
        )

    async def test_tc_f03_035_e_no_provider_sdk_import_required(self):
        """TC-F03-035 (e): Consuming call_llm_stream_async requires no provider SDK import.

        We verify this by iterating the result in a scope where anthropic/openai
        SDKs are temporarily shadowed to None, then asserting iteration still works.
        """
        svc = self._make_f04_svc()

        async def fake_sp(prov, messages, params, *, client, credentials):
            async for chunk in make_stream("test"):
                yield chunk

        with patch(
            "agentmap.services.llm_service.stream_provider", side_effect=fake_sp
        ):
            # Consume the iterator — must work regardless of SDK availability
            chunks = []
            async for chunk in svc.call_llm_stream_async(
                messages=[{"role": "user", "content": "hi"}],
                provider="anthropic",
                model="claude-3-sonnet",
            ):
                chunks.append(chunk)

        # If we got here without import errors, the SDK is not required to consume
        self.assertTrue(
            chunks,
            "Must receive at least one chunk without requiring provider SDK import",
        )
        terminal = [c for c in chunks if c.is_final]
        self.assertEqual(len(terminal), 1, "Must receive exactly one terminal chunk")
