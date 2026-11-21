import json
from types import SimpleNamespace
from unittest.mock import Mock

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
