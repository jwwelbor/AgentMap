"""B102 stops new work while preserving admitted invocation authority."""

import asyncio
from contextlib import contextmanager
from threading import Event
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.exceptions import LLMConfigurationError
from agentmap.services.llm_client_factory import LLMClientFactory
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    Ledger,
    observed_response,
    raw_response,
)
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle_boundaries import (
    fallback_service,
)
from tests.fresh_suite.unit.services.test_llm_resilience import _make_service


def config(model="test-model"):
    return {"api_key": "offline-key", "model": model}


def _lease_context():
    from agentmap.services.llm import client_lifecycle

    context = getattr(client_lifecycle, "governed_use_lease", None)
    assert context is not None, "governed invocation lease context is required"
    return context


@contextmanager
def _using_lease(lease):
    context = _lease_context()
    token = context.set(lease)
    try:
        yield
    finally:
        context.reset(token)


def _retire(factory):
    retire = getattr(factory, "retire", None)
    assert callable(retire), "factory must expose the irreversible retire operation"
    retire()


async def _reap_retired_worker(factory, invocation, resume, release, entered, exited):
    resume.set()
    release.set()
    if not invocation.done():
        invocation.cancel()
    await asyncio.gather(invocation, return_exceptions=True)
    if entered.is_set():
        await asyncio.to_thread(exited.wait, 5)
    await factory.shutdown()


async def _cancel_and_check_retired_worker(factory, invocation):
    invocation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(invocation, timeout=5)
    with pytest.raises(LLMConfigurationError, match="governed provider work"):
        await asyncio.wait_for(factory.shutdown(), timeout=5)


@pytest.mark.asyncio
async def test_retired_factory_rejects_new_invocations_and_cached_acquisition__b102(
    monkeypatch,
):
    factory = LLMClientFactory(Mock())
    created = []
    monkeypatch.setattr(
        factory,
        "_create_langchain_client",
        lambda *args, **kwargs: created.append(object()) or created[-1],
    )
    cached = await factory.get_or_create_governed_client("openai", config())
    _retire(factory)

    with pytest.raises(LLMConfigurationError, match="retir"):
        factory.begin_governed_invocation()
    with pytest.raises(LLMConfigurationError, match="retir"):
        await factory.get_or_create_governed_client("openai", config())
    with pytest.raises(LLMConfigurationError, match="retir"):
        factory.get_or_create_client("openai", config())

    assert created == [cached]
    await factory.shutdown()


@pytest.mark.asyncio
async def test_retired_factory_requires_active_same_factory_context__b102(monkeypatch):
    factory, foreign_factory = LLMClientFactory(Mock()), LLMClientFactory(Mock())
    created = []
    monkeypatch.setattr(
        factory,
        "_create_langchain_client",
        lambda *args, **kwargs: created.append(object()) or created[-1],
    )
    admitted = factory.begin_governed_invocation()
    unrelated = factory.begin_governed_invocation()
    foreign = foreign_factory.begin_governed_invocation()
    released = factory.begin_governed_invocation()
    released.release()
    _retire(factory)

    with _using_lease(admitted):
        client = await factory.get_or_create_governed_client("openai", config())
    for lease in (None, foreign, released):
        with _using_lease(lease), pytest.raises(LLMConfigurationError, match="retir"):
            await factory.get_or_create_governed_client("openai", config("other"))
    # An unrelated active lease cannot authorize access from outside its context.
    with _using_lease(None), pytest.raises(LLMConfigurationError, match="retir"):
        await factory.get_or_create_governed_client("openai", config("unrelated"))

    assert created == [client]
    for lease in (admitted, unrelated, foreign):
        lease.release()
    await factory.shutdown()
    await foreign_factory.shutdown()


async def _run_call_across_retirement(service, factory, ledger, nested_ledger):
    entered, resume = asyncio.Event(), asyncio.Event()
    original_get = service._get_async_client
    nested_refused = []
    waiting = True

    async def pause_first_acquisition(provider, provider_config):
        nonlocal waiting
        if waiting:
            waiting = False
            entered.set()
            await asyncio.wait_for(resume.wait(), timeout=10)
            try:
                await service.call_llm_async(
                    [{"role": "user", "content": "nested"}],
                    provider="openai",
                    model="test-model",
                    attempt_lifecycle=nested_ledger,
                )
            except LLMConfigurationError as error:
                nested_refused.append(error)
        return await original_get(provider, provider_config)

    service._get_async_client = pause_first_acquisition
    invocation = asyncio.create_task(
        service.call_llm_async(
            [{"role": "user", "content": "outer"}],
            provider="openai",
            model="test-model",
            attempt_lifecycle=ledger,
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), timeout=10)
        _retire(factory)
        with pytest.raises(LLMConfigurationError, match="retir"):
            await service.call_llm_async(
                [{"role": "user", "content": "new"}],
                provider="openai",
                model="test-model",
                attempt_lifecycle=nested_ledger,
            )
        resume.set()
        return await invocation, nested_refused
    finally:
        resume.set()
        if not invocation.done():
            invocation.cancel()
        await asyncio.gather(invocation, return_exceptions=True)


@pytest.mark.asyncio
async def test_admitted_call_can_fallback_after_retirement__b102(monkeypatch):
    client, ledger, nested = Mock(), Ledger("1.00"), Ledger("1.00")
    client.ainvoke = AsyncMock(
        side_effect=lambda _: observed_response(
            raw_response(), ledger.descriptions[-1].resolved_provider
        )
    )
    service, factory = fallback_service(client), LLMClientFactory(Mock())
    service._client_factory = factory
    creations = []
    monkeypatch.setattr(
        factory,
        "_create_langchain_client",
        lambda *args, **kwargs: creations.append(object()) or client,
    )
    with monkeypatch.context() as patcher:
        patcher.setattr(
            "agentmap.services.llm_service.normalize_response_content",
            Mock(
                side_effect=[
                    RuntimeError("connection timeout"),
                    ("recovered", "text"),
                ]
            ),
        )
        result, nested_refused = await _run_call_across_retirement(
            service, factory, ledger, nested
        )

    assert result.text == "recovered" and len(nested_refused) == 1
    assert nested.events == []
    assert [event[0] for event in ledger.events] == [
        "begin",
        "settle",
        "begin",
        "settle",
    ]
    assert [item.attempt_kind for item in ledger.descriptions] == [
        "primary",
        "fallback",
    ]
    assert client.ainvoke.await_count == len(creations) == 2
    with pytest.raises(LLMConfigurationError, match="retir"):
        await factory.get_or_create_governed_client("openai", config())
    await factory.shutdown()


@pytest.mark.asyncio
async def test_retired_sync_worker_stays_owned_after_caller_cancellation__b102(
    monkeypatch,
):
    entered, release, exited = Event(), Event(), Event()

    class SyncClient:
        def invoke(self, _messages):
            entered.set()
            release.wait(5)
            exited.set()
            return observed_response(raw_response())

    service, factory = _make_service(), LLMClientFactory(Mock())
    service._client_factory = factory
    monkeypatch.setattr(
        factory, "_create_langchain_client", lambda *a, **k: SyncClient()
    )
    acquired, resume, ledger = asyncio.Event(), asyncio.Event(), Ledger("1.00")
    original_get = service._get_async_client

    async def pause_before_acquisition(provider, provider_config):
        acquired.set()
        await asyncio.wait_for(resume.wait(), timeout=10)
        return await original_get(provider, provider_config)

    service._get_async_client = pause_before_acquisition
    invocation = asyncio.create_task(
        service.call_llm_async(
            [{"role": "user", "content": "worker"}],
            provider="openai",
            model="test-model",
            attempt_lifecycle=ledger,
        )
    )
    try:
        await asyncio.wait_for(acquired.wait(), timeout=5)
        _retire(factory)
        resume.set()
        assert await asyncio.to_thread(entered.wait, 5)
        await _cancel_and_check_retired_worker(factory, invocation)

        release.set()
        assert await asyncio.to_thread(exited.wait, 5)
        await factory.shutdown()
        assert [event[0] for event in ledger.events] == ["begin", "settle"]
    finally:
        await _reap_retired_worker(
            factory, invocation, resume, release, entered, exited
        )
