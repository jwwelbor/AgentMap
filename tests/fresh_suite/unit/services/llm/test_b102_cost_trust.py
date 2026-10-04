"""B102: incomplete core usage cannot authorize another physical attempt."""

from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.models.llm_execution import LLMUsage
from agentmap.services.llm.cost_calculator import LLMCostCalculator
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
    call,
    raw_response,
    service_with_client,
)


@pytest.mark.parametrize("missing_bucket", ["input_tokens", "output_tokens"])
@pytest.mark.parametrize("rate", [None, 0, 10000])
def test_missing_core_count_requires_explicit_free_rate__b102(missing_bucket, rate):
    rate_name = "input_per_1m" if missing_bucket == "input_tokens" else "output_per_1m"
    rates = {"input_per_1m": 10000, "output_per_1m": 10000}
    if rate is None:
        del rates[rate_name]
    else:
        rates[rate_name] = rate
    calculator = LLMCostCalculator(
        {"models": {"openai": {"test-model": rates}}}, Mock()
    )
    counts = {"input_tokens": 10, "output_tokens": 10}
    counts[missing_bucket] = None

    result = calculator.calculate(LLMUsage(**counts), "openai", "test-model")

    if rate == 0:
        assert result.total_cost == Decimal("0.100000")
    else:
        assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_bucket", ["input_tokens", "output_tokens"])
@pytest.mark.parametrize("rate", [None, 0, 10000])
async def test_public_lifecycle_refuses_unknown_core_spend__b102(missing_bucket, rate):
    response = raw_response()
    response.usage_metadata[missing_bucket] = None
    client = Mock(ainvoke=AsyncMock(return_value=response))
    service = service_with_client(client)
    rate_name = "input_per_1m" if missing_bucket == "input_tokens" else "output_per_1m"
    rates = {"input_per_1m": 10000, "output_per_1m": 10000}
    if rate is None:
        del rates[rate_name]
    else:
        rates[rate_name] = rate
    service._cost_calculator = LLMCostCalculator(
        {"models": {"openai": {"test-model": rates}}}, Mock()
    )
    ledger = Ledger("0.20")

    await call(service, ledger)
    if rate == 0:
        assert ledger.rows["1"].cost_usd == Decimal("0.10")
        await call(service, ledger)
        assert client.ainvoke.await_count == 2
    else:
        assert ledger.rows["1"].cost_usd is None
        with pytest.raises(AccountingRefusal, match="unresolved charge"):
            await call(service, ledger)
        assert client.ainvoke.await_count == 1


@pytest.mark.parametrize(
    "bucket",
    [
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ],
)
@pytest.mark.parametrize("rate", [0, 10000])
def test_negative_usage_is_diagnostic_not_priced__b102(bucket, rate):
    rates = {
        "input_per_1m": rate,
        "output_per_1m": rate,
        "cache_write_per_1m": rate,
        "cache_read_per_1m": rate,
    }
    calculator = LLMCostCalculator(
        {"models": {"openai": {"test-model": rates}}}, Mock()
    )
    counts = dict.fromkeys(
        [
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        ],
        10,
    )
    counts[bucket] = -1
    usage = LLMUsage(**counts)

    assert calculator.calculate(usage, "openai", "test-model") is None
    assert getattr(usage, bucket) == -1


@pytest.mark.asyncio
@pytest.mark.parametrize("rate", [0, 10000])
@pytest.mark.parametrize(
    "bucket",
    [
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ],
)
async def test_negative_usage_refuses_next_physical_call__b102(bucket, rate):
    response = raw_response()
    response.usage_metadata[bucket] = -1
    client = Mock(ainvoke=AsyncMock(return_value=response))
    service = service_with_client(client)
    service._cost_calculator = LLMCostCalculator(
        {
            "models": {
                "openai": {
                    "test-model": {
                        "input_per_1m": rate,
                        "output_per_1m": rate,
                        "cache_write_per_1m": rate,
                        "cache_read_per_1m": rate,
                    }
                }
            }
        },
        Mock(),
    )
    ledger = Ledger("0.20")

    await call(service, ledger)
    assert getattr(ledger.rows["1"].usage, bucket) == -1
    assert ledger.rows["1"].cost_usd is None
    with pytest.raises(AccountingRefusal, match="unresolved charge"):
        await call(service, ledger)
    assert client.ainvoke.await_count == 1
