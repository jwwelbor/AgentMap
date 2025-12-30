"""
Utility functions for graph runner operations.

Extracted from GraphRunnerService to improve modularity.
"""

from typing import Any, Dict

from agentmap.models.graph_bundle import GraphBundle


def create_node_registry_from_bundle(bundle: GraphBundle, logger=None) -> dict:
    """
    Create node registry from bundle for orchestrator agents.

    Transforms Node objects into the metadata format expected by OrchestratorService
    for node selection and routing decisions.

    Args:
        bundle: GraphBundle with nodes
        logger: Optional logger for debugging

    Returns:
        Dictionary mapping node names to metadata dicts with:
        - description: Node description for keyword matching
        - prompt: Node prompt for additional context
        - type: Agent type for filtering
        - context: Optional context dict for keyword extraction
    """
    if not bundle.nodes:
        return {}

    # Transform Node objects to metadata format expected by orchestrators
    registry = {}
    for node_name, node in bundle.nodes.items():
        # Extract metadata fields that OrchestratorService actually uses
        registry[node_name] = {
            "description": node.description or "",
            "prompt": node.prompt or "",
            "type": node.agent_type or "",
            # Include context if it's a dict (for keyword parsing)
            "context": node.context if isinstance(node.context, dict) else {},
        }

    if logger:
        logger.debug(
            f"[GraphRunnerService] Created node registry with {len(registry)} nodes "
            f"for orchestrator routing"
        )

    return registry


def create_bundle_context(bundle: GraphBundle) -> Dict[str, Any]:
    """
    Create bundle context dict for interrupt handling.

    Args:
        bundle: GraphBundle to extract context from

    Returns:
        Dictionary with bundle metadata
    """
    return {
        "csv_hash": getattr(bundle, "csv_hash", None),
        "bundle_path": (
            str(bundle.bundle_path)
            if hasattr(bundle, "bundle_path") and bundle.bundle_path
            else None
        ),
        "csv_path": (
            str(bundle.csv_path)
            if hasattr(bundle, "csv_path") and bundle.csv_path
            else None
        ),
        "graph_name": bundle.graph_name,
    }
