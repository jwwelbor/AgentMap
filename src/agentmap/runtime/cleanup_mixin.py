"""Terminal cleanup helpers for runtime containers."""

import asyncio
from typing import Any, Callable

from agentmap.async_lifecycle import (
    TerminalTaskOutcome,
    await_terminal_task,
    create_task_or_close,
)
from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.services.protocols.service_protocols import (
    LLMServiceLifecycleProtocol,
)


class RuntimeCleanupMixin:
    """Container shutdown and candidate rollback shared by runtime paths."""

    _initializing_container: Any | None = None
    _initializing_config_file: str | None = None

    @classmethod
    def _candidate_container(cls: Any) -> Any | None:
        candidate = cls._initializing_container
        return candidate if candidate is not None else cls._current_container()

    @classmethod
    def _publish_initializing_container(cls: Any) -> None:
        """Expose a candidate only after its startup validation has succeeded."""
        with cls._lock:
            container = cls._initializing_container
            if container is None:
                return
            if cls._container is not None or cls._is_initialized:
                raise AgentMapNotInitialized(
                    "Cannot publish a startup candidate over an active runtime"
                )
            cls._container = container
            cls._is_initialized = True
            cls._runtime_config_file = cls._initializing_config_file
            cls._initializing_container = None
            cls._initializing_config_file = None

    @classmethod
    def _prepare_container_shutdown(cls: Any, container: Any | None) -> None:
        if container is not None:
            service: LLMServiceLifecycleProtocol = container.llm_service()
            service.prepare_shutdown()

    @classmethod
    async def _shutdown_container(cls: Any, container: Any | None) -> None:
        if container is not None:
            service: LLMServiceLifecycleProtocol = container.llm_service()
            await service.shutdown()

    @classmethod
    async def _await_shutdown(cls: Any, container: Any | None) -> TerminalTaskOutcome:
        if container is None:
            return TerminalTaskOutcome()
        cls._assert_pending_cleanup_loop(container)
        try:
            task = create_task_or_close(cls._shutdown_container(container))
        except BaseException as error:
            return TerminalTaskOutcome(task_error=error)
        return await await_terminal_task(task)

    @classmethod
    async def _rollback_candidate(
        cls: Any, previous: Any | None, refresh: bool
    ) -> TerminalTaskOutcome:
        if previous is not None and not refresh:
            return TerminalTaskOutcome()
        candidate = cls._candidate_container()
        if candidate is None or candidate is previous:
            return TerminalTaskOutcome()
        try:
            pending = cls._retire_and_adopt_pending_cleanup(
                candidate, owner_loop=asyncio.get_running_loop()
            )
            cls._prepare_container_shutdown(pending)
        except BaseException as error:
            return TerminalTaskOutcome(task_error=error)
        outcome: TerminalTaskOutcome = await cls._await_shutdown(pending)
        if outcome.task_error is None:
            cls._clear_pending_cleanup(pending)
        return outcome

    @classmethod
    def _shutdown_for_sync_refresh(cls: Any, current: Any) -> None:
        cls._reject_sync_refresh_in_event_loop()
        service = current.llm_service()
        prepare_sync_shutdown = getattr(service, "prepare_sync_shutdown", None)
        if not callable(prepare_sync_shutdown) or prepare_sync_shutdown() is not True:
            raise AgentMapNotInitialized(
                "Synchronous refresh requires a successful shutdown reservation; "
                "use ensure_initialized_async(refresh=True)"
            )
        pending = cls._adopt_pending_cleanup(current)
        asyncio.run(cls._shutdown_container(pending))
        cls._clear_pending_cleanup(pending)

    @classmethod
    def _run_sync_startup(
        cls: Any,
        startup: Callable[[Any, bool], None] | None,
        previous: Any | None,
        refresh: bool,
    ) -> None:
        candidate = cls._candidate_container()
        if candidate is None:
            return
        try:
            if startup is not None:
                startup(candidate, refresh)
            cls._publish_initializing_container()
        except BaseException as startup_error:
            cleanup_error = cls._rollback_candidate_sync(previous, refresh)
            if cleanup_error is not None:
                startup_error.add_note(
                    "Runtime startup rollback also failed with "
                    f"{type(cleanup_error).__name__}"
                )
            raise

    @classmethod
    def _rollback_candidate_sync(
        cls: Any, previous: Any | None, refresh: bool
    ) -> BaseException | None:
        """Detach and close a new runtime after synchronous startup fails."""
        if previous is not None and not refresh:
            return None
        candidate = cls._candidate_container()
        if candidate is None or candidate is previous:
            return None
        try:
            try:
                owner_loop = asyncio.get_running_loop()
            except RuntimeError:
                owner_loop = None
            pending = cls._retire_and_adopt_pending_cleanup(
                candidate, owner_loop=owner_loop
            )
            cls._prepare_container_shutdown(pending)
            if owner_loop is not None:
                return AgentMapNotInitialized(
                    "Runtime startup cleanup remains pending on its owning event loop"
                )
            asyncio.run(cls._shutdown_container(pending))
        except BaseException as cleanup_error:
            return cleanup_error
        cls._clear_pending_cleanup(pending)
        return None

    @classmethod
    async def shutdown(cls: Any) -> None:
        """Detach the runtime and await its LLM resource owner."""
        token = await cls._acquire_async_transaction()
        try:
            if cls._lifespan_tokens:
                raise AgentMapNotInitialized(
                    "Cannot shut down a runtime with active HTTP lifespans"
                )
            container = cls._pending_cleanup()
            if container is None:
                container = cls._current_container()
                if container is None:
                    container = cls._initializing_container
                cls._prepare_container_shutdown(container)
                container = cls._adopt_pending_cleanup(
                    container, owner_loop=asyncio.get_running_loop()
                )
            if container is not None:
                outcome = await cls._await_shutdown(container)
                if outcome.task_error is None:
                    cls._clear_pending_cleanup(container)
                outcome.result()
        finally:
            cls._release_transaction(token)

    @classmethod
    async def _retry_pending_cleanup(cls: Any) -> None:
        container = cls._pending_cleanup()
        if container is None:
            return
        outcome = await cls._await_shutdown(container)
        if outcome.task_error is None:
            cls._clear_pending_cleanup(container)
        outcome.result()

    @classmethod
    def _pending_cleanup(cls: Any) -> Any | None:
        with cls._lock:
            return cls._pending_cleanup_container

    @classmethod
    def _adopt_pending_cleanup(
        cls: Any, container: Any | None, *, owner_loop: Any | None = None
    ) -> Any | None:
        if container is None:
            return None
        with cls._lock:
            pending = cls._validate_pending_cleanup_adoption_locked(
                container, owner_loop
            )
            return cls._adopt_pending_cleanup_locked(container, owner_loop, pending)

    @classmethod
    def _validate_pending_cleanup_adoption_locked(
        cls: Any,
        container: Any,
        owner_loop: Any | None,
        *,
        require_current_or_pending: bool = False,
    ) -> Any | None:
        pending = cls._pending_cleanup_container
        if pending is not None and pending is not container:
            raise AgentMapNotInitialized("A different runtime cleanup is still pending")
        cls._validate_pending_cleanup_loop_locked(container, owner_loop, pending)
        cls._validate_current_container_adoption_locked(
            container, pending, require_current_or_pending
        )
        return pending

    @classmethod
    def _validate_pending_cleanup_loop_locked(
        cls: Any, container: Any, owner_loop: Any | None, pending: Any | None
    ) -> None:
        if pending is container and cls._pending_cleanup_loop is not None:
            pending_loop = cls._pending_cleanup_loop
            if pending_loop.is_closed():
                raise AgentMapNotInitialized(
                    "Runtime cleanup cannot be retried because its owning event loop is closed"
                )
            if owner_loop is not None and pending_loop is not owner_loop:
                raise AgentMapNotInitialized(
                    "Runtime cleanup must be retried on its owning event loop"
                )

    @classmethod
    def _validate_current_container_adoption_locked(
        cls: Any,
        container: Any,
        pending: Any | None,
        require_current_or_pending: bool,
    ) -> None:
        if cls._container is not None and cls._container is not container:
            raise AgentMapNotInitialized(
                "Cannot detach a runtime while another container is active"
            )
        if (
            cls._initializing_container is not None
            and cls._initializing_container is not container
        ):
            raise AgentMapNotInitialized(
                "Cannot detach a runtime while another startup candidate is active"
            )
        if (
            require_current_or_pending
            and cls._container is not container
            and cls._initializing_container is not container
            and pending is not container
        ):
            raise AgentMapNotInitialized(
                "Cannot retire a runtime that is neither current nor pending"
            )

    @classmethod
    def _adopt_pending_cleanup_locked(
        cls: Any, container: Any, owner_loop: Any | None, pending: Any | None
    ) -> Any:
        cls._pending_cleanup_container = container
        if pending is None:
            cls._pending_cleanup_loop = owner_loop
        if cls._container is container:
            cls._is_initialized = False
            cls._container = None
            cls._runtime_config_file = None
        if cls._initializing_container is container:
            cls._initializing_container = None
            cls._initializing_config_file = None
        return container

    @classmethod
    def _retire_and_adopt_pending_cleanup(
        cls: Any, container: Any | None, *, owner_loop: Any | None = None
    ) -> Any | None:
        """Close admission before transferring a retiring runtime to cleanup."""
        if container is None:
            return None
        with cls._lock:
            pending = cls._validate_pending_cleanup_adoption_locked(
                container, owner_loop, require_current_or_pending=True
            )
            service: LLMServiceLifecycleProtocol = container.llm_service()
            service.retire()
            return cls._adopt_pending_cleanup_locked(container, owner_loop, pending)

    @classmethod
    def _assert_pending_cleanup_loop(cls: Any, container: Any | None) -> None:
        if container is None:
            return
        with cls._lock:
            if cls._pending_cleanup_container is not container:
                return
            owner_loop = cls._pending_cleanup_loop
        if owner_loop is None:
            return
        if owner_loop.is_closed():
            raise AgentMapNotInitialized(
                "Runtime cleanup cannot be retried because its owning event loop is closed"
            )
        if asyncio.get_running_loop() is not owner_loop:
            raise AgentMapNotInitialized(
                "Runtime cleanup must be retried on its owning event loop"
            )

    @classmethod
    def _clear_pending_cleanup(cls: Any, container: Any | None) -> None:
        if container is None:
            return
        with cls._lock:
            if cls._pending_cleanup_container is container:
                cls._pending_cleanup_container = None
                cls._pending_cleanup_loop = None

    @staticmethod
    def _reject_sync_refresh_in_event_loop() -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        raise AgentMapNotInitialized(
            "Runtime refresh from an event loop requires ensure_initialized_async()"
        )
