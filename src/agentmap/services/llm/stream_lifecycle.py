"""Terminal cleanup behavior for governed LLM response streams."""

from collections.abc import AsyncIterator, Callable
from typing import Any, Dict, List, Optional

from agentmap.async_lifecycle import (
    TerminalTaskOutcome,
    await_terminal_task,
    create_cleanup_task_or_close,
    raise_cleanup_error_or_note,
)
from agentmap.exceptions import AttemptLifecycleRefusal, LLMConfigurationError
from agentmap.services.llm._budget_guard_refusal import BudgetGuardRefusal
from agentmap.services.llm.attempt_lifecycle import clear_attempt_lifecycle
from agentmap.services.llm.invocation_lease import clear_governed_use_lease


async def close_async_stream_preserving_primary(
    stream: Any, primary_error: BaseException | None
) -> None:
    """Close a provider stream without replacing its active failure."""
    with clear_attempt_lifecycle(), clear_governed_use_lease():
        try:
            close_task, scheduling_error = create_cleanup_task_or_close(stream.aclose)
        except BaseException as cleanup_error:
            raise_cleanup_error_or_note(
                primary_error,
                cleanup_error,
                operation="LLM async stream close",
            )
            return
        outcome = await await_terminal_task(close_task)
        _raise_stream_close_outcome(primary_error, scheduling_error, outcome)


async def isolated_llm_stream(
    stream_factory: Callable[[], AsyncIterator[Any]],
) -> AsyncIterator[Any]:
    """Drain a stream without inherited invocation context and always close it."""
    with clear_attempt_lifecycle(), clear_governed_use_lease():
        stream = stream_factory()

    async def next_chunk() -> Any:
        with clear_attempt_lifecycle(), clear_governed_use_lease():
            return await stream.__anext__()

    async def isolated_chunks() -> AsyncIterator[Any]:
        while True:
            try:
                yield await next_chunk()
            except StopAsyncIteration:
                return

    primary_error: Optional[BaseException] = None
    try:
        async for chunk in isolated_chunks():
            yield chunk
    except (BudgetGuardRefusal, AttemptLifecycleRefusal) as refusal:
        primary_error = refusal.original
        raise refusal.original
    except BaseException as error:
        primary_error = error
        raise
    finally:
        await close_async_stream_preserving_primary(stream, primary_error)


def create_llm_stream_async(
    call_args: tuple[
        List[Any],
        Optional[str],
        Optional[str],
        Optional[float],
        Optional[Dict[str, Any]],
    ],
    cache_system_prompt: bool,
    kwargs: Dict[str, Any],
    telemetry_stream: Callable[..., Any],
    core_stream: Callable[..., Any],
    telemetry_enabled: bool,
) -> Any:
    """Select the stream path after rejecting governed options on this API."""
    if "attempt_lifecycle" in kwargs:
        raise LLMConfigurationError(
            "attempt_lifecycle is supported only by call_llm_async"
        )
    kwargs["cache_system_prompt"] = cache_system_prompt
    stream_method = telemetry_stream if telemetry_enabled else core_stream
    return stream_method(*call_args, **kwargs)


def _raise_stream_close_outcome(
    primary_error: BaseException | None,
    scheduling_error: BaseException | None,
    outcome: TerminalTaskOutcome,
) -> None:
    if primary_error is not None:
        for cleanup_error, operation in (
            (scheduling_error, "LLM async stream close scheduling"),
            (outcome.task_error, "LLM async stream close"),
            (outcome.caller_cancellation, "LLM async stream close cancellation"),
        ):
            if cleanup_error is not None:
                raise_cleanup_error_or_note(
                    primary_error, cleanup_error, operation=operation
                )
        return
    if outcome.caller_cancellation is not None:
        for cleanup_error, operation in (
            (scheduling_error, "LLM async stream close scheduling"),
            (outcome.task_error, "LLM async stream close"),
        ):
            if cleanup_error is not None:
                raise_cleanup_error_or_note(
                    outcome.caller_cancellation, cleanup_error, operation=operation
                )
        raise outcome.caller_cancellation from None
    _raise_stream_close_error(scheduling_error, outcome.task_error)


def _raise_stream_close_error(
    scheduling_error: BaseException | None, task_error: BaseException | None
) -> None:
    if scheduling_error is not None:
        if task_error is not None:
            raise_cleanup_error_or_note(
                scheduling_error, task_error, operation="LLM async stream close"
            )
        raise scheduling_error
    if task_error is not None:
        raise task_error
