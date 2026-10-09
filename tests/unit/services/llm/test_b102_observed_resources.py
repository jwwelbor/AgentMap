"""B102 observed resource cleanup preserves retry and terminal ownership."""

import asyncio
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from agentmap.exceptions import LLMLifecycleCleanupError
from agentmap.services.llm.observed_clients import ObservedResources


@pytest.mark.skipif(
    not hasattr(asyncio, "eager_task_factory"),
    reason="eager task factories require Python 3.12",
)
def test_observed_cleanup_yields_before_reacquiring_lock__b102():
    """A separate watchdog can stop an eager-task deadlock without hanging pytest."""
    script = textwrap.dedent("""
        import asyncio
        from agentmap.services.llm.observed_clients import ObservedResources

        class Resource:
            def __init__(self):
                self.closed = 0

            async def aclose(self):
                self.closed += 1

        async def main():
            owner = ObservedResources()
            resource = Resource()
            owner.create_async(lambda: resource)
            loop = asyncio.get_running_loop()
            loop.set_task_factory(asyncio.eager_task_factory)
            try:
                await owner.aclose()
            finally:
                loop.set_task_factory(None)
            assert resource.closed == 1
            assert owner._state == "closed"

        asyncio.run(main())
        """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[4],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_index", [0, 1, 2])
async def test_failed_close_retains_only_retryable_obligation__b102(failed_index):
    class Resource:
        def __init__(self, fail_once):
            self.fail_once = fail_once
            self.calls = 0

        def close(self):
            self.calls += 1
            if self.fail_once and self.calls == 1:
                raise RuntimeError("offline close failure")

    owner = ObservedResources()
    resources = [Resource(index == failed_index) for index in range(3)]
    for resource in resources:
        owner.create_sync(lambda resource=resource: resource, retry_safe_close=True)

    with pytest.raises(LLMLifecycleCleanupError) as first:
        await owner.aclose()
    assert first.value.stage == "resource_close"
    assert first.value.failure_count == 1
    assert owner.sync == [resources[failed_index]]
    assert owner._state == "cleanup_failed"
    assert [resource.calls for resource in resources] == [1, 1, 1]

    await owner.aclose()
    assert owner._state == "closed"
    assert owner.sync == []
    assert [resource.calls for resource in resources] == [
        2 if index == failed_index else 1 for index in range(3)
    ]


@pytest.mark.asyncio
async def test_nonretryable_close_failure_stays_terminal_and_owned__b102():
    class Resource:
        calls = 0

        def close(self):
            self.calls += 1
            raise RuntimeError("offline terminal close failure")

    owner = ObservedResources()
    resource = Resource()
    owner.create_sync(lambda: resource)
    with pytest.raises(LLMLifecycleCleanupError) as first:
        await owner.aclose()
    with pytest.raises(LLMLifecycleCleanupError) as second:
        await owner.aclose()

    assert second.value is first.value
    assert resource.calls == 1
    assert owner.sync == [resource]
    assert owner._state == "cleanup_failed"


@pytest.mark.asyncio
async def test_cleanup_continues_after_resource_cancellation__b102():
    owner = ObservedResources()
    closed: list[str] = []

    class Cancelled:
        async def aclose(self):
            raise asyncio.CancelledError()

    class Later:
        async def aclose(self):
            closed.append("later")

    owner.create_async(Cancelled)
    owner.create_async(Later)
    with pytest.raises(LLMLifecycleCleanupError) as first:
        await owner.aclose()
    assert closed == ["later"]
    with pytest.raises(LLMLifecycleCleanupError) as second:
        await owner.aclose()
    assert second.value is first.value
    assert closed == ["later"]
