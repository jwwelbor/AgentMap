"""
Graph assembly service for building LangGraph executable graphs.

This module provides the main GraphAssemblyService class that orchestrates
the assembly of LangGraph StateGraph instances from Graph domain models.
"""

from typing import Any, Dict, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph

from agentmap.models.graph import Graph
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.graph.edge_processor import EdgeProcessor
from agentmap.services.graph.graph_factory_service import GraphFactoryService
from agentmap.services.graph.state_schema_builder import StateSchemaBuilder
from agentmap.services.logging_service import LoggingService
from agentmap.services.protocols import OrchestrationCapableAgent
from agentmap.services.state_adapter_service import StateAdapterService


class GraphAssemblyService:
    """Assembles executable LangGraph graphs from Graph domain models."""

    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
        state_adapter_service: StateAdapterService,
        features_registry_service: FeaturesRegistryService,
        function_resolution_service: FunctionResolutionService,
        graph_factory_service: GraphFactoryService,
        orchestrator_service: Any,
    ):
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.functions_dir = self.config.get_functions_path()
        self.state_adapter = state_adapter_service
        self.features_registry = features_registry_service
        self.function_resolution = function_resolution_service
        self.graph_factory_service = graph_factory_service
        self.orchestrator_service = orchestrator_service

        # Initialize helper services
        self.state_schema_builder = StateSchemaBuilder(app_config_service, logging_service)
        self.edge_processor = EdgeProcessor(
            logging_service, function_resolution_service, state_adapter_service
        )

        state_schema = self.state_schema_builder.get_state_schema_from_config()
        self.builder = StateGraph(state_schema=state_schema)
        self.orchestrator_nodes: list = []
        self.orchestrator_node_registry: Optional[Dict[str, Any]] = None
        self.injection_stats = {
            "orchestrators_found": 0,
            "orchestrators_injected": 0,
            "injection_failures": 0,
        }

    def _initialize_builder(self, graph: Optional[Graph] = None) -> None:
        """Initialize a fresh StateGraph builder and reset orchestrator tracking."""
        state_schema = self.state_schema_builder.get_schema_for_graph(graph)
        self.builder = StateGraph(state_schema=state_schema)
        self.orchestrator_nodes = []
        self.injection_stats = {
            "orchestrators_found": 0,
            "orchestrators_injected": 0,
            "injection_failures": 0,
        }

    def _validate_graph(self, graph: Graph) -> None:
        """Validate graph has nodes."""
        if not graph.nodes:
            raise ValueError(f"Graph '{graph.name}' has no nodes")

    def _ensure_entry_point(self, graph: Graph) -> None:
        """Ensure graph has an entry point, detecting one if needed."""
        if not graph.entry_point:
            graph.entry_point = self.graph_factory_service.detect_entry_point(graph)
            self.logger.debug(f"Factory detected entry point: '{graph.entry_point}'")
        else:
            self.logger.debug(f"Using pre-existing graph entry point: '{graph.entry_point}'")

    def _process_all_nodes(self, graph: Graph, agent_instances: Dict[str, Any]) -> None:
        """Process all nodes and their edges."""
        node_names = list(graph.nodes.keys())
        self.logger.debug(f"Processing {len(node_names)} nodes: {node_names}")

        for node_name, node in graph.nodes.items():
            if node_name not in agent_instances:
                raise ValueError(f"No agent instance found for node: {node_name}")
            agent_instance = agent_instances[node_name]
            self.add_node(node_name, agent_instance)
            self.edge_processor.process_node_edges(
                self.builder, node_name, node.edges, self.orchestrator_nodes
            )

    def _add_orchestrator_routers(self, graph: Graph) -> None:
        """Add dynamic routers for all orchestrator nodes."""
        if not self.orchestrator_nodes:
            return

        self.logger.debug(
            f"Adding dynamic routers for {len(self.orchestrator_nodes)} orchestrator nodes"
        )
        for orch_node_name in self.orchestrator_nodes:
            node = graph.nodes.get(orch_node_name)
            failure_target = node.edges.get("failure") if node else None
            self.edge_processor.add_dynamic_router(self.builder, orch_node_name, failure_target)

    def _compile_graph(
        self, graph: Graph, checkpointer: Optional[BaseCheckpointSaver] = None
    ) -> Any:
        """Compile the graph with optional checkpoint support."""
        if checkpointer:
            compiled_graph = self.builder.compile(checkpointer=checkpointer)
            self.logger.debug(f"Graph '{graph.name}' compiled with checkpoint support")
        else:
            compiled_graph = self.builder.compile()
            self.logger.debug(f"Graph '{graph.name}' compiled successfully")
        return compiled_graph

    def assemble_graph(
        self,
        graph: Graph,
        agent_instances: Dict[str, Any],
        orchestrator_node_registry: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Assemble an executable LangGraph from a Graph domain model."""
        self.logger.info(f"Starting graph assembly: '{graph.name}'")
        return self._assemble_graph_common(
            graph, agent_instances, orchestrator_node_registry, checkpointer=None
        )

    def assemble_with_checkpoint(
        self,
        graph: Graph,
        agent_instances: Dict[str, Any],
        node_definitions: Optional[Dict[str, Any]] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ) -> Any:
        """Assemble an executable LangGraph with checkpoint support."""
        self.logger.info(f"Starting checkpoint-enabled graph assembly: '{graph.name}'")
        return self._assemble_graph_common(graph, agent_instances, node_definitions, checkpointer)

    def _assemble_graph_common(
        self,
        graph: Graph,
        agent_instances: Dict[str, Any],
        orchestrator_node_registry: Optional[Dict[str, Any]],
        checkpointer: Optional[BaseCheckpointSaver],
    ) -> Any:
        """Common assembly logic for both standard and checkpoint-enabled graphs."""
        self._validate_graph(graph)
        self._initialize_builder(graph)
        self.orchestrator_node_registry = orchestrator_node_registry
        self._ensure_entry_point(graph)
        self._process_all_nodes(graph, agent_instances)

        if graph.entry_point:
            self.builder.set_entry_point(graph.entry_point)
            self.logger.debug(f"Set entry point: '{graph.entry_point}'")

        self._add_orchestrator_routers(graph)
        return self._compile_graph(graph, checkpointer)

    def add_node(self, name: str, agent_instance: Any) -> None:
        """Add a node to the graph with its agent instance."""
        self.builder.add_node(name, agent_instance.run)
        class_name = agent_instance.__class__.__name__

        if isinstance(agent_instance, OrchestrationCapableAgent) and hasattr(
            agent_instance, "node_registry"
        ):
            self.orchestrator_nodes.append(name)
            self.injection_stats["orchestrators_found"] += 1
            try:
                agent_instance.configure_orchestrator_service(self.orchestrator_service)
                if self.orchestrator_node_registry:
                    agent_instance.node_registry = self.orchestrator_node_registry
                    self.logger.debug(
                        f"Injected orchestrator service and node registry into '{name}'"
                    )
                else:
                    self.logger.debug(
                        f"Injected orchestrator service into '{name}' (no node registry available)"
                    )
                self.injection_stats["orchestrators_injected"] += 1
            except Exception as e:
                self.injection_stats["injection_failures"] += 1
                error_msg = f"Failed to inject orchestrator service into '{name}': {e}"
                self.logger.error(f"{error_msg}")
                raise ValueError(error_msg) from e

        self.logger.debug(f"Added node: '{name}' ({class_name})")

    def get_injection_summary(self) -> Dict[str, int]:
        """Get summary of registry injection statistics."""
        return self.injection_stats.copy()

    def _add_dynamic_router(
        self, node_name: str, failure_target: Optional[str] = None
    ) -> None:
        """Add dynamic routing for orchestrator nodes (backwards compatibility)."""
        self.edge_processor.add_dynamic_router(self.builder, node_name, failure_target)
