"""B102 cleanup continues after its caller is cancelled."""

import asyncio
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm.observed_clients import ObservedResources
from agentmap.services.llm_client_factory import LLMClientFactory


@pytest.mark.asyncio
async def test_resource_owner_retries_when_task_factory_rejects_cleanup__b102():
    owner = ObservedResources()
    closed = []

    class Resource:
        async def aclose(self):
            closed.append("resource")

    owner.create_async(Resource)
    loop = asyncio.get_running_loop()
    previous_factory = loop.get_task_factory()

    def reject_task(loop, coroutine, context=None):
        raise RuntimeError("task factory unavailable")

    loop.set_task_factory(reject_task)
    try:
        with pytest.raises(RuntimeError, match="task factory unavailable"):
            await owner.aclose()
    finally:
        loop.set_task_factory(previous_factory)

    assert owner._state == "closing"
    assert closed == []
    with pytest.raises(LLMConfigurationError, match="owner is shut down"):
        owner.create_async(object)
    await owner.aclose()
    assert owner._state == "closed"
    assert closed == ["resource"]


@pytest.mark.asyncio
async def test_factory_retries_shutdown_when_task_factory_rejects_it__b102():
    factory = LLMClientFactory(Mock())
    loop = asyncio.get_running_loop()
    previous_factory = loop.get_task_factory()

    def reject_task(loop, coroutine, context=None):
        raise RuntimeError("task factory unavailable")

    loop.set_task_factory(reject_task)
    try:
        with pytest.raises(RuntimeError, match="task factory unavailable"):
            await factory.shutdown()
    finally:
        loop.set_task_factory(previous_factory)

    assert factory._closing
    assert not factory._closed
    assert factory._shutdown_task is None
    await factory.shutdown()
    assert factory._closed


@pytest.mark.asyncio
async def test_owner_cleanup_finishes_after_caller_cancellation__b102():
    owner = ObservedResources()
    entered, release = asyncio.Event(), asyncio.Event()
    closed: list[str] = []

    class First:
        async def aclose(self):
            entered.set()
            await asyncio.wait_for(release.wait(), timeout=10)
            closed.append("first")

    class Second:
        async def aclose(self):
            closed.append("second")

    owner.create_async(First)
    owner.create_async(Second)
    close = asyncio.create_task(owner.aclose())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        close.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await close
        assert closed == ["first", "second"]
    finally:
        release.set()
        if not close.done():
            close.cancel()
        await asyncio.gather(close, return_exceptions=True)


@pytest.mark.asyncio
async def test_factory_cleanup_finishes_after_caller_cancellation__b102():
    factory = LLMClientFactory(Mock())
    entered, release = asyncio.Event(), asyncio.Event()
    closed: list[str] = []

    class FirstOwner:
        async def aclose(self):
            entered.set()
            await asyncio.wait_for(release.wait(), timeout=10)
            closed.append("first")

    class LaterOwner:
        async def aclose(self):
            closed.append("later")

    factory._owners = [FirstOwner(), LaterOwner()]
    shutdown = asyncio.create_task(factory.shutdown())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        shutdown.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await shutdown
        assert closed == ["first", "later"]
        await factory.shutdown()
        assert closed == ["first", "later"]
    finally:
        release.set()
        if not shutdown.done():
            shutdown.cancel()
        await asyncio.gather(shutdown, return_exceptions=True)
        await factory.shutdown()
