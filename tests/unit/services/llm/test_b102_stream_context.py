"""Nested streaming calls do not inherit governed attempt accounting."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agentmap.exceptions import (
    AttemptLifecycleRefusal,
    LLMConfigurationError,
    LLMProviderError,
)
from agentmap.models.llm_execution import LLMStreamChunk
from agentmap.services.llm.attempt_lifecycle import attempt_lifecycle
from agentmap.services.llm.invocation_lease import GovernedUseLease, governed_use_lease
from agentmap.services.llm_service import LLMService


class StreamWithCloseFailure:
    def __init__(self, iteration_failure):
        self.iteration_failure = iteration_failure
        self.close_failure = RuntimeError("private close detail")

    async def __anext__(self):
        raise self.iteration_failure

    async def aclose(self):
        raise self.close_failure


class BlockingCloseStream:
    def __init__(self, started, release, closed):
        self.started = started
        self.release = release
        self.closed = closed

    async def aclose(self):
        self.started.set()
        await asyncio.wait_for(self.release.wait(), timeout=5)
        self.closed.set()


@pytest.mark.asyncio
async def test_nested_stream_restores_context_before_each_consumer_yield__b102():
    lifecycle = object()
    lease = GovernedUseLease(Mock())
    lifecycle_token = attempt_lifecycle.set(lifecycle)
    lease_token = governed_use_lease.set(lease)
    service = LLMService.__new__(LLMService)
    service._telemetry_service = None
    observed = []
    terminal = LLMStreamChunk(text_delta="", chunk_index=0, is_final=True)

    async def fake_core(*args, **kwargs):
        observed.append((attempt_lifecycle.get(), governed_use_lease.get()))
        yield terminal

    service._call_llm_stream_async_core = fake_core

    async def nested_stream():
        before = attempt_lifecycle.get(), governed_use_lease.get()
        stream = service.call_llm_stream_async(
            messages=[{"role": "user", "content": "nested"}]
        )
        first = await anext(stream)
        after_first = attempt_lifecycle.get(), governed_use_lease.get()
        remaining = [chunk async for chunk in stream]
        after = attempt_lifecycle.get(), governed_use_lease.get()
        return before, after_first, after, [first, *remaining]

    try:
        before, after_first, after, chunks = await asyncio.create_task(nested_stream())
    finally:
        governed_use_lease.reset(lease_token)
        attempt_lifecycle.reset(lifecycle_token)

    assert before == (lifecycle, lease)
    assert observed == [(None, None)]
    assert after_first == (lifecycle, lease)
    assert after == (lifecycle, lease)
    assert chunks == [terminal]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["provider", "host", "cancellation"])
async def test_stream_close_failure_preserves_active_failure__b102(failure_kind):
    primary = {
        "provider": LLMProviderError("provider failed"),
        "host": LLMConfigurationError("host refusal"),
        "cancellation": asyncio.CancelledError(),
    }[failure_kind]
    iteration_failure = (
        AttemptLifecycleRefusal(primary) if failure_kind == "host" else primary
    )
    stream = StreamWithCloseFailure(iteration_failure)
    service = LLMService.__new__(LLMService)
    service._telemetry_service = None
    service._call_llm_stream_async_core = lambda *args, **kwargs: stream

    with pytest.raises(type(primary)) as caught:
        async for _ in service.call_llm_stream_async([]):
            pass

    assert caught.value is primary
    assert caught.value.__notes__ == ["LLM async stream close failed with RuntimeError"]


@pytest.mark.asyncio
async def test_stream_close_failure_surfaces_when_iteration_succeeds__b102():
    stream = StreamWithCloseFailure(StopAsyncIteration())
    service = LLMService.__new__(LLMService)
    service._telemetry_service = None
    service._call_llm_stream_async_core = lambda *args, **kwargs: stream

    with pytest.raises(RuntimeError) as caught:
        async for _ in service.call_llm_stream_async([]):
            pass

    assert caught.value is stream.close_failure


@pytest.mark.asyncio
async def test_cancellation_during_stream_close_waits_for_close_finalizer__b102():
    started = asyncio.Event()
    release = asyncio.Event()
    closed = asyncio.Event()
    stream = BlockingCloseStream(started, release, closed)
    service = LLMService.__new__(LLMService)
    cleanup = asyncio.create_task(
        service._close_async_stream_preserving_primary(stream, None)
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        cleanup.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(cleanup, timeout=5)

        assert closed.is_set()
    finally:
        release.set()
        if not cleanup.done():
            cleanup.cancel()
        await asyncio.gather(cleanup, return_exceptions=True)


@pytest.mark.asyncio
async def test_stream_telemetry_close_preserves_active_failure__b102():
    primary = asyncio.CancelledError("caller cancelled")
    cleanup_error = RuntimeError("private telemetry cleanup detail")

    class SpanContext:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            raise cleanup_error

    service = LLMService.__new__(LLMService)
    service._telemetry_service = SimpleNamespace(
        start_span=lambda *args, **kwargs: SpanContext()
    )
    service._build_llm_span_initial_attributes = lambda *args: {}
    service._record_llm_call_exception_safe = Mock()

    async def fail_core(*args, **kwargs):
        raise primary
        yield  # pragma: no cover - makes this an async generator

    service._call_llm_stream_async_core = fail_core
    stream = service._call_llm_stream_async_with_telemetry([], None, None, None, None)

    with pytest.raises(asyncio.CancelledError) as caught:
        async for _ in stream:
            pass

    assert caught.value is primary
    assert primary.__notes__ == [
        "LLM stream telemetry span close failed with RuntimeError"
    ]
