"""Keep synchronous runtime refresh from losing loop-bound governed owners."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm_client_factory import LLMClientFactory


@pytest.mark.asyncio
async def test_sync_shutdown_reservation_rejects_later_governed_construction__b102():
    factory = LLMClientFactory(Mock())
    assert factory.prepare_sync_shutdown()
    with pytest.raises(LLMConfigurationError, match="shut down"):
        await factory.get_or_create_governed_client(
            "openai", {"model": "offline", "api_key": "offline"}
        )
    await factory.shutdown()


@pytest.mark.asyncio
async def test_sync_refresh_keeps_loop_bound_governed_runtime_live__b102(monkeypatch):
    caller_loop = asyncio.get_running_loop()
    factory = LLMClientFactory(Mock())

    class LoopBoundResource:
        async def aclose(self):
            assert asyncio.get_running_loop() is caller_loop

    def build(*args, owner, **kwargs):
        owner.create_async(LoopBoundResource)
        return object()

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    await factory.get_or_create_governed_client(
        "openai", {"model": "offline", "api_key": "offline"}
    )

    class Service:
        async def shutdown(self):
            await factory.shutdown()

        def prepare_sync_shutdown(self):
            return factory.prepare_sync_shutdown()

    old = SimpleNamespace(llm_service=Mock(return_value=Service()))
    RuntimeManager._container = old
    RuntimeManager._is_initialized = True
    try:
        with pytest.raises(AgentMapNotInitialized, match="async"):
            await asyncio.to_thread(RuntimeManager.initialize, refresh=True)
        assert RuntimeManager.get_container() is old
    finally:
        RuntimeManager.reset()
        if not factory._closed:
            await factory.shutdown()
