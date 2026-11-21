import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions import LLMConfigurationError, LLMProviderError
from agentmap.models.llm_attempt import LLMAttemptDescription, LLMAttemptOutcome
from agentmap.models.llm_execution import LLMResponse, LLMUsage
from agentmap.services.llm.attempt_lifecycle import file_attempt_logger
from agentmap.services.llm_attempt_file_logger import LLMAttemptFileLogger
from agentmap.services.llm_fallback_handler import LLMFallbackHandler
from agentmap.services.llm_service import LLMService


def _service_with_logger(logger):
    service = LLMService.__new__(LLMService)
    service._logger = Mock()
    service._cost_calculator = Mock(calculate=Mock(return_value=None))
    service._attempt_lifecycle = logger
    service._circuit_breaker = Mock()
    service._record_circuit_breaker_metric_on_close = Mock()
    service._record_duration_metric = Mock()
    service._record_llm_response_attributes = Mock()
    return service


def test_sync_provider_attempt_is_written_to_daily_log(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = _service_with_logger(logger)
    response = SimpleNamespace(
        content="ok",
        usage_metadata={"input_tokens": 7, "output_tokens": 3},
        response_metadata={},
    )

    result = service._complete_resilient_invocation(
        Mock(invoke=Mock(return_value=response)), [], "openai", "model", 1, 1
    )

    assert result == "ok"
    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text())
    assert record["provider"] == "openai"
    assert record["input_tokens"] == 7
    assert record["output_tokens"] == 3
    assert record["was_success"] is True
    assert record["response_datetime"] >= record["request_datetime"]


def test_sync_fallback_client_mode_is_defined_when_validation_fails(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = _service_with_logger(logger)
    service._provider_utils = Mock()
    service._provider_utils.normalize_provider.return_value = "openai"
    service._validate_prompt_caching_support = Mock(
        side_effect=LLMProviderError("prompt caching unsupported")
    )
    service._client_factory = Mock()
    service._message_utils = Mock()
    service._telemetry_service = None
    service._call_llm_core = lambda *args, **kwargs: service._call_llm_direct(
        *args, **kwargs
    )
    service.features_registry = object()
    service.routing_config = object()

    def fallback(*args, **_kwargs):
        args[5]("anthropic", {"api_key": "key"})
        return "fallback response"

    service._fallback_handler = Mock()
    service._fallback_handler.try_with_fallback.side_effect = fallback

    result = service.call_llm([{"role": "user", "content": "hello"}], provider="openai")

    assert result == "fallback response"
    service._client_factory.get_or_create_client.assert_called_once_with(
        "anthropic", {"api_key": "key"}, single_dispatch=True
    )


@pytest.mark.parametrize("fails", [False, True])
def test_sync_fallback_invocations_are_logged_via_resilience(tmp_path, fails):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = _service_with_logger(logger)
    service._resilience_config = {"retry": {"max_attempts": 1}}
    service._record_circuit_breaker_state = Mock()
    service._record_resilience_failure = Mock()
    service._circuit_breaker.is_open.return_value = False
    response = SimpleNamespace(
        content="fallback",
        usage_metadata={"input_tokens": 8, "output_tokens": 2},
        response_metadata={},
    )
    provider_client = Mock()
    if fails:
        provider_client.invoke.side_effect = LLMProviderError("fallback failed")
    else:
        provider_client.invoke.return_value = response
    fallback_handler = LLMFallbackHandler(
        Mock(), Mock(), Mock(), invoke_fn=service._invoke_with_resilience
    )

    if fails:
        with pytest.raises(LLMProviderError):
            fallback_handler._invoke_client(
                provider_client, [], "anthropic", "fallback-model"
            )
    else:
        assert (
            fallback_handler._invoke_client(
                provider_client, [], "anthropic", "fallback-model"
            )
            == "fallback"
        )

    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text())
    assert record["provider"] == "anthropic"
    assert record["was_success"] is not fails
    assert record["input_tokens"] == (None if fails else 8)


def test_sync_log_cost_diagnostic_does_not_fail_provider_success(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = _service_with_logger(logger)
    service._cost_calculator.calculate.side_effect = ValueError("invalid pricing")
    response = SimpleNamespace(
        content="ok",
        usage_metadata={"input_tokens": 7, "output_tokens": 3},
        response_metadata={},
    )

    result = service._complete_resilient_invocation(
        Mock(invoke=Mock(return_value=response)), [], "openai", "model", 1, 1
    )

    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text())
    assert result == "ok"
    assert record["was_success"] is True
    assert record["cost_usd"] is None
    service._logger.warning.assert_called_once()


def test_sync_log_does_not_label_non_usd_cost_as_usd(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = _service_with_logger(logger)
    service._cost_calculator.calculate.return_value = SimpleNamespace(
        currency="CAD", total_cost=Decimal("0.25")
    )
    response = SimpleNamespace(
        content="ok",
        usage_metadata={"input_tokens": 7, "output_tokens": 3},
        response_metadata={},
    )

    service._complete_resilient_invocation(
        Mock(invoke=Mock(return_value=response)), [], "openai", "model", 1, 1
    )

    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text())
    assert record["cost_usd"] is None
    assert record["was_success"] is True


def test_sync_anthropic_log_prices_disjoint_cache_token_buckets(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = _service_with_logger(logger)
    priced_usage = []

    def calculate(usage, _provider, _model):
        priced_usage.append(usage)
        return SimpleNamespace(currency="USD", total_cost=Decimal("0.00342"))

    service._cost_calculator.calculate.side_effect = calculate
    response = SimpleNamespace(
        content="ok",
        usage_metadata={
            "input_tokens": 1000,
            "output_tokens": 10,
            "cache_read_input_tokens": 900,
            "cache_creation_input_tokens": 0,
        },
        response_metadata={},
    )

    service._complete_resilient_invocation(
        Mock(invoke=Mock(return_value=response)), [], "anthropic", "model", 1, 1
    )

    assert priced_usage[0].input_tokens == 100
    assert priced_usage[0].cache_read_input_tokens == 900
    assert priced_usage[0].cache_creation_input_tokens == 0
    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text())
    assert record["cost_usd"] == "0.00342"


def test_sync_normalization_failure_settles_attempt_then_reraises(
    tmp_path, monkeypatch
):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = _service_with_logger(logger)
    service._cost_calculator.calculate.return_value = SimpleNamespace(
        currency="USD", total_cost=Decimal("0.42")
    )
    response = SimpleNamespace(
        usage_metadata={"input_tokens": 12, "output_tokens": 4},
        response_metadata={},
    )

    def fail_normalization(_response):
        raise ValueError("cannot normalize")

    monkeypatch.setattr(
        "agentmap.services.llm_service.normalize_response_content", fail_normalization
    )

    with pytest.raises(ValueError, match="cannot normalize"):
        service._complete_resilient_invocation(
            Mock(invoke=Mock(return_value=response)), [], "openai", "model", 1, 1
        )

    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text())
    assert record["was_success"] is False
    assert record["response_datetime"] is not None
    assert record["input_tokens"] == 12
    assert record["output_tokens"] == 4
    assert record["cost_usd"] == "0.42"
    assert record["error_message"] == "Provider attempt failed (ValueError)"


@pytest.mark.asyncio
async def test_async_production_entrypoint_uses_configured_attempt_logger(
    tmp_path, monkeypatch
):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = LLMService.__new__(LLMService)
    service._attempt_lifecycle = logger
    service._client_factory = Mock()
    service._dispatch_call_llm_async = Mock()

    async def invoke(*_args, **_kwargs):
        return "response"

    service._dispatch_call_llm_async = invoke
    observed = {}

    async def run_invocation(lifecycle, _client_factory, call):
        observed["lifecycle"] = lifecycle
        observed["file_logger"] = file_attempt_logger.get()
        return await call()

    monkeypatch.setattr(
        "agentmap.services.llm_service.run_governed_invocation", run_invocation
    )

    result = await service.call_llm_async([{"role": "user", "content": "hello"}])

    assert result == "response"
    assert observed["lifecycle"] is None
    assert observed["file_logger"] is logger


@pytest.mark.asyncio
async def test_async_file_logging_does_not_enable_governed_pricing_refusal(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = LLMService.__new__(LLMService)
    service._attempt_lifecycle = None
    service._client_factory = Mock()
    service._logger = Mock()
    service._cost_calculator = Mock()
    service._cost_calculator.calculate.side_effect = LLMConfigurationError(
        "malformed pricing"
    )
    service._build_success_llm_response = Mock(
        return_value=LLMResponse(
            text="ok",
            resolved_provider="openai",
            resolved_model="model",
            usage=LLMUsage(input_tokens=3, output_tokens=1),
            text_status="text",
        )
    )
    client = Mock()
    client.ainvoke = AsyncMock(
        return_value=SimpleNamespace(
            content="ok",
            usage_metadata={"input_tokens": 3, "output_tokens": 1},
            response_metadata={},
        )
    )
    token = file_attempt_logger.set(logger)
    try:
        result = await service._attempt_llm_call_async(
            client, [], "openai", "model", 1, retry_ordinal=1
        )
    finally:
        file_attempt_logger.reset(token)

    assert result.text == "ok"
    client.ainvoke.assert_awaited_once()
    service._client_factory.get_or_create_governed_client.assert_not_called()
    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text())
    assert record["was_success"] is True
    assert record["input_tokens"] == 3
    assert record["cost_usd"] is None


@pytest.mark.asyncio
async def test_per_call_lifecycle_is_composed_with_configured_logger(
    tmp_path, monkeypatch
):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    caller_lifecycle = Mock()
    caller_lifecycle.before_attempt = AsyncMock(return_value="caller-id")
    caller_lifecycle.after_attempt = AsyncMock()
    service = LLMService.__new__(LLMService)
    service._attempt_lifecycle = logger
    service._client_factory = Mock()
    service._dispatch_call_llm_async = Mock()
    observed = {}

    async def invoke(*_args, **_kwargs):
        return "response"

    async def run_invocation(lifecycle, _client_factory, call):
        observed["lifecycle"] = lifecycle
        attempt_id = await lifecycle.before_attempt(
            LLMAttemptDescription("openai", "model", "primary", 1, None, None, None)
        )
        await lifecycle.after_attempt(
            attempt_id, LLMAttemptOutcome(classification="text")
        )
        return await call()

    service._dispatch_call_llm_async = invoke
    monkeypatch.setattr(
        "agentmap.services.llm_service.run_governed_invocation", run_invocation
    )

    await service.call_llm_async(
        [{"role": "user", "content": "hello"}],
        attempt_lifecycle=caller_lifecycle,
    )

    caller_lifecycle.before_attempt.assert_awaited_once()
    caller_lifecycle.after_attempt.assert_awaited_once_with(
        "caller-id", LLMAttemptOutcome(classification="text")
    )
    assert len(list(tmp_path.glob("*.jsonl"))) == 1
