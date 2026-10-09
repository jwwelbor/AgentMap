"""B102 binds governed client lifecycle operations to one owner loop."""

import asyncio
from threading import Event
from unittest.mock import Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.runtime_manager_test_support import cancel_tasks_for_test


def config(model: str) -> dict[str, str]:
    return {"model": model, "api_key": "offline-key"}


def factory_state(factory):
    return (
        dict(factory._clients),
        dict(factory._api_key_tokens),
        dict(factory._pending_tokens),
        tuple(factory._owners),
        set(factory._active_governed),
        factory._owner_loop,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["same", "new"])
async def test_governed_factory_rejects_foreign_loop_cache_access__b102(
    monkeypatch, model
):
    factory = LLMClientFactory(Mock())
    built: list[object] = []
    entered, release = Event(), Event()

    def build(*args, **kwargs):
        client = object()
        built.append(client)
        entered.set()
        assert release.wait(5)
        return client

    monkeypatch.setattr(factory, "_create_langchain_client", build)
    owner_loop = asyncio.get_running_loop()
    owner_build = asyncio.create_task(
        factory.get_or_create_governed_client("openai", config("same"))
    )

    def acquire_from_foreign_loop():
        return asyncio.run(
            factory.get_or_create_governed_client("openai", config(model))
        )

    try:
        assert await asyncio.to_thread(entered.wait, 5)
        before = factory_state(factory)
        assert before[-1] is owner_loop
        with pytest.raises(LLMConfigurationError, match="owning event loop"):
            await asyncio.to_thread(acquire_from_foreign_loop)
        assert factory_state(factory) == before
        release.set()

        cached = await owner_build
        assert len(built) == 1
        assert (
            await factory.get_or_create_governed_client("openai", config("same"))
            is cached
        )
    finally:
        release.set()
        try:
            await cancel_tasks_for_test(owner_build)
        finally:
            await factory.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["prepare", "shutdown", "retire"])
async def test_factory_lifecycle_refuses_foreign_loop_before_mutation__b102(
    monkeypatch, operation
):
    factory = LLMClientFactory(Mock())
    monkeypatch.setattr(
        factory, "_create_langchain_client", lambda *args, **kwargs: object()
    )
    await factory.get_or_create_governed_client("openai", config("same"))
    owner_loop = asyncio.get_running_loop()

    async def foreign_action():
        if operation == "prepare":
            factory.prepare_shutdown()
        elif operation == "shutdown":
            await factory.shutdown()
        else:
            factory.retire()

    with pytest.raises(LLMConfigurationError, match="owning event loop"):
        await asyncio.to_thread(lambda: asyncio.run(foreign_action()))

    assert factory._owner_loop is owner_loop
    assert not factory._closing and not factory._closed and not factory._retired
    lease = factory.begin_governed_invocation()
    lease.release()
    await factory.shutdown()


def test_governed_factory_keeps_closed_owner_loop_evidence__b102(monkeypatch):
    factory = LLMClientFactory(Mock())
    monkeypatch.setattr(
        factory, "_create_langchain_client", lambda *args, **kwargs: object()
    )
    owner_loop = asyncio.new_event_loop()
    foreign_loop = asyncio.new_event_loop()
    try:
        owner_loop.run_until_complete(
            factory.get_or_create_governed_client("openai", config("same"))
        )
    finally:
        owner_loop.close()

    try:
        with pytest.raises(LLMConfigurationError, match="owning event loop is closed"):
            foreign_loop.run_until_complete(
                factory.get_or_create_governed_client("openai", config("same"))
            )
        assert factory._owner_loop is owner_loop
        assert not factory._closing and not factory._closed
    finally:
        foreign_loop.close()
