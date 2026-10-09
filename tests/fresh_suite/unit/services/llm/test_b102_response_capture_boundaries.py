"""Capture limits preserve exact-boundary and interrupted compression semantics."""

import gzip

import httpx
import pytest

from agentmap.services.llm import response_observer
from agentmap.services.llm.response_observer import (
    ResponseCollector,
    observe_async_response,
    observe_response,
    response_collector,
)


class SyncChunks(httpx.SyncByteStream):
    def __init__(self, chunks, failure=None):
        self.chunks, self.failure = chunks, failure
        self.closed = False

    def __iter__(self):
        yield from self.chunks
        if self.failure is not None:
            raise self.failure

    def close(self):
        self.closed = True


class AsyncChunks(httpx.AsyncByteStream):
    def __init__(self, chunks, failure=None):
        self.chunks, self.failure = chunks, failure
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk
        if self.failure is not None:
            raise self.failure

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_response_at_capture_limit_remains_available__b102(
    monkeypatch, asynchronous
):
    monkeypatch.setattr(
        response_observer, "MAX_CAPTURED_RESPONSE_BYTES", 4, raising=False
    )
    stream = AsyncChunks([b"abcd"]) if asynchronous else SyncChunks([b"abcd"])
    response = httpx.Response(200, stream=stream)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        if asynchronous:
            await observe_async_response(response)
        else:
            observe_response(response)
    finally:
        response_collector.reset(token)

    evidence = collector.seal()
    assert response.content == evidence.body == b"abcd"
    assert evidence.status == "available"
    assert evidence.unavailable_reason is None


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_interrupted_compressed_read_has_no_partial_entity__b102(asynchronous):
    failure = httpx.ReadError("offline read failed")
    prefix = gzip.compress(b"incomplete compressed entity")[:12]
    stream = (
        AsyncChunks([prefix], failure)
        if asynchronous
        else SyncChunks([prefix], failure)
    )
    response = httpx.Response(200, stream=stream, headers={"content-encoding": "gzip"})
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        with pytest.raises(httpx.ReadError) as caught:
            if asynchronous:
                await observe_async_response(response)
            else:
                observe_response(response)
    finally:
        response_collector.reset(token)

    evidence = collector.seal()
    assert caught.value is failure
    assert stream.closed
    assert evidence.status == "unavailable"
    assert evidence.body is None
    assert evidence.unavailable_reason == "interrupted_read"
    assert collector.failed
