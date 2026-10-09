"""B102 observed clients have one explicit, awaited resource owner."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import AsyncMock, MagicMock, Mock

import httpx
import pytest

from agentmap.exceptions import LLMConfigurationError, LLMLifecycleCleanupError
from agentmap.services.llm.observed_clients import observed_http_clients
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    Ledger,
)
from tests.fresh_suite.unit.services.llm.test_response_evidence import (
    PROVIDERS,
    body_for,
    invoke,
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
    client = await factory.get_or_create_governed_client(provider, config(model))
    assert (
        await factory.get_or_create_governed_client(provider, config(model)) is client
    )
    assert client.invoke("offline").content
    assert (await client.ainvoke("offline")).content
    with pytest.raises(LLMConfigurationError, match="shutdown"):
        factory.clear_cache()
    assert (
        await factory.get_or_create_governed_client(provider, config(model)) is client
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
    client = await factory.get_or_create_governed_client(
        "google", config("gemini-2.5-flash")
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
    await factory.get_or_create_governed_client("openai", config("gpt-4o-mini"))
    owner = factory._owners[0]
    closed = []
    sync_attempts = []

    def fail_sync_close():
        sync_attempts.append(True)
        raise RuntimeError("offline close failed")

    async def record_async_close():
        closed.append(True)

    monkeypatch.setattr(owner.sync[0], "close", fail_sync_close)
    monkeypatch.setattr(owner.async_[0], "aclose", record_async_close)
    with pytest.raises(LLMLifecycleCleanupError) as first:
        await factory.shutdown()
    assert closed == [True]
    assert first.value.stage == "factory_shutdown"
    assert factory._owners == [owner]
    assert len(owner.sync) == 1
    assert owner.async_ == []
    assert len(factory._clients) == 1
    assert factory._closed is False
    with pytest.raises(LLMLifecycleCleanupError):
        await factory.shutdown()
    assert len(sync_attempts) == 1
    assert factory._owners == [owner]
    with pytest.raises(LLMLifecycleCleanupError):
        factory.begin_governed_invocation()


@pytest.mark.asyncio
async def test_httpx_inner_close_failure_keeps_factory_owner_terminal__b102(
    monkeypatch,
):
    factory = LLMClientFactory(Mock())
    await factory.get_or_create_governed_client("openai", config("gpt-4o-mini"))
    owner = factory._owners[0]
    sync_client = owner.sync[0]
    observed_transport = sync_client._transport
    inner_client = observed_transport._sync
    inner_transport = inner_client._transport
    original_close = httpx.HTTPTransport.close
    attempts = []
    failure = RuntimeError("offline HTTPX inner close failure")

    def fail_inner_close(transport):
        attempts.append(transport)
        raise failure

    monkeypatch.setattr(httpx.HTTPTransport, "close", fail_inner_close)
    try:
        with pytest.raises(LLMLifecycleCleanupError):
            await factory.shutdown()
        assert sync_client.is_closed
        assert factory._owners == [owner]
        assert owner.sync == [sync_client]
        assert owner.async_ == []
        with pytest.raises(LLMLifecycleCleanupError):
            await factory.shutdown()
        assert attempts == [inner_transport]
        assert observed_transport._sync is inner_client
        assert factory._owners == [owner]
    finally:
        original_close(inner_transport)


@pytest.mark.asyncio
async def test_service_shutdown_awaits_factory_owner__b102(monkeypatch):
    setup_transport(monkeypatch, body_for("openai"))
    service = real_service("openai", "gpt-4o-mini")
    factory = service._client_factory
    await factory.get_or_create_governed_client("openai", config("gpt-4o-mini"))
    await service.shutdown()
    assert factory._clients == {}
    assert factory._owners == []
    await service.shutdown()


@pytest.mark.asyncio
async def test_shutdown_refuses_while_governed_provider_call_uses_transport__b102(
    monkeypatch,
):
    body = body_for("openai")
    calls = []
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_response(transport, request):
        calls.append(request)
        entered.set()
        await asyncio.wait_for(release.wait(), timeout=10)
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": "application/json; charset=utf-8"},
        )

    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", blocked_response
    )
    closed = []
    original_aclose = httpx.AsyncHTTPTransport.aclose

    async def record_close(transport):
        closed.append(transport)
        await original_aclose(transport)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "aclose", record_close)
    service = real_service("openai", "gpt-4o-mini")
    ledger = Ledger("1")
    invocation = asyncio.create_task(invoke(service, "openai", "gpt-4o-mini", ledger))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        with pytest.raises(LLMConfigurationError, match="governed provider work"):
            await service.shutdown()
        assert closed == []
        assert len(calls) == 1
        release.set()
        response = await invocation
        assert response.text == "body-secret café"
        assert [event[0] for event in ledger.events] == ["begin", "settle"]
        await service.shutdown()
        assert len(closed) == 1
    finally:
        release.set()
        if not invocation.done():
            await invocation
        await service.shutdown()


@pytest.mark.asyncio
async def test_construction_rollback_failure_bypasses_fallback_and_telemetry_retry__b102(
    monkeypatch,
):
    service = real_service("openai", "gpt-4o-mini")
    factory = service._client_factory
    construction = RuntimeError("provider construction failed with secret text")

    class FailedOwnerResource:
        async def aclose(self):
            raise RuntimeError("resource close failed with private detail")

    def fail_construction(*args, owner, **kwargs):
        owner.create_async(FailedOwnerResource)
        raise construction

    monkeypatch.setattr(factory, "_create_langchain_client", fail_construction)
    service._features_registry = Mock()
    service.routing_config = Mock()
    service._fallback_handler.try_with_fallback_async = AsyncMock()
    service._telemetry_service = MagicMock()
    ledger = Ledger("1")

    with pytest.raises(LLMLifecycleCleanupError) as caught:
        await invoke(service, "openai", "gpt-4o-mini", ledger)

    assert caught.value.stage == "construction_rollback"
    assert "secret" not in str(caught.value)
    assert "private detail" not in str(caught.value)
    service._fallback_handler.try_with_fallback_async.assert_not_awaited()
    service._telemetry_service.start_span.assert_called_once()
    assert ledger.events == []
    assert factory._owners
    with pytest.raises(LLMLifecycleCleanupError):
        await service.shutdown()


@pytest.mark.asyncio
async def test_shutdown_refuses_until_governed_attempt_finalizes__b102(monkeypatch):
    setup_transport(monkeypatch, body_for("openai"))
    service = real_service("openai", "gpt-4o-mini")
    finalizing, release = asyncio.Event(), asyncio.Event()

    class BlockingLedger(Ledger):
        async def after_attempt(self, attempt_id, outcome):
            finalizing.set()
            await asyncio.wait_for(release.wait(), timeout=10)
            await super().after_attempt(attempt_id, outcome)

    ledger = BlockingLedger("1")
    invocation = asyncio.create_task(invoke(service, "openai", "gpt-4o-mini", ledger))
    try:
        await asyncio.wait_for(finalizing.wait(), 5)
        with pytest.raises(LLMConfigurationError, match="governed provider work"):
            await service.shutdown()
        assert not service._client_factory._closing
        assert len(service._client_factory._owners) == 1
        release.set()
        await invocation
        assert len(ledger.rows) == 1
        await service.shutdown()
    finally:
        release.set()
        if not invocation.done():
            await invocation
        await service.shutdown()


@pytest.mark.asyncio
async def test_invocation_and_shutdown_reservations_share_one_gate__b102():
    factory = LLMClientFactory(Mock())
    invocation = factory.begin_governed_invocation()
    with pytest.raises(LLMConfigurationError, match="governed provider work"):
        factory.prepare_shutdown()
    assert not factory._closing
    invocation.release()

    factory.prepare_shutdown()
    with pytest.raises(LLMConfigurationError, match="shut down"):
        factory.begin_governed_invocation()
    await factory.shutdown()


@pytest.mark.asyncio
async def test_lazy_anthropic_client_cannot_escape_closed_owner__b102(monkeypatch):
    calls = setup_transport(monkeypatch, body_for("anthropic"))
    factory = LLMClientFactory(Mock())
    client = await factory.get_or_create_governed_client(
        "anthropic", config("claude-sonnet-4-5")
    )
    await factory.shutdown()
    with pytest.raises(LLMConfigurationError, match="shut down"):
        await client.ainvoke("offline")
    assert calls == []
