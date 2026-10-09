"""Container availability must survive zero core rates and SDK defaults."""

import json
from decimal import Decimal
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMServiceError
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
)
from tests.fresh_suite.unit.services.llm.test_b102_observed_usage import (
    KEYS,
    priced_service,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
    setup_transport,
)

INVALID_CONTAINERS = [
    "absent",
    None,
    [],
    "bad",
    0,
    True,
    "malformed_json",
    "scalar_body",
    "null_body",
    "array_body",
]


def container_body(provider, container):
    raw_bodies = {
        "malformed_json": b"{invalid json",
        "scalar_body": b'"scalar"',
        "null_body": b"null",
        "array_body": b"[]",
    }
    if isinstance(container, str) and container in raw_bodies:
        return raw_bodies[container]
    payload = json.loads(body_for(provider))
    key = KEYS[provider][0]
    if container == "absent":
        payload.pop(key)
    else:
        payload[key] = container
    return json.dumps(payload).encode()


def zero_core_service(provider, model, cache_bucket, cache_rate):
    service = priced_service(provider, model, "input_tokens")
    rates = service._cost_calculator._raw_rate_index[(provider, model)]
    rates.update(
        input_per_1m=0,
        output_per_1m=0,
        cache_write_per_1m=0,
        cache_read_per_1m=0,
    )
    rates[cache_bucket] = cache_rate
    service._extract_llm_usage = Mock(
        side_effect=AssertionError("SDK usage defaults must not be observed")
    )
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("container", INVALID_CONTAINERS)
@pytest.mark.parametrize("cache_bucket", ["cache_write_per_1m", "cache_read_per_1m"])
@pytest.mark.parametrize("cache_rate", [2000, None])
async def test_unavailable_container_cannot_erase_cache_chargeability__b102(
    monkeypatch, provider, model, container, cache_bucket, cache_rate
):
    body = container_body(provider, container)
    calls = setup_transport(monkeypatch, body)
    service = zero_core_service(provider, model, cache_bucket, cache_rate)
    ledger = Ledger("1")
    try:
        try:
            result = await invoke(service, provider, model, ledger)
        except LLMServiceError:
            result = None
        row = ledger.rows["1"]
        assert row.cost_usd is None
        assert row.usage.input_tokens is row.usage.output_tokens is None
        assert row.usage.cache_creation_input_tokens is None
        assert row.usage.cache_read_input_tokens is None
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        if result is not None:
            assert result.usage == row.usage
            assert result.cost is None
        service._extract_llm_usage.assert_not_called()
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("container", [{}, "core_counts"])
@pytest.mark.parametrize("cache_bucket", ["cache_write_per_1m", "cache_read_per_1m"])
@pytest.mark.parametrize("cache_rate", [2000, None])
async def test_valid_container_optional_cache_omission_stays_priceable__b102(
    monkeypatch, provider, model, container, cache_bucket, cache_rate
):
    if container == "core_counts":
        _, input_key, output_key = KEYS[provider]
        container = {input_key: 10, output_key: 10}
    body = container_body(provider, container)
    calls = setup_transport(monkeypatch, body)
    service = zero_core_service(provider, model, cache_bucket, cache_rate)
    ledger = Ledger("1")
    try:
        try:
            result = await invoke(service, provider, model, ledger)
        except LLMServiceError:
            if container:
                raise
            result = None
        row = ledger.rows["1"]
        assert row.cost_usd == Decimal(0)
        assert row.usage.cache_creation_input_tokens is None
        assert row.usage.cache_read_input_tokens is None
        if result is not None:
            assert result.usage == row.usage
            assert result.cost.total_cost == Decimal(0)
        service._extract_llm_usage.assert_not_called()
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()
