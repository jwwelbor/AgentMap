"""Bundle utility functions for extracting bundle information."""

from typing import Any, Dict, Optional

from agentmap.models.graph_bundle import GraphBundle


def extract_bundle_info(
    bundle: Optional[GraphBundle] = None,
    bundle_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
    if bundle and hasattr(bundle, "graph_name"):
        return bundle.graph_name
    elif bundle_context and "graph_name" in bundle_context:
        return bundle_context["graph_name"]
    elif checkpoint_data and "graph_name" in checkpoint_data:
        return checkpoint_data["graph_name"]
    return fallback
