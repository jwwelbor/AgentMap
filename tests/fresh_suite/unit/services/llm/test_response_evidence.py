"""B102 supplement: real wrappers retain entity bytes before SDK parsing."""

import json
from unittest.mock import Mock

import httpx
import pytest
import pytest_asyncio

from agentmap.models.llm_attempt import LLMAttemptOutcome
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    Ledger,
    service_with_client,
)

PROVIDERS = [
    ("openai", "gpt-4o-mini"),
    ("anthropic", "claude-sonnet-4-5"),
    ("google", "gemini-2.5-flash"),
]


def body_for(provider, text="body-secret café"):
    if provider == "openai":
        data = {
            "id": "chatcmpl-offline",
            "object": "chat.completion",
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }
    elif provider == "anthropic":
        data = {
            "id": "msg-offline",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-5",
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        }
    else:
        data = {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": text}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 10,
                "totalTokenCount": 20,
            },
        }
    data["unknown_provider_field"] = {"null": None, "opaque": "retained"}
    return (" \n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()


def setup_transport(monkeypatch, body, status=200):
    import aiohttp

    async def refuse_network(*args, **kwargs):
        raise AssertionError("offline regression attempted unstubbed aiohttp request")

    # Safety only: don't force Google's backend. Its production transport must
    # select HTTPX itself, or the fake-HTTP request-count assertion fails.
    monkeypatch.setattr(aiohttp.ClientSession, "_request", refuse_network)
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(
            status,
            content=body,
            headers={
                "content-type": "application/json; charset=utf-8",
                "x-private-secret": "header-secret",
            },
        )

    def send(transport, request):
        return response(request)

    async def asend(transport, request):
        return response(request)

    # Lowest network seam only. Real HTTPX clients, SDKs, and wrappers run.
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", send)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", asend)
    return calls


def real_service(provider, model):
    service = service_with_client(Mock())
    factory = LLMClientFactory(Mock())
    service._client_factory = factory
    service._get_provider_config = Mock(
        return_value={"api_key": "authorization-secret", "model": model}
    )
    return service


@pytest_asyncio.fixture(name="real_service_factory_fixture")
async def real_service_factory_fixture():
    services = []

    def create(provider, model):
        service = real_service(provider, model)
        services.append(service)
        return service

    yield create
    for service in services:
        await service.shutdown()


async def invoke(service, provider, model, ledger):
    return await service.call_llm_async(
        messages=[{"role": "user", "content": "synthetic request"}],
        provider=provider,
        model=model,
        attempt_lifecycle=ledger,
    )


def test_missing_response_is_explicitly_unavailable__b102():
    outcome = LLMAttemptOutcome(classification="timeout")
    evidence = getattr(outcome, "response_evidence", None)
    assert evidence is not None, "each physical outcome needs response evidence"
    assert evidence.status == "unavailable"
    assert evidence.body is None
    assert evidence.unavailable_reason == "no_response"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_real_wrapper_preserves_exact_preparse_body__b102(
    provider, model, monkeypatch, real_service_factory_fixture
):
    body = body_for(provider)
    calls = setup_transport(monkeypatch, body)
    service = real_service_factory_fixture(provider, model)
    ledger = Ledger("1")
    result = await invoke(service, provider, model, ledger)
    assert result.text == "body-secret café"
    assert len(calls) == 1
    outcome = ledger.rows["1"]
    evidence = getattr(outcome, "response_evidence", None)
    assert evidence is not None, "SDK-normalized messages are not transport evidence"
    assert evidence.body == body
    assert evidence.status == "available"
    assert evidence.layer == "http_entity_body"
    assert evidence.http_status == 200
    assert evidence.media_type == "application/json"
    assert evidence.unavailable_reason is None
    assert "body-secret" not in repr(outcome)
    assert "header-secret" not in repr(outcome)
    assert "authorization-secret" not in repr(outcome)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize(
    "body,status", [(b"{invalid json", 200), (b"plain error body", 500)]
)
async def test_sdk_error_still_settles_exact_response_body__b102(
    provider, model, body, status, monkeypatch, real_service_factory_fixture
):
    calls = setup_transport(monkeypatch, body, status)
    ledger = Ledger()
    with pytest.raises(Exception):
        await invoke(
            real_service_factory_fixture(provider, model), provider, model, ledger
        )
    assert len(calls) == 1
    evidence = getattr(ledger.rows["1"], "response_evidence", None)
    assert evidence is not None, "SDK parse failure must retain its received body"
    assert evidence.status == "available"
    assert evidence.body == body
    assert evidence.http_status == status


@pytest.mark.asyncio
async def test_observer_failure_keeps_known_usage_then_refuses__b102(
    monkeypatch, real_service_factory_fixture
):
    from agentmap.exceptions import ResponseCaptureFailure
    from agentmap.services.llm import response_observer

    calls = setup_transport(monkeypatch, body_for("openai"))
    monkeypatch.setattr(
        response_observer, "_evidence", Mock(side_effect=ValueError("observer-secret"))
    )
    ledger = Ledger()
    service = real_service_factory_fixture("openai", "test-model")
    with pytest.raises(ResponseCaptureFailure, match="capture failed"):
        await invoke(service, "openai", "test-model", ledger)
    assert len(calls) == 1
    assert ledger.rows["1"].cost_usd is not None
    assert ledger.rows["1"].usage.input_tokens == 10
    assert ledger.rows["1"].response_evidence.body == body_for("openai")
    assert ledger.rows["1"].classification == "capture_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_error_body_is_not_exported_in_error_or_logs__b102(
    provider, model, monkeypatch, real_service_factory_fixture
):
    from agentmap.exceptions import LLMResolvedCallError

    body = b'{"error": {"message": "body-secret", "type": "invalid_request_error", "code": 400}}'
    calls = setup_transport(monkeypatch, body, 400)
    service = real_service_factory_fixture(provider, model)
    ledger = Ledger()
    with pytest.raises(LLMResolvedCallError) as caught:
        await invoke(service, provider, model, ledger)
    assert len(calls) == 1
    assert ledger.rows["1"].response_evidence.body == body
    assert "body-secret" not in str(caught.value)
    assert "body-secret" not in str(service._logger.mock_calls)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "available"},
        {"status": "unavailable", "body": b"wrong"},
        {"status": "partial", "body": b"partial", "unavailable_reason": None},
        {"status": "available", "body": "text", "unavailable_reason": None},
        {"status": "unavailable", "unavailable_reason": "secret arbitrary reason"},
    ],
)
def test_inconsistent_response_evidence_is_rejected__b102(kwargs):
    from agentmap.models.llm_attempt import LLMResponseEvidence

    with pytest.raises((TypeError, ValueError)):
        LLMResponseEvidence(**kwargs)
