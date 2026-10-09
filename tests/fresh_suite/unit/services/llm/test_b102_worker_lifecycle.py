"""B102 retains sync provider resource use after caller cancellation."""

import asyncio
from contextlib import suppress
from threading import Event

import pytest

from agentmap.exceptions import LLMConfigurationError
from tests.fresh_suite.unit.services.llm.test_attempt_lifecycle import (
    Ledger,
    raw_response,
    service_with_client,
)


async def _cancel_managed_call(service, ledger, entered):
    invocation = asyncio.create_task(
        service.call_llm_async(
            messages=[{"role": "user", "content": "synthetic"}],
            provider="openai",
            model="test-model",
            attempt_lifecycle=ledger,
        )
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        invocation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await invocation
    finally:
        if not invocation.done():
            invocation.cancel()
            with suppress(asyncio.CancelledError):
                await invocation


@pytest.mark.asyncio
async def test_worker_use_survives_call_cancellation_until_thread_exits__b102(
    monkeypatch,
):
    entered, release, exited = Event(), Event(), Event()

    class BlockingClient:
        def invoke(self, messages):
            entered.set()
            release.wait(5)
            exited.set()
            return raw_response()

    service = service_with_client(BlockingClient())
    factory = service._client_factory
    worker_released = asyncio.Event()
    loop = asyncio.get_running_loop()
    begin_worker = factory.begin_governed_worker

    def track_worker_release():
        lease = begin_worker()
        release_lease = lease.release

        def release_tracked_worker():
            release_lease()
            loop.call_soon_threadsafe(worker_released.set)

        lease.release = release_tracked_worker
        return lease

    monkeypatch.setattr(factory, "begin_governed_worker", track_worker_release)
    ledger = Ledger("1")
    try:
        await _cancel_managed_call(service, ledger, entered)
        assert [event[0] for event in ledger.events] == ["begin", "settle"]
        assert ledger.rows["1"].classification == "cancelled"
        with pytest.raises(LLMConfigurationError, match="governed provider work"):
            await service.shutdown()
        assert not factory._closing
        release.set()
        assert await asyncio.to_thread(exited.wait, 5)
        await asyncio.wait_for(worker_released.wait(), 5)
        await service.shutdown()
    finally:
        release.set()
        if entered.is_set():
            await asyncio.to_thread(exited.wait, 5)
            await asyncio.wait_for(worker_released.wait(), 5)
        await service.shutdown()
