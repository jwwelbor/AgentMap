"""Awaited construction and shutdown for governed provider clients."""

import asyncio
import secrets
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict

from agentmap.async_lifecycle import (
    await_terminal_task,
    create_task_or_close,
)
from agentmap.async_lifecycle import raise_cleanup_error_or_note as note_cleanup
from agentmap.exceptions import LLMConfigurationError, LLMLifecycleCleanupError
from agentmap.services.llm.invocation_lease import GovernedUseLease, governed_use_lease
from agentmap.services.llm.observed_clients import ObservedResources
from agentmap.services.llm.ordinary_lifecycle import OrdinaryClientLifecycleMixin


class GovernedClientLifecycleMixin(OrdinaryClientLifecycleMixin):
    """Per-key construction and terminal resource ownership for the factory."""

    _cache_lock: Any
    _clients: dict[str, Any]

    if TYPE_CHECKING:

        def _create_langchain_client(
            self,
            provider: str,
            config: Dict[str, Any],
            streaming: bool = False,
            *,
            governed: bool = False,
            owner: ObservedResources | None = None,
        ) -> Any: ...

    def _initialize_governed_lifecycle(self) -> None:
        self._initialize_ordinary_lifecycle()
        self._owners: list[ObservedResources] = []
        self._key_locks: dict[str, Lock] = {}
        self._api_key_tokens: dict[str, str] = {}
        self._published_tokens: set[str] = set()
        self._pending_tokens: dict[str, int] = {}
        self._active_governed: set[asyncio.Task[Any]] = set()
        self._active_uses: set[GovernedUseLease] = set()
        self._owner_loop: asyncio.AbstractEventLoop | None = None
        self._shutdown_task: asyncio.Task[None] | None = None
        self._cleanup_error: LLMLifecycleCleanupError | None = None
        self._retired = False
        self._closing = False
        self._closed = False

    def retire(self) -> None:
        """Close invocation admission while existing leases finish their work."""
        with self._cache_lock:
            self._assert_owner_loop_locked()
            self._retired = True

    def begin_governed_invocation(self) -> GovernedUseLease:
        """Reserve one logical governed call before client acquisition."""
        with self._cache_lock:
            if self._retired:
                raise LLMConfigurationError("LLM client factory is retired")
            self._ensure_open()
            lease = GovernedUseLease(self)
            self._active_uses.add(lease)
            return lease

    def begin_governed_worker(self) -> GovernedUseLease:
        """Reserve a sync provider worker before submitting it to a thread."""
        with self._cache_lock:
            self._ensure_open()
            lease = GovernedUseLease(self, pending_worker=True)
            self._active_uses.add(lease)
            return lease

    def prepare_shutdown(self) -> None:
        """Reserve idle shutdown without consuming resource ownership."""
        with self._cache_lock:
            self._assert_owner_loop_locked()
            self._reserve_shutdown_locked()

    def _assert_owner_loop_locked(self) -> None:
        owner_loop = self._owner_loop
        if owner_loop is None:
            return
        wrong_loop_error = "LLM client factory must be used on its owning event loop"
        if owner_loop.is_closed():
            raise LLMConfigurationError(
                "LLM client factory owning event loop is closed"
            )
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError as error:
            raise LLMConfigurationError(wrong_loop_error) from error
        if current_loop is not owner_loop:
            raise LLMConfigurationError(wrong_loop_error)

    def _bind_or_assert_owner_loop_locked(self) -> None:
        if self._owner_loop is None:
            self._owner_loop = asyncio.get_running_loop()
            return
        self._assert_owner_loop_locked()

    def assert_owner_loop(self) -> None:
        """Refuse runtime use from a loop other than the governed owner."""
        with self._cache_lock:
            self._assert_owner_loop_locked()

    def _reserve_shutdown_locked(self) -> None:
        self._refuse_ordinary_reentry_locked()
        if self._closed:
            return
        if self._active_uses:
            raise LLMConfigurationError(
                "Cannot shut down while governed provider work is active"
            )
        self._closing = True

    async def get_or_create_governed_client(
        self, provider: str, config: Dict[str, Any]
    ) -> Any:
        """Construct one governed owner per key with awaited rollback."""
        if not isinstance(config, dict):
            raise TypeError("config must be a dictionary")
        with self._cache_lock:
            self._ensure_open()
            self._bind_or_assert_owner_loop_locked()
            cache_key = self._cache_key(provider, config, False, True)
            api_key = config.get("api_key") or ""
            token = self._api_key_tokens[api_key]
            key_lock = self._key_locks.setdefault(cache_key, Lock())
            self._pending_tokens[token] = self._pending_tokens.get(token, 0) + 1
            construction = self._run_governed_construction(
                key_lock, cache_key, provider, config, api_key, token
            )
            try:
                lifecycle = create_task_or_close(construction)
            except BaseException as primary_error:
                operation = "governed construction rollback"
                try:
                    self._finish_pending_token(api_key, token)
                except BaseException as error:
                    note_cleanup(primary_error, error, operation=operation)
                raise
            self._active_governed.add(lifecycle)
        outcome = await await_terminal_task(lifecycle)
        return outcome.result()

    async def _run_governed_construction(
        self,
        key_lock: Lock,
        cache_key: str,
        provider: str,
        config: Dict[str, Any],
        api_key: str,
        token: str,
    ) -> Any:
        current = asyncio.current_task()
        assert current is not None
        try:
            result = await asyncio.to_thread(
                self._construct_governed, key_lock, cache_key, provider, config, token
            )
            return await self._finish_governed_construction(result)
        finally:
            with self._cache_lock:
                self._active_governed.discard(current)
                self._finish_pending_token(api_key, token)

    def _construct_governed(
        self,
        key_lock: Lock,
        cache_key: str,
        provider: str,
        config: Dict[str, Any],
        token: str,
    ) -> tuple[Any | None, ObservedResources | None, BaseException | None]:
        with key_lock:
            with self._cache_lock:
                self._ensure_open()
                cached = self._clients.get(cache_key)
                if cached is not None:
                    return cached, None, None
            owner = ObservedResources()
            try:
                client = self._create_langchain_client(
                    provider, config, governed=True, owner=owner
                )
            except BaseException as error:
                return None, owner, error
            with self._cache_lock:
                try:
                    self._ensure_open()
                except (LLMLifecycleCleanupError, LLMConfigurationError) as error:
                    return None, owner, error
                self._clients[cache_key] = client
                self._published_tokens.add(token)
                self._owners.append(owner)
            return client, None, None

    async def _finish_governed_construction(
        self,
        result: tuple[Any | None, ObservedResources | None, BaseException | None],
    ) -> Any:
        client, owner, error = result
        if owner is not None:
            try:
                await owner.aclose()
            except BaseException as cleanup_error:
                assert error is not None
                if isinstance(cleanup_error, LLMLifecycleCleanupError):
                    retained_error = cleanup_error
                else:
                    retained_error = LLMLifecycleCleanupError(
                        "construction_rollback", (cleanup_error,)
                    )
                with self._cache_lock:
                    if not any(existing is owner for existing in self._owners):
                        self._owners.append(owner)
                    self._closing = True
                    self._cleanup_error = retained_error
                if not isinstance(error, Exception):
                    raise error from retained_error
                raise LLMLifecycleCleanupError(
                    "construction_rollback", (error, retained_error)
                ) from None
        if error is not None:
            raise error
        return client

    def _cache_key(
        self, provider: str, config: Dict[str, Any], streaming: bool, governed: bool
    ) -> str:
        api_key = config.get("api_key") or ""
        with self._cache_lock:
            self._ensure_open()
            api_key_identity = self._api_key_tokens.get(api_key)
            if api_key_identity is None:
                api_key_identity = secrets.token_hex(32)
                while api_key_identity in self._api_key_tokens.values():
                    api_key_identity = secrets.token_hex(32)
                self._api_key_tokens[api_key] = api_key_identity
        return (
            f"{provider}_{config.get('model')}_{api_key_identity}_"
            f"{config.get('max_tokens')}_{config.get('temperature', 0.7)!r}_{streaming}"
            + ("_single_dispatch" if governed else "")
        )

    def _finish_pending_token(self, api_key: str, token: str) -> None:
        remaining = self._pending_tokens[token] - 1
        if remaining:
            self._pending_tokens[token] = remaining
        else:
            del self._pending_tokens[token]
            self._release_unused_token(api_key, token)

    def _release_unused_token(self, api_key: str, token: str) -> None:
        if token in self._published_tokens or token in self._pending_tokens:
            return
        if self._api_key_tokens.get(api_key) == token:
            del self._api_key_tokens[api_key]
        for cache_key in list(self._key_locks):
            if f"_{token}_" in cache_key:
                del self._key_locks[cache_key]

    def _ensure_open(self) -> None:
        if self._cleanup_error is not None:
            raise self._cleanup_error from None
        if self._closing or self._closed:
            raise LLMConfigurationError("LLM client factory is shut down")
        if self._retired:
            lease = governed_use_lease.get()
            if (
                lease is None
                or lease._factory is not self
                or lease._state != "active"
                or lease not in self._active_uses
            ):
                raise LLMConfigurationError("LLM client factory is retired")

    async def shutdown(self) -> None:
        """Reject new clients and finish cleanup despite caller cancellation."""
        with self._cache_lock:
            if self._closed:
                return
            self._assert_owner_loop_locked()
            self._reserve_shutdown_locked()
            if self._shutdown_task is None or self._shutdown_task.done():
                self._shutdown_task = create_task_or_close(self._finish_shutdown())
            task = self._shutdown_task
        outcome = await await_terminal_task(task)
        outcome.result()

    async def _finish_shutdown(self) -> None:
        await self._wait_ordinary_drain()
        with self._cache_lock:
            active = list(self._active_governed)
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        with self._cache_lock:
            owners = list(self._owners)
        failures: list[BaseException] = []
        closed: set[int] = set()
        for owner in owners:
            try:
                await owner.aclose()
                closed.add(id(owner))
            except BaseException as error:
                failures.append(error)
        with self._cache_lock:
            self._owners = [owner for owner in self._owners if id(owner) not in closed]
            if failures or self._owners:
                if not failures:
                    failures.append(
                        LLMConfigurationError("Governed cleanup owner remains open")
                    )
                cleanup_error = LLMLifecycleCleanupError(
                    "factory_shutdown", tuple(failures)
                )
                self._cleanup_error = cleanup_error
                self._closing = True
            else:
                self._clients.clear()
                self._key_locks.clear()
                self._api_key_tokens.clear()
                self._published_tokens.clear()
                self._pending_tokens.clear()
                self._cleanup_error = None
                self._closed = True
                self._closing = True
                cleanup_error = None
        if cleanup_error is not None:
            raise cleanup_error from None
