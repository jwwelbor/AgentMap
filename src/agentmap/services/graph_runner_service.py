"""
GraphRunnerService for AgentMap.

Service that orchestrates complete graph execution by coordinating all other services
(GraphBuilderService, CompilationService, LLMService, etc.) to provide comprehensive
graph execution capabilities with tracking, error handling, and multiple execution modes.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.models.execution_result import ExecutionResult
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.graph_builder_service import GraphBuilderService
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


@dataclass
class RunOptions:
    """Options for graph execution."""
    initial_state: Optional[Dict[str, Any]] = None
    autocompile: Optional[bool] = None
    csv_path: Optional[Path] = None
    validate_before_run: bool = False
    track_execution: bool = True
    force_compilation: bool = False
    execution_mode: str = "standard"  # "standard", "debug", "minimal"


class GraphRunnerService:
    """
    Service for graph execution orchestration.
    
    Coordinates all services to provide complete graph execution capabilities:
    - Graph loading/building via GraphBuilderService  
    - Compilation management via CompilationService
    - Agent resolution and service injection
    - Execution tracking and result processing
    - Error handling and recovery
    
    This service extracts and orchestrates the complex logic from runner.py
    while maintaining all existing functionality and performance.
    """
    
    def __init__(
        self,
        graph_builder_service: GraphBuilderService,
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
        dependency_checker_service: DependencyCheckerService
    ):
        """Initialize service with dependency injection.
        
        Args:
            graph_builder_service: Service for building graphs from CSV
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
        """
        self.graph_builder = graph_builder_service
        self.compilation = compilation_service
        self.graph_bundle_service = graph_bundle_service
        self.llm_service = llm_service
        self.storage_service_manager = storage_service_manager
        self.node_registry = node_registry_service
        self.logger = logging_service.get_class_logger(self)
        self.config = app_config_service
        self.execution_tracking_service = execution_tracking_service
        self.execution_policy_service = execution_policy_service
        self.state_adapter_service = state_adapter_service
        self.dependency_checker = dependency_checker_service
        
        self.logger.info("[GraphRunnerService] Initialized with all dependencies")
        self._log_service_status()
    
    def run_graph(
        self, 
        graph_name: str, 
        options: Optional[RunOptions] = None
    ) -> ExecutionResult:
        """
        Main graph execution method.
        
        Orchestrates complete graph execution including:
        - Graph resolution (compiled/autocompiled/memory)
        - Agent resolution and service injection
        - Execution tracking and monitoring
        - Result processing and error handling
        
        Args:
            graph_name: Name of the graph to execute
            options: Execution options (uses defaults if None)
            
        Returns:
            ExecutionResult with complete execution details
        """
        import time
        import hashlib
        import threading
        
        # Initialize options with defaults
        if options is None:
            options = RunOptions()
        
        # Initialize state
        state = options.initial_state or {}
        
        # Create execution tracking
        execution_key = hashlib.md5(
            f"{graph_name}:{id(state)}:{options.csv_path}:{options.autocompile}".encode()
        ).hexdigest()
        
        self.logger.info(f"⭐ STARTING GRAPH: '{graph_name}'")
        self.logger.debug(f"[GraphRunnerService] Execution options: {options}")
        
        start_time = time.time()
        
        try:
            # Step 1: Resolve the graph using existing infrastructure
            self.logger.debug(f"[GraphRunnerService] Resolving graph: {graph_name}")
            compiled_graph, source_info, graph_def = self._resolve_graph(graph_name, options)
            
            self.logger.debug(f"[GraphRunnerService] Graph resolved via: {source_info}")
            
            # Step 2: Execute the graph with state management
            self.logger.debug(f"[GraphRunnerService] Executing graph: {graph_name}")
            
            # Initialize execution tracking using service factory
            execution_tracker = self.execution_tracking_service.create_tracker()
            
            # Execute the graph
            self.logger.debug(f"[GraphRunnerService] Initial state type: {type(state)}")
            self.logger.debug(f"[GraphRunnerService] Initial state keys: {list(state.keys()) if hasattr(state, 'keys') else 'N/A'}")
            
            # The core execution
            final_state = compiled_graph.invoke(state)
            
            self.logger.debug(f"[GraphRunnerService] Final state type: {type(final_state)}")
            self.logger.debug(f"[GraphRunnerService] Final state keys: {list(final_state.keys()) if hasattr(final_state, 'keys') else 'N/A'}")
            
            # Step 3: Process execution results with clean architecture
            execution_time = time.time() - start_time
            
            # Complete execution tracking (pure data collection)
            execution_tracker.complete_execution()
            summary = execution_tracker.get_summary()
            
            # Evaluate policy separately (business logic)
            graph_success = self.execution_policy_service.evaluate_success_policy(summary)
            
            # Update state with execution summary and policy result
            final_state = self.state_adapter_service.set_value(final_state, "__execution_summary", summary)
            final_state = self.state_adapter_service.set_value(final_state, "__policy_success", graph_success)
            
            # Step 4: Create ExecutionResult
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=graph_success,
                final_state=final_state,
                execution_summary=summary,
                execution_time=execution_time,
                source_info=source_info,
                error=None
            )
            
            # Log successful completion
            self.logger.info(f"✅ COMPLETED GRAPH: '{graph_name}' in {execution_time:.2f}s")
            self.logger.info(f"  Policy success: {graph_success}, Raw success: {summary['overall_success']}")
            
            return execution_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Log error
            self.logger.error(f"❌ GRAPH EXECUTION FAILED: '{graph_name}' after {execution_time:.2f}s")
            self.logger.error(f"[GraphRunnerService] Error: {str(e)}")
            
            # Create error result
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=state,  # Return original state on error
                execution_summary=None,
                execution_time=execution_time,
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
        Run graph from pre-compiled file.
        
        Args:
            graph_path: Path to compiled graph file
            options: Execution options
            
        Returns:
            ExecutionResult with execution details
        """
        import time
        
        # Initialize options with defaults
        if options is None:
            options = RunOptions()
        
        # Extract graph name from path
        graph_name = graph_path.stem
        
        self.logger.info(f"[GraphRunnerService] Running from compiled graph: {graph_path}")
        
        start_time = time.time()
        
        try:
            # Load compiled graph directly
            import pickle
            
            if not graph_path.exists():
                raise FileNotFoundError(f"Compiled graph not found: {graph_path}")
            
            # Try GraphBundle format first using the new service
            try:
                bundle = self.graph_bundle_service.load_bundle(graph_path)
                if bundle and bundle.graph:
                    compiled_graph = bundle.graph
                    self.logger.debug(f"[GraphRunnerService] Loaded GraphBundle format using service")
                else:
                    raise ValueError("Invalid bundle format")
            except Exception:
                # Fallback to legacy pickle format
                with open(graph_path, "rb") as f:
                    compiled_graph = pickle.load(f)
                    self.logger.debug(f"[GraphRunnerService] Loaded legacy pickle format")
            
            # Initialize state and tracking
            state = options.initial_state or {}
            execution_tracker = self.execution_tracking_service.create_tracker()
            
            # Execute the graph
            final_state = compiled_graph.invoke(state)
            
            # Process results
            execution_time = time.time() - start_time
            
            execution_tracker.complete_execution()
            summary = execution_tracker.get_summary()
            
            # Evaluate policy separately (business logic)
            graph_success = self.execution_policy_service.evaluate_success_policy(summary)
            
            # Update state with execution summary and policy result
            final_state = self.state_adapter_service.set_value(final_state, "__execution_summary", summary)
            final_state = self.state_adapter_service.set_value(final_state, "__policy_success", graph_success)
            
            # Create result
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=graph_success,
                final_state=final_state,
                execution_summary=summary,
                execution_time=execution_time,
                source_info="precompiled",
                error=None
            )
            
            self.logger.info(f"✅ COMPLETED COMPILED GRAPH: '{graph_name}' in {execution_time:.2f}s")
            return execution_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.logger.error(f"❌ COMPILED GRAPH EXECUTION FAILED: '{graph_name}' after {execution_time:.2f}s")
            self.logger.error(f"[GraphRunnerService] Error: {str(e)}")
            
            # Create error result
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=options.initial_state or {},
                execution_summary=None,
                execution_time=execution_time,
                source_info="precompiled",
                error=str(e)
            )
            
            return execution_result
    
    def run_from_csv_direct(
        self, 
        csv_path: Path, 
        graph_name: str, 
        options: Optional[RunOptions] = None
    ) -> ExecutionResult:
        """
        Run graph directly from CSV without compilation.
        
        Args:
            csv_path: Path to CSV file
            graph_name: Name of the graph to execute
            options: Execution options
            
        Returns:
            ExecutionResult with execution details
        """
        import time
        
        # Initialize options with defaults, force no autocompile
        if options is None:
            options = RunOptions()
        
        # Override options to force CSV path and disable autocompile
        options.csv_path = csv_path
        options.autocompile = False
        
        self.logger.info(f"[GraphRunnerService] Running directly from CSV: {csv_path}, graph: {graph_name}")
        
        start_time = time.time()
        
        try:
            # Load graph definition from CSV
            graph_def, resolved_graph_name = self._load_graph_definition(csv_path, graph_name)
            
            # Build graph in memory (forces memory execution path)
            compiled_graph = self._build_graph_in_memory(resolved_graph_name, graph_def)
            
            # Initialize state and tracking
            state = options.initial_state or {}
            execution_tracker = self.execution_tracking_service.create_tracker()
            
            # Execute the graph
            final_state = compiled_graph.invoke(state)
            
            # Process results
            execution_time = time.time() - start_time
            
            execution_tracker.complete_execution()
            summary = execution_tracker.get_summary()
            
            # Evaluate policy separately (business logic)
            graph_success = self.execution_policy_service.evaluate_success_policy(summary)
            
            # Update state with execution summary and policy result
            final_state = self.state_adapter_service.set_value(final_state, "__execution_summary", summary)
            final_state = self.state_adapter_service.set_value(final_state, "__policy_success", graph_success)
            
            # Create result
            execution_result = ExecutionResult(
                graph_name=resolved_graph_name,
                success=graph_success,
                final_state=final_state,
                execution_summary=summary,
                execution_time=execution_time,
                source_info="memory",
                error=None
            )
            
            self.logger.info(f"✅ COMPLETED CSV DIRECT GRAPH: '{resolved_graph_name}' in {execution_time:.2f}s")
            return execution_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.logger.error(f"❌ CSV DIRECT EXECUTION FAILED: '{graph_name}' after {execution_time:.2f}s")
            self.logger.error(f"[GraphRunnerService] Error: {str(e)}")
            
            # Create error result
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=options.initial_state or {},
                execution_summary=None,
                execution_time=execution_time,
                source_info="memory",
                error=str(e)
            )
            
            return execution_result
    
    def _resolve_graph(self, graph_name: str, options: RunOptions) -> tuple:
        """
        Resolve graph using three execution paths: precompiled, autocompiled, or in-memory.
        
        Args:
            graph_name: Name of the graph to resolve
            options: Run options containing configuration
            
        Returns:
            Tuple of (compiled_graph, source_info, graph_def) where:
            - compiled_graph: Ready-to-execute graph
            - source_info: Information about graph source ("precompiled", "autocompiled", "memory")
            - graph_def: Raw graph definition (only for memory-built graphs)
        """
        self.logger.debug(f"[GraphRunnerService] Resolving graph: {graph_name}")
        
        # Path 1: Try to load precompiled graph
        compiled_graph_bundle = self._load_compiled_graph(graph_name)
        if compiled_graph_bundle:
            self.logger.debug(f"[GraphRunnerService] Using precompiled graph for: {graph_name}")
            return self._extract_graph_from_bundle(compiled_graph_bundle), "precompiled", None
        
        # Path 2: Try autocompilation if enabled
        autocompile = options.autocompile
        if autocompile is None:
            autocompile = self.config.get_value("autocompile", False)
        
        if autocompile and graph_name:
            self.logger.debug(f"[GraphRunnerService] Attempting autocompilation for: {graph_name}")
            compiled_graph_bundle = self._autocompile_and_load(graph_name, options)
            if compiled_graph_bundle:
                self.logger.debug(f"[GraphRunnerService] Using autocompiled graph for: {graph_name}")
                return self._extract_graph_from_bundle(compiled_graph_bundle), "autocompiled", None
        
        # Path 3: Build graph in memory from CSV
        self.logger.debug(f"[GraphRunnerService] Building graph in memory for: {graph_name}")
        csv_path = options.csv_path or self.config.get_csv_path()
        graph_def, resolved_graph_name = self._load_graph_definition(csv_path, graph_name)
        compiled_graph = self._build_graph_in_memory(resolved_graph_name, graph_def)
        
        return compiled_graph, "memory", graph_def
    
    def _load_compiled_graph(self, graph_name: str) -> Optional[GraphBundle]:
        """
        Load a compiled graph bundle from the configured path.
        
        Wraps the existing load_compiled_graph functionality while using service configuration.
        
        Args:
            graph_name: Name of the graph to load
            
        Returns:
            GraphBundle instance or None if not found
        """
        compiled_path = self.config.get_compiled_graphs_path() / f"{graph_name}.pkl"
        
        if not compiled_path.exists():
            self.logger.debug(f"[GraphRunnerService] Compiled graph not found: {compiled_path}")
            return None
        
        self.logger.debug(f"[GraphRunnerService] Loading compiled graph: {compiled_path}")
        
        try:
            # Use GraphBundleService for loading
            bundle = self.graph_bundle_service.load_bundle(compiled_path)
            
            if bundle and bundle.graph:
                self.logger.debug(f"[GraphRunnerService] Loaded graph bundle using service")
                return bundle
            
            # If service loading failed, try legacy fallback
            import pickle
            with open(compiled_path, "rb") as f:
                legacy_graph = pickle.load(f)
                self.logger.debug(f"[GraphRunnerService] Loaded legacy compiled graph")
                # Create a GraphBundle from legacy format
                return GraphBundle(
                    graph=legacy_graph, 
                    node_registry={}, 
                    version_hash=None
                )
                
        except Exception as e:
            self.logger.error(f"[GraphRunnerService] Error loading compiled graph {compiled_path}: {e}")
            return None
    
    def _autocompile_and_load(self, graph_name: str, options: RunOptions) -> Optional[GraphBundle]:
        """
        Autocompile and load a graph using CompilationService.
        
        Args:
            graph_name: Name of the graph to compile and load
            options: Run options containing compilation configuration
            
        Returns:
            GraphBundle instance or None if compilation failed
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
                # Load the newly compiled graph
                return self._load_compiled_graph(graph_name)
            else:
                self.logger.warning(f"[GraphRunnerService] Autocompilation failed for: {graph_name}")
                if result:
                    self.logger.warning(f"[GraphRunnerService] Compilation error: {result.error}")
                return None
                
        except Exception as e:
            self.logger.error(f"[GraphRunnerService] Autocompilation error for {graph_name}: {e}")
            return None
    
    def _build_graph_in_memory(self, graph_name: str, graph_def: Dict[str, Any]) -> Any:
        """
        Build a graph in memory from graph definition with full service injection.
        
        Coordinates with all services to build a complete executable graph.
        
        Args:
            graph_name: Name of the graph to build
            graph_def: Pre-loaded graph definition from GraphBuilderService
            
        Returns:
            Compiled graph ready for execution
        """
        self.logger.debug(f"[GraphRunnerService] Building graph in memory: {graph_name}")
        
        if not graph_def:
            raise ValueError(f"[GraphRunnerService] Invalid or empty graph definition for graph: {graph_name}")
        
        # Build node registry BEFORE creating assembler
        self.logger.debug(f"[GraphRunnerService] Preparing node registry for: {graph_name}")
        node_registry = self.node_registry.prepare_for_assembly(graph_def, graph_name)
        
        # Create the StateGraph builder
        from langgraph.graph import StateGraph
        builder = StateGraph(dict)
        
        # Create assembler WITH node registry for pre-compilation injection
        from agentmap.graph import GraphAssembler
        assembler = GraphAssembler(builder, node_registry=node_registry)
        
        # Add all nodes to the graph with service injection
        for node in graph_def.values():
            self.logger.debug(f"[GraphRunnerService] Processing node: {node.name} with type: {node.agent_type}")
            
            # Create and configure agent instance using extracted methods
            agent_instance = self._create_agent_instance(node, graph_name)
            
            # Validate agent configuration
            self._validate_agent_configuration(agent_instance, node)
            
            # Add node to the graph (triggers automatic registry injection for orchestrators)
            assembler.add_node(node.name, agent_instance)
        
        # Set entry point
        assembler.set_entry_point(next(iter(graph_def)))
        
        # Process edges for all nodes
        for node_name, node in graph_def.items():
            assembler.process_node_edges(node_name, node.edges)
        
        # Verify that pre-compilation injection worked
        verification = self.node_registry.verify_pre_compilation_injection(assembler)
        if not verification["all_injected"] and verification["has_orchestrators"]:
            self.logger.warning(f"[GraphRunnerService] Pre-compilation injection incomplete for graph '{graph_name}'")
            self.logger.warning(f"[GraphRunnerService] Stats: {verification['stats']}")
        
        # Compile and return the graph
        compiled_graph = assembler.compile()
        
        self.logger.info(f"[GraphRunnerService] ✅ Successfully built graph '{graph_name}' with pre-compilation registry injection")
        return compiled_graph
    
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
        
        # Future: Add other service injection types here
        # - Vector database services
        # - External API services
        # - Custom service injections
        
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
    
    def _get_agent_capabilities(self, agent_class) -> Dict[str, bool]:
        """
        Determine agent capabilities by inspecting protocols it implements.
        
        Uses protocol inspection instead of hardcoded string matching for robust
        capability detection that works with custom agents.
        
        Args:
            agent_class: Agent class to inspect
            
        Returns:
            Dict with capability flags (is_llm_agent, is_storage_agent, etc.)
        """
        capabilities = {
            "is_llm_agent": self._implements_llm_protocol(agent_class),
            "is_storage_agent": self._implements_storage_protocol(agent_class),
            "is_custom": self._is_custom_agent_class(agent_class),
            "is_builtin": not self._is_custom_agent_class(agent_class)
        }
        
        self.logger.debug(f"[GraphRunnerService] Agent capabilities for {agent_class.__name__}: {capabilities}")
        return capabilities
    
    def _implements_llm_protocol(self, agent_class) -> bool:
        """
        Check if agent class implements LLM service protocol.
        
        Args:
            agent_class: Agent class to inspect
            
        Returns:
            True if agent implements LLMServiceUser protocol
        """
        try:
            from agentmap.services import LLMServiceUser
            return issubclass(agent_class, LLMServiceUser)
        except (ImportError, TypeError):
            self.logger.debug(f"[GraphRunnerService] Could not check LLM protocol for {agent_class.__name__}")
            return False
    
    def _implements_storage_protocol(self, agent_class) -> bool:
        """
        Check if agent class implements storage service protocols.
        
        Args:
            agent_class: Agent class to inspect
            
        Returns:
            True if agent implements any storage service protocols
        """
        try:
            # Try protocol-based detection first
            return self._check_storage_protocols(agent_class)
        except (ImportError, TypeError):
            # Fallback to class name inspection
            return self._inspect_class_for_storage_hints(agent_class)
    
    def _check_storage_protocols(self, agent_class) -> bool:
        """
        Check agent class against known storage protocols.
        
        Args:
            agent_class: Agent class to inspect
            
        Returns:
            True if agent implements any storage protocols
        """
        try:
            # Check against storage service injection requirements
            from agentmap.services.storage.injection import requires_storage_services
            
            # Create a temporary instance to check storage requirements
            # Use minimal args to avoid side effects
            temp_instance = agent_class("temp", "", {}, None, None)
            return requires_storage_services(temp_instance)
        except Exception:
            # If instantiation fails, fall back to class inspection
            return self._inspect_class_for_storage_hints(agent_class)
    
    def _inspect_class_for_storage_hints(self, agent_class) -> bool:
        """
        Inspect class hierarchy for storage-related indicators.
        
        Args:
            agent_class: Agent class to inspect
            
        Returns:
            True if class shows storage-related patterns
        """
        # Check method resolution order for storage-related base classes
        for base in agent_class.__mro__:
            base_name = base.__name__.lower()
            if any(storage_type in base_name for storage_type in 
                   ["csv", "json", "file", "storage", "vector", "blob", "firebase"]):
                return True
        
        # Check class name itself
        class_name = agent_class.__name__.lower()
        if any(storage_type in class_name for storage_type in 
               ["csv", "json", "file", "storage", "vector", "blob", "firebase"]):
            return True
        
        return False
    
    def _is_custom_agent_class(self, agent_class) -> bool:
        """
        Determine if agent class is a custom (non-builtin) agent.
        
        Args:
            agent_class: Agent class to inspect
            
        Returns:
            True if agent appears to be custom, False if builtin
        """
        # Check if class module path indicates custom agent
        module_path = getattr(agent_class, '__module__', '')
        
        # Builtin agents are typically in agentmap.agents.* modules
        if module_path.startswith('agentmap.agents.'):
            return False
        
        # Check if it's loaded from custom agents path
        custom_agents_path = self.config.get_custom_agents_path()
        custom_agents_path_str = str(custom_agents_path)
        
        if hasattr(agent_class, '__file__') and agent_class.__file__:
            agent_file_path = str(agent_class.__file__)
            if custom_agents_path_str in agent_file_path:
                return True
        
        # Default to custom if not clearly builtin
        return True
    
    def _get_agent_type_info(self, agent_type: str) -> Dict[str, Any]:
        """
        Get information about an agent type using protocol-based detection.
        
        Replaces hardcoded string matching with robust protocol inspection
        that works for custom agents and maintains consistency with service injection.
        
        Args:
            agent_type: Type of agent to analyze
            
        Returns:
            Dictionary with agent type information
        """
        self.logger.debug(f"[GraphRunnerService] Getting agent type info for: {agent_type}")
        
        try:
            # Step 1: Resolve the agent class
            agent_class = self._resolve_agent_class(agent_type)
            
            # Step 2: Inspect class for capabilities using protocols
            capabilities = self._get_agent_capabilities(agent_class)
            
            # Step 3: Build base info structure
            info = {
                "agent_type": agent_type,
                "agent_class": agent_class,
                **capabilities,  # Spread the capabilities
                "dependencies_available": True,
                "missing_dependencies": []
            }
            
            # Step 4: Check dependencies based on actual capabilities
            if capabilities["is_llm_agent"]:
                has_deps, missing = self.dependency_checker.check_llm_dependencies()
                info["dependencies_available"] = has_deps
                info["missing_dependencies"] = missing or []
                
            if capabilities["is_storage_agent"]:
                has_deps, missing = self.dependency_checker.check_storage_dependencies()
                info["dependencies_available"] = info["dependencies_available"] and has_deps
                info["missing_dependencies"].extend(missing or [])
            
            self.logger.debug(f"[GraphRunnerService] Agent type info resolved via protocol inspection: {info}")
            return info
            
        except Exception as e:
            # Fallback for agents that can't be resolved
            self.logger.warning(f"[GraphRunnerService] Could not resolve agent type '{agent_type}': {e}")
            return self._get_fallback_agent_info(agent_type)
    
    def _get_fallback_agent_info(self, agent_type: str) -> Dict[str, Any]:
        """
        Get fallback agent info for unresolvable agent types.
        
        Args:
            agent_type: Agent type that couldn't be resolved
            
        Returns:
            Basic agent info structure
        """
        self.logger.debug(f"[GraphRunnerService] Using fallback agent info for: {agent_type}")
        
        return {
            "agent_type": agent_type,
            "agent_class": None,
            "is_llm_agent": False,
            "is_storage_agent": False,
            "is_builtin": False,
            "is_custom": False,
            "dependencies_available": False,
            "missing_dependencies": [f"Could not resolve agent type: {agent_type}"]
        }
    
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
            
            # Get detailed info about this agent type using protocol inspection
            agent_info = self._get_agent_type_info(agent_type)
            
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
            
            if agent_info["is_custom"]:
                status["resolution_summary"]["custom_agents"] += 1
            elif agent_info["is_builtin"]:
                status["resolution_summary"]["builtin_agents"] += 1
            
            if agent_info["is_llm_agent"]:
                status["resolution_summary"]["llm_agents"] += 1
            
            if agent_info["is_storage_agent"]:
                status["resolution_summary"]["storage_agents"] += 1
        
        # Add overall status
        status["overall_status"] = {
            "all_resolvable": status["resolution_summary"]["missing_dependencies"] == 0,
            "has_issues": len(status["issues"]) > 0,
            "unique_agent_types": len(status["agent_types"]),
            "resolution_rate": status["resolution_summary"]["resolvable"] / status["total_nodes"] if status["total_nodes"] > 0 else 0
        }
        
        return status
    
    def _load_graph_definition(self, csv_path: Path, graph_name: Optional[str]) -> tuple:
        """
        Load graph definition from CSV using GraphBuilderService.
        
        Args:
            csv_path: Path to CSV file
            graph_name: Optional specific graph name to load
            
        Returns:
            Tuple of (graph_def, resolved_graph_name)
        """
        self.logger.debug(f"[GraphRunnerService] Loading graph definition from CSV: {csv_path}")
        
        # Convert to old format for compatibility with existing infrastructure
        if graph_name:
            # Load specific graph
            graph_domain_model = self.graph_builder.build_from_csv(csv_path, graph_name)
            graph_def = self._convert_domain_model_to_old_format(graph_domain_model)
            return graph_def, graph_name
        else:
            # Load first graph available
            all_graphs = self.graph_builder.build_all_from_csv(csv_path)
            if not all_graphs:
                raise ValueError(f"No graphs found in CSV file: {csv_path}")
            
            first_graph_name = next(iter(all_graphs))
            graph_domain_model = all_graphs[first_graph_name]
            graph_def = self._convert_domain_model_to_old_format(graph_domain_model)
            
            self.logger.debug(f"[GraphRunnerService] Using first graph: {first_graph_name}")
            return graph_def, first_graph_name
    
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
    
    def _extract_graph_from_bundle(self, graph_bundle: GraphBundle) -> Any:
        """
        Extract the executable graph from a GraphBundle.
        
        Args:
            graph_bundle: GraphBundle instance
            
        Returns:
            Executable graph object
        """
        if graph_bundle and graph_bundle.graph:
            version_hash = graph_bundle.version_hash
            self.logger.debug(f"[GraphRunnerService] Extracted graph from bundle with version hash: {version_hash}")
            return graph_bundle.graph
        else:
            raise ValueError("[GraphRunnerService] Invalid or empty GraphBundle")
    
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
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the runner service for debugging.
        
        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "GraphRunnerService",
            "graph_builder_available": self.graph_builder is not None,
            "compilation_service_available": self.compilation is not None,
            "graph_bundle_service_available": self.graph_bundle_service is not None,
            "llm_service_available": self.llm_service is not None,
            "storage_service_manager_available": self.storage_service_manager is not None,
            "node_registry_available": self.node_registry is not None,
            "execution_tracking_service_available": self.execution_tracking_service is not None,
            "execution_policy_service_available": self.execution_policy_service is not None,
            "state_adapter_service_available": self.state_adapter_service is not None,
            "dependency_checker_available": self.dependency_checker is not None,
            "config_available": self.config is not None,
            "dependencies_initialized": all([
                self.graph_builder is not None,
                self.compilation is not None,
                self.graph_bundle_service is not None,
                self.llm_service is not None,
                self.storage_service_manager is not None,
                self.node_registry is not None,
                self.execution_tracking_service is not None,
                self.execution_policy_service is not None,
                self.state_adapter_service is not None,
                self.dependency_checker is not None,
                self.config is not None
            ]),
            "capabilities": {
                "graph_resolution": True,
                "agent_resolution": True,
                "service_injection": True,
                "precompiled_graphs": True,
                "autocompilation": True,
                "memory_building": True,
                "agent_validation": True,
                "dependency_checking": True,
                "protocol_based_detection": True
            },
            "agent_resolution_methods": [
                "_resolve_agent_class",
                "_create_agent_instance", 
                "_inject_services_into_agent",
                "_inject_llm_service",
                "_inject_storage_services",
                "_validate_agent_configuration",
                "_get_agent_capabilities",
                "_implements_llm_protocol",
                "_implements_storage_protocol",
                "_get_agent_type_info",
                "get_agent_resolution_status"
            ]
        }
    
    def _log_service_status(self) -> None:
        """Log the status of all injected services for debugging."""
        status = self.get_service_info()
        self.logger.debug(f"[GraphRunnerService] Service status: {status}")
        
        if not status["dependencies_initialized"]:
            missing_deps = []
            if not self.graph_builder:
                missing_deps.append("graph_builder_service")
            if not self.compilation:
                missing_deps.append("compilation_service")
            if not self.graph_bundle_service:
                missing_deps.append("graph_bundle_service")
            if not self.llm_service:
                missing_deps.append("llm_service")
            if not self.storage_service_manager:
                missing_deps.append("storage_service_manager")
            if not self.node_registry:
                missing_deps.append("node_registry_service")
            if not self.execution_tracking_service:
                missing_deps.append("execution_tracking_service")
            if not self.execution_policy_service:
                missing_deps.append("execution_policy_service")
            if not self.state_adapter_service:
                missing_deps.append("state_adapter_service")
            if not self.dependency_checker:
                missing_deps.append("dependency_checker_service")
            if not self.config:
                missing_deps.append("app_config_service")
            
            self.logger.warning(f"[GraphRunnerService] Missing dependencies: {missing_deps}")
