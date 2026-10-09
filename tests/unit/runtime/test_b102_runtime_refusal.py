"""B102 leaves the active runtime attached when governed work blocks shutdown."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions import AgentMapNotInitialized, LLMConfigurationError
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.runtime_manager_test_support import cleanup_runtime_manager_for_test


@pytest.mark.asyncio
async def test_runtime_shutdown_refusal_preserves_container_and_can_retry__b102():
    factory = LLMClientFactory(Mock())
    invocation = factory.begin_governed_invocation()
    service = SimpleNamespace(
        prepare_shutdown=factory.prepare_shutdown, shutdown=factory.shutdown
    )
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    await cleanup_runtime_manager_for_test()
    RuntimeManager._container, RuntimeManager._is_initialized = container, True
    try:
        with pytest.raises(LLMConfigurationError, match="governed provider work"):
            await RuntimeManager.shutdown()
        assert RuntimeManager.get_container() is container
        assert not factory._closing and not factory._closed
        invocation.release()
        await RuntimeManager.shutdown()
        assert not RuntimeManager.is_initialized() and factory._closed
    finally:
        invocation.release()
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_async_refresh_refusal_keeps_current_runtime_attached__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    invocation = factory.begin_governed_invocation()
    service = SimpleNamespace(
        prepare_shutdown=factory.prepare_shutdown, shutdown=factory.shutdown
    )
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    install = Mock()
    await cleanup_runtime_manager_for_test()
    RuntimeManager._container, RuntimeManager._is_initialized = container, True
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", install)
    try:
        with pytest.raises(LLMConfigurationError, match="governed provider work"):
            await RuntimeManager.initialize_async(Mock(), refresh=True)
        assert RuntimeManager.get_container() is container
        assert not factory._closing
        install.assert_not_called()
        invocation.release()
        await RuntimeManager.shutdown()
        assert factory._closed
    finally:
        invocation.release()
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_reset_refuses_live_runtime_and_preserves_lifespan_ownership__b102():
    await cleanup_runtime_manager_for_test()
    factory = LLMClientFactory(Mock())
    invocation = factory.begin_governed_invocation()
    service = SimpleNamespace(
        prepare_shutdown=factory.prepare_shutdown, shutdown=factory.shutdown
    )
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    lease = object()
    loop = asyncio.get_running_loop()
    RuntimeManager._container, RuntimeManager._is_initialized = container, True
    RuntimeManager._lifespan_tokens.add(lease)
    RuntimeManager._lifespan_owned = True
    RuntimeManager._lifespan_container = container
    RuntimeManager._lifespan_loop = loop
    try:
        with pytest.raises(AgentMapNotInitialized, match="release lifespans"):
            RuntimeManager.reset()

        assert RuntimeManager._container is container
        assert RuntimeManager.is_initialized()
        assert RuntimeManager._lifespan_tokens == {lease}
        assert RuntimeManager._lifespan_owned
        assert RuntimeManager._lifespan_container is container
        assert RuntimeManager._lifespan_loop is loop
        later = factory.begin_governed_invocation()
        later.release()

        RuntimeManager._lifespan_tokens.remove(lease)
        RuntimeManager._lifespan_owned = False
        RuntimeManager._lifespan_container = None
        RuntimeManager._lifespan_loop = None
        invocation.release()
        await RuntimeManager.shutdown()
        await cleanup_runtime_manager_for_test()
    finally:
        if lease in RuntimeManager._lifespan_tokens:
            RuntimeManager._lifespan_tokens.remove(lease)
            RuntimeManager._lifespan_owned = False
            RuntimeManager._lifespan_container = None
            RuntimeManager._lifespan_loop = None
        invocation.release()
        if RuntimeManager._pending_cleanup() is not None:
            await RuntimeManager.shutdown()
        elif RuntimeManager._container is container:
            await RuntimeManager.shutdown()
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_reset_refuses_pending_cleanup_and_preserves_owner_loop__b102():
    await cleanup_runtime_manager_for_test()
    loop = asyncio.get_running_loop()
    service = SimpleNamespace(shutdown=AsyncMock())
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    RuntimeManager._pending_cleanup_container = container
    RuntimeManager._pending_cleanup_loop = loop

    try:
        with pytest.raises(AgentMapNotInitialized, match="pending"):
            RuntimeManager.reset()

        assert RuntimeManager._pending_cleanup() is container
        assert RuntimeManager._pending_cleanup_loop is loop
        service.shutdown.assert_not_awaited()

        await RuntimeManager.shutdown()
        assert RuntimeManager._pending_cleanup() is None
    finally:
        await cleanup_runtime_manager_for_test()


async def _install_loop_bound_runtime(monkeypatch):
    owner_loop = asyncio.get_running_loop()
    factory = LLMClientFactory(Mock())
    closed_on = []

    class LoopBoundResource:
        async def aclose(self):
            closed_on.append(asyncio.get_running_loop())

    def build(*args, owner, **kwargs):
        owner.create_async(LoopBoundResource)
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    cached = await factory.get_or_create_governed_client(
        "openai", {"model": "offline", "api_key": "offline"}
    )
    service = SimpleNamespace(
        prepare_shutdown=factory.prepare_shutdown, shutdown=factory.shutdown
    )
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    replacement_service = SimpleNamespace(prepare_shutdown=Mock(), shutdown=AsyncMock())
    replacement = SimpleNamespace(
        config=SimpleNamespace(path=Mock(return_value=None)),
        llm_service=Mock(return_value=replacement_service),
    )
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=replacement)
    )
    RuntimeManager._container, RuntimeManager._is_initialized = container, True
    return owner_loop, factory, cached, closed_on, container


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["refresh", "shutdown"])
async def test_async_runtime_transfer_refuses_foreign_factory_loop__b102(
    monkeypatch, operation
):
    await cleanup_runtime_manager_for_test()
    owner_loop, factory, cached, closed_on, container = (
        await _install_loop_bound_runtime(monkeypatch)
    )

    async def foreign_operation():
        if operation == "refresh":
            await RuntimeManager.initialize_async(Mock(), refresh=True)
        else:
            await RuntimeManager.shutdown()

    try:
        with pytest.raises(LLMConfigurationError, match="owning event loop"):
            await asyncio.to_thread(lambda: asyncio.run(foreign_operation()))

        assert RuntimeManager._container is container
        assert RuntimeManager._pending_cleanup() is None
        assert RuntimeManager.is_initialized()
        assert not factory._closing and not factory._closed
        assert closed_on == []
        assert (
            await factory.get_or_create_governed_client(
                "openai", {"model": "offline", "api_key": "offline"}
            )
            is cached
        )
        await RuntimeManager.shutdown()
        assert closed_on == [owner_loop]
        assert RuntimeManager._pending_cleanup() is None
    finally:
        if RuntimeManager._pending_cleanup() is not None:
            await RuntimeManager.shutdown()
        if RuntimeManager._container is not None:
            await RuntimeManager.shutdown()
        await cleanup_runtime_manager_for_test()
