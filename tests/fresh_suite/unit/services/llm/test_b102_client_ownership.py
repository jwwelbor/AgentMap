"""B102 observed clients have one explicit, awaited resource owner."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import httpx
import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm.observed_clients import observed_http_clients
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    real_service,
    setup_transport,
)


def config(model, key="same-prefix-first"):
    return {"model": model, "api_key": key}


def test_separate_observed_clients_own_one_matching_transport__b102():
    sync, async_client = observed_http_clients()
    try:
        assert hasattr(sync._transport, "_sync")
        assert not hasattr(sync._transport, "_async")
        assert hasattr(async_client._transport, "_async")
        assert not hasattr(async_client._transport, "_sync")
    finally:
        sync.close()
        asyncio.run(async_client.aclose())


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,model", PROVIDERS)
async def test_factory_shutdown_closes_each_observed_pool_once__b102(
    provider, model, monkeypatch
):
    setup_transport(monkeypatch, body_for(provider))
    factory = LLMClientFactory(Mock())
    sync_closed, async_closed = [], []
    original_sync = httpx.HTTPTransport.close
    original_async = httpx.AsyncHTTPTransport.aclose

    def close_sync(transport):
        sync_closed.append(transport)
        return original_sync(transport)

    async def close_async(transport):
        async_closed.append(transport)
        await original_async(transport)

    monkeypatch.setattr(httpx.HTTPTransport, "close", close_sync)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "aclose", close_async)
    client = factory.get_or_create_client(provider, config(model), governed=True)
    assert (
        factory.get_or_create_client(provider, config(model), governed=True) is client
    )
    assert client.invoke("offline").content
    assert (await client.ainvoke("offline")).content
    with pytest.raises(LLMConfigurationError, match="shutdown"):
        factory.clear_cache()
    assert (
        factory.get_or_create_client(provider, config(model), governed=True) is client
    )
    await factory.shutdown()
    assert len(sync_closed) == len(async_closed) == 1
    await factory.shutdown()
    assert len(sync_closed) == len(async_closed) == 1


def test_concurrent_first_construction_has_no_losing_client__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    entered, release = Event(), Event()
    created = []

    def build(*args, **kwargs):
        created.append(object())
        entered.set()
        assert release.wait(5)
        return created[-1]

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(factory.get_or_create_client, "openai", config("m"))
        assert entered.wait(5)
        second = pool.submit(factory.get_or_create_client, "openai", config("m"))
        release.set()
        assert first.result() is second.result()
    assert len(created) == 1


@pytest.mark.asyncio
async def test_google_shared_adapter_creates_only_used_mode__b102(monkeypatch):
    setup_transport(monkeypatch, body_for("google"))
    factory = LLMClientFactory(Mock())
    client = factory.get_or_create_client(
        "google", config("gemini-2.5-flash"), governed=True
    )
    transport = factory._owners[0].sync[0]
    assert transport._sync_client is None and transport._async_client is None
    assert (await client.ainvoke("offline")).content
    assert transport._sync_client is None and transport._async_client is not None
    await factory.shutdown()
    assert transport._sync_client is None and transport._async_client is None


@pytest.mark.asyncio
async def test_shutdown_reports_failure_and_closes_remaining_pool__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    factory.get_or_create_client("openai", config("gpt-4o-mini"), governed=True)
    owner = factory._owners[0]
    closed = []

    def fail_sync_close():
        raise RuntimeError("offline close failed")

    async def record_async_close():
        closed.append(True)

    monkeypatch.setattr(owner.sync[0], "close", fail_sync_close)
    monkeypatch.setattr(owner.async_[0], "aclose", record_async_close)
    with pytest.raises(ExceptionGroup, match="shutdown failed"):
        await factory.shutdown()
    assert closed == [True]
    assert factory._clients == {}
    await factory.shutdown()


@pytest.mark.asyncio
async def test_service_shutdown_awaits_factory_owner__b102(monkeypatch):
    setup_transport(monkeypatch, body_for("openai"))
    service = real_service("openai", "gpt-4o-mini")
    factory = service._client_factory
    factory.get_or_create_client("openai", config("gpt-4o-mini"), governed=True)
    await service.shutdown()
    assert factory._clients == {}
    assert factory._owners == []
    await service.shutdown()


@pytest.mark.asyncio
async def test_lazy_anthropic_client_cannot_escape_closed_owner__b102(monkeypatch):
    calls = setup_transport(monkeypatch, body_for("anthropic"))
    factory = LLMClientFactory(Mock())
    client = factory.get_or_create_client(
        "anthropic", config("claude-sonnet-4-5"), governed=True
    )
    await factory.shutdown()
    with pytest.raises(LLMConfigurationError, match="shut down"):
        await client.ainvoke("offline")
    assert calls == []
