"""
Core API orchestration layer for AgentMap.

This module provides a clean, framework-agnostic interface for API functionality.
All framework-specific implementations are delegated to the infrastructure layer.
"""

from agentmap.core.api.server_factory import (
    APIServer,
    create_api_server,
    create_default_api_server,
)

# Clean interface exports - no framework-specific imports
__all__ = [
    "APIServer",
    "create_api_server",
    "create_default_api_server",
]


# Backward compatibility imports with deprecation warnings
def create_fastapi_app(*args, **kwargs):
    """
    Deprecated: Use create_api_server() instead.

    This function is maintained for backward compatibility only.
    """
    import warnings

    warnings.warn(
        "create_fastapi_app is deprecated. Use create_api_server() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    from agentmap.infrastructure.api.fastapi.server import (
        create_fastapi_app as _create_app,
    )

    return _create_app(*args, **kwargs)


def run_server(*args, **kwargs):
    """
    Deprecated: Use create_api_server().run() instead.

    This function is maintained for backward compatibility only.
    """
    import warnings

    warnings.warn(
        "run_server is deprecated. Use create_api_server().run() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    from agentmap.infrastructure.api.fastapi.server import run_server as _run_server

    return _run_server(*args, **kwargs)
