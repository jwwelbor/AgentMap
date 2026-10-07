"""Cache usage fields retain explicit presence and pricing outcomes."""

import json
from decimal import Decimal

import pytest

from agentmap.exceptions import LLMServiceError
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
)
from tests.fresh_suite.unit.services.llm.test_b102_observed_usage import priced_service
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
    setup_transport,
)


def cache_body(provider, value):
    payload = json.loads(body_for(provider))
    if value != "absent":
        if provider == "anthropic":
            payload["usage"]["cache_read_input_tokens"] = value
        elif provider == "openai":
            payload["usage"]["prompt_tokens_details"] = {"cached_tokens": value}
        else:
            payload["usageMetadata"]["cachedContentTokenCount"] = value
    return json.dumps(payload).encode()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value,free,expected_usage,expected_cost,returns_result",
    [
        ("absent", False, None, Decimal("0.20"), True),
        ("absent", True, None, Decimal("0.20"), True),
        (None, False, None, None, True),
        (None, True, None, Decimal("0.20"), True),
        (0, False, 0, Decimal("0.20"), True),
        (0, True, 0, Decimal("0.20"), True),
        (5, False, 5, Decimal("0.21"), True),
        (5, True, 5, Decimal("0.20"), True),
        (-1, False, None, None, True),
        (-1, True, None, None, True),
        (-1.0, False, None, None, True),
        (-1.0, True, None, None, True),
        (-0.5, False, None, None, True),
        (-0.5, True, None, None, True),
        ("bad", False, None, None, False),
        ("bad", True, None, Decimal("0.20"), False),
        (True, False, None, None, True),
        (True, True, None, Decimal("0.20"), True),
        (1.5, False, None, None, True),
        (1.5, True, None, Decimal("0.20"), True),
    ],
)
async def test_anthropic_cache_write_has_presence_and_price_validation__b102(
    monkeypatch, value, free, expected_usage, expected_cost, returns_result
):
    provider, model = "anthropic", "claude-sonnet-4-5"
    payload = json.loads(body_for(provider))
    if value != "absent":
        payload["usage"]["cache_creation_input_tokens"] = value
    body = json.dumps(payload).encode()
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    service._cost_calculator._raw_rate_index[(provider, model)][
        "cache_write_per_1m"
    ] = (0 if free else 2000)
    ledger = Ledger("1")
    try:
        result = None
        try:
            result = await invoke(service, provider, model, ledger)
        except LLMServiceError:
            if returns_result:
                raise
        row = ledger.rows["1"]
        assert (result is not None) is returns_result
        assert row.usage.cache_creation_input_tokens == expected_usage
        assert row.cost_usd == expected_cost
        assert row.usage.input_tokens == row.usage.output_tokens == 10
        if returns_result:
            assert result.text == "body-secret café"
            assert result.usage == row.usage
            assert getattr(result.cost, "total_cost", None) == expected_cost
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        if expected_cost is None:
            with pytest.raises(AccountingRefusal):
                await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider,model,value,expected_usage,expected_cost,returns_result",
    [
        ("openai", "gpt-4o-mini", "absent", None, Decimal("0.20"), True),
        ("openai", "gpt-4o-mini", None, None, None, True),
        ("openai", "gpt-4o-mini", 0, 0, Decimal("0.20"), True),
        ("openai", "gpt-4o-mini", 5, 5, Decimal("0.16"), True),
        ("openai", "gpt-4o-mini", -1, None, None, True),
        ("openai", "gpt-4o-mini", "bad", None, None, True),
        ("openai", "gpt-4o-mini", True, None, None, True),
        ("openai", "gpt-4o-mini", 1.5, None, None, True),
        ("anthropic", "claude-sonnet-4-5", "absent", None, Decimal("0.20"), True),
        ("anthropic", "claude-sonnet-4-5", None, None, None, True),
        ("anthropic", "claude-sonnet-4-5", 0, 0, Decimal("0.20"), True),
        ("anthropic", "claude-sonnet-4-5", 5, 5, Decimal("0.21"), True),
        ("anthropic", "claude-sonnet-4-5", -1, None, None, True),
        ("anthropic", "claude-sonnet-4-5", "bad", None, None, False),
        ("anthropic", "claude-sonnet-4-5", True, None, None, True),
        ("anthropic", "claude-sonnet-4-5", 1.5, None, None, True),
        ("google", "gemini-2.5-flash", "absent", None, Decimal("0.20"), True),
        ("google", "gemini-2.5-flash", None, None, None, True),
        ("google", "gemini-2.5-flash", 0, 0, Decimal("0.20"), True),
        ("google", "gemini-2.5-flash", 5, 5, Decimal("0.16"), True),
        ("google", "gemini-2.5-flash", 11, 11, None, True),
        ("google", "gemini-2.5-flash", -1, None, None, True),
        ("google", "gemini-2.5-flash", "bad", None, None, False),
        ("google", "gemini-2.5-flash", True, None, None, True),
        ("google", "gemini-2.5-flash", 1.5, None, None, False),
    ],
)
async def test_optional_cache_omission_differs_from_present_invalid_measurement__b102(
    monkeypatch, provider, model, value, expected_usage, expected_cost, returns_result
):
    body = cache_body(provider, value)
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    service._cost_calculator._raw_rate_index[(provider, model)][
        "cache_read_per_1m"
    ] = 2000
    ledger = Ledger("1")
    try:
        result = None
        try:
            result = await invoke(service, provider, model, ledger)
        except LLMServiceError:
            if returns_result:
                raise
        assert (result is not None) is returns_result
        outcome = ledger.rows["1"]
        assert outcome.usage.cache_read_input_tokens == expected_usage
        assert outcome.usage.input_tokens == outcome.usage.output_tokens == 10
        assert outcome.cost_usd == expected_cost
        assert outcome.response_evidence.body == body
        if returns_result:
            assert result.text == "body-secret café"
            assert result.usage == outcome.usage
            assert getattr(result.cost, "total_cost", None) == expected_cost
        if expected_cost is None:
            with pytest.raises(AccountingRefusal):
                await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS[:1] + PROVIDERS[2:])
async def test_fully_cached_input_returns_and_settles_original_measurements__b102(
    monkeypatch, provider, model
):
    body = cache_body(provider, 10)
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    service._cost_calculator._raw_rate_index[(provider, model)][
        "cache_read_per_1m"
    ] = 2000
    ledger = Ledger("1")
    try:
        result = await invoke(service, provider, model, ledger)
        row = ledger.rows["1"]
        assert result.text == "body-secret café"
        assert result.usage == row.usage
        assert row.usage.input_tokens == row.usage.output_tokens == 10
        assert row.usage.cache_read_input_tokens == 10
        assert result.cost is not None
        assert result.cost.total_cost == row.cost_usd == Decimal("0.12")
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()
