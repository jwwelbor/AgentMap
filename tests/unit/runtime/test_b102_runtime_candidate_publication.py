"""Keep a runtime candidate private until startup validation succeeds."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.runtime_manager import RuntimeManager
from tests.runtime_manager_test_support import (
    cleanup_runtime_manager_for_test,
    cleanup_runtime_manager_sync_for_test,
)


def _candidate():
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = SimpleNamespace(
        config=SimpleNamespace(path=Mock(return_value=None)),
        llm_service=Mock(return_value=service),
    )
    return container, service


def _assert_candidate_is_private(container):
    assert RuntimeManager._initializing_container is container
    assert not RuntimeManager.is_initialized()
    with pytest.raises(AgentMapNotInitialized, match="Runtime not initialized"):
        RuntimeManager.get_container()
    assert RuntimeManager._current_container() is None


@pytest.mark.parametrize("fail_startup", [False, True])
def test_sync_initialization_keeps_candidate_private_until_validation_finishes(
    monkeypatch, fail_startup
):
    entered, release = threading.Event(), threading.Event()
    container, service = _candidate()
    failure = ValueError("cache validation failed")
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    cleanup_runtime_manager_sync_for_test()

    def startup(candidate, refresh):
        assert candidate is container
        assert refresh is False
        entered.set()
        assert release.wait(15)
        if fail_startup:
            raise failure

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            initialized = executor.submit(RuntimeManager.initialize, startup=startup)
            assert entered.wait(15)
            _assert_candidate_is_private(container)
            release.set()
            if fail_startup:
                with pytest.raises(ValueError) as caught:
                    initialized.result(timeout=5)
                assert caught.value is failure
                service.shutdown.assert_awaited_once_with()
                assert RuntimeManager._pending_cleanup() is None
                assert not RuntimeManager.is_initialized()
            else:
                initialized.result(timeout=5)
                assert RuntimeManager.get_container() is container
    finally:
        release.set()
        cleanup_runtime_manager_sync_for_test()


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_startup", [False, True])
async def test_async_initialization_keeps_candidate_private_until_validation_finishes(
    monkeypatch, fail_startup
):
    entered, release = threading.Event(), threading.Event()
    container, service = _candidate()
    failure = ValueError("cache validation failed")
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    await cleanup_runtime_manager_for_test()

    def startup(candidate, refresh):
        assert candidate is container
        assert refresh is False
        entered.set()
        assert release.wait(15)
        if fail_startup:
            raise failure

    initialized = asyncio.create_task(RuntimeManager.initialize_async(startup))
    try:
        assert await asyncio.to_thread(entered.wait, 15)
        _assert_candidate_is_private(container)
        release.set()
        if fail_startup:
            with pytest.raises(AgentMapNotInitialized) as caught:
                await initialized
            assert caught.value.__cause__ is failure
            service.shutdown.assert_awaited_once_with()
            assert RuntimeManager._pending_cleanup() is None
            assert not RuntimeManager.is_initialized()
        else:
            await initialized
            assert RuntimeManager.get_container() is container
    finally:
        release.set()
        if not initialized.done():
            initialized.cancel()
        await asyncio.gather(initialized, return_exceptions=True)
        await cleanup_runtime_manager_for_test()


def _prepare_cancelled_initialization(monkeypatch):
    startup_entered = threading.Event()
    release_startup = threading.Event()
    worker_finished = threading.Event()
    release_worker = threading.Event()
    container, service = _candidate()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    original_install_and_startup = RuntimeManager._install_and_startup

    def hold_worker_return(cls, startup, install_refresh, cache_refresh, config_file):
        original_install_and_startup(
            startup, install_refresh, cache_refresh, config_file
        )
        worker_finished.set()
        assert release_worker.wait(15)

    monkeypatch.setattr(
        RuntimeManager,
        "_install_and_startup",
        classmethod(hold_worker_return),
    )

    def startup(candidate, refresh):
        assert candidate is container
        startup_entered.set()
        assert release_startup.wait(15)

    return (
        startup,
        container,
        service,
        startup_entered,
        release_startup,
        worker_finished,
        release_worker,
    )


@pytest.mark.asyncio
async def test_cancelled_async_initialization_never_publishes_before_rollback(
    monkeypatch,
):
    (
        startup,
        container,
        service,
        startup_entered,
        release_startup,
        worker_finished,
        release_worker,
    ) = _prepare_cancelled_initialization(monkeypatch)
    await cleanup_runtime_manager_for_test()
    initialized = asyncio.create_task(RuntimeManager.initialize_async(startup))
    try:
        assert await asyncio.to_thread(startup_entered.wait, 15)
        _assert_candidate_is_private(container)
        initialized.cancel()
        await asyncio.sleep(0)
        assert initialized.cancelling() == 1
        release_startup.set()
        assert await asyncio.to_thread(worker_finished.wait, 15)

        _assert_candidate_is_private(container)
        release_worker.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(initialized, timeout=5)

        service.shutdown.assert_awaited_once_with()
        assert RuntimeManager._candidate_container() is None
        assert RuntimeManager._pending_cleanup() is None
    finally:
        release_startup.set()
        release_worker.set()
        if not initialized.done():
            initialized.cancel()
        await asyncio.gather(initialized, return_exceptions=True)
        await cleanup_runtime_manager_for_test()


def test_retry_does_not_forget_candidate_when_retirement_failed(monkeypatch):
    startup_error = ValueError("startup validation failed")
    retire_error = RuntimeError("retirement failed")
    container, service = _candidate()
    service.retire.side_effect = retire_error
    initialize_di = Mock(side_effect=[container, RuntimeError("new install failed")])
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", initialize_di)
    cleanup_runtime_manager_sync_for_test()

    def startup(candidate, refresh):
        raise startup_error

    try:
        with pytest.raises(ValueError) as caught:
            RuntimeManager.initialize(startup=startup)

        assert caught.value is startup_error
        assert RuntimeManager._initializing_container is container
        assert RuntimeManager._pending_cleanup() is None
        assert not RuntimeManager.is_initialized()

        with pytest.raises(AgentMapNotInitialized, match="prior startup candidate"):
            RuntimeManager.initialize()

        assert initialize_di.call_count == 1
        assert RuntimeManager._initializing_container is container
        assert RuntimeManager._candidate_container() is container

        asyncio.run(RuntimeManager.shutdown())
        assert RuntimeManager._initializing_container is None
        assert RuntimeManager._pending_cleanup() is None
        service.shutdown.assert_awaited_once_with()
    finally:
        if RuntimeManager._candidate_container() is not None:
            asyncio.run(RuntimeManager.shutdown())
        cleanup_runtime_manager_sync_for_test()
