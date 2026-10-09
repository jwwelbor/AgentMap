"""Finalizer failure cannot strand drain ownership or erase retained evidence."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMLifecycleCleanupError
from agentmap.services.llm_client_factory import LLMClientFactory

CONFIG = {"model": "m", "api_key": "offline"}


def install_failure(monkeypatch, factory, primary_type, cleanup_type=RuntimeError):
    loop = asyncio.get_running_loop()
    entered, registered, release = asyncio.Event(), asyncio.Event(), Event()
    primary = primary_type("builder failed") if primary_type else None
    cleanup = cleanup_type("token finalizer failed")
    original_drain = factory._wait_ordinary_drain

    def build(*args):
        loop.call_soon_threadsafe(entered.set)
        if not release.wait(5):
            raise TimeoutError("builder release missing")
        if primary is not None:
            raise primary
        return object()

    async def drain():
        registered.set()
        await original_drain()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    monkeypatch.setattr(factory, "_wait_ordinary_drain", drain)
    monkeypatch.setattr(
        factory,
        "_finish_pending_token",
        Mock(side_effect=cleanup),
    )
    return entered, registered, release, primary, cleanup


@pytest.mark.parametrize("primary_type", [None, ValueError, KeyboardInterrupt])
@pytest.mark.parametrize("cleanup_type", [RuntimeError, KeyboardInterrupt])
@pytest.mark.asyncio
async def test_token_failure_releases_drain_and_preserves_primary(
    monkeypatch, primary_type, cleanup_type
):
    factory = LLMClientFactory(Mock())
    entered, registered, release, primary, cleanup = install_failure(
        monkeypatch, factory, primary_type, cleanup_type
    )
    with ThreadPoolExecutor(max_workers=1) as builders:
        construction = builders.submit(factory.get_or_create_client, "openai", CONFIG)
        try:
            await asyncio.wait_for(entered.wait(), 5)
            shutdown = asyncio.create_task(factory.shutdown())
            await asyncio.wait_for(registered.wait(), 5)
            assert factory._ordinary_waiter is not None
        finally:
            release.set()
        with pytest.raises(primary_type or LLMLifecycleCleanupError) as caught:
            construction.result(timeout=5)
        if primary is not None:
            assert caught.value is primary
            assert (
                "ordinary finalization failed with LLMLifecycleCleanupError"
                in primary.__notes__
            )
        retained = factory._ordinary_cleanup_error
        assert retained.failures == (cleanup,)
        if primary is None:
            assert caught.value is retained
        with pytest.raises(LLMLifecycleCleanupError) as shutdown_error:
            await asyncio.wait_for(shutdown, 5)
        assert shutdown_error.value is retained
    assert factory._ordinary_pending == 0 and factory._ordinary_threads == {}
    assert factory._ordinary_waiter is None and not factory._closed
    assert factory._pending_tokens and factory._api_key_tokens
    with pytest.raises(LLMLifecycleCleanupError) as repeat:
        await factory.shutdown()
    assert repeat.value is retained


@pytest.mark.asyncio
async def test_closed_loop_notification_releases_reservation_and_retains_evidence(
    monkeypatch,
):
    factory = LLMClientFactory(Mock())
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    lost_loop = Mock()
    lost_loop.call_soon_threadsafe.side_effect = RuntimeError("event loop is closed")
    pair = (lost_loop, future)
    factory._ordinary_waiter = pair
    notified = Mock(wraps=factory._ordinary_condition.notify_all)
    monkeypatch.setattr(factory._ordinary_condition, "notify_all", notified)
    monkeypatch.setattr(factory, "_create_langchain_client", lambda *a: object())
    with pytest.raises(LLMLifecycleCleanupError) as caught:
        factory.get_or_create_client("openai", CONFIG)
    assert isinstance(caught.value.failures[0], RuntimeError)
    assert factory._ordinary_pending == 0 and factory._ordinary_threads == {}
    assert notified.call_count == 1
    assert factory._ordinary_waiter is pair and not future.done()
    assert factory._clients and factory._api_key_tokens
    with pytest.raises(LLMLifecycleCleanupError):
        await factory.shutdown()
    assert not factory._closed and factory._ordinary_waiter is pair
    future.cancel()


@pytest.mark.parametrize("cleanup_type", [RuntimeError, KeyboardInterrupt])
@pytest.mark.asyncio
async def test_token_failure_wakes_synchronous_clear_without_losing_evidence(
    monkeypatch, cleanup_type
):
    factory = LLMClientFactory(Mock())
    entered, registered, release, primary, cleanup = install_failure(
        monkeypatch, factory, None, cleanup_type
    )
    loop = asyncio.get_running_loop()
    waiting = asyncio.Event()
    original_wait = factory._ordinary_condition.wait

    def wait(*args):
        loop.call_soon_threadsafe(waiting.set)
        return original_wait(*args)

    monkeypatch.setattr(factory._ordinary_condition, "wait", wait)
    with ThreadPoolExecutor(max_workers=2) as builders:
        construction = builders.submit(factory.get_or_create_client, "openai", CONFIG)
        try:
            await asyncio.wait_for(entered.wait(), 5)
            clear = builders.submit(factory.clear_cache)
            await asyncio.wait_for(waiting.wait(), 5)
        finally:
            release.set()
        with pytest.raises(LLMLifecycleCleanupError) as construction_error:
            construction.result(timeout=5)
        with pytest.raises(LLMLifecycleCleanupError) as clear_error:
            clear.result(timeout=5)
        assert (
            construction_error.value
            is clear_error.value
            is factory._ordinary_cleanup_error
        )
        assert clear_error.value.failures == (cleanup,)
    assert factory._ordinary_pending == 0
    assert factory._pending_tokens and not factory._closed


@pytest.mark.parametrize("cleanup_type", [None, RuntimeError, KeyboardInterrupt])
def test_success_inside_caller_except_owns_only_its_finalization(
    monkeypatch, cleanup_type
):
    factory = LLMClientFactory(Mock())
    unrelated = ValueError("unrelated caller recovery")
    cleanup = cleanup_type("token finalizer failed") if cleanup_type else None
    client = object()
    monkeypatch.setattr(factory, "_create_langchain_client", lambda *a: client)
    if cleanup is not None:
        monkeypatch.setattr(factory, "_finish_pending_token", Mock(side_effect=cleanup))
    try:
        raise unrelated
    except ValueError:
        if cleanup is None:
            assert factory.get_or_create_client("openai", CONFIG) is client
        else:
            with pytest.raises(LLMLifecycleCleanupError) as caught:
                factory.get_or_create_client("openai", CONFIG)
            assert caught.value is factory._ordinary_cleanup_error
            assert caught.value.failures == (cleanup,)
    assert not hasattr(unrelated, "__notes__")
    assert factory._ordinary_pending == 0 and factory._ordinary_threads == {}


@pytest.mark.parametrize("primary_type", [ValueError, KeyboardInterrupt])
@pytest.mark.parametrize("cleanup_type", [RuntimeError, KeyboardInterrupt])
def test_constructor_inside_caller_except_preserves_exact_local_primary(
    monkeypatch, primary_type, cleanup_type
):
    factory = LLMClientFactory(Mock())
    unrelated = RuntimeError("caller recovery")
    primary, cleanup = primary_type("builder failed"), cleanup_type("finalizer failed")
    monkeypatch.setattr(factory, "_create_langchain_client", Mock(side_effect=primary))
    monkeypatch.setattr(factory, "_finish_pending_token", Mock(side_effect=cleanup))
    try:
        raise unrelated
    except RuntimeError:
        with pytest.raises(primary_type) as caught:
            factory.get_or_create_client("openai", CONFIG)
    assert caught.value is primary
    assert factory._ordinary_cleanup_error.failures == (cleanup,)
    assert not hasattr(unrelated, "__notes__")
    assert primary.__notes__ == [
        "ordinary finalization failed with LLMLifecycleCleanupError"
    ]
