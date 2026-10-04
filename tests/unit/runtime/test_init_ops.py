"""Unit tests for agentmap.runtime.init_ops.

TD-049: ensure_initialized_async is the canonical async startup entrypoint.
RuntimeManager owns the blocking offload and complete lifecycle transaction;
callers only need to prove they await this facade.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestEnsureInitializedAsyncOffload:
    """TD-018/TD-049: the facade delegates to RuntimeManager ownership."""

    @pytest.mark.asyncio
    async def test_delegates_to_runtime_manager_transaction(self):
        from agentmap.runtime.init_ops import _validate_cache, ensure_initialized_async

        with patch(
            "agentmap.runtime.init_ops.RuntimeManager.initialize_async",
            new_callable=AsyncMock,
        ) as initialize:
            await ensure_initialized_async(config_file="/configs/custom.yaml")

        initialize.assert_awaited_once_with(
            _validate_cache, refresh=False, config_file="/configs/custom.yaml"
        )

    @pytest.mark.asyncio
    async def test_forwards_refresh_flag(self):
        from agentmap.runtime.init_ops import _validate_cache, ensure_initialized_async

        with patch(
            "agentmap.runtime.init_ops.RuntimeManager.initialize_async",
            new_callable=AsyncMock,
        ) as initialize:
            await ensure_initialized_async(refresh=True)

        initialize.assert_awaited_once_with(
            _validate_cache, refresh=True, config_file=None
        )
