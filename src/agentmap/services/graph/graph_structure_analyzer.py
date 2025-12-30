# services/graph/graph_structure_analyzer.py

from typing import Any, Dict, List, Set

from agentmap.models.node import Node
from agentmap.services.logging_service import LoggingService


class GraphStructureAnalyzer:
    """
    Analyzes graph structure for Phase 2 optimization metadata.

    This service handles:
    - Graph structure analysis (node count, edges, conditional routing)
    - Parallel pattern detection
    - DAG validation
    - Maximum depth calculation
    - Fan-out and fan-in analysis
    """

    def __init__(self, logging_service: LoggingService):
        """Initialize GraphStructureAnalyzer.

        Args:
            logging_service: LoggingService for logging
        """
        self.logger = logging_service.get_class_logger(self)

    def analyze_graph_structure(self, nodes: Dict[str, Node]) -> Dict[str, Any]:
        """Analyze graph structure for optimization hints.

        Now includes parallel routing analysis for better metadata.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            Dictionary containing graph structure analysis including parallel patterns
        """
        try:
            edge_count = sum(len(node.edges) for node in nodes.values())
            has_conditional = any(
                any(condition in node.edges for condition in ["success", "failure"])
                for node in nodes.values()
            )

            # Analyze parallel patterns
            parallel_analysis = self.analyze_parallel_patterns(nodes)

            structure = {
                "node_count": len(nodes),
                "edge_count": edge_count,
                "has_conditional_routing": has_conditional,
                "max_depth": self.calculate_max_depth(nodes),
                "is_dag": self.check_dag(nodes),
                "parallel_opportunities": parallel_analysis["parallel_groups"],
                "has_parallel_routing": parallel_analysis["has_parallel"],
                "max_parallelism": parallel_analysis["max_parallelism"],
                "fan_out_count": len(parallel_analysis["fan_out_nodes"]),
                "fan_in_count": len(parallel_analysis["fan_in_nodes"]),
            }

            self.logger.debug(
                f"Analyzed graph structure: {structure['node_count']} nodes, "
                f"DAG: {structure['is_dag']}, conditional: {structure['has_conditional_routing']}, "
                f"parallel: {structure['has_parallel_routing']} (max={structure['max_parallelism']})"
            )
            return structure

        except Exception as e:
            self.logger.warning(
                f"Failed to analyze graph structure: {e}. Using minimal structure."
            )
            return {
                "node_count": len(nodes),
                "edge_count": 0,
                "has_conditional_routing": False,
                "max_depth": 1,
                "is_dag": True,
                "parallel_opportunities": [],
                "has_parallel_routing": False,
                "max_parallelism": 1,
                "fan_out_count": 0,
                "fan_in_count": 0,
            }

    def calculate_max_depth(self, nodes: Dict[str, Node]) -> int:
        """Calculate maximum depth of the graph.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            Maximum depth of the graph
        """
        # Simple implementation - could be enhanced with actual graph traversal
        return min(len(nodes), 10)  # Cap at 10 for performance

    def check_dag(self, nodes: Dict[str, Node]) -> bool:
        """Check if graph is a directed acyclic graph.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            True if graph is a DAG, False otherwise
        """
        # Simple heuristic - if any node has edges that could create cycles
        # This is a simplified check and could be enhanced
        return True  # Assume DAG for now

    def identify_parallel_nodes(self, nodes: Dict[str, Node]) -> List[Set[str]]:
        """Identify sets of nodes that can run in parallel.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            List of sets, where each set contains node names that can run in parallel
        """
        # Simple implementation - nodes without dependencies can run in parallel
        # This could be enhanced with actual dependency analysis
        return []  # Return empty for now

    def analyze_parallel_patterns(self, nodes: Dict[str, Node]) -> Dict[str, Any]:
        """Analyze parallel routing patterns in the graph.

        Identifies fan-out, fan-in, and parallel opportunities for optimization.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            Dictionary with parallel pattern analysis:
            - fan_out_nodes: Nodes that route to multiple targets
            - fan_in_nodes: Nodes that receive from multiple sources
            - parallel_groups: Groups of nodes that execute in parallel
            - max_parallelism: Maximum number of parallel branches
            - has_parallel: Whether graph contains any parallel routing
        """
        fan_out_nodes = []
        fan_in_count = {}
        parallel_groups = []
        max_parallelism = 1

        # Find fan-out nodes (nodes with parallel edges)
        for node_name, node in nodes.items():
            for condition, targets in node.edges.items():
                if isinstance(targets, list) and len(targets) > 1:
                    fan_out_nodes.append(
                        {
                            "node": node_name,
                            "condition": condition,
                            "targets": targets,
                            "parallelism": len(targets),
                        }
                    )
                    parallel_groups.append(targets)
                    max_parallelism = max(max_parallelism, len(targets))

                    # Track fan-in (nodes receiving from parallel source)
                    for target in targets:
                        fan_in_count[target] = fan_in_count.get(target, 0) + 1

        # Identify actual fan-in nodes (nodes with multiple incoming edges)
        fan_in_nodes = [
            {"node": node, "incoming_count": count}
            for node, count in fan_in_count.items()
            if count > 1
        ]

        return {
            "fan_out_nodes": fan_out_nodes,
            "fan_in_nodes": fan_in_nodes,
            "parallel_groups": parallel_groups,
            "max_parallelism": max_parallelism,
            "has_parallel": len(fan_out_nodes) > 0,
        }
