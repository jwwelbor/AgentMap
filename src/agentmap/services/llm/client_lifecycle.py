"""Awaited construction and shutdown for governed provider clients."""

import asyncio
from hashlib import sha256
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm.observed_clients import ObservedResources
from agentmap.services.llm.terminal_task import (
    await_terminal_task,
    raise_cleanup_failures,
)


class GovernedClientLifecycleMixin:
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
        self._owners: list[ObservedResources] = []
        self._key_locks: dict[str, Lock] = {}
        self._active_governed: set[asyncio.Task[Any]] = set()
        self._shutdown_task: asyncio.Task[None] | None = None
        self._closing = False
        self._closed = False

    async def get_or_create_governed_client(
        self, provider: str, config: Dict[str, Any]
    ) -> Any:
        """Construct one governed owner per key with awaited rollback."""
        cache_key = self._cache_key(provider, config, False, True)
        with self._cache_lock:
            self._ensure_open()
            key_lock = self._key_locks.setdefault(cache_key, Lock())
            lifecycle = asyncio.create_task(
                self._run_governed_construction(key_lock, cache_key, provider, config)
            )
            self._active_governed.add(lifecycle)
        outcome = await await_terminal_task(lifecycle)
        return outcome.result()

    async def _run_governed_construction(
        self,
        key_lock: Lock,
        cache_key: str,
        provider: str,
        config: Dict[str, Any],
    ) -> Any:
        current = asyncio.current_task()
        assert current is not None
        try:
            result = await asyncio.to_thread(
                self._construct_governed, key_lock, cache_key, provider, config
            )
            return await self._finish_governed_construction(result)
        finally:
            with self._cache_lock:
                self._active_governed.discard(current)

    def _construct_governed(
        self,
        key_lock: Lock,
        cache_key: str,
        provider: str,
        config: Dict[str, Any],
    ) -> tuple[Any | None, ObservedResources | None, Exception | None]:
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
            except Exception as error:
                return None, owner, error
            with self._cache_lock:
                if self._closing or self._closed:
                    closing_error = LLMConfigurationError(
                        "LLM client factory is shut down"
                    )
                    return None, owner, closing_error
                self._clients[cache_key] = client
                self._owners.append(owner)
            return client, None, None

    async def _finish_governed_construction(
        self, result: tuple[Any | None, ObservedResources | None, Exception | None]
    ) -> Any:
        client, owner, error = result
        if owner is not None:
            try:
                await owner.aclose()
            except (
                asyncio.CancelledError,
                BaseExceptionGroup,
                Exception,
            ) as cleanup_error:
                assert error is not None
                raise BaseExceptionGroup(
                    "governed client construction and rollback failed",
                    [error, cleanup_error],
                )
        if error is not None:
            raise error
        return client

    @staticmethod
    def _cache_key(
        provider: str, config: Dict[str, Any], streaming: bool, governed: bool
    ) -> str:
        api_key_identity = sha256((config.get("api_key") or "").encode()).hexdigest()
        return (
            f"{provider}_{config.get('model')}_{api_key_identity}_"
            f"{config.get('max_tokens')}_{config.get('temperature', 0.7)!r}_{streaming}"
            + ("_single_dispatch" if governed else "")
        )

    def _ensure_open(self) -> None:
        if self._closing or self._closed:
            raise LLMConfigurationError("LLM client factory is shut down")

    async def shutdown(self) -> None:
        """Reject new clients and finish cleanup despite caller cancellation."""
        with self._cache_lock:
            if self._closed:
                return
            self._closing = True
            if self._shutdown_task is None:
                self._shutdown_task = asyncio.create_task(self._finish_shutdown())
            task = self._shutdown_task
        outcome = await await_terminal_task(task)
        outcome.result()

    async def _finish_shutdown(self) -> None:
        with self._cache_lock:
            active = list(self._active_governed)
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        with self._cache_lock:
            owners, self._owners = self._owners, []
            self._clients.clear()
        failures: list[BaseException] = []
        for owner in owners:
            try:
                await owner.aclose()
            except (asyncio.CancelledError, BaseExceptionGroup) as error:
                failures.append(error)
            except Exception as error:
                failures.append(error)
        with self._cache_lock:
            self._closed = True
        raise_cleanup_failures("governed client shutdown failed", failures)
