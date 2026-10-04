"""B102 public sync facades cannot starve async runtime startup."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.runtime.init_ops import ensure_initialized_async
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.runtime.workflow_ops import (
    inspect_graph_async,
    list_graphs_async,
    validate_workflow_async,
)


class ActiveExecutor(ThreadPoolExecutor):
    """Expose when every bounded worker has entered a submitted facade."""

    def __init__(self, max_workers):
        super().__init__(max_workers=max_workers)
        self._max_workers_for_test = max_workers
        self._active = 0
        self._active_lock = Lock()
        self.all_workers_active = Event()

    def submit(self, fn, /, *args, **kwargs):
        def tracked():
            with self._active_lock:
                self._active += 1
                if self._active == self._max_workers_for_test:
                    self.all_workers_active.set()
            try:
                return fn(*args, **kwargs)
            finally:
                with self._active_lock:
                    self._active -= 1

        return super().submit(tracked)


def runtime_container(tmp_path: Path):
    """Build the minimum real-facade service surface for offline execution."""
    bundle = SimpleNamespace(
        csv_hash="offline",
        edges=[],
        entry_point=None,
        graph_name="graph",
        missing_declarations=[],
        nodes={},
        required_agents=[],
        required_services=[],
    )
    app_config = SimpleNamespace(get_csv_repository_path=Mock(return_value=tmp_path))
    logging_service = SimpleNamespace(get_logger=Mock(return_value=Mock()))
    graph_bundle = SimpleNamespace(
        get_or_create_bundle=Mock(return_value=(bundle, True))
    )
    return SimpleNamespace(
        app_config_service=Mock(return_value=app_config),
        graph_bundle_service=Mock(return_value=graph_bundle),
        llm_service=Mock(return_value=SimpleNamespace(shutdown=AsyncMock())),
        logging_service=Mock(return_value=logging_service),
        ready=False,
        validation_service=Mock(
            return_value=SimpleNamespace(validate_csv_for_bundling=Mock())
        ),
    )


def install_owner_gate(monkeypatch):
    """Pause after transaction ownership but before lifecycle dispatch."""
    acquired, release = asyncio.Event(), asyncio.Event()
    original = RuntimeManager._run_initialization_transaction

    async def gated(cls, startup, *, refresh: bool, config_file: str | None):
        acquired.set()
        await release.wait()
        await original(startup, refresh=refresh, config_file=config_file)

    monkeypatch.setattr(
        RuntimeManager, "_run_initialization_transaction", classmethod(gated)
    )
    return acquired, release


def configure_runtime(monkeypatch, installed) -> None:
    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", Mock(return_value=installed)
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", lambda value: value.ready
    )
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._refresh_cache",
        lambda value: setattr(value, "ready", True),
    )


def facade_call(name: str, graph_file: Path):
    if name == "list":
        return list_graphs_async()
    if name == "inspect":
        return inspect_graph_async("graph", csv_file=str(graph_file))
    return validate_workflow_async("workflow::graph")


async def wait_for_thread_event(event: Event) -> None:
    """Wait without consuming the bounded executor under test."""
    for _ in range(1000):
        if event.is_set():
            return
        await asyncio.sleep(0.001)
    raise AssertionError("bounded executor workers did not enter facade calls")


async def complete_tasks_or_break_counterfactual(tasks) -> bool:
    """Return starvation state after safely releasing a pre-fix deadlock."""
    _, pending = await asyncio.wait(tasks, timeout=1)
    starved = bool(pending)
    if starved:
        with RuntimeManager._transaction_condition:
            token = RuntimeManager._transaction_owner
        if token is not None:
            RuntimeManager._release_transaction(token)
        await asyncio.gather(*tasks, return_exceptions=True)
    return starved


@pytest.mark.parametrize("workers", [1, 2])
@pytest.mark.parametrize("facade_name", ["list", "inspect", "validate"])
@pytest.mark.asyncio
async def test_public_sync_facades_cannot_starve_async_transaction_owner__b102(
    monkeypatch, tmp_path: Path, workers: int, facade_name: str
):
    """Every to_thread facade terminates while an async transaction owns startup."""
    executor = ActiveExecutor(max_workers=workers)
    asyncio.get_running_loop().set_default_executor(executor)
    acquired, release = install_owner_gate(monkeypatch)
    installed = runtime_container(tmp_path)
    configure_runtime(monkeypatch, installed)
    graph_file = tmp_path / "workflow.csv"
    graph_file.write_text("GraphName,Agent\ngraph,offline\n")

    RuntimeManager.reset()
    owner = asyncio.create_task(ensure_initialized_async())
    await acquired.wait()
    calls = [
        asyncio.create_task(facade_call(facade_name, graph_file))
        for _ in range(workers)
    ]
    await wait_for_thread_event(executor.all_workers_active)
    release.set()
    starved = await complete_tasks_or_break_counterfactual([owner, *calls])

    try:
        assert not starved, f"{facade_name} starved owner with {workers} workers"
        assert owner.result() is None
        assert all(call.result()["success"] for call in calls)
        assert RuntimeManager.is_initialized()
    finally:
        if RuntimeManager.is_initialized():
            await RuntimeManager.shutdown()
