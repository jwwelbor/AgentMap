"""Mandatory host hooks for an opt-in physical-attempt lifecycle.

The ContextVar belongs to an invocation, never the APP-scoped service. Host
exceptions cross retry/fallback/telemetry handlers as control flow, not as
provider failures. No host exception message is sent to telemetry.
"""

import asyncio
from contextvars import ContextVar
from dataclasses import replace
from typing import Any, Awaitable, Callable, NoReturn, Optional, Tuple

from agentmap.exceptions import LLMTimeoutError
from agentmap.models.llm_attempt import LLMAttemptDescription, LLMAttemptOutcome
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
) -> Tuple[LLMAttemptOutcome, Optional[Exception]]:
    """Extract fields independently, even if another extraction step fails.

    This diagnostic boundary catches arbitrary provider property/calculator
    exceptions only to retain available evidence. The first failure is returned
    and re-raised by the caller after mandatory settlement, never swallowed.
    """
    outcome = LLMAttemptOutcome(classification="response")
    failure = None
    try:
        outcome = replace(outcome, usage=extract_usage(response))
    except Exception as error:
        failure = error
    try:
        cost = calculate_cost(outcome.usage)
        if cost is not None and cost.currency == "USD":
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


async def settle_cancelled(
    lifecycle: LLMAttemptLifecycleProtocol,
    attempt_id: str,
    outcome: LLMAttemptOutcome,
    cancellation: asyncio.CancelledError,
) -> NoReturn:
    """Attempt settlement, preserving cancellation even when cleanup fails.

    The host's committed pending intent survives failed or interrupted cleanup.
    No detached task or automatic retry assumes that reconciliation succeeded.
    """
    try:
        await finish_attempt(lifecycle, attempt_id, outcome)
    finally:
        raise cancellation


async def settle_failed_attempt(
    lifecycle: LLMAttemptLifecycleProtocol,
    attempt_id: str,
    outcome: LLMAttemptOutcome,
    collector: ResponseCollector,
    error: Exception,
    provider: str,
) -> NoReturn:
    """Settle one failed dispatch before propagating a sanitized error."""
    classification = (
        "timeout" if isinstance(error, LLMTimeoutError) else outcome.classification
    )
    if collector.failed:
        classification = "capture_error"
    outcome = replace(
        outcome,
        classification=classification,
        error_type=(
            "ResponseCaptureFailure" if collector.failed else type(error).__name__
        ),
        response_evidence=collector.seal(),
    )
    await finish_attempt(lifecycle, attempt_id, outcome)
    if collector.failed:
        raise AttemptLifecycleRefusal(ResponseCaptureFailure()) from None
    # Classify for retry while excluding transport and SDK representations.
    typed_error = classify_llm_error(error, provider)
    raise type(typed_error)("governed physical provider attempt failed") from None


async def settle_successful_attempt(
    lifecycle: LLMAttemptLifecycleProtocol,
    attempt_id: str,
    outcome: LLMAttemptOutcome,
    collector: ResponseCollector,
) -> None:
    """Settle the observed response even when capture itself failed."""
    outcome = replace(outcome, response_evidence=collector.evidence)
    if collector.failed:
        outcome = replace(
            outcome, classification="capture_error", error_type="ResponseCaptureFailure"
        )
    await finish_attempt(lifecycle, attempt_id, outcome)
    if collector.failed:
        raise AttemptLifecycleRefusal(ResponseCaptureFailure()) from None


async def invoke_governed_attempt(
    lifecycle: LLMAttemptLifecycleProtocol,
    description: LLMAttemptDescription,
    invoke: Callable[[], Awaitable[Tuple[Any, float]]],
    read_evidence: Callable[[Any], Tuple[LLMAttemptOutcome, Optional[Exception]]],
    build_response: Callable[[Any, float], LLMResponse],
) -> LLMResponse:
    """Settle once, outside the raw provider exception's active context."""
    attempt_id = await begin_attempt(lifecycle, description)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    outcome = LLMAttemptOutcome(classification="provider_error")
    failure: Optional[Exception] = None
    cancelled: Optional[asyncio.CancelledError] = None
    try:
        response, duration = await invoke()
        outcome, error = read_evidence(response)
        if error is not None:
            outcome = replace(outcome, classification="receipt_error")
            raise error
        outcome = replace(outcome, classification="normalization_error")
        result = build_response(response, duration)
        outcome = replace(outcome, classification=result.text_status)
    except asyncio.CancelledError as cancellation:
        cancelled = cancellation
        outcome = replace(
            outcome,
            classification="cancelled",
            error_type="CancelledError",
            response_evidence=collector.seal(),
        )
    except Exception as error:
        failure = error
    finally:
        collector.seal()
        response_collector.reset(token)
    if cancelled is not None:
        await settle_cancelled(lifecycle, attempt_id, outcome, cancelled)
    if failure is not None:
        await settle_failed_attempt(
            lifecycle,
            attempt_id,
            outcome,
            collector,
            failure,
            description.resolved_provider,
        )
    await settle_successful_attempt(lifecycle, attempt_id, outcome, collector)
    return result
