"""B102 neutral terminal-task waiting keeps cancellation origins distinct."""

import asyncio
from threading import Event

import pytest

from agentmap import async_lifecycle
from agentmap.async_lifecycle import await_terminal_task


@pytest.mark.asyncio
async def test_prior_cancellation_count_does_not_relabel_child_cancellation__b102():
    current = asyncio.current_task()
    assert current is not None
    current.cancel()
    try:
        await asyncio.sleep(0)
    except asyncio.CancelledError:
        pass

    async def cancelled_child():
        raise asyncio.CancelledError("child stopped")

    try:
        outcome = await await_terminal_task(asyncio.create_task(cancelled_child()))
        assert outcome.caller_cancellation is None
        assert isinstance(outcome.task_error, asyncio.CancelledError)
    finally:
        current.uncancel()


@pytest.mark.asyncio
async def test_repeated_caller_cancellation_is_observed_in_order__b102(monkeypatch):
    release = asyncio.Event()
    started, first_seen, second_seen = Event(), Event(), Event()
    real_count = async_lifecycle._cancellation_count

    def observed_count(task):
        count = real_count(task)
        if count == 0:
            started.set()
        elif count == 1:
            first_seen.set()
        elif count == 2:
            second_seen.set()
        return count

    monkeypatch.setattr(async_lifecycle, "_cancellation_count", observed_count)
    inner = asyncio.create_task(release.wait())
    waiter = asyncio.create_task(await_terminal_task(inner))
    assert await asyncio.to_thread(started.wait, 5)
    waiter.cancel()
    assert await asyncio.to_thread(first_seen.wait, 5)
    waiter.cancel()
    assert await asyncio.to_thread(second_seen.wait, 5)
    release.set()
    outcome = await waiter
    assert isinstance(outcome.caller_cancellation, asyncio.CancelledError)
    assert outcome.value is True
