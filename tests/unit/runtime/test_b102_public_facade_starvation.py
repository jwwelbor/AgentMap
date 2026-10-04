"""B102 public sync facades cannot starve async runtime startup."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from pathlib import Path
from threading import Lock, get_ident
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agentmap.async_lifecycle import await_terminal_task
from agentmap.runtime.init_ops import ensure_initialized_async
from agentmap.runtime.runtime_manager import RuntimeManager
from agentmap.runtime.workflow_ops import (
    inspect_graph_async,
    list_graphs_async,
    validate_workflow_async,
)

GUARD_SECONDS = 10


class LifecycleProbeAbort(BaseException):
    """Exercise cleanup for failures outside the ``Exception`` hierarchy."""


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
    graphs = SimpleNamespace(get_or_create_bundle=Mock(return_value=(bundle, True)))
    return SimpleNamespace(
        app_config_service=Mock(return_value=app_config),
        graph_bundle_service=Mock(return_value=graphs),
        llm_service=Mock(return_value=SimpleNamespace(shutdown=AsyncMock())),
        logging_service=Mock(return_value=logging_service),
        ready=False,
        validation_service=Mock(
            return_value=SimpleNamespace(validate_csv_for_bundling=Mock())
        ),
    )


def install_owner_gate(monkeypatch):
    """Pause after transaction ownership but before lifecycle dispatch."""
    acquired = asyncio.Event()
    release = asyncio.Event()
    skip_lifecycle = asyncio.Event()
    original = RuntimeManager._run_initialization_transaction

    async def gated(cls, startup, *, refresh: bool, config_file: str | None):
        acquired.set()
        await release.wait()
        if skip_lifecycle.is_set():
            return
        await original(startup, refresh=refresh, config_file=config_file)

    monkeypatch.setattr(
        RuntimeManager, "_run_initialization_transaction", classmethod(gated)
    )
    return acquired, release, skip_lifecycle


def configure_runtime(monkeypatch, installed, initialize=None) -> None:
    initialize = initialize or Mock(return_value=installed)
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", initialize)
    module = "agentmap.runtime.init_ops"
    monkeypatch.setattr(f"{module}._is_cache_initialized", lambda value: value.ready)
    monkeypatch.setattr(
        f"{module}._refresh_cache", lambda value: setattr(value, "ready", True)
    )


@pytest.mark.asyncio
async def test_lifecycle_executor_preserves_calling_task_context__b102(
    monkeypatch, tmp_path: Path
):
    """DI installation and cache startup see the calling task's exact context."""
    lifecycle_context = ContextVar("b102_lifecycle_context")
    sentinel = object()
    observed = {}
    event_loop_thread = get_ident()
    installed = runtime_container(tmp_path)

    def initialize_di(config_file):
        observed["initialize"] = (lifecycle_context.get(), get_ident())
        return installed

    def is_cache_initialized(value):
        observed.setdefault("startup", (lifecycle_context.get(), get_ident()))
        return value.ready

    def refresh_cache(value):
        observed["cache"] = (lifecycle_context.get(), get_ident())
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
        assert set(observed) == {"initialize", "startup", "cache"}
        assert all(value is sentinel for value, _ in observed.values())
        assert all(
            callback_thread != event_loop_thread
            for _, callback_thread in observed.values()
        )
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


async def reap_tasks(tasks):
    async def reap():
        return await asyncio.gather(*tasks, return_exceptions=True)

    outcome = await await_terminal_task(asyncio.create_task(reap()))
    assert outcome.task_error is None
    return outcome.value, outcome.caller_cancellation


async def guard_completion(
    task, release, tasks, *, timeout=GUARD_SECONDS, entered=None, on_timeout=None
) -> None:
    """Bound completion, then release and reap every deliberately gated task."""
    primary = None
    timed_out = False
    try:
        if entered is not None:
            entered.set()
        done, _ = await asyncio.wait([task], timeout=timeout)
        if not done:
            primary = AssertionError("public facades starved the runtime lifecycle")
            timed_out = True
        else:
            task.result()
    except BaseException as error:
        primary = error
    finally:
        if timed_out and on_timeout is not None:
            on_timeout()
        release.set()
        outcomes, cancellation = await reap_tasks([task, *tasks])
        if primary is None:
            primary = cancellation
    failures = [
        outcome
        for outcome in outcomes
        if isinstance(outcome, BaseException) and outcome is not primary
    ]
    if failures:
        secondary = BaseExceptionGroup("deadlock guard cleanup failed", failures)
        if primary is not None:
            raise primary from secondary
        raise secondary
    if primary is not None:
        raise primary


@pytest.mark.parametrize(
    "primary",
    [AssertionError("assertion"), RuntimeError("error"), LifecycleProbeAbort("base")],
)
@pytest.mark.asyncio
async def test_early_lifecycle_failure_releases_and_reaps_gated_tasks__b102(primary):
    """An early lifecycle signal stays primary after all gated tasks terminate."""
    release = asyncio.Event()
    lifecycle_started = asyncio.Event()
    completed = []

    async def gated(label):
        await release.wait()
        completed.append(label)

    owner = asyncio.create_task(gated("owner"))
    facades = [asyncio.create_task(gated(f"facade-{index}")) for index in range(2)]

    async def fail_after_early_start():
        lifecycle_started.set()
        raise primary

    completion = asyncio.create_task(fail_after_early_start())
    try:
        await lifecycle_started.wait()
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
    """Cancellation and timeout stay primary after every gated task terminates."""
    release, timeout_cleanup, entered = (asyncio.Event() for _ in range(3))
    completed = []

    async def gated(label):
        await release.wait()
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
        await entered.wait()
        if route == "cancellation":
            guard.cancel("offline caller cancellation")
        done, _ = await asyncio.wait([guard], timeout=1)
        assert done == {guard}
        with pytest.raises(expected) as caught:
            guard.result()
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
    assert cleanup_cancellation is None
    assert cleanup_outcomes[:3] == [None, None, None]
    assert isinstance(cleanup_outcomes[3], expected)


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
    acquired, release, skip_lifecycle = install_owner_gate(monkeypatch)
    installed = runtime_container(tmp_path)
    lifecycle_started = asyncio.Event()

    def observed_initialize_di(config_file):
        loop.call_soon_threadsafe(lifecycle_started.set)
        return installed

    configure_runtime(monkeypatch, installed, observed_initialize_di)
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
        await guard_completion(
            completion,
            release,
            [owner, *calls],
            on_timeout=skip_lifecycle.set,
        )
        assert owner.result() is None
        assert all(call.result()["success"] for call in calls)
        assert RuntimeManager.is_initialized()
    finally:
        if RuntimeManager.is_initialized():
            await RuntimeManager.shutdown()
