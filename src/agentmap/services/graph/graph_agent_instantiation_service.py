"""
GraphAgentInstantiationService for AgentMap.

Service responsible for creating and configuring agent instances from a GraphBundle.
Bridges the gap between agent class registration (GraphBootstrapService) and
graph assembly (GraphAssemblyService) by creating actual agent instances with
injected services.
"""

from typing import Any, Dict, Optional

from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.agent.agent_factory_service import AgentFactoryService
from agentmap.services.agent.agent_service_injection_service import (
    AgentServiceInjectionService,
)
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.logging_service import LoggingService
from agentmap.services.prompt_manager_service import PromptManagerService
from agentmap.services.protocols import (
    GraphBundleCapableAgent,
    ToolCapableAgent,
    ToolSelectionCapableAgent,
)
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.tool_loader import load_tools_from_module


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
        """
        self.agent_factory = agent_factory_service
        self.agent_injection = agent_service_injection_service
        self.execution_tracking = execution_tracking_service
        self.state_adapter = state_adapter_service
        self.prompt_manager = prompt_manager_service
        self.graph_bundle_service = graph_bundle_service
        self.logger = logging_service.get_class_logger(self)

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

        # Extract the information we need from the bundle
        agent_mappings = bundle.agent_mappings or {}
        custom_agents = bundle.custom_agents or set()
        orchestration_agents = bundle.protocol_mappings

        # Check if bundle has no agent mappings at all
        if bundle.required_agents and not agent_mappings:
            error_msg = (
                f"❌ Bundle '{graph_name}' has no agent mappings but requires agents: "
                f"{sorted(list(bundle.required_agents))}\n\n"
                f"💡 This usually means the bundle needs to be updated:\n"
                f"   • Run 'agentmap update-bundle' to sync with current declarations\n"
                f"   • If agents need scaffolding, run 'agentmap scaffold' first\n\n"
                f"ℹ️  Modern AgentMap scaffolding automatically updates bundles with mappings"
            )
            raise RuntimeError(error_msg)

        # Validate we have mappings for all required agents
        if bundle.required_agents:
            missing_mappings = bundle.required_agents - set(agent_mappings.keys())
            if missing_mappings:
                missing_list = sorted(list(missing_mappings))
                available_list = sorted(list(agent_mappings.keys()))

                error_msg = (
                    f"❌ Missing agent mappings for: {missing_list}\n"
                    f"   Available mappings: {available_list}\n\n"
                    f"💡 Possible solutions:\n"
                    f"   1. Run 'agentmap update-bundle' to update bundle with current declarations\n"
                    f"   2. If agents need scaffolding, run 'agentmap scaffold' (auto-updates bundles)\n"
                    f"   3. Check that agent declarations exist in custom_agents.yaml\n\n"
                    f"ℹ️  Note: Scaffolding operations automatically update bundles with agent mappings"
                )
                raise RuntimeError(error_msg)

        # Initialize node_registry if not present
        if bundle.node_instances is None:
            bundle.node_instances = {}

        # Initialize tools cache if not present
        if bundle.tools is None:
            bundle.tools = {}

        # Phase 2: Tool Loading - Load tools from modules before agent instantiation
        self._load_tools_for_nodes(bundle)

        # Create node registry for orchestrator agents (contains node definitions)
        node_definitions_registry = self._create_node_definitions_registry(bundle)

        instantiated_count = 0
        failed_nodes = []

        # Process each node
        for node_name, node in bundle.nodes.items():
            try:
                self.logger.debug(
                    f"[GraphAgentInstantiationService] Instantiating agent for node: {node_name}"
                )

                # Step 1: Create agent instance using factory
                # AGM-TOOLS-001: Pass bundle.tools to factory for ToolAgent support
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

                # Step 2: Inject services using injection service
                injection_summary = self.agent_injection.configure_all_services(
                    agent=agent_instance, tracker=execution_tracker
                )

                total_configured = injection_summary["total_services_configured"]
                self.logger.debug(
                    f"[GraphAgentInstantiationService] Configured {total_configured} services "
                    f"for agent: {node_name}"
                )

                # Step 2a: Inject GraphBundleService if agent supports it
                if isinstance(agent_instance, GraphBundleCapableAgent):
                    agent_instance.configure_graph_bundle_service(
                        self.graph_bundle_service
                    )
                    self.logger.debug(
                        f"[GraphAgentInstantiationService] Injected GraphBundleService into {node_name}"
                    )

                # Phase 3: Tool Binding - Configure tools for ToolCapableAgent instances
                if isinstance(agent_instance, ToolCapableAgent):
                    tools = bundle.tools.get(node_name, [])
                    if tools:
                        agent_instance.configure_tools(tools)
                        tool_names = [t.name for t in tools]
                        self.logger.info(
                            f"[GraphAgentInstantiationService] ✅ Configured {len(tools)} tools for {node_name}: {', '.join(tool_names)}"
                        )

                # Step 3: Store instance in node_registry
                bundle.node_instances[node_name] = agent_instance

                instantiated_count += 1
                self.logger.debug(
                    f"[GraphAgentInstantiationService] ✅ Successfully instantiated: {node_name}"
                )

            except Exception as e:
                error_details = str(e)
                self.logger.error(
                    f"[GraphAgentInstantiationService] ❌ Failed to instantiate node {node_name}: {error_details}"
                )

                # Add helpful hints for common agent instantiation failures
                if (
                    "class_path" in error_details.lower()
                    or "import" in error_details.lower()
                ):
                    enhanced_error = (
                        f"{error_details}\n\n"
                        f"💡 If this is a class path issue, try:\n"
                        f"   • Run 'agentmap update-bundle' to sync agent mappings\n"
                        f"   • Check if agent exists in custom_agents.yaml declarations"
                    )
                    failed_nodes.append((node_name, enhanced_error))
                else:
                    failed_nodes.append((node_name, error_details))

        # Report results
        if failed_nodes:
            error_msg = (
                f"Failed to instantiate {len(failed_nodes)} nodes: "
                f"{', '.join([f'{name} ({error})' for name, error in failed_nodes])}"
            )
            self.logger.error(f"[GraphAgentInstantiationService] {error_msg}")
            raise RuntimeError(error_msg)

        self.logger.info(
            f"[GraphAgentInstantiationService] ✅ Successfully instantiated {instantiated_count} agents "
            f"for graph: {graph_name}"
        )

        return bundle

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
        validation_results = {
            "valid": True,
            "total_nodes": len(bundle.nodes) if bundle.nodes else 0,
            "instantiated_nodes": 0,
            "missing_instances": [],
            "invalid_instances": [],
        }

        if not bundle.nodes:
            validation_results["valid"] = False
            validation_results["error"] = "No nodes in bundle"
            return validation_results

        if not bundle.node_instances:
            validation_results["valid"] = False
            validation_results["error"] = (
                "No node_registry in bundle - agents may not have been instantiated.\n"
                "💡 Try running 'agentmap update-bundle' to ensure bundle has proper agent mappings."
            )
            return validation_results

        for node_name, node in bundle.nodes.items():
            # Check if instance exists in node_registry
            if node_name not in bundle.node_instances:
                validation_results["missing_instances"].append(node_name)
                validation_results["valid"] = False
                continue

            agent_instance = bundle.node_instances[node_name]

            # Validate instance has required methods
            if not hasattr(agent_instance, "run"):
                validation_results["invalid_instances"].append(
                    (node_name, "Missing 'run' method")
                )
                validation_results["valid"] = False
                continue

            if not hasattr(agent_instance, "name"):
                validation_results["invalid_instances"].append(
                    (node_name, "Missing 'name' attribute")
                )
                validation_results["valid"] = False
                continue

            validation_results["instantiated_nodes"] += 1

        # Log validation results
        if validation_results["valid"]:
            self.logger.debug(
                f"[GraphAgentInstantiationService] ✅ Validation passed: "
                f"{validation_results['instantiated_nodes']}/{validation_results['total_nodes']} nodes instantiated"
            )
        else:
            self.logger.error(
                f"[GraphAgentInstantiationService] ❌ Validation failed: "
                f"Missing instances: {validation_results['missing_instances']}, "
                f"Invalid instances: {validation_results['invalid_instances']}"
            )

        return validation_results

    def get_instantiation_summary(self, bundle: GraphBundle) -> Dict[str, Any]:
        """
        Get a summary of agent instantiation status for the bundle.

        Args:
            bundle: GraphBundle to analyze

        Returns:
            Summary dictionary with instantiation statistics
        """
        summary = {
            "graph_name": bundle.graph_name,
            "total_nodes": len(bundle.nodes) if bundle.nodes else 0,
            "instantiated": 0,
            "missing": 0,
            "agent_types": {},
            "service_injection_stats": {},
        }

        if not bundle.nodes:
            return summary

        node_registry = bundle.node_instances or {}

        for node_name, node in bundle.nodes.items():
            agent_type = getattr(node, "agent_type", "unknown")

            # Track agent type counts
            if agent_type not in summary["agent_types"]:
                summary["agent_types"][agent_type] = {
                    "count": 0,
                    "instantiated": 0,
                    "nodes": [],
                }

            summary["agent_types"][agent_type]["count"] += 1
            summary["agent_types"][agent_type]["nodes"].append(node_name)

            # Check instantiation status in node_registry
            if node_name in node_registry:
                summary["instantiated"] += 1
                summary["agent_types"][agent_type]["instantiated"] += 1

                # Get service injection status if available
                agent_instance = node_registry[node_name]
                injection_status = self.agent_injection.get_service_injection_status(
                    agent_instance
                )
                summary["service_injection_stats"][node_name] = {
                    "protocols_implemented": len(
                        injection_status.get("implemented_protocols", [])
                    ),
                    "services_ready": injection_status.get("summary", {}).get(
                        "injection_ready_count", 0
                    ),
                }
            else:
                summary["missing"] += 1

        return summary

    def _load_tools_for_nodes(self, bundle: GraphBundle) -> None:
        """
        Load tools from modules for all nodes that specify tool sources.

        This method processes each node's tool_source field and loads the specified
        tools into bundle.tools[node_name] for later binding during agent instantiation.

        Args:
            bundle: GraphBundle with nodes that may require tools

        Raises:
            ImportError: If a tool module cannot be imported
            ValueError: If specified tools are not found in the module
        """
        if not bundle.nodes:
            return

        loaded_count = 0
        for node_name, node in bundle.nodes.items():
            # Skip nodes without tool_source or with "toolnode" (special case)
            tool_source = getattr(node, "tool_source", None)
            if not tool_source or tool_source.lower() == "toolnode":
                continue

            try:
                # Load all tools from the module
                self.logger.debug(
                    f"[GraphAgentInstantiationService] Loading tools from: {tool_source}"
                )
                all_tools = load_tools_from_module(tool_source)

                # Filter to available_tools if specified
                available_tools = getattr(node, "available_tools", None)
                if available_tools:
                    # Filter tools by name
                    tools = [t for t in all_tools if t.name in available_tools]

                    # Validate all requested tools were found
                    found_names = {t.name for t in tools}
                    requested_names = set(available_tools)
                    missing = requested_names - found_names

                    if missing:
                        available_names = [t.name for t in all_tools]
                        raise ValueError(
                            f"Tools not found in {tool_source}: {sorted(missing)}\n"
                            f"Available tools: {sorted(available_names)}\n"
                            f"Suggestions:\n"
                            f"  • Check spelling in AvailableTools column\n"
                            f"  • Verify @tool decorated functions exist in module"
                        )
                else:
                    # Use all tools from module
                    tools = all_tools

                # Store in bundle
                bundle.tools[node_name] = tools
                tool_names = [t.name for t in tools]
                loaded_count += 1

                self.logger.info(
                    f"[GraphAgentInstantiationService] ✅ Loaded {len(tools)} tools for {node_name}: {', '.join(tool_names)}"
                )

            except ImportError as e:
                error_msg = (
                    f"Failed to load tools for node {node_name}: {str(e)}\n"
                    f"Tool source: {tool_source}\n"
                    f"Suggestions:\n"
                    f"  • Check ToolSource column in CSV\n"
                    f"  • Verify the file path is correct\n"
                    f"  • Ensure the module exists and is accessible"
                )
                self.logger.error(f"[GraphAgentInstantiationService] ❌ {error_msg}")
                raise ImportError(error_msg) from e

            except ValueError as e:
                # Re-raise with context
                self.logger.error(
                    f"[GraphAgentInstantiationService] ❌ Tool validation failed for {node_name}: {str(e)}"
                )
                raise

            except Exception as e:
                error_msg = (
                    f"Unexpected error loading tools for node {node_name}: {str(e)}\n"
                    f"Tool source: {tool_source}"
                )
                self.logger.error(f"[GraphAgentInstantiationService] ❌ {error_msg}")
                raise RuntimeError(error_msg) from e

        if loaded_count > 0:
            self.logger.info(
                f"[GraphAgentInstantiationService] ✅ Tool loading complete: {loaded_count} nodes configured with tools"
            )
