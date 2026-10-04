"""B102 public sync facades cannot starve async runtime startup."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from pathlib import Path
from threading import Lock
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

    def __init__(self, loop, max_workers):
        super().__init__(max_workers=max_workers)
        self._loop = loop
        self._max_workers_for_test = max_workers
        self._active = 0
        self._active_lock = Lock()
        self.all_workers_active = asyncio.Event()

    def submit(self, fn, /, *args, **kwargs):
        def tracked():
            with self._active_lock:
                self._active += 1
                if self._active == self._max_workers_for_test:
                    self._loop.call_soon_threadsafe(self.all_workers_active.set)
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


@pytest.mark.asyncio
async def test_lifecycle_executor_preserves_calling_task_context__b102(
    monkeypatch, tmp_path: Path
):
    """DI installation and cache startup see the calling task's exact context."""
    lifecycle_context = ContextVar("b102_lifecycle_context")
    sentinel = object()
    observed = {}
    installed = runtime_container(tmp_path)

    def initialize_di(config_file):
        observed["initialize"] = lifecycle_context.get()
        return installed

    def is_cache_initialized(value):
        observed.setdefault("startup", lifecycle_context.get())
        return value.ready

    def refresh_cache(value):
        observed["cache"] = lifecycle_context.get()
        value.ready = True

    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", initialize_di)
    monkeypatch.setattr(
        "agentmap.runtime.init_ops._is_cache_initialized", is_cache_initialized
    )
    monkeypatch.setattr("agentmap.runtime.init_ops._refresh_cache", refresh_cache)

    RuntimeManager.reset()
    token = lifecycle_context.set(sentinel)
    try:
        await ensure_initialized_async()
        assert observed == {
            "initialize": sentinel,
            "startup": sentinel,
            "cache": sentinel,
        }
    finally:
        lifecycle_context.reset(token)
        if RuntimeManager.is_initialized():
            await RuntimeManager.shutdown()


def facade_call(name: str, graph_file: Path):
    if name == "list":
        return list_graphs_async()
    if name == "inspect":
        return inspect_graph_async("graph", csv_file=str(graph_file))
    return validate_workflow_async("workflow::graph")


async def complete_before_deadlock_guard(completion, tasks) -> None:
    """Use one generous outer timeout and unblock the pre-fix counterfactual."""
    try:
        await asyncio.wait_for(asyncio.shield(completion), timeout=10)
    except TimeoutError:
        with RuntimeManager._transaction_condition:
            token = RuntimeManager._transaction_owner
        if token is not None:
            RuntimeManager._release_transaction(token)
        await asyncio.gather(*tasks, return_exceptions=True)
        raise AssertionError("public facades starved the runtime lifecycle") from None


@pytest.mark.parametrize("workers", [1, 2])
@pytest.mark.parametrize("facade_name", ["list", "inspect", "validate"])
@pytest.mark.asyncio
async def test_public_sync_facades_cannot_starve_async_transaction_owner__b102(
    monkeypatch, tmp_path: Path, workers: int, facade_name: str
):
    """Every to_thread facade terminates while an async transaction owns startup."""
    loop = asyncio.get_running_loop()
    executor = ActiveExecutor(loop, max_workers=workers)
    loop.set_default_executor(executor)
    acquired, release = install_owner_gate(monkeypatch)
    installed = runtime_container(tmp_path)
    lifecycle_started = asyncio.Event()
    configure_runtime(monkeypatch, installed)

    def observed_initialize_di(config_file):
        loop.call_soon_threadsafe(lifecycle_started.set)
        return installed

    monkeypatch.setattr(
        "agentmap.runtime.runtime_manager.initialize_di", observed_initialize_di
    )
    graph_file = tmp_path / "workflow.csv"
    graph_file.write_text("GraphName,Agent\ngraph,offline\n")

    RuntimeManager.reset()
    owner = asyncio.create_task(ensure_initialized_async())
    await acquired.wait()
    calls = [
        asyncio.create_task(facade_call(facade_name, graph_file))
        for _ in range(workers)
    ]

    async def exercise_ordered_startup():
        await executor.all_workers_active.wait()
        assert acquired.is_set()
        assert not lifecycle_started.is_set()
        release.set()
        await lifecycle_started.wait()
        await asyncio.gather(owner, *calls)

    completion = asyncio.create_task(exercise_ordered_startup())
    try:
        await complete_before_deadlock_guard(completion, [owner, *calls])
        assert owner.result() is None
        assert all(call.result()["success"] for call in calls)
        assert RuntimeManager.is_initialized()
    finally:
        if RuntimeManager.is_initialized():
            await RuntimeManager.shutdown()
