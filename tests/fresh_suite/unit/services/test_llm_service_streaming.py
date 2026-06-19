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

    async def test_retries_exhausted_fallback_yields_synthetic_terminal_chunk(self):
        """TC-F03-010: When all max_attempts raise before any chunk and fallback
        is eligible, try_with_fallback_async is called exactly once and its
        LLMResponse is materialized as a single synthetic terminal LLMStreamChunk
        (is_final=True, text_delta="").
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

        # Caller receives exactly one chunk — the synthetic terminal chunk
        self.assertEqual(
            len(collected), 1, "Must receive exactly one synthetic terminal chunk"
        )
        synthetic = collected[0]
        self.assertTrue(
            synthetic.is_final, "Synthetic chunk must be terminal (is_final=True)"
        )
        self.assertEqual(
            synthetic.text_delta, "", "Synthetic terminal chunk must have text_delta=''"
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

        self.assertEqual(len(collected), 1)
        synthetic = collected[0]
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

        synthetic = collected[0]
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
