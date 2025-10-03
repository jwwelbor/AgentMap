# src/agentmap/runtime/__init__.py
"""
AgentMap Runtime Package
========================

Provides grouped runtime operations with a stable public API.

Preferred import path going forward:

    from agentmap.runtime import run_workflow

Legacy imports via `agentmap.runtime_api` continue to work.
"""

from .bundle_ops import scaffold_agents, update_bundle
from .init_ops import ensure_initialized, get_container
from .runtime_manager import RuntimeManager
from .system_ops import (
    diagnose_system,
    get_config,
    get_health,
    get_system_paths,
    get_version,
    refresh_cache,
    validate_cache,
)
from .workflow_ops import (
    inspect_graph,
    list_graphs,
    resume_workflow,
    run_workflow,
    validate_workflow,
)

__all__ = [
    "ensure_initialized",
    "get_container",
    "run_workflow",
    "resume_workflow",
    "list_graphs",
    "inspect_graph",
    "validate_workflow",
    "update_bundle",
    "scaffold_agents",
    "refresh_cache",
    "validate_cache",
    "get_config",
    "diagnose_system",
    "RuntimeManager",
    "get_health",
    "get_system_paths",
    "get_version",
]
