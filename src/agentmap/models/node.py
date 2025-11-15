"""
Node domain model for AgentMap workflows.

Simple data container representing a workflow node with properties and edge relationships.
All business logic belongs in services, not in this domain model.
"""

from typing import Any, Dict, List, Optional, Union


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
        tool_source: Optional[str] = None,
        available_tools: Optional[List[str]] = None,
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
            tool_source: Path to Python module containing @tool functions
            available_tools: List of tool names to load from tool_source
        """
        self.name = name
        self.context = context
        self.agent_type = agent_type
        self.inputs = inputs or []
        self.output = output
        self.prompt = prompt
        self.description = description
        self.tool_source = tool_source
        self.available_tools = available_tools
        # Support both str and list[str] for parallel edges
        self.edges: Dict[str, Union[str, List[str]]] = {}

    def add_edge(self, condition: str, target_node: Union[str, List[str]]) -> None:
        """
        Store an edge relationship to another node(s).

        Supports both single-target and multi-target (parallel) edges.

        Args:
            condition: Routing condition (e.g., 'success', 'failure', 'default')
            target_node: Name of target node (str) or list of target nodes (list[str])

        Examples:
            node.add_edge("success", "NextNode")  # Single target (existing)
            node.add_edge("success", ["A", "B", "C"])  # Parallel targets (new)
        """
        self.edges[condition] = target_node

    def is_parallel_edge(self, condition: str) -> bool:
        """
        Check if edge condition routes to multiple parallel nodes.

        Args:
            condition: Edge condition to check

        Returns:
            True if edge has multiple targets, False otherwise
        """
        edge_value = self.edges.get(condition)
        return isinstance(edge_value, list) and len(edge_value) > 1

    def get_edge_targets(self, condition: str) -> List[str]:
        """
        Get edge targets as a list (normalized view).

        Always returns a list for consistent handling, whether edge is
        single-target or multi-target.

        Args:
            condition: Edge condition to retrieve

        Returns:
            List of target node names (empty if condition not found)
        """
        edge_value = self.edges.get(condition)
        if edge_value is None:
            return []
        elif isinstance(edge_value, str):
            return [edge_value]
        else:
            return list(edge_value)  # Return copy to prevent mutation

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
        edge_parts = []
        for condition, targets in self.edges.items():
            if isinstance(targets, list):
                targets_str = "|".join(targets)
                edge_parts.append(f"{condition}->{targets_str}")
            else:
                edge_parts.append(f"{condition}->{targets}")
        edge_info = ", ".join(edge_parts)
        return f"<Node {self.name} [{self.agent_type}] → {edge_info}>"
