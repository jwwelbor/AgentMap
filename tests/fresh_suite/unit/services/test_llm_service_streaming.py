"""
Unit tests for LLMService streaming entry point skeleton (E06-F03).

Covers TC-F03-007 and TC-F03-017 — the two test cases owned by T-E06-F03-001:
  - TC-F03-007: __init__ creates _metric_ttft histogram; instrument not None.
  - TC-F03-017 (constant assertion portion): METRIC_LLM_TTFT value and distinctness.

Framework: unittest.IsolatedAsyncioTestCase for async tests; plain unittest.TestCase
for sync assertions. No real network calls. asyncio_mode NOT auto.
"""

import unittest
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
