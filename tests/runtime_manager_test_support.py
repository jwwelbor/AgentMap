"""Test-owned runtime cleanup helpers."""

import asyncio
from threading import Event
from unittest.mock import AsyncMock, Mock

from agentmap.runtime.runtime_manager import RuntimeManager


def assert_owned_runtime_container(container, owned_containers) -> None:
    if container is not None and not any(
        container is owned for owned in owned_containers
    ):
        raise AssertionError("Test fixture cannot clear a runtime it did not create")


def _assert_no_foreign_runtime_lifecycle() -> None:
    if (
        RuntimeManager._lifespan_tokens
        or RuntimeManager._lifespan_owned
        or RuntimeManager._lifespan_container is not None
        or RuntimeManager._lifespan_loop is not None
    ):
        raise AssertionError("Test fixture cannot clear unowned lifespan state")
    if RuntimeManager._pending_cleanup_loop is not None:
        raise AssertionError("Test fixture cannot clear an unowned cleanup loop")


def _validate_owned_runtime_test_state(owned_containers, installed_by_test):
    if RuntimeManager._pending_cleanup_container is not None:
        raise AssertionError("Test fixture cannot discard pending runtime cleanup")
    container = RuntimeManager._container
    initializing = RuntimeManager._initializing_container
    assert_owned_runtime_container(container, owned_containers)
    assert_owned_runtime_container(initializing, owned_containers)
    if initializing is not None:
        raise AssertionError("Test fixture cannot clear an active startup candidate")
    _assert_no_foreign_runtime_lifecycle()
    if container is None and RuntimeManager._is_initialized and not installed_by_test:
        raise AssertionError("Test fixture cannot clear unowned initialization state")
    return container


def cleanup_owned_runtime_test_state(owned_containers, installed_by_test) -> None:
    """Release only this test module's runtime and reject foreign lifecycle owners."""
    with RuntimeManager._lock:
        container = _validate_owned_runtime_test_state(
            owned_containers, installed_by_test
        )

    if container is not None:
        service = container.llm_service()
        if isinstance(service, Mock) and not isinstance(service.shutdown, AsyncMock):
            service.shutdown = AsyncMock()
        cleanup_runtime_manager_sync_for_test()
    else:
        RuntimeManager.reset()


async def cancel_tasks_for_test(*tasks) -> None:
    """Cancel and reap any tasks started by a test, including optional tasks."""
    active = [task for task in tasks if task is not None]
    for task in active:
        if not task.done():
            task.cancel()
    await asyncio.gather(*active, return_exceptions=True)


async def release_reap_and_cleanup_runtime_for_test(release: Event, *tasks) -> None:
    """Release blocked workers, reap their tasks, and clean shared runtime state."""
    release.set()
    await cancel_tasks_for_test(*tasks)
    await cleanup_runtime_manager_for_test()


async def cleanup_runtime_manager_for_test() -> None:
    """Release test lifespans and await shutdown before resetting manager state."""
    for lease in tuple(RuntimeManager._lifespan_tokens):
        await RuntimeManager.release_lifespan(lease)
    if (
        RuntimeManager._pending_cleanup() is not None
        or RuntimeManager._container is not None
        or RuntimeManager._initializing_container is not None
    ):
        await RuntimeManager.shutdown()
    RuntimeManager.reset()


def cleanup_runtime_manager_sync_for_test() -> None:
    """Shut down an owned runtime from a synchronous integration fixture."""
    if (
        RuntimeManager._pending_cleanup() is not None
        or RuntimeManager._container is not None
        or RuntimeManager._initializing_container is not None
        or RuntimeManager._lifespan_tokens
    ):
        asyncio.run(cleanup_runtime_manager_for_test())
    else:
        RuntimeManager.reset()
