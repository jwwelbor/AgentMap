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
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.graph_definition_service import GraphDefinitionService
from agentmap.services.graph_execution_service import GraphExecutionService
from agentmap.services.compilation_service import CompilationService
from agentmap.services.graph_bundle_service import GraphBundleService
from agentmap.services.dependency_checker_service import DependencyCheckerService
# Direct imports from migrated services in src_new
from agentmap.services.logging_service import LoggingService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.node_registry_service import NodeRegistryService
from agentmap.services.llm_service import LLMService
from agentmap.services.storage.manager import StorageServiceManager
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.execution_policy_service import ExecutionPolicyService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.graph_assembly_service import GraphAssemblyService


@dataclass
class RunOptions:
    """Options for graph execution."""
    initial_state: Optional[Any] = None # could by pydantic or dict
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
        llm_service: LLMService,
        storage_service_manager: StorageServiceManager,
        node_registry_service: NodeRegistryService,
        logging_service: LoggingService,
        app_config_service: AppConfigService,
        execution_tracking_service: ExecutionTrackingService,
        execution_policy_service: ExecutionPolicyService,
        state_adapter_service: StateAdapterService,
        dependency_checker_service: DependencyCheckerService,
        graph_assembly_service: GraphAssemblyService
    ):
        """Initialize facade service with specialized service dependencies.
        
        Args:
            graph_definition_service: Service for building graphs from CSV
            graph_execution_service: Service for execution orchestration
            compilation_service: Service for graph compilation
            graph_bundle_service: Service for graph bundle operations
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
        """
        # Core specialized services
        self.graph_definition = graph_definition_service
        self.graph_execution = graph_execution_service
        self.compilation = compilation_service
        self.graph_bundle_service = graph_bundle_service
        
        # Supporting services for agent resolution and injection
        self.llm_service = llm_service
        self.storage_service_manager = storage_service_manager
        self.node_registry = node_registry_service
        self.dependency_checker = dependency_checker_service
        self.graph_assembly_service = graph_assembly_service
        
        # Infrastructure services
        self.logger = logging_service.get_class_logger(self)
        self.config = app_config_service
        
        # Services used for delegation to GraphExecutionService
        self.execution_tracking_service = execution_tracking_service
        self.execution_policy_service = execution_policy_service
        self.state_adapter_service = state_adapter_service
        
        self.logger.info("[GraphRunnerService] Initialized as simplified facade")
        self._log_service_status()
    
    def get_default_options(self) -> RunOptions:
        """Get default run options from configuration."""
        options = RunOptions()
        options.initial_state = None # could by pydantic or dict
        options.autocompile = self.config.get_value("autocompile", False) 
        options.csv_path = self.config.get_csv_path()
        options.validate_before_run = False
        options.track_execution = self.config.get_execution_config().get("track_execution", True)
        options.force_compilation = False
        options.execution_mode = "standard"  # "standard", "debug", "minimal"
        return options

    def run_graph(
        self, 
        graph_name: str, 
        options: Optional[RunOptions] = None
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
                self.logger.debug(f"[GraphRunnerService] Delegating compiled graph execution")
                return self.graph_execution.execute_compiled_graph(
                    bundle_path=resolved_execution["bundle_path"],
                    state=state
                )
            elif resolved_execution["type"] == "definition":
                self.logger.debug(f"[GraphRunnerService] Delegating definition graph execution")
                return self.graph_execution.execute_from_definition(
                    graph_def=resolved_execution["graph_def"],
                    state=state
                )
            else:
                raise ValueError(f"Unknown resolution type: {resolved_execution['type']}")
            
        except Exception as e:
            self.logger.error(f"❌ GRAPH EXECUTION FAILED: '{graph_name}'")
            self.logger.error(f"[GraphRunnerService] Error: {str(e)}")
            
            # Create error result using same pattern as GraphExecutionService
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=state,  # Return original state on error
                execution_summary=None,
                execution_time=0.0,
                source_info=None,
                error=str(e)
            )
            
            return execution_result
    
    def run_from_compiled(
        self, 
        graph_path: Path, 
        options: Optional[RunOptions] = None
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
        
        self.logger.info(f"[GraphRunnerService] Running from compiled graph: {graph_path}")
        
        # Delegate directly to GraphExecutionService
        return self.graph_execution.execute_compiled_graph(
            bundle_path=graph_path,
            state=state
        )
    
    def run_from_csv_direct(
        self, 
        csv_path: Path, 
        graph_name: str, 
        options: Optional[RunOptions] = None
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
        options.autocompile = False
        
        # Initialize state
        state = options.initial_state or {}
        
        self.logger.info(f"[GraphRunnerService] Running directly from CSV: {csv_path}, graph: {graph_name}")
        
        try:
            # Step 1: Load graph definition using GraphDefinitionService
            graph_def, resolved_graph_name = self._load_graph_definition_for_execution(csv_path, graph_name)
            
            # Step 2: Delegate execution to GraphExecutionService
            return self.graph_execution.execute_from_definition(
                graph_def=graph_def,
                state=state
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
                execution_time=0.0,
                source_info="memory",
                error=str(e)
            )
            
            return execution_result
    
    def _resolve_graph_for_execution(self, graph_name: str, options: RunOptions) -> Dict[str, Any]:
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
        self.logger.debug(f"[GraphRunnerService] Resolving graph for execution: {graph_name}")
        
        # Path 1: Try to load precompiled graph
        compiled_bundle_path = self._find_compiled_graph(graph_name)
        if compiled_bundle_path:
            self.logger.debug(f"[GraphRunnerService] Found precompiled graph: {compiled_bundle_path}")
            return {
                "type": "compiled",
                "bundle_path": compiled_bundle_path
            }
        
        # Path 2: Try autocompilation if enabled
        autocompile = options.autocompile
        if autocompile is None:
            autocompile = self.config.get_value("autocompile", False)
        
        if autocompile and graph_name:
            self.logger.debug(f"[GraphRunnerService] Attempting autocompilation for: {graph_name}")
            autocompiled_path = self._autocompile_graph(graph_name, options)
            if autocompiled_path:
                self.logger.debug(f"[GraphRunnerService] Autocompiled graph: {autocompiled_path}")
                return {
                    "type": "compiled",
                    "bundle_path": autocompiled_path
                }
        
        # Path 3: Build graph definition for in-memory execution
        self.logger.debug(f"[GraphRunnerService] Building graph definition for memory execution: {graph_name}")
        csv_path = options.csv_path or self.config.get_csv_path()
        graph_def, resolved_graph_name = self._load_graph_definition_for_execution(csv_path, graph_name)
        
        return {
            "type": "definition",
            "graph_def": graph_def
        }
    
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
            self.logger.debug(f"[GraphRunnerService] Found compiled graph: {compiled_path}")
            return compiled_path
        
        self.logger.debug(f"[GraphRunnerService] No compiled graph found: {compiled_path}")
        return None
    
    def _autocompile_graph(self, graph_name: str, options: RunOptions) -> Optional[Path]:
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
                include_source=True
            )
            
            # Try auto-compile if needed
            csv_path = options.csv_path or self.config.get_csv_path()
            result = self.compilation.auto_compile_if_needed(graph_name, csv_path, compilation_options)
            
            if result and result.success:
                self.logger.debug(f"[GraphRunnerService] Autocompilation successful for: {graph_name}")
                # Return path to the newly compiled graph
                return self.config.get_compiled_graphs_path() / f"{graph_name}.pkl"
            else:
                self.logger.warning(f"[GraphRunnerService] Autocompilation failed for: {graph_name}")
                if result:
                    self.logger.warning(f"[GraphRunnerService] Compilation error: {result.error}")
                return None
                
        except Exception as e:
            self.logger.error(f"[GraphRunnerService] Autocompilation error for {graph_name}: {e}")
            return None
    
    def _load_graph_definition_for_execution(self, csv_path: Path, graph_name: Optional[str]) -> tuple:
        """
        Load and prepare graph definition for execution.
        
        Uses GraphDefinitionService and prepares the definition with agent instances.
        
        Args:
            csv_path: Path to CSV file
            graph_name: Optional specific graph name to load
            
        Returns:
            Tuple of (prepared_graph_def, resolved_graph_name)
        """
        self.logger.debug(f"[GraphRunnerService] Loading graph definition for execution: {csv_path}")
        
        # Step 1: Load graph definition using GraphDefinitionService
        if graph_name:
            # Load specific graph
            graph_domain_model = self.graph_definition.build_from_csv(csv_path, graph_name)
            resolved_graph_name = graph_name
        else:
            # Load first graph available
            all_graphs = self.graph_definition.build_all_from_csv(csv_path)
            if not all_graphs:
                raise ValueError(f"No graphs found in CSV file: {csv_path}")
            
            resolved_graph_name = next(iter(all_graphs))
            graph_domain_model = all_graphs[resolved_graph_name]
            
            self.logger.debug(f"[GraphRunnerService] Using first graph: {resolved_graph_name}")
        
        # Step 2: Convert to execution format and prepare with agent instances
        prepared_graph_def = self._prepare_graph_definition_for_execution(
            graph_domain_model, resolved_graph_name
        )
        
        return prepared_graph_def, resolved_graph_name
    
    def _prepare_graph_definition_for_execution(self, graph_domain_model: Any, graph_name: str) -> Dict[str, Any]:
        """
        Prepare graph definition with agent instances for execution.
        
        Converts domain model to execution format and creates agent instances.
        
        Args:
            graph_domain_model: Graph domain model from GraphDefinitionService
            graph_name: Name of the graph for logging context
            
        Returns:
            Prepared graph definition ready for GraphExecutionService
        """
        self.logger.debug(f"[GraphRunnerService] Preparing graph definition for execution: {graph_name}")
        
        # Convert domain model to old format for compatibility
        graph_def = self._convert_domain_model_to_old_format(graph_domain_model)
        
        if not graph_def:
            raise ValueError(f"Invalid or empty graph definition for graph: {graph_name}")

        # Prepare node registry
        self.logger.debug(f"[GraphRunnerService] Preparing node registry for: {graph_name}")
        node_registry = self.node_registry.prepare_for_assembly(graph_def, graph_name)

        # Create and configure agent instances for each node
        for node in graph_def.values():
            agent_instance = self._create_agent_instance(node, graph_name)
            self._validate_agent_configuration(agent_instance, node)
            node.context["instance"] = agent_instance

        self.logger.debug(f"[GraphRunnerService] Graph definition prepared for execution: {graph_name}")
        return graph_def
    
    def _convert_domain_model_to_old_format(self, graph) -> Dict[str, Any]:
        """
        Convert Graph domain model to old format for compatibility.
        
        Args:
            graph: Graph domain model
            
        Returns:
            Dictionary in old GraphBuilder format
        """
        old_format = {}
        
        for node_name, node in graph.nodes.items():
            # Convert Node to old format compatible with existing infrastructure
            old_format[node_name] = type('Node', (), {
                'name': node.name,
                'context': node.context,
                'agent_type': node.agent_type,
                'inputs': node.inputs,
                'output': node.output,
                'prompt': node.prompt,
                'description': node.description,
                'edges': node.edges
            })()
        
        return old_format
    
    def _create_agent_instance(self, node, graph_name: str):
        """
        Create and configure an agent instance for a node.
        
        Handles agent class resolution, instantiation, and service injection.
        
        Args:
            node: Node definition with agent configuration
            graph_name: Name of the graph being built
            
        Returns:
            Fully configured agent instance ready for graph assembly
        """
        self.logger.debug(f"[GraphRunnerService] Creating agent instance for node: {node.name} (type: {node.agent_type})")
        
        # Step 1: Resolve agent class
        agent_cls = self._resolve_agent_class(node.agent_type)
        
        # Step 2: Create context with input/output field information
        context = {
            "input_fields": node.inputs,
            "output_field": node.output,
            "description": node.description or ""
        }
        
        self.logger.debug(f"[GraphRunnerService] Instantiating {agent_cls.__name__} as node '{node.name}'")
        
        # Step 3: Create agent instance
        agent_instance = agent_cls(
            name=node.name, 
            prompt=node.prompt or "", 
            context=context, 
            logger=self.logger, 
            execution_tracker=None  # Execution tracking will be provided at runtime
        )
        
        # Step 4: Inject all required services
        self._inject_services_into_agent(agent_instance, node, graph_name)
        
        self.logger.debug(f"[GraphRunnerService] ✅ Successfully created and configured agent: {node.name}")
        return agent_instance
    
    def _inject_services_into_agent(self, agent_instance, node, graph_name: str) -> None:
        """
        Inject all required services into an agent instance.
        
        Handles LLM service injection, storage service injection, and any other
        service injection requirements based on agent capabilities.
        
        Args:
            agent_instance: Agent instance to inject services into
            node: Node definition for context
            graph_name: Name of the graph for logging context
        """
        self.logger.debug(f"[GraphRunnerService] Injecting services into agent: {node.name}")
        
        # Inject LLM service if agent requires it
        self._inject_llm_service(agent_instance, node.name)
        
        # Inject storage services if agent requires them
        self._inject_storage_services(agent_instance, node.name)
        
        self.logger.debug(f"[GraphRunnerService] ✅ Service injection complete for agent: {node.name}")
    
    def _inject_llm_service(self, agent_instance, node_name: str) -> None:
        """
        Inject LLM service if the agent requires it.
        
        Args:
            agent_instance: Agent instance to potentially inject LLM service into
            node_name: Name of the node for logging
        """
        from agentmap.services import LLMServiceUser
        
        if isinstance(agent_instance, LLMServiceUser):
            agent_instance.llm_service = self.llm_service
            self.logger.debug(f"[GraphRunnerService] ✅ Injected LLM service into {node_name}")
        else:
            self.logger.debug(f"[GraphRunnerService] Agent {node_name} does not require LLM service")
    
    def _inject_storage_services(self, agent_instance, node_name: str) -> None:
        """
        Inject storage services if the agent requires them.
        
        Args:
            agent_instance: Agent instance to potentially inject storage services into
            node_name: Name of the node for logging
        """
        from agentmap.services.storage.injection import inject_storage_services, requires_storage_services
        
        if requires_storage_services(agent_instance):
            inject_storage_services(agent_instance, self.storage_service_manager, self.logger)
            self.logger.debug(f"[GraphRunnerService] ✅ Injected storage services into {node_name}")
        else:
            self.logger.debug(f"[GraphRunnerService] Agent {node_name} does not require storage services")
    
    def _validate_agent_configuration(self, agent_instance, node) -> None:
        """
        Validate that an agent instance is properly configured.
        
        Args:
            agent_instance: Agent instance to validate
            node: Node definition for validation context
            
        Raises:
            ValueError: If agent configuration is invalid
        """
        self.logger.debug(f"[GraphRunnerService] Validating agent configuration for: {node.name}")
        
        # Basic validation
        if not hasattr(agent_instance, 'name') or not agent_instance.name:
            raise ValueError(f"Agent {node.name} missing required 'name' attribute")
        
        if not hasattr(agent_instance, 'run'):
            raise ValueError(f"Agent {node.name} missing required 'run' method")
        
        # Validate service injection requirements are met
        from agentmap.services import LLMServiceUser
        if isinstance(agent_instance, LLMServiceUser):
            if not hasattr(agent_instance, 'llm_service') or agent_instance.llm_service is None:
                raise ValueError(f"LLM agent {node.name} missing required LLM service injection")
        
        from agentmap.services.storage.injection import requires_storage_services
        if requires_storage_services(agent_instance):
            # Check that storage services were properly injected
            # This is a simplified check - full validation would inspect specific services
            if not hasattr(agent_instance, '_storage_services_injected'):
                self.logger.warning(f"Storage agent {node.name} may be missing storage service injection")
        
        self.logger.debug(f"[GraphRunnerService] ✅ Agent configuration valid for: {node.name}")
    
    def _resolve_agent_class(self, agent_type: str):
        """
        Resolve agent class by type with fallback to custom agents.
        
        Wraps the existing resolve_agent_class functionality while using DependencyCheckerService.
        
        Args:
            agent_type: Type of agent to resolve
            
        Returns:
            Agent class
        """
        self.logger.debug(f"[GraphRunnerService] Resolving agent class for type: {agent_type}")
        
        from agentmap.agents import get_agent_class
        from agentmap.exceptions import AgentInitializationError
        
        agent_type_lower = agent_type.lower() if agent_type else ""
        
        # Handle empty or None agent_type - default to DefaultAgent
        if not agent_type or agent_type_lower == "none":
            self.logger.debug("[GraphRunnerService] Empty or None agent type, defaulting to DefaultAgent")
            from agentmap.agents.builtins.default_agent import DefaultAgent
            return DefaultAgent
        
        # Check LLM agent types using DependencyCheckerService
        if agent_type_lower in ("openai", "anthropic", "google", "gpt", "claude", "gemini", "llm"):
            # Use dependency checker to validate LLM dependencies
            has_deps, missing = self.dependency_checker.check_llm_dependencies()
            
            if not has_deps:
                missing_str = ", ".join(missing) if missing else "required dependencies"
                installation_guide = self.dependency_checker.get_installation_guide("llm", "llm")
                raise ImportError(
                    f"LLM agent '{agent_type}' requested but LLM dependencies are not available. "
                    f"Missing: {missing_str}. Install with: {installation_guide}"
                )
            
            # Handle base LLM case
            if agent_type_lower == "llm":
                agent_class = get_agent_class("llm")
                if agent_class:
                    return agent_class
                raise ImportError(
                    "Base LLM agent requested but not available. "
                    "Install with: pip install agentmap[llm]"
                )
            
            # Check specific provider using DependencyCheckerService
            provider = agent_type_lower
            if provider in ("gpt", "claude", "gemini"):
                provider = {"gpt": "openai", "claude": "anthropic", "gemini": "google"}[provider]
            
            # Validate specific provider
            has_provider_deps, missing_provider = self.dependency_checker.check_llm_dependencies(provider)
            
            if not has_provider_deps:
                installation_guide = self.dependency_checker.get_installation_guide(provider, "llm")
                raise ImportError(
                    f"LLM agent '{agent_type}' requested but dependencies are not available. "
                    f"Missing: {', '.join(missing_provider)}. Install with: {installation_guide}"
                )
            
            # Get the agent class
            agent_class = get_agent_class(agent_type)
            if agent_class:
                return agent_class
            
            raise ImportError(
                f"LLM agent '{agent_type}' requested. Dependencies are available "
                f"but agent class could not be loaded. This might be a registration issue."
            )
        
        # Check storage agent types using DependencyCheckerService
        if agent_type_lower in ("csv_reader", "csv_writer", "json_reader", "json_writer", 
                                "file_reader", "file_writer", "vector_reader", "vector_writer"):
            # Use dependency checker to validate storage dependencies
            has_deps, missing = self.dependency_checker.check_storage_dependencies()
            
            if not has_deps:
                missing_str = ", ".join(missing) if missing else "required dependencies"
                installation_guide = self.dependency_checker.get_installation_guide("storage", "storage")
                raise ImportError(
                    f"Storage agent '{agent_type}' requested but storage dependencies are not installed. "
                    f"Missing: {missing_str}. Install with: {installation_guide}"
                )
        
        # Get agent class from registry
        agent_class = get_agent_class(agent_type)
        if agent_class:
            self.logger.debug(f"[GraphRunnerService] Using built-in agent class: {agent_class.__name__}")
            return agent_class
        
        # Try to load from custom agents path
        custom_agents_path = self.config.get_custom_agents_path()
        self.logger.debug(f"[GraphRunnerService] Custom agents path: {custom_agents_path}")
        
        # Add custom agents path to sys.path if not already present
        import sys
        custom_agents_path_str = str(custom_agents_path)
        if custom_agents_path_str not in sys.path:
            sys.path.insert(0, custom_agents_path_str)
        
        # Try to import the custom agent
        try:
            modname = f"{agent_type.lower()}_agent"
            classname = f"{agent_type}Agent"
            module = __import__(modname, fromlist=[classname])
            self.logger.debug(f"[GraphRunnerService] Imported custom agent module: {modname}")
            self.logger.debug(f"[GraphRunnerService] Using custom agent class: {classname}")
            agent_class = getattr(module, classname)
            return agent_class
        
        except (ImportError, AttributeError) as e:
            error_message = f"[GraphRunnerService] Failed to import custom agent '{agent_type}': {e}"
            self.logger.error(error_message)
            raise AgentInitializationError(error_message)
    
    def get_agent_resolution_status(self, graph_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get comprehensive status of agent resolution for a graph definition.
        
        Uses protocol-based detection for accurate capability assessment.
        
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
                "storage_agents": 0
            },
            "issues": []
        }
        
        for node_name, node in graph_def.items():
            agent_type = node.agent_type or "Default"
            
            # Get detailed info about this agent type using existing resolution logic
            try:
                agent_class = self._resolve_agent_class(agent_type)
                agent_info = {
                    "agent_type": agent_type,
                    "agent_class": agent_class,
                    "dependencies_available": True,
                    "missing_dependencies": []
                }
            except Exception as e:
                agent_info = {
                    "agent_type": agent_type,
                    "agent_class": None,
                    "dependencies_available": False,
                    "missing_dependencies": [str(e)]
                }
            
            # Track agent type usage
            if agent_type not in status["agent_types"]:
                status["agent_types"][agent_type] = {
                    "count": 0,
                    "nodes": [],
                    "info": agent_info
                }
            
            status["agent_types"][agent_type]["count"] += 1
            status["agent_types"][agent_type]["nodes"].append(node_name)
            
            # Update summary counts
            if agent_info["dependencies_available"]:
                status["resolution_summary"]["resolvable"] += 1
            else:
                status["resolution_summary"]["missing_dependencies"] += 1
                status["issues"].append({
                    "node": node_name,
                    "agent_type": agent_type,
                    "issue": "missing_dependencies",
                    "missing_deps": agent_info["missing_dependencies"]
                })
        
        # Add overall status
        status["overall_status"] = {
            "all_resolvable": status["resolution_summary"]["missing_dependencies"] == 0,
            "has_issues": len(status["issues"]) > 0,
            "unique_agent_types": len(status["agent_types"]),
            "resolution_rate": status["resolution_summary"]["resolvable"] / status["total_nodes"] if status["total_nodes"] > 0 else 0
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
                "llm_service_available": self.llm_service is not None,
                "storage_service_manager_available": self.storage_service_manager is not None,
                "node_registry_available": self.node_registry is not None,
                "dependency_checker_available": self.dependency_checker is not None,
                "graph_assembly_service_available": self.graph_assembly_service is not None,
            },
            "infrastructure_services": {
                "config_available": self.config is not None,
                "execution_tracking_service_available": self.execution_tracking_service is not None,
                "execution_policy_service_available": self.execution_policy_service is not None,
                "state_adapter_service_available": self.state_adapter_service is not None,
            },
            "dependencies_initialized": all([
                self.graph_definition is not None,
                self.graph_execution is not None,
                self.compilation is not None,
                self.graph_bundle_service is not None,
                self.llm_service is not None,
                self.storage_service_manager is not None,
                self.node_registry is not None,
                self.dependency_checker is not None,
                self.graph_assembly_service is not None,
                self.config is not None,
                self.execution_tracking_service is not None,
                self.execution_policy_service is not None,
                self.state_adapter_service is not None
            ]),
            "capabilities": {
                "graph_resolution": True,
                "agent_resolution": True,
                "service_injection": True,
                "execution_delegation": True,
                "precompiled_graphs": True,
                "autocompilation": True,
                "memory_building": True,
                "agent_validation": True,
                "dependency_checking": True,
                "facade_pattern": True
            },
            "delegation_methods": [
                "run_graph -> GraphExecutionService",
                "run_from_compiled -> GraphExecutionService.execute_compiled_graph",
                "run_from_csv_direct -> GraphDefinitionService + GraphExecutionService",
                "compilation -> CompilationService",
                "graph_loading -> GraphDefinitionService"
            ],
            "complexity_reduction": {
                "execution_logic_extracted": True,
                "delegation_based": True,
                "single_responsibility": True,
                "clean_separation": True
            }
        }
    
    def _log_service_status(self) -> None:
        """Log the status of all injected services for debugging."""
        status = self.get_service_info()
        self.logger.debug(f"[GraphRunnerService] Simplified facade service status: {status}")
        
        if not status["dependencies_initialized"]:
            missing_deps = []
            if not self.graph_definition:
                missing_deps.append("graph_definition_service")
            if not self.graph_execution:
                missing_deps.append("graph_execution_service")
            if not self.compilation:
                missing_deps.append("compilation_service")
            # ... additional dependency checks as needed
            
            self.logger.warning(f"[GraphRunnerService] Missing dependencies: {missing_deps}")
        else:
            self.logger.info("[GraphRunnerService] All dependencies initialized successfully")
