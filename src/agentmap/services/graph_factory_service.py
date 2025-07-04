"""
GraphFactoryService for AgentMap.

Centralized service for all graph creation, name resolution, and entry point detection.
Eliminates duplication across GraphDefinitionService, GraphExecutionService, and GraphAssemblyService.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from agentmap.models.graph import Graph
from agentmap.models.node import Node
from agentmap.services.logging_service import LoggingService


class GraphFactoryService:
    """
    Centralized factory for all graph creation operations.

    Single source of truth for:
    - Graph object creation and node population
    - Entry point detection with consistent fallback logic
    - Graph name resolution from various sources
    - Node dictionary to Graph domain model conversion
    """

    def __init__(self, logging_service: LoggingService):
        """Initialize factory with logging service."""
        self.logger = logging_service.get_class_logger(self)
        self.logger.info("[GraphFactoryService] Initialized")

    def create_graph_from_nodes(
        self,
        graph_name: str,
        nodes_dict: Dict[str, Node],
        auto_detect_entry_point: bool = True,
    ) -> Graph:
        """
        Create Graph domain model from nodes dictionary.

        Args:
            graph_name: Name for the graph
            nodes_dict: Dictionary mapping node names to Node instances
            auto_detect_entry_point: Whether to automatically detect entry point

        Returns:
            Graph domain model with nodes and entry point set
        """
        self.logger.debug(f"Creating graph '{graph_name}' with {len(nodes_dict)} nodes")

        # Create Graph domain model
        graph = Graph(name=graph_name)

        # Add all nodes to the graph
        for node_name, node in nodes_dict.items():
            graph.nodes[node_name] = node

        # Detect and set entry point
        if auto_detect_entry_point:
            entry_point = self.detect_entry_point(graph)
            graph.entry_point = entry_point

        self.logger.debug(
            f"Created graph '{graph_name}' with entry point: {graph.entry_point}"
        )
        return graph

    def create_graph_from_definition(
        self, graph_def: Dict[str, Any], graph_name: Optional[str] = None
    ) -> Graph:
        """
        Create Graph domain model from in-memory definition dictionary.

        Args:
            graph_def: Dictionary definition with node name -> node object mapping
            graph_name: Optional graph name (will be resolved if not provided)

        Returns:
            Graph domain model
        """
        # Resolve graph name if not provided
        if graph_name is None:
            graph_name = self.resolve_graph_name_from_definition(graph_def)

        self.logger.debug(f"Creating graph from definition: '{graph_name}'")

        # Convert definition to nodes dictionary
        nodes_dict = {}
        for node_name, node in graph_def.items():
            # Assume definition contains Node objects
            nodes_dict[node_name] = node

        return self.create_graph_from_nodes(graph_name, nodes_dict)

    def resolve_graph_name_from_definition(self, graph_def: Dict[str, Any]) -> str:
        """
        Resolve graph name from definition using standardized logic.

        Args:
            graph_def: Graph definition dictionary

        Returns:
            Resolved graph name string
        """
        # Priority 1: Check for explicit graph name metadata
        if hasattr(graph_def, "get") and graph_def.get("__graph_name"):
            name = graph_def["__graph_name"]
            self.logger.debug(f"Resolved graph name from metadata: '{name}'")
            return name

        # Priority 2: Extract from first node's graph_name attribute
        if graph_def:
            for node_name, node in graph_def.items():
                if hasattr(node, "graph_name") and node.graph_name:
                    name = node.graph_name
                    self.logger.debug(
                        f"Resolved graph name from node attribute: '{name}'"
                    )
                    return name

        # Priority 3: Generate name based on node count
        if graph_def:
            node_count = len(graph_def)
            name = f"graph_{node_count}_nodes"
            self.logger.debug(f"Generated graph name from node count: '{name}'")
            return name

        # Fallback
        name = "unknown_graph"
        self.logger.warning(f"Using fallback graph name: '{name}'")
        return name

    def resolve_graph_name_from_path(self, path: Path) -> str:
        """
        Resolve graph name from file path.

        Args:
            path: Path to graph file (CSV, bundle, etc.)

        Returns:
            Graph name derived from path
        """
        # Use file stem (filename without extension)
        name = path.stem
        self.logger.debug(f"Resolved graph name from path: '{name}'")
        return name

    def detect_entry_point(self, graph: Graph) -> Optional[str]:
        """
        Detect entry point for a graph using simple, predictable logic.

        Entry point detection priority:
        1. Node explicitly marked as entry point (for programmatic use)
        2. First node in the graph (natural CSV order)

        Args:
            graph: Graph domain model

        Returns:
            Entry point node name or None if no nodes
        """
        if not graph.nodes:
            self.logger.warning("Cannot detect entry point: graph has no nodes")
            return None

        node_names = list(graph.nodes.keys())

        # Priority 1: Check for explicitly marked entry point (for programmatic use)
        for node_name, node in graph.nodes.items():
            if hasattr(node, "_is_entry_point") and node._is_entry_point:
                self.logger.debug(f"Found explicitly marked entry point: '{node_name}'")
                return node_name

        # Priority 2: First node (natural CSV order - most common case)
        entry_point = node_names[0]
        self.logger.debug(f"Using first node as entry point: '{entry_point}'")
        return entry_point

    def validate_graph_structure(self, graph: Graph) -> List[str]:
        """
        Validate graph structure and return any issues.

        Args:
            graph: Graph to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check basic structure
        if not graph.nodes:
            errors.append("Graph has no nodes")
            return errors

        if not graph.entry_point:
            errors.append("Graph has no entry point")
        elif graph.entry_point not in graph.nodes:
            errors.append(f"Entry point '{graph.entry_point}' not found in nodes")

        # Check edge validity
        for node_name, node in graph.nodes.items():
            for condition, target in node.edges.items():
                if target not in graph.nodes:
                    errors.append(
                        f"Node '{node_name}' edge '{condition}' targets non-existent node '{target}'"
                    )

        self.logger.debug(f"Graph validation for '{graph.name}': {len(errors)} errors")
        return errors

    def get_graph_summary(self, graph: Graph) -> Dict[str, Any]:
        """
        Get summary information about a graph.

        Args:
            graph: Graph to summarize

        Returns:
            Dictionary with graph summary information
        """
        return {
            "name": graph.name,
            "node_count": len(graph.nodes),
            "node_names": list(graph.nodes.keys()),
            "entry_point": graph.entry_point,
            "total_edges": sum(len(node.edges) for node in graph.nodes.values()),
            "validation_errors": self.validate_graph_structure(graph),
        }
