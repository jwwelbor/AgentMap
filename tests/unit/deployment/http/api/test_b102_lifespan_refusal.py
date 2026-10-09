"""B102 transfers retiring lifespan ownership when active work blocks shutdown."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.lifespan_mixin import effective_config_file
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm_client_factory import LLMClientFactory
from agentmap.services.llm_service import LLMService
from tests.runtime_manager_test_support import cleanup_runtime_manager_for_test
from tests.utils.mock_service_factory import MockServiceFactory


@pytest.mark.asyncio
async def test_last_lifespan_refusal_transfers_runtime_to_pending_cleanup__b102(
    monkeypatch,
):
    factory = LLMClientFactory(Mock())
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
    await cleanup_runtime_manager_for_test()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=container)
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", Mock())
    lease = invocation = None
    try:
        lease, current = await RuntimeManager.acquire_lifespan(Mock())
        assert current is container
        invocation = factory.begin_governed_invocation()
        with pytest.raises(LLMConfigurationError, match="governed provider work"):
            await RuntimeManager.release_lifespan(lease)
        assert RuntimeManager._pending_cleanup() is container
        assert lease not in RuntimeManager._lifespan_tokens
        with pytest.raises(AgentMapNotInitialized, match="cleanup is pending"):
            RuntimeManager.get_container()
        assert not factory._closing
        invocation.release()
        await RuntimeManager.shutdown()
        assert RuntimeManager._pending_cleanup() is None
        assert not RuntimeManager.is_initialized()
        assert factory._closed
    finally:
        if invocation is not None:
            invocation.release()
        if RuntimeManager._pending_cleanup() is not None:
            await RuntimeManager.shutdown()
        elif lease in RuntimeManager._lifespan_tokens:
            await RuntimeManager.release_lifespan(lease)
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_lifespan_rejects_existing_runtime_owned_by_foreign_loop__b102():
    factory = LLMClientFactory(Mock())
    owner_loop = asyncio.new_event_loop()
    factory._owner_loop = owner_loop
    service = LLMService(
        configuration=MockServiceFactory.create_mock_app_config_service(),
        logging_service=MockServiceFactory.create_mock_logging_service(),
        routing_service=Mock(),
        llm_models_config_service=MockServiceFactory.create_mock_llm_models_config_service(),
        routing_config_service=Mock(),
    )
    service._client_factory = factory
    container = SimpleNamespace(
        app_config_service=Mock(),
        auth_service=Mock(),
        llm_service=Mock(return_value=service),
    )
    await cleanup_runtime_manager_for_test()
    RuntimeManager._container = container
    RuntimeManager._is_initialized = True
    RuntimeManager._runtime_config_file = effective_config_file(None)
    startup = Mock()
    try:
        with pytest.raises(LLMConfigurationError, match="owning event loop"):
            await RuntimeManager.acquire_lifespan(startup)

        assert RuntimeManager._container is container
        assert RuntimeManager._pending_cleanup() is None
        assert RuntimeManager._lifespan_tokens == set()
        assert factory._owner_loop is owner_loop
        startup.assert_not_called()
    finally:
        factory._owner_loop = asyncio.get_running_loop()
        for lease in tuple(RuntimeManager._lifespan_tokens):
            await RuntimeManager.release_lifespan(lease)
        if RuntimeManager.is_initialized():
            await RuntimeManager.shutdown()
        await cleanup_runtime_manager_for_test()
        owner_loop.close()
