"""B102: SDK retries cannot multiply a governed AgentMap attempt."""

from unittest.mock import Mock

import httpx
import pytest

from agentmap.exceptions import LLMDependencyError
from agentmap.services.llm_client_factory import LLMClientFactory


@pytest.mark.parametrize(
    "provider,model,attempts",
    [
        ("openai", "gpt-4o-mini", 0),
        ("anthropic", "claude-sonnet-4-5", 0),
        ("google", "gemini-2.5-flash", 1),
    ],
)
@pytest.mark.parametrize("governed_first", [True, False])
def test_governed_retry_policy_has_its_own_cached_client__b102(
    provider, model, attempts, governed_first
):
    factory = LLMClientFactory(Mock())
    config = {"api_key": "offline-test-key", "model": model}
    first = factory.get_or_create_client(provider, config, governed=governed_first)
    second = factory.get_or_create_client(provider, config, governed=not governed_first)
    governed, plain = (first, second) if governed_first else (second, first)
    assert governed is not plain
    assert governed.max_retries == attempts
    assert plain.max_retries != attempts
    assert factory.get_or_create_client(provider, config, governed=True) is governed
    assert factory.get_or_create_client(provider, config) is plain


@pytest.mark.parametrize(
    "provider,model",
    [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-sonnet-4-5"),
        ("google", "gemini-2.5-flash"),
    ],
)
@pytest.mark.parametrize("governed", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_same_prefix_credentials_get_distinct_cached_clients__b102(
    provider, model, governed, reverse
):
    factory = LLMClientFactory(Mock())
    keys = ["same-pre-first-account", "same-pre-other-account"]
    if reverse:
        keys.reverse()
    configs = [{"api_key": key, "model": model} for key in keys]
    first, second = [
        factory.get_or_create_client(provider, config, governed=governed)
        for config in configs
    ]
    assert first is not second
    assert (
        factory.get_or_create_client(provider, configs[0], governed=governed) is first
    )
    assert (
        factory.get_or_create_client(provider, configs[1], governed=governed) is second
    )
    assert all(key not in repr(tuple(factory._clients)) for key in keys)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider,model",
    [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-sonnet-4-5"),
        ("google", "gemini-2.5-flash"),
    ],
)
@pytest.mark.parametrize("status", [429, 500])
async def test_real_governed_wrapper_sends_one_http_request_on_retryable_error__b102(
    provider,
    model,
    status,
    monkeypatch,
):
    calls = []

    async def send(client, request, **kwargs):
        calls.append(request)
        return httpx.Response(
            status,
            request=request,
            json={
                "error": {
                    "code": status,
                    "message": "offline retryable failure",
                    "type": "rate_limit_error",
                }
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    # Choose the SDK's httpx transport so the fake intercepts every request.
    monkeypatch.setattr("google.genai._api_client.has_aiohttp", False)
    factory = LLMClientFactory(Mock())
    client = factory.get_or_create_client(
        provider, {"api_key": "offline-test-key", "model": model}, governed=True
    )
    with pytest.raises(Exception):
        await client.ainvoke("synthetic request")
    assert len(calls) == 1


def test_governed_google_rejects_wrapper_with_unverified_retry_semantics__b102(
    monkeypatch,
):
    monkeypatch.setattr("importlib.metadata.version", lambda name: "3.2.0")
    factory = LLMClientFactory(Mock())
    with pytest.raises(LLMDependencyError, match="single-dispatch"):
        factory.get_or_create_client(
            "google",
            {"api_key": "offline-test-key", "model": "gemini-2.5-flash"},
            governed=True,
        )
