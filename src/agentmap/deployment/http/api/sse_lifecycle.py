"""Cleanup ownership for the HTTP workflow event stream."""

import asyncio
from typing import Any, AsyncGenerator, Optional

from agentmap.async_lifecycle import (
    await_terminal_task,
    create_cleanup_task_or_close,
    raise_cleanup_error_or_note,
)


def _merge_cleanup_error(
    current: BaseException | None, error: BaseException, *, operation: str
) -> BaseException:
    if current is None:
        return error
    raise_cleanup_error_or_note(current, error, operation=operation)
    return current


def _finish_sse_cleanup(
    primary_error: BaseException | None,
    cleanup_error: BaseException | None,
    caller_cancellation: asyncio.CancelledError | None,
) -> None:
    if primary_error is not None:
        if caller_cancellation is not None and caller_cancellation is not primary_error:
            primary_error.add_note("SSE cleanup observed caller cancellation")
        if cleanup_error is not None:
            raise_cleanup_error_or_note(
                primary_error, cleanup_error, operation="SSE upstream cleanup"
            )
        return
    if caller_cancellation is not None:
        if cleanup_error is not None:
            raise_cleanup_error_or_note(
                caller_cancellation, cleanup_error, operation="SSE upstream cleanup"
            )
        raise caller_cancellation
    if cleanup_error is not None:
        raise cleanup_error


async def _close_upstream_and_release_slot(
    upstream: AsyncGenerator[Any, None],
    semaphore: Optional[asyncio.Semaphore],
    cleanup_error: BaseException | None,
    caller_cancellation: asyncio.CancelledError | None,
    current_task: asyncio.Task[Any] | None,
    initial_cancellation_count: int,
) -> tuple[BaseException | None, asyncio.CancelledError | None]:
    cleanup_error, caller_cancellation = await _close_upstream(
        upstream,
        cleanup_error,
        caller_cancellation,
        current_task,
        initial_cancellation_count,
    )
    cleanup_error = _release_semaphore_slot(semaphore, cleanup_error)
    if caller_cancellation is None and current_task is not None:
        if current_task.cancelling() > initial_cancellation_count:
            caller_cancellation = asyncio.CancelledError()
    return cleanup_error, caller_cancellation


async def _close_upstream(
    upstream: AsyncGenerator[Any, None],
    cleanup_error: BaseException | None,
    caller_cancellation: asyncio.CancelledError | None,
    current_task: asyncio.Task[Any] | None,
    initial_cancellation_count: int,
) -> tuple[BaseException | None, asyncio.CancelledError | None]:
    try:
        close_task, scheduling_error = create_cleanup_task_or_close(upstream.aclose)
        if scheduling_error is not None:
            cleanup_error = _merge_cleanup_error(
                cleanup_error,
                scheduling_error,
                operation="SSE upstream close scheduling",
            )
        close_outcome = await await_terminal_task(close_task)
        if close_outcome.caller_cancellation is not None:
            caller_cancellation = (
                caller_cancellation or close_outcome.caller_cancellation
            )
        if close_outcome.task_error is not None:
            cleanup_error, caller_cancellation = _record_upstream_close_error(
                close_outcome.task_error,
                cleanup_error,
                caller_cancellation,
                current_task,
                initial_cancellation_count,
            )
    except BaseException as error:
        cleanup_error, caller_cancellation = _record_upstream_close_error(
            error,
            cleanup_error,
            caller_cancellation,
            current_task,
            initial_cancellation_count,
        )
    return cleanup_error, caller_cancellation


def _record_upstream_close_error(
    error: BaseException,
    cleanup_error: BaseException | None,
    caller_cancellation: asyncio.CancelledError | None,
    current_task: asyncio.Task[Any] | None,
    initial_cancellation_count: int,
) -> tuple[BaseException | None, asyncio.CancelledError | None]:
    if (
        isinstance(error, asyncio.CancelledError)
        and current_task is not None
        and current_task.cancelling() > initial_cancellation_count
    ):
        caller_cancellation = caller_cancellation or error
    else:
        cleanup_error = _merge_cleanup_error(
            cleanup_error, error, operation="SSE upstream close"
        )
    return cleanup_error, caller_cancellation


def _release_semaphore_slot(
    semaphore: Optional[asyncio.Semaphore], cleanup_error: BaseException | None
) -> BaseException | None:
    if semaphore is not None:
        try:
            semaphore.release()
        except BaseException as error:
            cleanup_error = _merge_cleanup_error(
                cleanup_error, error, operation="SSE semaphore release"
            )
    return cleanup_error


async def aclose_upstream_and_release(
    pending: "Optional[asyncio.Future[Any]]",
    upstream: AsyncGenerator[Any, None],
    semaphore: Optional[asyncio.Semaphore],
    primary_error: BaseException | None = None,
) -> None:
    """Close an upstream stream and release its concurrency slot.

    Cancel and await an in-flight ``__anext__`` before closing ``upstream`` so
    the route's single finalizer runs. Always attempt the semaphore release,
    even when upstream close fails.
    """
    current_task = asyncio.current_task()
    initial_cancellation_count = (
        current_task.cancelling() if current_task is not None else 0
    )
    cleanup_error = None
    caller_cancellation = None
    if pending is not None:
        if not pending.done():
            pending.cancel()
        outcome = await await_terminal_task(pending)
        caller_cancellation = outcome.caller_cancellation
        if (
            outcome.task_error is not None
            and outcome.task_error is not primary_error
            and not isinstance(
                outcome.task_error, (asyncio.CancelledError, StopAsyncIteration)
            )
        ):
            cleanup_error = _merge_cleanup_error(
                cleanup_error,
                outcome.task_error,
                operation="SSE pending event cleanup",
            )

    cleanup_error, caller_cancellation = await _close_upstream_and_release_slot(
        upstream,
        semaphore,
        cleanup_error,
        caller_cancellation,
        current_task,
        initial_cancellation_count,
    )
    _finish_sse_cleanup(primary_error, cleanup_error, caller_cancellation)
