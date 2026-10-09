"""Span cleanup and retry-safe telemetry boundaries for LLM calls."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Awaitable, Callable, TypeVar

from agentmap.async_lifecycle import raise_cleanup_error_or_note

_T = TypeVar("_T")
_ErrorTypes = tuple[type[BaseException], ...]


@contextmanager
def span_preserving_primary(span_context: Any, *, operation: str) -> Iterator[Any]:
    """Keep a core failure primary when telemetry span teardown also fails."""
    span = span_context.__enter__()
    try:
        yield span
    except BaseException as primary_error:
        suppressed = False
        try:
            suppressed = span_context.__exit__(
                type(primary_error),
                primary_error,
                primary_error.__traceback__,
            )
        except BaseException as cleanup_error:
            raise_cleanup_error_or_note(
                primary_error, cleanup_error, operation=operation
            )
        if not suppressed:
            raise
    else:
        span_context.__exit__(None, None, None)


def close_span_preserving_primary(
    span_context: Any, primary_error: BaseException | None, *, operation: str
) -> None:
    """Close a manually managed span without replacing an active failure."""
    try:
        span_context.__exit__(None, None, None)
    except BaseException as cleanup_error:
        raise_cleanup_error_or_note(primary_error, cleanup_error, operation=operation)


def call_with_telemetry(
    telemetry_service: Any,
    span_name: str,
    initial_attributes: dict[str, Any],
    call_core: Callable[[], _T],
    capture_content: Callable[[Any, _T], None],
    set_span_status_ok: Callable[[Any], None],
    record_exception: Callable[[Any, Exception], None],
    logger: Any,
    fallback_errors: _ErrorTypes,
    fallback: Callable[[], _T],
) -> _T:
    """Run a sync call once and fall back only when span setup fails."""
    core_started = False
    core_completed = False
    result: _T | None = None
    try:
        with span_preserving_primary(
            telemetry_service.start_span(span_name, attributes=initial_attributes),
            operation="LLM telemetry span exit",
        ) as span:
            try:
                core_started = True
                result = call_core()
                core_completed = True
                capture_content(span, result)
                set_span_status_ok(span)
                return result
            except Exception as error:
                record_exception(span, error)
                raise
    except Exception as outer_error:
        if core_completed:
            logger.warning(f"Telemetry error after provider execution: {outer_error}")
            assert result is not None
            return result
        if core_started or isinstance(outer_error, fallback_errors):
            raise
        logger.warning(
            f"Telemetry error, executing without instrumentation: {outer_error}"
        )
        return fallback()


async def call_with_telemetry_async(
    telemetry_service: Any,
    span_name: str,
    initial_attributes: dict[str, Any],
    call_core: Callable[[], Awaitable[_T]],
    capture_content: Callable[[Any, _T], None],
    set_span_status_ok: Callable[[Any], None],
    record_exception: Callable[[Any, Exception], None],
    logger: Any,
    fallback_errors: _ErrorTypes,
    fallback: Callable[[], Awaitable[_T]],
) -> _T:
    """Run an async call once and fall back only when span setup fails."""
    core_started = False
    core_completed = False
    result: _T | None = None
    try:
        with span_preserving_primary(
            telemetry_service.start_span(span_name, attributes=initial_attributes),
            operation="LLM telemetry span exit",
        ) as span:
            try:
                core_started = True
                result = await call_core()
                core_completed = True
                capture_content(span, result)
                set_span_status_ok(span)
                return result
            except Exception as error:
                record_exception(span, error)
                raise
    except Exception as outer_error:
        if core_completed:
            logger.warning(f"Telemetry error after provider execution: {outer_error}")
            assert result is not None
            return result
        if core_started or isinstance(outer_error, fallback_errors):
            raise
        logger.warning(
            f"Telemetry error, executing without instrumentation: {outer_error}"
        )
        return await fallback()
