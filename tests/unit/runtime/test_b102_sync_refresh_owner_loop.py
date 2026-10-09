"""Keep synchronous runtime refresh from losing loop-bound governed owners."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.init_ops import ensure_initialized
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm_client_factory import LLMClientFactory
from agentmap.services.llm_service import LLMService
from agentmap.services.protocols.service_protocols import LLMServiceProtocol
from tests.runtime_manager_test_support import (
    cleanup_runtime_manager_for_test,
    cleanup_runtime_manager_sync_for_test,
)

_NO_SYNC_RESERVATION = object()


class StartupControlFlowFailure(BaseException):
    pass


class _LLMServiceView:
    def __init__(self, service, sync_reservation=_NO_SYNC_RESERVATION):
        self._service = service
        self._sync_reservation = sync_reservation
        # Runtime protocols inspect concrete attributes on Python 3.12.
        for name, member in vars(LLMServiceProtocol).items():
            if not name.startswith("_") and callable(member):
                setattr(self, name, getattr(service, name))

    def __getattr__(self, name):
        if name == "prepare_sync_shutdown":
            if self._sync_reservation is _NO_SYNC_RESERVATION:
                raise AttributeError(name)
            return self._sync_reservation
        return getattr(self._service, name)


def _llm_service_view(sync_reservation=_NO_SYNC_RESERVATION):
    configuration = Mock()
    configuration.get_llm_pricing_config.return_value = {}
    configuration.get_llm_resilience_config.return_value = {}
    service = LLMService(configuration, Mock(), Mock(), Mock())
    return _LLMServiceView(service, sync_reservation)


def test_sync_startup_baseexception_rolls_back_new_runtime__b102(monkeypatch):
    """A failed cache validation must not publish a runtime to later callers."""
    failure = StartupControlFlowFailure("startup stopped")
    service = SimpleNamespace(
        retire=Mock(),
        prepare_shutdown=Mock(),
        shutdown=AsyncMock(),
    )
    candidate = SimpleNamespace(
        config=SimpleNamespace(path=Mock(return_value=None)),
        llm_service=Mock(return_value=service),
    )
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di",
        Mock(return_value=candidate),
    )

    def fail_validation(container, refresh):
        assert container is candidate
        assert refresh is False
        raise failure

    monkeypatch.setattr("agentmap.runtime.init_ops._validate_cache", fail_validation)
    cleanup_runtime_manager_sync_for_test()
    try:
        with pytest.raises(StartupControlFlowFailure) as caught:
            ensure_initialized()

        assert caught.value is failure
        assert RuntimeManager._current_container() is None
        assert RuntimeManager._pending_cleanup() is None
        service.retire.assert_called_once_with()
        service.prepare_shutdown.assert_called_once_with()
        service.shutdown.assert_awaited_once_with()
    finally:
        cleanup_runtime_manager_sync_for_test()


@pytest.mark.asyncio
async def test_sync_startup_failure_retains_cleanup_on_owner_loop__b102(monkeypatch):
    """A synchronous failure inside a loop keeps cleanup bound to that loop."""
    owner_loop = asyncio.get_running_loop()
    failure = StartupControlFlowFailure("startup stopped")
    service = SimpleNamespace(
        retire=Mock(),
        prepare_shutdown=Mock(),
        shutdown=AsyncMock(),
    )
    candidate = SimpleNamespace(
        config=SimpleNamespace(path=Mock(return_value=None)),
        llm_service=Mock(return_value=service),
    )
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di",
        Mock(return_value=candidate),
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._validate_cache",
        Mock(side_effect=failure),
    )
    await cleanup_runtime_manager_for_test()
    try:
        with pytest.raises(StartupControlFlowFailure) as caught:
            ensure_initialized()

        assert caught.value is failure
        assert RuntimeManager._current_container() is None
        assert RuntimeManager._pending_cleanup() is candidate
        assert RuntimeManager._pending_cleanup_loop is owner_loop
        service.shutdown.assert_not_awaited()

        await RuntimeManager.shutdown()
        assert RuntimeManager._pending_cleanup() is None
        service.shutdown.assert_awaited_once_with()
    finally:
        await cleanup_runtime_manager_for_test()


def test_sync_startup_failure_preserves_reused_runtime__b102(monkeypatch):
    """Validation failure must not detach a runtime that startup reused."""
    failure = StartupControlFlowFailure("cache validation stopped")
    service = SimpleNamespace(prepare_shutdown=Mock(), shutdown=AsyncMock())
    existing = SimpleNamespace(llm_service=Mock(return_value=service))
    initialize_di = Mock()
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", initialize_di)
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._validate_cache",
        Mock(side_effect=failure),
    )
    cleanup_runtime_manager_sync_for_test()
    RuntimeManager._container = existing
    RuntimeManager._is_initialized = True
    try:
        with pytest.raises(StartupControlFlowFailure) as caught:
            ensure_initialized()

        assert caught.value is failure
        assert RuntimeManager._current_container() is existing
        assert RuntimeManager._pending_cleanup() is None
        initialize_di.assert_not_called()
    finally:
        cleanup_runtime_manager_sync_for_test()


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
        def prepare_shutdown(self):
            return factory.prepare_shutdown()

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
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_sync_refresh_refusal_preserves_active_invocation__b102():
    factory = LLMClientFactory(Mock())
    invocation = factory.begin_governed_invocation()
    service = SimpleNamespace(
        prepare_shutdown=factory.prepare_shutdown,
        prepare_sync_shutdown=factory.prepare_sync_shutdown,
        shutdown=factory.shutdown,
    )
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    await cleanup_runtime_manager_for_test()
    RuntimeManager._container = container
    RuntimeManager._is_initialized = True
    try:
        with pytest.raises(AgentMapNotInitialized, match="ensure_initialized_async"):
            await asyncio.to_thread(RuntimeManager.initialize, refresh=True)
        assert RuntimeManager.get_container() is container
        assert not factory._closing
        subsequent_invocation = factory.begin_governed_invocation()
        subsequent_invocation.release()
        invocation.release()
        await factory.shutdown()
    finally:
        invocation.release()
        await cleanup_runtime_manager_for_test()


def test_sync_refresh_refuses_service_without_reservation_before_detaching__b102(
    monkeypatch,
):
    service = _llm_service_view()
    assert isinstance(service, LLMServiceProtocol)
    assert not hasattr(service, "prepare_sync_shutdown")
    old = SimpleNamespace(llm_service=Mock(return_value=service))
    replacement = object()
    initialize_di = Mock(return_value=replacement)
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", initialize_di)
    cleanup_runtime_manager_sync_for_test()
    RuntimeManager._container = old
    RuntimeManager._is_initialized = True
    RuntimeManager._runtime_config_file = "existing-config.yml"
    try:
        with pytest.raises(AgentMapNotInitialized, match="ensure_initialized_async"):
            RuntimeManager.initialize(refresh=True)
        assert RuntimeManager.get_container() is old
        assert RuntimeManager._runtime_config_file == "existing-config.yml"
        assert RuntimeManager.is_initialized()
        assert RuntimeManager._pending_cleanup() is None
        initialize_di.assert_not_called()
        invocation = service._service._client_factory.begin_governed_invocation()
        invocation.release()
    finally:
        cleanup_runtime_manager_sync_for_test()


@pytest.mark.parametrize("hook_kind", ["noncallable", "raises"])
def test_sync_refresh_rejects_invalid_reservation_before_detaching__b102(
    monkeypatch, hook_kind
):
    hook = (
        None
        if hook_kind == "noncallable"
        else Mock(side_effect=RuntimeError("reservation failed"))
    )
    service = _llm_service_view(hook)
    old = SimpleNamespace(llm_service=Mock(return_value=service))
    initialize_di = Mock(return_value=object())
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", initialize_di)
    cleanup_runtime_manager_sync_for_test()
    RuntimeManager._container, RuntimeManager._is_initialized = old, True
    RuntimeManager._runtime_config_file = "existing-config.yml"
    try:
        expected_error = (
            AgentMapNotInitialized if hook_kind == "noncallable" else RuntimeError
        )
        with pytest.raises(expected_error):
            RuntimeManager.initialize(refresh=True)
        assert RuntimeManager.get_container() is old
        assert RuntimeManager._runtime_config_file == "existing-config.yml"
        assert RuntimeManager.is_initialized()
        assert RuntimeManager._pending_cleanup() is None
        initialize_di.assert_not_called()
        invocation = service._service._client_factory.begin_governed_invocation()
        invocation.release()
    finally:
        cleanup_runtime_manager_sync_for_test()


@pytest.mark.asyncio
async def test_async_refresh_accepts_service_without_sync_reservation__b102(
    monkeypatch,
):
    service = _llm_service_view()
    old = SimpleNamespace(llm_service=Mock(return_value=service))
    replacement_service = SimpleNamespace(prepare_shutdown=Mock(), shutdown=AsyncMock())
    replacement = SimpleNamespace(
        config=SimpleNamespace(path=Mock(return_value=None)),
        llm_service=Mock(return_value=replacement_service),
    )
    startup = Mock()
    await cleanup_runtime_manager_for_test()
    RuntimeManager._container = old
    RuntimeManager._is_initialized = True
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=replacement)
    )
    try:
        await RuntimeManager.initialize_async(startup, refresh=True)
        assert RuntimeManager.get_container() is replacement
        startup.assert_called_once_with(replacement, True)
        assert service._service._client_factory._closed
    finally:
        await cleanup_runtime_manager_for_test()
