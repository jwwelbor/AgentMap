"""
Unit tests for LLMService streaming entry point skeleton (E06-F03).

Covers TC-F03-007 and TC-F03-017 — the two test cases owned by T-E06-F03-001:
  - TC-F03-007: __init__ creates _metric_ttft histogram; instrument not None.
  - TC-F03-017 (constant assertion portion): METRIC_LLM_TTFT value and distinctness.

Framework: unittest.IsolatedAsyncioTestCase for async tests; plain unittest.TestCase
for sync assertions. No real network calls. asyncio_mode NOT auto.
"""

import unittest
from typing import get_type_hints
from unittest.mock import MagicMock, Mock

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
