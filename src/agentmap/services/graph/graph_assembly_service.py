from typing import Any, Callable, Dict, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph

from agentmap.models.graph import Graph
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.graph.graph_factory_service import GraphFactoryService
from agentmap.services.logging_service import LoggingService
from agentmap.services.protocols import (
    OrchestrationCapableAgent,
    ToolSelectionCapableAgent,
)
from agentmap.services.state_adapter_service import StateAdapterService


class GraphAssemblyService:
    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
        state_adapter_service: StateAdapterService,
        features_registry_service: FeaturesRegistryService,
        function_resolution_service: FunctionResolutionService,
        graph_factory_service: GraphFactoryService,
        orchestrator_service: Any,  # OrchestratorService
    ):
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.functions_dir = self.config.get_functions_path()
        self.state_adapter = state_adapter_service
        self.features_registry = features_registry_service
        self.function_resolution = function_resolution_service
        self.graph_factory_service = graph_factory_service
        self.orchestrator_service = orchestrator_service

        # Get state schema from config or default to dict
        state_schema = self._get_state_schema_from_config()
        self.builder = StateGraph(state_schema=state_schema)
        self.orchestrator_nodes = []
        self.orchestrator_node_registry: Optional[Dict[str, Any]] = None
        self.injection_stats = {
            "orchestrators_found": 0,
            "orchestrators_injected": 0,
            "injection_failures": 0,
        }

    def _get_state_schema_from_config(self):
        """
        Get state schema from configuration.

        Returns:
            State schema type (dict, pydantic model, or other LangGraph-compatible schema)
        """
        try:
            execution_config = self.config.get_execution_config()
            state_schema_config = execution_config.get("graph", {}).get(
                "state_schema", "dict"
            )

            if state_schema_config == "dict":
                return dict

            if state_schema_config == "pydantic":
                return self._get_pydantic_schema(execution_config)

            # Unknown schema type
            self.logger.warning(
                f"Unknown state schema type '{state_schema_config}', falling back to dict"
            )
            return dict

        except Exception as e:
            self.logger.debug(
                f"Could not read state schema from config: {e}, using dict"
            )
            return dict

    def _get_pydantic_schema(self, execution_config: Dict[str, Any]):
        """Get pydantic BaseModel schema from configuration."""
        try:
            from pydantic import BaseModel

            model_class = execution_config.get("graph", {}).get("state_model_class")
            # TODO: Implement dynamic model class import when needed
            return BaseModel
        except ImportError:
            self.logger.warning(
                "Pydantic requested but not available, falling back to dict"
            )
            return dict

    def _initialize_builder(self) -> None:
        """Initialize a fresh StateGraph builder and reset orchestrator tracking."""
        state_schema = self._get_state_schema_from_config()
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
            self.logger.debug(f"🚪 Factory detected entry point: '{graph.entry_point}'")
        else:
            self.logger.debug(
                f"🚪 Using pre-existing graph entry point: '{graph.entry_point}'"
            )

    def _process_all_nodes(self, graph: Graph, agent_instances: Dict[str, Any]) -> None:
        """Process all nodes and their edges."""
        node_names = list(graph.nodes.keys())
        self.logger.debug(f"Processing {len(node_names)} nodes: {node_names}")

        for node_name, node in graph.nodes.items():
            if node_name not in agent_instances:
                raise ValueError(f"No agent instance found for node: {node_name}")
            agent_instance = agent_instances[node_name]
            self.add_node(node_name, agent_instance)
            self.process_node_edges(node_name, node.edges)

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
            self._add_dynamic_router(orch_node_name, failure_target)

    def _compile_graph(
        self, graph: Graph, checkpointer: Optional[BaseCheckpointSaver] = None
    ) -> Any:
        """Compile the graph with optional checkpoint support."""
        if checkpointer:
            compiled_graph = self.builder.compile(checkpointer=checkpointer)
            self.logger.debug(
                f"✅ Graph '{graph.name}' compiled with checkpoint support"
            )
        else:
            compiled_graph = self.builder.compile()
            self.logger.debug(f"✅ Graph '{graph.name}' compiled successfully")

        return compiled_graph

    def assemble_graph(
        self,
        graph: Graph,
        agent_instances: Dict[str, Any],
        orchestrator_node_registry: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Assemble an executable LangGraph from a Graph domain model.

        Args:
            graph: Graph domain model with nodes and configuration
            agent_instances: Dictionary mapping node names to agent instances
            orchestrator_node_registry: Optional node registry for orchestrator injection

        Returns:
            Compiled executable graph

        Raises:
            ValueError: If graph has no nodes or missing agent instances
        """
        self.logger.info(f"🚀 Starting graph assembly: '{graph.name}'")
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
        """
        Assemble an executable LangGraph with checkpoint support.

        This method creates a graph with checkpoint capability for pause/resume functionality.

        Args:
            graph: Graph domain model with nodes and configuration
            agent_instances: Dictionary mapping node names to agent instances
            node_definitions: Optional node registry for orchestrator injection
            checkpointer: Checkpoint service for state persistence

        Returns:
            Compiled executable graph with checkpoint support

        Raises:
            ValueError: If graph has no nodes or missing agent instances
        """
        self.logger.info(
            f"🚀 Starting checkpoint-enabled graph assembly: '{graph.name}'"
        )
        return self._assemble_graph_common(
            graph, agent_instances, node_definitions, checkpointer
        )

    def _assemble_graph_common(
        self,
        graph: Graph,
        agent_instances: Dict[str, Any],
        orchestrator_node_registry: Optional[Dict[str, Any]],
        checkpointer: Optional[BaseCheckpointSaver],
    ) -> Any:
        """Common assembly logic for both standard and checkpoint-enabled graphs."""
        self._validate_graph(graph)
        self._initialize_builder()

        self.orchestrator_node_registry = orchestrator_node_registry

        self._ensure_entry_point(graph)
        self._process_all_nodes(graph, agent_instances)

        # Set entry point
        if graph.entry_point:
            self.builder.set_entry_point(graph.entry_point)
            self.logger.debug(f"🚪 Set entry point: '{graph.entry_point}'")

        self._add_orchestrator_routers(graph)

        return self._compile_graph(graph, checkpointer)

    def add_node(self, name: str, agent_instance: Any) -> None:
        """
        Add a node to the graph with its agent instance.

        Args:
            name: Node name
            agent_instance: Agent instance with run method
        """
        self.builder.add_node(name, agent_instance.run)
        class_name = agent_instance.__class__.__name__

        # Only orchestrator agents (not tool selection agents) get dynamic routing
        # OrchestrationCapableAgent has node_registry for dynamic routing
        # ToolSelectionCapableAgent uses orchestrator service for tool selection but uses conditional routing
        if isinstance(agent_instance, OrchestrationCapableAgent) and hasattr(
            agent_instance, "node_registry"
        ):
            self.orchestrator_nodes.append(name)
            self.injection_stats["orchestrators_found"] += 1
            try:
                # Configure orchestrator service (always available)
                agent_instance.configure_orchestrator_service(self.orchestrator_service)

                # Configure node registry if available
                if self.orchestrator_node_registry:
                    agent_instance.node_registry = self.orchestrator_node_registry
                    self.logger.debug(
                        f"✅ Injected orchestrator service and node registry into '{name}'"
                    )
                else:
                    self.logger.debug(
                        f"✅ Injected orchestrator service into '{name}' (no node registry available)"
                    )

                self.injection_stats["orchestrators_injected"] += 1
            except Exception as e:
                self.injection_stats["injection_failures"] += 1
                error_msg = f"Failed to inject orchestrator service into '{name}': {e}"
                self.logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg) from e

        self.logger.debug(f"🔹 Added node: '{name}' ({class_name})")

    def process_node_edges(self, node_name: str, edges: Dict[str, str]) -> None:
        """
        Process edges for a node and add them to the graph.

        Args:
            node_name: Source node name
            edges: Dictionary of edge conditions to target nodes
        """
        # Orchestrator nodes use dynamic routing - only log failure edges
        if node_name in self.orchestrator_nodes:
            if edges and "failure" in edges:
                self.logger.debug(
                    f"Adding failure edge for orchestrator '{node_name}' → {edges['failure']}"
                )
            return

        if not edges:
            return

        self.logger.debug(
            f"Processing edges for node '{node_name}': {list(edges.keys())}"
        )

        # Check for function-based routing first
        if self._try_add_function_edge(node_name, edges):
            return

        # Handle standard edge types
        self._add_standard_edges(node_name, edges)

    def _try_add_function_edge(self, node_name: str, edges: Dict[str, str]) -> bool:
        """
        Try to add function-based routing edge.

        Returns:
            True if function edge was added, False otherwise
        """
        for target in edges.values():
            func_ref = self.function_resolution.extract_func_ref(target)
            if func_ref:
                success = edges.get("success")
                failure = edges.get("failure")
                self._add_function_edge(node_name, func_ref, success, failure)
                return True
        return False

    def _add_standard_edges(self, node_name: str, edges: Dict[str, str]) -> None:
        """Add standard edge types (success/failure/default)."""
        has_success = "success" in edges
        has_failure = "failure" in edges

        if has_success and has_failure:
            self._add_success_failure_edge(
                node_name, edges["success"], edges["failure"]
            )
        elif has_success:
            self._add_conditional_edge(
                node_name,
                lambda state: (
                    edges["success"] if state.get("last_action_success", True) else None
                ),
            )
        elif has_failure:
            self._add_conditional_edge(
                node_name,
                lambda state: (
                    edges["failure"]
                    if not state.get("last_action_success", True)
                    else None
                ),
            )
        elif "default" in edges:
            self.builder.add_edge(node_name, edges["default"])
            self.logger.debug(f"[{node_name}] → default → {edges['default']}")

    def _add_conditional_edge(self, source: str, func: Callable) -> None:
        """Add a conditional edge to the graph."""
        self.builder.add_conditional_edges(source, func)
        self.logger.debug(f"[{source}] → conditional edge added")

    def _add_success_failure_edge(
        self, source: str, success: str, failure: str
    ) -> None:
        """Add success/failure conditional edges."""

        def branch(state):
            return success if state.get("last_action_success", True) else failure

        self.builder.add_conditional_edges(source, branch)
        self.logger.debug(f"[{source}] → success → {success} / failure → {failure}")

    def _add_function_edge(
        self,
        source: str,
        func_name: str,
        success: Optional[str],
        failure: Optional[str],
    ) -> None:
        """Add function-based routing edge."""
        func = self.function_resolution.load_function(func_name)

        def wrapped(state):
            return func(state, success, failure)

        self.builder.add_conditional_edges(source, wrapped)
        self.logger.debug(f"[{source}] → routed by function '{func_name}'")

    def _add_dynamic_router(
        self, node_name: str, failure_target: Optional[str] = None
    ) -> None:
        """Add dynamic routing for orchestrator nodes.

        Args:
            node_name: Name of the orchestrator node
            failure_target: Optional failure target node
        """
        self.logger.debug(f"[{node_name}] → adding dynamic router for orchestrator")
        if failure_target:
            self.logger.debug(f"  Failure target: {failure_target}")

        def dynamic_router(state):
            # Check for failure first (early return pattern)
            if failure_target:
                last_success = self.state_adapter.get_value(
                    state, "last_action_success", True
                )
                if not last_success:
                    self.logger.debug(
                        f"Orchestrator '{node_name}' routing to failure: {failure_target}"
                    )
                    return failure_target

            # Check for dynamic next_node
            next_node = self.state_adapter.get_value(state, "__next_node")
            if not next_node:
                return None

            # Clear __next_node and route to it
            self.state_adapter.set_value(state, "__next_node", None)
            self.logger.debug(f"Orchestrator '{node_name}' routing to: {next_node}")
            return next_node

        # Allow orchestrator to route to any node (including runtime-provided nodes)
        self.builder.add_conditional_edges(node_name, dynamic_router, path_map=None)
        self.logger.debug(f"[{node_name}] → dynamic router added with open routing")

    def get_injection_summary(self) -> Dict[str, int]:
        """Get summary of registry injection statistics."""
        return self.injection_stats.copy()
