"""
Runtime State Management

This module provides thread-safe runtime state management for AgentMap,
implementing a singleton pattern for DI container lifecycle management.
"""

import asyncio
import threading
from typing import Any, Callable, Optional

from agentmap.async_lifecycle import TerminalTaskOutcome, await_terminal_task
from agentmap.di import initialize_di
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized


class RuntimeManager:
    """
    Thread-safe, idempotent runtime container manager.

    This class owns the DI container for the process and exposes simple helpers
    for initialization, access, and lifecycle management. Uses a singleton pattern
    with thread safety to ensure only one container instance exists per process.
    """

    _lock = threading.RLock()
    _transaction_condition = threading.Condition()
    _transaction_owner: object | None = None
    _transaction_async_waiters: set[tuple[Any, Any]] = set()
    _is_initialized = False
    _container = None

    @classmethod
    def initialize(
        cls, *, refresh: bool = False, config_file: Optional[str] = None
    ) -> None:
        """
        Initialize the DI container once for the process.

        This method is idempotent - calling it multiple times won't reinitialize
        unless refresh=True is explicitly set. Thread-safe using RLock.

        Args:
            refresh: Rebuild the container even if we already initialized.
            config_file: Optional path to config file for DI bootstrap.

        Raises:
            AgentMapNotInitialized: If initialization fails for any reason.
        """
        token = cls._acquire_sync_transaction()
        try:
            current = cls._current_container()
            if current is not None and not refresh:
                return
            if current is not None:
                cls._reject_sync_refresh_in_event_loop()
                detached = cls._detach_if_current(current)
                asyncio.run(cls._shutdown_container(detached))
            cls._install(config_file)
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
        previous = cls._current_container()
        if previous is not None and refresh:
            detached = cls._detach_if_current(previous)
            shutdown = await cls._await_shutdown(detached)
            cls._raise_initialization_outcome(shutdown, TerminalTaskOutcome())
        install_refresh = refresh and previous is None
        task = asyncio.create_task(
            asyncio.to_thread(
                cls._install_and_startup,
                startup,
                install_refresh,
                refresh,
                config_file,
            )
        )
        outcome = await await_terminal_task(task)
        if outcome.task_error is None and outcome.caller_cancellation is None:
            return
        cleanup = await cls._rollback_candidate(previous, refresh)
        cls._raise_initialization_outcome(outcome, cleanup)

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
            startup(cls.get_container(), cache_refresh)
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
        try:
            container = initialize_di(config_file)
        except Exception as error:
            with cls._lock:
                cls._is_initialized = False
                cls._container = None
            raise AgentMapNotInitialized(f"Initialization failed: {error}") from error
        with cls._lock:
            cls._container = container
            cls._is_initialized = True

    @classmethod
    async def shutdown(cls) -> None:
        """Detach the runtime and await its LLM resource owner."""
        token = await cls._acquire_async_transaction()
        try:
            container = cls._detach_if_current(cls._current_container())
            await cls._shutdown_container(container)
        finally:
            cls._release_transaction(token)

    @classmethod
    async def _acquire_async_transaction(cls) -> object:
        loop = asyncio.get_running_loop()
        while True:
            with cls._transaction_condition:
                if cls._transaction_owner is None:
                    token = object()
                    cls._transaction_owner = token
                    return token
                future = loop.create_future()
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
    def _wake_transaction_waiter(future: Any) -> None:
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
    async def _shutdown_container(cls, container: Any | None) -> None:
        if container is not None:
            await container.llm_service().shutdown()

    @classmethod
    async def _await_shutdown(cls, container: Any | None) -> TerminalTaskOutcome:
        if container is None:
            return TerminalTaskOutcome()
        task = asyncio.create_task(cls._shutdown_container(container))
        return await await_terminal_task(task)

    @classmethod
    async def _rollback_candidate(
        cls, previous: Any | None, refresh: bool
    ) -> TerminalTaskOutcome:
        if previous is not None and not refresh:
            return TerminalTaskOutcome()
        candidate = cls._current_container()
        if candidate is None or candidate is previous:
            return TerminalTaskOutcome()
        detached = cls._detach_if_current(candidate)
        return await cls._await_shutdown(detached)

    @staticmethod
    def _raise_initialization_outcome(
        outcome: TerminalTaskOutcome, cleanup: TerminalTaskOutcome
    ) -> None:
        original = (
            outcome.caller_cancellation
            or cleanup.caller_cancellation
            or outcome.task_error
            or cleanup.task_error
        )
        if original is None:
            return
        terminal = (
            outcome.caller_cancellation,
            outcome.task_error,
            cleanup.caller_cancellation,
            cleanup.task_error,
        )
        secondary = [
            error for error in terminal if error is not None and error is not original
        ]
        if len(secondary) == 1:
            raise original from secondary[0]
        if secondary:
            raise original from BaseExceptionGroup(
                "runtime initialization cleanup failed", secondary
            )
        raise original

    @classmethod
    def _current_container(cls) -> Any | None:
        with cls._lock:
            if not cls._is_initialized:
                return None
            return cls._container

    @classmethod
    def _detach_if_current(cls, expected: Any | None) -> Any | None:
        with cls._lock:
            if expected is None or cls._container is not expected:
                return None
            container = cls._container
            cls._is_initialized = False
            cls._container = None
            return container

    @staticmethod
    def _reject_sync_refresh_in_event_loop() -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise AgentMapNotInitialized(
            "Runtime refresh from an event loop requires ensure_initialized_async()"
        )

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
                cls._is_initialized = False
                cls._container = None
        finally:
            cls._release_transaction(token)
