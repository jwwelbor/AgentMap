"""Shutdown must retain ordinary construction ownership through cancellation."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm_client_factory import LLMClientFactory


class QueuedLock:
    def __init__(self):
        self.lock = Lock()
        self.queued = Event()

    def __enter__(self):
        if not self.lock.acquire(blocking=False):
            self.queued.set()
            self.lock.acquire()
        return self

    def __exit__(self, *args):
        self.lock.release()


def setup_builder(monkeypatch, factory):
    entered, release, draining = Event(), Event(), Event()
    client = object()
    original_drain = factory._wait_ordinary_drain

    def build(*args):
        entered.set()
        if not release.wait(5):
            raise TimeoutError("constructor release missing")
        return client

    async def drain():
        draining.set()
        await original_drain()

    monkeypatch.setattr(factory, "_create_langchain_client", Mock(side_effect=build))
    monkeypatch.setattr(factory, "_wait_ordinary_drain", drain)
    return entered, release, draining, client


@pytest.mark.parametrize("cancel", [False, True])
def test_shutdown_drains_admitted_publication_and_retains_cancelled_cleanup(
    monkeypatch, cancel
):
    factory = LLMClientFactory(Mock())
    entered, release, draining, client = setup_builder(monkeypatch, factory)
    config = {"model": "m", "api_key": "offline"}

    async def exercise():
        with ThreadPoolExecutor(max_workers=1) as pool:
            construction = pool.submit(factory.get_or_create_client, "openai", config)
            try:
                assert await asyncio.to_thread(entered.wait, 5)
                factory.prepare_shutdown()
                assert factory._ordinary_pending == 1
                shutdown = asyncio.create_task(factory.shutdown())
                assert await asyncio.to_thread(draining.wait, 5)
                if cancel:
                    shutdown.cancel()
                assert not factory._shutdown_task.done()
            finally:
                release.set()
            assert await asyncio.to_thread(construction.result, 5) is client
            if cancel:
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(shutdown, 5)
            else:
                await asyncio.wait_for(shutdown, 5)
            await asyncio.wait_for(factory.shutdown(), 5)
        assert factory._closed
        assert (
            factory._clients == factory._pending_tokens == factory._api_key_tokens == {}
        )
        with pytest.raises(LLMConfigurationError, match="shut down"):
            factory.get_or_create_client("openai", config)

    asyncio.run(exercise())


@pytest.mark.parametrize("transition", ["retire", "prepare_shutdown"])
def test_queued_same_key_retains_token_then_refuses_before_builder(
    monkeypatch, transition
):
    factory = LLMClientFactory(Mock())
    entered, release, draining, client = setup_builder(monkeypatch, factory)
    config = {"model": "m", "api_key": "offline"}
    with factory._cache_lock:
        key = factory._cache_key("openai", config, False, False)
        token = factory._api_key_tokens["offline"]
        keyed = QueuedLock()
        factory._key_locks[key] = keyed
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(factory.get_or_create_client, "openai", config)
        try:
            assert entered.wait(5)
            queued = pool.submit(factory.get_or_create_client, "openai", config)
            assert keyed.queued.wait(5)
            assert factory._pending_tokens[token] == 2
            getattr(factory, transition)()
        finally:
            release.set()
        assert first.result(timeout=5) is client
        with pytest.raises(LLMConfigurationError):
            queued.result(timeout=5)
    assert factory._pending_tokens == {}
    assert factory._api_key_tokens["offline"] == token
    asyncio.run(factory.shutdown())
    assert factory._api_key_tokens == {}


def test_same_key_waiters_share_single_publication(monkeypatch):
    factory = LLMClientFactory(Mock())
    entered, release, draining, client = setup_builder(monkeypatch, factory)
    config = {"model": "m", "api_key": "offline"}
    with factory._cache_lock:
        key = factory._cache_key("openai", config, False, False)
        keyed = QueuedLock()
        factory._key_locks[key] = keyed
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(factory.get_or_create_client, "openai", config)
        try:
            assert entered.wait(5)
            second = pool.submit(factory.get_or_create_client, "openai", config)
            assert keyed.queued.wait(5)
        finally:
            release.set()
        assert first.result(timeout=5) is second.result(timeout=5) is client
    assert factory._ordinary_pending == 0
    assert factory._create_langchain_client.call_count == 1


def test_mixed_governed_and_ordinary_shutdown_drains_both(monkeypatch):
    factory = LLMClientFactory(Mock())
    config = {"model": "m", "api_key": "offline"}

    async def exercise():
        monkeypatch.setattr(
            factory, "_create_langchain_client", lambda *a, **kw: object()
        )
        await factory.get_or_create_governed_client("openai", config)
        assert len(factory._owners) == 1
        entered, release, draining, client = setup_builder(monkeypatch, factory)
        with ThreadPoolExecutor(max_workers=1) as pool:
            construction = pool.submit(factory.get_or_create_client, "openai", config)
            try:
                assert await asyncio.to_thread(entered.wait, 5)
                shutdown = asyncio.create_task(factory.shutdown())
                assert await asyncio.to_thread(draining.wait, 5)
                assert not shutdown.done()
            finally:
                release.set()
            assert await asyncio.to_thread(construction.result, 5) is client
            await asyncio.wait_for(shutdown, 5)
        assert factory._owners == []
        assert factory._clients == factory._pending_tokens == {}

    asyncio.run(exercise())


def test_clear_rechecks_shutdown_admission_after_builder_drains(monkeypatch):
    factory = LLMClientFactory(Mock())
    entered, release, draining, client = setup_builder(monkeypatch, factory)
    config = {"model": "m", "api_key": "offline"}
    waiting = Event()
    original_wait = factory._ordinary_condition.wait

    def wait(*args):
        waiting.set()
        return original_wait(*args)

    monkeypatch.setattr(factory._ordinary_condition, "wait", wait)
    with ThreadPoolExecutor(max_workers=2) as pool:
        construction = pool.submit(factory.get_or_create_client, "openai", config)
        try:
            assert entered.wait(5)
            clear = pool.submit(factory.clear_cache)
            assert waiting.wait(5)
            factory.prepare_shutdown()
        finally:
            release.set()
        assert construction.result(timeout=5) is client
        with pytest.raises(LLMConfigurationError, match="shut down"):
            clear.result(timeout=5)
    assert len(factory._clients) == 1
    asyncio.run(factory.shutdown())
    assert factory._clients == {}


def test_idle_shutdown_requires_no_default_executor_submission(monkeypatch):
    factory = LLMClientFactory(Mock())
    config = {"model": "m", "api_key": "offline"}
    monkeypatch.setattr(factory, "_create_langchain_client", lambda *a: object())
    factory.get_or_create_client("openai", config)

    async def forbidden(*args, **kwargs):
        raise AssertionError("idle shutdown submitted default-executor work")

    monkeypatch.setattr(asyncio, "to_thread", forbidden)

    async def exercise():
        await asyncio.wait_for(factory.shutdown(), 5)
        assert factory._closed
        assert factory._clients == factory._pending_tokens == {}

    asyncio.run(exercise())
