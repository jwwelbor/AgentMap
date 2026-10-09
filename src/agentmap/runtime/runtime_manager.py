"""
Runtime State Management

This module provides thread-safe runtime state management for AgentMap,
implementing a singleton pattern for DI container lifecycle management.
"""

import asyncio
import contextvars
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

import agentmap.async_lifecycle as async_lifecycle
from agentmap.di import initialize_di
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.cleanup_mixin import RuntimeCleanupMixin
from agentmap.runtime.lifespan_mixin import (
    RuntimeLifespanMixin,
    canonical_config_path,
    effective_config_file,
)

AsyncTransactionWaiter = tuple[asyncio.AbstractEventLoop, asyncio.Future[None]]


class RuntimeManager(RuntimeLifespanMixin, RuntimeCleanupMixin):
    """
    Thread-safe, idempotent runtime container manager.

    This class owns the DI container for the process and exposes simple helpers
    for initialization, access, and lifecycle management. Uses a singleton pattern
    with thread safety to ensure only one container instance exists per process.
    """

    _lock = threading.RLock()
    _lifecycle_executor = ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="agentmap-runtime-lifecycle"
    )
    _transaction_condition = threading.Condition()
    _transaction_owner: object | None = None
    _transaction_async_waiters: set[AsyncTransactionWaiter] = set()
    _is_initialized = False
    _container = None
    _runtime_config_file = None
    _pending_cleanup_container = None
    _pending_cleanup_loop = None

    @classmethod
    def initialize(
        cls,
        *,
        refresh: bool = False,
        config_file: Optional[str] = None,
        startup: Callable[[Any, bool], None] | None = None,
    ) -> None:
        """
        Initialize and optionally validate the DI container in one transaction.

        This method is idempotent - calling it multiple times won't reinitialize
        unless refresh=True is explicitly set. Thread-safe using RLock.

        Args:
            refresh: Rebuild the container even if we already initialized.
            config_file: Optional path to config file for DI bootstrap.
            startup: Optional validation callback run before the transaction ends.

        Raises:
            AgentMapNotInitialized: If initialization fails for any reason.
        """
        token = cls._acquire_sync_transaction()
        try:
            if cls._pending_cleanup() is not None:
                raise AgentMapNotInitialized(
                    "Runtime cleanup is pending; complete shutdown before initialization"
                )
            current = cls._current_container()
            if refresh and cls._lifespan_tokens:
                raise AgentMapNotInitialized(
                    "Cannot refresh a runtime with active HTTP lifespans"
                )
            if current is not None and not refresh:
                cls._run_sync_startup(startup, current, refresh)
                return
            if current is not None:
                cls._shutdown_for_sync_refresh(current)
            cls._install(config_file)
            cls._run_sync_startup(startup, current, refresh)
        finally:
            cls._release_transaction(token)

    @classmethod
    async def initialize_async(
        cls,
        startup: Callable[[Any, bool], None],
        *,
        refresh: bool = False,
        config_file: Optional[str] = None,
    ) -> None:
        """Own one serialized initialize, validate, and rollback transaction."""
        token = await cls._acquire_async_transaction()
        try:
            if refresh and cls._lifespan_tokens:
                raise AgentMapNotInitialized(
                    "Cannot refresh a runtime with active HTTP lifespans"
                )
            await cls._run_initialization_transaction(
                startup, refresh=refresh, config_file=config_file
            )
        finally:
            cls._release_transaction(token)

    @classmethod
    async def _run_initialization_transaction(
        cls,
        startup: Callable[[Any, bool], None],
        *,
        refresh: bool,
        config_file: Optional[str],
    ) -> None:
        await cls._retry_pending_cleanup()
        previous = cls._current_container()
        if previous is not None and refresh:
            cls._prepare_container_shutdown(previous)
            pending = cls._adopt_pending_cleanup(
                previous, owner_loop=asyncio.get_running_loop()
            )
            shutdown = await cls._await_shutdown(pending)
            if shutdown.task_error is None:
                cls._clear_pending_cleanup(pending)
            async_lifecycle.raise_initialization_outcome(
                shutdown, async_lifecycle.TerminalTaskOutcome()
            )
        install_refresh = refresh and previous is None
        task = async_lifecycle.create_task_or_close(
            cls._run_install_and_startup(startup, install_refresh, refresh, config_file)
        )
        outcome = await async_lifecycle.await_terminal_task(task)
        if outcome.task_error is None and outcome.caller_cancellation is None:
            cls._publish_initializing_container()
            return
        cleanup = await cls._rollback_candidate(previous, refresh)
        async_lifecycle.raise_initialization_outcome(outcome, cleanup)

    @classmethod
    async def _run_install_and_startup(
        cls,
        startup: Callable[[Any, bool], None],
        install_refresh: bool,
        cache_refresh: bool,
        config_file: Optional[str],
    ) -> None:
        """Run blocking lifecycle work outside the shared default executor."""
        loop = asyncio.get_running_loop()
        context = contextvars.copy_context()
        await loop.run_in_executor(
            cls._lifecycle_executor,
            context.run,
            cls._install_and_startup,
            startup,
            install_refresh,
            cache_refresh,
            config_file,
        )

    @classmethod
    def _install_and_startup(
        cls,
        startup: Callable[[Any, bool], None],
        install_refresh: bool,
        cache_refresh: bool,
        config_file: Optional[str],
    ) -> None:
        try:
            cls._initialize_in_transaction(
                refresh=install_refresh, config_file=config_file
            )
            candidate = cls._candidate_container()
            if candidate is None:
                raise AgentMapNotInitialized(
                    "Runtime initialization completed without a candidate container"
                )
            startup(candidate, cache_refresh)
        except AgentMapNotInitialized:
            raise
        except Exception as error:
            raise AgentMapNotInitialized(f"Initialization failed: {error}") from error

    @classmethod
    def _initialize_in_transaction(
        cls, *, refresh: bool, config_file: Optional[str]
    ) -> None:
        if cls._current_container() is not None and not refresh:
            return
        cls._install(config_file)

    @classmethod
    def _install(cls, config_file: Optional[str]) -> None:
        with cls._lock:
            if cls._initializing_container is not None:
                raise AgentMapNotInitialized("A prior startup candidate awaits cleanup")
        try:
            container = initialize_di(config_file)
            try:
                installed_config = canonical_config_path(container.config.path())
            except (AttributeError, TypeError):
                installed_config = effective_config_file(config_file)
        except Exception as error:
            raise AgentMapNotInitialized(f"Initialization failed: {error}") from error
        with cls._lock:
            if cls._initializing_container is not None:
                raise AgentMapNotInitialized(
                    "A runtime startup candidate is already being validated"
                )
            cls._initializing_container = container
            cls._initializing_config_file = installed_config

    @classmethod
    async def _acquire_async_transaction(cls) -> object:
        loop = asyncio.get_running_loop()
        while True:
            with cls._transaction_condition:
                if cls._transaction_owner is None:
                    token = object()
                    cls._transaction_owner = token
                    return token
                future: asyncio.Future[None] = loop.create_future()
                waiter = (loop, future)
                cls._transaction_async_waiters.add(waiter)
            try:
                await future
            finally:
                with cls._transaction_condition:
                    cls._transaction_async_waiters.discard(waiter)

    @classmethod
    def _acquire_sync_transaction(cls) -> object:
        in_event_loop = cls._in_event_loop()
        with cls._transaction_condition:
            if in_event_loop and cls._transaction_owner is not None:
                raise AgentMapNotInitialized(
                    "Synchronous runtime initialization cannot wait for an active "
                    "async transaction; await ensure_initialized_async()"
                )
            while cls._transaction_owner is not None:
                cls._transaction_condition.wait()
            token = object()
            cls._transaction_owner = token
            return token

    @classmethod
    def _release_transaction(cls, token: object) -> None:
        with cls._transaction_condition:
            if cls._transaction_owner is not token:
                raise RuntimeError("Runtime transaction owner mismatch")
            cls._transaction_owner = None
            cls._transaction_condition.notify_all()
            waiters = tuple(cls._transaction_async_waiters)
        for loop, future in waiters:
            try:
                loop.call_soon_threadsafe(cls._wake_transaction_waiter, future)
            except RuntimeError:
                continue

    @staticmethod
    def _wake_transaction_waiter(future: asyncio.Future[None]) -> None:
        if not future.done():
            future.set_result(None)

    @staticmethod
    def _in_event_loop() -> bool:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return False
        return True

    @classmethod
    def is_initialized(cls) -> bool:
        """
        Return True if the runtime has been initialized.

        Returns:
            bool: True if container is initialized and ready for use.
        """
        return cls._current_container() is not None

    @classmethod
    def get_container(cls):
        """
        Return the DI container or raise if uninitialized.

        Returns:
            ApplicationContainer: The initialized DI container.

        Raises:
            AgentMapNotInitialized: If runtime not initialized or container is None.
        """
        container = cls._current_container()
        if container is None:
            if cls._pending_cleanup() is not None:
                raise AgentMapNotInitialized(
                    "Runtime cleanup is pending; container access is unavailable"
                )
            raise AgentMapNotInitialized(
                "Runtime not initialized. Call RuntimeManager.initialize() first."
            )
        return container

    @classmethod
    def reset(cls) -> None:
        """
        Reset runtime state (primarily for tests).

        This method clears the initialization state and container reference,
        allowing for clean reinitialization. Thread-safe using RLock.
        """
        token = cls._acquire_sync_transaction()
        try:
            with cls._lock:
                if cls._pending_cleanup_container is not None:
                    raise AgentMapNotInitialized(
                        "Cannot reset while runtime cleanup is pending"
                    )
                if (
                    cls._container is not None
                    or cls._initializing_container is not None
                    or cls._lifespan_tokens
                    or cls._lifespan_owned
                    or cls._lifespan_container is not None
                    or cls._lifespan_loop is not None
                ):
                    raise AgentMapNotInitialized(
                        "Cannot reset while runtime or lifespan ownership is active; "
                        "release lifespans and await shutdown first"
                    )
                cls._is_initialized = False
                cls._container = None
                cls._runtime_config_file = None
                cls._initializing_container = None
                cls._initializing_config_file = None
                cls._pending_cleanup_loop = None
                cls._lifespan_tokens.clear()
                cls._lifespan_owned = False
                cls._lifespan_container = None
                cls._lifespan_loop = None
        finally:
            cls._release_transaction(token)
