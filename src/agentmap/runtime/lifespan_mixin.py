"""HTTP lifespan leases for the process runtime singleton."""

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional

from agentmap.async_lifecycle import await_terminal_task
from agentmap.di import discover_config_file
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized


def canonical_config_path(config_file: str | None) -> str | None:
    """Identify one config file independent of relative path or symlink spelling."""
    return str(Path(config_file).resolve()) if config_file else None


def effective_config_file(config_file: str | None) -> str | None:
    """Resolve AgentMap's explicit path or current-directory discovery."""
    return canonical_config_path(config_file or discover_config_file())


class RuntimeLifespanMixin:
    """Lease operations serialized by the consuming runtime manager."""

    _lifespan_tokens: set[object] = set()
    _lifespan_owned = False
    _lifespan_container = None
    _lifespan_loop = None

    @classmethod
    async def acquire_lifespan(
        cls, startup: Callable[[Any, bool], None], *, config_file: Optional[str] = None
    ) -> tuple[object, Any]:
        """Initialize and lease the runtime for one HTTP application lifespan."""
        transaction = await cls._acquire_async_transaction()
        try:
            loop = asyncio.get_running_loop()
            if cls._lifespan_tokens and cls._lifespan_loop is not loop:
                raise AgentMapNotInitialized(
                    "Overlapping HTTP lifespans must use the same event loop"
                )
            previous = cls._current_container()
            if (
                previous is not None
                and effective_config_file(config_file) != cls._runtime_config_file
            ):
                raise AgentMapNotInitialized(
                    "HTTP lifespan config differs from the active runtime"
                )
            await cls._run_initialization_transaction(
                startup, refresh=False, config_file=config_file
            )
            container = cls.get_container()
            if not cls._lifespan_tokens:
                cls._lifespan_owned = previous is None
                cls._lifespan_container = container
                cls._lifespan_loop = loop
            lease = object()
            cls._lifespan_tokens.add(lease)
            return lease, container
        finally:
            cls._release_transaction(transaction)

    @classmethod
    async def release_lifespan(cls, lease: object) -> None:
        """Release one HTTP lease and close its owned runtime after the last exit."""
        task = asyncio.create_task(cls._release_lifespan_transaction(lease))
        (await await_terminal_task(task)).result()

    @classmethod
    async def _release_lifespan_transaction(cls, lease: object) -> None:
        transaction = await cls._acquire_async_transaction()
        try:
            if lease not in cls._lifespan_tokens:
                raise RuntimeError("Unknown HTTP lifespan lease")
            if cls._lifespan_loop is not asyncio.get_running_loop():
                raise AgentMapNotInitialized(
                    "HTTP lifespan must be released on its owning event loop"
                )
            cls._lifespan_tokens.remove(lease)
            if cls._lifespan_tokens:
                return
            owned = cls._lifespan_owned
            container = cls._lifespan_container
            cls._lifespan_owned = False
            cls._lifespan_container = None
            cls._lifespan_loop = None
            if owned:
                detached = cls._detach_if_current(container)
                outcome = await cls._await_shutdown(detached)
                outcome.result()
        finally:
            cls._release_transaction(transaction)
