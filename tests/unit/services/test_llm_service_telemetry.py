"""
Tests for LLMService telemetry instrumentation.

Covers task T-E02-F03-002: LLMService GenAI Semantic Convention Span Instrumentation.
Test cases TC-220 through TC-225, TC-251, TC-261-262, TC-270-275.
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, create_autospec, patch

import pytest

from agentmap.services.llm_service import LLMService
from agentmap.services.telemetry.constants import (
    GEN_AI_PROMPT_CONTENT,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_CONTENT,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    LLM_CALL_SPAN,
)
from agentmap.services.telemetry.protocol import TelemetryServiceProtocol

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_mock_telemetry():
    """Create a mock telemetry service with working context-manager span."""
    svc = create_autospec(TelemetryServiceProtocol, instance=True)
    mock_span = MagicMock()

    @contextmanager
    def _ctx_mgr(*args, **kwargs):
        yield mock_span

    svc.start_span.side_effect = _ctx_mgr
    return svc, mock_span


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
        # No usage_metadata attribute
        del mock_response.usage_metadata

    mock_response.response_metadata = {}

    mock_client = MagicMock()
    mock_client.invoke.return_value = mock_response

    # Replace internal components with mocks
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
# TC-220: gen_ai.chat span created
# ====================================================================


class TestTC220SpanCreation:
    """TC-220: call_llm() creates gen_ai.chat span."""

    def test_call_llm_creates_gen_ai_chat_span(self):
        """start_span called with LLM_CALL_SPAN when telemetry is present."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        mock_telemetry.start_span.assert_called_once()
        call_args = mock_telemetry.start_span.call_args
        assert call_args[0][0] == LLM_CALL_SPAN


# ====================================================================
# TC-221: GenAI semconv attributes present
# ====================================================================


class TestTC221GenAIAttributes:
    """TC-221: GenAI semantic convention attributes set on span."""

    def test_gen_ai_system_attribute(self):
        """GEN_AI_SYSTEM attribute set to normalized provider."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        # Check initial attributes passed to start_span
        call_args = mock_telemetry.start_span.call_args
        attrs = call_args[1].get(
            "attributes", call_args[0][1] if len(call_args[0]) > 1 else {}
        )
        assert GEN_AI_SYSTEM in attrs
        assert attrs[GEN_AI_SYSTEM] == "anthropic"

    def test_gen_ai_request_model_attribute(self):
        """GEN_AI_REQUEST_MODEL attribute set to requested model."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        call_args = mock_telemetry.start_span.call_args
        attrs = call_args[1].get(
            "attributes", call_args[0][1] if len(call_args[0]) > 1 else {}
        )
        assert GEN_AI_REQUEST_MODEL in attrs
        assert attrs[GEN_AI_REQUEST_MODEL] == "claude-3-sonnet"


# ====================================================================
# TC-222: Token counts extracted
# ====================================================================


class TestTC222TokenCounts:
    """TC-222: Token counts recorded when available."""

    @patch("agentmap.services.llm_service.LLMService._record_llm_response_attributes")
    def test_token_counts_from_dict_usage_metadata(self, mock_record):
        """Token counts extracted from dict-style usage_metadata."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        mock_response, _ = _mock_successful_llm_call(
            svc,
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 50,
            },
        )

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        # Verify _record_llm_response_attributes was called with the response
        mock_record.assert_called_once()
        call_args = mock_record.call_args
        assert call_args[0][0] is mock_response
        assert call_args[0][1] == "anthropic"

    @patch("agentmap.services.llm_service.LLMService._record_llm_response_attributes")
    def test_token_counts_from_dataclass_usage_metadata(self, mock_record):
        """Token counts extracted from dataclass-style usage_metadata."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)

        # Create a dataclass-like usage_metadata
        usage = MagicMock()
        usage.input_tokens = 200
        usage.output_tokens = 75

        mock_response, _ = _mock_successful_llm_call(svc)
        mock_response.usage_metadata = usage

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        mock_record.assert_called_once()
        call_args = mock_record.call_args
        assert call_args[0][0] is mock_response


class TestTokenCountExtraction:
    """Test _record_llm_response_attributes directly for token extraction."""

    @patch("opentelemetry.trace.get_current_span")
    def test_dict_usage_metadata_sets_token_attrs(self, mock_get_span):
        """Dict usage_metadata tokens set on span."""
        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True
        mock_get_span.return_value = mock_current_span

        mock_telemetry, _ = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)

        mock_response = MagicMock()
        mock_response.usage_metadata = {
            "input_tokens": 100,
            "output_tokens": 50,
        }
        mock_response.response_metadata = {}

        svc._record_llm_response_attributes(mock_response, "anthropic")

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_USAGE_INPUT_TOKENS in all_attrs
        assert all_attrs[GEN_AI_USAGE_INPUT_TOKENS] == 100
        assert GEN_AI_USAGE_OUTPUT_TOKENS in all_attrs
        assert all_attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 50

    @patch("opentelemetry.trace.get_current_span")
    def test_dataclass_usage_metadata_sets_token_attrs(self, mock_get_span):
        """Dataclass-like usage_metadata tokens set on span."""
        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True
        mock_get_span.return_value = mock_current_span

        mock_telemetry, _ = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)

        usage = MagicMock(spec=[])  # No dict interface
        usage.input_tokens = 200
        usage.output_tokens = 75

        mock_response = MagicMock()
        mock_response.usage_metadata = usage
        mock_response.response_metadata = {}

        svc._record_llm_response_attributes(mock_response, "anthropic")

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_USAGE_INPUT_TOKENS in all_attrs
        assert all_attrs[GEN_AI_USAGE_INPUT_TOKENS] == 200
        assert GEN_AI_USAGE_OUTPUT_TOKENS in all_attrs
        assert all_attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 75


# ====================================================================
# TC-223: Token counts omitted when not available
# ====================================================================


class TestTC223TokenCountsOmitted:
    """TC-223: Token counts omitted when not available."""

    def test_no_token_attrs_without_usage_metadata(self):
        """No token count attributes when response has no usage_metadata."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc, usage_metadata=None)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )

        # Collect all attributes set
        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_USAGE_INPUT_TOKENS not in all_attrs
        assert GEN_AI_USAGE_OUTPUT_TOKENS not in all_attrs


# ====================================================================
# TC-224: Error status on LLM failure  (TC-223 in test plan for error)
# ====================================================================


class TestTC224ErrorStatus:
    """TC-224: Span status ERROR on LLM call failure."""

    def test_span_error_on_llm_exception(self):
        """record_exception called when LLM call raises."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)

        # Set up mocks then make the client raise
        _mock_successful_llm_call(svc)
        mock_client = MagicMock()
        mock_client.invoke.side_effect = RuntimeError("API error")
        svc._client_factory.get_or_create_client.return_value = mock_client

        with pytest.raises(Exception):
            svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )

        # record_exception should have been called on the span
        mock_telemetry.record_exception.assert_called_once()


# ====================================================================
# TC-225: Constants used (not hardcoded strings)
# ====================================================================


class TestTC225ConstantsUsed:
    """TC-225: All attribute keys use constants from constants.py."""

    def test_span_name_uses_constant(self):
        """Span name matches LLM_CALL_SPAN constant value."""
        assert LLM_CALL_SPAN == "gen_ai.chat"

        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        call_args = mock_telemetry.start_span.call_args
        assert call_args[0][0] == LLM_CALL_SPAN


# ====================================================================
# TC-251: LLMService works with None telemetry
# ====================================================================


class TestTC251NoneTelemetry:
    """TC-251: LLMService works correctly with telemetry_service=None."""

    def test_call_llm_works_without_telemetry(self):
        """call_llm() completes normally when telemetry_service is None."""
        svc = _make_llm_service(telemetry_service=None)
        _mock_successful_llm_call(svc)

        result = svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        assert result == "Hello!"

    def test_no_telemetry_calls_when_none(self):
        """No telemetry methods called when telemetry_service is None."""
        svc = _make_llm_service(telemetry_service=None)
        _mock_successful_llm_call(svc)

        result = svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        # Verify no telemetry interaction
        assert svc._telemetry_service is None
        assert result == "Hello!"


# ====================================================================
# TC-261: start_span() failure -- LLM call continues
# ====================================================================


class TestTC261TelemetryFailureIsolation:
    """TC-261: LLM call completes despite telemetry start_span failure."""

    def test_llm_call_succeeds_when_start_span_raises(self):
        """LLM call returns correct result when start_span raises."""
        mock_telemetry = create_autospec(TelemetryServiceProtocol, instance=True)
        mock_telemetry.start_span.side_effect = RuntimeError("telemetry broken")

        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        result = svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        assert result == "Hello!"

    def test_warning_logged_on_telemetry_failure(self):
        """Warning logged when telemetry fails."""
        mock_telemetry = create_autospec(TelemetryServiceProtocol, instance=True)
        mock_telemetry.start_span.side_effect = RuntimeError("telemetry broken")

        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        # Logger should have been called with a warning
        svc._logger.warning.assert_called()


# ====================================================================
# TC-262: set_span_attributes() failure -- execution continues
# ====================================================================


class TestTC262AttributeFailureIsolation:
    """TC-262: Execution continues when set_span_attributes raises."""

    def test_call_succeeds_when_set_attributes_raises(self):
        """LLM call returns correctly when attribute setting raises."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        mock_telemetry.set_span_attributes.side_effect = RuntimeError("attrs broken")

        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        result = svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        assert result == "Hello!"


# ====================================================================
# TC-270: Content capture disabled by default
# ====================================================================


class TestTC270ContentCaptureDisabledDefault:
    """TC-270: Prompt content not captured by default."""

    def test_no_prompt_content_by_default(self):
        """No GEN_AI_PROMPT_CONTENT in attributes with default config."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_PROMPT_CONTENT not in all_attrs


# ====================================================================
# TC-271: Response capture disabled by default
# ====================================================================


class TestTC271ResponseCaptureDisabledDefault:
    """TC-271: Response content not captured by default."""

    def test_no_response_content_by_default(self):
        """No GEN_AI_RESPONSE_CONTENT in attributes with default config."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_RESPONSE_CONTENT not in all_attrs


# ====================================================================
# TC-272: Prompt captured when flag is true
# ====================================================================


class TestTC272PromptCapture:
    """TC-272: Prompt text captured when flag enabled."""

    def test_prompt_captured_when_enabled(self):
        """Prompt content present in span attributes when flag is True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        svc._capture_llm_prompts = True
        _mock_successful_llm_call(svc)

        svc.call_llm(
            messages=[{"role": "user", "content": "What is AI?"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_PROMPT_CONTENT in all_attrs


# ====================================================================
# TC-273: Response captured when flag is true
# ====================================================================


class TestTC273ResponseCapture:
    """TC-273: Response text captured when flag enabled."""

    def test_response_captured_when_enabled(self):
        """Response content present in span attributes when flag is True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        svc._capture_llm_responses = True
        _mock_successful_llm_call(svc, response_content="AI is cool")

        svc.call_llm(
            messages=[{"role": "user", "content": "What is AI?"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_RESPONSE_CONTENT in all_attrs
        assert all_attrs[GEN_AI_RESPONSE_CONTENT] == "AI is cool"


# ====================================================================
# TC-274: Content values truncated to size limit
# ====================================================================


class TestTC274ContentTruncation:
    """TC-274: Content truncated to 4096 chars."""

    def test_prompt_truncated_to_4096(self):
        """Prompt longer than 4096 chars is truncated."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        svc._capture_llm_prompts = True

        long_prompt = "x" * 5000
        _mock_successful_llm_call(svc)
        svc._message_utils.extract_prompt_from_messages.return_value = long_prompt

        svc.call_llm(
            messages=[{"role": "user", "content": long_prompt}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_PROMPT_CONTENT in all_attrs
        assert len(all_attrs[GEN_AI_PROMPT_CONTENT]) <= 4096

    def test_response_truncated_to_4096(self):
        """Response longer than 4096 chars is truncated."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        svc._capture_llm_responses = True

        long_response = "y" * 5000
        _mock_successful_llm_call(svc, response_content=long_response)

        svc.call_llm(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_RESPONSE_CONTENT in all_attrs
        assert len(all_attrs[GEN_AI_RESPONSE_CONTENT]) <= 4096


# ====================================================================
# TC-275: Flags operate independently
# ====================================================================


class TestTC275IndependentFlags:
    """TC-275: Prompt and response capture flags operate independently."""

    def test_prompt_only_capture(self):
        """Only prompt captured when only prompt flag is True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        svc._capture_llm_prompts = True
        svc._capture_llm_responses = False
        _mock_successful_llm_call(svc, response_content="response text")

        svc.call_llm(
            messages=[{"role": "user", "content": "prompt text"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_PROMPT_CONTENT in all_attrs
        assert GEN_AI_RESPONSE_CONTENT not in all_attrs

    def test_response_only_capture(self):
        """Only response captured when only response flag is True."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        svc._capture_llm_prompts = False
        svc._capture_llm_responses = True
        _mock_successful_llm_call(svc, response_content="response text")

        svc.call_llm(
            messages=[{"role": "user", "content": "prompt text"}],
            provider="anthropic",
        )

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_PROMPT_CONTENT not in all_attrs
        assert GEN_AI_RESPONSE_CONTENT in all_attrs


# ====================================================================
# Span status OK on success
# ====================================================================


class TestSpanStatusOk:
    """Span status set to OK on successful LLM call."""

    def test_span_status_ok_on_success(self):
        """_set_span_status_ok called on successful call."""
        mock_telemetry, mock_span = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        _mock_successful_llm_call(svc)

        with patch.object(svc, "_set_span_status_ok") as mock_ok:
            svc.call_llm(
                messages=[{"role": "user", "content": "hello"}],
                provider="anthropic",
            )
            mock_ok.assert_called_once_with(mock_span)


# ====================================================================
# Constructor backward compatibility
# ====================================================================


class TestConstructorBackwardCompat:
    """Constructor works with and without telemetry_service parameter."""

    def test_constructor_without_telemetry_param(self):
        """LLMService can be constructed without telemetry_service."""
        svc = _make_llm_service()
        assert svc._telemetry_service is None

    def test_constructor_with_telemetry_param(self):
        """LLMService stores telemetry_service when provided."""
        mock_telemetry, _ = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)
        assert svc._telemetry_service is mock_telemetry


# ====================================================================
# Response model attribute
# ====================================================================


class TestResponseModel:
    """Response model recorded from response_metadata."""

    @patch("opentelemetry.trace.get_current_span")
    def test_response_model_from_metadata(self, mock_get_span):
        """GEN_AI_RESPONSE_MODEL set from response_metadata."""
        mock_current_span = MagicMock()
        mock_current_span.is_recording.return_value = True
        mock_get_span.return_value = mock_current_span

        mock_telemetry, _ = _make_mock_telemetry()
        svc = _make_llm_service(telemetry_service=mock_telemetry)

        mock_response = MagicMock()
        mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 5}
        mock_response.response_metadata = {"model_name": "claude-3-sonnet-20240229"}

        svc._record_llm_response_attributes(mock_response, "anthropic")

        all_attrs = {}
        for call in mock_telemetry.set_span_attributes.call_args_list:
            all_attrs.update(call[0][1])

        assert GEN_AI_RESPONSE_MODEL in all_attrs
        assert all_attrs[GEN_AI_RESPONSE_MODEL] == "claude-3-sonnet-20240229"
