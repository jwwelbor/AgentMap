"""B102 runtime replacement awaits its old LLM resource owner."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from agentmap.runtime.runtime_manager import RuntimeManager


def test_refresh_awaits_old_container_llm_shutdown__b102(monkeypatch):
    service = SimpleNamespace(shutdown=AsyncMock())
    old = SimpleNamespace(llm_service=Mock(return_value=service))
    new = object()
    RuntimeManager._container = old
    RuntimeManager._is_initialized = True
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=new)
    )
    try:
        RuntimeManager.initialize(refresh=True)
        service.shutdown.assert_awaited_once_with()
        assert RuntimeManager.get_container() is new
    finally:
        RuntimeManager.reset()
