"""B102: failed observation releases acquired HTTP responses."""

import asyncio
import gzip

import httpx
import pytest

from agentmap.services.llm import response_observer
from agentmap.services.llm.observed_transports import ObservedTransport
from agentmap.services.llm.response_observer import (
    ResponseCollector,
    observe_async_response,
    observe_response,
    response_collector,
)


class FailingSyncStream(httpx.SyncByteStream):
    def __init__(self, failure, prefix=b"partial"):
        self.failure = failure
        self.prefix = prefix
        self.closed = False

    def __iter__(self):
        yield self.prefix
        raise self.failure

    def close(self):
        self.closed = True


class FailingAsyncStream(httpx.AsyncByteStream):
    def __init__(self, failure, prefix=b"partial"):
        self.failure = failure
        self.prefix = prefix
        self.closed = False

    async def __aiter__(self):
        yield self.prefix
        raise self.failure

    async def aclose(self):
        self.closed = True


class ChunkedSyncStream(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    def __iter__(self):
        yield from self.chunks

    def close(self):
        pass


class ChunkedAsyncStream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        pass


def test_response_collector_keeps_only_bounded_prefix__b102(monkeypatch):
    monkeypatch.setattr(
        response_observer, "MAX_CAPTURED_RESPONSE_BYTES", 4, raising=False
    )
    collector = ResponseCollector()

    collector.progress(b"abcd")
    collector.progress(b"efgh")

    assert collector.partial_body() == b"abcd"


def test_sync_oversized_response_is_partial_while_httpx_body_stays_complete__b102(
    monkeypatch,
):
    monkeypatch.setattr(
        response_observer, "MAX_CAPTURED_RESPONSE_BYTES", 4, raising=False
    )
    response = httpx.Response(
        200,
        stream=ChunkedSyncStream([b"abcd", b"efgh"]),
        headers={"content-type": "application/json"},
    )
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        observe_response(response)
    finally:
        response_collector.reset(token)

    evidence = collector.seal()
    assert response.content == b"abcdefgh"
    assert evidence.status == "partial"
    assert evidence.body == b"abcd"
    assert evidence.unavailable_reason == "capture_size_limit"
    assert not collector.failed


@pytest.mark.asyncio
async def test_async_oversized_response_is_partial_while_httpx_body_stays_complete__b102(
    monkeypatch,
):
    monkeypatch.setattr(
        response_observer, "MAX_CAPTURED_RESPONSE_BYTES", 4, raising=False
    )
    response = httpx.Response(
        200,
        stream=ChunkedAsyncStream([b"abcd", b"efgh"]),
        headers={"content-type": "application/json"},
    )
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        await observe_async_response(response)
    finally:
        response_collector.reset(token)

    evidence = collector.seal()
    assert response.content == b"abcdefgh"
    assert evidence.status == "partial"
    assert evidence.body == b"abcd"
    assert evidence.unavailable_reason == "capture_size_limit"
    assert not collector.failed


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_compressed_oversized_entity_is_bounded_after_decode__b102(
    monkeypatch, asynchronous
):
    monkeypatch.setattr(
        response_observer, "MAX_CAPTURED_RESPONSE_BYTES", 4, raising=False
    )
    payload = gzip.compress(b"abcdefgh")
    stream = (
        ChunkedAsyncStream([payload]) if asynchronous else ChunkedSyncStream([payload])
    )
    response = httpx.Response(
        200,
        stream=stream,
        headers={"content-encoding": "gzip", "content-type": "application/json"},
    )
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
    assert response.content == b"abcdefgh"
    assert evidence.status == "partial"
    assert evidence.body == b"abcd"
    assert evidence.unavailable_reason == "capture_size_limit"
    assert not collector.failed


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_interrupted_oversized_entity_keeps_only_bounded_prefix__b102(
    monkeypatch, asynchronous
):
    monkeypatch.setattr(
        response_observer, "MAX_CAPTURED_RESPONSE_BYTES", 4, raising=False
    )
    failure = httpx.ReadError("offline read failed")
    stream = FailingAsyncStream(failure) if asynchronous else FailingSyncStream(failure)
    response = httpx.Response(200, stream=stream)
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
    assert response.is_closed and stream.closed
    assert evidence.status == "partial"
    assert evidence.body == b"part"
    assert evidence.unavailable_reason == "capture_size_limit"
    assert collector.failed


def test_sync_interrupted_read_closes_response_and_retains_original__b102():
    failure = httpx.ReadError("offline read failed")
    stream = FailingSyncStream(failure)
    response = httpx.Response(200, stream=stream)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        with pytest.raises(httpx.ReadError) as caught:
            observe_response(response)
    finally:
        response_collector.reset(token)
    assert caught.value is failure
    assert response.is_closed and stream.closed
    assert collector.seal().body == b"partial"


def test_sync_transport_releases_acquired_response_on_read_error__b102(monkeypatch):
    response = httpx.Response(200, stream=FailingSyncStream(httpx.ReadError("read")))
    transport = ObservedTransport()
    monkeypatch.setattr(transport._sync, "send", lambda request, **kwargs: response)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        with pytest.raises(httpx.ReadError):
            transport.handle_request(httpx.Request("GET", "https://offline.test"))
    finally:
        response_collector.reset(token)
        transport.close()
    assert response.is_closed
    assert collector.seal().body == b"partial"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [httpx.ReadError("read"), asyncio.CancelledError()])
async def test_async_interrupted_read_closes_response_and_retains_original__b102(
    failure,
):
    stream = FailingAsyncStream(failure)
    response = httpx.Response(200, stream=stream)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        with pytest.raises(type(failure)) as caught:
            await observe_async_response(response)
    finally:
        response_collector.reset(token)
    assert caught.value is failure
    assert response.is_closed and stream.closed
    assert collector.seal().body == b"partial"


@pytest.mark.asyncio
async def test_async_transport_releases_acquired_response_on_read_error__b102(
    monkeypatch,
):
    response = httpx.Response(200, stream=FailingAsyncStream(httpx.ReadError("read")))
    transport = ObservedTransport()

    async def acquired(request, **kwargs):
        return response

    monkeypatch.setattr(transport._async, "send", acquired)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        with pytest.raises(httpx.ReadError):
            await transport.handle_async_request(
                httpx.Request("GET", "https://offline.test")
            )
    finally:
        response_collector.reset(token)
        await transport.aclose()
    assert response.is_closed
    assert collector.seal().body == b"partial"


def test_cleanup_failure_remains_visible_without_hiding_read_failure__b102():
    failure = httpx.ReadError("offline read failed")
    cleanup = RuntimeError("cleanup failed")
    stream = FailingSyncStream(failure)
    stream.close = lambda: (_ for _ in ()).throw(cleanup)
    response = httpx.Response(200, stream=stream)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        with pytest.raises(httpx.ReadError) as caught:
            observe_response(response)
    finally:
        response_collector.reset(token)
    assert caught.value is failure
    assert caught.value.__cause__ is cleanup
    assert collector.seal().body == b"partial"


@pytest.mark.asyncio
async def test_async_cleanup_failure_remains_visible_with_cancellation__b102():
    failure = asyncio.CancelledError()
    cleanup = RuntimeError("async cleanup failed")
    stream = FailingAsyncStream(failure)

    async def fail_cleanup():
        raise cleanup

    stream.aclose = fail_cleanup
    response = httpx.Response(200, stream=stream)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        with pytest.raises(asyncio.CancelledError) as caught:
            await observe_async_response(response)
    finally:
        response_collector.reset(token)
    assert caught.value is failure
    assert caught.value.__cause__ is cleanup
    assert collector.seal().body == b"partial"
