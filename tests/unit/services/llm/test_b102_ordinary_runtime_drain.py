"""Runtime cleanup with an ordinary builder must bypass occupied workers."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.unit.services.llm.test_b102_ordinary_drain_bridge import (
    CONFIG,
    install_builder,
)


@pytest.mark.asyncio
async def test_runtime_shutdown_drains_ordinary_builder_before_facade_waiters_release(
    monkeypatch,
):
    assert RuntimeManager._container is None
    assert RuntimeManager._pending_cleanup_container is None
    assert RuntimeManager._transaction_owner is None
    loop = asyncio.get_running_loop()
    factory = LLMClientFactory(Mock())
    container = SimpleNamespace(llm_service=Mock(return_value=factory))
    monkeypatch.setattr(RuntimeManager, "_container", container)
    monkeypatch.setattr(RuntimeManager, "_is_initialized", True)
    entered, registered, release = install_builder(monkeypatch, factory, loop)
    blocked = asyncio.Event()
    original_wait = RuntimeManager._transaction_condition.wait

    def observed_wait(timeout=None):
        loop.call_soon_threadsafe(blocked.set)
        return original_wait(5 if timeout is None else timeout)

    monkeypatch.setattr(RuntimeManager._transaction_condition, "wait", observed_wait)
    executor = ThreadPoolExecutor(max_workers=1)
    loop.set_default_executor(executor)
    with ThreadPoolExecutor(max_workers=1) as builders:
        construction = builders.submit(factory.get_or_create_client, "openai", CONFIG)
        try:
            await asyncio.wait_for(entered.wait(), 5)
            shutdown = asyncio.create_task(RuntimeManager.shutdown())
            await asyncio.wait_for(registered.wait(), 5)
            facade = loop.run_in_executor(None, RuntimeManager.reset)
            await asyncio.wait_for(blocked.wait(), 5)
            assert not facade.done() and RuntimeManager._transaction_owner is not None
            release.set()
            await asyncio.wait_for(shutdown, 2)
            assert factory._closed
            assert RuntimeManager._pending_cleanup_container is None
            construction.result(timeout=5)
            await asyncio.wait_for(facade, 5)
        finally:
            release.set()
            await asyncio.wait_for(RuntimeManager.shutdown(), 5)
    executor.shutdown(wait=True)
    assert RuntimeManager._container is None
    assert RuntimeManager._transaction_owner is None
