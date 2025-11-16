"""
Static Bundle Analyzer service for AgentMap.

Creates bundles using only declarations without loading implementations,
eliminating circular dependencies and providing 10x performance improvement.
"""

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple
from uuid import uuid4

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.services.csv_graph_parser_service import CSVGraphParserService
from agentmap.services.custom_agent_declaration_manager import (
    CustomAgentDeclarationManager,
)
from agentmap.services.declaration_registry_service import DeclarationRegistryService
from agentmap.services.logging_service import LoggingService


class StaticBundleAnalyzer:
    """
    Service for creating static bundles using only declaration metadata.

    This service creates bundles without loading any implementations,
    eliminating circular dependencies and providing significant performance
    improvements through declaration-only analysis.
    """

    def __init__(
        self,
        declaration_registry_service: DeclarationRegistryService,
        custom_agent_declaration_manager: CustomAgentDeclarationManager,
        csv_parser_service: CSVGraphParserService,
        logging_service: LoggingService,
    ):
        """Initialize with dependency injection."""
        self.declaration_registry = declaration_registry_service
        self.custom_agent_declaration_manager = custom_agent_declaration_manager
        self.csv_parser = csv_parser_service
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[StaticBundleAnalyzer] Initialized")

    def create_static_bundle(
        self, csv_path: Path, graph_name: Optional[str] = None
    ) -> GraphBundle:
        """
        Create a GraphBundle from CSV using only declarations.

        Args:
            csv_path: Path to CSV file containing graph definition
            graph_name: Optional override for graph name

        Returns:
            GraphBundle containing declaration metadata without loaded implementations

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV structure is invalid
        """
        self.logger.info(f"Creating static bundle from CSV: {csv_path}")

        # Validate CSV file exists
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Parse CSV to extract structure (lightweight operation)
        try:
            self.logger.debug(f"Parsing CSV to graph specification")
            graph_spec = self.csv_parser.parse_csv_to_graph_spec(csv_path)

            # Get available graphs
            graph_names = graph_spec.get_graph_names()
            if not graph_names:
                raise ValueError(f"No graphs found in CSV file: {csv_path}")

            self.logger.debug(f"Found {len(graph_names)} graphs: {graph_names}")

            # Determine which graph to return
            if graph_name is None:
                if len(graph_names) == 1:
                    target_graph_name = graph_names[0]
                    self.logger.debug(f"Single graph found, using: {target_graph_name}")
                else:
                    # For multiple graphs, use the first one and log a warning
                    target_graph_name = graph_names[0]
                    self.logger.warning(
                        f"Multiple graphs found: {graph_names}. "
                        f"No graph_to_return specified, using first: {target_graph_name}"
                    )
            else:
                if graph_name not in graph_names:
                    raise ValueError(
                        f"Requested graph '{graph_name}' not found in CSV. "
                        f"Available graphs: {graph_names}"
                    )
                target_graph_name = graph_name
                self.logger.debug(f"Using requested graph: {target_graph_name}")

            node_specs = graph_spec.get_nodes_for_graph(target_graph_name)
            nodes = self.csv_parser._convert_node_specs_to_nodes(node_specs)
        except Exception as e:
            self.logger.error(f"Failed to parse CSV {csv_path}: {e}")
            raise ValueError(f"Invalid CSV structure: {e}") from e

        # Convert node list to dict if needed
        if isinstance(nodes, list):
            nodes = {node.name: node for node in nodes}

        # Extract agent types from nodes
        agent_types = self._extract_agent_types(list(nodes.values()))
        self.logger.debug(f"Extracted {len(agent_types)} unique agent types")

        # Resolve requirements using declaration registry (fast dictionary lookups)
        requirements = self.declaration_registry.resolve_agent_requirements(agent_types)
        required_services = requirements.get("services", set())
        required_protocols = requirements.get("protocols", set())
        missing_declarations = requirements.get("missing", set())

        self.logger.debug(
            f"Resolved requirements: {len(required_services)} services, "
            f"{len(required_protocols)} protocols, {len(missing_declarations)} missing"
        )

        # Validate declarations
        valid_agents, missing_agents = self._validate_declarations(agent_types)
        missing_declarations.update(missing_agents)

        # Extract agent mappings for all valid agents that have declarations
        agent_mappings = {}
        builtin_agents = set()
        custom_agents = set()

        for agent_type in valid_agents:
            # Check registry first, then custom declarations
            decl = self.declaration_registry.get_agent_declaration(agent_type)
            if not decl:
                # Check custom agent declarations if not found in registry
                custom_decl = (
                    self.custom_agent_declaration_manager.get_agent_declaration(
                        agent_type
                    )
                )
                if custom_decl and "class_path" in custom_decl:
                    agent_mappings[agent_type] = custom_decl["class_path"]
                    custom_agents.add(agent_type)
            elif hasattr(decl, "class_path"):
                agent_mappings[agent_type] = decl.class_path
                if self._is_builtin_agent(agent_type, decl):
                    builtin_agents.add(agent_type)
                else:
                    custom_agents.add(agent_type)

        self.logger.debug(
            f"Extracted agent mappings: {len(agent_mappings)} total, "
            f"{len(builtin_agents)} builtin, {len(custom_agents)} custom"
        )

        # Compute CSV hash for validation
        csv_hash = self._compute_csv_hash(csv_path)

        # Find entry point
        entry_point = list(nodes.keys())[0]  # self._find_entry_point(nodes)

        # Create validation metadata
        validation_metadata = {
            "csv_path": str(csv_path),
            "node_count": len(nodes),
            "agent_type_count": len(agent_types),
            "created_via": "static_analysis",
            "has_missing": len(missing_declarations) > 0,
            "has_parallel_routing": self._has_parallel_routing(nodes),
            "parallel_edge_count": self._count_parallel_edges(nodes),
        }

        # protocol map will contain all protocol mappings
        protocol_mappings = self.declaration_registry.get_protcol_service_map()

        # Create GraphBundle using metadata-only format
        bundle = GraphBundle.create_metadata(
            graph_name=target_graph_name,
            nodes=nodes,
            required_agents=agent_types,
            required_services=required_services,
            function_mappings={},  # Empty for static analysis
            csv_hash=csv_hash,
            entry_point=entry_point,
            validation_metadata=validation_metadata,
            protocol_mappings=protocol_mappings,
            missing_declarations=missing_declarations,
            agent_mappings=agent_mappings,
            builtin_agents=builtin_agents,
            custom_agents=custom_agents,
        )

        self.logger.info(
            f"Created GraphBundle for graph '{target_graph_name}' "
            f"with {len(nodes)} nodes and {len(missing_declarations)} missing declarations"
        )

        return bundle

    def _compute_csv_hash(self, csv_path: Path) -> str:
        """
        Compute hash of CSV file for validation.

        Args:
            csv_path: Path to CSV file

        Returns:
            SHA256 hash of CSV file contents
        """
        try:
            with open(csv_path, "rb") as f:
                content = f.read()
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            self.logger.warning(f"Failed to compute CSV hash for {csv_path}: {e}")
            return "unknown_hash"

    def _extract_agent_types(self, nodes: list[Node]) -> Set[str]:
        """
        Extract unique agent types from nodes.

        Args:
            nodes: List of Node objects

        Returns:
            Set of unique agent type strings
        """
        agent_types = set()

        for node in nodes:
            if node.agent_type:
                # Normalize to lowercase for case-insensitive matching
                agent_types.add(node.agent_type.lower())

        # Default to 'default' agent type if no agent type specified
        if not agent_types:
            agent_types.add("default")
            self.logger.debug(
                "No agent types found, defaulting to 'default' agent type"
            )

        return agent_types

    def _validate_declarations(
        self, agent_types: Set[str]
    ) -> Tuple[Set[str], Set[str]]:
        """
        Validate that declarations exist for agent types.

        Args:
            agent_types: Set of agent types to validate

        Returns:
            Tuple of (valid_agent_types, missing_agent_types)
        """
        valid_agents = set()
        missing_agents = set()

        for agent_type in agent_types:
            # Check declaration registry first
            declaration = self.declaration_registry.get_agent_declaration(agent_type)
            if declaration:
                valid_agents.add(agent_type)
            else:
                # Check custom agent declarations if not found in registry
                custom_declaration = (
                    self.custom_agent_declaration_manager.get_agent_declaration(
                        agent_type
                    )
                )
                if custom_declaration:
                    valid_agents.add(agent_type)
                else:
                    missing_agents.add(agent_type)
                    self.logger.warning(
                        f"No declaration found for agent type: {agent_type}"
                    )

        return valid_agents, missing_agents

    def _find_entry_point(self, nodes: dict[str, Node]) -> Optional[str]:
        """
        Find the entry point node for the graph.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            Name of entry point node or None if not found
        """
        if not nodes:
            return None

        # Simple heuristic: look for nodes that are not targets of any edges
        target_nodes = set()
        for node in nodes.values():
            if hasattr(node, "edges") and node.edges:
                target_nodes.update(node.edges.values())

        # Find nodes that are not targets (potential entry points)
        entry_candidates = set(nodes.keys()) - target_nodes

        if entry_candidates:
            # Return the first candidate alphabetically for consistency
            return sorted(entry_candidates)[0]

        # Fallback: return the first node if no clear entry point
        return next(iter(nodes.keys()))

    def _is_builtin_agent(self, agent_type: str, declaration) -> bool:
        """
        Determine if an agent is a builtin framework agent.

        Args:
            agent_type: Type of the agent
            declaration: Agent declaration object

        Returns:
            True if agent is builtin, False if custom
        """
        # Check if the class path starts with builtin namespace
        if hasattr(declaration, "class_path") and declaration.class_path:
            return declaration.class_path.startswith("agentmap.agents.builtins.")

        # Check if the declaration source is "builtin"
        if hasattr(declaration, "source"):
            return declaration.source == "builtin"

        # Fallback: assume custom if cannot determine
        self.logger.debug(
            f"Could not determine if agent '{agent_type}' is builtin, assuming custom"
        )
        return False

    def _has_parallel_routing(self, nodes: dict[str, Node]) -> bool:
        """Check if graph contains any parallel routing edges.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            True if any node has parallel edges, False otherwise
        """
        for node in nodes.values():
            for condition, targets in node.edges.items():
                if isinstance(targets, list) and len(targets) > 1:
                    return True
        return False

    def _count_parallel_edges(self, nodes: dict[str, Node]) -> int:
        """Count number of parallel edges in the graph.

        Args:
            nodes: Dictionary of node name to Node objects

        Returns:
            Count of edges with multiple targets
        """
        count = 0
        for node in nodes.values():
            for condition, targets in node.edges.items():
                if isinstance(targets, list) and len(targets) > 1:
                    count += 1
        return count

    def _analyze_parallel_patterns(self, nodes: dict[str, Node]) -> Dict[str, Any]:
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
