"""Usage presence is measured before qualified wrappers fabricate defaults."""

import json
from decimal import Decimal
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMServiceError
from agentmap.services.llm.cost_calculator import LLMCostCalculator
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
    real_service,
    setup_transport,
)

KEYS = {
    "anthropic": ("usage", "input_tokens", "output_tokens"),
    "openai": ("usage", "prompt_tokens", "completion_tokens"),
    "google": ("usageMetadata", "promptTokenCount", "candidatesTokenCount"),
}


def changed_body(provider, bucket, value):
    payload = json.loads(body_for(provider))
    container, input_key, output_key = KEYS[provider]
    key = input_key if bucket == "input_tokens" else output_key
    if value == "absent":
        payload[container].pop(key)
    else:
        payload[container][key] = value
    return json.dumps(payload, ensure_ascii=False).encode()


def priced_service(provider, model, bucket, free=False):
    service = real_service(provider, model)
    rates = {"input_per_1m": 10000, "output_per_1m": 10000}
    if free:
        rates["input_per_1m" if bucket == "input_tokens" else "output_per_1m"] = 0
    service._cost_calculator = LLMCostCalculator(
        {"models": {provider: {model: rates}}}, Mock()
    )
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("bucket", ["input_tokens", "output_tokens"])
@pytest.mark.parametrize("value", ["absent", None, 0, 10, -1, "bad", True, 1.5])
@pytest.mark.parametrize("tools", [False, True])
async def test_raw_usage_presence_controls_accounting_and_redispatch__b102(
    monkeypatch, provider, model, bucket, value, tools
):
    body = changed_body(provider, bucket, value)
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, bucket)
    ledger = Ledger("1")
    kwargs = {}
    if tools:
        kwargs["tools"] = [
            {"name": "extract", "parameters": {"type": "object", "properties": {}}}
        ]
    try:
        expected = value if type(value) is int and value >= 0 else None
        result = None
        try:
            result = await service.call_llm_async(
                messages=[{"role": "user", "content": "synthetic"}],
                provider=provider,
                model=model,
                attempt_lifecycle=ledger,
                **kwargs,
            )
        except LLMServiceError:
            if expected is not None:
                raise
        if expected is not None:
            assert result.text == "body-secret café"
            assert result.usage == ledger.rows["1"].usage
            assert result.cost.total_cost == ledger.rows["1"].cost_usd
        outcome = ledger.rows["1"]
        assert getattr(outcome.usage, bucket) == expected
        assert outcome.response_evidence.body == body
        other = "output_tokens" if bucket == "input_tokens" else "input_tokens"
        assert getattr(outcome.usage, other) == 10
        assert outcome.cost_usd == (
            None if expected is None else Decimal("0.10") + Decimal(expected) / 100
        )
        if expected is None:
            with pytest.raises(AccountingRefusal):
                await invoke(service, provider, model, ledger)
            assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("bucket", ["input_tokens", "output_tokens"])
async def test_unavailable_core_count_at_explicit_zero_rate_remains_costed__b102(
    monkeypatch, provider, model, bucket
):
    body = changed_body(provider, bucket, "absent")
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, bucket, free=True)
    ledger = Ledger("1")
    try:
        result = await invoke(service, provider, model, ledger)
        assert getattr(result.usage, bucket) is None
        assert result.cost.total_cost == ledger.rows["1"].cost_usd == Decimal("0.10")
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
async def test_duplicate_provider_usage_key_is_unknown_and_blocks_redispatch__b102(
    monkeypatch,
):
    provider, model = "anthropic", "claude-sonnet-4-5"
    body = body_for(provider).replace(
        b'"input_tokens": 10,',
        b'"input_tokens": 10, "input_tokens": 10,',
        1,
    )
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    ledger = Ledger("1")
    try:
        result = await invoke(service, provider, model, ledger)

        outcome = ledger.rows["1"]
        assert result.usage.input_tokens is None
        assert result.usage.output_tokens is None
        assert getattr(result.cost, "total_cost", None) is None
        assert outcome.response_evidence.body == body
        assert outcome.usage.input_tokens is None
        assert outcome.usage.output_tokens is None
        assert outcome.cost_usd is None
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.parametrize(
    "field",
    [
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    ],
)
@pytest.mark.parametrize("value", [-1, -1.0, -0.5, (10, -0.5), (10, (5, -1.0))])
def test_negative_measurements_in_every_bucket_prevent_zero_rate_pricing__b102(
    field, value
):
    from agentmap.models.llm_cost import LLMModelRates
    from agentmap.services.llm.usage_presence import (
        pricing_usage,
        validate_usage_presence,
    )

    values = {"input_tokens": 10, "output_tokens": 10, field: value}
    usage = validate_usage_presence(values)
    rates = LLMModelRates(
        currency="USD",
        input_per_1m=Decimal(0),
        output_per_1m=Decimal(0),
        cache_write_per_1m=Decimal(0),
        cache_read_per_1m=Decimal(0),
    )
    assert pricing_usage(usage, values, "anthropic", rates) is None
    assert getattr(usage, field) is None
    other = "output_tokens" if field == "input_tokens" else "input_tokens"
    assert getattr(usage, other) == 10


@pytest.mark.parametrize(
    "value", [None, False, True, 0, 1.5, float("inf"), float("-inf"), float("nan")]
)
def test_zero_rate_unavailable_measurements_are_not_negative_evidence__b102(value):
    from agentmap.models.llm_cost import LLMModelRates
    from agentmap.services.llm.usage_presence import (
        pricing_usage,
        validate_usage_presence,
    )

    values = {
        "input_tokens": 10,
        "output_tokens": 10,
        "cache_creation_input_tokens": value,
    }
    usage = validate_usage_presence(values)
    rates = LLMModelRates(
        currency="USD",
        input_per_1m=Decimal(1),
        output_per_1m=Decimal(1),
        cache_write_per_1m=Decimal(0),
    )
    assert pricing_usage(usage, values, "anthropic", rates) == usage


def test_pricing_usage_declared_optional_measurement_fails_closed__b102():
    from agentmap.models.llm_cost import LLMModelRates
    from agentmap.services.llm.usage_presence import pricing_usage

    rates = LLMModelRates(
        currency="USD", input_per_1m=Decimal(1), output_per_1m=Decimal(1)
    )
    assert pricing_usage(None, {"input_tokens": 10}, "anthropic", rates) is None


def composite_body(candidate, thoughts):
    payload = json.loads(body_for("google"))
    for key, value in (
        ("candidatesTokenCount", candidate),
        ("thoughtsTokenCount", thoughts),
    ):
        if value == "absent":
            payload["usageMetadata"].pop(key, None)
        else:
            payload["usageMetadata"][key] = value
    return json.dumps(payload).encode()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "candidate,thoughts,expected",
    [
        (10, 5, 15),
        (10, 0, 10),
        (0, 5, 5),
        (10, "absent", 10),
    ],
)
async def test_google_thoughts_are_part_of_output_usage_before_pricing__b102(
    monkeypatch, candidate, thoughts, expected
):
    provider, model = "google", "gemini-2.5-flash"
    body = composite_body(candidate, thoughts)
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "output_tokens")
    ledger = Ledger("1")
    try:
        result = await invoke(service, provider, model, ledger)
        row = ledger.rows["1"]
        assert result.text == "body-secret café"
        assert result.usage == row.usage
        assert row.usage.input_tokens == 10
        assert row.usage.output_tokens == expected
        assert (
            result.cost.total_cost
            == row.cost_usd
            == (Decimal("0.10") + Decimal(expected) / 100)
        )
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "candidate,thoughts,expected",
    [
        ("absent", 5, None),
        (None, 5, None),
        (10, None, None),
        (10, -1, None),
        (10, -0.5, None),
        (10, True, None),
        (10, "bad", None),
        (1.5, 5, None),
    ],
)
async def test_invalid_google_composite_output_blocks_redispatch__b102(
    monkeypatch, candidate, thoughts, expected
):
    provider, model = "google", "gemini-2.5-flash"
    body = composite_body(candidate, thoughts)
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "output_tokens")
    ledger = Ledger("1")
    try:
        try:
            result = await invoke(service, provider, model, ledger)
        except LLMServiceError:
            result = None
        row = ledger.rows["1"]
        assert row.usage.input_tokens == 10
        assert row.usage.output_tokens == expected
        assert row.cost_usd == (
            None if expected is None else Decimal("0.10") + Decimal(expected) / 100
        )
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        if result is not None:
            assert result.usage == row.usage
        if expected is None:
            with pytest.raises(AccountingRefusal):
                await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()
