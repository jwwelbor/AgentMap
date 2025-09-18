"""
AgentMap Runtime API (Facade)
=============================

This module provides the stable, public API for running AgentMap graphs
from any launch point (CLI, serverless adapters, embedded apps).

It re-exports the public functions from the split runtime modules.
"""

from .runtime.bundle_ops import scaffold_agents, update_bundle
from .runtime.init_ops import ensure_initialized, get_container
from .runtime.system_ops import (
    diagnose_system,
    get_config,
    refresh_cache,
    validate_cache,
)
from .runtime.workflow_ops import (
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
]
