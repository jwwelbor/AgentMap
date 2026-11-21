import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions import LLMProviderError
from agentmap.models.llm_execution import LLMResponse, LLMStreamChunk, LLMUsage
from agentmap.services.config.llm_routing_config_service import LLMRoutingConfigService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.llm_attempt_file_logger import LLMAttemptFileLogger
from agentmap.services.llm_fallback_handler import LLMFallbackHandler
from agentmap.services.llm_service import LLMService


def test_stream_fallback_preserves_sdk_retry_defaults_when_logging_disabled():
    service = LLMService.__new__(LLMService)
    service._attempt_lifecycle = None
    service._client_factory = Mock()
    config = {"model": "fallback-model"}

    service._get_stream_fallback_client("anthropic", config)

    service._client_factory.get_or_create_client.assert_called_once_with(
        "anthropic", config
    )


@pytest.mark.asyncio
async def test_stream_retry_logs_each_physical_attempt(tmp_path, monkeypatch):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = LLMService.__new__(LLMService)
    service._attempt_lifecycle = logger
    service._logger = Mock()
    service._circuit_breaker = Mock()
    service._circuit_breaker.is_open.return_value = False
    service._record_circuit_breaker_state = Mock()
    service._record_circuit_breaker_metric_on_close = Mock()
    service._record_error_metric = Mock()
    service._record_circuit_breaker_metric_on_open = Mock()
    service._resolve_retry_config = Mock(return_value=(2, 0, 0, False, 1))
    service._cost_calculator = Mock(calculate=Mock(return_value=None))
    calls = 0

    async def stream_provider(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise LLMProviderError("temporary provider failure")
        yield LLMStreamChunk(
            text_delta="done",
            chunk_index=0,
            is_final=False,
        )
        yield LLMStreamChunk(
            text_delta="",
            chunk_index=1,
            is_final=True,
            usage=LLMUsage(input_tokens=5, output_tokens=2),
        )

    monkeypatch.setattr(
        "agentmap.services.llm_service.stream_provider", stream_provider
    )
    monkeypatch.setattr(
        "agentmap.services.llm_service.is_retryable", lambda _error: True
    )

    chunks = [
        chunk
        async for chunk in service._invoke_with_resilience_stream_async(
            [], {}, "openai", "model", Mock(), None
        )
    ]

    records = [
        json.loads(line)
        for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()
    ]
    assert len(chunks) == 2
    assert len(records) == 2
    assert [record["was_success"] for record in records] == [False, True]
    assert records[0]["response_datetime"] is None
    assert records[1]["input_tokens"] == 5
    assert records[1]["output_tokens"] == 2


@pytest.mark.asyncio
async def test_closing_after_terminal_chunk_records_stream_success(
    tmp_path, monkeypatch
):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = LLMService.__new__(LLMService)
    service._attempt_lifecycle = logger
    service._logger = Mock()
    service._circuit_breaker = Mock()
    service._circuit_breaker.is_open.return_value = False
    service._record_circuit_breaker_state = Mock()
    service._record_circuit_breaker_metric_on_close = Mock()
    service._record_error_metric = Mock()
    service._record_circuit_breaker_metric_on_open = Mock()
    service._resolve_retry_config = Mock(return_value=(1, 0, 0, False, 1))
    service._cost_calculator = Mock(calculate=Mock(return_value=None))

    async def stream_provider(*_args, **_kwargs):
        yield LLMStreamChunk(
            text_delta="",
            chunk_index=0,
            is_final=True,
            usage=LLMUsage(input_tokens=4, output_tokens=1),
        )

    monkeypatch.setattr(
        "agentmap.services.llm_service.stream_provider", stream_provider
    )
    stream = service._invoke_with_resilience_stream_async(
        [], {}, "openai", "model", Mock(), None
    )

    terminal_chunk = await stream.__anext__()
    assert terminal_chunk.is_final is True
    await stream.aclose()

    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text())
    assert record["was_success"] is True
    assert record["input_tokens"] == 4
    assert record["output_tokens"] == 1
    assert record["response_datetime"] is not None


@pytest.mark.asyncio
async def test_stream_prechunk_fallback_logs_fallback_attempt(tmp_path, monkeypatch):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    service = LLMService.__new__(LLMService)
    service._attempt_lifecycle = logger
    service._provider_utils = Mock()
    service._provider_utils.normalize_provider.return_value = "openai"
    service._provider_utils.get_provider_config.side_effect = lambda provider: {
        "api_key": f"{provider}-key",
        "model": f"{provider}-model",
    }
    service._validate_streaming_support = Mock()
    service._message_utils = Mock()
    service._message_utils.inject_cache_metadata.side_effect = (
        lambda messages, *_: messages
    )
    service._message_utils.convert_messages_to_langchain.return_value = []
    service._client_factory = Mock()
    primary_client = Mock()
    fallback_client = Mock()
    fallback_client.ainvoke = AsyncMock(
        return_value=SimpleNamespace(
            content="fallback response",
            usage_metadata={"input_tokens": 6, "output_tokens": 2},
            response_metadata={},
        )
    )
    service._client_factory.get_or_create_client.side_effect = (
        lambda _provider, _config, **kwargs: (
            primary_client if kwargs.get("streaming") else fallback_client
        )
    )
    service.features_registry = Mock(spec=FeaturesRegistryService)
    service.features_registry.is_provider_available.return_value = True
    service.routing_config = SimpleNamespace(
        fallback={"default_provider": "anthropic"},
        routing_matrix={"anthropic": {"low": "fallback-model"}},
    )
    service._fallback_handler = LLMFallbackHandler(
        Mock(),
        service.routing_config,
        service.features_registry,
        invoke_fn=service._invoke_with_resilience,
        invoke_async_fn=lambda client, messages, fallback_provider, model, **limits: (
            service._invoke_with_resilience_async(
                client,
                messages,
                fallback_provider,
                model,
                attempt_kind="fallback",
                **limits,
            )
        ),
    )
    service._logger = Mock()
    service._circuit_breaker = Mock()
    service._circuit_breaker.is_open.return_value = False
    service._record_circuit_breaker_state = Mock()
    service._record_circuit_breaker_metric_on_close = Mock()
    service._record_circuit_breaker_metric_on_open = Mock()
    service._record_error_metric = Mock()
    service._resolve_retry_config = Mock(return_value=(1, 0, 0, False, 1))
    service._check_budget_before_dispatch = AsyncMock(return_value=None)
    service._cost_calculator = Mock(calculate=Mock(return_value=None))
    service._calculate_attempt_log_cost = Mock(return_value=None)
    service._build_success_llm_response = Mock(
        side_effect=lambda _raw, fallback_provider, model, _duration, **kwargs: LLMResponse(
            text="fallback response",
            resolved_provider=fallback_provider,
            resolved_model=model,
            usage=LLMUsage(input_tokens=6, output_tokens=2),
            text_status="text",
        )
    )

    async def fail_before_first_chunk(*_args, **_kwargs):
        raise LLMProviderError("primary failed")
        yield

    monkeypatch.setattr(
        "agentmap.services.llm_service.stream_provider", fail_before_first_chunk
    )

    chunks = [
        chunk
        async for chunk in service._call_llm_stream_async_direct(
            "openai",
            [{"role": "user", "content": "hello"}],
            eligible_providers=["anthropic"],
        )
    ]

    records = [
        json.loads(line)
        for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()
    ]
    assert [chunk.text_delta for chunk in chunks] == ["fallback response", ""]
    assert [record["provider"] for record in records] == ["openai", "anthropic"]
    assert [record["was_success"] for record in records] == [False, True]
    assert records[0]["response_datetime"] is None
    assert records[1]["input_tokens"] == 6
    assert records[1]["output_tokens"] == 2
    assert service._client_factory.get_or_create_client.call_args_list == [
        (
            ("openai", {"api_key": "openai-key", "model": "openai-model"}),
            {"streaming": True, "single_dispatch": True},
        ),
        (
            ("anthropic", {"api_key": "anthropic-key", "model": "fallback-model"}),
            {"single_dispatch": True},
        ),
    ]
