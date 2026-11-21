import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agentmap.services.llm_attempt_file_logger import LLMAttemptFileLogger
from agentmap.services.llm_service import LLMService


def _service_with_logger(logger):
    service = LLMService.__new__(LLMService)
    service._logger = Mock()
    service._attempt_lifecycle = logger
    service._circuit_breaker = Mock()
    service._record_circuit_breaker_metric_on_close = Mock()
    service._record_duration_metric = Mock()
    service._record_llm_response_attributes = Mock()
    return service


def test_sync_provider_attempt_is_written_to_daily_log(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path)
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


@pytest.mark.asyncio
async def test_async_production_entrypoint_uses_configured_attempt_logger(
    tmp_path, monkeypatch
):
    logger = LLMAttemptFileLogger(tmp_path)
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
        return await call()

    monkeypatch.setattr(
        "agentmap.services.llm_service.run_governed_invocation", run_invocation
    )

    result = await service.call_llm_async([{"role": "user", "content": "hello"}])

    assert result == "response"
    assert observed["lifecycle"] is logger
