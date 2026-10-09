"""Loop-owned ordinary drain progresses without an executor waiter."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from agentmap.services.llm_client_factory import LLMClientFactory

CONFIG = {"model": "m", "api_key": "offline"}


def install_builder(monkeypatch, factory, loop):
    entered, registered = asyncio.Event(), asyncio.Event()
    release = Event()
    original = factory._wait_ordinary_drain

    def build(*args):
        loop.call_soon_threadsafe(entered.set)
        if not release.wait(5):
            raise TimeoutError("builder release missing")
        return object()

    async def drain():
        registered.set()
        await original()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    monkeypatch.setattr(factory, "_wait_ordinary_drain", drain)
    return entered, registered, release


@pytest.mark.asyncio
async def test_pending_shutdown_finishes_before_saturated_executor_is_released(
    monkeypatch,
):
    loop = asyncio.get_running_loop()
    factory = LLMClientFactory(Mock())
    entered, registered, release = install_builder(monkeypatch, factory, loop)
    occupied = asyncio.Event()
    unblock = Event()
    executor = ThreadPoolExecutor(max_workers=1)
    loop.set_default_executor(executor)

    def blocker():
        loop.call_soon_threadsafe(occupied.set)
        if not unblock.wait(5):
            raise TimeoutError("executor blocker release missing")

    blocked = loop.run_in_executor(None, blocker)
    with ThreadPoolExecutor(max_workers=1) as builders:
        construction = builders.submit(factory.get_or_create_client, "openai", CONFIG)
        try:
            await asyncio.wait_for(entered.wait(), 5)
            await asyncio.wait_for(occupied.wait(), 5)
            shutdown = asyncio.create_task(factory.shutdown())
            await asyncio.wait_for(registered.wait(), 5)
            assert factory._ordinary_waiter is not None
            release.set()
            await asyncio.wait_for(shutdown, 2)
            assert factory._closed and not unblock.is_set()
            assert not blocked.done()
            construction.result(timeout=5)
        finally:
            release.set()
            unblock.set()
            await asyncio.wait_for(blocked, 5)
            await asyncio.wait_for(factory.shutdown(), 5)
    executor.shutdown(wait=True)


@pytest.mark.asyncio
async def test_final_release_before_registration_needs_no_future(monkeypatch):
    loop = asyncio.get_running_loop()
    factory = LLMClientFactory(Mock())
    monkeypatch.setattr(factory, "_create_langchain_client", lambda *a: object())
    factory.get_or_create_client("openai", CONFIG)
    with monkeypatch.context() as patch:
        patch.setattr(
            loop,
            "create_future",
            Mock(side_effect=AssertionError("unexpected drain Future")),
        )
        await factory._wait_ordinary_drain()
    await factory.shutdown()
    assert factory._closed and factory._ordinary_waiter is None


@pytest.mark.asyncio
async def test_repeated_caller_cancellation_retains_registered_waiter(monkeypatch):
    loop = asyncio.get_running_loop()
    factory = LLMClientFactory(Mock())
    entered, registered, release = install_builder(monkeypatch, factory, loop)
    with ThreadPoolExecutor(max_workers=1) as builders:
        construction = builders.submit(factory.get_or_create_client, "openai", CONFIG)
        try:
            await asyncio.wait_for(entered.wait(), 5)
            caller = asyncio.create_task(factory.shutdown())
            await asyncio.wait_for(registered.wait(), 5)
            pair = factory._ordinary_waiter
            for _ in range(3):
                caller.cancel()
                await asyncio.sleep(0)
            assert factory._ordinary_waiter is pair
            assert not pair[1].done() and not factory._shutdown_task.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(caller, 5)
        construction.result(timeout=5)
        assert factory._ordinary_waiter is None and factory._closed


@pytest.mark.parametrize("start_coroutine", [False, True])
@pytest.mark.asyncio
async def test_rejected_shutdown_task_preserves_reservations_and_retries(
    monkeypatch, start_coroutine
):
    loop = asyncio.get_running_loop()
    factory = LLMClientFactory(Mock())
    entered, registered, release = install_builder(monkeypatch, factory, loop)
    rejected = []

    def reject(loop, coroutine, **kwargs):
        rejected.append(coroutine)
        if start_coroutine:
            coroutine.send(None)
        raise RuntimeError("task rejected")

    with ThreadPoolExecutor(max_workers=1) as builders:
        construction = builders.submit(factory.get_or_create_client, "openai", CONFIG)
        try:
            await asyncio.wait_for(entered.wait(), 5)
            loop.set_task_factory(reject)
            with pytest.raises(RuntimeError, match="task rejected"):
                await factory.shutdown()
            assert rejected[0].cr_frame is None
            assert factory._closing and factory._ordinary_pending == 1
            assert factory._ordinary_waiter is None
        finally:
            loop.set_task_factory(None)
            release.set()
        construction.result(timeout=5)
        await asyncio.wait_for(factory.shutdown(), 5)
        assert factory._closed


@pytest.mark.asyncio
async def test_stale_callback_cannot_complete_replacement_waiter():
    factory = LLMClientFactory(Mock())
    loop = asyncio.get_running_loop()
    old = (loop, loop.create_future())
    replacement = (loop, loop.create_future())
    old[1].cancel()
    factory._ordinary_waiter = replacement
    factory._complete_ordinary_drain(old)
    assert not replacement[1].done()
    factory._complete_ordinary_drain(replacement)
    assert replacement[1].done()
    factory._ordinary_waiter = None
    await factory.shutdown()


@pytest.mark.asyncio
async def test_eager_shutdown_uses_same_atomic_drain_registration(monkeypatch):
    if not hasattr(asyncio, "eager_task_factory"):
        pytest.skip("requires Python 3.12 eager task scheduling")
    loop = asyncio.get_running_loop()
    factory = LLMClientFactory(Mock())
    entered, registered, release = install_builder(monkeypatch, factory, loop)
    with ThreadPoolExecutor(max_workers=1) as builders:
        construction = builders.submit(factory.get_or_create_client, "openai", CONFIG)
        try:
            await asyncio.wait_for(entered.wait(), 5)
            loop.set_task_factory(asyncio.eager_task_factory)
            caller = asyncio.create_task(factory.shutdown())
            assert registered.is_set() and factory._ordinary_waiter is not None
        finally:
            loop.set_task_factory(None)
            release.set()
        await asyncio.wait_for(caller, 5)
        construction.result(timeout=5)
        assert factory._closed and factory._ordinary_waiter is None


@pytest.mark.asyncio
async def test_finalizer_notifies_after_registration_before_future_suspends(
    monkeypatch,
):
    loop = asyncio.get_running_loop()
    factory = LLMClientFactory(Mock())
    entered, registered, release = install_builder(monkeypatch, factory, loop)
    original_drain = factory._wait_ordinary_drain
    before_suspend = []

    with ThreadPoolExecutor(max_workers=1) as builders:
        construction = builders.submit(factory.get_or_create_client, "openai", CONFIG)

        class BeforeAwaitFuture(asyncio.Future):
            def __await__(self):
                assert factory._ordinary_waiter[1] is self
                release.set()
                construction.result(timeout=5)
                before_suspend.append(factory._ordinary_pending)
                return super().__await__()

        async def drain():
            with monkeypatch.context() as patch:
                patch.setattr(
                    loop, "create_future", lambda: BeforeAwaitFuture(loop=loop)
                )
                await original_drain()

        monkeypatch.setattr(factory, "_wait_ordinary_drain", drain)
        try:
            await asyncio.wait_for(entered.wait(), 5)
            await asyncio.wait_for(factory.shutdown(), 5)
        finally:
            release.set()
        assert before_suspend == [0]
        assert factory._closed and factory._ordinary_waiter is None
