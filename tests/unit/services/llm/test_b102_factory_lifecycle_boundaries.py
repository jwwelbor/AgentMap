"""B102 governed construction and shutdown are one terminal transaction."""

import asyncio
from threading import Event
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError, LLMLifecycleCleanupError
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.llm_lifecycle_test_support import signalling_lock_factory
from tests.runtime_manager_test_support import cancel_tasks_for_test


def config(model: str) -> dict[str, str]:
    return {"model": model, "api_key": "offline-key"}


class SyncResource:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


class AsyncResource:
    def __init__(self) -> None:
        self.closed = 0

    async def aclose(self) -> None:
        self.closed += 1


async def _reap_factory_shutdown(
    factory, acquisition, shutdown, release, entered, exited
):
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
    if entered.is_set():
        await asyncio.to_thread(exited.wait, 5)
    await factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_config", [None, []])
async def test_governed_client_rejects_invalid_config_before_binding_or_mutation(
    invalid_config,
):
    factory = LLMClientFactory(Mock())

    with pytest.raises(TypeError, match="config must be a dictionary"):
        await factory.get_or_create_governed_client("openai", invalid_config)

    assert factory._owner_loop is None
    assert factory._clients == {}
    assert factory._api_key_tokens == {}
    assert factory._pending_tokens == {}
    assert factory._active_governed == set()


@pytest.mark.asyncio
async def test_task_creation_failure_survives_coroutine_close_failure__b102(
    monkeypatch,
):
    factory = LLMClientFactory(Mock())
    primary = RuntimeError("task creation failed")
    cleanup = RuntimeError("private coroutine close detail")

    class FailingCoroutineClose:
        def close(self):
            raise cleanup

    def fail_create_task(_coroutine):
        raise primary

    construction = FailingCoroutineClose()
    monkeypatch.setattr(
        factory, "_run_governed_construction", lambda *args: construction
    )
    monkeypatch.setattr(asyncio, "create_task", fail_create_task)

    with pytest.raises(RuntimeError) as caught:
        await factory.get_or_create_governed_client("openai", config("m"))

    assert caught.value is primary
    assert primary.__notes__ == ["unscheduled coroutine close failed with RuntimeError"]
    assert factory._pending_tokens == {}


@pytest.mark.asyncio
async def test_failed_construction_awaits_transactional_owner_rollback__b102(
    monkeypatch,
):
    factory = LLMClientFactory(Mock())
    sync, async_ = SyncResource(), AsyncResource()
    failure = ValueError("typed constructor failure")

    attempts = 0

    def fail_once(*args, owner, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            owner.create_sync(lambda: sync)
            owner.create_async(lambda: async_)
            raise failure
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", fail_once)
    with pytest.raises(ValueError) as caught:
        await factory.get_or_create_governed_client("openai", config("m"))
    assert caught.value is failure
    assert factory._owner_loop is asyncio.get_running_loop()
    assert (sync.closed, async_.closed) == (1, 1)
    assert factory._owners == [] and factory._clients == {}
    assert factory._api_key_tokens == {}
    assert factory._pending_tokens == {}
    assert factory._key_locks == {}
    assert not factory.prepare_sync_shutdown()
    assert await factory.get_or_create_governed_client("openai", config("m"))
    assert attempts == 2
    await factory.shutdown()


@pytest.mark.asyncio
async def test_same_key_governed_construction_has_one_owner__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    entered, release = Event(), Event()
    waiting = Event()
    created: list[object] = []

    def build(*args, owner, **kwargs):
        created.append(object())
        entered.set()
        assert release.wait(5)
        return created[-1]

    monkeypatch.setattr(
        "agentmap.services.llm.client_lifecycle.Lock",
        signalling_lock_factory(waiting),
    )
    monkeypatch.setattr(factory, "_create_langchain_client", build)
    first = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("same"))
    )
    second = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        second = asyncio.create_task(
            factory.get_or_create_governed_client("openai", config("same"))
        )
        assert await asyncio.to_thread(waiting.wait, 5)
        release.set()
        assert await first is await second
        assert len(created) == len(factory._owners) == 1
    finally:
        release.set()
        try:
            await cancel_tasks_for_test(first, second)
        finally:
            await factory.shutdown()


@pytest.mark.asyncio
async def test_different_keys_construct_independently__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    entered = {"a": Event(), "b": Event()}
    release = Event()

    def build(provider, provider_config, *args, owner, **kwargs):
        entered[provider_config["model"]].set()
        assert release.wait(5)
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    first = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("a"))
    )
    second = None
    try:
        second = asyncio.create_task(
            factory.get_or_create_governed_client("openai", config("b"))
        )
        assert await asyncio.to_thread(entered["a"].wait, 5)
        assert await asyncio.to_thread(entered["b"].wait, 5)
        release.set()
        assert await first is not await second
    finally:
        release.set()
        try:
            await cancel_tasks_for_test(first, second)
        finally:
            await factory.shutdown()


@pytest.mark.asyncio
async def test_shutdown_wins_against_inflight_and_later_construction__b102(
    monkeypatch,
):
    factory = LLMClientFactory(Mock())
    entered, release = Event(), Event()
    exited = Event()
    shutdown_entered = asyncio.Event()
    resource = AsyncResource()

    def build(*args, owner, **kwargs):
        owner.create_async(lambda: resource)
        entered.set()
        try:
            assert release.wait(5)
            return object()
        finally:
            exited.set()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    original_finish = factory._finish_shutdown

    async def marked_finish():
        shutdown_entered.set()
        await original_finish()

    monkeypatch.setattr(factory, "_finish_shutdown", marked_finish)
    acquisition = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("m"))
    )
    shutdown = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        shutdown = asyncio.create_task(factory.shutdown())
        await asyncio.wait_for(shutdown_entered.wait(), timeout=5)
        release.set()
        with pytest.raises(LLMConfigurationError, match="shut down"):
            await acquisition
        await shutdown
        assert resource.closed == 1
        with pytest.raises(LLMConfigurationError, match="shut down"):
            await factory.get_or_create_governed_client("openai", config("later"))
        with pytest.raises(LLMConfigurationError, match="shut down"):
            factory.get_or_create_client("openai", config("ordinary"))
    finally:
        await _reap_factory_shutdown(
            factory, acquisition, shutdown, release, entered, exited
        )


@pytest.mark.asyncio
async def test_factory_cleanup_continues_after_owner_cancellation__b102():
    factory = LLMClientFactory(Mock())
    closed: list[str] = []

    class CancelledOwner:
        async def aclose(self):
            raise asyncio.CancelledError()

    class LaterOwner:
        async def aclose(self):
            closed.append("later")

    factory._owners = [CancelledOwner(), LaterOwner()]
    with pytest.raises(LLMLifecycleCleanupError) as first:
        await factory.shutdown()
    assert first.value.failure_count == 1
    assert closed == ["later"]
    with pytest.raises(LLMLifecycleCleanupError) as second:
        await factory.shutdown()
    assert second.value.failures[0].__class__ is asyncio.CancelledError
    assert closed == ["later"]
