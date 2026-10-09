"""Ordinary constructors must progress independently and retain reservations."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm_client_factory import LLMClientFactory


def config(model="paused", key="offline"):
    return {"model": model, "api_key": key}


def pause_builder(monkeypatch, factory):
    entered, release = Event(), Event()
    clients = []

    def build(provider, settings, streaming=False):
        if settings["model"] == "paused":
            entered.set()
            if not release.wait(5):
                raise TimeoutError("constructor release missing")
        client = object()
        clients.append(client)
        return client

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    return entered, release, clients


@pytest.mark.parametrize("streaming", [False, True])
def test_unrelated_cached_and_new_keys_progress_before_builder_release(
    monkeypatch, streaming
):
    factory = LLMClientFactory(Mock())
    entered, release, clients = pause_builder(monkeypatch, factory)
    cached = factory.get_or_create_client("openai", config("cached"), streaming)
    with ThreadPoolExecutor(max_workers=3) as pool:
        paused = pool.submit(
            factory.get_or_create_client, "openai", config(), streaming
        )
        try:
            assert entered.wait(5)
            hit = pool.submit(
                factory.get_or_create_client, "openai", config("cached"), streaming
            )
            fresh = pool.submit(
                factory.get_or_create_client,
                "google",
                config("fresh", "other"),
                streaming,
            )
            assert hit.result(timeout=2) is cached
            assert fresh.result(timeout=2) is not cached
        finally:
            release.set()
        assert paused.result(timeout=5) is clients[-1]


def test_clear_waits_for_builder_then_removes_publication(monkeypatch):
    factory = LLMClientFactory(Mock())
    entered, release, clients = pause_builder(monkeypatch, factory)
    waiting = Event()
    original_wait = factory._ordinary_condition.wait

    def observed_wait(*args):
        waiting.set()
        return original_wait(*args)

    monkeypatch.setattr(factory._ordinary_condition, "wait", observed_wait)
    with ThreadPoolExecutor(max_workers=2) as pool:
        build = pool.submit(factory.get_or_create_client, "openai", config())
        try:
            assert entered.wait(5)
            clear = pool.submit(factory.clear_cache)
            assert waiting.wait(5)
            assert not clear.done()
            assert factory.prepare_sync_shutdown() is False
            assert factory._closing is False
        finally:
            release.set()
        assert build.result(timeout=5) is clients[0]
        clear.result(timeout=5)
    assert factory._clients == factory._pending_tokens == factory._api_key_tokens == {}


@pytest.mark.parametrize("error_type", [ValueError, KeyboardInterrupt])
def test_failed_builder_releases_only_its_token(monkeypatch, error_type):
    factory = LLMClientFactory(Mock())
    sentinel = error_type("original constructor failure")

    def failed(*args):
        raise sentinel

    monkeypatch.setattr(factory, "_create_langchain_client", failed)
    with pytest.raises(error_type) as caught:
        factory.get_or_create_client("openai", config())
    assert caught.value is sentinel
    assert (
        factory._pending_tokens == factory._api_key_tokens == factory._key_locks == {}
    )
    assert factory._ordinary_pending == 0


@pytest.mark.parametrize(
    "operation",
    [
        "same_key",
        "clear_cache",
        "prepare_shutdown",
        "prepare_sync_shutdown",
        "shutdown",
    ],
)
def test_reentrant_constructor_refuses_without_consuming_outer_owner(
    monkeypatch, operation
):
    import asyncio

    factory = LLMClientFactory(Mock())
    client = object()

    def nested(*args):
        with pytest.raises(LLMConfigurationError, match="Reentrant"):
            if operation == "same_key":
                factory.get_or_create_client("openai", config())
            elif operation == "shutdown":
                asyncio.run(factory.shutdown())
            else:
                getattr(factory, operation)()
        assert factory._ordinary_pending == 1
        assert factory._closing is False
        return client

    monkeypatch.setattr(factory, "_create_langchain_client", nested)
    assert factory.get_or_create_client("openai", config()) is client
    assert factory._ordinary_pending == 0


@pytest.mark.parametrize("error_type", [ValueError, KeyboardInterrupt])
def test_nested_different_key_failure_keeps_outer_same_token(monkeypatch, error_type):
    factory = LLMClientFactory(Mock())
    client = object()

    def nested(provider, settings, streaming=False):
        if settings["model"] == "nested":
            raise error_type("nested failed")
        token = factory._api_key_tokens["offline"]
        with pytest.raises(error_type, match="nested failed"):
            factory.get_or_create_client("openai", config("nested"))
        assert factory._api_key_tokens["offline"] == token
        assert factory._pending_tokens[token] == 1
        return client

    monkeypatch.setattr(factory, "_create_langchain_client", nested)
    assert factory.get_or_create_client("openai", config()) is client
    assert factory._pending_tokens == {}


def test_nested_different_key_construction_publishes_both(monkeypatch):
    factory = LLMClientFactory(Mock())
    outer, inner = object(), object()

    def nested(provider, settings, streaming=False):
        if settings["model"] == "nested":
            return inner
        assert factory.get_or_create_client("openai", config("nested")) is inner
        return outer

    monkeypatch.setattr(factory, "_create_langchain_client", nested)
    assert factory.get_or_create_client("openai", config()) is outer
    assert factory.get_or_create_client("openai", config("nested")) is inner
    assert len(factory._clients) == 2
    assert factory._pending_tokens == {}
