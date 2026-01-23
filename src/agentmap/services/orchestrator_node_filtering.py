"""
Node filtering utilities for OrchestratorService.
"""

from typing import Any, Dict


class NodeFilter:
    @staticmethod
    def apply_node_filter(
        nodes: Dict[str, Dict[str, Any]], node_filter: str
    ) -> Dict[str, Dict[str, Any]]:
        if not nodes or node_filter == "all":
            return nodes
        if "|" in node_filter:
            node_names = [name.strip() for name in node_filter.split("|")]
            return {name: info for name, info in nodes.items() if name in node_names}
        elif node_filter.startswith("nodeType:"):
            type_filter = node_filter.split(":", 1)[1].strip()
            return {
                name: info
                for name, info in nodes.items()
                if info.get("type", "").lower() == type_filter.lower()
            }
        return nodes
