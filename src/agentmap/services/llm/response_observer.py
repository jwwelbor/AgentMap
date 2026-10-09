"""Attempt-local observation of decoded HTTP entities, before SDK parsing."""

import re
from contextvars import ContextVar
from threading import Lock
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator, Optional

import httpx

from agentmap.exceptions import ResponseCaptureFailure
from agentmap.models.llm_attempt import LLMResponseEvidence

MAX_CAPTURED_RESPONSE_BYTES = 1_048_576


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
        self._capture_limit_exceeded = False

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
                self._partial.clear()

    def seal(self) -> LLMResponseEvidence:
        with self._lock:
            if self._sealed:
                return self.evidence
            self._sealed = True
            if self._partial and self.evidence.status != "available":
                reason = (
                    "capture_size_limit"
                    if self._capture_limit_exceeded
                    else "interrupted_read"
                )
                self.evidence = LLMResponseEvidence(
                    status="partial",
                    body=bytes(self._partial),
                    http_status=self.evidence.http_status,
                    media_type=self.evidence.media_type,
                    unavailable_reason=reason,
                )
            return self.evidence

    def progress(self, chunk: bytes) -> None:
        with self._lock:
            if not self._sealed:
                remaining = MAX_CAPTURED_RESPONSE_BYTES - len(self._partial)
                if len(chunk) > remaining:
                    if remaining > 0:
                        self._partial.extend(chunk[:remaining])
                    self._capture_limit_exceeded = True
                else:
                    self._partial.extend(chunk)

    def capture_limit_exceeded(self) -> bool:
        with self._lock:
            return self._capture_limit_exceeded

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
    response: httpx.Response,
    body: Optional[bytes],
    interrupted: bool = False,
    partial_reason: Optional[str] = None,
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
    unavailable_reason = partial_reason or ("interrupted_read" if interrupted else None)
    return LLMResponseEvidence(
        status=(
            ("partial" if body is not None else "unavailable")
            if unavailable_reason is not None
            else "available"
        ),
        body=body,
        http_status=response.status_code,
        media_type=media,
        unavailable_reason=unavailable_reason,
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
    reason = (
        "capture_size_limit"
        if collector.capture_limit_exceeded()
        else "interrupted_read"
    )
    return _evidence(response, body, interrupted=True, partial_reason=reason)


def _record_complete(
    collector: ResponseCollector, response: httpx.Response, body: bytes
) -> None:
    oversized = len(body) > MAX_CAPTURED_RESPONSE_BYTES
    captured_body = body[:MAX_CAPTURED_RESPONSE_BYTES] if oversized else body
    try:
        evidence = _evidence(
            response,
            captured_body,
            partial_reason="capture_size_limit" if oversized else None,
        )
    except Exception:
        # Observation diagnostics must not prevent SDK parsing/accounting.
        # Preserve only bounded evidence if metadata inspection failed.
        if oversized:
            collector.record(
                LLMResponseEvidence(
                    status="partial",
                    body=captured_body,
                    unavailable_reason="capture_size_limit",
                )
            )
        else:
            collector.record(
                LLMResponseEvidence(
                    status="available", body=body, unavailable_reason=None
                ),
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


def observe_successful_receipt(
    logger: Any,
    log_non_text: Callable[..., None],
    response: Any,
    text: str,
    text_status: str,
    provider: str,
    model: str,
    request_id: Optional[str],
    finish_reason: Optional[str],
    usage: Optional[Any],
) -> None:
    """Log a safe receipt summary and delegate non-text diagnostics."""
    if text_status == "non_text":
        log_non_text(
            response,
            provider=provider,
            model=model,
            request_id=request_id,
            finish_reason=finish_reason,
            usage_present=usage is not None,
        )
    logger.debug(
        f"LLM call successful, response length: {len(text)}"
        + (f", request_id: {request_id}" if request_id else "")
    )
