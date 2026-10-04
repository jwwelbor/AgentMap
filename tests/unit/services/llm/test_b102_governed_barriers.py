"""Deterministic barriers for B102 governed construction lifecycle races."""

import asyncio
from threading import Event
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm_client_factory import LLMClientFactory


def config(model: str) -> dict[str, str]:
    return {"model": model, "api_key": "offline-key"}


class AsyncResource:
    def __init__(self) -> None:
        self.closed = 0

    async def aclose(self) -> None:
        self.closed += 1


@pytest.mark.asyncio
async def test_repeated_cancellation_cannot_hide_build_from_shutdown__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    allocated, release = Event(), Event()
    resource = AsyncResource()

    def build(*args, owner, **kwargs):
        owner.create_async(lambda: resource)
        allocated.set()
        assert release.wait(5)
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    acquisition = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("m"))
    )
    assert await asyncio.to_thread(allocated.wait, 5)
    acquisition.cancel()
    asyncio.get_running_loop().call_soon(acquisition.cancel)
    await asyncio.sleep(0)
    shutdown = asyncio.create_task(factory.shutdown())
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await acquisition
    await shutdown
    assert resource.closed == 1
    assert factory._active_governed == set()


@pytest.mark.asyncio
async def test_clear_cache_refuses_while_owner_is_unpublished__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    ordinary = object()
    factory._clients["ordinary"] = ordinary
    allocated, release = Event(), Event()
    resource = AsyncResource()

    def build(*args, owner, **kwargs):
        owner.create_async(lambda: resource)
        allocated.set()
        assert release.wait(5)
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    acquisition = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("m"))
    )
    assert await asyncio.to_thread(allocated.wait, 5)
    with pytest.raises(LLMConfigurationError, match="awaited shutdown"):
        factory.clear_cache()
    assert factory._clients["ordinary"] is ordinary
    release.set()
    await acquisition
    await factory.shutdown()
    assert resource.closed == 1


@pytest.mark.asyncio
async def test_shutdown_barrier_precedes_inflight_publication__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    allocated, release = Event(), Event()
    shutdown_entered = asyncio.Event()

    def build(*args, owner, **kwargs):
        allocated.set()
        assert release.wait(5)
        return object()

    original_finish = factory._finish_shutdown

    async def marked_finish():
        shutdown_entered.set()
        await original_finish()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    monkeypatch.setattr(factory, "_finish_shutdown", marked_finish)
    acquisition = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("m"))
    )
    assert await asyncio.to_thread(allocated.wait, 5)
    shutdown = asyncio.create_task(factory.shutdown())
    await shutdown_entered.wait()
    release.set()
    with pytest.raises(LLMConfigurationError, match="shut down"):
        await acquisition
    await shutdown


@pytest.mark.asyncio
async def test_construction_and_rollback_failures_are_both_visible__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    construction = ValueError("offline construction failure")
    rollback = RuntimeError("offline rollback failure")

    class Resource:
        async def aclose(self):
            raise rollback

    def build(*args, owner, **kwargs):
        owner.create_async(Resource)
        raise construction

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    with pytest.raises(ExceptionGroup) as caught:
        await factory.get_or_create_governed_client("openai", config("m"))
    assert caught.value.exceptions[0] is construction
    assert rollback in caught.value.exceptions[1].exceptions
    assert factory._owners == [] and factory._clients == {}
    await factory.shutdown()
