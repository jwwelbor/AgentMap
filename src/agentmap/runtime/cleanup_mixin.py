"""Terminal cleanup helpers for runtime containers."""

import asyncio
from typing import Any

from agentmap.async_lifecycle import TerminalTaskOutcome, await_terminal_task


class RuntimeCleanupMixin:
    """Container shutdown and candidate rollback shared by runtime paths."""

    @classmethod
    async def _shutdown_container(cls, container: Any | None) -> None:
        if container is not None:
            await container.llm_service().shutdown()

    @classmethod
    async def _await_shutdown(cls, container: Any | None) -> TerminalTaskOutcome:
        if container is None:
            return TerminalTaskOutcome()
        task = asyncio.create_task(cls._shutdown_container(container))
        return await await_terminal_task(task)

    @classmethod
    async def _rollback_candidate(
        cls, previous: Any | None, refresh: bool
    ) -> TerminalTaskOutcome:
        if previous is not None and not refresh:
            return TerminalTaskOutcome()
        candidate = cls._current_container()
        if candidate is None or candidate is previous:
            return TerminalTaskOutcome()
        detached = cls._detach_if_current(candidate)
        return await cls._await_shutdown(detached)
