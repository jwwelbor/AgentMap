"""B102 production HTTP lifespan owns the awaited LLM shutdown boundary."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI

from agentmap.deployment.http.api.server import create_lifespan
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
        "agentmap.deployment.http.api.server.ensure_initialized", Mock()
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
        assert closed == ["closed"]
        assert not RuntimeManager.is_initialized()
    finally:
        RuntimeManager.reset()
