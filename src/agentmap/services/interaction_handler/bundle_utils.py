"""
Bundle utility functions for extracting bundle information.

This module contains shared utility functions for extracting bundle context
information from GraphBundle objects or bundle context dictionaries.
"""

from typing import Any, Dict, Optional

from agentmap.models.graph_bundle import GraphBundle


def extract_bundle_info(
    bundle: Optional[GraphBundle] = None,
    bundle_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Extract bundle information for rehydration.

    This function extracts bundle context information from either a GraphBundle
    object or a bundle context dictionary.

    Args:
        bundle: Optional GraphBundle for context extraction
        bundle_context: Optional bundle context metadata

    Returns:
        Dictionary containing bundle information
    """
    if bundle_context:
        return bundle_context.copy()
    elif bundle:
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
        }
    return {}


def extract_graph_name(
    bundle: Optional[GraphBundle] = None,
    bundle_context: Optional[Dict[str, Any]] = None,
    checkpoint_data: Optional[Dict[str, Any]] = None,
    fallback: str = "unknown",
) -> str:
    """
    Extract graph name from various sources.

    Tries to get graph name from bundle, bundle_context, checkpoint_data,
    or falls back to the provided default.

    Args:
        bundle: Optional GraphBundle for context extraction
        bundle_context: Optional bundle context metadata
        checkpoint_data: Optional checkpoint data
        fallback: Fallback value if no graph name found

    Returns:
        Graph name string
    """
    if bundle and hasattr(bundle, "graph_name"):
        return bundle.graph_name
    elif bundle_context and "graph_name" in bundle_context:
        return bundle_context["graph_name"]
    elif checkpoint_data and "graph_name" in checkpoint_data:
        return checkpoint_data["graph_name"]
    return fallback
