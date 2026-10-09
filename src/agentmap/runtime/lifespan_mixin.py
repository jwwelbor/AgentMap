"""HTTP lifespan leases for the process runtime singleton."""

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional

from agentmap.async_lifecycle import await_terminal_task, create_cleanup_task_or_close
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
    def _current_container(cls: Any) -> Any | None:
        with cls._lock:
            if not cls._is_initialized:
                return None
            return cls._container

    @classmethod
    async def acquire_lifespan(
        cls: Any,
        startup: Callable[[Any, bool], None],
        *,
        config_file: Optional[str] = None,
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
            if previous is not None:
                cls._assert_runtime_owner_loop(previous)
            await cls._run_initialization_transaction(
                startup, refresh=False, config_file=config_file
            )
            container = cls.get_container()
            if previous is None:
                cls._assert_runtime_owner_loop(container)
            if not cls._lifespan_tokens:
                cls._lifespan_owned = previous is None
                cls._lifespan_container = container
                cls._lifespan_loop = loop
            lease = object()
            cls._lifespan_tokens.add(lease)
            return lease, container
        finally:
            cls._release_transaction(transaction)

    @staticmethod
    def _assert_runtime_owner_loop(container: Any) -> None:
        """Check loop affinity when the container exposes governed clients."""
        assert_owner_loop = getattr(
            container.llm_service(), "assert_runtime_owner_loop", None
        )
        if callable(assert_owner_loop):
            assert_owner_loop()

    @classmethod
    async def release_lifespan(cls: Any, lease: object) -> None:
        """Release one HTTP lease and close its owned runtime after the last exit."""
        task, scheduling_error = create_cleanup_task_or_close(
            lambda: cls._release_lifespan_transaction(lease)
        )
        outcome = await await_terminal_task(task)
        if outcome.caller_cancellation is not None and scheduling_error is not None:
            for error, operation in (
                (scheduling_error, "scheduling"),
                (outcome.task_error, "cleanup"),
            ):
                if error is not None:
                    outcome.caller_cancellation.add_note(
                        "HTTP lifespan release "
                        f"{operation} failed with {type(error).__name__}"
                    )
            raise outcome.caller_cancellation from None
        if scheduling_error is not None:
            if outcome.task_error is not None:
                scheduling_error.add_note(
                    "HTTP lifespan release cleanup failed with "
                    f"{type(outcome.task_error).__name__}"
                )
            raise scheduling_error
        outcome.result()

    @classmethod
    async def _release_lifespan_transaction(cls: Any, lease: object) -> None:
        transaction = await cls._acquire_async_transaction()
        try:
            if lease not in cls._lifespan_tokens:
                raise RuntimeError("Unknown HTTP lifespan lease")
            if cls._lifespan_loop is not asyncio.get_running_loop():
                raise AgentMapNotInitialized(
                    "HTTP lifespan must be released on its owning event loop"
                )
            last_lease = len(cls._lifespan_tokens) == 1
            owned = cls._lifespan_owned
            container = cls._lifespan_container
            pending = None
            if last_lease and owned:
                pending = cls._retire_and_adopt_pending_cleanup(
                    container, owner_loop=asyncio.get_running_loop()
                )
            cls._lifespan_tokens.remove(lease)
            if cls._lifespan_tokens:
                return
            cls._lifespan_owned = False
            cls._lifespan_container = None
            cls._lifespan_loop = None
            if owned:
                cls._prepare_container_shutdown(pending)
                outcome = await cls._await_shutdown(pending)
                if outcome.task_error is None:
                    cls._clear_pending_cleanup(pending)
                outcome.result()
        finally:
            cls._release_transaction(transaction)
