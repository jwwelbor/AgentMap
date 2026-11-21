"""Collect response evidence and choose the final attempt outcome."""

import asyncio
from dataclasses import dataclass, field, replace
from typing import Any, Callable, NoReturn, Optional, Tuple

from agentmap.exceptions import (
    AttemptLifecycleRefusal,
    LLMConfigurationError,
    LLMTimeoutError,
    ResponseCaptureFailure,
)
from agentmap.models.llm_attempt import LLMAttemptOutcome
from agentmap.models.llm_cost import LLMCostBreakdown
from agentmap.models.llm_execution import LLMResponse, LLMUsage
from agentmap.services.llm.response_observer import ResponseCollector
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


def collect_evidence(
    response: Any,
    extract_usage: Callable[[Any], Optional[LLMUsage]],
    calculate_cost: Callable[[Optional[LLMUsage]], Optional[LLMCostBreakdown]],
    extract_request_id: Callable[[Any], Optional[str]],
    *,
    outcome: LLMAttemptOutcome,
) -> Tuple[LLMAttemptOutcome, Optional[BaseException]]:
    """Extract fields independently and retain the strongest extraction error."""
    failure: Optional[BaseException] = None
    try:
        outcome = replace(outcome, usage=extract_usage(response))
    except BaseException as error:
        failure = _prefer_attempt_failure(failure, error)
    try:
        cost = calculate_cost(outcome.usage)
        if cost is not None:
            outcome = replace(
                outcome,
                cost_usd=(
                    cost.total_cost
                    if cost.currency.upper() == "USD"
                    else outcome.cost_usd
                ),
                cost_amount=cost.total_cost,
                cost_currency=cost.currency.upper(),
            )
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
    """Build a response only after evidence capture; convert accounting errors."""
    result = None
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
    typed_error = classify_llm_error(failure, provider)
    raise type(typed_error)("governed physical provider attempt failed") from None
