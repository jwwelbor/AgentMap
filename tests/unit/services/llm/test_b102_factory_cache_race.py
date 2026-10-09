"""B102 cache clearing cannot split identity selection from publication."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm_client_factory import LLMClientFactory


class PublicationLock:
    def __init__(self, lock):
        self.lock = lock
        self.tracking = False
        self.owner_thread = None
        self.clear_attempted = Event()
        self.clear_blocked = Event()

    def __enter__(self):
        if self.tracking and get_ident() != self.owner_thread:
            acquired = self.lock.acquire(blocking=False)
            if not acquired:
                self.clear_blocked.set()
            self.clear_attempted.set()
            if not acquired:
                self.lock.acquire()
        else:
            self.lock.acquire()
        return self

    def __exit__(self, *args):
        self.lock.release()


def acquire(factory, governed, acquired, shutdown_requested):
    config = {"model": "m", "api_key": "offline-key"}
    if governed:

        async def acquire_and_shutdown():
            client = await factory.get_or_create_governed_client("openai", config)
            acquired.set()
            if not await asyncio.to_thread(shutdown_requested.wait, 5):
                raise TimeoutError("test did not release governed shutdown")
            await factory.shutdown()
            return client

        return asyncio.run(acquire_and_shutdown())
    return factory.get_or_create_client("openai", config)


def assert_cache_clear_is_blocked(publication):
    assert publication.clear_attempted.wait(5)
    assert publication.clear_blocked.is_set()


@pytest.mark.parametrize("governed", [False, True])
def test_clear_cannot_run_between_token_and_publication__b102(monkeypatch, governed):
    factory = LLMClientFactory(Mock())
    publication = PublicationLock(factory._cache_lock)
    factory._cache_lock = publication
    ready, release = Event(), Event()
    acquired, shutdown_requested = Event(), Event()
    original_key = factory._cache_key
    constructed = []

    def paused_key(*args):
        publication.owner_thread = get_ident()
        publication.tracking = True
        key = original_key(*args)
        ready.set()
        assert release.wait(5)
        return key

    def build(*args, **kwargs):
        client = object()
        constructed.append(client)
        return client

    monkeypatch.setattr(factory, "_cache_key", paused_key)
    monkeypatch.setattr(factory, "_create_langchain_client", build)
    with ThreadPoolExecutor(max_workers=2) as pool:
        acquisition = pool.submit(
            acquire, factory, governed, acquired, shutdown_requested
        )
        try:
            try:
                assert ready.wait(5)
                clearing = pool.submit(factory.clear_cache)
                assert_cache_clear_is_blocked(publication)
            finally:
                release.set()
            if governed:
                assert acquired.wait(5)
                with pytest.raises(LLMConfigurationError, match="awaited shutdown"):
                    clearing.result(timeout=5)
                shutdown_requested.set()
                assert acquisition.result(timeout=5) is constructed[0]
            else:
                assert acquisition.result(timeout=5) is constructed[0]
                clearing.result(timeout=5)
        finally:
            release.set()
            shutdown_requested.set()
    assert len(constructed) == 1
    assert factory._clients == {}
    assert factory._api_key_tokens == {}
