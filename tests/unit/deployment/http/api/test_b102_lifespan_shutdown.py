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
    initialized = AsyncMock()
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.ensure_initialized_async", initialized
    )
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.get_container",
        Mock(return_value=container),
    )
    RuntimeManager._container = container
    RuntimeManager._is_initialized = True
    app = FastAPI()
    try:
        async with create_lifespan()(app):
            assert app.state.container is container
        initialized.assert_awaited_once_with(config_file=None)
        assert closed == ["closed"]
        assert not RuntimeManager.is_initialized()
    finally:
        RuntimeManager.reset()


@pytest.mark.asyncio
async def test_lifespan_uses_transactional_async_startup__b102(monkeypatch):
    failure = RuntimeError("startup transaction failed")
    initialize = AsyncMock(side_effect=failure)
    shutdown = AsyncMock()
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.ensure_initialized_async", initialize
    )
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.shutdown_runtime", shutdown
    )

    with pytest.raises(RuntimeError) as caught:
        async with create_lifespan()(FastAPI()):
            pytest.fail("failed startup must not enter the application lifespan")

    assert caught.value is failure
    initialize.assert_awaited_once_with(config_file=None)
    shutdown.assert_not_awaited()


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
