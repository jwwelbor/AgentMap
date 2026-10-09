"""B102 transfers retiring HTTP and startup scopes to pending cleanup."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI

from agentmap.deployment.http.api.server import create_lifespan
from agentmap.exceptions import LLMConfigurationError
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.runtime_manager_test_support import (
    cleanup_runtime_manager_for_test,
    cleanup_runtime_manager_sync_for_test,
)


def _install_runtime(monkeypatch, factory):
    service = SimpleNamespace(
        retire=factory.retire,
        prepare_shutdown=factory.prepare_shutdown,
        shutdown=factory.shutdown,
    )
    container = SimpleNamespace(
        app_config_service=Mock(),
        auth_service=Mock(),
        llm_service=Mock(return_value=service),
    )
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    return container


@pytest.mark.asyncio
async def test_fastapi_lifespan_transfers_active_worker_to_pending_cleanup(monkeypatch):
    await cleanup_runtime_manager_for_test()
    factory = LLMClientFactory(Mock())
    container = _install_runtime(monkeypatch, factory)
    worker_lease = factory.begin_governed_worker()
    started, finish, finished = threading.Event(), threading.Event(), threading.Event()

    def worker():
        assert worker_lease.start_worker()
        started.set()
        try:
            finish.wait(timeout=10)
        finally:
            worker_lease.release()
            finished.set()

    try:
        with pytest.raises(LLMConfigurationError, match="provider work is active"):
            async with create_lifespan()(FastAPI()):
                waiting = asyncio.create_task(asyncio.to_thread(worker))
                assert await asyncio.to_thread(started.wait, 5)
                waiting.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiting

        assert not RuntimeManager._lifespan_tokens
        assert RuntimeManager._pending_cleanup() is container
        assert not factory._closed
        with pytest.raises(LLMConfigurationError, match="retired"):
            factory.begin_governed_invocation()
        with pytest.raises(AgentMapNotInitialized, match="cleanup is pending"):
            RuntimeManager.get_container()
        with pytest.raises(AgentMapNotInitialized, match="owning event loop"):
            await asyncio.to_thread(lambda: asyncio.run(RuntimeManager.shutdown()))
        assert RuntimeManager._pending_cleanup() is container
        finish.set()
        assert await asyncio.to_thread(finished.wait, 5)
        await RuntimeManager.shutdown()
        assert RuntimeManager._pending_cleanup() is None
        assert factory._closed
    finally:
        finish.set()
        if not finished.is_set():
            await asyncio.to_thread(finished.wait, 5)
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_failed_startup_transfers_active_candidate_before_cleanup(monkeypatch):
    await cleanup_runtime_manager_for_test()
    factory = LLMClientFactory(Mock())
    container = _install_runtime(monkeypatch, factory)
    active = {}
    installs = Mock(return_value=container)
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", installs)

    def startup(_container, _refresh):
        active["lease"] = factory.begin_governed_invocation()
        raise RuntimeError("startup failed")

    try:
        with pytest.raises(Exception):
            await RuntimeManager.initialize_async(startup)
        assert RuntimeManager._pending_cleanup() is container
        with pytest.raises(AgentMapNotInitialized, match="cleanup is pending"):
            RuntimeManager.get_container()
        with pytest.raises(Exception):
            await RuntimeManager.initialize_async(Mock())
        with pytest.raises(LLMConfigurationError, match="retired"):
            factory.begin_governed_invocation()
        installs.assert_called_once()
        active["lease"].release()
        await RuntimeManager.shutdown()
        assert RuntimeManager._pending_cleanup() is None
        assert not RuntimeManager.is_initialized()
    finally:
        lease = active.get("lease")
        if lease is not None:
            lease.release()
        if RuntimeManager._pending_cleanup() is not None:
            await RuntimeManager.shutdown()
        await cleanup_runtime_manager_for_test()


def test_closed_owner_loop_keeps_pending_cleanup_without_foreign_retry(monkeypatch):
    cleanup_runtime_manager_sync_for_test()
    factory = LLMClientFactory(Mock())
    container = _install_runtime(monkeypatch, factory)
    service = container.llm_service()
    original_shutdown = service.shutdown
    shutdown_loops = []

    async def record_shutdown_loop():
        shutdown_loops.append(asyncio.get_running_loop())
        await original_shutdown()

    service.shutdown = record_shutdown_loop
    owner_loop = asyncio.new_event_loop()
    worker_lease = factory.begin_governed_worker()

    async def leave_cleanup_pending():
        with pytest.raises(LLMConfigurationError, match="provider work is active"):
            async with create_lifespan()(FastAPI()):
                pass
        worker_lease.release()

    try:
        owner_loop.run_until_complete(leave_cleanup_pending())
        assert RuntimeManager._pending_cleanup() is container
        assert RuntimeManager._pending_cleanup_loop is owner_loop
        owner_loop.close()

        with pytest.raises(AgentMapNotInitialized, match="event loop is closed"):
            asyncio.run(RuntimeManager.shutdown())

        assert RuntimeManager._pending_cleanup() is container
        assert RuntimeManager._pending_cleanup_loop is owner_loop
        assert shutdown_loops == []
        assert not factory._closed
    finally:
        worker_lease.release()
        if not owner_loop.is_closed():
            owner_loop.close()
        with RuntimeManager._lock:
            RuntimeManager._pending_cleanup_container = None
            RuntimeManager._pending_cleanup_loop = None
        RuntimeManager.reset()
