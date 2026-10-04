"""Runtime initialization and container access."""

import asyncio

from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm.terminal_task import (
    TerminalTaskOutcome,
    await_terminal_task,
)


def _is_cache_initialized(container) -> bool:
    try:
        availability_cache_service = container.availability_cache_service()
        return availability_cache_service.is_initialized()
    except Exception:
        return False


def _refresh_cache(container) -> None:
    try:
        availability_cache_service = container.availability_cache_service()
        availability_cache_service.refresh_cache(container)
    except Exception as e:
        raise AgentMapNotInitialized(f"Failed to refresh provider cache: {e}")


def ensure_initialized(
    *, refresh: bool = False, config_file: str | None = None
) -> None:
    try:
        RuntimeManager.initialize(refresh=refresh, config_file=config_file)
        container = RuntimeManager.get_container()
        if refresh or not _is_cache_initialized(container):
            _refresh_cache(container)
        if not _is_cache_initialized(container):
            raise AgentMapNotInitialized("Cache file was not created after refresh")
    except Exception as e:
        if isinstance(e, AgentMapNotInitialized):
            raise
        raise AgentMapNotInitialized(f"Initialization failed: {e}")


async def ensure_initialized_async(
    *, refresh: bool = False, config_file: str | None = None
) -> None:
    """Initialize without blocking and own refresh or failed-startup cleanup.

    Old-runtime shutdown stays on the caller loop. Only synchronous DI and
    cache work crosses the thread boundary. A newly installed runtime is
    detached and shut down if later startup work fails or is cancelled.
    """
    was_initialized = RuntimeManager.is_initialized()
    worker_refresh = refresh
    if refresh and was_initialized:
        await RuntimeManager.shutdown()
        worker_refresh = False
    task = asyncio.create_task(
        asyncio.to_thread(
            ensure_initialized, refresh=worker_refresh, config_file=config_file
        )
    )
    outcome = await await_terminal_task(task)
    if outcome.task_error is None and outcome.caller_cancellation is None:
        return
    cleanup_error = await _rollback_started_runtime(was_initialized, refresh)
    _raise_initialization_outcome(outcome, cleanup_error)


async def _rollback_started_runtime(
    was_initialized: bool, refresh: bool
) -> BaseException | None:
    if was_initialized and not refresh:
        return None
    if not RuntimeManager.is_initialized():
        return None
    cleanup = asyncio.create_task(RuntimeManager.shutdown())
    outcome = await await_terminal_task(cleanup)
    if outcome.caller_cancellation is not None and outcome.task_error is not None:
        return BaseExceptionGroup(
            "runtime rollback failed",
            [outcome.caller_cancellation, outcome.task_error],
        )
    if outcome.caller_cancellation is not None:
        return outcome.caller_cancellation
    return outcome.task_error


def _raise_initialization_outcome(
    outcome: TerminalTaskOutcome, cleanup_error: BaseException | None
) -> None:
    original = outcome.caller_cancellation or outcome.task_error
    assert original is not None
    secondary = []
    if outcome.caller_cancellation is not None and outcome.task_error is not None:
        secondary.append(outcome.task_error)
    if cleanup_error is not None:
        secondary.append(cleanup_error)
    if isinstance(original, asyncio.CancelledError):
        cause = (
            BaseExceptionGroup("runtime initialization failed", secondary)
            if secondary
            else None
        )
        raise original from cause
    if secondary:
        raise BaseExceptionGroup(
            "runtime initialization and rollback failed", [original, *secondary]
        )
    raise original


def get_container():
    return RuntimeManager.get_container()


async def shutdown_runtime() -> None:
    """Await resource cleanup and detach the process runtime container."""
    await RuntimeManager.shutdown()
