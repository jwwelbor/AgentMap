"""Deterministic barriers for B102 governed construction lifecycle races."""

import asyncio
from threading import Event
from unittest.mock import Mock

import pytest

from agentmap import async_lifecycle
from agentmap.exceptions import LLMConfigurationError, LLMLifecycleCleanupError
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.runtime_manager_test_support import cancel_tasks_for_test


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
    first_seen, second_seen = Event(), Event()
    resource = AsyncResource()
    real_count = async_lifecycle._cancellation_count

    def observed_count(task):
        count = real_count(task)
        if count == 1:
            first_seen.set()
        elif count == 2:
            second_seen.set()
        return count

    def build(*args, owner, **kwargs):
        owner.create_async(lambda: resource)
        allocated.set()
        assert release.wait(5)
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    monkeypatch.setattr(async_lifecycle, "_cancellation_count", observed_count)
    acquisition = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("m"))
    )
    shutdown = None
    try:
        assert await asyncio.to_thread(allocated.wait, 5)
        acquisition.cancel()
        assert await asyncio.to_thread(first_seen.wait, 5)
        acquisition.cancel()
        assert await asyncio.to_thread(second_seen.wait, 5)
        shutdown = asyncio.create_task(factory.shutdown())
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await acquisition
        await shutdown
        assert resource.closed == 1
        assert factory._active_governed == set()
    finally:
        release.set()
        try:
            await cancel_tasks_for_test(acquisition, shutdown)
        finally:
            await factory.shutdown()


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
    try:
        assert await asyncio.to_thread(allocated.wait, 5)
        with pytest.raises(LLMConfigurationError, match="awaited shutdown"):
            factory.clear_cache()
        assert factory._clients["ordinary"] is ordinary
        release.set()
        await acquisition
    finally:
        release.set()
        try:
            await cancel_tasks_for_test(acquisition)
        finally:
            await factory.shutdown()
    assert resource.closed == 1


@pytest.mark.asyncio
async def test_shutdown_barrier_precedes_inflight_publication__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    allocated, release = Event(), Event()
    exited = Event()
    shutdown_entered = asyncio.Event()

    def build(*args, owner, **kwargs):
        allocated.set()
        try:
            assert release.wait(5)
            return object()
        finally:
            exited.set()

    original_finish = factory._finish_shutdown

    async def marked_finish():
        shutdown_entered.set()
        await original_finish()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    monkeypatch.setattr(factory, "_finish_shutdown", marked_finish)
    acquisition = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("m"))
    )
    shutdown = None
    try:
        assert await asyncio.to_thread(allocated.wait, 5)
        shutdown = asyncio.create_task(factory.shutdown())
        await asyncio.wait_for(shutdown_entered.wait(), timeout=5)
        release.set()
        with pytest.raises(LLMConfigurationError, match="shut down"):
            await acquisition
        await shutdown
    finally:
        release.set()
        if not acquisition.done():
            acquisition.cancel()
        if shutdown is not None and not shutdown.done():
            shutdown.cancel()
        await asyncio.gather(
            acquisition,
            *([shutdown] if shutdown is not None else []),
            return_exceptions=True,
        )
        if allocated.is_set():
            await asyncio.to_thread(exited.wait, 5)
        await factory.shutdown()


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
    with pytest.raises(LLMLifecycleCleanupError) as caught:
        await factory.get_or_create_governed_client("openai", config("m"))
    assert caught.value.stage == "construction_rollback"
    assert caught.value.failure_count == 2
    assert caught.value.failures[0] is construction
    assert factory._owners and factory._clients == {}
    with pytest.raises(LLMLifecycleCleanupError):
        factory.begin_governed_invocation()
    with pytest.raises(LLMLifecycleCleanupError):
        await factory.shutdown()
    assert factory._owners
