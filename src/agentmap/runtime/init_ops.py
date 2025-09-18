"""Runtime initialization and container access."""

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


def ensure_initialized(
    *, refresh: bool = False, config_file: str | None = None
) -> None:
    try:
        RuntimeManager.initialize(refresh=refresh, config_file=config_file)
        container = RuntimeManager.get_container()
        if refresh or not _is_cache_initialized(container):
            _refresh_cache(container)
        if not _is_cache_initialized(container):
            raise AgentMapNotInitialized("Cache file was not created after refresh")
    except Exception as e:
        if isinstance(e, AgentMapNotInitialized):
            raise
        raise AgentMapNotInitialized(f"Initialization failed: {e}")


def get_container():
    return RuntimeManager.get_container()
