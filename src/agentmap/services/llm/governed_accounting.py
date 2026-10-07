"""Governed provider usage capture and accounting callbacks."""

from dataclasses import replace
from typing import Any, Callable, Dict, Optional, Tuple

from agentmap.exceptions import LLMConfigurationError
from agentmap.models.llm_cost import LLMCostBreakdown, LLMModelRates
from agentmap.models.llm_execution import LLMResponse, LLMUsage
from agentmap.services.llm.attempt_lifecycle import (
    AttemptAccumulator,
    accounting_refusal,
    collect_evidence,
)
from agentmap.services.llm.cost_calculator import LLMCostCalculator
from agentmap.services.llm.response_observer import response_collector
from agentmap.services.llm.usage_presence import capture_measurements, pricing_usage

_Accounting = Tuple[Optional[LLMUsage], Optional[LLMCostBreakdown]]
_EvidenceReader = Callable[[Any, AttemptAccumulator], Optional[Exception]]
_RequestIdExtractor = Callable[[Any], Optional[str]]
_ResponseBuilder = Callable[[Any, float, _Accounting], LLMResponse]


def governed_rates(
    calculator: LLMCostCalculator, provider: str, model: str
) -> Optional[LLMModelRates]:
    try:
        return calculator.get_rates(provider, model)
    except LLMConfigurationError:
        calculator._logger.warning(
            "governed_rates_refused category=configuration stage=rate_lookup"
        )
        raise accounting_refusal() from None
    except Exception as error:
        calculator._logger.warning(
            "governed_rates_refused category=unexpected stage=rate_lookup exception_type=%s",
            type(error).__name__,
        )
        raise accounting_refusal() from None


def governed_cost(
    calculator: LLMCostCalculator,
    usage: Optional[LLMUsage],
    values: Optional[Dict[str, Any]],
    provider: str,
    model: str,
) -> Optional[LLMCostBreakdown]:
    priced_usage = pricing_usage(
        usage, values, provider, calculator.get_rates(provider, model)
    )
    return calculator.calculate(priced_usage, provider, model)


def governed_accounting_callbacks(
    calculator: LLMCostCalculator,
    provider: str,
    model: str,
    accumulator: AttemptAccumulator,
    extract_request_id: _RequestIdExtractor,
    build_success_response: _ResponseBuilder,
) -> tuple[_EvidenceReader, Callable[[Any, float], LLMResponse]]:
    def read_evidence(raw: Any, accumulator: AttemptAccumulator) -> Optional[Exception]:
        collector = response_collector.get()
        if collector is None:
            raise RuntimeError("governed accounting requires an active collector")
        capture_error: Optional[Exception] = None
        try:
            usage, values = capture_measurements(provider, collector.evidence)
        except Exception as measurement_error:
            capture_error = measurement_error
            usage, values = accumulator.outcome.usage, None
        else:
            accumulator.outcome = replace(accumulator.outcome, usage=usage)

        def calculate(_: Optional[LLMUsage]) -> Optional[LLMCostBreakdown]:
            if capture_error is not None:
                return None
            accumulator.cost = governed_cost(calculator, usage, values, provider, model)
            return accumulator.cost

        accumulator.outcome, evidence_error = collect_evidence(
            raw,
            lambda _: usage,
            calculate,
            extract_request_id,
            outcome=accumulator.outcome,
        )
        return capture_error or evidence_error

    def build_response(raw: Any, duration: float) -> LLMResponse:
        return build_success_response(
            raw,
            duration,
            (accumulator.outcome.usage, accumulator.cost),
        )

    return read_evidence, build_response
