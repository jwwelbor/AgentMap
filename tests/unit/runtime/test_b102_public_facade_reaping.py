"""Bound and preserve cleanup outcomes in runtime starvation tests."""

import asyncio

import pytest

from agentmap.async_lifecycle import await_terminal_task

GUARD_SECONDS, TEST_TIMEOUT_SECONDS, REAP_SECONDS = 10, 1, 2
CANCELLATION_MESSAGE = "offline caller cancellation"
TIMEOUT_MESSAGE = "public facades starved the runtime lifecycle"
EARLY_ERRORS = AssertionError("assertion"), RuntimeError("error"), BaseException("base")


async def reap_tasks(tasks, *, timeout=REAP_SECONDS):
    async def reap():
        done, pending = await asyncio.wait(tasks, timeout=timeout)
        if pending:
            for task in pending:
                task.cancel()
            reaped, pending = await asyncio.wait(pending, timeout=timeout)
            done.update(reaped)
        outcomes = []
        for task in tasks:
            if task not in done:
                outcomes.append(
                    TimeoutError("test cleanup did not reach a terminal state")
                )
            elif task.cancelled():
                outcomes.append(asyncio.CancelledError())
            else:
                try:
                    outcomes.append(task.result())
                except BaseException as error:
                    outcomes.append(error)
        return outcomes

    outcome = await await_terminal_task(asyncio.create_task(reap()))
    return outcome.value, outcome.caller_cancellation


def _raise_guard_failure(primary, outcomes) -> None:
    failures = [x for x in outcomes if isinstance(x, BaseException)]
    failures = [x for x in failures if x is not primary]
    if failures:
        secondary = BaseExceptionGroup("deadlock guard cleanup failed", failures)
        if primary is not None:
            raise primary from secondary
        raise secondary
    if primary is not None:
        raise primary


async def guard_completion(
    task,
    release,
    tasks,
    *,
    timeout=GUARD_SECONDS,
    entered=None,
    on_timeout=None,
    on_failure=None,
) -> None:
    primary = None
    timed_out = False
    try:
        if entered is not None:
            entered.set()
        done, _ = await asyncio.wait([task], timeout=timeout)
        if not done:
            primary = AssertionError(TIMEOUT_MESSAGE)
            timed_out = True
        else:
            task.result()
    except BaseException as error:
        primary = error
    finally:
        if timed_out and on_timeout is not None:
            on_timeout()
        if primary is not None and on_failure is not None:
            on_failure()
        release.set()
        outcomes, cancellation = await reap_tasks([task, *tasks], timeout=REAP_SECONDS)
        if primary is None:
            primary = cancellation
    _raise_guard_failure(primary, outcomes)


@pytest.mark.parametrize("primary", EARLY_ERRORS)
@pytest.mark.asyncio
async def test_early_lifecycle_failure_releases_and_reaps_gated_tasks__b102(primary):
    release, lifecycle_started = (asyncio.Event() for _ in range(2))
    completed = []

    async def gated(label):
        await asyncio.wait_for(release.wait(), timeout=10)
        completed.append(label)

    owner = asyncio.create_task(gated("owner"))
    facades = [asyncio.create_task(gated(f"facade-{index}")) for index in range(2)]

    async def fail_after_early_start():
        lifecycle_started.set()
        raise primary

    completion = asyncio.create_task(fail_after_early_start())
    try:
        await asyncio.wait_for(lifecycle_started.wait(), timeout=TEST_TIMEOUT_SECONDS)
        with pytest.raises(type(primary)) as caught:
            await guard_completion(completion, release, [owner, *facades])
        assert caught.value is primary
        assert caught.value.__cause__ is None
        assert release.is_set()
        assert all(task.done() for task in [completion, owner, *facades])
        assert completed == ["owner", "facade-0", "facade-1"]
    finally:
        release.set()
        await asyncio.gather(owner, *facades, completion, return_exceptions=True)


@pytest.mark.parametrize("route", ["cancellation", "timeout"])
@pytest.mark.asyncio
async def test_guard_reaps_gated_tasks_on_cancellation_or_timeout__b102(route):
    release, timeout_cleanup, entered = (asyncio.Event() for _ in range(3))
    completed = []

    async def gated(label):
        await asyncio.wait_for(release.wait(), timeout=10)
        assert route != "timeout" or timeout_cleanup.is_set()
        completed.append(label)

    owner, facade, completion = [
        asyncio.create_task(gated(label)) for label in ("owner", "facade", "completion")
    ]
    guard = asyncio.create_task(
        guard_completion(
            completion,
            release,
            [owner, facade],
            timeout=0.01 if route == "timeout" else GUARD_SECONDS,
            entered=entered,
            on_timeout=timeout_cleanup.set,
        )
    )
    expected = asyncio.CancelledError if route == "cancellation" else AssertionError
    try:
        await asyncio.wait_for(entered.wait(), timeout=TEST_TIMEOUT_SECONDS)
        if route == "cancellation":
            guard.cancel(CANCELLATION_MESSAGE)
        done, _ = await asyncio.wait([guard], timeout=TEST_TIMEOUT_SECONDS)
        assert done == {guard}
        with pytest.raises(expected) as caught:
            guard.result()
        expected_message = (CANCELLATION_MESSAGE, TIMEOUT_MESSAGE)[route == "timeout"]
        assert caught.value.args == (expected_message,)
        assert caught.value.__cause__ is None
        assert release.is_set()
        assert all(task.done() for task in [owner, facade, completion, guard])
        assert completed == ["owner", "facade", "completion"]
    finally:
        release.set()
        if not guard.done():
            guard.cancel()
        cleanup_outcomes, cleanup_cancellation = await reap_tasks(
            [owner, facade, completion, guard]
        )
    assert cleanup_cancellation is None and cleanup_outcomes[:3] == [None, None, None]
    assert isinstance(cleanup_outcomes[3], expected)
    assert timeout_cleanup.is_set() is (route == "timeout")


@pytest.mark.asyncio
async def test_reaper_bounds_cancellation_resistant_cleanup__b102():
    release = asyncio.Event()

    async def resist_cancellation():
        try:
            await asyncio.wait_for(release.wait(), timeout=10)
        except asyncio.CancelledError:
            await asyncio.wait_for(release.wait(), timeout=10)

    task = asyncio.create_task(resist_cancellation())
    try:
        outcomes, cancellation = await reap_tasks([task], timeout=0.01)
        assert cancellation is None
        assert len(outcomes) == 1 and isinstance(outcomes[0], TimeoutError)
        assert not task.done()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
