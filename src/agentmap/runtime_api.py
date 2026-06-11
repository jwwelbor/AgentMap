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
    inspect_graph_async,
    list_graphs,
    list_graphs_async,
    resume_workflow,
    resume_workflow_async,
    run_workflow,
    run_workflow_async,
    validate_workflow,
    validate_workflow_async,
)

# Public alias for external applications (more descriptive than ensure_initialized)
agentmap_initialize = ensure_initialized

__all__ = [
    "ensure_initialized",  # Internal/legacy name
    "agentmap_initialize",  # Recommended external name
    "get_container",
    "run_workflow",
    "run_workflow_async",
    "resume_workflow",
    "resume_workflow_async",
    "list_graphs",
    "list_graphs_async",
    "inspect_graph",
    "inspect_graph_async",
    "validate_workflow",
    "validate_workflow_async",
    "update_bundle",
    "scaffold_agents",
    "refresh_cache",
    "validate_cache",
    "get_config",
    "diagnose_system",
]
