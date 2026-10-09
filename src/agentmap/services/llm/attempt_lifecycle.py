"""Mandatory host hooks for an opt-in physical-attempt lifecycle.

The ContextVar belongs to an invocation, never the APP-scoped service. Host
exceptions cross retry/fallback/telemetry handlers as control flow, not as
provider failures. No host exception message is sent to telemetry.
"""

import asyncio
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any, Awaitable, Callable, NoReturn, Optional, Tuple, TypeVar

from agentmap.exceptions import (
    AttemptLifecycleRefusal,
    LLMConfigurationError,
    LLMLifecycleCleanupError,
    LLMTimeoutError,
    ResponseCaptureFailure,
)
from agentmap.models.llm_attempt import LLMAttemptDescription, LLMAttemptOutcome
from agentmap.models.llm_cost import LLMCostBreakdown
from agentmap.models.llm_execution import LLMResponse, LLMUsage
from agentmap.services.llm.invocation_lease import governed_use_lease
from agentmap.services.llm.response_observer import (
    ResponseCollector,
    response_collector,
)
from agentmap.services.llm_error_utils import classify_llm_error
from agentmap.services.protocols.service_protocols import LLMAttemptLifecycleProtocol


@dataclass
class AttemptAccumulator:
    outcome: LLMAttemptOutcome = field(
        default_factory=lambda: LLMAttemptOutcome(classification="provider_error")
    )
    cost: Optional[LLMCostBreakdown] = None


def accounting_refusal() -> AttemptLifecycleRefusal:
    return AttemptLifecycleRefusal(
        LLMConfigurationError("governed attempt accounting unavailable")
    )


def _prefer_attempt_failure(
    current: Optional[BaseException], candidate: Optional[BaseException]
) -> Optional[BaseException]:
    """Retain the first failure unless a raw control-flow failure supersedes it."""
    if candidate is None:
        return current
    if current is None or (
        isinstance(current, Exception) and not isinstance(candidate, Exception)
    ):
        return candidate
    return current


attempt_lifecycle: ContextVar[Optional[LLMAttemptLifecycleProtocol]] = ContextVar(
    "agentmap_attempt_lifecycle", default=None
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


def collect_evidence(
    response: Any,
    extract_usage: Callable[[Any], Optional[LLMUsage]],
    calculate_cost: Callable[[Optional[LLMUsage]], Optional[LLMCostBreakdown]],
    extract_request_id: Callable[[Any], Optional[str]],
    *,
    outcome: LLMAttemptOutcome,
) -> Tuple[LLMAttemptOutcome, Optional[BaseException]]:
    """Extract fields independently, even if another extraction step fails.

    This diagnostic boundary catches arbitrary provider property/calculator
    exceptions only to retain available evidence. The caller re-raises the
    selected failure after mandatory settlement; raw control-flow failures take
    precedence over ordinary diagnostic errors.
    """
    failure: Optional[BaseException] = None
    try:
        outcome = replace(outcome, usage=extract_usage(response))
    except BaseException as error:
        failure = _prefer_attempt_failure(failure, error)
    try:
        cost = calculate_cost(outcome.usage)
        if cost is not None and cost.currency.upper() == "USD":
            outcome = replace(outcome, cost_usd=cost.total_cost)
    except BaseException as error:
        failure = _prefer_attempt_failure(failure, error)
    try:
        request_id = extract_request_id(response)
        if isinstance(request_id, str) and request_id:
            outcome = replace(outcome, provider_request_id=request_id)
    except BaseException as error:
        failure = _prefer_attempt_failure(failure, error)
    return outcome, failure


def evaluate_attempt_response(
    response: Any,
    duration: float,
    failure: Optional[BaseException],
    accumulator: AttemptAccumulator,
    read_evidence: Callable[[Any, AttemptAccumulator], Optional[BaseException]],
    build_response: Callable[[Any, float], LLMResponse],
) -> Tuple[LLMAttemptOutcome, Optional[LLMResponse], Optional[BaseException]]:
    """Read the same accumulator even when downstream accounting raises.

    Diagnostic failures stop dispatch after mandatory completion. Accounting
    errors never enter provider classification based on their exception text.
    """
    result = None
    accounting_error: Optional[BaseException] = None
    try:
        accounting_error = read_evidence(response, accumulator)
    except BaseException as error:
        accounting_error = error
    outcome = accumulator.outcome
    if accounting_error is not None and not isinstance(failure, asyncio.CancelledError):
        if not isinstance(accounting_error, Exception):
            failure = _prefer_attempt_failure(failure, accounting_error)
        elif failure is None or isinstance(failure, Exception):
            failure = accounting_refusal()
        outcome = replace(outcome, classification="receipt_error")
    elif failure is not None:
        outcome = replace(outcome, classification="provider_error")
    if failure is None:
        outcome = replace(outcome, classification="normalization_error")
        try:
            result = build_response(response, duration)
            outcome = replace(outcome, classification=result.text_status)
        except BaseException as error:
            failure = error
    return outcome, result, failure


def terminal_outcome(
    outcome: LLMAttemptOutcome,
    collector: ResponseCollector,
    failure: Optional[BaseException],
) -> LLMAttemptOutcome:
    classification, error_type = outcome.classification, None
    if failure is not None:
        error_type = type(failure).__name__
        if isinstance(failure, asyncio.CancelledError):
            classification = "cancelled"
        elif isinstance(failure, LLMTimeoutError):
            classification = "timeout"
    if (
        collector.failed
        and not isinstance(failure, asyncio.CancelledError)
        and (failure is None or isinstance(failure, Exception))
    ):
        classification, error_type = "capture_error", "ResponseCaptureFailure"
    return replace(
        outcome,
        classification=classification,
        error_type=error_type,
        response_evidence=collector.evidence,
        cleanup_failed=collector.cleanup_failed,
    )


def propagate_finalized_failure(
    failure: Optional[BaseException], collector: ResponseCollector, provider: str
) -> NoReturn:
    if isinstance(failure, asyncio.CancelledError):
        raise failure from None
    if failure is not None and not isinstance(failure, Exception):
        raise failure from None
    if collector.failed:
        raise AttemptLifecycleRefusal(
            ResponseCaptureFailure(cleanup_failed=collector.cleanup_failed)
        ) from None
    if isinstance(failure, AttemptLifecycleRefusal):
        raise failure from None
    assert isinstance(failure, Exception)
    # Classify for retry while excluding transport and SDK representations.
    typed_error = classify_llm_error(failure, provider)
    raise type(typed_error)("governed physical provider attempt failed") from None


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
        except BaseException as error:
            failure = error
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
