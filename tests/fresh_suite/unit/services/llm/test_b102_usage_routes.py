"""All qualified routes consume the same shared accounting boundary."""

import json
from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest

from agentmap.models.llm_attempt import LLMResponseEvidence
from agentmap.models.llm_execution import LLMUsage
from agentmap.services.llm.cost_calculator import LLMCostCalculator
from agentmap.services.llm.usage_presence import (
    pricing_usage,
    provider_usage_presence,
    validate_usage_presence,
)
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    AccountingRefusal,
    Ledger,
)
from tests.fresh_suite.unit.services.llm.test_b102_observed_usage import (
    KEYS,
    changed_body,
    priced_service,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
    setup_transport,
)


def fallback_route(provider, model):
    from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle_boundaries import (
        fallback_service,
    )

    primary = "anthropic" if provider == "openai" else "openai"
    service = fallback_service(Mock())
    service._client_factory = LLMClientFactory(Mock())
    routing = service._fallback_handler.routing_config
    routing.fallback = {"default_provider": provider}
    routing.routing_matrix = {primary: {"low": "test-model"}, provider: {"low": model}}
    service._cost_calculator = LLMCostCalculator(
        {
            "models": {
                primary: {
                    "test-model": {"input_per_1m": 10000, "output_per_1m": 10000}
                },
                provider: {model: {"input_per_1m": 10000, "output_per_1m": 10000}},
            }
        },
        Mock(),
    )
    return service, primary


@pytest.mark.parametrize("provider", ["anthropic", "openai", "google"])
@pytest.mark.parametrize("body", [b"null", b"[]", b'"scalar"', b"0", b"true"])
def test_valid_non_object_json_has_no_observed_usage__b102(provider, body):
    evidence = LLMResponseEvidence(
        status="available", body=body, unavailable_reason=None
    )

    values = provider_usage_presence(provider, evidence)
    assert values == {"_container_unavailable": True}


def test_malformed_evidence_and_usage_containers_fail_closed__b102():
    malformed_evidence: Any = None
    malformed_values: Any = []

    assert provider_usage_presence("anthropic", malformed_evidence) is None
    assert provider_usage_presence("anthropic", object()) is None
    with pytest.raises(TypeError, match="usage measurements must be a mapping"):
        validate_usage_presence(malformed_values)
    assert (
        pricing_usage(
            LLMUsage(input_tokens=10, output_tokens=10),
            malformed_values,
            "anthropic",
            None,
        )
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_fallback_settles_unknown_core_usage_before_next_dispatch__b102(
    monkeypatch, provider, model
):
    service, primary = fallback_route(provider, model)
    bodies = [body_for(primary), changed_body(provider, "output_tokens", "absent")]
    calls = setup_transport(monkeypatch, bodies[0])

    async def send(transport, request):
        calls.append(request)
        return httpx.Response(200, content=bodies[len(calls) - 1])

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    ledger = Ledger("1")
    try:
        with patch(
            "agentmap.services.llm_service.normalize_response_content",
            side_effect=[RuntimeError("connection timeout"), ("fallback", "text")],
        ):
            result = await service.call_llm_async(
                messages=[{"role": "user", "content": "synthetic"}],
                provider=primary,
                model="test-model",
                attempt_lifecycle=ledger,
            )
        assert result.usage.output_tokens is result.cost is None
        assert ledger.rows["1"].cost_usd == Decimal("0.20")
        assert ledger.rows["2"].cost_usd is None
        assert ledger.rows["2"].usage.input_tokens == 10
        assert ledger.rows["2"].response_evidence.body == bodies[1]
        assert ledger.descriptions[1].attempt_kind == "fallback"
        assert ledger.descriptions[1].resolved_provider == provider
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 2
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("value", ["absent", None, 0, 10])
async def test_sync_wrapper_path_keeps_honest_core_accounting__b102(
    monkeypatch, provider, model, value
):
    body = changed_body(provider, "output_tokens", value)
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "output_tokens")
    client = await service._client_factory.get_or_create_governed_client(
        provider, {"api_key": "authorization-secret", "model": model}
    )
    monkeypatch.setattr(type(client), "ainvoke", None)
    ledger = Ledger("1")
    try:
        result = await invoke(service, provider, model, ledger)
        expected = value if type(value) is int else None
        assert (
            result.usage.output_tokens
            == ledger.rows["1"].usage.output_tokens
            == expected
        )
        assert ledger.rows["1"].cost_usd == (
            None if expected is None else Decimal("0.10") + Decimal(expected) / 100
        )
        assert ledger.rows["1"].response_evidence.body == body
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("container", ["absent", None, [], "bad"])
async def test_bad_usage_container_cannot_authorize_known_spend__b102(
    monkeypatch, provider, model, container
):
    payload = json.loads(body_for(provider))
    key = KEYS[provider][0]
    if container == "absent":
        payload.pop(key)
    else:
        payload[key] = container
    body = json.dumps(payload).encode()
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    ledger = Ledger("1")
    try:
        from agentmap.exceptions import LLMServiceError

        try:
            await invoke(service, provider, model, ledger)
        except LLMServiceError:
            pass
        row = ledger.rows["1"]
        assert row.cost_usd is None
        assert row.usage.input_tokens is row.usage.output_tokens is None
        assert row.response_evidence.body == body
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("body", [b"null", b"[]", b'"scalar"', b"0"])
async def test_non_object_json_response_preserves_unknown_spend_and_blocks_retry__b102(
    monkeypatch, provider, model, body
):
    calls = setup_transport(monkeypatch, body)
    service = priced_service(provider, model, "input_tokens")
    ledger = Ledger("1")
    try:
        from agentmap.exceptions import LLMServiceError

        try:
            await invoke(service, provider, model, ledger)
        except LLMServiceError:
            pass
        row = ledger.rows["1"]
        assert row.cost_usd is None
        assert row.usage.input_tokens is row.usage.output_tokens is None
        assert row.response_evidence.status == "available"
        assert row.response_evidence.body == body
        assert ledger.events == [("begin", "1"), ("settle", "1")]
        with pytest.raises(AccountingRefusal):
            await invoke(service, provider, model, ledger)
        assert len(calls) == len(ledger.rows) == 1
    finally:
        await service._client_factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_governed_receipt_never_reads_normalized_usage_defaults__b102(
    monkeypatch, provider, model
):
    calls = setup_transport(monkeypatch, body_for(provider))
    service = priced_service(provider, model, "input_tokens")
    service._extract_llm_usage = Mock(
        side_effect=AssertionError("normalized defaults consulted")
    )
    ledger = Ledger("1")
    try:
        result = await invoke(service, provider, model, ledger)
        assert result.usage == ledger.rows["1"].usage
        assert result.cost.total_cost == ledger.rows["1"].cost_usd == Decimal("0.20")
        service._extract_llm_usage.assert_not_called()
        assert len(calls) == 1
    finally:
        await service._client_factory.shutdown()
