"""B102 client cache tokens retain credentials only for live acquisitions."""

import asyncio
from threading import Event
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.llm_lifecycle_test_support import signalling_lock_factory
from tests.runtime_manager_test_support import cancel_tasks_for_test


class ControlFlowFailure(BaseException):
    pass


def config(model: str) -> dict[str, str]:
    return {"model": model, "api_key": "offline-key"}


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


@pytest.mark.parametrize("governed", [False, True])
@pytest.mark.asyncio
async def test_cache_identity_is_reserved_under_publication_lock__b102(
    monkeypatch, governed
):
    """Cache clearing cannot split identity selection from publication."""
    factory = LLMClientFactory(Mock())
    original_key = factory._cache_key

    def checked_key(*args):
        assert factory._cache_lock._is_owned()
        return original_key(*args)

    monkeypatch.setattr(factory, "_cache_key", checked_key)
    monkeypatch.setattr(
        factory, "_create_langchain_client", lambda *args, **kwargs: object()
    )
    if governed:
        assert await factory.get_or_create_governed_client("openai", config("m"))
        await factory.shutdown()
    else:
        assert factory.get_or_create_client("openai", config("m"))
        factory.clear_cache()
    assert factory._clients == {}
    assert factory._api_key_tokens == {}


def test_failed_and_rejected_sync_acquisitions_release_credential__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    credential = config("m")

    with pytest.raises(LLMConfigurationError, match="awaited async construction"):
        factory.get_or_create_client("openai", credential, governed=True)
    assert factory._api_key_tokens == {}

    def fail(*args, **kwargs):
        raise ValueError("construction failed")

    monkeypatch.setattr(factory, "_create_langchain_client", fail)
    with pytest.raises(ValueError, match="construction failed"):
        factory.get_or_create_client("openai", credential)
    assert factory._api_key_tokens == {}

    monkeypatch.setattr(factory, "_create_langchain_client", lambda *a, **k: object())
    client = factory.get_or_create_client("openai", credential)
    assert factory.get_or_create_client("openai", credential) is client
    assert set(factory._api_key_tokens) == {"offline-key"}
    factory.clear_cache()
    assert factory._api_key_tokens == {}


def test_distinct_credentials_retry_opaque_token_collision__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    tokens = iter(["a" * 64, "a" * 64, "b" * 64])
    monkeypatch.setattr(
        "agentmap.services.llm.client_lifecycle.secrets.token_hex",
        lambda size: next(tokens),
    )
    first = factory._cache_key("openai", {"api_key": "one"}, False, False)
    second = factory._cache_key("openai", {"api_key": "two"}, False, False)
    assert first != second
    assert factory._api_key_tokens == {"one": "a" * 64, "two": "b" * 64}


def test_failed_variant_keeps_token_for_cached_sibling__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    first = {"model": "first", "api_key": "shared-secret"}
    second = {"model": "second", "api_key": "shared-secret"}
    client = object()
    monkeypatch.setattr(factory, "_create_langchain_client", lambda *a, **k: client)
    assert factory.get_or_create_client("openai", first) is client
    token = factory._api_key_tokens["shared-secret"]

    def fail(*args, **kwargs):
        raise ValueError("second variant failed")

    monkeypatch.setattr(factory, "_create_langchain_client", fail)
    with pytest.raises(ValueError, match="second variant failed"):
        factory.get_or_create_client("openai", second)
    assert factory._api_key_tokens["shared-secret"] == token
    assert factory.get_or_create_client("openai", first) is client


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [RuntimeError, ValueError, ControlFlowFailure])
async def test_failed_governed_scheduling_releases_credential__b102(
    monkeypatch, error_type
):
    factory = LLMClientFactory(Mock())

    def reject_schedule(coroutine):
        raise error_type("task scheduling failed")

    with monkeypatch.context() as patch:
        patch.setattr(
            "agentmap.services.llm.client_lifecycle.asyncio.create_task",
            reject_schedule,
        )
        with pytest.raises(error_type, match="task scheduling failed"):
            await factory.get_or_create_governed_client("openai", config("m"))
    assert factory._api_key_tokens == {}
    assert factory._pending_tokens == {}
    assert factory._key_locks == {}
    await factory.shutdown()


@pytest.mark.asyncio
async def test_waiting_failed_governed_calls_release_last_credential__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    entered, release = Event(), Event()
    waiting = Event()

    def fail(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        raise ValueError("constructor failed")

    monkeypatch.setattr(
        "agentmap.services.llm.client_lifecycle.Lock",
        signalling_lock_factory(waiting),
    )
    monkeypatch.setattr(factory, "_create_langchain_client", fail)
    first = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("m"))
    )
    second = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        second = asyncio.create_task(
            factory.get_or_create_governed_client("openai", config("m"))
        )
        assert await asyncio.to_thread(waiting.wait, 5)
        assert list(factory._pending_tokens.values()) == [2]
        release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert all(isinstance(result, ValueError) for result in results)
        assert factory._clients == {}
        assert factory._api_key_tokens == {}
        assert factory._pending_tokens == {}
        assert factory._key_locks == {}
    finally:
        release.set()
        try:
            await cancel_tasks_for_test(first, second)
        finally:
            await factory.shutdown()


@pytest.mark.asyncio
async def test_sync_governed_cache_hit_refuses_without_mutation__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    client = object()
    monkeypatch.setattr(
        factory, "_create_langchain_client", lambda *args, **kwargs: client
    )
    assert (
        await factory.get_or_create_governed_client("openai", config("cached"))
        is client
    )
    state = (
        dict(factory._clients),
        dict(factory._api_key_tokens),
        set(factory._published_tokens),
        dict(factory._pending_tokens),
        dict(factory._key_locks),
        tuple(factory._owners),
        set(factory._active_governed),
        factory._owner_loop,
    )

    with pytest.raises(LLMConfigurationError, match="awaited async construction"):
        factory.get_or_create_client("openai", config("cached"), governed=True)

    assert (
        dict(factory._clients),
        dict(factory._api_key_tokens),
        set(factory._published_tokens),
        dict(factory._pending_tokens),
        dict(factory._key_locks),
        tuple(factory._owners),
        set(factory._active_governed),
        factory._owner_loop,
    ) == state
    await factory.shutdown()
