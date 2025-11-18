"""
Bundle extraction utilities for scaffolding.

This module provides functionality for extracting agent and function
information from GraphBundle objects for scaffolding purposes.
"""

from typing import Any, Dict, Optional

from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.function_resolution_service import FunctionResolutionService


class BundleExtractor:
    """
    Extracts agent and function information from GraphBundle objects.

    This class provides methods to extract structured information from
    bundle nodes that can be used for scaffolding agent classes and
    edge functions.
    """

    def __init__(self, function_service: FunctionResolutionService):
        """
        Initialize the BundleExtractor.

        Args:
            function_service: Service for function resolution and extraction
        """
        self.function_service = function_service

    def extract_agent_info(
        self, agent_type: str, bundle: GraphBundle
    ) -> Optional[Dict[str, Any]]:
        """
        Extract agent information from bundle nodes.

        Args:
            agent_type: Agent type to find
            bundle: GraphBundle containing nodes

        Returns:
            Agent info dict or None if not found
        """
        # Search through bundle nodes for matching agent type
        for node_name, node in bundle.nodes.items():
            if node.agent_type.lower() == agent_type.lower():
                # Convert Node object to info dict format expected by scaffolding
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

    def extract_functions(
        self, bundle: GraphBundle
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract function information from bundle nodes' edges.

        Args:
            bundle: GraphBundle containing nodes with edges

        Returns:
            Dictionary mapping function names to their info
        """
        func_info = {}

        # Process each node's edges for function references
        for node_name, node in bundle.nodes.items():
            for condition, target in node.edges.items():
                # Check if edge condition is a function reference
                func_name = self.function_service.extract_func_ref(condition)
                if func_name and func_name not in func_info:
                    func_info[func_name] = {
                        "node_name": node_name,
                        "context": node.context or "",
                        "input_fields": node.inputs or [],
                        "output_field": node.output or "",
                        "success_next": (
                            target if condition == f"func:{func_name}" else ""
                        ),
                        "failure_next": "",  # Would need more edge analysis
                        "description": f"Edge function for {node_name} -> {target}",
                    }

        return func_info
