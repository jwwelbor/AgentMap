"""Runtime initialization and container access."""

from typing import Any

from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
from agentmap.runtime.runtime_manager import RuntimeManager


def _is_cache_initialized(container) -> bool:
    try:
        availability_cache_service = container.availability_cache_service()
        return availability_cache_service.is_initialized()
    except Exception:
        return False


def _refresh_cache(container) -> None:
    try:
        availability_cache_service = container.availability_cache_service()
        availability_cache_service.refresh_cache(container)
    except Exception as e:
        raise AgentMapNotInitialized(f"Failed to refresh provider cache: {e}")


def _validate_cache(container: Any, refresh: bool) -> None:
    if refresh or not _is_cache_initialized(container):
        _refresh_cache(container)
    if not _is_cache_initialized(container):
        raise AgentMapNotInitialized("Cache file was not created after refresh")


def ensure_initialized(
    *, refresh: bool = False, config_file: str | None = None
) -> None:
    try:
        RuntimeManager.initialize(
            refresh=refresh,
            config_file=config_file,
            startup=_validate_cache,
        )
    except Exception as e:
        if isinstance(e, AgentMapNotInitialized):
            raise
        raise AgentMapNotInitialized(f"Initialization failed: {e}")


async def ensure_initialized_async(
    *, refresh: bool = False, config_file: str | None = None
) -> None:
    """Run the RuntimeManager-owned async startup transaction."""
    await RuntimeManager.initialize_async(
        _validate_cache,
        refresh=refresh,
        config_file=config_file,
    )


async def acquire_runtime_lifespan(
    *, config_file: str | None = None
) -> tuple[object, Any]:
    """Lease the initialized runtime for an HTTP application lifespan."""
    return await RuntimeManager.acquire_lifespan(
        _validate_cache, config_file=config_file
    )


async def release_runtime_lifespan(lease: object) -> None:
    """Release an HTTP application's runtime lease."""
    await RuntimeManager.release_lifespan(lease)


def get_container():
    return RuntimeManager.get_container()


async def shutdown_runtime() -> None:
    """Await resource cleanup and detach the process runtime container."""
    await RuntimeManager.shutdown()
