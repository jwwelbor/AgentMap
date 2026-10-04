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
    _transaction_lock = threading.Lock()
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
        with cls._transaction_lock:
            current = cls._current_container()
            if current is not None and not refresh:
                return
            if current is not None:
                cls._reject_sync_refresh_in_event_loop()
                detached = cls._detach_if_current(current)
                asyncio.run(cls._shutdown_container(detached))
            cls._install(config_file)

    @classmethod
    async def initialize_async(
        cls,
        startup: Callable[[Any, bool], None],
        *,
        refresh: bool = False,
        config_file: Optional[str] = None,
    ) -> None:
        """Own one serialized initialize, validate, and rollback transaction."""
        await cls._acquire_transaction()
        try:
            await cls._run_initialization_transaction(
                startup, refresh=refresh, config_file=config_file
            )
        finally:
            cls._transaction_lock.release()

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
            cls._raise_initialization_outcome(shutdown, None)
        worker_refresh = refresh and previous is None
        task = asyncio.create_task(
            asyncio.to_thread(
                cls._install_and_startup,
                startup,
                worker_refresh,
                config_file,
            )
        )
        outcome = await await_terminal_task(task)
        if outcome.task_error is None and outcome.caller_cancellation is None:
            return
        cleanup_error = await cls._rollback_candidate(previous, refresh)
        cls._raise_initialization_outcome(outcome, cleanup_error)

    @classmethod
    def _install_and_startup(
        cls,
        startup: Callable[[Any, bool], None],
        worker_refresh: bool,
        config_file: Optional[str],
    ) -> None:
        try:
            cls._initialize_in_transaction(
                refresh=worker_refresh, config_file=config_file
            )
            startup(cls.get_container(), worker_refresh)
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
        await cls._acquire_transaction()
        try:
            container = cls._detach_if_current(cls._current_container())
            await cls._shutdown_container(container)
        finally:
            cls._transaction_lock.release()

    @classmethod
    async def _acquire_transaction(cls) -> None:
        task = asyncio.create_task(asyncio.to_thread(cls._transaction_lock.acquire))
        outcome = await await_terminal_task(task)
        acquired = outcome.task_error is None and bool(outcome.value)
        if outcome.caller_cancellation is not None:
            if acquired:
                cls._transaction_lock.release()
            outcome.result()
        outcome.result()

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
    ) -> BaseException | None:
        if previous is not None and not refresh:
            return None
        candidate = cls._current_container()
        if candidate is None or candidate is previous:
            return None
        detached = cls._detach_if_current(candidate)
        outcome = await cls._await_shutdown(detached)
        return cls._outcome_error(outcome)

    @staticmethod
    def _outcome_error(outcome: TerminalTaskOutcome) -> BaseException | None:
        if outcome.caller_cancellation is not None and outcome.task_error is not None:
            return BaseExceptionGroup(
                "runtime rollback failed",
                [outcome.caller_cancellation, outcome.task_error],
            )
        return outcome.caller_cancellation or outcome.task_error

    @staticmethod
    def _raise_initialization_outcome(
        outcome: TerminalTaskOutcome, cleanup_error: BaseException | None
    ) -> None:
        original = outcome.caller_cancellation or outcome.task_error
        if original is None:
            return
        secondary: list[BaseException] = []
        if outcome.caller_cancellation is not None and outcome.task_error is not None:
            secondary.append(outcome.task_error)
        if cleanup_error is not None:
            secondary.append(cleanup_error)
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
        with cls._transaction_lock:
            with cls._lock:
                cls._is_initialized = False
                cls._container = None
