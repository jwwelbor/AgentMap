"""Keep startup errors primary when synchronous rollback also fails."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.runtime.init_ops import ensure_initialized
from agentmap.runtime.runtime_manager import RuntimeManager
from tests.runtime_manager_test_support import cleanup_runtime_manager_sync_for_test


class StartupControlFlowFailure(BaseException):
    pass


def test_sync_startup_failure_keeps_primary_error_when_rollback_fails__b102(
    monkeypatch,
):
    startup_error = StartupControlFlowFailure("cache validation stopped")
    cleanup_error = RuntimeError("offline rollback failure")
    service = SimpleNamespace(
        retire=Mock(),
        prepare_shutdown=Mock(),
        shutdown=AsyncMock(side_effect=[cleanup_error, None]),
    )
    candidate = SimpleNamespace(
        config=SimpleNamespace(path=Mock(return_value=None)),
        llm_service=Mock(return_value=service),
    )
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di",
        Mock(return_value=candidate),
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._validate_cache",
        Mock(side_effect=startup_error),
    )
    cleanup_runtime_manager_sync_for_test()
    try:
        with pytest.raises(StartupControlFlowFailure) as caught:
            ensure_initialized()

        assert caught.value is startup_error
        assert any(
            "Runtime startup rollback also failed with RuntimeError" in note
            for note in caught.value.__notes__
        )
        assert RuntimeManager._current_container() is None
        assert RuntimeManager._pending_cleanup() is candidate
        service.shutdown.assert_awaited_once_with()

        asyncio.run(RuntimeManager.shutdown())
        assert RuntimeManager._pending_cleanup() is None
        assert service.shutdown.await_count == 2
    finally:
        cleanup_runtime_manager_sync_for_test()
