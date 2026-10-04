"""B102 async runtime replacement and startup are lifecycle transactions."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.init_ops import ensure_initialized_async
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm_client_factory import LLMClientFactory


def test_refresh_awaits_old_container_llm_shutdown__b102(monkeypatch):
    service = SimpleNamespace(shutdown=AsyncMock())
    old = SimpleNamespace(llm_service=Mock(return_value=service))
    new = object()
    RuntimeManager._container = old
    RuntimeManager._is_initialized = True
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=new)
    )
    try:
        RuntimeManager.initialize(refresh=True)
        service.shutdown.assert_awaited_once_with()
        assert RuntimeManager.get_container() is new
    finally:
        RuntimeManager.reset()


@pytest.mark.asyncio
async def test_async_refresh_closes_loop_bound_owner_on_caller_loop__b102(monkeypatch):
    caller_loop = asyncio.get_running_loop()
    factory = LLMClientFactory(Mock())
    closed = []

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
    old = SimpleNamespace(
        llm_service=Mock(return_value=SimpleNamespace(shutdown=factory.shutdown))
    )
    new = SimpleNamespace()
    RuntimeManager._container = old
    RuntimeManager._is_initialized = True
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=new)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", Mock(return_value=True)
    )
    try:
        await ensure_initialized_async(refresh=True)
        assert closed == [True]
        assert RuntimeManager.get_container() is new
    finally:
        RuntimeManager.reset()


@pytest.mark.asyncio
async def test_async_startup_failure_rolls_back_installed_runtime__b102(monkeypatch):
    service = SimpleNamespace(shutdown=AsyncMock())
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    RuntimeManager.reset()
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
        RuntimeManager.reset()


@pytest.mark.asyncio
async def test_async_startup_and_rollback_failures_are_both_visible__b102(monkeypatch):
    cleanup_error = RuntimeError("offline cleanup failure")
    service = SimpleNamespace(shutdown=AsyncMock(side_effect=cleanup_error))
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    RuntimeManager.reset()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._refresh_cache",
        Mock(side_effect=ValueError("offline cache failure")),
    )
    try:
        with pytest.raises(ExceptionGroup) as caught:
            await ensure_initialized_async()
        assert any(
            isinstance(item, AgentMapNotInitialized) for item in caught.value.exceptions
        )
        assert cleanup_error in caught.value.exceptions
        assert not RuntimeManager.is_initialized()
    finally:
        RuntimeManager.reset()
