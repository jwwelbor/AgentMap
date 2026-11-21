import errno
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from agentmap.models.llm_attempt import LLMAttemptDescription, LLMAttemptOutcome
from agentmap.models.llm_execution import LLMUsage
from agentmap.services.llm_attempt_file_logger import LLMAttemptFileLogger


@pytest.mark.asyncio
async def test_writes_one_json_record_per_attempt_to_utc_day_file(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    attempt_id = await logger.before_attempt(
        LLMAttemptDescription("openai", "gpt-test", "retry", 2, None, None, None)
    )

    await logger.after_attempt(
        attempt_id,
        LLMAttemptOutcome(
            classification="text",
            usage=LLMUsage(input_tokens=12, output_tokens=4),
        ),
    )

    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    record = json.loads(files[0].read_text().strip())
    request_datetime = datetime.fromisoformat(record["request_datetime"])
    assert files[0].name == f"llm-calls-{request_datetime:%Y-%m-%d}.jsonl"
    assert record["provider"] == "openai"
    assert record["input_tokens"] == 12
    assert record["output_tokens"] == 4
    assert record["cost_usd"] is None
    assert record["was_success"] is True
    assert record["request_datetime"]
    assert record["response_datetime"]
    assert record["error_message"] is None


@pytest.mark.asyncio
async def test_failed_attempt_keeps_missing_response_and_usage_unset(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    attempt_id = await logger.before_attempt(
        LLMAttemptDescription(
            "anthropic", "claude-test", "primary", 1, None, None, None
        )
    )

    await logger.after_attempt(
        attempt_id,
        LLMAttemptOutcome(
            classification="provider_error",
            error_type="ProviderError",
        ),
    )

    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text().strip())
    assert record["response_datetime"] is None
    assert record["input_tokens"] is None
    assert record["output_tokens"] is None
    assert record["was_success"] is False
    assert record["error_message"] == "Provider attempt failed (ProviderError)"


@pytest.mark.asyncio
async def test_does_not_include_raw_exception_text(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    attempt_id = await logger.before_attempt(
        LLMAttemptDescription("openai", "gpt-test", "primary", 1, None, None, None)
    )

    await logger.after_attempt(
        attempt_id,
        LLMAttemptOutcome(
            classification="provider_error",
            error_type="ProviderError",
        ),
    )

    content = next(tmp_path.glob("*.jsonl")).read_text()
    assert "secret token" not in content


@pytest.mark.asyncio
async def test_records_configured_cost_amount_and_currency(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    attempt_id = await logger.before_attempt(
        LLMAttemptDescription("openai", "model", "primary", 1, None, None, None)
    )

    await logger.after_attempt(
        attempt_id,
        LLMAttemptOutcome(
            classification="text",
            cost_amount=Decimal("0.25"),
            cost_currency="CAD",
        ),
    )

    record = json.loads(next(tmp_path.glob("*.jsonl")).read_text())
    assert record["cost_usd"] is None
    assert record["cost_amount"] == "0.25"
    assert record["cost_currency"] == "CAD"


@pytest.mark.asyncio
async def test_records_each_retry_or_fallback_attempt_separately(tmp_path):
    logger = LLMAttemptFileLogger(tmp_path, Mock())
    attempt_ids = [
        await logger.before_attempt(
            LLMAttemptDescription(provider, "model", kind, ordinal, None, None, None)
        )
        for provider, kind, ordinal in (
            ("openai", "primary", 1),
            ("anthropic", "fallback", 1),
        )
    ]

    for attempt_id, classification in zip(attempt_ids, ("provider_error", "text")):
        await logger.after_attempt(
            attempt_id,
            LLMAttemptOutcome(classification=classification),
        )

    records = [
        json.loads(line)
        for line in next(tmp_path.glob("*.jsonl")).read_text().splitlines()
    ]
    assert len(records) == 2
    assert [record["provider"] for record in records] == ["openai", "anthropic"]
    assert [record["was_success"] for record in records] == [False, True]


def test_write_oserror_does_not_escape_provider_lifecycle(tmp_path):
    logging_service = Mock()
    logger = LLMAttemptFileLogger(tmp_path, logging_service)
    attempt_id = logger.before_attempt_sync(
        LLMAttemptDescription("openai", "model", "primary", 1, None, None, None)
    )
    logger._append_record = Mock(side_effect=OSError(errno.ENOSPC, "full"))

    logger.after_attempt_sync(attempt_id, LLMAttemptOutcome(classification="text"))

    logging_service.get_class_logger.return_value.warning.assert_called_once()
