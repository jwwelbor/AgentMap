"""Bundle extraction utilities for scaffolding."""

from typing import Any, Dict, Optional

from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.function_resolution_service import FunctionResolutionService


class BundleExtractor:
    """Extracts agent and function information from GraphBundle objects."""

    def __init__(self, function_service: FunctionResolutionService):
        self.function_service = function_service

    def extract_agent_info(
        self, agent_type: str, bundle: GraphBundle
    ) -> Optional[Dict[str, Any]]:
        """Extract agent information from bundle nodes."""
        for node_name, node in bundle.nodes.items():
            if node.agent_type.lower() == agent_type.lower():
                return {
                    "agent_type": agent_type,
                    "node_name": node_name,
                    "context": node.context or "",
                    "prompt": node.prompt or "",
                    "input_fields": node.inputs or [],
                    "output_field": node.output or "",
                    "description": node.description or "",
                }
        return None

    def extract_functions(self, bundle: GraphBundle) -> Dict[str, Dict[str, Any]]:
        """Extract function information from bundle nodes' edges."""
        func_info = {}
        for node_name, node in bundle.nodes.items():
            for condition, target in node.edges.items():
                func_name = self.function_service.extract_func_ref(condition)
                if func_name and func_name not in func_info:
                    func_info[func_name] = {
                        "node_name": node_name,
                        "context": node.context or "",
                        "input_fields": node.inputs or [],
                        "output_field": node.output or "",
                        "success_next": target if condition == f"func:{func_name}" else "",
                        "failure_next": "",
                        "description": f"Edge function for {node_name} -> {target}",
                    }
        return func_info
