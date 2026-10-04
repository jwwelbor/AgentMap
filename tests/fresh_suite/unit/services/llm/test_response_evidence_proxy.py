"""B102 governed wrappers retain proxy and bypass routing with body observation."""

from unittest.mock import Mock

import httpx
import pytest

from agentmap.services.llm.response_observer import (
    ResponseCollector,
    response_collector,
)
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
)


@pytest.fixture(autouse=True)
def refuse_unstubbed_aiohttp(monkeypatch):
    import aiohttp

    async def refuse(*args, **kwargs):
        raise AssertionError("unstubbed aiohttp request")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", refuse)


@pytest.mark.parametrize("provider,model", PROVIDERS)
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("bypass", [False, True])
@pytest.mark.asyncio
async def test_real_wrapper_observes_one_body_through_environment_proxy_or_bypass__b102(
    provider, model, asynchronous, bypass, monkeypatch
):
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
        "ANTHROPIC_PROXY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:8123")
    if bypass:
        monkeypatch.setenv("NO_PROXY", "*")
    routes = []
    body = body_for(provider)

    def send(transport, request):
        routes.append(type(transport._pool).__name__)
        return httpx.Response(200, content=body, request=request)

    async def asend(transport, request):
        return send(transport, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", send)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", asend)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        factory = LLMClientFactory(Mock())
        client = await factory.get_or_create_governed_client(
            provider, {"api_key": "offline-test-key", "model": model}
        )
        if asynchronous:
            await client.ainvoke("offline request")
        else:
            client.invoke("offline request")
    finally:
        response_collector.reset(token)
    assert len(routes) == 1
    assert ("Proxy" in routes[0]) is not bypass
    assert collector.seal().body == body
    await factory.shutdown()


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.asyncio
async def test_anthropic_explicit_proxy_keeps_observed_body__b102(
    asynchronous, monkeypatch
):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTHROPIC_PROXY", "http://explicit-proxy.invalid:8123")
    routes = []
    body = body_for("anthropic")

    def send(transport, request):
        routes.append(type(transport._pool).__name__)
        return httpx.Response(200, content=body, request=request)

    async def asend(transport, request):
        return send(transport, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", send)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", asend)
    collector = ResponseCollector()
    token = response_collector.set(collector)
    try:
        factory = LLMClientFactory(Mock())
        client = await factory.get_or_create_governed_client(
            "anthropic",
            {"api_key": "offline-test-key", "model": "claude-sonnet-4-5"},
        )
        if asynchronous:
            await client.ainvoke("offline request")
        else:
            client.invoke("offline request")
    finally:
        response_collector.reset(token)
    assert len(routes) == 1
    assert "Proxy" in routes[0]
    assert collector.seal().body == body
    await factory.shutdown()
