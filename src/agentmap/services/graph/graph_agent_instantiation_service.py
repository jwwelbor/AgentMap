"""
GraphAgentInstantiationService for AgentMap.

Service responsible for creating and configuring agent instances from a GraphBundle.
Bridges the gap between agent class registration (GraphBootstrapService) and
graph assembly (GraphAssemblyService) by creating actual agent instances with
injected services.
"""

from typing import Any, Dict, Optional, Set

from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.agent.agent_factory_service import AgentFactoryService
from agentmap.services.agent.agent_service_injection_service import (
    AgentServiceInjectionService,
)
from agentmap.services.declaration_registry_service import DeclarationRegistryService
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.graph.graph_agent_validation_service import (
    GraphAgentValidationService,
)
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.graph.graph_tool_loading_service import GraphToolLoadingService
from agentmap.services.logging_service import LoggingService
from agentmap.services.prompt_manager_service import PromptManagerService
from agentmap.services.protocols import (
    GraphBundleCapableAgent,
    ToolCapableAgent,
)
from agentmap.services.state_adapter_service import StateAdapterService


class GraphAgentInstantiationService:
    """
    Service for creating and configuring agent instances from graph metadata.

    This service takes a GraphBundle with registered agent classes and creates
    actual agent instances with all required services injected. It stores the
    instances in the bundle's node_registry field, keeping metadata and runtime
    instances cleanly separated.
    """

    def __init__(
        self,
        agent_factory_service: AgentFactoryService,
        agent_service_injection_service: AgentServiceInjectionService,
        execution_tracking_service: ExecutionTrackingService,
        state_adapter_service: StateAdapterService,
        logging_service: LoggingService,
        prompt_manager_service: PromptManagerService,
        graph_bundle_service: GraphBundleService,
        declaration_registry_service: Optional[DeclarationRegistryService] = None,
    ):
        """
        Initialize with required services for agent instantiation.

        Args:
            agent_factory_service: Service for creating agent instances
            agent_service_injection_service: Service for injecting dependencies
            execution_tracking_service: Service for execution tracking
            state_adapter_service: Service for state management
            logging_service: Service for logging
            prompt_manager_service: Optional service for prompt management
            graph_bundle_service: Service for managing graph bundles
            declaration_registry_service: Optional service for looking up agent declarations
                                         to enable bundle-aware service injection optimization
        """
        self.agent_factory = agent_factory_service
        self.agent_injection = agent_service_injection_service
        self.execution_tracking = execution_tracking_service
        self.state_adapter = state_adapter_service
        self.prompt_manager = prompt_manager_service
        self.graph_bundle_service = graph_bundle_service
        self.declaration_registry = declaration_registry_service
        self.logger = logging_service.get_class_logger(self)

        # Initialize helper services
        self._tool_loading_service = GraphToolLoadingService(logging_service)
        self._validation_service = GraphAgentValidationService(
            agent_service_injection_service, logging_service
        )

        self.logger.info("[GraphAgentInstantiationService] Initialized")

    def instantiate_agents(
        self, bundle: GraphBundle, execution_tracker: Optional[Any] = None
    ) -> GraphBundle:
        """
        Create and configure agent instances for all nodes in the bundle.

        This method:
        1. Creates agent instances using AgentFactoryService
        2. Injects required services using AgentServiceInjectionService
        3. Stores instances in bundle.node_registry as Dict[node_name, agent_instance]
        4. Returns the updated bundle ready for graph assembly

        Args:
            bundle: GraphBundle with nodes requiring agent instances
            execution_tracker: Optional execution tracker for agents

        Returns:
            Updated GraphBundle with agent instances in node_registry

        Raises:
            RuntimeError: If agent instantiation fails for any node
        """
        graph_name = bundle.graph_name or "unknown"
        self.logger.info(
            f"[GraphAgentInstantiationService] Starting agent instantiation for graph: {graph_name}"
        )

        if not bundle.nodes:
            self.logger.warning(
                f"[GraphAgentInstantiationService] No nodes to instantiate for graph: {graph_name}"
            )
            return bundle

        # Validate agent mappings
        self._validate_agent_mappings(bundle, graph_name)

        # Initialize bundle containers
        self._initialize_bundle_containers(bundle)

        # Phase 2: Tool Loading - Load tools from modules before agent instantiation
        self._tool_loading_service.load_tools_for_nodes(bundle)

        # Create node registry for orchestrator agents (contains node definitions)
        node_definitions_registry = self._create_node_definitions_registry(bundle)

        # Phase 3: Agent Instantiation
        instantiated_count, failed_nodes = self._instantiate_all_agents(
            bundle=bundle,
            graph_name=graph_name,
            node_definitions_registry=node_definitions_registry,
            execution_tracker=execution_tracker,
        )

        # Report results
        if failed_nodes:
            error_msg = (
                f"Failed to instantiate {len(failed_nodes)} nodes: "
                f"{', '.join([f'{name} ({error})' for name, error in failed_nodes])}"
            )
            self.logger.error(f"[GraphAgentInstantiationService] {error_msg}")
            raise RuntimeError(error_msg)

        self.logger.info(
            f"[GraphAgentInstantiationService] Successfully instantiated {instantiated_count} agents "
            f"for graph: {graph_name}"
        )

        return bundle

    def _validate_agent_mappings(self, bundle: GraphBundle, graph_name: str) -> None:
        """
        Validate that bundle has required agent mappings.

        Args:
            bundle: GraphBundle to validate
            graph_name: Name of the graph for error messages

        Raises:
            RuntimeError: If required mappings are missing
        """
        agent_mappings = bundle.agent_mappings or {}

        # Check if bundle has no agent mappings at all
        if bundle.required_agents and not agent_mappings:
            error_msg = (
                f"Bundle '{graph_name}' has no agent mappings but requires agents: "
                f"{sorted(list(bundle.required_agents))}\n\n"
                f"This usually means the bundle needs to be updated:\n"
                f"   - Run 'agentmap update-bundle' to sync with current declarations\n"
                f"   - If agents need scaffolding, run 'agentmap scaffold' first\n\n"
                f"Modern AgentMap scaffolding automatically updates bundles with mappings"
            )
            raise RuntimeError(error_msg)

        # Validate we have mappings for all required agents
        if bundle.required_agents:
            missing_mappings = bundle.required_agents - set(agent_mappings.keys())
            if missing_mappings:
                missing_list = sorted(list(missing_mappings))
                available_list = sorted(list(agent_mappings.keys()))

                error_msg = (
                    f"Missing agent mappings for: {missing_list}\n"
                    f"   Available mappings: {available_list}\n\n"
                    f"Possible solutions:\n"
                    f"   1. Run 'agentmap update-bundle' to update bundle with current declarations\n"
                    f"   2. If agents need scaffolding, run 'agentmap scaffold' (auto-updates bundles)\n"
                    f"   3. Check that agent declarations exist in custom_agents.yaml\n\n"
                    f"Note: Scaffolding operations automatically update bundles with agent mappings"
                )
                raise RuntimeError(error_msg)

    def _initialize_bundle_containers(self, bundle: GraphBundle) -> None:
        """
        Initialize bundle containers if not present.

        Args:
            bundle: GraphBundle to initialize
        """
        if bundle.node_instances is None:
            bundle.node_instances = {}

        if bundle.tools is None:
            bundle.tools = {}

    def _instantiate_all_agents(
        self,
        bundle: GraphBundle,
        graph_name: str,
        node_definitions_registry: Dict[str, Any],
        execution_tracker: Optional[Any],
    ) -> tuple:
        """
        Instantiate all agents in the bundle.

        Args:
            bundle: GraphBundle with nodes
            graph_name: Name of the graph
            node_definitions_registry: Registry for orchestrators
            execution_tracker: Optional execution tracker

        Returns:
            Tuple of (instantiated_count, failed_nodes)
        """
        instantiated_count = 0
        failed_nodes = []

        for node_name, node in bundle.nodes.items():
            try:
                self._instantiate_single_agent(
                    bundle=bundle,
                    node_name=node_name,
                    node=node,
                    graph_name=graph_name,
                    node_definitions_registry=node_definitions_registry,
                    execution_tracker=execution_tracker,
                )
                instantiated_count += 1

            except Exception as e:
                error_details = str(e)
                self.logger.error(
                    f"[GraphAgentInstantiationService] Failed to instantiate node {node_name}: {error_details}"
                )

                # Add helpful hints for common agent instantiation failures
                enhanced_error = self._enhance_error_message(error_details)
                failed_nodes.append((node_name, enhanced_error))

        return instantiated_count, failed_nodes

    def _instantiate_single_agent(
        self,
        bundle: GraphBundle,
        node_name: str,
        node: Any,
        graph_name: str,
        node_definitions_registry: Dict[str, Any],
        execution_tracker: Optional[Any],
    ) -> None:
        """
        Instantiate a single agent for a node.

        Args:
            bundle: GraphBundle containing the node
            node_name: Name of the node
            node: Node object
            graph_name: Name of the graph
            node_definitions_registry: Registry for orchestrators
            execution_tracker: Optional execution tracker
        """
        self.logger.debug(
            f"[GraphAgentInstantiationService] Instantiating agent for node: {node_name}"
        )

        # Extract from bundle
        agent_mappings = bundle.agent_mappings or {}
        custom_agents = bundle.custom_agents or set()

        # Step 1: Create agent instance using factory
        agent_instance = self.agent_factory.create_agent_instance(
            node=node,
            graph_name=graph_name,
            agent_mappings=agent_mappings,
            custom_agents=custom_agents,
            execution_tracking_service=self.execution_tracking,
            state_adapter_service=self.state_adapter,
            prompt_manager_service=self.prompt_manager,
            node_registry=node_definitions_registry,
            bundle_tools=bundle.tools if bundle.tools else None,
        )

        # Step 2: Inject services using injection service (with agent_type for optimization)
        # Pass bundle to enable thread-safe scoped registry access
        self._inject_services(
            agent_instance, node_name, execution_tracker, node.agent_type, bundle
        )

        # Step 2a: Inject GraphBundleService if agent supports it
        self._inject_graph_bundle_service(agent_instance, node_name)

        # Phase 3: Tool Binding - Configure tools for ToolCapableAgent instances
        self._configure_tools(bundle, agent_instance, node_name)

        # Step 3: Store instance in node_registry
        bundle.node_instances[node_name] = agent_instance

        self.logger.debug(
            f"[GraphAgentInstantiationService] Successfully instantiated: {node_name}"
        )

    def _get_required_services_for_agent(
        self, agent_type: Optional[str], bundle: Optional[GraphBundle] = None
    ) -> Optional[Set[str]]:
        """
        Look up required services for an agent type from the declaration registry.

        Prefers the scoped registry from the bundle (if available) for thread-safety
        in concurrent execution. Falls back to the singleton declaration_registry
        for backwards compatibility.

        Args:
            agent_type: The agent type to look up
            bundle: Optional bundle containing scoped_registry for thread-safe access

        Returns:
            Set of required service names, or None if not available
        """
        if not agent_type:
            return None

        # Prefer scoped registry from bundle for thread-safe concurrent execution
        registry = None
        if (
            bundle is not None
            and hasattr(bundle, "scoped_registry")
            and bundle.scoped_registry
        ):
            registry = bundle.scoped_registry
        elif self.declaration_registry:
            registry = self.declaration_registry

        if not registry:
            return None

        agent_decl = registry.get_agent_declaration(agent_type)
        if not agent_decl:
            return None

        # Get all services (required + optional) to allow full injection
        all_services = agent_decl.get_all_services()
        if not all_services:
            return None

        return set(all_services)

    def _inject_services(
        self,
        agent_instance: Any,
        node_name: str,
        execution_tracker: Optional[Any],
        agent_type: Optional[str] = None,
        bundle: Optional[GraphBundle] = None,
    ) -> None:
        """
        Inject services into an agent instance.

        Args:
            agent_instance: Agent to configure
            node_name: Name of the node for logging
            execution_tracker: Optional execution tracker
            agent_type: Optional agent type for looking up required services
            bundle: Optional bundle for thread-safe scoped registry access
        """
        # Look up required services from declaration registry for optimization
        # Pass bundle to use scoped_registry for thread-safe concurrent execution
        required_services = self._get_required_services_for_agent(agent_type, bundle)

        injection_summary = self.agent_injection.configure_all_services(
            agent=agent_instance,
            tracker=execution_tracker,
            required_services=required_services,
        )

        total_configured = injection_summary["total_services_configured"]
        self.logger.debug(
            f"[GraphAgentInstantiationService] Configured {total_configured} services "
            f"for agent: {node_name}"
            + (
                f" (filtered to {len(required_services)} declared services)"
                if required_services
                else ""
            )
        )

    def _inject_graph_bundle_service(self, agent_instance: Any, node_name: str) -> None:
        """
        Inject GraphBundleService if agent supports it.

        Args:
            agent_instance: Agent to configure
            node_name: Name of the node for logging
        """
        if isinstance(agent_instance, GraphBundleCapableAgent):
            agent_instance.configure_graph_bundle_service(self.graph_bundle_service)
            self.logger.debug(
                f"[GraphAgentInstantiationService] Injected GraphBundleService into {node_name}"
            )

    def _configure_tools(
        self, bundle: GraphBundle, agent_instance: Any, node_name: str
    ) -> None:
        """
        Configure tools for a ToolCapableAgent instance.

        Args:
            bundle: GraphBundle containing tools
            agent_instance: Agent to configure
            node_name: Name of the node for logging
        """
        if isinstance(agent_instance, ToolCapableAgent):
            tools = bundle.tools.get(node_name, [])
            if tools:
                agent_instance.configure_tools(tools)
                tool_names = [t.name for t in tools]
                self.logger.info(
                    f"[GraphAgentInstantiationService] Configured {len(tools)} tools for {node_name}: {', '.join(tool_names)}"
                )

    def _enhance_error_message(self, error_details: str) -> str:
        """
        Enhance error message with helpful hints for common failures.

        Args:
            error_details: Original error message

        Returns:
            Enhanced error message with hints
        """
        if "class_path" in error_details.lower() or "import" in error_details.lower():
            return (
                f"{error_details}\n\n"
                f"If this is a class path issue, try:\n"
                f"   - Run 'agentmap update-bundle' to sync agent mappings\n"
                f"   - Check if agent exists in custom_agents.yaml declarations"
            )
        return error_details

    def _create_node_definitions_registry(self, bundle: GraphBundle) -> Dict[str, Any]:
        """
        Create node definitions registry for orchestrator agents.

        This transforms Node objects into the metadata format expected by OrchestratorService
        for node selection and routing decisions.

        Args:
            bundle: GraphBundle with nodes

        Returns:
            Dictionary mapping node names to metadata dicts with:
            - description: Node description for keyword matching
            - prompt: Node prompt for additional context
            - type: Agent type for filtering
            - context: Optional context dict for keyword extraction
        """
        self.logger.debug(
            "[GraphAgentInstantiationService] Creating node definitions registry for orchestrators"
        )

        if not bundle.nodes:
            return {}

        # Transform Node objects to metadata format expected by orchestrators
        registry = {}
        for node_name, node in bundle.nodes.items():
            # Extract metadata fields that OrchestratorService actually uses
            registry[node_name] = {
                "description": node.description or "",
                "prompt": node.prompt or "",
                "type": node.agent_type or "",
                # Include context if it's a dict (for keyword parsing)
                "context": node.context if isinstance(node.context, dict) else {},
            }

        self.logger.debug(
            f"[GraphAgentInstantiationService] Created definitions registry with {len(registry)} nodes"
        )

        return registry

    def validate_instantiation(self, bundle: GraphBundle) -> Dict[str, Any]:
        """
        Validate that all nodes have properly instantiated agents in node_registry.

        Args:
            bundle: GraphBundle to validate

        Returns:
            Validation summary with status and any issues found
        """
        return self._validation_service.validate_instantiation(bundle)

    def get_instantiation_summary(self, bundle: GraphBundle) -> Dict[str, Any]:
        """
        Get a summary of agent instantiation status for the bundle.

        Args:
            bundle: GraphBundle to analyze

        Returns:
            Summary dictionary with instantiation statistics
        """
        return self._validation_service.get_instantiation_summary(bundle)
