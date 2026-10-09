"""B102 cleanup ownership survives task-factory scheduling failures."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agentmap.runtime.runtime_manager import RuntimeManager
from tests.runtime_manager_test_support import cleanup_runtime_manager_for_test


@pytest.mark.asyncio
async def test_shutdown_scheduling_failure_retains_pending_owner_for_retry__b102():
    shutdown_calls = []

    async def shutdown():
        shutdown_calls.append("shutdown")

    service = SimpleNamespace(retire=Mock(), prepare_shutdown=Mock(), shutdown=shutdown)
    container = SimpleNamespace(llm_service=Mock(return_value=service))
    await cleanup_runtime_manager_for_test()
    loop = asyncio.get_running_loop()
    previous_factory = loop.get_task_factory()

    def reject_task(loop, coroutine, context=None):
        raise RuntimeError("task factory unavailable")

    try:
        RuntimeManager._adopt_pending_cleanup(container, owner_loop=loop)
        loop.set_task_factory(reject_task)
        with pytest.raises(RuntimeError, match="task factory unavailable"):
            await RuntimeManager.shutdown()
        assert RuntimeManager._pending_cleanup() is container
        assert shutdown_calls == []
        loop.set_task_factory(previous_factory)
        await RuntimeManager.shutdown()
        assert shutdown_calls == ["shutdown"]
        assert RuntimeManager._pending_cleanup() is None
    finally:
        loop.set_task_factory(previous_factory)
        await cleanup_runtime_manager_for_test()
        assert RuntimeManager._pending_cleanup() is None
