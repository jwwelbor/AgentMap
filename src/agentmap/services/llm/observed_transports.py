"""HTTPX transport adapters for observed governed responses."""

from threading import Lock
from typing import Optional

import httpx

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm.response_observer import (
    _send_observed_async,
    _send_observed_sync,
)


class ObservedTransport(httpx.BaseTransport, httpx.AsyncBaseTransport):
    """Stateless adapter usable by Google's shared client_args surface."""

    def __init__(self, proxy: Optional[str] = None) -> None:
        # Google shares this adapter across modes. Create only the mode used.
        self._proxy = proxy
        self._sync_client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        self._lock = Lock()
        self._sync_closed = False
        self._async_closed = False
        self._sync_close_error: BaseException | None = None
        self._async_close_error: BaseException | None = None

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
        with self._lock:
            if self._sync_closed:
                raise LLMConfigurationError("Observed sync transport is shut down")
        return _send_observed_sync(self._sync.send, request)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        with self._lock:
            if self._async_closed:
                raise LLMConfigurationError("Observed async transport is shut down")
        return await _send_observed_async(self._async.send, request)

    def close(self) -> None:
        with self._lock:
            self._sync_closed = True
            if self._sync_close_error is not None:
                raise self._sync_close_error
            client = self._sync_client
        if client is not None:
            try:
                client.close()
            except BaseException as error:
                with self._lock:
                    self._sync_close_error = error
                raise
            with self._lock:
                if self._sync_client is client:
                    self._sync_client = None

    async def aclose(self) -> None:
        with self._lock:
            self._async_closed = True
            if self._async_close_error is not None:
                raise self._async_close_error
            client = self._async_client
        if client is not None:
            try:
                await client.aclose()
            except BaseException as error:
                with self._lock:
                    self._async_close_error = error
                raise
            with self._lock:
                if self._async_client is client:
                    self._async_client = None


class ObservedSyncTransport(httpx.BaseTransport):
    """One synchronous observed HTTPX pool."""

    def __init__(self, proxy: Optional[str] = None) -> None:
        self._sync = httpx.Client(proxy=proxy)
        self._closed = False
        self._close_error: BaseException | None = None
        self._lock = Lock()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        with self._lock:
            if self._closed:
                raise LLMConfigurationError("Observed sync transport is shut down")
        return _send_observed_sync(self._sync.send, request)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            if self._close_error is not None:
                raise self._close_error
        try:
            self._sync.close()
        except BaseException as error:
            with self._lock:
                self._close_error = error
            raise


class ObservedAsyncTransport(httpx.AsyncBaseTransport):
    """One asynchronous observed HTTPX pool."""

    def __init__(self, proxy: Optional[str] = None) -> None:
        self._async = httpx.AsyncClient(proxy=proxy)
        self._closed = False
        self._close_error: BaseException | None = None
        self._lock = Lock()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        with self._lock:
            if self._closed:
                raise LLMConfigurationError("Observed async transport is shut down")
        return await _send_observed_async(self._async.send, request)

    async def aclose(self) -> None:
        with self._lock:
            self._closed = True
            if self._close_error is not None:
                raise self._close_error
        try:
            await self._async.aclose()
        except BaseException as error:
            with self._lock:
                self._close_error = error
            raise
