# src/agentmap/models/graph_spec.py
"""
GraphSpec domain model for representing parsed CSV data.

This intermediate model represents the raw parsed data from CSV files
before conversion to full Graph domain models. It serves as a clean
interface between CSV parsing and graph building.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


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
    edge: Optional[str] = None
    success_next: Optional[str] = None
    failure_next: Optional[str] = None

    # Metadata
    line_number: Optional[int] = None


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
