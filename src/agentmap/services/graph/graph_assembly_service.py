from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, Union

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

    def _create_dynamic_state_schema(self, graph: Graph) -> type:
        """
        Create a TypedDict state schema dynamically from graph structure.

        This enables parallel node execution by allowing LangGraph to track
        individual state fields independently. Without this, concurrent updates
        to a plain dict state schema cause InvalidUpdateError.

        Args:
            graph: Graph domain model with nodes

        Returns:
            TypedDict class with fields for all node outputs
        """
        # Collect all input and output fields from nodes
        field_names = set()
        for node in graph.nodes.values():
            # Add output field
            if node.output:
                field_names.add(node.output)
            # Add input fields (nodes may read from initial state)
            if node.inputs:
                if isinstance(node.inputs, list):
                    field_names.update(node.inputs)
                elif isinstance(node.inputs, str):
                    field_names.add(node.inputs)

        # Add system fields that are always needed
        # These are used by the execution service and orchestrator
        system_fields = {
            "__execution_summary",  # Execution tracking metadata
            "__policy_success",  # Policy evaluation result
            "__next_node",  # Orchestrator dynamic routing
            "last_action_success",  # Standard success tracking
            "graph_success",  # Overall graph success
            "errors",  # Error collection
        }
        field_names.update(system_fields)

        if not field_names:
            # No output fields defined, fall back to dict
            self.logger.debug("No output fields found, using plain dict schema")
            return dict

        # Create TypedDict with all fields as optional Any
        # Using total=False makes all fields optional (not required at initialization)
        state_fields = {name: Any for name in field_names}

        # Create dynamic TypedDict class
        StateSchema = TypedDict(f"{graph.name}State", state_fields, total=False)

        self.logger.debug(
            f"Created dynamic state schema for '{graph.name}' with {len(field_names)} fields: {sorted(field_names)}"
        )

        return StateSchema

    def _initialize_builder(self, graph: Optional[Graph] = None) -> None:
        """
        Initialize a fresh StateGraph builder and reset orchestrator tracking.

        Args:
            graph: Optional graph to use for dynamic state schema creation.
                   If provided and config allows, creates TypedDict from graph structure.
        """
        # Try to create dynamic schema if graph provided
        if graph is not None:
            try:
                execution_config = self.config.get_execution_config()
                state_schema_config = execution_config.get("graph", {}).get(
                    "state_schema", "dynamic"
                )

                # Support both 'dynamic' (new default) and 'dict' (legacy)
                if state_schema_config in ("dynamic", "auto"):
                    state_schema = self._create_dynamic_state_schema(graph)
                else:
                    state_schema = self._get_state_schema_from_config()
            except Exception as e:
                self.logger.debug(
                    f"Could not create dynamic state schema: {e}, using config schema"
                )
                state_schema = self._get_state_schema_from_config()
        else:
            # No graph provided, use config-based schema
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
        self._initialize_builder(graph)  # Pass graph for dynamic state schema

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

    def process_node_edges(
        self, node_name: str, edges: Dict[str, Union[str, List[str]]]
    ) -> None:
        """
        Process edges for a node and add them to the graph.

        Args:
            node_name: Source node name
            edges: Dictionary of edge conditions to target nodes (str or list[str] for parallel)
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

    def _try_add_function_edge(
        self, node_name: str, edges: Dict[str, Union[str, List[str]]]
    ) -> bool:
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

    def _is_parallel_edge(self, edge_value: Union[str, List[str], None]) -> bool:
        """Check if edge value represents parallel targets.

        Args:
            edge_value: Edge value from node.edges (str, list[str], or None)

        Returns:
            True if edge has multiple targets for parallel execution
        """
        return isinstance(edge_value, list) and len(edge_value) > 1

    def _normalize_edge_value(
        self, edge_value: Union[str, List[str], None]
    ) -> Tuple[bool, Union[str, List[str], None]]:
        """Normalize edge value and determine if parallel.

        Args:
            edge_value: Edge value from node.edges

        Returns:
            Tuple of (is_parallel, normalized_value)
            - is_parallel: True if multiple targets
            - normalized_value: The edge value (str or list)
        """
        if edge_value is None:
            return False, None
        elif isinstance(edge_value, str):
            return False, edge_value
        elif isinstance(edge_value, list):
            if len(edge_value) == 0:
                return False, None
            elif len(edge_value) == 1:
                return False, edge_value[0]  # Single item list -> string
            else:
                return True, edge_value  # Multiple items -> parallel
        else:
            # Unexpected type, treat as single
            self.logger.warning(
                f"Unexpected edge value type: {type(edge_value)}. Treating as single target."
            )
            return False, str(edge_value)

    def _add_standard_edges(
        self, node_name: str, edges: Dict[str, Union[str, List[str]]]
    ) -> None:
        """Add standard edge types with parallel support.

        Handles success/failure/default edges and detects parallel targets.

        Args:
            node_name: Source node name
            edges: Dictionary of edge conditions to targets (str or list[str])
        """
        has_success = "success" in edges
        has_failure = "failure" in edges
        has_default = "default" in edges

        # Analyze edge types for parallel routing
        success_parallel = False
        failure_parallel = False
        success_targets = None
        failure_targets = None

        if has_success:
            success_parallel, success_targets = self._normalize_edge_value(
                edges["success"]
            )
        if has_failure:
            failure_parallel, failure_targets = self._normalize_edge_value(
                edges["failure"]
            )

        # Route to appropriate handler based on parallel detection
        if has_success and has_failure:
            # Both success and failure paths
            if success_parallel or failure_parallel:
                self._add_parallel_success_failure_edge(
                    node_name,
                    success_targets,
                    success_parallel,
                    failure_targets,
                    failure_parallel,
                )
            else:
                # Both single targets (existing behavior)
                self._add_success_failure_edge(
                    node_name, success_targets, failure_targets
                )
        elif has_success:
            # Only success path
            if success_parallel:
                self._add_conditional_edge(
                    node_name,
                    lambda state, targets=success_targets: (
                        targets if state.get("last_action_success", True) else None
                    ),
                )
                self.logger.debug(
                    f"[{node_name}] → parallel success → {success_targets}"
                )
            else:
                # Single success target (existing behavior)
                self._add_conditional_edge(
                    node_name,
                    lambda state, target=success_targets: (
                        target if state.get("last_action_success", True) else None
                    ),
                )
        elif has_failure:
            # Only failure path
            if failure_parallel:
                self._add_conditional_edge(
                    node_name,
                    lambda state, targets=failure_targets: (
                        targets if not state.get("last_action_success", True) else None
                    ),
                )
                self.logger.debug(
                    f"[{node_name}] → parallel failure → {failure_targets}"
                )
            else:
                # Single failure target (existing behavior)
                self._add_conditional_edge(
                    node_name,
                    lambda state, target=failure_targets: (
                        target if not state.get("last_action_success", True) else None
                    ),
                )
        elif has_default:
            # Unconditional edge (default)
            default_parallel, default_targets = self._normalize_edge_value(
                edges["default"]
            )
            if default_parallel:
                # Parallel default edge - return list directly
                self.logger.debug(
                    f"[{node_name}] → parallel default → {default_targets}"
                )
                # For default parallel, we need a routing function that always returns the list
                self._add_conditional_edge(
                    node_name, lambda state, targets=default_targets: targets
                )
            else:
                # Single default edge (existing behavior)
                self.builder.add_edge(node_name, default_targets)
                self.logger.debug(f"[{node_name}] → default → {default_targets}")

    def _add_conditional_edge(self, source: str, func: Callable) -> None:
        """Add a conditional edge to the graph."""
        self.builder.add_conditional_edges(source, func)
        self.logger.debug(f"[{source}] → conditional edge added")

    def _add_success_failure_edge(
        self, source: str, success: str, failure: str
    ) -> None:
        """Add single-target success/failure conditional edges.

        This is the existing behavior for single-target routing.
        For parallel routing, use _add_parallel_success_failure_edge().

        Args:
            source: Source node name
            success: Single success target
            failure: Single failure target
        """

        def branch(state):
            return success if state.get("last_action_success", True) else failure

        self.builder.add_conditional_edges(source, branch)
        self.logger.debug(f"[{source}] → success → {success} / failure → {failure}")

    def _add_parallel_success_failure_edge(
        self,
        source: str,
        success_targets: Union[str, List[str]],
        success_parallel: bool,
        failure_targets: Union[str, List[str]],
        failure_parallel: bool,
    ) -> None:
        """Add success/failure edges with parallel support.

        Generates routing function that returns either:
        - Single target (str) for sequential routing
        - Multiple targets (list[str]) for parallel routing

        LangGraph's superstep architecture handles parallel execution automatically
        when the routing function returns a list.

        Args:
            source: Source node name
            success_targets: Target(s) for success path (str or list[str])
            success_parallel: True if success has multiple targets
            failure_targets: Target(s) for failure path (str or list[str])
            failure_parallel: True if failure has multiple targets
        """

        def branch(state):
            """Routing function that may return str or list[str]."""
            last_action_success = state.get("last_action_success", True)

            if last_action_success:
                # Success path
                result = success_targets  # May be str or list[str]
                if success_parallel:
                    self.logger.debug(
                        f"[{source}] Routing to parallel success targets: {result}"
                    )
                return result
            else:
                # Failure path
                result = failure_targets  # May be str or list[str]
                if failure_parallel:
                    self.logger.debug(
                        f"[{source}] Routing to parallel failure targets: {result}"
                    )
                return result

        self.builder.add_conditional_edges(source, branch)

        # Enhanced logging for parallel edges
        success_display = (
            f"{success_targets} (parallel)" if success_parallel else success_targets
        )
        failure_display = (
            f"{failure_targets} (parallel)" if failure_parallel else failure_targets
        )
        self.logger.debug(
            f"[{source}] → success → {success_display} / failure → {failure_display}"
        )

    def _add_function_edge(
        self,
        source: str,
        func_name: str,
        success: Optional[Union[str, List[str]]],
        failure: Optional[Union[str, List[str]]],
    ) -> None:
        """Add function-based routing edge with parallel support.

        The routing function may return str or list[str], enabling parallel
        routing when the function logic determines multiple targets.

        Args:
            source: Source node name
            func_name: Name of routing function to load
            success: Success target(s) - may be str or list[str]
            failure: Failure target(s) - may be str or list[str]
        """
        func = self.function_resolution.load_function(func_name)

        def wrapped(state):
            # Function may return str or list[str]
            result = func(state, success, failure)

            # Log parallel routing if function returns list
            if isinstance(result, list) and len(result) > 1:
                self.logger.debug(
                    f"[{source}] Function '{func_name}' returned parallel targets: {result}"
                )

            return result

        self.builder.add_conditional_edges(source, wrapped)
        self.logger.debug(
            f"[{source}] → routed by function '{func_name}' "
            f"(success={success}, failure={failure})"
        )

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
