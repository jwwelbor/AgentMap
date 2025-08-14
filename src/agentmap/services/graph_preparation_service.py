"""
GraphPreparationService for AgentMap.

Service responsible for preparing graph definitions for execution by:
- Loading graph definitions from various sources
- Injecting agent instances into graph nodes
- Setting up node registries for orchestration
- Preparing execution-ready graph structures

This service follows the Single Responsibility Principle by handling only
graph preparation concerns, extracted from the larger GraphRunnerService.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from agentmap.services.graph_definition_service import GraphDefinitionService
from agentmap.services.logging_service import LoggingService
from agentmap.services.node_registry_service import NodeRegistryService


class GraphPreparationService:
    """
    Service for preparing graph definitions for execution.

    Handles the conversion of graph definitions into execution-ready format
    with agent instances properly injected and node registries prepared.
    
    This service is responsible for:
    - Loading graph definitions from CSV files
    - Preparing graph definitions with agent instances
    - Setting up node registries for orchestration agents
    - Validating graph preparation results
    """

    def __init__(
        self,
        graph_definition_service: GraphDefinitionService,
        node_registry_service: NodeRegistryService,
        logging_service: LoggingService,
    ):
        """
        Initialize GraphPreparationService with dependencies.

        Args:
            graph_definition_service: Service for loading graph definitions
            node_registry_service: Service for node registry management
            logging_service: Service for logging operations
        """
        self.graph_definition = graph_definition_service
        self.node_registry = node_registry_service
        self.logger = logging_service.get_class_logger(self)
        
        self.logger.info("[GraphPreparationService] Initialized")

    def load_graph_definition_for_execution(
        self, csv_path: Path, graph_name: Optional[str]
    ) -> Tuple[Dict[str, Any], str]:
        """
        Load and prepare graph definition for execution.

        Uses GraphDefinitionService and prepares the definition with agent instances.

        Args:
            csv_path: Path to CSV file
            graph_name: Optional specific graph name to load

        Returns:
            Tuple of (prepared_graph_def, resolved_graph_name)
        """
        self.logger.debug(
            f"[GraphPreparationService] Loading graph definition for execution: {csv_path}"
        )

        # Step 1: Load graph definition using GraphDefinitionService
        if graph_name:
            # Load specific graph
            graph_domain_model = self.graph_definition.build_from_csv(
                csv_path, graph_name
            )
            resolved_graph_name = graph_name
        else:
            # Load first graph available
            all_graphs = self.graph_definition.build_all_from_csv(csv_path)
            if not all_graphs:
                raise ValueError(f"No graphs found in CSV file: {csv_path}")

            resolved_graph_name = next(iter(all_graphs))
            graph_domain_model = all_graphs[resolved_graph_name]

            self.logger.debug(
                f"[GraphPreparationService] Using first graph: {resolved_graph_name}"
            )

        # Step 2: Convert to execution format and prepare with agent instances
        prepared_graph_def = self.prepare_graph_definition(
            graph_domain_model, resolved_graph_name
        )

        return prepared_graph_def, resolved_graph_name

    def prepare_graph_definition(
        self, graph_domain_model: Any, graph_name: str
    ) -> Dict[str, Any]:
        """
        Prepare graph definition with node registry for execution.

        Works directly with Graph domain model without unnecessary conversion.
        Prepares the node registry that will be used by orchestration agents.

        Args:
            graph_domain_model: Graph domain model from GraphDefinitionService
            graph_name: Name of the graph for logging context

        Returns:
            Prepared graph definition ready for agent injection
        """
        self.logger.debug(
            f"[GraphPreparationService] Preparing graph definition for execution: {graph_name}"
        )

        # Work directly with the domain model nodes
        graph_nodes = graph_domain_model.nodes

        if not graph_nodes:
            raise ValueError(
                f"Invalid or empty graph definition for graph: {graph_name}"
            )

        # Prepare node registry for orchestration agents
        self.logger.debug(
            f"[GraphPreparationService] Preparing node registry for: {graph_name}"
        )
        node_registry = self.node_registry.prepare_for_assembly(graph_nodes, graph_name)

        # Store node registry reference for later agent injection
        # This will be used by AgentFactoryService when creating agent instances
        self._last_prepared_node_registry = node_registry

        # Initialize node contexts for agent injection
        for node_name, node in graph_nodes.items():
            if not hasattr(node, 'context') or node.context is None:
                node.context = {}
            # Ensure context is ready for agent instance injection
            node.context.setdefault('preparation_metadata', {
                'graph_name': graph_name,
                'node_registry_prepared': True,
                'prepared_at': None  # Will be set when agents are injected
            })

        self.logger.debug(
            f"[GraphPreparationService] Graph structure prepared, ready for agent injection: {graph_name}"
        )
        return graph_nodes

    def get_last_prepared_node_registry(self) -> Optional[Dict[str, Any]]:
        """
        Get the node registry from the last preparation operation.
        
        This is used by AgentFactoryService during agent creation to inject
        the node registry into orchestration agents.
        
        Returns:
            Node registry dictionary or None if no preparation has occurred
        """
        return getattr(self, '_last_prepared_node_registry', None)
