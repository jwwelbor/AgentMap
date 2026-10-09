"""B102 cleanup retains caller cancellation and every cleanup failure."""

import asyncio
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMLifecycleCleanupError
from agentmap.services.llm.observed_clients import ObservedResources
from agentmap.services.llm_client_factory import LLMClientFactory


class ControlFlowFailure(BaseException):
    pass


def flattened(error: BaseException) -> list[BaseException]:
    results = []
    if isinstance(error, LLMLifecycleCleanupError):
        for cause in error.failures:
            results.extend(flattened(cause))
    elif isinstance(error, BaseExceptionGroup):
        for cause in error.exceptions:
            results.extend(flattened(cause))
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
    with pytest.raises(LLMLifecycleCleanupError) as caught:
        await owner.aclose()
    terminal = flattened(caught.value)
    assert any(isinstance(error, asyncio.CancelledError) for error in terminal)
    assert failure in terminal
    assert owner.sync == [] and len(owner.async_) == 2


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
    with pytest.raises(LLMLifecycleCleanupError) as caught:
        await factory.shutdown()
    terminal = flattened(caught.value)
    assert any(isinstance(error, asyncio.CancelledError) for error in terminal)
    assert failure in terminal
    assert len(factory._owners) == 2


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
    with pytest.raises(LLMLifecycleCleanupError) as caught:
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
            await asyncio.wait_for(release.wait(), timeout=10)
            raise failure

    owner.create_async(FailedAfterRelease)
    close = asyncio.create_task(owner.aclose())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        close.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await close
        assert isinstance(caught.value.__cause__, LLMLifecycleCleanupError)
        assert failure in flattened(caught.value.__cause__)
    finally:
        release.set()
        if not close.done():
            close.cancel()
        await asyncio.gather(close, return_exceptions=True)


@pytest.mark.asyncio
async def test_sync_terminal_failures_do_not_skip_later_resources__b102():
    owner = ObservedResources()
    cancellation = asyncio.CancelledError("sync cancellation")
    grouped = BaseExceptionGroup("sync group", [RuntimeError("sync failure")])
    closed: list[str] = []

    class Failed:
        def __init__(self, error):
            self.error = error

        def close(self):
            raise self.error

    class LaterSync:
        def close(self):
            closed.append("sync")

    class LaterAsync:
        async def aclose(self):
            closed.append("async")

    owner.create_sync(lambda: Failed(cancellation))
    owner.create_sync(lambda: Failed(grouped))
    owner.create_sync(LaterSync)
    owner.create_async(LaterAsync)
    with pytest.raises(LLMLifecycleCleanupError) as caught:
        await owner.aclose()
    assert cancellation in caught.value.failures
    assert grouped in caught.value.failures
    assert closed == ["sync", "async"]
    with pytest.raises(LLMLifecycleCleanupError) as repeated:
        await owner.aclose()
    assert repeated.value is caught.value
    assert closed == ["sync", "async"]


@pytest.mark.asyncio
async def test_raw_control_flow_failures_do_not_skip_later_resources__b102():
    owner = ObservedResources()
    sync_failure = ControlFlowFailure("sync control flow")
    async_failure = ControlFlowFailure("async control flow")
    closed = []

    class FailedSync:
        def close(self):
            raise sync_failure

    class FailedAsync:
        async def aclose(self):
            raise async_failure

    class LaterSync:
        def close(self):
            closed.append("sync")

    class LaterAsync:
        async def aclose(self):
            closed.append("async")

    owner.create_sync(FailedSync)
    owner.create_sync(LaterSync)
    owner.create_async(FailedAsync)
    owner.create_async(LaterAsync)
    with pytest.raises(LLMLifecycleCleanupError) as caught:
        await owner.aclose()

    assert sync_failure in caught.value.failures
    assert async_failure in caught.value.failures
    assert closed == ["sync", "async"]


@pytest.mark.asyncio
async def test_factory_raw_owner_failure_does_not_skip_later_owner__b102():
    factory = LLMClientFactory(Mock())
    failure = ControlFlowFailure("owner control flow")
    closed = []

    class FailedOwner:
        async def aclose(self):
            raise failure

    class LaterOwner:
        async def aclose(self):
            closed.append(True)

    factory._owners = [FailedOwner(), LaterOwner()]
    with pytest.raises(LLMLifecycleCleanupError) as caught:
        await factory.shutdown()

    assert failure in caught.value.failures
    assert closed == [True]


@pytest.mark.asyncio
async def test_construction_control_flow_failure_closes_partial_owner__b102(
    monkeypatch,
):
    factory = LLMClientFactory(Mock())
    failure = ControlFlowFailure("construction control flow")
    closed = []

    class Resource:
        async def aclose(self):
            closed.append(True)

    def build(*args, owner, **kwargs):
        owner.create_async(Resource)
        raise failure

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    with pytest.raises(ControlFlowFailure) as caught:
        await factory.get_or_create_governed_client("openai", {"api_key": "key"})

    assert caught.value is failure
    assert closed == [True]
    assert factory._owners == []
