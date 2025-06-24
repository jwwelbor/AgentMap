"""
Node domain model for AgentMap workflows.

Simple data container representing a workflow node with properties and edge relationships.
All business logic belongs in services, not in this domain model.
"""

from typing import Any, Dict, List, Optional


class Node:
    """
    Domain entity representing a workflow node.

    Simple data container for node properties and edge relationships.
    Business logic for parsing, validation, and graph operations belongs in services.
    """

    def __init__(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None,
        agent_type: Optional[str] = None,
        inputs: Optional[List[str]] = None,
        output: Optional[str] = None,
        prompt: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """
        Initialize a workflow node with properties.

        Args:
            name: Unique identifier for the node
            context: Node-specific context and configuration
            agent_type: Type of agent this node represents
            inputs: List of input field names
            output: Output field name
            prompt: Prompt template for the node
            description: Human-readable description of the node
        """
        self.name = name
        self.context = context
        self.agent_type = agent_type
        self.inputs = inputs or []
        self.output = output
        self.prompt = prompt
        self.description = description
        self.edges: Dict[str, str] = {}  # condition: next_node

    def add_edge(self, condition: str, target_node: str) -> None:
        """
        Store an edge relationship to another node.

        Used by GraphBuilder to store routing relationships during CSV parsing.

        Args:
            condition: Routing condition (e.g., 'success', 'failure', 'default')
            target_node: Name of the target node
        """
        self.edges[condition] = target_node

    def has_conditional_routing(self) -> bool:
        """
        Check if this node has conditional routing (success/failure paths).

        Simple query method for determining if the node uses conditional routing
        versus direct routing.

        Returns:
            True if node has 'success' or 'failure' edges, False otherwise
        """
        return "success" in self.edges or "failure" in self.edges

    def __repr__(self) -> str:
        """String representation of the node."""
        edge_info = ", ".join([f"{k}->{v}" for k, v in self.edges.items()])
        return f"<Node {self.name} [{self.agent_type}] → {edge_info}>"
