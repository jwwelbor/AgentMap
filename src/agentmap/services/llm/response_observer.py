"""Attempt-local observation of decoded HTTP entities, before SDK parsing."""

import re
from contextvars import ContextVar
from threading import Lock
from typing import AsyncIterator, Awaitable, Callable, Iterator, Optional

import httpx

from agentmap.exceptions import LLMConfigurationError
from agentmap.models.llm_attempt import LLMResponseEvidence


class ResponseCaptureFailure(RuntimeError):
    def __init__(self, *, cleanup_failed: bool = False) -> None:
        super().__init__("physical attempt response capture failed")
        self.cleanup_failed = cleanup_failed


class ResponseCollector:
    """Thread-safe and sealable: late thread responses cannot change settlement."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._sealed = False
        self._requests = 0
        self._responses = 0
        self.evidence = LLMResponseEvidence()
        self.failed = False
        self.cleanup_failed = False
        self._partial = bytearray()

    def start_request(self) -> bool:
        """Reject a second wire request before any transport can send it."""
        with self._lock:
            if self._sealed:
                return False
            self._requests += 1
            if self._requests > 1:
                self.failed = True
                return False
            return True

    def start(self) -> bool:
        with self._lock:
            if self._sealed:
                return False
            self._responses += 1
            if self._responses > 1:
                self.failed = True
                return False
            return True

    def record(self, evidence: LLMResponseEvidence, failed: bool = False) -> None:
        with self._lock:
            if not self._sealed:
                self.evidence = evidence
                self.failed = self.failed or failed
                if evidence.status == "available":
                    self._partial.clear()

    def seal(self) -> LLMResponseEvidence:
        with self._lock:
            if self._sealed:
                return self.evidence
            self._sealed = True
            if self._partial and self.evidence.status != "available":
                self.evidence = LLMResponseEvidence(
                    status="partial",
                    body=bytes(self._partial),
                    http_status=self.evidence.http_status,
                    media_type=self.evidence.media_type,
                    unavailable_reason="interrupted_read",
                )
            return self.evidence

    def progress(self, chunk: bytes) -> None:
        with self._lock:
            if not self._sealed:
                self._partial.extend(chunk)

    def partial_body(self) -> bytes:
        with self._lock:
            return bytes(self._partial)

    def mark_cleanup_failed(self) -> None:
        with self._lock:
            if not self._sealed:
                self.cleanup_failed = True


response_collector: ContextVar[Optional[ResponseCollector]] = ContextVar(
    "agentmap_response_collector", default=None
)


def _evidence(
    response: httpx.Response, body: Optional[bytes], interrupted: bool = False
) -> LLMResponseEvidence:
    media_token = (
        response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    )
    # Export only a syntactically valid media-type token, never a header dump.
    media = (
        media_token
        if re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", media_token)
        else None
    )
    return LLMResponseEvidence(
        status=(
            ("partial" if body is not None else "unavailable")
            if interrupted
            else "available"
        ),
        body=body,
        http_status=response.status_code,
        media_type=media,
        unavailable_reason="interrupted_read" if interrupted else None,
    )


class _SyncRead(httpx.SyncByteStream):
    def __init__(
        self,
        stream: httpx.SyncByteStream,
        progress: Callable[[bytes], None],
    ) -> None:
        self.stream, self.progress = stream, progress

    def __iter__(self) -> Iterator[bytes]:
        for chunk in self.stream:
            self.progress(chunk)
            yield chunk

    def close(self) -> None:
        self.stream.close()


class _AsyncRead(httpx.AsyncByteStream):
    def __init__(
        self,
        stream: httpx.AsyncByteStream,
        progress: Callable[[bytes], None],
    ) -> None:
        self.stream, self.progress = stream, progress

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self.stream:
            self.progress(chunk)
            yield chunk

    async def aclose(self) -> None:
        await self.stream.aclose()


def _interrupted(
    response: httpx.Response, collector: ResponseCollector
) -> LLMResponseEvidence:
    # Interrupted compressed transfer chunks are not decoded entity bytes.
    body = (
        None
        if response.headers.get("content-encoding", "identity") != "identity"
        else collector.partial_body()
    )
    return _evidence(response, body, interrupted=True)


def _record_complete(
    collector: ResponseCollector, response: httpx.Response, body: bytes
) -> None:
    try:
        evidence = _evidence(response, body)
    except Exception:
        # Observation diagnostics must not prevent SDK parsing/accounting.
        # The complete bytes are still known; retain them without metadata.
        collector.record(
            LLMResponseEvidence(status="available", body=body, unavailable_reason=None),
            failed=True,
        )
        return
    collector.record(evidence)


def observe_response(response: httpx.Response) -> None:
    collector = response_collector.get()
    if collector is None or not collector.start():
        return
    progress = (
        collector.progress
        if response.headers.get("content-encoding", "identity") == "identity"
        else lambda chunk: None
    )
    assert isinstance(response.stream, httpx.SyncByteStream)
    response.stream = _SyncRead(response.stream, progress)
    try:
        body = response.read()  # Public HTTPX read caches bytes for the SDK.
    except BaseException as read_error:
        # Diagnose interrupted reads (including cancellation), retain, propagate.
        collector.record(_interrupted(response, collector), failed=True)
        try:
            response.close()
        except BaseException as cleanup_error:
            collector.mark_cleanup_failed()
            raise read_error from cleanup_error
        raise
    _record_complete(collector, response, body)


async def observe_async_response(response: httpx.Response) -> None:
    collector = response_collector.get()
    if collector is None or not collector.start():
        return
    progress = (
        collector.progress
        if response.headers.get("content-encoding", "identity") == "identity"
        else lambda chunk: None
    )
    assert isinstance(response.stream, httpx.AsyncByteStream)
    response.stream = _AsyncRead(response.stream, progress)
    try:
        body = await response.aread()
    except BaseException as read_error:
        collector.record(_interrupted(response, collector), failed=True)
        try:
            await response.aclose()
        except BaseException as cleanup_error:
            collector.mark_cleanup_failed()
            raise read_error from cleanup_error
        raise
    _record_complete(collector, response, body)


def _send_observed_sync(
    send: Callable[..., httpx.Response], request: httpx.Request
) -> httpx.Response:
    collector = response_collector.get()
    if collector is not None and not collector.start_request():
        raise ResponseCaptureFailure()
    response = send(request, stream=True)
    observe_response(response)
    return response


async def _send_observed_async(
    send: Callable[..., Awaitable[httpx.Response]], request: httpx.Request
) -> httpx.Response:
    collector = response_collector.get()
    if collector is not None and not collector.start_request():
        raise ResponseCaptureFailure()
    response = await send(request, stream=True)
    await observe_async_response(response)
    return response


class ObservedTransport(httpx.BaseTransport, httpx.AsyncBaseTransport):
    """Stateless transport adapter usable by Google's shared client_args surface.

    Both underlying HTTPX transports retain ownership of HTTP requests. Reading
    the entity here leaves the cached body intact for the SDK parser, while an
    explicit transport selects HTTPX over Google's alternate aiohttp backend.
    """

    def __init__(self, proxy: Optional[str] = None) -> None:
        # Google shares this adapter across modes. Create only the mode used.
        self._proxy = proxy
        self._sync_client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        self._lock = Lock()
        self._sync_closed = False
        self._async_closed = False

    @property
    def _sync(self) -> httpx.Client:
        with self._lock:
            if self._sync_closed:
                raise LLMConfigurationError("Observed transport is shut down")
            if self._sync_client is None:
                self._sync_client = httpx.Client(proxy=self._proxy)
            return self._sync_client

    @property
    def _async(self) -> httpx.AsyncClient:
        with self._lock:
            if self._async_closed:
                raise LLMConfigurationError("Observed transport is shut down")
            if self._async_client is None:
                self._async_client = httpx.AsyncClient(proxy=self._proxy)
            return self._async_client

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return _send_observed_sync(self._sync.send, request)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await _send_observed_async(self._async.send, request)

    def close(self) -> None:
        with self._lock:
            self._sync_closed = True
            client, self._sync_client = self._sync_client, None
        if client is not None:
            client.close()

    async def aclose(self) -> None:
        with self._lock:
            self._async_closed = True
            client, self._async_client = self._async_client, None
        if client is not None:
            await client.aclose()


class ObservedSyncTransport(httpx.BaseTransport):
    """One synchronous observed HTTPX pool."""

    def __init__(self, proxy: Optional[str] = None) -> None:
        self._sync = httpx.Client(proxy=proxy)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return _send_observed_sync(self._sync.send, request)

    def close(self) -> None:
        self._sync.close()


class ObservedAsyncTransport(httpx.AsyncBaseTransport):
    """One asynchronous observed HTTPX pool."""

    def __init__(self, proxy: Optional[str] = None) -> None:
        self._async = httpx.AsyncClient(proxy=proxy)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await _send_observed_async(self._async.send, request)

    async def aclose(self) -> None:
        await self._async.aclose()
