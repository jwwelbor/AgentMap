"""
GraphDefinitionService - REFACTORED to eliminate duplication.

This shows the AFTER state using GraphFactoryService to eliminate
graph creation and entry point detection duplication.
"""

from pathlib import Path
from typing import Dict, List, Optional

from agentmap.exceptions.graph_exceptions import InvalidEdgeDefinitionError
from agentmap.models.graph import Graph
from agentmap.models.graph_spec import GraphSpec, NodeSpec
from agentmap.models.node import Node
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.csv_graph_parser_service import CSVGraphParserService
from agentmap.services.graph_factory_service import GraphFactoryService
from agentmap.services.logging_service import LoggingService


class GraphDefinitionService:
    """
    Service for building Graph domain models from various sources.

    REFACTORED: Now uses GraphFactoryService to eliminate duplication of:
    - Graph object creation and node population
    - Entry point detection logic
    - Graph name resolution
    """

    def __init__(
        self,
        logging_service: LoggingService,
        app_config_service: AppConfigService,
        csv_parser: CSVGraphParserService,
        graph_factory: GraphFactoryService,  # NEW: Injected factory
    ):
        """Initialize service with dependency injection."""
        self.logger = logging_service.get_class_logger(self)
        self.config = app_config_service
        self.csv_parser = csv_parser
        self.graph_factory = graph_factory  # NEW: Factory dependency
        self.logger.info("[GraphDefinitionService] Initialized")

    def build_from_csv(self, csv_path: Path, graph_name: Optional[str] = None) -> Graph:
        """
        Build single graph from CSV file.

        Args:
            csv_path: Path to CSV file containing graph definitions
            graph_name: Specific graph name to extract (returns first graph if None)

        Returns:
            Graph domain model for the specified or first graph found

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If specified graph_name not found in CSV
        """
        self.logger.info(
            f"[GraphDefinitionService] Building single graph from: {csv_path}"
        )

        # Build all graphs first
        all_graphs = self.build_all_from_csv(csv_path)

        if not all_graphs:
            raise ValueError(f"No graphs found in CSV file: {csv_path}")

        # Return specific graph if requested
        if graph_name:
            if graph_name not in all_graphs:
                available_graphs = list(all_graphs.keys())
                raise ValueError(
                    f"Graph '{graph_name}' not found in CSV. "
                    f"Available graphs: {available_graphs}"
                )
            return all_graphs[graph_name]

        # Return first graph if no specific name requested
        first_graph_name = next(iter(all_graphs))
        self.logger.info(
            f"[GraphDefinitionService] Returning first graph: {first_graph_name}"
        )
        return all_graphs[first_graph_name]

    def build_all_from_csv(self, csv_path: Path) -> Dict[str, Graph]:
        """
        Build all graphs found in CSV file.

        Args:
            csv_path: Path to CSV file containing graph definitions

        Returns:
            Dictionary mapping graph names to Graph domain models

        Raises:
            FileNotFoundError: If CSV file doesn't exist
        """
        csv_path = Path(csv_path)
        self.logger.info(
            f"[GraphDefinitionService] Building all graphs from: {csv_path}"
        )

        # Step 1: Parse CSV to GraphSpec using injected parser
        graph_spec = self.csv_parser.parse_csv_to_graph_spec(csv_path)

        # Step 2: Convert GraphSpec to Graph domain models
        domain_graphs = self.build_from_graph_spec(graph_spec)

        self.logger.info(
            f"[GraphDefinitionService] Successfully built {len(domain_graphs)} graph(s): "
            f"{list(domain_graphs.keys())}"
        )

        return domain_graphs

    def build_from_graph_spec(self, graph_spec: GraphSpec) -> Dict[str, Graph]:
        """
        Build Graph domain models from GraphSpec.

        Args:
            graph_spec: Parsed graph specification from CSV or other source

        Returns:
            Dictionary mapping graph names to Graph domain models
        """
        self.logger.info(f"[GraphDefinitionService] Building graphs from GraphSpec")

        domain_graphs = {}

        for graph_name in graph_spec.get_graph_names():
            node_specs = graph_spec.get_nodes_for_graph(graph_name)

            # Step 1: Create nodes from specs
            nodes_dict = self._create_nodes_from_specs(node_specs, graph_name)

            # Step 2: Connect nodes with edges
            self._connect_nodes_from_specs(nodes_dict, node_specs, graph_name)

            # Step 3: Convert to Graph domain model using factory
            # REFACTORED: Replace duplicated graph creation with factory call
            graph = self.graph_factory.create_graph_from_nodes(graph_name, nodes_dict)

            domain_graphs[graph_name] = graph

            self.logger.debug(
                f"Built graph '{graph_name}' with {len(nodes_dict)} nodes. "
                f"Entry point: {graph.entry_point}"
            )

        return domain_graphs

    def build_graph_from_csv(
        self, csv_path: Path, graph_name: Optional[str] = None
    ) -> Graph:
        """
        Build graph from CSV file (alias for build_from_csv for backward compatibility).

        Args:
            csv_path: Path to CSV file containing graph definitions
            graph_name: Specific graph name to extract (returns first graph if None)

        Returns:
            Graph domain model for the specified or first graph found
        """
        return self.build_from_csv(csv_path, graph_name)

    def build_from_config(self, config_dict: Dict) -> Graph:
        """
        Build graph from configuration dictionary.

        Future extensibility method for building graphs from programmatic config.

        Args:
            config_dict: Dictionary containing graph configuration

        Returns:
            Graph domain model

        Raises:
            NotImplementedError: This method is not yet implemented
        """
        self.logger.info(f"[GraphDefinitionService] Building graph from config")
        # TODO: Implement when needed for configuration-based graph building
        raise NotImplementedError("build_from_config not yet implemented")

    def validate_csv_before_building(self, csv_path: Path) -> List[str]:
        """
        Pre-validate CSV structure and content.

        Args:
            csv_path: Path to CSV file to validate

        Returns:
            List of validation errors (empty if valid)
        """
        self.logger.info(f"[GraphDefinitionService] Validating CSV: {csv_path}")

        # Use the injected CSV parser for validation
        validation_result = self.csv_parser.validate_csv_structure(csv_path)

        errors = []

        # Convert ValidationResult to simple error list for backward compatibility
        if not validation_result.is_valid:
            for issue in validation_result.errors:
                errors.append(str(issue))

        # Add warnings as informational errors
        for warning in validation_result.warnings:
            errors.append(f"Warning: {warning}")

        return errors

    def _create_nodes_from_specs(
        self, node_specs: List[NodeSpec], graph_name: str
    ) -> Dict[str, Node]:
        """
        Create Node domain models from NodeSpec specifications.

        Args:
            node_specs: List of node specifications
            graph_name: Name of the graph being built

        Returns:
            Dictionary mapping node names to Node domain models
        """
        nodes_dict = {}

        for node_spec in node_specs:
            self.logger.debug(
                f"[GraphDefinitionService] Creating node: '{node_spec.name}' "
                f"in graph '{graph_name}'"
            )

            # Only create if not already exists (handle duplicate definitions)
            if node_spec.name not in nodes_dict:
                # Convert context string to dict if needed (preserve existing logic)
                context_dict = (
                    {"context": node_spec.context} if node_spec.context else None
                )

                # Use default agent type if not specified
                agent_type = node_spec.agent_type or "Default"

                nodes_dict[node_spec.name] = Node(
                    name=node_spec.name,
                    context=context_dict,
                    agent_type=agent_type,
                    inputs=node_spec.input_fields,
                    output=node_spec.output_field,
                    prompt=node_spec.prompt,
                    description=node_spec.description,
                )

                self.logger.debug(
                    f"  ➕ Created Node: {node_spec.name} with agent_type: {agent_type}, "
                    f"output_field: {node_spec.output_field}"
                )
            else:
                self.logger.debug(
                    f"  ⏩ Node {node_spec.name} already exists, skipping creation"
                )

        return nodes_dict

    def _connect_nodes_from_specs(
        self, nodes_dict: Dict[str, Node], node_specs: List[NodeSpec], graph_name: str
    ) -> None:
        """
        Connect nodes with edges based on NodeSpec specifications.

        Args:
            nodes_dict: Dictionary of created nodes
            node_specs: List of node specifications with edge information
            graph_name: Name of the graph being built
        """
        for node_spec in node_specs:
            node_name = node_spec.name

            # Check for conflicting edge definitions
            if node_spec.edge and (node_spec.success_next or node_spec.failure_next):
                self.logger.debug(
                    f"  ⚠️ CONFLICT: Node '{node_name}' has both Edge and Success/Failure defined!"
                )
                raise InvalidEdgeDefinitionError(
                    f"Node '{node_name}' has both Edge and Success/Failure defined. "
                    f"Please use either Edge OR Success/Failure_Next, not both."
                )

            # Connect with direct edge
            if node_spec.edge:
                self._connect_direct_edge(
                    nodes_dict, node_name, node_spec.edge, graph_name
                )

            # Connect with conditional edges
            elif node_spec.success_next or node_spec.failure_next:
                if node_spec.success_next:
                    self._connect_success_edge(
                        nodes_dict, node_name, node_spec.success_next, graph_name
                    )

                if node_spec.failure_next:
                    self._connect_failure_edge(
                        nodes_dict, node_name, node_spec.failure_next, graph_name
                    )

    def _connect_direct_edge(
        self,
        nodes_dict: Dict[str, Node],
        source_node: str,
        target_node: str,
        graph_name: str,
    ) -> None:
        """Connect nodes with a direct edge."""
        # Verify the edge target exists
        if target_node not in nodes_dict:
            self.logger.error(
                f"  ❌ Edge target '{target_node}' not defined in graph '{graph_name}'"
            )
            raise ValueError(
                f"Edge target '{target_node}' is not defined as a node in graph '{graph_name}'"
            )

        nodes_dict[source_node].add_edge("default", target_node)
        self.logger.debug(f"  🔗 {source_node} --default--> {target_node}")

    def _connect_success_edge(
        self,
        nodes_dict: Dict[str, Node],
        source_node: str,
        target_node: str,
        graph_name: str,
    ) -> None:
        """Connect nodes with a success edge."""
        # Verify the success target exists
        if target_node not in nodes_dict:
            self.logger.error(
                f"  ❌ Success target '{target_node}' not defined in graph '{graph_name}'"
            )
            raise ValueError(
                f"Success target '{target_node}' is not defined as a node in graph '{graph_name}'"
            )

        nodes_dict[source_node].add_edge("success", target_node)
        self.logger.debug(f"  🔗 {source_node} --success--> {target_node}")

    def _connect_failure_edge(
        self,
        nodes_dict: Dict[str, Node],
        source_node: str,
        target_node: str,
        graph_name: str,
    ) -> None:
        """Connect nodes with a failure edge."""
        # Verify the failure target exists
        if target_node not in nodes_dict:
            self.logger.error(
                f"  ❌ Failure target '{target_node}' not defined in graph '{graph_name}'"
            )
            raise ValueError(
                f"Failure target '{target_node}' is not defined as a node in graph '{graph_name}'"
            )

        nodes_dict[source_node].add_edge("failure", target_node)
        self.logger.debug(f"  🔗 {source_node} --failure--> {target_node}")

    # REMOVED: _convert_to_graph_domain_model() - replaced by graph_factory.create_graph_from_nodes()
    # REMOVED: _detect_entry_point() - replaced by graph_factory.detect_entry_point()
