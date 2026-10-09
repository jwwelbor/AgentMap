"""USD receipt spelling does not erase measured attempt cost."""

from decimal import Decimal

import pytest

from agentmap.models.llm_attempt import LLMAttemptOutcome
from agentmap.models.llm_cost import LLMCostBreakdown
from agentmap.models.llm_execution import LLMUsage
from agentmap.services.llm.attempt_lifecycle import collect_evidence


@pytest.mark.parametrize(
    ("currency", "expected_cost"),
    [("USD", Decimal("0.20")), ("usd", Decimal("0.20")), ("CAD", None)],
)
def test_governed_currency_receipt_only_publishes_usd_cost__b102(
    currency, expected_cost
):
    cost = LLMCostBreakdown(
        total_cost=Decimal("0.20"),
        currency=currency,
        catalog_version="offline-v1",
        input_cost=Decimal("0.10"),
        output_cost=Decimal("0.10"),
        cache_write_cost=Decimal(0),
        cache_read_cost=Decimal(0),
    )
    outcome, error = collect_evidence(
        object(),
        lambda _: LLMUsage(input_tokens=10, output_tokens=20),
        lambda _: cost,
        lambda _: None,
        outcome=LLMAttemptOutcome(classification="response"),
    )
    assert error is None
    assert outcome.cost_usd == expected_cost
    assert outcome.usage == LLMUsage(input_tokens=10, output_tokens=20)
