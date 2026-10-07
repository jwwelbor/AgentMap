"""USD receipt spelling does not erase measured attempt cost."""

from decimal import Decimal

import pytest

from agentmap.models.llm_attempt import LLMAttemptOutcome
from agentmap.models.llm_cost import LLMCostBreakdown
from agentmap.models.llm_execution import LLMUsage
from agentmap.services.llm.attempt_lifecycle import collect_evidence


@pytest.mark.parametrize("currency", ["USD", "usd"])
def test_governed_usd_receipt_preserves_cost__b102(currency):
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
    assert outcome.cost_usd == Decimal("0.20")
