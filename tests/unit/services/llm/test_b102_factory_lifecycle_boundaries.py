"""B102 governed construction and shutdown are one terminal transaction."""

import asyncio
from threading import Event
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm.observed_clients import ObservedResources
from agentmap.services.llm_client_factory import LLMClientFactory


def config(model: str) -> dict[str, str]:
    return {"model": model, "api_key": "offline-key"}


class SyncResource:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


class AsyncResource:
    def __init__(self) -> None:
        self.closed = 0

    async def aclose(self) -> None:
        self.closed += 1


@pytest.mark.asyncio
async def test_cache_clear_and_shutdown_release_credential_tokens__b102():
    factory = LLMClientFactory(Mock())
    first = {"model": "m", "api_key": "first-secret"}
    factory._cache_key("openai", first, False, False)
    assert set(factory._api_key_tokens) == {"first-secret"}

    factory.clear_cache()
    assert factory._api_key_tokens == {}

    factory._cache_key("openai", first, False, False)
    await factory.shutdown()
    assert factory._api_key_tokens == {}
    with pytest.raises(LLMConfigurationError, match="shut down"):
        factory.get_or_create_client(
            "openai", {"model": "m", "api_key": "late-sync-secret"}
        )
    with pytest.raises(LLMConfigurationError, match="shut down"):
        await factory.get_or_create_governed_client(
            "openai", {"model": "m", "api_key": "late-async-secret"}
        )
    assert factory._api_key_tokens == {}


@pytest.mark.asyncio
async def test_failed_construction_awaits_transactional_owner_rollback__b102(
    monkeypatch,
):
    factory = LLMClientFactory(Mock())
    sync, async_ = SyncResource(), AsyncResource()
    failure = ValueError("typed constructor failure")

    attempts = 0

    def fail_once(*args, owner, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            owner.create_sync(lambda: sync)
            owner.create_async(lambda: async_)
            raise failure
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", fail_once)
    with pytest.raises(ValueError) as caught:
        await factory.get_or_create_governed_client("openai", config("m"))
    assert caught.value is failure
    assert (sync.closed, async_.closed) == (1, 1)
    assert factory._owners == [] and factory._clients == {}
    assert await factory.get_or_create_governed_client("openai", config("m"))
    assert attempts == 2
    await factory.shutdown()


@pytest.mark.asyncio
async def test_same_key_governed_construction_has_one_owner__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    entered, release = Event(), Event()
    created: list[object] = []

    def build(*args, owner, **kwargs):
        created.append(object())
        entered.set()
        assert release.wait(5)
        return created[-1]

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    first = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("same"))
    )
    assert await asyncio.to_thread(entered.wait, 5)
    second = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("same"))
    )
    release.set()
    assert await first is await second
    assert len(created) == len(factory._owners) == 1
    await factory.shutdown()


@pytest.mark.asyncio
async def test_different_keys_construct_independently__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    entered = {"a": Event(), "b": Event()}
    release = Event()

    def build(provider, provider_config, *args, owner, **kwargs):
        entered[provider_config["model"]].set()
        assert release.wait(5)
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    first = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("a"))
    )
    second = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("b"))
    )
    assert await asyncio.to_thread(entered["a"].wait, 5)
    assert await asyncio.to_thread(entered["b"].wait, 5)
    release.set()
    assert await first is not await second
    await factory.shutdown()


@pytest.mark.asyncio
async def test_shutdown_wins_against_inflight_and_later_construction__b102(
    monkeypatch,
):
    factory = LLMClientFactory(Mock())
    entered, release = Event(), Event()
    shutdown_entered = asyncio.Event()
    resource = AsyncResource()

    def build(*args, owner, **kwargs):
        owner.create_async(lambda: resource)
        entered.set()
        assert release.wait(5)
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    original_finish = factory._finish_shutdown

    async def marked_finish():
        shutdown_entered.set()
        await original_finish()

    monkeypatch.setattr(factory, "_finish_shutdown", marked_finish)
    acquisition = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("m"))
    )
    assert await asyncio.to_thread(entered.wait, 5)
    shutdown = asyncio.create_task(factory.shutdown())
    await shutdown_entered.wait()
    release.set()
    with pytest.raises(LLMConfigurationError, match="shut down"):
        await acquisition
    await shutdown
    assert resource.closed == 1
    with pytest.raises(LLMConfigurationError, match="shut down"):
        await factory.get_or_create_governed_client("openai", config("later"))
    with pytest.raises(LLMConfigurationError, match="shut down"):
        factory.get_or_create_client("openai", config("ordinary"))


@pytest.mark.asyncio
async def test_owner_cleanup_finishes_after_caller_cancellation__b102():
    owner = ObservedResources()
    entered, release = asyncio.Event(), asyncio.Event()
    closed: list[str] = []

    class First:
        async def aclose(self):
            entered.set()
            await release.wait()
            closed.append("first")

    class Second:
        async def aclose(self):
            closed.append("second")

    owner.create_async(First)
    owner.create_async(Second)
    close = asyncio.create_task(owner.aclose())
    await entered.wait()
    close.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await close
    assert closed == ["first", "second"]
    await owner.aclose()
    assert closed == ["first", "second"]


@pytest.mark.asyncio
async def test_cleanup_continues_after_resource_cancellation__b102():
    owner = ObservedResources()
    closed: list[str] = []

    class Cancelled:
        async def aclose(self):
            raise asyncio.CancelledError()

    class Later:
        async def aclose(self):
            closed.append("later")

    owner.create_async(Cancelled)
    owner.create_async(Later)
    with pytest.raises(asyncio.CancelledError):
        await owner.aclose()
    assert closed == ["later"]
    await owner.aclose()
    assert closed == ["later"]


@pytest.mark.asyncio
async def test_factory_cleanup_continues_after_owner_cancellation__b102():
    factory = LLMClientFactory(Mock())
    closed: list[str] = []

    class CancelledOwner:
        async def aclose(self):
            raise asyncio.CancelledError()

    class LaterOwner:
        async def aclose(self):
            closed.append("later")

    factory._owners = [CancelledOwner(), LaterOwner()]
    with pytest.raises(asyncio.CancelledError):
        await factory.shutdown()
    assert closed == ["later"]
    await factory.shutdown()
    assert closed == ["later"]


@pytest.mark.asyncio
async def test_factory_cleanup_finishes_after_caller_cancellation__b102():
    factory = LLMClientFactory(Mock())
    entered, release = asyncio.Event(), asyncio.Event()
    closed: list[str] = []

    class FirstOwner:
        async def aclose(self):
            entered.set()
            await release.wait()
            closed.append("first")

    class LaterOwner:
        async def aclose(self):
            closed.append("later")

    factory._owners = [FirstOwner(), LaterOwner()]
    shutdown = asyncio.create_task(factory.shutdown())
    await entered.wait()
    shutdown.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await shutdown
    assert closed == ["first", "later"]
    await factory.shutdown()
    assert closed == ["first", "later"]
