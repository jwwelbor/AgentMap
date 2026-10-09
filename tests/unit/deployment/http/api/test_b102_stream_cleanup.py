"""B102 preserves active stream failures when upstream cleanup also fails."""

import asyncio

import pytest

from agentmap.deployment.http.api.routes.stream import _sse_generator
from agentmap.deployment.http.api.sse import aclose_upstream_and_release


class ControlFlowFailure(BaseException):
    pass


class ConnectedRequest:
    async def is_disconnected(self):
        return False


class FailingUpstream:
    def __init__(self, next_error, close_error):
        self.next_error = next_error
        self.close_error = close_error

    async def __anext__(self):
        raise self.next_error

    async def aclose(self):
        raise self.close_error


class BlockingUpstream:
    def __init__(self, started, release, close_error):
        self.started = started
        self.release = release
        self.close_error = close_error

    async def __anext__(self):
        self.started.set()
        await asyncio.wait_for(self.release.wait(), timeout=5)
        return None

    async def aclose(self):
        raise self.close_error


class ClosingUpstream:
    def __init__(self):
        self.closed = False

    async def aclose(self):
        self.closed = True


class BlockingCloseUpstream:
    def __init__(self, started, release, closed):
        self.started = started
        self.release = release
        self.closed = closed

    async def aclose(self):
        self.started.set()
        await asyncio.wait_for(self.release.wait(), timeout=5)
        self.closed.set()


class SchedulingUpstream:
    def __init__(self):
        self.closed = False
        self.next_calls = 0

    def __anext__(self):
        self.next_calls += 1

        async def pull():
            return None

        return pull()

    async def aclose(self):
        self.closed = True


def _stream(upstream, semaphore=None):
    return _sse_generator(
        upstream=upstream,
        primed_first_event=None,
        primed_exhausted=True,
        graph_name="workflow",
        request=ConnectedRequest(),
        max_stream_duration_seconds=10,
        idle_timeout_seconds=10,
        heartbeat_interval_seconds=10,
        semaphore=semaphore,
    )


@pytest.mark.asyncio
async def test_sse_close_failure_preserves_stream_failure_and_releases_slot__b102():
    primary = RuntimeError("stream failed")
    cleanup_error = RuntimeError("private cleanup detail")
    semaphore = asyncio.Semaphore(0)
    upstream = FailingUpstream(primary, cleanup_error)

    with pytest.raises(RuntimeError) as caught:
        async for _ in _stream(upstream, semaphore):
            pass

    assert caught.value is primary
    assert primary.__notes__ == ["SSE upstream cleanup failed with RuntimeError"]
    assert semaphore._value == 1


@pytest.mark.asyncio
async def test_sse_child_control_flow_failure_preserves_close_failure__b102():
    primary = ControlFlowFailure("stream control flow")
    cleanup_error = RuntimeError("private cleanup detail")
    semaphore = asyncio.Semaphore(0)
    upstream = FailingUpstream(primary, cleanup_error)

    with pytest.raises(ControlFlowFailure) as caught:
        async for _ in _stream(upstream, semaphore):
            pass

    assert caught.value is primary
    assert primary.__notes__ == ["SSE upstream cleanup failed with RuntimeError"]
    assert semaphore._value == 1


@pytest.mark.asyncio
async def test_sse_raw_close_failure_is_secondary_to_stream_failure__b102():
    primary = RuntimeError("stream failed")
    cleanup_error = ControlFlowFailure("private control-flow detail")
    semaphore = asyncio.Semaphore(0)
    upstream = FailingUpstream(primary, cleanup_error)

    with pytest.raises(RuntimeError) as caught:
        async for _ in _stream(upstream, semaphore):
            pass

    assert caught.value is primary
    assert primary.__notes__ == ["SSE upstream cleanup failed with ControlFlowFailure"]
    assert semaphore._value == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_type", [RuntimeError, ControlFlowFailure])
async def test_sse_task_factory_rejection_closes_wrapper_and_releases_slot__b102(
    failure_type,
):
    loop = asyncio.get_running_loop()
    previous_factory = loop.get_task_factory()
    upstream = SchedulingUpstream()
    semaphore = asyncio.Semaphore(0)
    failure = failure_type("task factory unavailable")

    def reject_task(loop, coroutine, context=None):
        raise failure

    loop.set_task_factory(reject_task)
    try:
        with pytest.raises(failure_type, match="task factory unavailable") as caught:
            async for _ in _stream(upstream, semaphore):
                pass
    finally:
        loop.set_task_factory(previous_factory)

    assert upstream.next_calls == 0
    assert upstream.closed
    assert semaphore._value == 1
    assert caught.value is failure


@pytest.mark.asyncio
async def test_sse_close_failure_propagates_without_stream_failure__b102():
    cleanup_error = RuntimeError("close failed")
    upstream = FailingUpstream(StopAsyncIteration(), cleanup_error)

    with pytest.raises(RuntimeError) as caught:
        async for _ in _stream(upstream):
            pass

    assert caught.value is cleanup_error


@pytest.mark.asyncio
async def test_completed_pending_failure_is_preserved_during_cleanup__b102():
    pending_error = RuntimeError("pending event failed")

    async def fail_pending():
        raise pending_error

    pending = asyncio.create_task(fail_pending())
    await asyncio.sleep(0)
    assert pending.done()

    upstream = ClosingUpstream()
    semaphore = asyncio.Semaphore(0)
    with pytest.raises(RuntimeError) as caught:
        await aclose_upstream_and_release(pending, upstream, semaphore)

    assert caught.value is pending_error
    assert upstream.closed
    assert semaphore._value == 1


@pytest.mark.asyncio
async def test_sse_close_failure_does_not_replace_caller_cancellation__b102():
    started = asyncio.Event()
    release = asyncio.Event()
    cleanup_error = RuntimeError("private cleanup detail")
    upstream = BlockingUpstream(started, release, cleanup_error)

    async def consume():
        async for _ in _stream(upstream):
            pass

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError) as caught:
            await asyncio.wait_for(task, timeout=5)
        assert caught.value.__notes__ == [
            "SSE upstream cleanup failed with RuntimeError"
        ]
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancellation_during_pending_task_cleanup_is_rethrown__b102():
    cancellation_seen = asyncio.Event()
    release_pending = asyncio.Event()
    upstream = ClosingUpstream()
    semaphore = asyncio.Semaphore(0)

    async def pending_work():
        try:
            await asyncio.wait_for(asyncio.Event().wait(), timeout=5)
        except asyncio.CancelledError:
            cancellation_seen.set()
            await asyncio.wait_for(release_pending.wait(), timeout=5)

    pending = asyncio.create_task(pending_work())
    cleanup = asyncio.create_task(
        aclose_upstream_and_release(pending, upstream, semaphore)
    )
    try:
        await asyncio.wait_for(cancellation_seen.wait(), timeout=5)
        cleanup.cancel()
        release_pending.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(cleanup, timeout=5)

        assert pending.done()
        assert upstream.closed
        assert semaphore._value == 1
    finally:
        release_pending.set()
        if not cleanup.done():
            cleanup.cancel()
        await asyncio.gather(cleanup, pending, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancellation_during_upstream_close_waits_for_close_and_releases_slot__b102():
    started = asyncio.Event()
    release = asyncio.Event()
    closed = asyncio.Event()
    semaphore = asyncio.Semaphore(0)
    upstream = BlockingCloseUpstream(started, release, closed)
    cleanup = asyncio.create_task(
        aclose_upstream_and_release(None, upstream, semaphore)
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        cleanup.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(cleanup, timeout=5)

        assert closed.is_set()
        assert semaphore._value == 1
    finally:
        release.set()
        if not cleanup.done():
            cleanup.cancel()
        await asyncio.gather(cleanup, return_exceptions=True)
