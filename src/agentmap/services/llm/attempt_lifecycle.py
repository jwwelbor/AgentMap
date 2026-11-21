"""Mandatory host hooks for an opt-in physical-attempt lifecycle.

The ContextVar belongs to an invocation, never the APP-scoped service. Host
exceptions cross retry/fallback/telemetry handlers as control flow, not as
provider failures. No host exception message is sent to telemetry.
"""

import asyncio
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Awaitable, Callable, Optional, Tuple, TypeVar

from agentmap.exceptions import (
    AttemptLifecycleRefusal,
    LLMLifecycleCleanupError,
    LLMTimeoutError,
)
from agentmap.models.llm_attempt import LLMAttemptDescription, LLMAttemptOutcome
from agentmap.models.llm_execution import LLMResponse
from agentmap.services.llm.attempt_lifecycle_evidence import (
    AttemptAccumulator,
    _prefer_attempt_failure,
    accounting_refusal,
    collect_evidence,
    evaluate_attempt_response,
    propagate_finalized_failure,
    terminal_outcome,
)
from agentmap.services.llm.invocation_lease import governed_use_lease
from agentmap.services.llm.response_observer import (
    ResponseCollector,
    response_collector,
)
from agentmap.services.protocols.service_protocols import LLMAttemptLifecycleProtocol


class CompositeAttemptLifecycle:
    """Fan out one attempt lifecycle to each configured host observer."""

    def __init__(self, lifecycles: tuple[LLMAttemptLifecycleProtocol, ...]):
        self._lifecycles = lifecycles
        self._pending: dict[str, tuple[str, ...]] = {}
        self._lock = Lock()

    async def before_attempt(self, description: LLMAttemptDescription) -> str:
        attempt_ids = []
        for lifecycle in self._lifecycles:
            try:
                attempt_ids.append(await lifecycle.before_attempt(description))
            except BaseException as error:
                for admitted, admitted_id in zip(self._lifecycles, attempt_ids):
                    try:
                        await admitted.after_attempt(
                            admitted_id,
                            LLMAttemptOutcome(
                                classification="provider_error",
                                error_type=type(error).__name__,
                            ),
                        )
                    except BaseException:
                        pass
                raise
        composite_id = uuid.uuid4().hex
        with self._lock:
            self._pending[composite_id] = tuple(attempt_ids)
        return composite_id

    async def after_attempt(self, attempt_id: str, outcome: LLMAttemptOutcome) -> None:
        with self._lock:
            attempt_ids = self._pending.pop(attempt_id, ())
        failures = []
        for lifecycle, attempt_id in zip(self._lifecycles, attempt_ids):
            try:
                await lifecycle.after_attempt(attempt_id, outcome)
            except BaseException as error:
                failures.append(error)
        if failures:
            raise failures[0]


def compose_attempt_lifecycles(
    first: Optional[LLMAttemptLifecycleProtocol],
    second: Optional[LLMAttemptLifecycleProtocol],
) -> Optional[LLMAttemptLifecycleProtocol]:
    """Combine distinct lifecycle hooks while preserving their order."""
    if first is None:
        return second
    if second is None or first is second:
        return first
    return CompositeAttemptLifecycle((first, second))


attempt_lifecycle: ContextVar[Optional[LLMAttemptLifecycleProtocol]] = ContextVar(
    "agentmap_attempt_lifecycle", default=None
)
file_attempt_logger: ContextVar[Optional[LLMAttemptLifecycleProtocol]] = ContextVar(
    "agentmap_file_attempt_logger", default=None
)
_T = TypeVar("_T")


async def run_governed_invocation(
    lifecycle: Optional[LLMAttemptLifecycleProtocol],
    client_factory: Any,
    invoke: Callable[[], Awaitable[_T]],
) -> _T:
    """Scope attempt context and factory ownership to one async call."""
    invocation_lease = (
        client_factory.begin_governed_invocation() if lifecycle is not None else None
    )
    lease_token = governed_use_lease.set(invocation_lease)
    token = attempt_lifecycle.set(lifecycle)
    try:
        return await invoke()
    finally:
        try:
            attempt_lifecycle.reset(token)
        finally:
            try:
                governed_use_lease.reset(lease_token)
            finally:
                if invocation_lease is not None:
                    invocation_lease.release()


async def get_async_client(factory: Any, provider: str, config: dict[str, Any]) -> Any:
    """Acquire the appropriate client and classify terminal lifecycle refusal."""
    try:
        if attempt_lifecycle.get() is not None:
            return await factory.get_or_create_governed_client(provider, config)
        if file_attempt_logger.get() is not None:
            return factory.get_or_create_client(provider, config, single_dispatch=True)
        return factory.get_or_create_client(provider, config)
    except LLMLifecycleCleanupError as error:
        raise AttemptLifecycleRefusal(error) from None


async def invoke_timed_provider(
    invoke: Callable[[], Awaitable[Any]],
    provider: str,
    model: str,
    attempt_timeout: float,
) -> Tuple[Any, float]:
    """Apply the provider idle timeout and exclude host accounting time."""
    start_time = time.monotonic()
    try:
        async with asyncio.timeout(attempt_timeout):
            response = await invoke()
    except TimeoutError as error:
        raise LLMTimeoutError(
            f"LLM call to {provider}:{model} timed out after "
            f"{attempt_timeout}s with no response (idle timeout)"
        ) from error
    return response, time.monotonic() - start_time


@contextmanager
def clear_attempt_lifecycle() -> Iterator[None]:
    """Prevent a nested non-governed call from inheriting attempt accounting."""
    token = attempt_lifecycle.set(None)
    try:
        yield
    finally:
        attempt_lifecycle.reset(token)


async def begin_attempt(
    lifecycle: LLMAttemptLifecycleProtocol, description: LLMAttemptDescription
) -> str:
    try:
        return await lifecycle.before_attempt(description)
    except Exception as error:
        # Arbitrary host policy/DB exceptions must stop every dispatch path.
        raise AttemptLifecycleRefusal(error) from error


async def finish_attempt(
    lifecycle: LLMAttemptLifecycleProtocol, attempt_id: str, outcome: LLMAttemptOutcome
) -> None:
    try:
        await lifecycle.after_attempt(attempt_id, outcome)
    except Exception as error:
        # One settlement only: never reinterpret this as a provider failure.
        raise AttemptLifecycleRefusal(error) from error


def provider_error_response_datetime(error: BaseException) -> Optional[datetime]:
    """Timestamp an error only when it carries the provider's HTTP response."""
    try:
        has_response = getattr(error, "response", None) is not None
    except BaseException:
        has_response = False
    return datetime.now(timezone.utc) if has_response else None


async def finalize_attempt(
    lifecycle: LLMAttemptLifecycleProtocol,
    attempt_id: str,
    description: LLMAttemptDescription,
    collector: ResponseCollector,
    accumulator: AttemptAccumulator,
    response: Any,
    duration: float,
    failure: Optional[BaseException],
    read_evidence: Callable[[Any, AttemptAccumulator], Optional[BaseException]],
    build_response: Callable[[Any, float], LLMResponse],
) -> LLMResponse:
    """Seal, diagnose, and complete every admitted attempt exactly once.

    Completion is outside provider/recovery catches. Failed or interrupted
    completion leaves the host's pending identity intact; it is never retried.
    """
    collector.seal()
    outcome, result, failure = evaluate_attempt_response(
        response, duration, failure, accumulator, read_evidence, build_response
    )
    outcome = terminal_outcome(outcome, collector, failure)
    await finish_attempt(lifecycle, attempt_id, outcome)
    if failure is not None or collector.failed:
        propagate_finalized_failure(failure, collector, description.resolved_provider)
    assert result is not None
    return result


async def invoke_governed_attempt(
    lifecycle: LLMAttemptLifecycleProtocol,
    description: LLMAttemptDescription,
    invoke: Callable[[], Awaitable[Tuple[Any, float]]],
    accumulator: AttemptAccumulator,
    read_evidence: Callable[[Any, AttemptAccumulator], Optional[BaseException]],
    build_response: Callable[[Any, float], LLMResponse],
) -> LLMResponse:
    """Admit before I/O, then hand all outcomes to the single finalizer."""
    attempt_id = await begin_attempt(lifecycle, description)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    response, duration = None, 0.0
    failure: Optional[BaseException] = None
    try:
        try:
            response, duration = await invoke()
            accumulator.outcome = replace(
                accumulator.outcome, response_datetime=datetime.now(timezone.utc)
            )
        except BaseException as error:
            failure = error
            response_datetime = provider_error_response_datetime(error)
            if response_datetime is not None:
                accumulator.outcome = replace(
                    accumulator.outcome, response_datetime=response_datetime
                )
        return await finalize_attempt(
            lifecycle,
            attempt_id,
            description,
            collector,
            accumulator,
            response,
            duration,
            failure,
            read_evidence,
            build_response,
        )
    finally:
        collector.seal()
        response_collector.reset(token)
