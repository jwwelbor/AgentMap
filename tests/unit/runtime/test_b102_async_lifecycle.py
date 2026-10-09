"""B102 neutral terminal-task waiting keeps cancellation origins distinct."""

import asyncio
from threading import Event

import pytest

from agentmap import async_lifecycle
from agentmap.async_lifecycle import await_terminal_task, create_task_or_close
from agentmap.runtime.cleanup_mixin import RuntimeCleanupMixin


class ControlFlowFailure(BaseException):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_type", [RuntimeError, ControlFlowFailure])
async def test_task_factory_failure_closes_unscheduled_coroutine__b102(failure_type):
    async def work():
        return None

    failure = failure_type("task factory unavailable")
    coroutine = work()
    loop = asyncio.get_running_loop()
    previous_factory = loop.get_task_factory()

    def reject_task(loop, coroutine, context=None):
        raise failure

    loop.set_task_factory(reject_task)
    try:
        with pytest.raises(failure_type, match="task factory unavailable") as caught:
            create_task_or_close(coroutine)
    finally:
        loop.set_task_factory(previous_factory)

    assert coroutine.cr_frame is None
    assert caught.value is failure


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
    inner = asyncio.create_task(asyncio.wait_for(release.wait(), timeout=5))
    waiter = asyncio.create_task(await_terminal_task(inner))
    try:
        assert await asyncio.to_thread(started.wait, 5)
        waiter.cancel()
        assert await asyncio.to_thread(first_seen.wait, 5)
        waiter.cancel()
        assert await asyncio.to_thread(second_seen.wait, 5)
        release.set()
        outcome = await waiter
        assert isinstance(outcome.caller_cancellation, asyncio.CancelledError)
        assert outcome.value is True
    finally:
        release.set()
        if not waiter.done():
            waiter.cancel()
        await asyncio.gather(waiter, inner, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("already_done", [False, True])
async def test_terminal_wait_records_child_control_flow_failure__b102(already_done):
    failure = ControlFlowFailure("child control flow")
    release = asyncio.Event()

    async def child():
        if not already_done:
            await asyncio.wait_for(release.wait(), timeout=5)
        raise failure

    task = asyncio.create_task(child())
    if already_done:
        await asyncio.sleep(0)
    else:
        waiter = asyncio.create_task(await_terminal_task(task))
        await asyncio.sleep(0)
        release.set()
        outcome = await waiter
        assert outcome.task_error is failure
        return

    outcome = await await_terminal_task(task)
    assert outcome.task_error is failure


@pytest.mark.asyncio
async def test_terminal_wait_retains_child_failure_with_caller_cancellation__b102():
    failure = ControlFlowFailure("child control flow")
    started, release = asyncio.Event(), asyncio.Event()

    async def child():
        started.set()
        await asyncio.wait_for(release.wait(), timeout=5)
        raise failure

    task = asyncio.create_task(child())
    waiter = asyncio.create_task(await_terminal_task(task))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        await asyncio.sleep(0)
        waiter.cancel()
        release.set()
        outcome = await waiter
        assert isinstance(outcome.caller_cancellation, asyncio.CancelledError)
        assert outcome.task_error is failure
    finally:
        release.set()
        if not waiter.done():
            waiter.cancel()
        await asyncio.gather(waiter, task, return_exceptions=True)


@pytest.mark.asyncio
async def test_runtime_rollback_retains_child_control_flow_failure__b102():
    failure = ControlFlowFailure("rollback control flow")

    class Cleanup(RuntimeCleanupMixin):
        @classmethod
        def _current_container(cls):
            return object()

        @classmethod
        def _retire_and_adopt_pending_cleanup(cls, candidate, *, owner_loop=None):
            raise failure

    outcome = await Cleanup._rollback_candidate(previous=None, refresh=True)
    assert outcome.task_error is failure


def test_cleanup_failure_becomes_primary_when_no_error_is_active__b102():
    cleanup_error = RuntimeError("cleanup failed")

    with pytest.raises(RuntimeError) as caught:
        async_lifecycle.raise_cleanup_error_or_note(
            None, cleanup_error, operation="runtime cleanup"
        )

    assert caught.value is cleanup_error


def test_cleanup_failure_adds_only_its_type_to_the_active_error__b102():
    primary_error = RuntimeError("application failed")
    cleanup_error = RuntimeError("cleanup secret")

    async_lifecycle.raise_cleanup_error_or_note(
        primary_error, cleanup_error, operation="runtime cleanup"
    )

    assert primary_error.__notes__ == ["runtime cleanup failed with RuntimeError"]
    assert "cleanup secret" not in " ".join(primary_error.__notes__)
