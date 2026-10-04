"""B102 admin endpoints use nonblocking runtime initialization."""

import asyncio
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI

from agentmap.deployment.http.api.routes import admin
from agentmap.runtime.init_ops import ensure_initialized_async
from agentmap.runtime.runtime_manager import RuntimeManager


@pytest.mark.asyncio
async def test_every_async_admin_initializer_awaits_async_facade__b102(monkeypatch):
    initialize = AsyncMock()
    legacy_sync = Mock()
    monkeypatch.setattr(admin, "ensure_initialized_async", initialize, raising=False)
    monkeypatch.setattr(admin, "ensure_initialized", legacy_sync, raising=False)
    monkeypatch.setattr(
        admin,
        "diagnose_system",
        Mock(return_value={"success": True, "outputs": {}, "metadata": {}}),
    )
    monkeypatch.setattr(
        admin,
        "get_config",
        Mock(
            return_value={
                "success": True,
                "outputs": {
                    "csv_repository_path": "",
                    "custom_agents_path": "",
                    "functions_path": "",
                },
            }
        ),
    )
    monkeypatch.setattr(
        admin,
        "validate_cache",
        Mock(
            return_value={
                "success": True,
                "outputs": {"cache_stats": {}, "removed_entries": 0},
            }
        ),
    )
    request = Mock()
    calls = [
        lambda: admin.get_diagnostics.__wrapped__(request),
        lambda: admin.get_configuration.__wrapped__(request),
        lambda: admin.get_cache_stats.__wrapped__(request),
        lambda: admin.clear_cache.__wrapped__(request=request),
        admin.health_check,
        lambda: admin.get_system_paths.__wrapped__(request),
    ]
    for call in calls:
        initialize.reset_mock()
        await call()
        initialize.assert_awaited_once_with()
    legacy_sync.assert_not_called()


@pytest.mark.asyncio
async def test_admin_health_waits_without_blocking_transaction_owner__b102(monkeypatch):
    loop = asyncio.get_running_loop()
    entered, release = asyncio.Event(), Event()
    service = SimpleNamespace(shutdown=AsyncMock())
    installed = SimpleNamespace(
        ready=False,
        llm_service=Mock(return_value=service),
    )
    RuntimeManager.reset()
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=installed)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", lambda value: value.ready
    )

    def refresh(value):
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        value.ready = True

    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", refresh)
    owner = asyncio.create_task(ensure_initialized_async())
    await entered.wait()
    app = FastAPI()
    app.include_router(admin.router)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = asyncio.create_task(client.get("/admin/health"))
        marker = asyncio.Event()
        loop.call_soon(marker.set)
        await marker.wait()
        with RuntimeManager._transaction_condition:
            assert len(RuntimeManager._transaction_async_waiters) == 1
        release.set()
        await owner
        response = await health
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "initialized": True}
    await RuntimeManager.shutdown()
