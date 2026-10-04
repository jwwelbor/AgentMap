"""B102: cached governed clients send the selected account credential."""

from unittest.mock import Mock, patch

import httpx
import pytest

from agentmap.services.llm.cost_calculator import LLMCostCalculator
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import Ledger
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle_boundaries import (
    fallback_service,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
    real_service,
    setup_transport,
)


def wire_credential(provider, request):
    if provider == "openai":
        return request.headers.get("authorization")
    if provider == "anthropic":
        return request.headers.get("x-api-key")
    return request.headers.get("x-goog-api-key") or request.url.params.get("key")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("reverse", [False, True])
async def test_direct_calls_send_each_complete_credential__b102(
    provider, model, reverse, monkeypatch
):
    keys = ["same-pre-first-account", "same-pre-other-account"]
    if reverse:
        keys.reverse()
    calls = setup_transport(monkeypatch, body_for(provider))
    service = real_service(provider, model)
    outcomes = []
    for key in keys:
        service._provider_utils.get_provider_config = Mock(
            return_value={"api_key": key, "model": model}
        )
        ledger = Ledger("1")
        await invoke(service, provider, model, ledger)
        outcomes.append(ledger.rows["1"])
    assert len(calls) == 2
    for request, key in zip(calls, keys):
        expected = f"Bearer {key}" if provider == "openai" else key
        assert wire_credential(provider, request) == expected
    assert all(key not in repr(service._client_factory._clients) for key in keys)
    assert all(key not in repr(outcome) for key in keys for outcome in outcomes)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("reverse", [False, True])
async def test_real_fallback_sends_selected_complete_credential__b102(
    provider, model, reverse, monkeypatch
):
    keys = ["same-pre-first-account", "same-pre-other-account"]
    if reverse:
        keys.reverse()
    primary = "anthropic" if provider != "anthropic" else "openai"
    primary_model = "claude-sonnet-4-5" if primary == "anthropic" else "gpt-4o-mini"
    calls = []

    async def send(transport, request):
        calls.append(request)
        destination = request.url.host
        actual = (
            "anthropic"
            if "anthropic" in destination
            else "google" if "google" in destination else "openai"
        )
        return httpx.Response(200, content=body_for(actual))

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    service = fallback_service(Mock())
    service._client_factory = LLMClientFactory(Mock())
    routing = service._fallback_handler.routing_config
    routing.fallback = {"default_provider": provider}
    routing.routing_matrix = {
        primary: {"low": primary_model},
        provider: {"low": model},
    }
    service._cost_calculator = LLMCostCalculator(
        {
            "models": {
                name: {name_model: {"input_per_1m": 10000, "output_per_1m": 10000}}
                for name, name_model in [(primary, primary_model), (provider, model)]
            }
        },
        Mock(),
    )
    outcomes = []
    for key in keys:
        service._provider_utils.get_provider_config = Mock(
            side_effect=lambda requested, selected=key: {
                "api_key": selected if requested == provider else "primary-key",
                "model": model if requested == provider else primary_model,
                "max_tokens": 23,
            }
        )
        ledger = Ledger("1")
        with patch(
            "agentmap.services.llm_service.normalize_response_content",
            side_effect=[RuntimeError("connection timeout"), ("fallback", "text")],
        ):
            result = await service.call_llm_async(
                [{"role": "user", "content": "offline"}],
                provider=primary,
                model=primary_model,
                attempt_lifecycle=ledger,
            )
            assert result.text == "fallback"
        outcomes.extend(ledger.rows.values())
    assert len(calls) == 4
    for request, key in zip(calls[1::2], keys):
        expected = f"Bearer {key}" if provider == "openai" else key
        assert wire_credential(provider, request) == expected
    expected_primary = "Bearer primary-key" if primary == "openai" else "primary-key"
    assert all(
        wire_credential(primary, request) == expected_primary for request in calls[::2]
    )
    assert all(key not in repr(service._client_factory._clients) for key in keys)
    assert all(key not in repr(outcome) for key in keys for outcome in outcomes)
