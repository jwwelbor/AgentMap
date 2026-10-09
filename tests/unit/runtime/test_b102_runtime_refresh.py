"""B102 refresh awaits cleanup and closes loop-bound resources on its caller."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.init_ops import ensure_initialized_async
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.runtime_manager_test_support import (
    cleanup_runtime_manager_for_test,
    cleanup_runtime_manager_sync_for_test,
)


def test_refresh_awaits_old_container_llm_shutdown__b102(monkeypatch):
    service = SimpleNamespace(
        prepare_shutdown=Mock(),
        prepare_sync_shutdown=Mock(return_value=True),
        shutdown=AsyncMock(),
    )
    old = SimpleNamespace(llm_service=Mock(return_value=service))
    new_service = SimpleNamespace(prepare_shutdown=Mock(), shutdown=AsyncMock())
    new = SimpleNamespace(
        config=SimpleNamespace(path=Mock(return_value=None)),
        llm_service=Mock(return_value=new_service),
    )
    RuntimeManager._container, RuntimeManager._is_initialized = old, True
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=new)
    )
    try:
        RuntimeManager.initialize(refresh=True)
        service.shutdown.assert_awaited_once_with()
        assert RuntimeManager.get_container() is new
    finally:
        cleanup_runtime_manager_sync_for_test()


@pytest.mark.asyncio
async def test_async_refresh_closes_loop_bound_owner_on_caller_loop__b102(monkeypatch):
    caller_loop = asyncio.get_running_loop()
    factory, closed = LLMClientFactory(Mock()), []

    class LoopBoundResource:
        async def aclose(self):
            assert asyncio.get_running_loop() is caller_loop
            closed.append(True)

    def build(*args, owner, **kwargs):
        owner.create_async(LoopBoundResource)
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    await factory.get_or_create_governed_client(
        "openai", {"model": "offline", "api_key": "offline"}
    )
    service = SimpleNamespace(
        prepare_shutdown=factory.prepare_shutdown, shutdown=factory.shutdown
    )
    old = SimpleNamespace(llm_service=Mock(return_value=service))
    new_service = SimpleNamespace(prepare_shutdown=Mock(), shutdown=AsyncMock())
    new = SimpleNamespace(
        config=SimpleNamespace(path=Mock(return_value=None)),
        llm_service=Mock(return_value=new_service),
    )
    RuntimeManager._container, RuntimeManager._is_initialized = old, True
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=new)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", Mock(return_value=True)
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", Mock())
    try:
        await ensure_initialized_async(refresh=True)
        assert closed == [True]
        assert RuntimeManager.get_container() is new
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_async_refresh_retains_failed_shutdown_until_retry__b102(monkeypatch):
    failure = RuntimeError("offline old runtime close failure")
    service = SimpleNamespace(
        prepare_shutdown=Mock(), shutdown=AsyncMock(side_effect=[failure, None])
    )
    old = SimpleNamespace(llm_service=Mock(return_value=service))
    replacement_service = SimpleNamespace(prepare_shutdown=Mock(), shutdown=AsyncMock())
    replacement = SimpleNamespace(
        config=SimpleNamespace(path=Mock(return_value=None)),
        llm_service=Mock(return_value=replacement_service),
    )
    RuntimeManager._container, RuntimeManager._is_initialized = old, True
    startup = Mock()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di",
        Mock(return_value=replacement),
    )
    try:
        with pytest.raises(RuntimeError, match="old runtime close"):
            await RuntimeManager.initialize_async(startup, refresh=True)
        assert RuntimeManager._pending_cleanup() is old
        with pytest.raises(AgentMapNotInitialized, match="cleanup is pending"):
            RuntimeManager.get_container()
        startup.assert_not_called()

        await RuntimeManager.initialize_async(startup, refresh=True)
        assert service.shutdown.await_count == 2
        assert RuntimeManager._pending_cleanup() is None
        assert RuntimeManager.get_container() is replacement
        startup.assert_called_once_with(replacement, True)
    finally:
        await cleanup_runtime_manager_for_test()


def test_sync_refresh_retains_failed_shutdown_until_explicit_retry__b102(monkeypatch):
    failure = RuntimeError("offline old runtime close failure")
    service = SimpleNamespace(
        prepare_shutdown=Mock(),
        prepare_sync_shutdown=Mock(return_value=True),
        shutdown=AsyncMock(side_effect=[failure, None]),
    )
    old = SimpleNamespace(llm_service=Mock(return_value=service))
    replacement_service = SimpleNamespace(prepare_shutdown=Mock(), shutdown=AsyncMock())
    replacement = SimpleNamespace(
        config=SimpleNamespace(path=Mock(return_value=None)),
        llm_service=Mock(return_value=replacement_service),
    )
    RuntimeManager._container, RuntimeManager._is_initialized = old, True
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di",
        Mock(return_value=replacement),
    )
    try:
        with pytest.raises(RuntimeError, match="old runtime close"):
            RuntimeManager.initialize(refresh=True)
        assert RuntimeManager._pending_cleanup() is old
        with pytest.raises(AgentMapNotInitialized, match="cleanup is pending"):
            RuntimeManager.get_container()

        asyncio.run(RuntimeManager.shutdown())
        assert service.shutdown.await_count == 2
        assert RuntimeManager._pending_cleanup() is None
        RuntimeManager.initialize()
        assert RuntimeManager.get_container() is replacement
    finally:
        cleanup_runtime_manager_sync_for_test()
