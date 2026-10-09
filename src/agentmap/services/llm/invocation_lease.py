"""Invocation lease state shared by governed calls and provider clients."""

import asyncio
import inspect
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Dict, List, Optional, TypeVar

from agentmap.exceptions import LLMConfigurationError

_T = TypeVar("_T")


class GovernedUseLease:
    """Keep governed provider work visible to shutdown until it truly ends."""

    def __init__(self, factory: Any, *, pending_worker: bool = False) -> None:
        self._factory = factory
        self._state = "pending" if pending_worker else "active"

    def start_worker(self) -> bool:
        with self._factory._cache_lock:
            if self._state != "pending":
                return False
            self._state = "active"
            return True

    def release_if_pending(self) -> None:
        with self._factory._cache_lock:
            if self._state == "pending":
                self._release_locked()

    def release(self) -> None:
        with self._factory._cache_lock:
            self._release_locked()

    def _release_locked(self) -> None:
        if self._state != "released":
            self._state = "released"
            self._factory._active_uses.discard(self)


governed_use_lease: ContextVar[GovernedUseLease | None] = ContextVar(
    "agentmap_governed_use_lease", default=None
)


@contextmanager
def clear_governed_use_lease() -> Iterator[None]:
    """Prevent a new public service call from inheriting another call's lease."""
    token = governed_use_lease.set(None)
    try:
        yield
    finally:
        governed_use_lease.reset(token)


def dispatch_plain_sync_call(
    call_args: tuple[Any, ...],
    cache_system_prompt: bool,
    kwargs: Dict[str, Any],
    telemetry_call: Optional[Callable[..., _T]],
    core_call: Callable[..., _T],
) -> _T:
    """Run a synchronous service call without inheriting an invocation lease."""
    with clear_governed_use_lease():
        if "attempt_lifecycle" in kwargs:
            raise LLMConfigurationError(
                "attempt_lifecycle is supported only by call_llm_async"
            )
        kwargs["cache_system_prompt"] = cache_system_prompt
        dispatch = telemetry_call if telemetry_call is not None else core_call
        return dispatch(*call_args, **kwargs)


async def invoke_provider_async(
    client: Any,
    messages: List[Any],
    client_factory: Any,
    *,
    governed: bool,
) -> Any:
    """Invoke natively or retain ownership of a governed worker thread."""
    async_invoke = getattr(client, "ainvoke", None)
    if callable(async_invoke):
        response = async_invoke(messages)
        if inspect.isawaitable(response):
            return await response
        return response
    if not governed:
        return await asyncio.to_thread(client.invoke, messages)

    worker_lease = client_factory.begin_governed_worker()

    def invoke_sync() -> Any:
        if not worker_lease.start_worker():
            return None
        try:
            return client.invoke(messages)
        finally:
            worker_lease.release()

    try:
        return await asyncio.to_thread(invoke_sync)
    except BaseException:
        worker_lease.release_if_pending()
        raise
