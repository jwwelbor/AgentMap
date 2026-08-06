"""Unit tests for agentmap.runtime.init_ops.

TD-049: ensure_initialized_async is the single canonical async wrapper for
the ``await asyncio.to_thread(ensure_initialized, ...)`` idiom that was
previously duplicated at 7 call sites across execute.py, workflows.py, and
workflow_ops.py. These tests cover the wrapper directly; callers only need
to prove they await it (see test_async_route_facade.py and
test_workflow_ops_async_facade.py).
"""

from unittest.mock import patch

import pytest


class TestEnsureInitializedAsyncOffload:
    """TD-018/TD-049: ensure_initialized_async must dispatch the blocking
    ensure_initialized() call through asyncio.to_thread, not call it inline
    on the event loop.
    """

    @pytest.mark.asyncio
    async def test_dispatches_via_asyncio_to_thread(self):
        from agentmap.runtime.init_ops import ensure_initialized_async

        calls = []

        async def spy_to_thread(func, *args, **kwargs):
            calls.append((func, args, kwargs))
            return func(*args, **kwargs)

        with (
            patch(
                "agentmap.runtime.init_ops.ensure_initialized"
            ) as mock_ensure_initialized,
            patch("agentmap.runtime.init_ops.asyncio.to_thread", spy_to_thread),
        ):
            await ensure_initialized_async(config_file="/configs/custom.yaml")

        assert len(calls) == 1
        func, _, kwargs = calls[0]
        assert func is mock_ensure_initialized
        assert kwargs == {"refresh": False, "config_file": "/configs/custom.yaml"}

    @pytest.mark.asyncio
    async def test_forwards_refresh_flag(self):
        from agentmap.runtime.init_ops import ensure_initialized_async

        with patch(
            "agentmap.runtime.init_ops.ensure_initialized"
        ) as mock_ensure_initialized:
            await ensure_initialized_async(refresh=True)

        mock_ensure_initialized.assert_called_once_with(refresh=True, config_file=None)
