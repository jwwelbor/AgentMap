"""B102 async runtime replacement and startup are lifecycle transactions."""

import asyncio
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.init_ops import ensure_initialized_async
from agentmap.runtime.runtime_manager import RuntimeManager
from tests.runtime_manager_test_support import (
    cancel_tasks_for_test,
    cleanup_runtime_manager_for_test,
    release_reap_and_cleanup_runtime_for_test,
)


@pytest.mark.asyncio
async def test_shutdown_retains_failed_cleanup_until_explicit_retry__b102():
    failure = RuntimeError("offline runtime shutdown failure")
    service = SimpleNamespace(
        retire=Mock(),
        prepare_shutdown=Mock(),
        shutdown=AsyncMock(side_effect=[failure, None]),
    )
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    await cleanup_runtime_manager_for_test()
    RuntimeManager._container, RuntimeManager._is_initialized = container, True
    try:
        with pytest.raises(RuntimeError, match="runtime shutdown"):
            await RuntimeManager.shutdown()
        assert RuntimeManager._pending_cleanup() is container
        assert not RuntimeManager.is_initialized()
        with pytest.raises(AgentMapNotInitialized, match="cleanup is pending"):
            RuntimeManager.get_container()

        await RuntimeManager.shutdown()
        assert service.shutdown.await_count == 2
        assert RuntimeManager._pending_cleanup() is None
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_async_startup_failure_rolls_back_installed_runtime__b102(monkeypatch):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._refresh_cache",
        Mock(side_effect=RuntimeError("offline cache failure")),
    )
    try:
        with pytest.raises(AgentMapNotInitialized, match="offline cache failure"):
            await ensure_initialized_async()
        service.shutdown.assert_awaited_once_with()
        assert not RuntimeManager.is_initialized()
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_async_startup_and_rollback_failures_are_both_visible__b102(monkeypatch):
    cleanup_error = RuntimeError("offline cleanup failure")
    service = SimpleNamespace(
        retire=Mock(),
        prepare_shutdown=Mock(),
        shutdown=AsyncMock(side_effect=[cleanup_error, None]),
    )
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._refresh_cache",
        Mock(side_effect=ValueError("offline cache failure")),
    )
    try:
        with pytest.raises(AgentMapNotInitialized) as caught:
            await ensure_initialized_async()
        assert caught.value.__cause__ is cleanup_error
        assert not RuntimeManager.is_initialized()
    finally:
        await RuntimeManager.shutdown()
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_cancelled_post_install_startup_rolls_back_once__b102(monkeypatch):
    entered, release = Event(), Event()
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )

    def block_after_install(_container):
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", block_after_install)
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", Mock(return_value=True)
    )
    startup = asyncio.create_task(ensure_initialized_async(refresh=True))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        startup.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await startup
        service.shutdown.assert_awaited_once_with()
        assert not RuntimeManager.is_initialized()
    finally:
        await release_reap_and_cleanup_runtime_for_test(release, startup)


@pytest.mark.asyncio
async def test_cancelled_startup_keeps_rollback_failure_as_cause__b102(monkeypatch):
    entered, release = Event(), Event()
    cleanup_error = RuntimeError("offline rollback failure")
    service = SimpleNamespace(
        retire=Mock(),
        prepare_shutdown=Mock(),
        shutdown=AsyncMock(side_effect=[cleanup_error, None]),
    )
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )

    def block_after_install(_container):
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", block_after_install)
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", Mock(return_value=True)
    )
    startup = asyncio.create_task(ensure_initialized_async(refresh=True))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        startup.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await startup
        assert caught.value.__cause__ is cleanup_error
        service.shutdown.assert_awaited_once_with()
        assert not RuntimeManager.is_initialized()
    finally:
        await release_reap_and_cleanup_runtime_for_test(release, startup)


@pytest.mark.asyncio
async def test_concurrent_failed_start_cannot_detach_peer_success__b102(monkeypatch):
    entered, release = Event(), Event()

    def candidate():
        service = SimpleNamespace(
            retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
        )
        return SimpleNamespace(ready=False, llm_service=Mock(return_value=service))

    first, second = candidate(), candidate()
    containers = iter([first, second])
    refreshes = 0
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", lambda _: next(containers)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", lambda value: value.ready
    )

    def refresh(value):
        nonlocal refreshes
        refreshes += 1
        if refreshes == 1:
            entered.set()
            assert release.wait(5)
            raise RuntimeError("first cache failed")
        value.ready = True

    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", refresh)
    failed = asyncio.create_task(ensure_initialized_async())
    succeeded = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        succeeded = asyncio.create_task(ensure_initialized_async())
        assert RuntimeManager._transaction_owner is not None
        release.set()
        first_result, second_result = await asyncio.gather(
            failed, succeeded, return_exceptions=True
        )
        assert isinstance(first_result, AgentMapNotInitialized)
        assert second_result is None
        assert RuntimeManager.get_container() is second
        first.llm_service().shutdown.assert_awaited_once_with()
    finally:
        await release_reap_and_cleanup_runtime_for_test(release, failed, succeeded)


@pytest.mark.asyncio
async def test_cancelled_transaction_waiter_cannot_orphan_lock__b102(monkeypatch):
    entered, release = Event(), Event()
    container = SimpleNamespace(
        ready=False,
        llm_service=Mock(
            return_value=SimpleNamespace(
                retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
            )
        ),
    )
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", lambda value: value.ready
    )

    def refresh(value):
        entered.set()
        assert release.wait(5)
        value.ready = True

    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", refresh)
    owner = asyncio.create_task(ensure_initialized_async())
    queued = asyncio.Event()

    async def wait_for_transaction():
        queued.set()
        await ensure_initialized_async()

    waiter = asyncio.create_task(wait_for_transaction())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        await asyncio.wait_for(queued.wait(), timeout=5)
        waiter.cancel()
        release.set()
        await asyncio.wait_for(owner, timeout=5)
        with pytest.raises(asyncio.CancelledError):
            await waiter
        await asyncio.wait_for(ensure_initialized_async(), timeout=1)
        assert RuntimeManager.get_container() is container
    finally:
        release.set()
        for task in (owner, waiter):
            if not task.done():
                task.cancel()
        await asyncio.gather(owner, waiter, return_exceptions=True)
        await RuntimeManager.shutdown()


@pytest.mark.asyncio
async def test_cancellation_before_install_keeps_task_failure_as_cause__b102(
    monkeypatch,
):
    entered, release = Event(), Event()
    failure = ValueError("offline DI failure")
    await cleanup_runtime_manager_for_test()

    def fail_before_install(_config_file):
        entered.set()
        assert release.wait(5)
        raise failure

    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", fail_before_install
    )
    startup = asyncio.create_task(ensure_initialized_async())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        startup.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError) as caught:
            await startup
        assert isinstance(caught.value.__cause__, AgentMapNotInitialized)
        assert caught.value.__cause__.__cause__ is failure
        assert not RuntimeManager.is_initialized()
    finally:
        release.set()
        if not startup.done():
            startup.cancel()
        await asyncio.gather(startup, return_exceptions=True)
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_concurrent_refresh_transactions_close_each_replaced_owner__b102(
    monkeypatch,
):
    shutdown_entered, release_shutdown = asyncio.Event(), asyncio.Event()

    async def block_old_shutdown():
        shutdown_entered.set()
        await asyncio.wait_for(release_shutdown.wait(), timeout=10)

    old_service = SimpleNamespace(
        retire=Mock(),
        prepare_shutdown=Mock(),
        shutdown=AsyncMock(side_effect=block_old_shutdown),
    )
    new_services = [
        SimpleNamespace(retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock())
        for _ in range(2)
    ]
    old = SimpleNamespace(llm_service=Mock(return_value=old_service))
    new = [
        SimpleNamespace(llm_service=Mock(return_value=value)) for value in new_services
    ]
    containers = iter(new)
    RuntimeManager._container, RuntimeManager._is_initialized = old, True
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", lambda _: next(containers)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", Mock(return_value=True)
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", Mock())
    first = asyncio.create_task(ensure_initialized_async(refresh=True))
    second = None
    try:
        await asyncio.wait_for(shutdown_entered.wait(), timeout=5)
        second = asyncio.create_task(ensure_initialized_async(refresh=True))
        assert RuntimeManager._transaction_owner is not None
        release_shutdown.set()
        await asyncio.wait_for(asyncio.gather(first, second), timeout=5)
        old_service.shutdown.assert_awaited_once_with()
        new_services[0].shutdown.assert_awaited_once_with()
        assert RuntimeManager.get_container() is new[1]
    finally:
        release_shutdown.set()
        await cancel_tasks_for_test(first, second)
        await RuntimeManager.shutdown()
    new_services[1].shutdown.assert_awaited_once_with()
