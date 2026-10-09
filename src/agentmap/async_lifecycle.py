"""Cancellation-safe waiting for lifecycle tasks that must reach a terminal state."""

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, TypeVar

_T = TypeVar("_T")


def _cancellation_count(task: asyncio.Task[Any] | None) -> int:
    """Return the caller's current cancellation-request count."""
    return task.cancelling() if task is not None else 0


def raise_cleanup_error_or_note(
    primary_error: BaseException | None,
    cleanup_error: BaseException,
    *,
    operation: str,
) -> None:
    """Raise cleanup-only failures or retain an active error with safe evidence."""
    if primary_error is None:
        raise cleanup_error
    primary_error.add_note(f"{operation} failed with {type(cleanup_error).__name__}")


def create_task_or_close(coroutine: Coroutine[Any, Any, _T]) -> asyncio.Task[_T]:
    """Close a coroutine when the loop cannot schedule its task."""
    try:
        return asyncio.create_task(coroutine)
    except BaseException as primary_error:
        try:
            coroutine.close()
        except BaseException as cleanup_error:
            raise_cleanup_error_or_note(
                primary_error,
                cleanup_error,
                operation="unscheduled coroutine close",
            )
        raise


def create_cleanup_task_or_close(
    coroutine_factory: Callable[[], Coroutine[Any, Any, _T]],
) -> tuple[asyncio.Task[_T], BaseException | None]:
    """Create an owned cleanup task, bypassing a rejecting task factory as fallback."""
    coroutine = coroutine_factory()
    try:
        return create_task_or_close(coroutine), None
    except BaseException as scheduling_error:
        try:
            fallback_coroutine = coroutine_factory()
        except BaseException as fallback_error:
            raise_cleanup_error_or_note(
                scheduling_error,
                fallback_error,
                operation="cleanup coroutine recreation",
            )
            raise scheduling_error.with_traceback(
                scheduling_error.__traceback__
            ) from None
        try:
            task = asyncio.Task(fallback_coroutine, loop=asyncio.get_running_loop())
        except BaseException as fallback_error:
            try:
                fallback_coroutine.close()
            except BaseException as close_error:
                raise_cleanup_error_or_note(
                    scheduling_error,
                    close_error,
                    operation="unscheduled cleanup coroutine close",
                )
            raise_cleanup_error_or_note(
                scheduling_error,
                fallback_error,
                operation="cleanup task fallback",
            )
            raise scheduling_error.with_traceback(
                scheduling_error.__traceback__
            ) from None
        return task, scheduling_error


@dataclass(frozen=True)
class TerminalTaskOutcome:
    """Separate a task result from cancellation requested by its caller."""

    value: Any = None
    task_error: BaseException | None = None
    caller_cancellation: asyncio.CancelledError | None = None

    def result(self) -> Any:
        """Return the value or raise both terminal dimensions losslessly."""
        if self.caller_cancellation is not None:
            if self.task_error is not None:
                raise self.caller_cancellation from self.task_error
            raise self.caller_cancellation
        if self.task_error is not None:
            raise self.task_error
        return self.value


async def await_terminal_task(task: asyncio.Future[Any]) -> TerminalTaskOutcome:
    """Wait through repeated caller cancellation without cancelling ``task``."""
    cancellation = None
    current = asyncio.current_task()
    cancellation_count = _cancellation_count(current)
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            current_count = _cancellation_count(current)
            if current_count > cancellation_count:
                cancellation = cancellation or error
                cancellation_count = current_count
            if task.done():
                break
        except BaseException:
            break
    try:
        value = task.result()
    except BaseException as error:
        return TerminalTaskOutcome(task_error=error, caller_cancellation=cancellation)
    return TerminalTaskOutcome(value=value, caller_cancellation=cancellation)


def raise_initialization_outcome(
    outcome: TerminalTaskOutcome, cleanup: TerminalTaskOutcome
) -> None:
    """Raise the primary startup failure while retaining cleanup failures."""
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
