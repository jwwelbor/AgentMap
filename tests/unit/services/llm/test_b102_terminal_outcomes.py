"""B102 cleanup retains caller cancellation and every cleanup failure."""

import asyncio
from unittest.mock import Mock

import pytest

from agentmap.services.llm.observed_clients import ObservedResources
from agentmap.services.llm_client_factory import LLMClientFactory


def flattened(group: BaseExceptionGroup) -> list[BaseException]:
    results = []
    for error in group.exceptions:
        if isinstance(error, BaseExceptionGroup):
            results.extend(flattened(error))
        else:
            results.append(error)
    return results


@pytest.mark.asyncio
async def test_resource_cancellation_and_failure_are_both_reported__b102():
    owner = ObservedResources()
    failure = RuntimeError("offline resource cleanup failure")

    class Cancelled:
        async def aclose(self):
            raise asyncio.CancelledError("resource cancelled")

    class Failed:
        async def aclose(self):
            raise failure

    owner.create_async(Cancelled)
    owner.create_async(Failed)
    with pytest.raises(BaseExceptionGroup) as caught:
        await owner.aclose()
    terminal = flattened(caught.value)
    assert any(isinstance(error, asyncio.CancelledError) for error in terminal)
    assert failure in terminal


@pytest.mark.asyncio
async def test_factory_owner_cancellation_and_failure_are_both_reported__b102():
    factory = LLMClientFactory(Mock())
    failure = RuntimeError("offline owner cleanup failure")

    class Cancelled:
        async def aclose(self):
            raise asyncio.CancelledError("owner cancelled")

    class Failed:
        async def aclose(self):
            raise failure

    factory._owners = [Cancelled(), Failed()]
    with pytest.raises(BaseExceptionGroup) as caught:
        await factory.shutdown()
    terminal = flattened(caught.value)
    assert any(isinstance(error, asyncio.CancelledError) for error in terminal)
    assert failure in terminal


@pytest.mark.asyncio
async def test_nested_mixed_owner_failure_does_not_skip_later_owner__b102():
    factory = LLMClientFactory(Mock())
    mixed = ObservedResources()
    later_closed = []

    class Cancelled:
        async def aclose(self):
            raise asyncio.CancelledError("resource cancelled")

    class Failed:
        async def aclose(self):
            raise RuntimeError("offline resource cleanup failure")

    class LaterOwner:
        async def aclose(self):
            later_closed.append(True)

    mixed.create_async(Cancelled)
    mixed.create_async(Failed)
    factory._owners = [mixed, LaterOwner()]
    with pytest.raises(BaseExceptionGroup) as caught:
        await factory.shutdown()
    terminal = flattened(caught.value)
    assert any(isinstance(error, asyncio.CancelledError) for error in terminal)
    assert any(isinstance(error, RuntimeError) for error in terminal)
    assert later_closed == [True]


@pytest.mark.asyncio
async def test_caller_cancellation_retains_cleanup_failure_as_cause__b102():
    owner = ObservedResources()
    entered, release = asyncio.Event(), asyncio.Event()
    failure = RuntimeError("offline cleanup failure")

    class FailedAfterRelease:
        async def aclose(self):
            entered.set()
            await release.wait()
            raise failure

    owner.create_async(FailedAfterRelease)
    close = asyncio.create_task(owner.aclose())
    await entered.wait()
    close.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError) as caught:
        await close
    assert isinstance(caught.value.__cause__, ExceptionGroup)
    assert failure in caught.value.__cause__.exceptions
