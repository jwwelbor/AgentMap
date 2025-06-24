from typing import Any, Callable, Dict, Optional

from langgraph.graph import StateGraph

from agentmap.models.graph import Graph
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.logging_service import LoggingService
from agentmap.services.node_registry_service import NodeRegistryUser
from agentmap.services.state_adapter_service import StateAdapterService


class GraphAssemblyService:
    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
        state_adapter_service: StateAdapterService,
        features_registry_service: FeaturesRegistryService,
        function_resolution_service: FunctionResolutionService,
    ):
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.functions_dir = self.config.get_functions_path()
        self.state_adapter = state_adapter_service
        self.features_registry = features_registry_service
        self.function_resolution = function_resolution_service

        # Get state schema from config or default to dict
        state_schema = self._get_state_schema_from_config()
        self.builder = StateGraph(state_schema=state_schema)
        self.orchestrator_nodes = []
        self.node_registry: Optional[Dict[str, Any]] = None
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
            # Try to get state schema configuration
            execution_config = self.config.get_execution_config()
            state_schema_config = execution_config.get("graph", {}).get(
                "state_schema", "dict"
            )

            if state_schema_config == "dict":
                return dict
            elif state_schema_config == "pydantic":
                # Try to import pydantic and return BaseModel or a custom model
                try:
                    from pydantic import BaseModel

                    # Could be configured to use a specific model class
                    model_class = execution_config.get("graph", {}).get(
                        "state_model_class"
                    )
                    if model_class:
                        # Would need to dynamically import the specified class
                        # For now, return BaseModel as a safe default
                        return BaseModel
                    return BaseModel
                except ImportError:
                    self.logger.warning(
                        "Pydantic requested but not available, falling back to dict"
                    )
                    return dict
            else:
                # Custom state schema - would need specific handling
                self.logger.warning(
                    f"Unknown state schema type '{state_schema_config}', falling back to dict"
                )
                return dict

        except Exception as e:
            self.logger.debug(
                f"Could not read state schema from config: {e}, using dict"
            )
            return dict

    def assemble_graph(
        self,
        graph: Graph,
        node_registry: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Assemble an executable LangGraph from a Graph domain model.

        Args:
            graph: Graph domain model with nodes and configuration
            node_registry: Optional node registry for orchestrator injection

        Returns:
            Compiled executable graph

        Raises:
            ValueError: If graph has no nodes
        """
        self.logger.info(f"🚀 Starting graph assembly: '{graph.name}'")

        # Validate graph has nodes
        if not graph.nodes:
            raise ValueError(f"Graph '{graph.name}' has no nodes")

        # Create fresh StateGraph builder for each compilation to avoid LangGraph conflicts
        state_schema = self._get_state_schema_from_config()
        self.builder = StateGraph(state_schema=state_schema)
        self.orchestrator_nodes = []
        self.injection_stats = {
            "orchestrators_found": 0,
            "orchestrators_injected": 0,
            "injection_failures": 0,
        }

        self.node_registry = node_registry

        # Add all nodes and process their edges
        node_names = list(graph.nodes.keys())
        entry_point = None

        self.logger.debug(f"Processing {len(node_names)} nodes: {node_names}")

        # First, check if graph-level entry point is available
        if graph.entry_point:
            entry_point = graph.entry_point
            self.logger.debug(f"🚪 Using graph-level entry point: '{entry_point}'")

        for node_name, node in graph.nodes.items():
            self.add_node(node_name, node.context.get("instance"))
            self.process_node_edges(node_name, node.edges)

            # Check if this node has entry point information from Node domain model
            if (
                not entry_point
                and hasattr(node, "_is_entry_point")
                and node._is_entry_point
            ):
                entry_point = node_name
                self.logger.debug(f"🚪 Using node-level entry point: '{entry_point}'")

        # Set entry point - use detected entry point or fall back to first node
        if not entry_point and node_names:
            entry_point = node_names[0]  # Fallback to first node
            self.logger.warning(
                f"🚪 No entry point detected, using first node: '{entry_point}'"
            )

        if entry_point:
            self.set_entry_point(entry_point)

        # Add dynamic routers for orchestrator nodes
        if self.orchestrator_nodes:
            self.logger.debug(
                f"Adding dynamic routers for {len(self.orchestrator_nodes)} orchestrator nodes"
            )
            for node_name in self.orchestrator_nodes:
                self._add_dynamic_router(node_name)

        return self.compile()

    def add_node(self, name: str, agent_instance: Any) -> None:
        """
        Add a node to the graph with its agent instance.

        Args:
            name: Node name
            agent_instance: Agent instance with run method
        """
        self.builder.add_node(name, agent_instance.run)
        class_name = agent_instance.__class__.__name__

        if isinstance(agent_instance, NodeRegistryUser):
            self.orchestrator_nodes.append(name)
            self.injection_stats["orchestrators_found"] += 1
            if self.node_registry:
                try:
                    agent_instance.node_registry = self.node_registry
                    self.injection_stats["orchestrators_injected"] += 1
                    self.logger.debug(
                        f"✅ Injected registry into orchestrator '{name}'"
                    )
                except Exception as e:
                    self.injection_stats["injection_failures"] += 1
                    self.logger.error(
                        f"❌ Failed to inject registry into '{name}': {e}"
                    )

        self.logger.debug(f"🔹 Added node: '{name}' ({class_name})")

    def set_entry_point(self, node_name: str) -> None:
        """
        Set the entry point for the graph.

        Args:
            node_name: Name of the entry point node
        """
        self.builder.set_entry_point(node_name)
        self.logger.debug(f"🚪 Set entry point: '{node_name}'")

    def process_node_edges(self, node_name: str, edges: Dict[str, str]) -> None:
        """
        Process edges for a node and add them to the graph.

        Args:
            node_name: Source node name
            edges: Dictionary of edge conditions to target nodes
        """
        if not edges:
            return

        self.logger.debug(
            f"Processing edges for node '{node_name}': {list(edges.keys())}"
        )

        has_func = False
        for condition, target in edges.items():
            func_ref = self.function_resolution.extract_func_ref(target)
            if func_ref:
                success = edges.get("success")
                failure = edges.get("failure")
                self._add_function_edge(node_name, func_ref, success, failure)
                has_func = True
                break

        if not has_func:
            if "success" in edges and "failure" in edges:
                self._add_success_failure_edge(
                    node_name, edges["success"], edges["failure"]
                )
            elif "success" in edges:

                def success_only(state):
                    return (
                        edges["success"]
                        if state.get("last_action_success", True)
                        else None
                    )

                self._add_conditional_edge(node_name, success_only)
            elif "failure" in edges:

                def failure_only(state):
                    return (
                        edges["failure"]
                        if not state.get("last_action_success", True)
                        else None
                    )

                self._add_conditional_edge(node_name, failure_only)
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

    def _add_dynamic_router(self, node_name: str) -> None:
        """Add dynamic routing for orchestrator nodes."""

        def dynamic_router(state):
            next_node = self.state_adapter.get_value(state, "__next_node")
            if next_node:
                self.state_adapter.set_value(state, "__next_node", None)
                return next_node
            return None

        self.builder.add_conditional_edges(node_name, dynamic_router)
        self.logger.debug(f"[{node_name}] → dynamic router added")

    def compile(self) -> Any:
        """
        Compile the assembled graph into an executable form.

        Returns:
            Compiled executable graph
        """
        self.logger.info("📋 Compiling graph")

        stats = self.injection_stats
        if stats["orchestrators_found"] > 0:
            self.logger.info(f"📊 Registry injection summary: {stats}")

        compiled_graph = self.builder.compile()
        self.logger.info("✅ Graph compilation completed successfully")

        return compiled_graph

    def get_injection_summary(self) -> Dict[str, int]:
        """Get summary of registry injection statistics."""
        return self.injection_stats.copy()
