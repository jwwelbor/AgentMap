"""Synchronous client reservations sharing the factory's cache ownership."""

import asyncio
from threading import Condition, Lock, get_ident
from typing import TYPE_CHECKING, Any, Dict, Tuple

from agentmap.async_lifecycle import raise_cleanup_error_or_note
from agentmap.exceptions import LLMConfigurationError, LLMLifecycleCleanupError


class OrdinaryClientLifecycleMixin:
    """Keep admitted builders owned until publication or failure and drain."""

    if TYPE_CHECKING:
        _cache_lock: Any
        _ordinary_condition: Condition
        _ordinary_pending: int
        _ordinary_threads: dict[int, set[str]]
        _ordinary_waiter: Tuple[asyncio.AbstractEventLoop, asyncio.Future[Any]] | None
        _ordinary_cleanup_error: LLMLifecycleCleanupError | None
        _clients: dict[str, Any]
        _key_locks: dict[str, Any]
        _api_key_tokens: dict[str, str]
        _published_tokens: set[str]
        _pending_tokens: dict[str, int]
        _owners: list[Any]
        _active_governed: set[asyncio.Task[Any]]
        _active_uses: set[Any]
        _cleanup_error: LLMLifecycleCleanupError | None
        _owner_loop: asyncio.AbstractEventLoop | None
        _closing: bool

        def _cache_key(
            self, provider: str, config: Dict[str, Any], streaming: bool, governed: bool
        ) -> str: ...

        def _create_langchain_client(
            self,
            provider: str,
            config: Dict[str, Any],
            streaming: bool = False,
            *,
            governed: bool = False,
            owner: Any = None,
        ) -> Any: ...

        def _finish_pending_token(self, api_key: str, token: str) -> None: ...

        def _ensure_open(self) -> None: ...

    def _initialize_ordinary_lifecycle(self) -> None:
        self._ordinary_condition = Condition(self._cache_lock)
        self._ordinary_pending = 0
        self._ordinary_threads: dict[int, set[str]] = {}
        self._ordinary_waiter = None
        self._ordinary_cleanup_error = None

    def _get_or_create_ordinary(
        self, provider: str, config: Dict[str, Any], streaming: bool
    ) -> Any:
        with self._cache_lock:
            cache_key = self._cache_key(provider, config, streaming, False)
            api_key = config.get("api_key") or ""
            token = self._api_key_tokens[api_key]
            if cache_key in self._ordinary_threads.get(get_ident(), ()):
                raise LLMConfigurationError("Reentrant same-key client construction")
            if cache_key in self._clients:
                return self._clients[cache_key]
            key_lock = self._key_locks.setdefault(cache_key, Lock())
            self._pending_tokens[token] = self._pending_tokens.get(token, 0) + 1
            self._ordinary_pending += 1
            self._ordinary_threads.setdefault(get_ident(), set()).add(cache_key)
        primary_error: BaseException | None = None
        try:
            with key_lock:
                with self._cache_lock:
                    self._ensure_open()
                    if cache_key in self._clients:
                        return self._clients[cache_key]
                client = self._create_langchain_client(provider, config, streaming)
                with self._cache_lock:
                    self._clients[cache_key] = client
                    self._published_tokens.add(token)
                return client
        except BaseException as error:
            primary_error = error
            raise
        finally:
            self._finish_ordinary_reservation(cache_key, api_key, token, primary_error)

    def _finish_ordinary_reservation(
        self,
        cache_key: str,
        api_key: str,
        token: str,
        primary: BaseException | None,
    ) -> None:
        failures: list[BaseException] = []
        with self._cache_lock:
            try:
                self._finish_pending_token(api_key, token)
            except BaseException as error:
                failures.append(error)
            finally:
                self._ordinary_pending -= 1
                keys = self._ordinary_threads[get_ident()]
                keys.remove(cache_key)
                if not keys:
                    del self._ordinary_threads[get_ident()]
                self._ordinary_condition.notify_all()
                try:
                    self._notify_ordinary_drain_locked()
                except RuntimeError as error:
                    failures.append(error)
            if failures:
                previous = self._ordinary_cleanup_error
                if previous is not None:
                    failures.insert(0, previous)
                cleanup = LLMLifecycleCleanupError(
                    "construction_rollback", tuple(failures)
                )
                self._ordinary_cleanup_error = self._cleanup_error = cleanup
                self._closing = True
                raise_cleanup_error_or_note(
                    primary, cleanup, operation="ordinary finalization"
                )

    def _notify_ordinary_drain_locked(self) -> None:
        pair = self._ordinary_waiter
        if self._ordinary_pending == 0 and pair is not None:
            pair[0].call_soon_threadsafe(self._complete_ordinary_drain, pair)

    def _complete_ordinary_drain(
        self, pair: Tuple[asyncio.AbstractEventLoop, asyncio.Future[Any]]
    ) -> None:
        with self._cache_lock:
            if self._ordinary_waiter is pair and not pair[1].done():
                pair[1].set_result(None)

    def _refuse_ordinary_reentry_locked(self) -> None:
        if get_ident() in self._ordinary_threads:
            raise LLMConfigurationError("Reentrant client construction lifecycle call")

    async def _wait_ordinary_drain(self) -> None:
        loop = asyncio.get_running_loop()
        pair: Tuple[asyncio.AbstractEventLoop, asyncio.Future[Any]] | None = None
        with self._cache_lock:
            if self._ordinary_pending:
                pair = (loop, loop.create_future())
                self._ordinary_waiter = pair
        try:
            if pair is not None:
                await pair[1]
            with self._cache_lock:
                if self._ordinary_cleanup_error is not None:
                    raise self._ordinary_cleanup_error from None
        finally:
            with self._cache_lock:
                if pair is not None and self._ordinary_waiter is pair:
                    self._ordinary_waiter = None

    def _clear_ordinary_cache(self) -> None:
        with self._cache_lock:
            self._refuse_ordinary_reentry_locked()
            self._check_clear_admission_locked()
            while self._ordinary_pending:
                self._ordinary_condition.wait()
                self._check_clear_admission_locked()
            self._clients.clear()
            self._key_locks.clear()
            self._api_key_tokens.clear()
            self._published_tokens.clear()
            self._pending_tokens.clear()

    def _check_clear_admission_locked(self) -> None:
        self._ensure_open()
        if self._owners or self._active_governed or self._active_uses:
            raise LLMConfigurationError(
                "Governed clients require awaited shutdown before cache clearing"
            )

    def prepare_sync_shutdown(self) -> bool:
        """Refuse pending ownership without mutating healthy admission."""
        with self._cache_lock:
            self._refuse_ordinary_reentry_locked()
            if (
                self._ordinary_pending
                or self._owners
                or self._active_governed
                or self._active_uses
                or self._cleanup_error is not None
                or self._owner_loop is not None
            ):
                return False
            self._closing = True
            return True
