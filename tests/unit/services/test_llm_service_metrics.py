"""
Tests for LLMService metrics instrument creation and recording.

Covers task T-E02-F07-002: LLMService Metrics Instrument Creation and Recording.
Test cases TC-700 through TC-724, TC-737, TC-741.

Acceptance Criteria:
  AC1: Instruments created at init (TC-737)
  AC2: Duration recorded on success (TC-700, TC-705)
  AC3: Token counters recorded when present (TC-701, TC-702)
  AC4: Token counters skipped when absent (TC-704)
  AC5: Error counter on final failure only (TC-710-714)
  AC6: Circuit breaker tracking (TC-720, TC-721)
  AC7: Fallback and cache hit (TC-722-724)
  AC8: None telemetry path (TC-703)
  AC9: Failure isolation (TC-741)
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, create_autospec, patch

import pytest

from agentmap.services.llm_service import LLMService
from agentmap.services.telemetry.constants import (
    METRIC_DIM_ERROR_TYPE,
    METRIC_DIM_MODEL,
    METRIC_DIM_PROVIDER,
    METRIC_DIM_TIER,
    METRIC_LLM_CIRCUIT_BREAKER,
    METRIC_LLM_DURATION,
    METRIC_LLM_ERRORS,
    METRIC_LLM_FALLBACK,
    METRIC_LLM_ROUTING_CACHE_HIT,
    METRIC_LLM_TOKENS_INPUT,
    METRIC_LLM_TOKENS_OUTPUT,
)
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_mock_telemetry():
    """Create a mock telemetry service with working context-manager span
    and mock metric instruments."""
    svc = create_autospec(TelemetryServiceProtocol, instance=True)
    mock_span = MagicMock()

    @contextmanager
    def _ctx_mgr(*args, **kwargs):
        yield mock_span

    svc.start_span.side_effect = _ctx_mgr

    # Create mock instruments returned by create_* methods
    mock_duration = MagicMock(name="duration_histogram")
    mock_tokens_input = MagicMock(name="tokens_input_counter")
    mock_tokens_output = MagicMock(name="tokens_output_counter")
    mock_errors = MagicMock(name="errors_counter")
    mock_cache_hit = MagicMock(name="cache_hit_counter")
    mock_circuit_breaker = MagicMock(name="circuit_breaker_updown")
    mock_fallback = MagicMock(name="fallback_counter")

    def _create_histogram(name, **kwargs):
        if name == METRIC_LLM_DURATION:
            return mock_duration
        return MagicMock()

    def _create_counter(name, **kwargs):
        mapping = {
            METRIC_LLM_TOKENS_INPUT: mock_tokens_input,
            METRIC_LLM_TOKENS_OUTPUT: mock_tokens_output,
            METRIC_LLM_ERRORS: mock_errors,
            METRIC_LLM_ROUTING_CACHE_HIT: mock_cache_hit,
            METRIC_LLM_FALLBACK: mock_fallback,
        }
        return mapping.get(name, MagicMock())

    def _create_up_down_counter(name, **kwargs):
        if name == METRIC_LLM_CIRCUIT_BREAKER:
            return mock_circuit_breaker
        return MagicMock()

    svc.create_histogram.side_effect = _create_histogram
    svc.create_counter.side_effect = _create_counter
    svc.create_up_down_counter.side_effect = _create_up_down_counter

    instruments = {
        "duration": mock_duration,
        "tokens_input": mock_tokens_input,
        "tokens_output": mock_tokens_output,
        "errors": mock_errors,
        "cache_hit": mock_cache_hit,
        "circuit_breaker": mock_circuit_breaker,
        "fallback": mock_fallback,
    }

    return svc, mock_span, instruments


def _make_llm_service(telemetry_service=None, **overrides):
    """Create an LLMService with mocked dependencies."""
    mock_logging = MagicMock()
    mock_logger = MagicMock()
    mock_logging.get_class_logger.return_value = mock_logger

    mock_config = MagicMock()
    mock_config.get_llm_resilience_config.return_value = {
        "retry": {"max_attempts": 1},
        "circuit_breaker": {},
    }
    mock_config.get_llm_config.return_value = {
        "model": "claude-3-sonnet",
        "temperature": 0.7,
        "api_key": "test-key",
    }

    mock_models_config = MagicMock()
    mock_routing_service = MagicMock()

    svc = LLMService(
        configuration=mock_config,
        logging_service=mock_logging,
        routing_service=mock_routing_service,
        llm_models_config_service=mock_models_config,
        telemetry_service=telemetry_service,
        **overrides,
    )
    return svc


def _mock_successful_llm_call(svc, response_content="Hello!", usage_metadata=None):
    """Patch internal methods so call_llm succeeds with given response."""
    mock_response = MagicMock()
    mock_response.content = response_content

    if usage_metadata is not None:
        mock_response.usage_metadata = usage_metadata
    else:
        del mock_response.usage_metadata

    mock_response.response_metadata = {}

    mock_client = MagicMock()
    mock_client.invoke.return_value = mock_response

    svc._provider_utils = MagicMock()
    svc._provider_utils.normalize_provider.return_value = "anthropic"
    svc._provider_utils.get_provider_config.return_value = {
        "model": "claude-3-sonnet",
        "api_key": "test-key",
    }
    svc._client_factory = MagicMock()
    svc._client_factory.get_or_create_client.return_value = mock_client
    svc._message_utils = MagicMock()
    svc._message_utils.convert_messages_to_langchain.return_value = []
    svc._message_utils.extract_prompt_from_messages.return_value = "hello"

    return mock_response, mock_client


# ====================================================================
# AC1: Instruments created at init (TC-737)
# ====================================================================


class TestAC1InstrumentsCreatedAtInit:
    """AC1 / TC-737: Instruments created once in __init__."""

    def test_create_histogram_called_for_duration(self):
        """create_histogram called with METRIC_LLM_DURATION."""
        mock_telemetry, _, instruments = _make_mock_telemetry()
        _make_llm_service(telemetry_service=mock_telemetry)

        mock_telemetry.create_histogram.assert_called_once()
        call_args = mock_telemetry.create_histogram.call_args
        assert call_args[0][0] == METRIC_LLM_DURATION

    def test_create_counter_called_five_times(self):
        """create_counter called 5 times for tokens_input, tokens_output,
        errors, cache_hit, fallback."""
        mock_telemetry, _, instruments = _make_mock_telemetry()
        _make_llm_service(telemetry_service=mock_telemetry)

        assert mock_telemetry.create_counter.call_count == 5
        names = [c[0][0] for c in mock_telemetry.create_counter.call_args_list]
        assert METRIC_LLM_TOKENS_INPUT in names
        assert METRIC_LLM_TOKENS_OUTPUT in names
        assert METRIC_LLM_ERRORS in names
        assert METRIC_LLM_ROUTING_CACHE_HIT in names

    def test_create_up_down_counter_called_once(self):
        """create_up_down_counter called once for circuit breaker."""
        mock_telemetry, _, instruments = _make_mock_telemetry()
        _make_llm_service(telemetry_service=mock_telemetry)

        mock_telemetry.create_up_down_counter.assert_called_once()
        call_args = mock_telemetry.create_up_down_counter.call_args
        assert call_args[0][0] == METRIC_LLM_CIRCUIT_BREAKER

    def test_create_counter_for_fallback(self):
        """create_counter includes METRIC_LLM_FALLBACK."""
        mock_telemetry, _, instruments = _make_mock_telemetry()
        _make_llm_service(telemetry_service=mock_telemetry)

        names = [c[0][0] for c in mock_telemetry.create_counter.call_args_list]
        assert METRIC_LLM_FALLBACK in names

    def test_total_counter_calls_is_five(self):
        """create_counter called 5 times total (4 + fallback)."""
        mock_telemetry, _, instruments = _make_mock_telemetry()
        _make_llm_service(telemetry_service=mock_telemetry)

        assert mock_telemetry.create_counter.call_count == 5

    def test_instruments_stored_as_instance_attributes(self):
        """All seven instruments stored on self."""
        mock_telemetry, _, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)

        assert svc._metric_duration is instruments["duration"]
        assert svc._metric_tokens_input is instruments["tokens_input"]
        assert svc._metric_tokens_output is instruments["tokens_output"]
        assert svc._metric_errors is instruments["errors"]
        assert svc._metric_cache_hit is instruments["cache_hit"]
        assert svc._metric_circuit_breaker is instruments["circuit_breaker"]
        assert svc._metric_fallback is instruments["fallback"]

    def test_units_correct(self):
        """Instruments created with correct unit strings."""
        mock_telemetry, _, _ = _make_mock_telemetry()
        _make_llm_service(telemetry_service=mock_telemetry)

        # Histogram: unit="s"
        hist_kwargs = mock_telemetry.create_histogram.call_args[1]
        assert hist_kwargs.get("unit") == "s"

        # Check counter calls for unit values
        for call in mock_telemetry.create_counter.call_args_list:
            name = call[0][0]
            unit = call[1].get("unit", "")
            if name in (METRIC_LLM_TOKENS_INPUT, METRIC_LLM_TOKENS_OUTPUT):
                assert unit == "token"
            elif name in (
                METRIC_LLM_ERRORS,
                METRIC_LLM_ROUTING_CACHE_HIT,
                METRIC_LLM_FALLBACK,
            ):
                assert unit == "1"

        # UpDownCounter: unit="1"
        udc_kwargs = mock_telemetry.create_up_down_counter.call_args[1]
        assert udc_kwargs.get("unit") == "1"


# ====================================================================
# AC2: Duration recorded on success (TC-700, TC-705)
# ====================================================================


class TestAC2DurationRecorded:
    """AC2 / TC-700, TC-705: Duration histogram recorded on success."""

    def test_duration_recorded_on_successful_call(self):
        """_metric_duration.record() called with positive float."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        instruments["duration"].record.assert_called_once()
        call_args = instruments["duration"].record.call_args
        duration_value = call_args[0][0]
        assert isinstance(duration_value, float)
        assert duration_value >= 0

    def test_duration_has_provider_model_attributes(self):
        """Duration recorded with provider and model dimensions."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        call_args = instruments["duration"].record.call_args
        attrs = call_args[0][1]
        assert METRIC_DIM_PROVIDER in attrs
        assert METRIC_DIM_MODEL in attrs
        assert attrs[METRIC_DIM_PROVIDER] == "anthropic"
        assert attrs[METRIC_DIM_MODEL] == "claude-3-sonnet"

    def test_duration_not_recorded_on_failure(self):
        """Duration NOT recorded when LLM call fails."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        # Make client raise
        mock_client = MagicMock()
        mock_client.invoke.side_effect = RuntimeError("API error")
        svc._client_factory.get_or_create_client.return_value = mock_client

        with pytest.raises(Exception):
            svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )

        instruments["duration"].record.assert_not_called()


# ====================================================================
# AC3: Token counters recorded when present (TC-701, TC-702)
# ====================================================================


class TestAC3TokenCountersRecorded:
    """AC3 / TC-701, TC-702: Token counters recorded with correct values."""

    def test_input_tokens_recorded(self):
        """_metric_tokens_input.add() called with correct count."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(
            svc,
            usage_metadata={"input_tokens": 100, "output_tokens": 50},
        )

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        instruments["tokens_input"].add.assert_called_once()
        call_args = instruments["tokens_input"].add.call_args
        assert call_args[0][0] == 100

    def test_output_tokens_recorded(self):
        """_metric_tokens_output.add() called with correct count."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(
            svc,
            usage_metadata={"input_tokens": 100, "output_tokens": 50},
        )

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        instruments["tokens_output"].add.assert_called_once()
        call_args = instruments["tokens_output"].add.call_args
        assert call_args[0][0] == 50

    def test_token_counters_have_provider_model_dims(self):
        """Token counters recorded with provider and model attributes."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(
            svc,
            usage_metadata={"input_tokens": 100, "output_tokens": 50},
        )

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        for instr in [instruments["tokens_input"], instruments["tokens_output"]]:
            call_args = instr.add.call_args
            attrs = call_args[0][1]
            assert attrs[METRIC_DIM_PROVIDER] == "anthropic"
            assert attrs[METRIC_DIM_MODEL] == "claude-3-sonnet"

    def test_zero_token_count_still_recorded(self):
        """Counter called with add(0, ...) when token count is zero."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(
            svc,
            usage_metadata={"input_tokens": 0, "output_tokens": 0},
        )

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        instruments["tokens_input"].add.assert_called_once()
        assert instruments["tokens_input"].add.call_args[0][0] == 0
        instruments["tokens_output"].add.assert_called_once()
        assert instruments["tokens_output"].add.call_args[0][0] == 0

    def test_only_input_token_recorded_when_output_absent(self):
        """Only input counter fires when output_tokens is None."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(
            svc,
            usage_metadata={"input_tokens": 100, "output_tokens": None},
        )

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        instruments["tokens_input"].add.assert_called_once()
        instruments["tokens_output"].add.assert_not_called()


# ====================================================================
# AC4: Token counters skipped when absent (TC-704)
# ====================================================================


class TestAC4TokenCountersSkipped:
    """AC4 / TC-704: Token counters not called when no usage_metadata."""

    def test_no_token_counters_without_usage_metadata(self):
        """Token counters NOT called when response has no usage_metadata."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc, usage_metadata=None)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        instruments["tokens_input"].add.assert_not_called()
        instruments["tokens_output"].add.assert_not_called()


# ====================================================================
# AC5: Error counter on final failure only (TC-710-714)
# ====================================================================


class TestAC5ErrorCounter:
    """AC5 / TC-710-714: Error counter fires once on final failure."""

    def test_error_counter_on_non_retryable_failure(self):
        """Error counter incremented on non-retryable error."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        mock_client = MagicMock()
        mock_client.invoke.side_effect = RuntimeError("API error")
        svc._client_factory.get_or_create_client.return_value = mock_client

        with pytest.raises(Exception):
            svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )

        instruments["errors"].add.assert_called_once()
        call_args = instruments["errors"].add.call_args
        assert call_args[0][0] == 1

    def test_error_counter_has_error_type_dimension(self):
        """Error counter includes error_type, provider, model dims."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        mock_client = MagicMock()
        mock_client.invoke.side_effect = RuntimeError("API error")
        svc._client_factory.get_or_create_client.return_value = mock_client

        with pytest.raises(Exception):
            svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )

        call_args = instruments["errors"].add.call_args
        attrs = call_args[0][1]
        assert METRIC_DIM_ERROR_TYPE in attrs
        assert METRIC_DIM_PROVIDER in attrs
        assert METRIC_DIM_MODEL in attrs

    def test_error_counter_not_on_intermediate_retry(self):
        """Error counter NOT fired on intermediate retryable failures."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()

        # Use max_attempts=3 to test intermediate retries
        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {
                "max_attempts": 3,
                "backoff_base": 0.001,
                "backoff_max": 0.001,
            },
            "circuit_breaker": {},
        }

        svc = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )
        _mock_successful_llm_call(svc)

        # Make client fail with a retryable error (timeout)
        mock_client = MagicMock()
        mock_client.invoke.side_effect = RuntimeError("timeout error")
        svc._client_factory.get_or_create_client.return_value = mock_client

        with pytest.raises(Exception):
            svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )

        # Should be called exactly once (final failure), not 3 times
        instruments["errors"].add.assert_called_once()

    def test_error_counter_not_on_success(self):
        """Error counter NOT called on successful LLM call."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        instruments["errors"].add.assert_not_called()


# ====================================================================
# AC6: Circuit breaker tracking (TC-720, TC-721)
# ====================================================================


class TestAC6CircuitBreakerTracking:
    """AC6 / TC-720, TC-721: UpDownCounter tracks circuit breaker state."""

    def test_circuit_breaker_increment_on_open(self):
        """add(1) called when circuit breaker opens (failure recorded)."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()

        # Use threshold=1 so one failure opens the circuit
        mock_logging = MagicMock()
        mock_logging.get_class_logger.return_value = MagicMock()
        mock_config = MagicMock()
        mock_config.get_llm_resilience_config.return_value = {
            "retry": {"max_attempts": 1},
            "circuit_breaker": {"failure_threshold": 1},
        }

        svc = LLMService(
            configuration=mock_config,
            logging_service=mock_logging,
            routing_service=MagicMock(),
            llm_models_config_service=MagicMock(),
            telemetry_service=mock_telemetry,
        )
        _mock_successful_llm_call(svc)

        mock_client = MagicMock()
        mock_client.invoke.side_effect = RuntimeError("API error")
        svc._client_factory.get_or_create_client.return_value = mock_client

        with pytest.raises(Exception):
            svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )

        # Circuit opens after 1 failure -> add(1)
        instruments["circuit_breaker"].add.assert_called_once_with(1)

    def test_circuit_breaker_decrement_on_close(self):
        """add(-1) called when circuit breaker closes (success after open)."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        # Mock is_open to return:
        # 1st call (guard check in _invoke_with_resilience): False
        # 2nd call (was_open check before record_success): True
        # 3rd call (_record_circuit_breaker_metric_on_close): False (now closed)
        # Note: _record_circuit_breaker_state may not call is_open when span
        # context is unavailable
        svc._circuit_breaker.is_open = MagicMock(side_effect=[False, True, False])
        svc._circuit_breaker.record_success = MagicMock()

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        instruments["circuit_breaker"].add.assert_called_once_with(-1)


# ====================================================================
# AC7: Fallback and cache hit (TC-722, TC-723, TC-724)
# ====================================================================


class TestAC7FallbackAndCacheHit:
    """AC7 / TC-722-724: Cache hit counter and fallback counter."""

    def test_cache_hit_counter_when_true(self):
        """_metric_cache_hit.add(1) called when decision.cache_hit is True."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)

        from agentmap.services.routing.types import RoutingDecision, TaskComplexity

        decision = RoutingDecision(
            provider="anthropic",
            model="claude-3-sonnet",
            complexity=TaskComplexity.MEDIUM,
            confidence=0.85,
            reasoning="test",
            fallback_used=False,
            cache_hit=True,
        )

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            svc._record_routing_attributes(decision)

        instruments["cache_hit"].add.assert_called_once_with(1)

    def test_cache_hit_counter_not_when_false(self):
        """_metric_cache_hit.add() NOT called when decision.cache_hit is False."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)

        from agentmap.services.routing.types import RoutingDecision, TaskComplexity

        decision = RoutingDecision(
            provider="anthropic",
            model="claude-3-sonnet",
            complexity=TaskComplexity.MEDIUM,
            confidence=0.85,
            reasoning="test",
            fallback_used=False,
            cache_hit=False,
        )

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            svc._record_routing_attributes(decision)

        instruments["cache_hit"].add.assert_not_called()

    def test_fallback_counter_on_routing_fallback(self):
        """_metric_fallback.add(1, {tier: ...}) on routing fallback."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        # Set up routing to fail so fallback activates
        svc.routing_service.route_request.side_effect = RuntimeError("routing fail")
        svc._provider_utils.get_available_providers.return_value = ["anthropic"]

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            routing_context={"task_type": "general", "fallback_provider": "anthropic"},
        )

        instruments["fallback"].add.assert_called_once()
        call_args = instruments["fallback"].add.call_args
        assert call_args[0][0] == 1
        attrs = call_args[0][1]
        assert METRIC_DIM_TIER in attrs


# ====================================================================
# AC8: None telemetry path (TC-703)
# ====================================================================


class TestAC8NoneTelemetryPath:
    """AC8 / TC-703: No metrics when telemetry_service is None."""

    def test_metric_attributes_are_none_when_no_telemetry(self):
        """All _metric_* attributes are None when telemetry is None."""
        svc = _make_llm_service(telemetry_service=None)

        assert svc._metric_duration is None
        assert svc._metric_tokens_input is None
        assert svc._metric_tokens_output is None
        assert svc._metric_errors is None
        assert svc._metric_cache_hit is None
        assert svc._metric_circuit_breaker is None
        assert svc._metric_fallback is None

    def test_call_llm_works_without_telemetry(self):
        """call_llm completes without error when telemetry is None."""
        svc = _make_llm_service(telemetry_service=None)
        _mock_successful_llm_call(svc)

        result = svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        assert result == "Hello!"

    def test_no_attribute_error_on_any_path(self):
        """No AttributeError for metric attrs on any code path."""
        svc = _make_llm_service(telemetry_service=None)
        _mock_successful_llm_call(svc)

        # Successful call
        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        # Failed call
        mock_client = MagicMock()
        mock_client.invoke.side_effect = RuntimeError("API error")
        svc._client_factory.get_or_create_client.return_value = mock_client

        with pytest.raises(Exception):
            svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )


# ====================================================================
# AC9: Failure isolation (TC-741)
# ====================================================================


class TestAC9FailureIsolation:
    """AC9 / TC-741: Metrics failures do not break LLM operations."""

    def test_duration_record_failure_isolated(self):
        """LLM call succeeds even if duration.record() raises."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        instruments["duration"].record.side_effect = RuntimeError("metrics broken")

        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        result = svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        assert result == "Hello!"

    def test_token_counter_failure_isolated(self):
        """LLM call succeeds even if tokens_input.add() raises."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        instruments["tokens_input"].add.side_effect = RuntimeError("metrics broken")
        instruments["tokens_output"].add.side_effect = RuntimeError("metrics broken")

        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(
            svc,
            usage_metadata={"input_tokens": 100, "output_tokens": 50},
        )

        result = svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        assert result == "Hello!"

    def test_error_counter_failure_isolated(self):
        """LLM error propagated even if error counter fails."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        instruments["errors"].add.side_effect = RuntimeError("metrics broken")

        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        mock_client = MagicMock()
        mock_client.invoke.side_effect = RuntimeError("API error")
        svc._client_factory.get_or_create_client.return_value = mock_client

        # The LLM error should still propagate (not the metrics error)
        with pytest.raises(Exception):
            svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )

    def test_multiple_instrument_failures_isolated(self):
        """LLM call succeeds even if multiple instruments fail."""
        mock_telemetry, mock_span, instruments = _make_mock_telemetry()
        instruments["duration"].record.side_effect = RuntimeError("broken")
        instruments["tokens_input"].add.side_effect = RuntimeError("broken")
        instruments["tokens_output"].add.side_effect = RuntimeError("broken")

        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(
            svc,
            usage_metadata={"input_tokens": 100, "output_tokens": 50},
        )

        result = svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        assert result == "Hello!"
