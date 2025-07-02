"""
GraphRunnerService for AgentMap.

Simplified facade service that coordinates graph execution by delegating to specialized services:
- GraphDefinitionService for graph loading and building
- GraphExecutionService for execution orchestration
- CompilationService for graph compilation management
- Other specialized services as needed

Maintains backward compatibility while dramatically reducing internal complexity.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.models.execution_result import ExecutionResult
from agentmap.services.agent_factory_service import AgentFactoryService
from agentmap.services.compilation_service import CompilationService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.dependency_checker_service import DependencyCheckerService
from agentmap.services.execution_policy_service import ExecutionPolicyService
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.graph_assembly_service import GraphAssemblyService
from agentmap.services.graph_bundle_service import GraphBundleService
from agentmap.services.graph_definition_service import GraphDefinitionService
from agentmap.services.graph_execution_service import GraphExecutionService
from agentmap.services.host_protocol_configuration_service import (
    HostProtocolConfigurationService,
)
from agentmap.services.llm_service import LLMService

# Direct imports from migrated services in src_new
from agentmap.services.logging_service import LoggingService
from agentmap.services.node_registry_service import NodeRegistryService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.storage.manager import StorageServiceManager


@dataclass
class RunOptions:
    """Options for graph execution."""

    initial_state: Optional[Any] = None  # could by pydantic or dict
    autocompile: Optional[bool] = None
    csv_path: Optional[Path] = None
    validate_before_run: bool = False
    track_execution: bool = True
    force_compilation: bool = False
    execution_mode: str = "standard"  # "standard", "debug", "minimal"


class GraphRunnerService:
    """
    Simplified facade service for graph execution orchestration.

    Provides high-level coordination by delegating to specialized services:
    - GraphDefinitionService: Graph loading and building from CSV
    - GraphExecutionService: Clean execution orchestration
    - CompilationService: Compilation management
    - Other services: Agent resolution, dependency checking, etc.

    This service maintains all existing public APIs while dramatically reducing
    internal complexity through clean delegation patterns.
    """

    def __init__(
        self,
        graph_definition_service: GraphDefinitionService,
        graph_execution_service: GraphExecutionService,
        compilation_service: CompilationService,
        graph_bundle_service: GraphBundleService,
        agent_factory_service: AgentFactoryService,
        llm_service: LLMService,
        storage_service_manager: StorageServiceManager,
        node_registry_service: NodeRegistryService,
        logging_service: LoggingService,
        app_config_service: AppConfigService,
        execution_tracking_service: ExecutionTrackingService,
        execution_policy_service: ExecutionPolicyService,
        state_adapter_service: StateAdapterService,
        dependency_checker_service: DependencyCheckerService,
        graph_assembly_service: GraphAssemblyService,
        prompt_manager_service: Any = None,  # PromptManagerService - optional for backward compatibility
        orchestrator_service: Any = None,  # OrchestratorService - optional for backward compatibility
        host_protocol_configuration_service: HostProtocolConfigurationService = None,  # Optional for host service injection
        graph_checkpoint_service: Any = None,  # GraphCheckpointService - optional for human-in-the-loop
    ):
        """Initialize facade service with specialized service dependencies.

        Args:
            graph_definition_service: Service for building graphs from CSV
            graph_execution_service: Service for execution orchestration
            compilation_service: Service for graph compilation
            graph_bundle_service: Service for graph bundle operations
            agent_factory_service: Service for agent class resolution and validation
            llm_service: Service for LLM operations and injection
            storage_service_manager: Manager for storage service injection
            node_registry_service: Service for node registry management
            logging_service: Service for logging operations
            app_config_service: Service for application configuration
            execution_tracking_service: Service for creating execution trackers
            execution_policy_service: Service for policy evaluation
            state_adapter_service: Service for state management
            dependency_checker_service: Service for dependency validation
            graph_assembly_service: Service for graph assembly
            prompt_manager_service: Service for prompt template resolution and formatting
            orchestrator_service: Service for orchestration business logic (optional)
            host_protocol_configuration_service: Service for host protocol configuration (optional)
            graph_checkpoint_service: Service for graph execution checkpoints (optional)
        """
        # Core specialized services
        self.graph_definition = graph_definition_service
        self.graph_execution = graph_execution_service
        self.compilation = compilation_service
        self.graph_bundle_service = graph_bundle_service

        # Agent creation and management
        self.agent_factory = agent_factory_service

        # Supporting services for agent resolution and injection
        self.llm_service = llm_service
        self.storage_service_manager = storage_service_manager
        self.node_registry = node_registry_service
        self.dependency_checker = dependency_checker_service
        self.graph_assembly_service = graph_assembly_service
        self.prompt_manager_service = prompt_manager_service
        self.orchestrator_service = orchestrator_service

        # Infrastructure services
        self.logger = logging_service.get_class_logger(self)
        self.config = app_config_service

        # Services used for delegation to GraphExecutionService
        self.execution_tracking_service = execution_tracking_service
        self.execution_policy_service = execution_policy_service
        self.state_adapter_service = state_adapter_service

        # Host service injection support (optional)
        self.host_protocol_configuration = host_protocol_configuration_service
        self._host_services_available = host_protocol_configuration_service is not None

        # Graph checkpoint service (optional)
        self.graph_checkpoint_service = graph_checkpoint_service

        self.logger.info("[GraphRunnerService] Initialized as simplified facade")
        self._log_service_status()

    def get_default_options(self) -> RunOptions:
        """Get default run options from configuration."""
        options = RunOptions()
        options.initial_state = None  # could by pydantic or dict
        options.autocompile = self.config.get_value("autocompile", False)
        options.csv_path = self.config.get_csv_path()
        options.validate_before_run = False
        options.track_execution = self.config.get_execution_config().get(
            "track_execution", True
        )
        options.force_compilation = False
        options.execution_mode = "standard"  # "standard", "debug", "minimal"
        return options

    def run_graph(
        self, graph_name: str, options: Optional[RunOptions] = None
    ) -> ExecutionResult:
        """
        Main graph execution method - simplified facade implementation.

        Coordinates graph resolution and delegates execution to GraphExecutionService.

        Args:
            graph_name: Name of the graph to execute
            options: Execution options (uses defaults if None)

        Returns:
            ExecutionResult with complete execution details
        """
        # Initialize options with defaults
        if options is None:
            options = self.get_default_options()

        # Initialize state
        state = options.initial_state or {}

        self.logger.info(f"⭐ STARTING GRAPH: '{graph_name}'")
        self.logger.debug(f"[GraphRunnerService] Execution options: {options}")

        try:
            # Step 1: Resolve the graph using simplified resolution
            self.logger.debug(f"[GraphRunnerService] Resolving graph: {graph_name}")
            resolved_execution = self._resolve_graph_for_execution(graph_name, options)

            # Step 2: Delegate execution to GraphExecutionService based on resolution type
            if resolved_execution["type"] == "compiled":
                self.logger.debug(
                    f"[GraphRunnerService] Delegating compiled graph execution"
                )
                return self.graph_execution.execute_compiled_graph(
                    bundle_path=resolved_execution["bundle_path"], state=state
                )
            elif resolved_execution["type"] == "definition":
                self.logger.debug(
                    f"[GraphRunnerService] Delegating definition graph execution"
                )
                return self.graph_execution.execute_from_definition(
                    graph_def=resolved_execution["graph_def"],
                    state=state,
                    graph_name=graph_name,
                )
            else:
                raise ValueError(
                    f"Unknown resolution type: {resolved_execution['type']}"
                )

        except Exception as e:
            self.logger.error(f"❌ GRAPH EXECUTION FAILED: '{graph_name}'")
            self.logger.error(f"[GraphRunnerService] Error: {str(e)}")

            # Create error result using same pattern as GraphExecutionService
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=state,  # Return original state on error
                execution_summary=None,
                total_duration=0.0,
                compiled_from=None,
                error=str(e),
            )

            return execution_result

    def run_from_compiled(
        self, graph_path: Path, options: Optional[RunOptions] = None
    ) -> ExecutionResult:
        """
        Run graph from pre-compiled file - simplified facade implementation.

        Delegates directly to GraphExecutionService.execute_compiled_graph().

        Args:
            graph_path: Path to compiled graph file
            options: Execution options

        Returns:
            ExecutionResult with execution details
        """
        # Initialize options with defaults
        if options is None:
            options = self.get_default_options()

        # Initialize state
        state = options.initial_state or {}

        # Extract graph name from path for logging and error handling
        graph_name = graph_path.stem

        self.logger.info(
            f"[GraphRunnerService] Running from compiled graph: {graph_path}"
        )

        try:
            # Delegate directly to GraphExecutionService
            return self.graph_execution.execute_compiled_graph(
                bundle_path=graph_path, state=state
            )
        except Exception as e:
            self.logger.error(f"❌ COMPILED GRAPH EXECUTION FAILED: '{graph_name}'")
            self.logger.error(f"[GraphRunnerService] Error: {str(e)}")

            # Create error result using same pattern as other methods
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=state,  # Return original state on error
                execution_summary=None,
                total_duration=0.0,
                compiled_from=None,
                error=str(e),
            )

            return execution_result

    def run_from_csv_direct(
        self, csv_path: Path, graph_name: str, options: Optional[RunOptions] = None
    ) -> ExecutionResult:
        """
        Run graph directly from CSV without compilation - simplified facade implementation.

        Coordinates GraphDefinitionService for loading and GraphExecutionService for execution.

        Args:
            csv_path: Path to CSV file
            graph_name: Name of the graph to execute
            options: Execution options

        Returns:
            ExecutionResult with execution details
        """
        # Initialize options with defaults, force no autocompile
        if options is None:
            options = self.get_default_options()

        # Override options to force CSV path and disable autocompile
        options.csv_path = csv_path
        # options.autocompile = False

        # Initialize state
        state = options.initial_state or {}

        self.logger.info(
            f"[GraphRunnerService] Running directly from CSV: {csv_path}, graph: {graph_name}"
        )

        try:
            # Step 1: Load graph definition using GraphDefinitionService
            graph_def, resolved_graph_name = self._load_graph_definition_for_execution(
                csv_path, graph_name
            )

            # Step 2: Delegate execution to GraphExecutionService with graph name
            return self.graph_execution.execute_from_definition(
                graph_def=graph_def, state=state, graph_name=resolved_graph_name
            )

        except Exception as e:
            self.logger.error(f"❌ CSV DIRECT EXECUTION FAILED: '{graph_name}'")
            self.logger.error(f"[GraphRunnerService] Error: {str(e)}")

            # Create error result
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=state,
                execution_summary=None,
                total_duration=0.0,
                compiled_from="memory",
                error=str(e),
            )

            return execution_result

    def _resolve_graph_for_execution(
        self, graph_name: str, options: RunOptions
    ) -> Dict[str, Any]:
        """
        Simplified graph resolution that determines execution path.

        Returns resolution information for GraphExecutionService delegation.

        Args:
            graph_name: Name of the graph to resolve
            options: Run options containing configuration

        Returns:
            Dictionary with resolution information:
            - type: "compiled" or "definition"
            - bundle_path: Path to bundle (for compiled type)
            - graph_def: Graph definition (for definition type)
        """
        self.logger.debug(
            f"[GraphRunnerService] Resolving graph for execution: {graph_name}"
        )

        # Path 1: Try to load precompiled graph
        compiled_bundle_path = self._find_compiled_graph(graph_name)
        if compiled_bundle_path:
            self.logger.debug(
                f"[GraphRunnerService] Found precompiled graph: {compiled_bundle_path}"
            )
            return {"type": "compiled", "bundle_path": compiled_bundle_path}

        # Path 2: Try autocompilation if enabled
        autocompile = options.autocompile
        if autocompile is None:
            autocompile = self.config.get_value("autocompile", False)

        if autocompile and graph_name:
            self.logger.debug(
                f"[GraphRunnerService] Attempting autocompilation for: {graph_name}"
            )
            autocompiled_path = self._autocompile_graph(graph_name, options)
            if autocompiled_path:
                self.logger.debug(
                    f"[GraphRunnerService] Autocompiled graph: {autocompiled_path}"
                )
                return {"type": "compiled", "bundle_path": autocompiled_path}

        # Path 3: Build graph definition for in-memory execution
        self.logger.debug(
            f"[GraphRunnerService] Building graph definition for memory execution: {graph_name}"
        )
        csv_path = options.csv_path or self.config.get_csv_path()
        graph_def, resolved_graph_name = self._load_graph_definition_for_execution(
            csv_path, graph_name
        )

        return {"type": "definition", "graph_def": graph_def}

    def _find_compiled_graph(self, graph_name: str) -> Optional[Path]:
        """
        Find compiled graph bundle if it exists.

        Args:
            graph_name: Name of the graph to find

        Returns:
            Path to compiled bundle or None if not found
        """
        compiled_path = self.config.get_compiled_graphs_path() / f"{graph_name}.pkl"

        if compiled_path.exists():
            self.logger.debug(
                f"[GraphRunnerService] Found compiled graph: {compiled_path}"
            )
            return compiled_path

        self.logger.debug(
            f"[GraphRunnerService] No compiled graph found: {compiled_path}"
        )
        return None

    def _autocompile_graph(
        self, graph_name: str, options: RunOptions
    ) -> Optional[Path]:
        """
        Attempt to autocompile a graph using CompilationService.

        Args:
            graph_name: Name of the graph to compile
            options: Run options containing compilation configuration

        Returns:
            Path to compiled bundle or None if compilation failed
        """
        self.logger.debug(f"[GraphRunnerService] Autocompiling graph: {graph_name}")

        try:
            # Use CompilationService for autocompilation
            from agentmap.services.compilation_service import CompilationOptions

            compilation_options = CompilationOptions(
                csv_path=options.csv_path,
                force_recompile=options.force_compilation,
                include_source=True,
            )

            # Try auto-compile if needed
            csv_path = options.csv_path or self.config.get_csv_path()
            result = self.compilation.auto_compile_if_needed(
                graph_name, csv_path, compilation_options
            )

            if result and result.success:
                self.logger.debug(
                    f"[GraphRunnerService] Autocompilation successful for: {graph_name}"
                )
                # Return path to the newly compiled graph
                return self.config.get_compiled_graphs_path() / f"{graph_name}.pkl"
            else:
                self.logger.warning(
                    f"[GraphRunnerService] Autocompilation failed for: {graph_name}"
                )
                if result:
                    self.logger.warning(
                        f"[GraphRunnerService] Compilation error: {result.error}"
                    )
                return None

        except Exception as e:
            self.logger.error(
                f"[GraphRunnerService] Autocompilation error for {graph_name}: {e}"
            )
            return None

    def _load_graph_definition_for_execution(
        self, csv_path: Path, graph_name: Optional[str]
    ) -> tuple:
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
            f"[GraphRunnerService] Loading graph definition for execution: {csv_path}"
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
                f"[GraphRunnerService] Using first graph: {resolved_graph_name}"
            )

        # Step 2: Convert to execution format and prepare with agent instances
        prepared_graph_def = self._prepare_graph_definition_for_execution(
            graph_domain_model, resolved_graph_name
        )

        return prepared_graph_def, resolved_graph_name

    def _prepare_graph_definition_for_execution(
        self, graph_domain_model: Any, graph_name: str
    ) -> Dict[str, Any]:
        """
        Prepare graph definition with agent instances for execution.

        Works directly with Graph domain model without unnecessary conversion.

        Args:
            graph_domain_model: Graph domain model from GraphDefinitionService
            graph_name: Name of the graph for logging context

        Returns:
            Prepared graph definition ready for GraphExecutionService
        """
        self.logger.debug(
            f"[GraphRunnerService] Preparing graph definition for execution: {graph_name}"
        )

        # Work directly with the domain model nodes
        graph_nodes = graph_domain_model.nodes

        if not graph_nodes:
            raise ValueError(
                f"Invalid or empty graph definition for graph: {graph_name}"
            )

        # Prepare node registry
        self.logger.debug(
            f"[GraphRunnerService] Preparing node registry for: {graph_name}"
        )
        node_registry = self.node_registry.prepare_for_assembly(graph_nodes, graph_name)

        # Create and configure agent instances for each node
        for node_name, node in graph_nodes.items():
            agent_instance = self._create_agent_instance(
                node, graph_name, node_registry
            )
            self._validate_agent_configuration(agent_instance, node)
            if not node.context:
                node.context = {}
            node.context["instance"] = agent_instance

        self.logger.debug(
            f"[GraphRunnerService] Graph definition prepared for execution: {graph_name}"
        )
        return graph_nodes

    def _create_agent_instance(
        self,
        node,
        graph_name: str,
        node_registry: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        Simplified agent creation with protocol-based injection.

        Args:
            node: Node definition with agent configuration
            graph_name: Name of the graph being built

        Returns:
            Fully configured agent instance ready for graph assembly
        """
        self.logger.debug(
            f"[GraphRunnerService] Creating agent instance for node: {node.name} (type: {node.agent_type})"
        )

        # Step 1: Resolve agent class using AgentFactory
        agent_cls = self._resolve_agent_class(node.agent_type)

        # Step 2: Create context with input/output field information
        context = {
            "input_fields": node.inputs,
            "output_field": node.output,
            "description": node.description or "",
        }

        # Add CSV context data if available
        if hasattr(node, "context") and node.context:
            # Merge CSV context with basic context
            context.update(node.context)

        self.logger.debug(
            f"[GraphRunnerService] Instantiating {agent_cls.__name__} as node '{node.name}'"
        )

        # Step 3: Create agent with infrastructure services - check what the agent supports
        import inspect

        # Get the agent class constructor signature
        agent_signature = inspect.signature(agent_cls.__init__)
        agent_params = list(agent_signature.parameters.keys())

        # Build constructor arguments based on what the agent supports
        constructor_args = {
            "name": node.name,
            "prompt": node.prompt or "",
            "context": context,
            "logger": self.logger,
            "execution_tracker_service": self.execution_tracking_service,
            "state_adapter_service": self.state_adapter_service,
        }

        # Only add prompt_manager_service if the agent supports it
        if "prompt_manager_service" in agent_params and self.prompt_manager_service:
            constructor_args["prompt_manager_service"] = self.prompt_manager_service
            self.logger.debug(
                f"[GraphRunnerService] Adding prompt_manager_service to {node.name}"
            )

        agent_instance = agent_cls(**constructor_args)

        # Step 4: Configure business services based on protocols
        self._configure_agent_services(agent_instance)

        # Step 5: Special handling for OrchestratorAgent - inject node registry
        if agent_cls.__name__ == "OrchestratorAgent":
            self.logger.debug(
                f"[GraphRunnerService] Injecting node registry for OrchestratorAgent: {node.name}"
            )
            if node_registry:
                agent_instance.node_registry = node_registry
                self.logger.debug(
                    f"[GraphRunnerService] ✅ Node registry injected with {len(node_registry)} nodes"
                )
            else:
                self.logger.warning(
                    f"[GraphRunnerService] No node registry available for OrchestratorAgent: {node.name}"
                )

        self.logger.debug(
            f"[GraphRunnerService] ✅ Successfully created and configured agent: {node.name}"
        )
        return agent_instance

    def _configure_agent_services(self, agent: Any) -> None:
        """
        Configure services using clean protocol checking.

        This method now supports both AgentMap core services and host-defined services.
        Host services are configured after core services to ensure proper layering.

        Args:
            agent: Agent instance to configure services for
        """
        from agentmap.services.protocols import (
            CheckpointCapableAgent,
            LLMCapableAgent,
            OrchestrationCapableAgent,
            PromptCapableAgent,
            StorageCapableAgent,
        )

        # Configure core AgentMap services first
        core_services_configured = 0

        if isinstance(agent, LLMCapableAgent):
            agent.configure_llm_service(self.llm_service)
            self.logger.debug(
                f"[GraphRunnerService] ✅ Configured LLM service for {agent.name}"
            )
            core_services_configured += 1

        if isinstance(agent, StorageCapableAgent):
            agent.configure_storage_service(self.storage_service_manager)
            self.logger.debug(
                f"[GraphRunnerService] ✅ Configured storage service for {agent.name}"
            )
            core_services_configured += 1

        if isinstance(agent, PromptCapableAgent):
            # Check if agent has prompt_manager_service (either from constructor or post-construction)
            has_prompt_service = (
                hasattr(agent, "prompt_manager_service")
                and agent.prompt_manager_service is not None
            )

            if has_prompt_service:
                self.logger.debug(
                    f"[GraphRunnerService] Agent {agent.name} has prompt service available"
                )
            elif self.prompt_manager_service:
                # Try post-construction configuration if service is available
                agent.configure_prompt_service(self.prompt_manager_service)
                self.logger.debug(
                    f"[GraphRunnerService] ✅ Configured prompt service for {agent.name}"
                )
                core_services_configured += 1
            else:
                self.logger.debug(
                    f"[GraphRunnerService] Agent {agent.name} will use fallback prompt handling (no service available)"
                )

        if isinstance(agent, CheckpointCapableAgent):
            if (
                hasattr(self, "graph_checkpoint_service")
                and self.graph_checkpoint_service
            ):
                agent.configure_checkpoint_service(self.graph_checkpoint_service)
                self.logger.debug(
                    f"[GraphRunnerService] ✅ Configured checkpoint service for {agent.name}"
                )
                core_services_configured += 1
            else:
                self.logger.debug(
                    f"[GraphRunnerService] Graph checkpoint service not available for {agent.name}"
                )

        if isinstance(agent, OrchestrationCapableAgent):
            if self.orchestrator_service:
                agent.configure_orchestrator_service(self.orchestrator_service)
                self.logger.debug(
                    f"[GraphRunnerService] ✅ Configured orchestrator service for {agent.name}"
                )
                core_services_configured += 1
            else:
                self.logger.debug(
                    f"[GraphRunnerService] Orchestrator service not available for {agent.name}"
                )

        # Future services - ready for when these services are available:
        # if isinstance(agent, VectorCapableAgent):
        #     agent.configure_vector_service(self.vector_service)
        #     self.logger.debug(f"[GraphRunnerService] ✅ Configured vector service for {agent.name}")
        #
        # if isinstance(agent, DatabaseCapableAgent):
        #     agent.configure_database_service(self.database_service)
        #     self.logger.debug(f"[GraphRunnerService] ✅ Configured database service for {agent.name}")

        # Configure host-defined services after core services
        host_services_configured = self._configure_host_services(agent)

        # Log summary of service configuration
        total_configured = core_services_configured + host_services_configured
        if total_configured > 0:
            self.logger.debug(
                f"[GraphRunnerService] Total services configured for {agent.name}: {total_configured} (core: {core_services_configured}, host: {host_services_configured})"
            )
        else:
            self.logger.debug(
                f"[GraphRunnerService] No services configured for {agent.name} (agent does not implement service protocols)"
            )

    def _configure_host_services(self, agent: Any) -> int:
        """
        Configure host-defined services using dynamic protocol discovery.

        This method extends the existing service injection pattern to support
        host application services that are dynamically discovered and registered.

        Args:
            agent: Agent instance to configure host services for

        Returns:
            Number of host services successfully configured
        """
        if not self._host_services_available:
            self.logger.debug(
                f"[GraphRunnerService] Host services not available for {agent.name}"
            )
            return 0

        if not self.config.is_host_application_enabled():
            self.logger.debug(
                f"[GraphRunnerService] Host application support disabled for {agent.name}"
            )
            return 0

        try:
            # Delegate to HostProtocolConfigurationService
            configured_count = (
                self.host_protocol_configuration.configure_host_protocols(agent)
            )

            if configured_count > 0:
                self.logger.debug(
                    f"[GraphRunnerService] ✅ Configured {configured_count} host services for {agent.name}"
                )
            else:
                self.logger.debug(
                    f"[GraphRunnerService] Agent {agent.name} does not implement host protocols"
                )

            return configured_count

        except Exception as e:
            self.logger.error(
                f"[GraphRunnerService] ❌ Failed to configure host services for {agent.name}: {e}"
            )
            # Graceful degradation - continue without host services
            return 0

    def get_host_service_status(self, agent: Any) -> Dict[str, Any]:
        """
        Get status of host service injection for debugging and monitoring.

        Args:
            agent: Agent instance to check

        Returns:
            Dictionary with host service status information
        """
        status = {
            "agent_name": getattr(agent, "name", "unknown"),
            "host_services_available": self._host_services_available,
            "host_application_enabled": (
                self.config.is_host_application_enabled() if self.config else False
            ),
            "protocols_implemented": [],
            "services_configured": 0,
            "error": None,
        }

        if not self._host_services_available:
            status["error"] = "HostProtocolConfigurationService not available"
            return status

        if not self.config.is_host_application_enabled():
            status["error"] = "Host application support disabled"
            return status

        try:
            # Use HostProtocolConfigurationService to get status
            config_status = self.host_protocol_configuration.get_configuration_status(
                agent
            )

            # Update status with configuration details
            status["protocols_implemented"] = config_status.get(
                "configuration_potential", []
            )
            status["services_configured"] = config_status.get("summary", {}).get(
                "configuration_ready", 0
            )

            # Add service summary to status
            status["registry_stats"] = {
                "total_services": config_status.get("summary", {}).get(
                    "total_services_available", 0
                ),
                "total_protocols": config_status.get("summary", {}).get(
                    "total_protocols_implemented", 0
                ),
            }

        except Exception as e:
            status["error"] = str(e)

        return status

    def _validate_agent_configuration(self, agent_instance, node) -> None:
        """
        Validate that an agent instance is properly configured.

        Args:
            agent_instance: Agent instance to validate
            node: Node definition for validation context

        Raises:
            ValueError: If agent configuration is invalid
        """
        self.logger.debug(
            f"[GraphRunnerService] Validating agent configuration for: {node.name}"
        )

        # Basic validation
        if not hasattr(agent_instance, "name") or not agent_instance.name:
            raise ValueError(f"Agent {node.name} missing required 'name' attribute")

        if not hasattr(agent_instance, "run"):
            raise ValueError(f"Agent {node.name} missing required 'run' method")

        # Validate service configuration using new protocol pattern
        from agentmap.services.protocols import (
            LLMCapableAgent,
            PromptCapableAgent,
            StorageCapableAgent,
        )

        if isinstance(agent_instance, LLMCapableAgent):
            # Check that LLM service was properly configured
            try:
                # This will raise if service not configured
                _ = agent_instance.llm_service
                self.logger.debug(
                    f"[GraphRunnerService] LLM service properly configured for {node.name}"
                )
            except ValueError:
                raise ValueError(
                    f"LLM agent {node.name} missing required LLM service configuration"
                )

        if isinstance(agent_instance, StorageCapableAgent):
            # Check that storage service was properly configured
            try:
                # This will raise if service not configured
                _ = agent_instance.storage_service
                self.logger.debug(
                    f"[GraphRunnerService] Storage service properly configured for {node.name}"
                )
            except ValueError:
                raise ValueError(
                    f"Storage agent {node.name} missing required storage service configuration"
                )

        if isinstance(agent_instance, PromptCapableAgent):
            # Check that prompt service is working if agent supports it
            has_prompt_service = (
                hasattr(agent_instance, "prompt_manager_service")
                and agent_instance.prompt_manager_service is not None
            )

            if has_prompt_service:
                self.logger.debug(
                    f"[GraphRunnerService] Prompt service available for {node.name}"
                )
                # Verify prompt resolution is working
                try:
                    if hasattr(agent_instance, "resolved_prompt"):
                        self.logger.debug(
                            f"[GraphRunnerService] Prompt resolution working for {node.name}"
                        )
                except Exception as e:
                    self.logger.warning(
                        f"[GraphRunnerService] Prompt resolution issue for {node.name}: {e}"
                    )
            else:
                self.logger.debug(
                    f"[GraphRunnerService] Agent {node.name} using fallback prompt handling"
                )

        self.logger.debug(
            f"[GraphRunnerService] ✅ Agent configuration valid for: {node.name}"
        )

    def _resolve_agent_class(self, agent_type: str):
        """
        Resolve agent class by type using AgentFactory.

        Args:
            agent_type: Type of agent to resolve

        Returns:
            Agent class

        Raises:
            AgentInitializationError: If agent cannot be resolved
        """
        self.logger.debug(
            f"[GraphRunnerService] Resolving agent class for type: {agent_type}"
        )

        from agentmap.exceptions import AgentInitializationError

        agent_type_lower = agent_type.lower() if agent_type else ""

        # Handle empty or None agent_type - default to DefaultAgent
        if not agent_type or agent_type_lower == "none":
            self.logger.debug(
                "[GraphRunnerService] Empty or None agent type, defaulting to DefaultAgent"
            )
            from agentmap.agents.builtins.default_agent import DefaultAgent

            return DefaultAgent

        try:
            # Use AgentFactory for resolution with full dependency validation
            agent_class = self.agent_factory.resolve_agent_class(agent_type)
            self.logger.debug(
                f"[GraphRunnerService] Successfully resolved {agent_type} to {agent_class.__name__}"
            )
            return agent_class

        except ValueError as e:
            # AgentFactory handles all dependency checking, so we just need to handle resolution failures
            self.logger.error(
                f"[GraphRunnerService] Failed to resolve agent '{agent_type}': {e}"
            )

            # Try to load custom agent as fallback
            try:
                custom_agent_class = self._try_load_custom_agent(agent_type)
                if custom_agent_class:
                    self.logger.debug(
                        f"[GraphRunnerService] Resolved to custom agent: {custom_agent_class.__name__}"
                    )
                    return custom_agent_class
            except Exception as custom_error:
                self.logger.debug(
                    f"[GraphRunnerService] Custom agent fallback failed: {custom_error}"
                )

            # Final fallback - raise the original error from AgentFactory
            raise AgentInitializationError(
                f"Cannot resolve agent type '{agent_type}': {str(e)}"
            )

    def _try_load_custom_agent(self, agent_type: str):
        """
        Try to load a custom agent as fallback.

        Args:
            agent_type: Type of agent to load

        Returns:
            Agent class or None if not found

        Raises:
            ImportError: If custom agent loading fails
        """
        # Try to load from custom agents path
        custom_agents_path = self.config.get_custom_agents_path()
        self.logger.debug(
            f"[GraphRunnerService] Trying custom agent path: {custom_agents_path}"
        )

        # Add custom agents path to sys.path if not already present
        import sys

        custom_agents_path_str = str(custom_agents_path)
        if custom_agents_path_str not in sys.path:
            sys.path.insert(0, custom_agents_path_str)

        # Try to import the custom agent
        modname = f"{agent_type.lower()}_agent"
        classname = f"{agent_type}Agent"
        module = __import__(modname, fromlist=[classname])
        self.logger.debug(
            f"[GraphRunnerService] Imported custom agent module: {modname}"
        )
        agent_class = getattr(module, classname)
        return agent_class

    def get_agent_resolution_status(self, graph_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get comprehensive status of agent resolution for a graph definition.

        Uses AgentFactory for accurate capability assessment.

        Args:
            graph_def: Graph definition to analyze

        Returns:
            Dictionary with detailed agent resolution status
        """
        status = {
            "total_nodes": len(graph_def),
            "agent_types": {},
            "resolution_summary": {
                "resolvable": 0,
                "missing_dependencies": 0,
                "custom_agents": 0,
                "builtin_agents": 0,
                "llm_agents": 0,
                "storage_agents": 0,
            },
            "issues": [],
        }

        for node_name, node in graph_def.items():
            agent_type = node.agent_type or "Default"

            # Get detailed info using AgentFactory
            agent_info = self.agent_factory.get_agent_resolution_context(agent_type)

            # Track agent type usage
            if agent_type not in status["agent_types"]:
                status["agent_types"][agent_type] = {
                    "count": 0,
                    "nodes": [],
                    "info": agent_info,
                }

            status["agent_types"][agent_type]["count"] += 1
            status["agent_types"][agent_type]["nodes"].append(node_name)

            # Update summary counts
            if agent_info["resolvable"]:
                status["resolution_summary"]["resolvable"] += 1
            else:
                status["resolution_summary"]["missing_dependencies"] += 1
                status["issues"].append(
                    {
                        "node": node_name,
                        "agent_type": agent_type,
                        "issue": "missing_dependencies",
                        "missing_deps": agent_info.get("missing_dependencies", []),
                        "resolution_error": agent_info.get("resolution_error"),
                    }
                )

        # Add overall status
        status["overall_status"] = {
            "all_resolvable": status["resolution_summary"]["missing_dependencies"] == 0,
            "has_issues": len(status["issues"]) > 0,
            "unique_agent_types": len(status["agent_types"]),
            "resolution_rate": (
                status["resolution_summary"]["resolvable"] / status["total_nodes"]
                if status["total_nodes"] > 0
                else 0
            ),
        }

        return status

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the simplified facade service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "GraphRunnerService",
            "architecture": "simplified_facade",
            "specialized_services": {
                "graph_definition_service_available": self.graph_definition is not None,
                "graph_execution_service_available": self.graph_execution is not None,
                "compilation_service_available": self.compilation is not None,
                "graph_bundle_service_available": self.graph_bundle_service is not None,
            },
            "supporting_services": {
                "agent_factory_available": self.agent_factory is not None,
                "llm_service_available": self.llm_service is not None,
                "storage_service_manager_available": self.storage_service_manager
                is not None,
                "node_registry_available": self.node_registry is not None,
                "dependency_checker_available": self.dependency_checker is not None,
                "graph_assembly_service_available": self.graph_assembly_service
                is not None,
                "prompt_manager_service_available": self.prompt_manager_service
                is not None,
            },
            "infrastructure_services": {
                "config_available": self.config is not None,
                "execution_tracking_service_available": self.execution_tracking_service
                is not None,
                "execution_policy_service_available": self.execution_policy_service
                is not None,
                "state_adapter_service_available": self.state_adapter_service
                is not None,
            },
            "dependencies_initialized": all(
                [
                    self.graph_definition is not None,
                    self.graph_execution is not None,
                    self.compilation is not None,
                    self.graph_bundle_service is not None,
                    self.agent_factory is not None,
                    self.llm_service is not None,
                    self.storage_service_manager is not None,
                    self.node_registry is not None,
                    self.dependency_checker is not None,
                    self.graph_assembly_service is not None,
                    self.config is not None,
                    self.execution_tracking_service is not None,
                    self.execution_policy_service is not None,
                    self.state_adapter_service is not None,
                    # Note: prompt_manager_service and application_container are optional, so not included in required dependencies check
                ]
            ),
            "host_services": {
                "container_available": self._host_services_available,
                "host_application_enabled": (
                    self.config.is_host_application_enabled() if self.config else False
                ),
                "protocol_discovery_available": (
                    self._host_services_available
                    and self.config.is_host_application_enabled()
                    if self.config
                    else False
                ),
            },
            "capabilities": {
                "graph_resolution": True,
                "agent_resolution": True,
                "service_injection": True,
                "host_service_injection": self._host_services_available,
                "execution_delegation": True,
                "precompiled_graphs": True,
                "autocompilation": True,
                "memory_building": True,
                "agent_validation": True,
                "dependency_checking": True,
                "facade_pattern": True,
                "prompt_resolution": self.prompt_manager_service is not None,
                "dynamic_protocol_discovery": self._host_services_available,
            },
            "delegation_methods": [
                "run_graph -> GraphExecutionService",
                "run_from_compiled -> GraphExecutionService.execute_compiled_graph",
                "run_from_csv_direct -> GraphDefinitionService + GraphExecutionService",
                "compilation -> CompilationService",
                "graph_loading -> GraphDefinitionService",
                "agent_resolution -> AgentFactoryService.resolve_agent_class",
                "service_injection -> protocol-based in _configure_agent_services",
                "host_service_injection -> HostProtocolConfigurationService.configure_host_protocols",
            ],
            "complexity_reduction": {
                "execution_logic_extracted": True,
                "delegation_based": True,
                "single_responsibility": True,
                "clean_separation": True,
            },
        }

    def _log_service_status(self) -> None:
        """Log the status of all injected services for debugging."""
        status = self.get_service_info()
        self.logger.debug(
            f"[GraphRunnerService] Simplified facade service status: {status}"
        )

        if not status["dependencies_initialized"]:
            missing_deps = []
            if not self.graph_definition:
                missing_deps.append("graph_definition_service")
            if not self.graph_execution:
                missing_deps.append("graph_execution_service")
            if not self.compilation:
                missing_deps.append("compilation_service")
            if not self.agent_factory:
                missing_deps.append("agent_factory_service")
            # ... additional dependency checks as needed

            self.logger.warning(
                f"[GraphRunnerService] Missing dependencies: {missing_deps}"
            )
        else:
            self.logger.info(
                "[GraphRunnerService] All dependencies initialized successfully"
            )

        # Log host service status
        if status["host_services"]["container_available"]:
            if status["host_services"]["host_application_enabled"]:
                self.logger.info(
                    "[GraphRunnerService] Host service injection enabled and available"
                )
            else:
                self.logger.debug(
                    "[GraphRunnerService] Host service container available but host application disabled"
                )
        else:
            self.logger.debug(
                "[GraphRunnerService] Host service injection not available (container not injected)"
            )
