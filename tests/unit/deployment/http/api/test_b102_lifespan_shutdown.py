"""B102 production HTTP lifespan owns the awaited LLM shutdown boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI

from agentmap.deployment.http.api.server import FastAPIServer, create_lifespan
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.init_ops import ensure_initialized_async
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm_client_factory import LLMClientFactory


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
    service = SimpleNamespace(shutdown=factory.shutdown)
    container = SimpleNamespace(
        app_config_service=Mock(),
        auth_service=Mock(),
        llm_service=Mock(return_value=service),
    )
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    RuntimeManager.reset()
    app = FastAPI()
    try:
        async with create_lifespan()(app):
            assert app.state.container is container
        assert closed == ["closed"]
        assert not RuntimeManager.is_initialized()
    finally:
        RuntimeManager.reset()


@pytest.mark.asyncio
async def test_lifespan_borrows_preexisting_runtime_without_shutdown__b102(monkeypatch):
    service = SimpleNamespace(shutdown=AsyncMock())
    container = SimpleNamespace(
        app_config_service=Mock(),
        auth_service=Mock(),
        llm_service=Mock(return_value=service),
    )
    RuntimeManager._container = container
    RuntimeManager._is_initialized = True
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    try:
        async with create_lifespan()(FastAPI()):
            assert RuntimeManager.get_container() is container
        assert RuntimeManager.get_container() is container
        service.shutdown.assert_not_awaited()
    finally:
        RuntimeManager.reset()


@pytest.mark.asyncio
async def test_overlapping_lifespans_keep_runtime_until_last_exit__b102(monkeypatch):
    service = SimpleNamespace(shutdown=AsyncMock())
    container = SimpleNamespace(
        app_config_service=Mock(),
        auth_service=Mock(),
        llm_service=Mock(return_value=service),
    )
    RuntimeManager.reset()

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
        RuntimeManager.reset()


@pytest.mark.asyncio
async def test_active_lifespan_rejects_runtime_replacement__b102(monkeypatch):
    service = SimpleNamespace(shutdown=AsyncMock())
    container = SimpleNamespace(
        app_config_service=Mock(),
        auth_service=Mock(),
        llm_service=Mock(return_value=service),
    )
    RuntimeManager.reset()
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
        RuntimeManager.reset()


@pytest.mark.asyncio
async def test_lifespan_uses_transactional_async_startup__b102(monkeypatch):
    failure = RuntimeError("startup transaction failed")
    acquire = AsyncMock(side_effect=failure)
    release = AsyncMock()
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.acquire_runtime_lifespan", acquire
    )
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.release_runtime_lifespan", release
    )

    with pytest.raises(RuntimeError) as caught:
        async with create_lifespan()(FastAPI()):
            pytest.fail("failed startup must not enter the application lifespan")

    assert caught.value is failure
    acquire.assert_awaited_once_with(config_file=None)
    release.assert_not_awaited()


@pytest.mark.asyncio
async def test_startup_and_rollback_failure_remains_http_503__b102(monkeypatch):
    cleanup_error = RuntimeError("offline rollback failure")
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
        RuntimeManager.reset()
