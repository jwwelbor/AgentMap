# src/agentmap/models/graph_spec.py
"""
GraphSpec domain model for representing parsed CSV data.

This intermediate model represents the raw parsed data from CSV files
before conversion to full Graph domain models. It serves as a clean
interface between CSV parsing and graph building.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union


@dataclass
class NodeSpec:
    """Specification for a single node parsed from CSV."""

    name: str
    graph_name: str
    agent_type: Optional[str] = None
    prompt: Optional[str] = None
    description: Optional[str] = None
    context: Optional[str] = None
    input_fields: List[str] = field(default_factory=list)
    output_field: Optional[str] = None

    # Edge information (raw from CSV)
    # Support both single target (str) and multiple targets (list[str]) for parallel execution
    edge: Optional[Union[str, List[str]]] = None
    success_next: Optional[Union[str, List[str]]] = None
    failure_next: Optional[Union[str, List[str]]] = None

    # Tool information
    available_tools: Optional[List[str]] = None
    tool_source: Optional[str] = None

    # Metadata
    line_number: Optional[int] = None

    def is_parallel_edge(self, edge_type: str) -> bool:
        """Check if specified edge type has multiple targets.

        Args:
            edge_type: One of 'edge', 'success_next', 'failure_next'

        Returns:
            True if edge has multiple targets, False otherwise
        """
        edge_value = getattr(self, edge_type, None)
        return isinstance(edge_value, list) and len(edge_value) > 1

    def get_edge_targets(self, edge_type: str) -> List[str]:
        """Get edge targets as a list (always returns list).

        Args:
            edge_type: One of 'edge', 'success_next', 'failure_next'

        Returns:
            List of target node names (may be empty, single, or multiple)
        """
        edge_value = getattr(self, edge_type, None)
        if edge_value is None:
            return []
        elif isinstance(edge_value, str):
            return [edge_value]
        else:
            return edge_value


@dataclass
class GraphSpec:
    """Specification for all graphs parsed from a CSV file."""

    graphs: Dict[str, List[NodeSpec]] = field(default_factory=dict)
    total_rows: int = 0
    file_path: Optional[str] = None

    def add_node_spec(self, node_spec: NodeSpec) -> None:
        """Add a node specification to the appropriate graph."""
        if node_spec.graph_name not in self.graphs:
            self.graphs[node_spec.graph_name] = []
        self.graphs[node_spec.graph_name].append(node_spec)

    def get_graph_names(self) -> List[str]:
        """Get list of all graph names found in the CSV."""
        return list(self.graphs.keys())

    def get_nodes_for_graph(self, graph_name: str) -> List[NodeSpec]:
        """Get all node specifications for a specific graph."""
        return self.graphs.get(graph_name, [])

    def has_graph(self, graph_name: str) -> bool:
        """Check if a specific graph exists in the specification."""
        return graph_name in self.graphs
