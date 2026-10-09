"""B102 production HTTP lifespan owns the awaited LLM shutdown boundary."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI

from agentmap.deployment.http.api.server import FastAPIServer, create_lifespan
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.init_ops import ensure_initialized_async
from agentmap.runtime.lifespan_mixin import effective_config_file
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.runtime_manager_test_support import cleanup_runtime_manager_for_test


def _runtime_container(service):
    return SimpleNamespace(
        app_config_service=Mock(),
        auth_service=Mock(),
        llm_service=Mock(return_value=service),
    )


@pytest.mark.asyncio
async def test_lifespan_awaits_llm_shutdown_once__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    closed = []

    class Resource:
        async def aclose(self):
            closed.append("closed")

    def build(*args, owner, **kwargs):
        owner.create_async(Resource)
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    await factory.get_or_create_governed_client(
        "openai", {"model": "offline", "api_key": "offline"}
    )
    service = SimpleNamespace(
        retire=factory.retire,
        prepare_shutdown=factory.prepare_shutdown,
        shutdown=factory.shutdown,
    )
    container = _runtime_container(service)
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    await cleanup_runtime_manager_for_test()
    app = FastAPI()
    try:
        async with create_lifespan()(app):
            assert app.state.container is container
        assert closed == ["closed"]
        assert not RuntimeManager.is_initialized()
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_lifespan_borrows_preexisting_runtime_without_shutdown__b102(monkeypatch):
    await cleanup_runtime_manager_for_test()
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = _runtime_container(service)
    RuntimeManager._container = container
    RuntimeManager._is_initialized = True
    RuntimeManager._runtime_config_file = effective_config_file(None)
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    try:
        async with create_lifespan()(FastAPI()):
            assert RuntimeManager.get_container() is container
        assert RuntimeManager.get_container() is container
        service.retire.assert_not_called()
        service.shutdown.assert_not_awaited()
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_overlapping_lifespans_keep_runtime_until_last_exit__b102(monkeypatch):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = _runtime_container(service)
    await cleanup_runtime_manager_for_test()

    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    try:
        async with create_lifespan()(FastAPI()):
            async with create_lifespan()(FastAPI()):
                assert RuntimeManager.get_container() is container
            assert RuntimeManager.get_container() is container
            service.shutdown.assert_not_awaited()
        service.shutdown.assert_awaited_once_with()
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_active_lifespan_rejects_runtime_replacement__b102(monkeypatch):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = _runtime_container(service)
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    try:
        async with create_lifespan()(FastAPI()):
            with pytest.raises(AgentMapNotInitialized, match="active HTTP lifespans"):
                await RuntimeManager.shutdown()
            with pytest.raises(AgentMapNotInitialized, match="active HTTP lifespans"):
                await RuntimeManager.initialize_async(Mock(), refresh=True)
            with pytest.raises(AgentMapNotInitialized, match="active HTTP lifespans"):
                RuntimeManager.initialize(refresh=True)
            assert RuntimeManager.get_container() is container
            service.shutdown.assert_not_awaited()
        service.shutdown.assert_awaited_once_with()
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_overlapping_lifespans_reject_different_config__b102(monkeypatch):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = _runtime_container(service)
    await cleanup_runtime_manager_for_test()
    install = Mock(return_value=container)
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", install)
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    try:
        async with create_lifespan("first.yml")(FastAPI()):
            with pytest.raises(AgentMapNotInitialized, match="config differs"):
                async with create_lifespan("second.yml")(FastAPI()):
                    pytest.fail("incompatible app must not start")
            assert RuntimeManager.get_container() is container
            service.shutdown.assert_not_awaited()
        install.assert_called_once_with("first.yml")
        service.shutdown.assert_awaited_once_with()
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_default_config_cannot_borrow_explicit_runtime__b102(monkeypatch):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = _runtime_container(service)
    await cleanup_runtime_manager_for_test()
    install = Mock(return_value=container)
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", install)
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    try:
        async with create_lifespan("first.yml")(FastAPI()):
            with pytest.raises(AgentMapNotInitialized, match="config differs"):
                async with create_lifespan()(FastAPI()):
                    pytest.fail("default-config app must not borrow explicit config")
            service.shutdown.assert_not_awaited()
        install.assert_called_once_with("first.yml")
        service.shutdown.assert_awaited_once_with()
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_overlapping_lifespans_share_same_explicit_config__b102(monkeypatch):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = _runtime_container(service)
    await cleanup_runtime_manager_for_test()
    install = Mock(return_value=container)
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", install)
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    try:
        async with create_lifespan("shared.yml")(FastAPI()):
            async with create_lifespan("shared.yml")(FastAPI()):
                assert RuntimeManager.get_container() is container
            service.shutdown.assert_not_awaited()
        install.assert_called_once_with("shared.yml")
        service.shutdown.assert_awaited_once_with()
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_borrowed_runtime_rejects_different_config__b102(monkeypatch):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = _runtime_container(service)
    await cleanup_runtime_manager_for_test()
    RuntimeManager._container = container
    RuntimeManager._is_initialized = True
    RuntimeManager._runtime_config_file = effective_config_file("host.yml")
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    try:
        with pytest.raises(AgentMapNotInitialized, match="config differs"):
            async with create_lifespan("other.yml")(FastAPI()):
                pytest.fail("incompatible borrower must not start")
        assert RuntimeManager.get_container() is container
        service.retire.assert_not_called()
        service.shutdown.assert_not_awaited()
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_lifespan_lease_rejects_foreign_event_loop__b102(monkeypatch):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = _runtime_container(service)
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    try:
        lease, _ = await RuntimeManager.acquire_lifespan(Mock())
        with pytest.raises(AgentMapNotInitialized, match="same event loop"):
            await asyncio.to_thread(
                lambda: asyncio.run(RuntimeManager.acquire_lifespan(Mock()))
            )
        with pytest.raises(AgentMapNotInitialized, match="owning event loop"):
            await asyncio.to_thread(
                lambda: asyncio.run(RuntimeManager.release_lifespan(lease))
            )
        assert RuntimeManager.get_container() is container
        service.shutdown.assert_not_awaited()
        await RuntimeManager.release_lifespan(lease)
        service.shutdown.assert_awaited_once_with()
    finally:
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_lifespan_release_finishes_after_waiter_cancellation__b102(monkeypatch):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
    )
    container = _runtime_container(service)
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    held = None
    release = None
    try:
        lease, _ = await RuntimeManager.acquire_lifespan(Mock())
        held = await RuntimeManager._acquire_async_transaction()
        original = RuntimeManager._acquire_async_transaction.__func__
        waiting = asyncio.Event()

        async def observed(cls):
            waiting.set()
            return await original(cls)

        monkeypatch.setattr(
            RuntimeManager, "_acquire_async_transaction", classmethod(observed)
        )
        release = asyncio.create_task(RuntimeManager.release_lifespan(lease))
        await asyncio.wait_for(waiting.wait(), timeout=5)
        release.cancel()
        RuntimeManager._release_transaction(held)
        held = None
        with pytest.raises(asyncio.CancelledError):
            await release
        service.shutdown.assert_awaited_once_with()
        assert not RuntimeManager.is_initialized()
        assert not RuntimeManager._lifespan_tokens
    finally:
        if held is not None:
            RuntimeManager._release_transaction(held)
        if release is not None and not release.done():
            release.cancel()
        if release is not None:
            try:
                await asyncio.wait_for(release, timeout=5)
            except asyncio.CancelledError:
                pass
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_startup_and_rollback_failure_remains_http_503__b102(monkeypatch):
    cleanup_error = RuntimeError("offline rollback failure")
    service = SimpleNamespace(
        retire=Mock(),
        prepare_shutdown=Mock(),
        shutdown=AsyncMock(side_effect=[cleanup_error, None]),
    )
    container = _runtime_container(service)
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._refresh_cache",
        Mock(side_effect=ValueError("offline cache failure")),
    )
    app = FastAPI()
    FastAPIServer._add_exception_handlers(object(), app)

    @app.get("/startup")
    async def startup():
        await ensure_initialized_async()

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/startup")
        assert response.status_code == 503
        assert response.json()["type"] == AgentMapNotInitialized.__name__
        service.shutdown.assert_awaited_once_with()
    finally:
        await RuntimeManager.shutdown()
        await cleanup_runtime_manager_for_test()
