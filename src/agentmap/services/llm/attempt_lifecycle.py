"""Mandatory host hooks for an opt-in physical-attempt lifecycle.

The ContextVar belongs to an invocation, never the APP-scoped service. Host
exceptions cross retry/fallback/telemetry handlers as control flow, not as
provider failures. No host exception message is sent to telemetry.
"""

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from typing import Any, Awaitable, Callable, NoReturn, Optional, Tuple

from agentmap.exceptions import LLMConfigurationError, LLMTimeoutError
from agentmap.models.llm_attempt import LLMAttemptDescription, LLMAttemptOutcome
from agentmap.models.llm_cost import LLMCostBreakdown
from agentmap.models.llm_execution import LLMResponse
from agentmap.services.llm.response_observer import (
    ResponseCaptureFailure,
    ResponseCollector,
    response_collector,
)
from agentmap.services.llm_error_utils import classify_llm_error
from agentmap.services.protocols.service_protocols import LLMAttemptLifecycleProtocol


class AttemptLifecycleRefusal(Exception):
    def __init__(self, original: BaseException) -> None:
        super().__init__("physical attempt lifecycle refused")
        self.original = original


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


attempt_lifecycle: ContextVar[Optional[LLMAttemptLifecycleProtocol]] = ContextVar(
    "agentmap_attempt_lifecycle", default=None
)


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
    extract_usage: Callable,
    calculate_cost: Callable,
    extract_request_id: Callable,
    *,
    outcome: LLMAttemptOutcome,
) -> Tuple[LLMAttemptOutcome, Optional[Exception]]:
    """Extract fields independently, even if another extraction step fails.

    This diagnostic boundary catches arbitrary provider property/calculator
    exceptions only to retain available evidence. The first failure is returned
    and re-raised by the caller after mandatory settlement, never swallowed.
    """
    failure = None
    try:
        outcome = replace(outcome, usage=extract_usage(response))
    except Exception as error:
        failure = error
    try:
        cost = calculate_cost(outcome.usage)
        if cost is not None and cost.currency.upper() == "USD":
            outcome = replace(outcome, cost_usd=cost.total_cost)
    except Exception as error:
        failure = failure or error
    try:
        request_id = extract_request_id(response)
        if isinstance(request_id, str) and request_id:
            outcome = replace(outcome, provider_request_id=request_id)
    except Exception as error:
        failure = failure or error
    return outcome, failure


def evaluate_attempt_response(
    response: Any,
    duration: float,
    failure: Optional[BaseException],
    accumulator: AttemptAccumulator,
    read_evidence: Callable[[Any, AttemptAccumulator], Optional[Exception]],
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
    except (Exception, asyncio.CancelledError) as error:
        accounting_error = error
    outcome = accumulator.outcome
    if accounting_error is not None and not isinstance(failure, asyncio.CancelledError):
        failure = (
            accounting_error
            if isinstance(accounting_error, asyncio.CancelledError)
            else accounting_refusal()
        )
        outcome = replace(outcome, classification="receipt_error")
    elif failure is not None:
        outcome = replace(outcome, classification="provider_error")
    if failure is None:
        outcome = replace(outcome, classification="normalization_error")
        try:
            result = build_response(response, duration)
            outcome = replace(outcome, classification=result.text_status)
        except (Exception, asyncio.CancelledError) as error:
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
    if collector.failed and not isinstance(failure, asyncio.CancelledError):
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
    read_evidence: Callable[[Any, AttemptAccumulator], Optional[Exception]],
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
    try:
        await finish_attempt(lifecycle, attempt_id, outcome)
    except (AttemptLifecycleRefusal, asyncio.CancelledError):
        if isinstance(failure, asyncio.CancelledError):
            raise failure from None
        raise
    if failure is not None or collector.failed:
        propagate_finalized_failure(failure, collector, description.resolved_provider)
    assert result is not None
    return result


async def invoke_governed_attempt(
    lifecycle: LLMAttemptLifecycleProtocol,
    description: LLMAttemptDescription,
    invoke: Callable[[], Awaitable[Tuple[Any, float]]],
    accumulator: AttemptAccumulator,
    read_evidence: Callable[[Any, AttemptAccumulator], Optional[Exception]],
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
        except (Exception, asyncio.CancelledError) as error:
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
