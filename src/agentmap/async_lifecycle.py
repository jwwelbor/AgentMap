"""Cancellation-safe waiting for lifecycle tasks that must reach a terminal state."""

import asyncio
from dataclasses import dataclass
from typing import Any


def _cancellation_count(task: asyncio.Task[Any] | None) -> int:
    """Return the caller's current cancellation-request count."""
    return task.cancelling() if task is not None else 0


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


async def await_terminal_task(task: asyncio.Task[Any]) -> TerminalTaskOutcome:
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
        except (BaseExceptionGroup, Exception):
            break
    try:
        value = task.result()
    except (asyncio.CancelledError, BaseExceptionGroup, Exception) as error:
        return TerminalTaskOutcome(task_error=error, caller_cancellation=cancellation)
    return TerminalTaskOutcome(value=value, caller_cancellation=cancellation)


def raise_cleanup_failures(message: str, failures: list[BaseException]) -> None:
    """Retain mixed outcomes while preserving a lone cancellation's type."""
    if len(failures) == 1 and isinstance(failures[0], asyncio.CancelledError):
        raise failures[0]
    if failures:
        raise BaseExceptionGroup(message, failures)
