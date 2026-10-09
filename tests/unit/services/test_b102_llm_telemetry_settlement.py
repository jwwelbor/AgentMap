"""B102 telemetry failures do not replay a settled provider request."""

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock

import pytest

from tests.unit.services.test_llm_service_telemetry import (
    _make_llm_service,
    _make_mock_telemetry,
    _mock_successful_llm_call,
)


class SpanExitFailure:
    def __init__(self, failure):
        self.failure = failure

    def __enter__(self):
        return Mock()

    def __exit__(self, *args):
        raise self.failure


@pytest.mark.parametrize("failure_stage", ["content_capture", "span_exit"])
def test_sync_telemetry_failure_after_result_does_not_repeat_provider_call(
    failure_stage,
):
    """Telemetry failure after the provider returns must not bill twice."""
    mock_telemetry, mock_span = _make_mock_telemetry()

    @contextmanager
    def _exit_fails(*args, **kwargs):
        yield mock_span
        raise RuntimeError("span exit failed")

    if failure_stage == "span_exit":
        mock_telemetry.start_span.side_effect = _exit_fails
    service = _make_llm_service(telemetry_service=mock_telemetry)
    _, mock_client = _mock_successful_llm_call(service)
    if failure_stage == "content_capture":
        service._capture_llm_content = Mock(side_effect=RuntimeError("capture failed"))

    result = service.call_llm(
        messages=[{"role": "user", "content": "hello"}],
        provider="anthropic",
        model="claude-3-sonnet",
    )

    assert result == "Hello!"
    mock_client.invoke.assert_called_once()


@pytest.mark.parametrize("failure_stage", ["content_capture", "span_exit"])
def test_async_telemetry_failure_after_result_does_not_repeat_provider_call(
    failure_stage,
):
    """The async wrapper returns its settled response after telemetry fails."""
    mock_telemetry, mock_span = _make_mock_telemetry()

    @contextmanager
    def _exit_fails(*args, **kwargs):
        yield mock_span
        raise RuntimeError("span exit failed")

    if failure_stage == "span_exit":
        mock_telemetry.start_span.side_effect = _exit_fails
    service = _make_llm_service(telemetry_service=mock_telemetry)
    response, mock_client = _mock_successful_llm_call(service, "Hello async!")
    mock_client.ainvoke = AsyncMock(return_value=response)
    if failure_stage == "content_capture":
        service._capture_llm_content = Mock(side_effect=RuntimeError("capture failed"))

    result = asyncio.run(
        service.call_llm_async(
            messages=[{"role": "user", "content": "hello"}],
            provider="anthropic",
            model="claude-3-sonnet",
        )
    )

    assert result.text == "Hello async!"
    mock_client.ainvoke.assert_awaited_once()


def test_sync_span_exit_failure_does_not_replace_provider_failure():
    provider_error = RuntimeError("provider failed")
    span_error = RuntimeError("private span teardown detail")
    telemetry, _ = _make_mock_telemetry()
    telemetry.start_span.side_effect = lambda *args, **kwargs: SpanExitFailure(
        span_error
    )
    service = _make_llm_service(telemetry_service=telemetry)
    service._call_llm_core = Mock(side_effect=provider_error)
    service._record_llm_call_exception_safe = Mock()

    with pytest.raises(RuntimeError) as caught:
        service._call_llm_with_telemetry(
            [{"role": "user", "content": "hello"}],
            "anthropic",
            "claude-3-sonnet",
            None,
            None,
        )

    assert caught.value is provider_error
    assert provider_error.__notes__ == [
        "LLM telemetry span exit failed with RuntimeError"
    ]
    service._call_llm_core.assert_called_once()


def test_async_span_exit_failure_does_not_replace_caller_cancellation():
    cancellation = asyncio.CancelledError("caller cancelled")
    span_error = RuntimeError("private span teardown detail")
    telemetry, _ = _make_mock_telemetry()
    telemetry.start_span.side_effect = lambda *args, **kwargs: SpanExitFailure(
        span_error
    )
    service = _make_llm_service(telemetry_service=telemetry)
    service._call_llm_async_core = AsyncMock(side_effect=cancellation)
    service._record_llm_call_exception_safe = Mock()

    with pytest.raises(asyncio.CancelledError) as caught:
        asyncio.run(
            service._call_llm_async_with_telemetry(
                [{"role": "user", "content": "hello"}],
                "anthropic",
                "claude-3-sonnet",
                None,
                None,
            )
        )

    assert caught.value is cancellation
    assert cancellation.__notes__ == [
        "LLM telemetry span exit failed with RuntimeError"
    ]
    service._call_llm_async_core.assert_awaited_once()
