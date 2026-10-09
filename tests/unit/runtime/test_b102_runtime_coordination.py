"""B102 runtime coordination never blocks the event loop or loses outcomes."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.init_ops import ensure_initialized, ensure_initialized_async
from agentmap.runtime.runtime_manager import RuntimeManager
from tests.runtime_manager_test_support import cleanup_runtime_manager_for_test


class CountingExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers):
        super().__init__(max_workers=max_workers)
        self.submissions = 0

    def submit(self, fn, /, *args, **kwargs):
        self.submissions += 1
        return super().submit(fn, *args, **kwargs)


def container(*, shutdown=None, ready=True):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=shutdown or AsyncMock()
    )
    return SimpleNamespace(
        ready=ready,
        llm_service=Mock(return_value=service),
    )


def flatten(error: BaseException) -> list[BaseException]:
    if isinstance(error, BaseExceptionGroup):
        return [item for child in error.exceptions for item in flatten(child)]
    return [error]


@pytest.mark.asyncio
async def test_async_replacement_preserves_requested_cache_refresh__b102(monkeypatch):
    old, replacement = container(), container()
    refresh_cache = Mock()
    await cleanup_runtime_manager_for_test()
    RuntimeManager._container, RuntimeManager._is_initialized = old, True
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=replacement)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", lambda value: value.ready
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", refresh_cache)
    try:
        await ensure_initialized_async(refresh=True)
        refresh_cache.assert_called_once_with(replacement)
        assert RuntimeManager.get_container() is replacement
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_cancellation_during_prerequisite_shutdown_is_primary__b102(monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()

    async def shutdown():
        entered.set()
        await asyncio.wait_for(release.wait(), timeout=10)

    old = container(shutdown=AsyncMock(side_effect=shutdown))
    install = Mock(return_value=container())
    await cleanup_runtime_manager_for_test()
    RuntimeManager._container, RuntimeManager._is_initialized = old, True
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", install)
    refresh = asyncio.create_task(ensure_initialized_async(refresh=True))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        refresh.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await refresh
        old.llm_service().shutdown.assert_awaited_once_with()
        install.assert_not_called()
        assert not RuntimeManager.is_initialized()
    finally:
        release.set()
        if not refresh.done():
            refresh.cancel()
        await asyncio.gather(refresh, return_exceptions=True)
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_prerequisite_shutdown_failure_stays_under_cancellation__b102(
    monkeypatch,
):
    entered, release = asyncio.Event(), asyncio.Event()
    failure = RuntimeError("offline old-runtime cleanup failure")
    calls = 0

    async def shutdown():
        nonlocal calls
        calls += 1
        entered.set()
        if calls == 1:
            await asyncio.wait_for(release.wait(), timeout=10)
            raise failure

    old = container(shutdown=AsyncMock(side_effect=shutdown))
    await cleanup_runtime_manager_for_test()
    RuntimeManager._container, RuntimeManager._is_initialized = old, True
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", Mock())
    refresh = asyncio.create_task(ensure_initialized_async(refresh=True))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        refresh.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await refresh
        assert caught.value.__cause__ is failure
        old.llm_service().shutdown.assert_awaited_once_with()
        assert not RuntimeManager.is_initialized()
    finally:
        release.set()
        if not refresh.done():
            refresh.cancel()
        await asyncio.gather(refresh, return_exceptions=True)
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_cancellation_during_rollback_remains_primary__b102(monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    cleanup_failure = RuntimeError("offline rollback failure")
    calls = 0

    async def shutdown():
        nonlocal calls
        calls += 1
        entered.set()
        if calls == 1:
            await asyncio.wait_for(release.wait(), timeout=10)
            raise cleanup_failure

    installed = container(shutdown=AsyncMock(side_effect=shutdown), ready=False)
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=installed)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._refresh_cache",
        Mock(side_effect=ValueError("offline startup failure")),
    )
    startup = asyncio.create_task(ensure_initialized_async())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        startup.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await startup
        retained = flatten(caught.value.__cause__)
        assert any(isinstance(error, AgentMapNotInitialized) for error in retained)
        assert cleanup_failure in retained
        assert not RuntimeManager.is_initialized()
    finally:
        release.set()
        if not startup.done():
            startup.cancel()
        await asyncio.gather(startup, return_exceptions=True)
        await cleanup_runtime_manager_for_test()


@pytest.mark.parametrize("workers", [1, 2])
@pytest.mark.asyncio
async def test_bounded_executor_burst_cannot_starve_transaction_owner__b102(
    monkeypatch, workers
):
    loop = asyncio.get_running_loop()
    executor = CountingExecutor(max_workers=workers)
    loop.set_default_executor(executor)
    entered, release = asyncio.Event(), Event()
    installed = container(ready=False)
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=installed)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", lambda value: value.ready
    )

    def refresh(value):
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        value.ready = True

    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", refresh)
    owner = asyncio.create_task(ensure_initialized_async())
    queued = []
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        owner_submissions = executor.submissions

        async def queued_initializer(started):
            started.set()
            await ensure_initialized_async()

        started = [asyncio.Event() for _ in range(workers + 2)]
        queued = [asyncio.create_task(queued_initializer(event)) for event in started]
        await asyncio.wait_for(
            asyncio.gather(*(event.wait() for event in started)), timeout=5
        )
        submissions_while_owner_blocked = executor.submissions
        assert submissions_while_owner_blocked == owner_submissions
        release.set()
        await asyncio.wait_for(asyncio.gather(owner, *queued), timeout=2)
    finally:
        release.set()
        for task in (owner, *queued):
            if not task.done():
                task.cancel()
        await asyncio.gather(owner, *queued, return_exceptions=True)
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_sync_initializer_refuses_async_owner_without_blocking__b102(monkeypatch):
    loop = asyncio.get_running_loop()
    entered, release = asyncio.Event(), Event()
    installed = container(ready=False)
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=installed)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", lambda value: value.ready
    )

    def refresh(value):
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        value.ready = True

    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", refresh)
    owner = asyncio.create_task(ensure_initialized_async())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        with pytest.raises(AgentMapNotInitialized, match="async transaction"):
            ensure_initialized()
    finally:
        release.set()
        if not owner.done():
            owner.cancel()
        await asyncio.gather(owner, return_exceptions=True)
        await cleanup_runtime_manager_for_test()
