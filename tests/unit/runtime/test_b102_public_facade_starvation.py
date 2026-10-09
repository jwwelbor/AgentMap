import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from pathlib import Path
from threading import Event, Lock, get_ident
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
from tests.runtime_manager_test_support import cleanup_runtime_manager_for_test
from tests.unit.runtime.test_b102_public_facade_reaping import (
    guard_completion,
    reap_tasks,
)

GUARD_SECONDS, TEST_TIMEOUT_SECONDS = 10, 1
TIMEOUT_MESSAGE = "public facades starved the runtime lifecycle"


class ActiveExecutor(ThreadPoolExecutor):
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
    validation = SimpleNamespace(validate_csv_for_bundling=Mock())
    return SimpleNamespace(
        app_config_service=Mock(return_value=app_config),
        graph_bundle_service=Mock(return_value=graphs),
        llm_service=Mock(return_value=Mock(shutdown=AsyncMock())),
        logging_service=Mock(return_value=logging_service),
        ready=False,
        validation_service=Mock(return_value=validation),
    )


def install_owner_gate(patch, *, ack=True):
    entered, acquired, release, skip_lifecycle = (asyncio.Event() for _ in range(4))
    original = RuntimeManager._run_initialization_transaction

    async def gated(cls, startup, *, refresh: bool, config_file: str | None):
        entered.set()
        if ack:
            acquired.set()
        await asyncio.wait_for(release.wait(), timeout=10)
        if skip_lifecycle.is_set():
            return
        await original(startup, refresh=refresh, config_file=config_file)

    patch.setattr(RuntimeManager, "_run_initialization_transaction", classmethod(gated))
    return entered, acquired, release, skip_lifecycle


def configure_runtime(monkeypatch, initialize) -> None:
    monkeypatch.setattr("agentmap.runtime.runtime_manager.initialize_di", initialize)
    ops = "agentmap.runtime.init_ops"
    monkeypatch.setattr(f"{ops}._is_cache_initialized", lambda v: v.ready)
    monkeypatch.setattr(f"{ops}._refresh_cache", lambda v: setattr(v, "ready", True))


@pytest.mark.asyncio
async def test_lifecycle_executor_preserves_calling_task_context__b102(
    monkeypatch, tmp_path: Path
):
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
    module = "agentmap.runtime.init_ops"
    monkeypatch.setattr(f"{module}._is_cache_initialized", is_cache_initialized)
    monkeypatch.setattr(f"{module}._refresh_cache", refresh_cache)

    await cleanup_runtime_manager_for_test()
    token = lifecycle_context.set(sentinel)
    try:
        await ensure_initialized_async()
        assert set(observed) == {"initialize", "startup", "cache"}
        assert all(value is sentinel for value, _ in observed.values())
        assert all(thread != event_loop_thread for _, thread in observed.values())
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


@pytest.mark.parametrize("ack", [True, False], ids=["guard", "acquisition-timeout"])
@pytest.mark.asyncio
async def test_live_owner_timeout_cleanup__b102(monkeypatch, ack):
    entered, acquired, release, skip = install_owner_gate(monkeypatch, ack=ack)
    await cleanup_runtime_manager_for_test()
    owner = asyncio.create_task(ensure_initialized_async())
    try:
        await asyncio.wait_for(entered.wait(), timeout=TEST_TIMEOUT_SECONDS)
        assert RuntimeManager._transaction_owner is not None
        if ack:
            await asyncio.wait_for(acquired.wait(), timeout=TEST_TIMEOUT_SECONDS)
            with pytest.raises(AssertionError, match=f"^{TIMEOUT_MESSAGE}$") as caught:
                await guard_completion(
                    owner, release, [], timeout=0.01, on_timeout=skip.set
                )
            assert caught.value.__cause__ is None and owner.result() is None
        else:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(acquired.wait(), timeout=TEST_TIMEOUT_SECONDS)
    finally:
        skip.set()
        release.set()
        owner.cancel()
        await reap_tasks([owner])
    with RuntimeManager._transaction_condition:
        assert owner.done() and RuntimeManager._transaction_owner is None


def configure_public_facade_scenario(monkeypatch, tmp_path, workers):
    loop = asyncio.get_running_loop()
    executor = ActiveExecutor(loop, max_workers=workers)
    loop.set_default_executor(executor)
    _, acquired, release, skip_lifecycle = install_owner_gate(monkeypatch)
    installed = runtime_container(tmp_path)
    lifecycle_started = asyncio.Event()
    cleanup_started = asyncio.Event()
    startup_or_cleanup = asyncio.Event()
    abort_sync_waiters = Event()
    original_condition_wait = RuntimeManager._transaction_condition.wait

    def bounded_condition_wait(timeout=None):
        wait_result = original_condition_wait(
            0.05 if timeout is None else min(timeout, 0.05)
        )
        if abort_sync_waiters.is_set():
            raise RuntimeError("starvation test cleanup released a facade waiter")
        return wait_result

    monkeypatch.setattr(
        RuntimeManager._transaction_condition, "wait", bounded_condition_wait
    )

    def observed_initialize_di(config_file):
        loop.call_soon_threadsafe(lifecycle_started.set)
        loop.call_soon_threadsafe(startup_or_cleanup.set)
        return installed

    configure_runtime(monkeypatch, observed_initialize_di)
    graph_file = tmp_path / "workflow.csv"
    graph_file.write_text("GraphName,Agent\ngraph,offline\n")
    return SimpleNamespace(
        abort_sync_waiters=abort_sync_waiters,
        acquired=acquired,
        cleanup_started=cleanup_started,
        executor=executor,
        graph_file=graph_file,
        lifecycle_started=lifecycle_started,
        release=release,
        skip_lifecycle=skip_lifecycle,
        startup_or_cleanup=startup_or_cleanup,
    )


async def cleanup_public_facade_scenario(state, owner, calls, completion):
    state.abort_sync_waiters.set()
    state.cleanup_started.set()
    state.startup_or_cleanup.set()
    state.skip_lifecycle.set()
    state.release.set()
    cleanup_tasks = [owner, *calls]
    if completion is not None:
        cleanup_tasks.append(completion)
    if not owner.done():
        owner.cancel()
    await reap_tasks(cleanup_tasks)
    await cleanup_runtime_manager_for_test()


async def run_public_facade_scenario(monkeypatch, tmp_path, workers, facade_name):
    state = configure_public_facade_scenario(monkeypatch, tmp_path, workers)

    await cleanup_runtime_manager_for_test()
    owner = asyncio.create_task(ensure_initialized_async())
    calls = []
    completion = None
    try:
        await asyncio.wait_for(state.acquired.wait(), timeout=TEST_TIMEOUT_SECONDS)
        facades = (facade_call(facade_name, state.graph_file) for _ in range(workers))
        calls = [asyncio.create_task(call) for call in facades]

        async def exercise_ordered_startup():
            await asyncio.wait_for(state.executor.all_workers_active.wait(), timeout=10)
            assert state.acquired.is_set()
            assert not state.lifecycle_started.is_set()
            state.release.set()
            await asyncio.wait_for(state.startup_or_cleanup.wait(), timeout=10)
            if state.cleanup_started.is_set():
                await owner
                return
            await asyncio.gather(owner, *calls)

        completion = asyncio.create_task(exercise_ordered_startup())

        def stop_waiting_facades():
            state.abort_sync_waiters.set()
            state.cleanup_started.set()
            state.startup_or_cleanup.set()

        await guard_completion(
            completion,
            state.release,
            [owner, *calls],
            on_timeout=state.skip_lifecycle.set,
            on_failure=stop_waiting_facades,
        )
        assert all(call.result()["success"] for call in calls)
        assert RuntimeManager.is_initialized()
    finally:
        await cleanup_public_facade_scenario(state, owner, calls, completion)


@pytest.mark.parametrize("workers", [1, 2])
@pytest.mark.parametrize("facade_name", ["list", "inspect", "validate"])
@pytest.mark.asyncio
async def test_public_sync_facades_cannot_starve_async_transaction_owner__b102(
    monkeypatch, tmp_path: Path, workers: int, facade_name: str
):
    await run_public_facade_scenario(monkeypatch, tmp_path, workers, facade_name)
