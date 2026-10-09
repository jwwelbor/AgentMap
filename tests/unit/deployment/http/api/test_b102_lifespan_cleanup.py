"""B102 verifies HTTP lifespan and runtime cleanup ownership."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI

from agentmap.deployment.http.api.server import create_lifespan
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.runtime_manager import RuntimeManager
from tests.runtime_manager_test_support import cleanup_runtime_manager_for_test


@pytest.mark.asyncio
async def test_lifespan_uses_transactional_async_startup__b102(monkeypatch):
    failure = RuntimeError("startup transaction failed")
    acquire = AsyncMock(side_effect=failure)
    release = AsyncMock()
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.acquire_runtime_lifespan", acquire
    )
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.release_runtime_lifespan", release
    )

    with pytest.raises(RuntimeError) as caught:
        async with create_lifespan()(FastAPI()):
            pytest.fail("failed startup must not enter the application lifespan")

    assert caught.value is failure
    acquire.assert_awaited_once_with(config_file=None)
    release.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_site", ["startup", "application", "cancellation"])
async def test_release_failure_preserves_http_lifespan_primary__b102(
    monkeypatch, failure_site
):
    primary = (
        asyncio.CancelledError("caller cancelled")
        if failure_site == "cancellation"
        else RuntimeError("primary failure")
    )
    cleanup_error = RuntimeError("private cleanup detail")
    lease = object()
    container = SimpleNamespace(app_config_service=Mock(), auth_service=Mock())
    acquire = AsyncMock(return_value=(lease, container))
    release = AsyncMock(side_effect=cleanup_error)
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.acquire_runtime_lifespan", acquire
    )
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.release_runtime_lifespan", release
    )

    if failure_site == "startup":

        class BrokenState:
            def __setattr__(self, name, value):
                raise primary

        app = SimpleNamespace(state=BrokenState())
        action = create_lifespan()(app).__aenter__()
    else:

        async def run_application():
            async with create_lifespan()(FastAPI()):
                raise primary

        action = run_application()

    with pytest.raises(type(primary)) as caught:
        await action

    assert caught.value is primary
    assert primary.__notes__ == ["HTTP lifespan cleanup failed with RuntimeError"]
    release.assert_awaited_once_with(lease)


@pytest.mark.asyncio
async def test_http_lifespan_cleanup_failure_propagates_without_primary__b102(
    monkeypatch,
):
    cleanup_error = RuntimeError("release failed")
    lease = object()
    container = SimpleNamespace(app_config_service=Mock(), auth_service=Mock())
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.acquire_runtime_lifespan",
        AsyncMock(return_value=(lease, container)),
    )
    release = AsyncMock(side_effect=cleanup_error)
    monkeypatch.setattr(
        "agentmap.deployment.http.api.server.release_runtime_lifespan", release
    )

    with pytest.raises(RuntimeError) as caught:
        async with create_lifespan()(FastAPI()):
            pass

    assert caught.value is cleanup_error
    release.assert_awaited_once_with(lease)


@pytest.mark.asyncio
async def test_last_lifespan_release_retains_failed_cleanup_for_retry__b102(
    monkeypatch,
):
    failure = RuntimeError("offline lifespan cleanup failure")
    service = SimpleNamespace(
        retire=Mock(),
        prepare_shutdown=Mock(),
        shutdown=AsyncMock(side_effect=[failure, None]),
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
    lease = None
    try:
        lease, current = await RuntimeManager.acquire_lifespan(Mock())
        assert current is container
        with pytest.raises(RuntimeError, match="lifespan cleanup"):
            await RuntimeManager.release_lifespan(lease)
        assert lease not in RuntimeManager._lifespan_tokens
        assert RuntimeManager._pending_cleanup() is container
        with pytest.raises(AgentMapNotInitialized, match="cleanup is pending"):
            RuntimeManager.get_container()

        await RuntimeManager.shutdown()
        assert service.shutdown.await_count == 2
        assert RuntimeManager._pending_cleanup() is None
    finally:
        if lease in RuntimeManager._lifespan_tokens:
            await RuntimeManager.release_lifespan(lease)
        if RuntimeManager._pending_cleanup() is not None:
            await RuntimeManager.shutdown()
        await cleanup_runtime_manager_for_test()


@pytest.mark.asyncio
async def test_release_scheduling_failure_transfers_pending_owner__b102(monkeypatch):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
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
    loop = asyncio.get_running_loop()
    previous_factory = loop.get_task_factory()
    lease = None

    def reject_task(loop, coroutine, context=None):
        raise RuntimeError("task factory unavailable")

    try:
        lease, _ = await RuntimeManager.acquire_lifespan(Mock())
        loop.set_task_factory(reject_task)
        with pytest.raises(RuntimeError, match="task factory unavailable") as caught:
            await RuntimeManager.release_lifespan(lease)
        loop.set_task_factory(previous_factory)
        assert caught.value.__notes__ == [
            "HTTP lifespan release cleanup failed with RuntimeError"
        ]
        assert lease not in RuntimeManager._lifespan_tokens
        assert RuntimeManager._pending_cleanup() is container
        service.shutdown.assert_not_awaited()
        await RuntimeManager.shutdown()
        service.shutdown.assert_awaited_once_with()
        assert RuntimeManager._pending_cleanup() is None
    finally:
        loop.set_task_factory(previous_factory)
        try:
            if lease in RuntimeManager._lifespan_tokens:
                await RuntimeManager.release_lifespan(lease)
            if RuntimeManager._pending_cleanup() is not None:
                await RuntimeManager.shutdown()
        finally:
            await cleanup_runtime_manager_for_test()


def _reject_cleanup_task_creation(unscheduled):
    def reject_task_creation(loop_or_coroutine, coroutine=None, **kwargs):
        unscheduled.append(coroutine or loop_or_coroutine)
        message = (
            "task factory unavailable"
            if len(unscheduled) == 1
            else "direct task creation unavailable"
        )
        raise RuntimeError(message)

    return reject_task_creation


@pytest.mark.asyncio
async def test_release_retains_lease_when_both_cleanup_task_paths_fail__b102(
    monkeypatch,
):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
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
    loop = asyncio.get_running_loop()
    previous_factory = loop.get_task_factory()
    unscheduled = []
    lease = None
    reject_task_creation = _reject_cleanup_task_creation(unscheduled)

    try:
        lease, _ = await RuntimeManager.acquire_lifespan(Mock())
        loop.set_task_factory(reject_task_creation)
        with patch("agentmap.async_lifecycle.asyncio.Task", reject_task_creation):
            with pytest.raises(RuntimeError, match="task factory unavailable"):
                await RuntimeManager.release_lifespan(lease)
        assert len(unscheduled) == 2
        assert all(coroutine.cr_frame is None for coroutine in unscheduled)
        assert lease in RuntimeManager._lifespan_tokens
        assert RuntimeManager._current_container() is container
        assert RuntimeManager._pending_cleanup() is None
        service.shutdown.assert_not_awaited()

        loop.set_task_factory(previous_factory)
        await RuntimeManager.release_lifespan(lease)
        assert lease not in RuntimeManager._lifespan_tokens
        service.shutdown.assert_awaited_once_with()
    finally:
        loop.set_task_factory(previous_factory)
        if lease in RuntimeManager._lifespan_tokens:
            await RuntimeManager.release_lifespan(lease)
        if RuntimeManager._pending_cleanup() is not None:
            await RuntimeManager.shutdown()
        await cleanup_runtime_manager_for_test()


async def _cancel_shared_release_task_waiting_for_transaction(lease, loop, owner_token):
    fallback_entered = asyncio.Event()
    release_transaction = RuntimeManager._release_lifespan_transaction

    async def observed_release_transaction(cls, current_lease):
        fallback_entered.set()
        await release_transaction(current_lease)

    async def invoke_release():
        await RuntimeManager.release_lifespan(lease)

    release_task = asyncio.create_task(invoke_release())
    previous_factory = loop.get_task_factory()

    def reject_task(loop, coroutine, context=None):
        raise RuntimeError("task factory unavailable")

    try:
        with patch.object(
            RuntimeManager,
            "_release_lifespan_transaction",
            classmethod(observed_release_transaction),
        ):
            loop.set_task_factory(reject_task)
            async with asyncio.timeout(5):
                await fallback_entered.wait()
            release_task.cancel()
            RuntimeManager._release_transaction(owner_token)
            with pytest.raises(asyncio.CancelledError) as caught:
                await asyncio.wait_for(release_task, timeout=5)
            return caught.value
    finally:
        loop.set_task_factory(previous_factory)
        if RuntimeManager._transaction_owner is owner_token:
            RuntimeManager._release_transaction(owner_token)
        if not release_task.done():
            release_task.cancel()
        await asyncio.gather(release_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_shared_release_task_finishes_after_cancellation_waiting_for_transaction(
    monkeypatch,
):
    service = SimpleNamespace(
        retire=Mock(), prepare_shutdown=Mock(), shutdown=AsyncMock()
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
    lease, _ = await RuntimeManager.acquire_lifespan(Mock())
    loop = asyncio.get_running_loop()
    owner_token = RuntimeManager._acquire_sync_transaction()
    try:
        caught = await _cancel_shared_release_task_waiting_for_transaction(
            lease, loop, owner_token
        )
        assert caught.__notes__ == [
            "HTTP lifespan release scheduling failed with RuntimeError",
            "HTTP lifespan release cleanup failed with RuntimeError",
        ]
        assert lease not in RuntimeManager._lifespan_tokens
        assert RuntimeManager._pending_cleanup() is container
        service.shutdown.assert_not_awaited()
    finally:
        if RuntimeManager._transaction_owner is owner_token:
            RuntimeManager._release_transaction(owner_token)
        if lease in RuntimeManager._lifespan_tokens:
            await RuntimeManager.release_lifespan(lease)
        if RuntimeManager._pending_cleanup() is not None:
            await RuntimeManager.shutdown()
        await cleanup_runtime_manager_for_test()
