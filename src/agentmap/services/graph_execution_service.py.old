"""
GraphExecutionService for AgentMap - REFACTORED VERSION.

Service that provides clean execution orchestration by coordinating with existing
ExecutionTrackingService and ExecutionPolicyService. Extracted from GraphRunnerService
to separate execution concerns from graph building and compilation.
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional, Set


from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.exceptions.graph_exceptions import BundleLoadError
from agentmap.models.execution_result import ExecutionResult
from agentmap.models.graph_bundle import GraphBundle

from agentmap.services.agent_factory_service import AgentFactoryService
from agentmap.services.execution_policy_service import ExecutionPolicyService
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.graph_assembly_service import GraphAssemblyService
from agentmap.services.graph_bundle_service import GraphBundleService
from agentmap.services.graph_factory_service import GraphFactoryService
from agentmap.services.logging_service import LoggingService
from agentmap.services.state_adapter_service import StateAdapterService


class GraphExecutionService:
    """
    Service for clean graph execution orchestration.

    Coordinates execution flow by working with existing execution-related services:
    - ExecutionTrackingService for tracking creation and management
    - ExecutionPolicyService for success evaluation
    - StateAdapterService for state management
    - GraphAssemblyService for in-memory graph compilation
    - GraphBundleService for bundle loading
    - AgentFactoryService for agent creation and instantiation

    This service focuses on execution coordination without duplication of
    existing execution service functionality.
    """

    def __init__(
        self,
        execution_tracking_service: ExecutionTrackingService,
        execution_policy_service: ExecutionPolicyService,
        state_adapter_service: StateAdapterService,
        graph_assembly_service: GraphAssemblyService,
        graph_bundle_service: GraphBundleService,
        graph_factory_service: GraphFactoryService,
        agent_factory_service: AgentFactoryService,
        logging_service: LoggingService,
    ):
        """Initialize service with dependency injection.

        Args:
            execution_tracking_service: Service for creating execution trackers
            execution_policy_service: Service for policy evaluation
            state_adapter_service: Service for state management
            graph_assembly_service: Service for graph assembly from definitions
            graph_bundle_service: Service for graph bundle operations
            graph_factory_service: Service for centralized graph creation
            agent_factory_service: Service for agent creation and instantiation
            logging_service: Service for logging operations
        """
        self.execution_tracking_service = execution_tracking_service
        self.execution_policy_service = execution_policy_service
        self.state_adapter_service = state_adapter_service
        self.graph_assembly_service = graph_assembly_service
        self.graph_bundle_service = graph_bundle_service
        self.graph_factory_service = graph_factory_service
        self.agent_factory_service = agent_factory_service
        self.logger = logging_service.get_class_logger(self)

        self.logger.info(
            "[GraphExecutionService] Initialized with execution coordination services"
        )

    def setup_execution_tracking(self, graph_name: str) -> Any:
        """
        Setup execution tracking for a graph execution.

        Args:
            graph_name: Name of the graph for tracking context

        Returns:
            ExecutionTracker instance
        """
        self.logger.debug(
            f"[GraphExecutionService] Setting up execution tracking for: {graph_name}"
        )

        # Use ExecutionTrackingService to create tracker
        execution_tracker = self.execution_tracking_service.create_tracker()

        self.logger.debug(
            f"[GraphExecutionService] Execution tracking setup complete for: {graph_name}"
        )
        return execution_tracker

    def execute_runnable_graph(
        self, bundle_path: Path, state: Dict[str, Any]
    ) -> ExecutionResult:
        """
        Execute a pre-compiled graph from a bundle file.

        Args:
            bundle_path: Path to the compiled graph bundle
            state: Initial state dictionary

        Returns:
            ExecutionResult with complete execution details
        """
        # Extract graph name from path
        graph_name = bundle_path.stem

        self.logger.info(
            f"[GraphExecutionService] Executing compiled graph: {graph_name}"
        )

        # Load the compiled graph bundle
        runnable_graph = self._load_runnable_graph_from_bundle(bundle_path)

        # Initialize execution tracking for precompiled graph
        execution_tracker = self.setup_execution_tracking(graph_name)
        # Note: Precompiled graphs may not have tracker distribution capability

        return self._execute_graph(
            runnable_graph,
            graph_name,
            execution_tracker,
            state,
            "precompiled",
            "COMPILED GRAPH"
        )

    def execute_from_definition(
        self,
        graph_def: Dict[str, Any],
        state: Dict[str, Any],
        graph_name: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a graph from an in-memory graph definition.

        Args:
            graph_def: Graph definition dictionary with nodes and their configurations,
                      or a GraphBundle instance for metadata-based execution
            state: Initial state dictionary
            graph_name: Optional graph name (if not provided, will extract from definition)

        Returns:
            ExecutionResult with complete execution details
        """
        # Check if this is a metadata bundle instead of a traditional graph definition
        if isinstance(graph_def, GraphBundle):
            self.logger.debug(
                "[GraphExecutionService] Detected metadata bundle, using selective loading execution"
            )
            return self.execute_with_bundle(graph_def, state)
            
        # Use provided graph name or extract from definition
        if graph_name is None:
            graph_name = self.graph_factory_service.resolve_graph_name_from_definition(
                graph_def
            )

        self.logger.info(
            f"[GraphExecutionService] Executing from definition: {graph_name}"
        )

        # Initialize execution tracking BEFORE assembly
        self.logger.debug(
            f"[GraphExecutionService] Setting up execution tracking for: {graph_name}"
        )
        execution_tracker = self.setup_execution_tracking(graph_name)
        self.logger.debug(
            f"[GraphExecutionService] Execution tracker created: {type(execution_tracker)}"
        )

        # Assemble the graph from definition and set tracker on agents
        self.logger.debug(
            f"[GraphExecutionService] Assembling graph from definition: {graph_name}"
        )
        runnable_graph = self._assemble_graph_from_definition(
            graph_def, graph_name, execution_tracker
        )
        self.logger.debug(
            f"[GraphExecutionService] Graph assembly complete: {graph_name}"
        )

        return self._execute_graph(
            runnable_graph,
            graph_name,
            execution_tracker,
            state,
            "memory",
            "DEFINITION GRAPH"
        )

    def execute_with_bundle(
        self, bundle: GraphBundle, state: Dict[str, Any]
    ) -> ExecutionResult:
        """
        Execute a graph using selective service loading from metadata bundle.
        
        Creates minimal DI container with only required services, creates fresh agent
        instances for only required agent types, and builds/executes graph at runtime.
        
        Args:
            bundle: GraphBundle with metadata for selective loading
            state: Initial state dictionary
            
        Returns:
            ExecutionResult with complete execution details
        """
        graph_name = bundle.graph_name or "unknown_graph"
        
        self.logger.info(
            f"[GraphExecutionService] Executing with metadata bundle: {graph_name}"
        )
        
        # Create minimal container with only required services
        self.logger.debug(
            f"[GraphExecutionService] Creating minimal container with services: {bundle.required_services}"
        )
        minimal_container = self._create_minimal_container(bundle.required_services or set())
        
        # Create fresh agent instances from metadata
        self.logger.debug(
            f"[GraphExecutionService] Creating agents from metadata: {bundle.required_agents}"
        )
        agents = self._create_agents_from_metadata(
            bundle.nodes or {}, 
            bundle.required_agents or set(), 
            minimal_container
        )
        
        # Set up execution tracking
        execution_tracker = self.setup_execution_tracking(graph_name)
        
        # Inject services into agents and set tracking
        configured_agents = 0
        for agent_type, agent_instance in agents.items():
            # Inject required services based on agent protocols
            services = self._get_agent_services(agent_instance.__class__, minimal_container)
            for service_name, service_instance in services.items():
                # Use protocol-based injection pattern
                if hasattr(agent_instance, f'configure_{service_name}'):
                    getattr(agent_instance, f'configure_{service_name}')(service_instance)
                    self.logger.debug(
                        f"[GraphExecutionService] Injected {service_name} into {agent_type}"
                    )
            
            # Set execution tracker
            if hasattr(agent_instance, 'set_execution_tracker'):
                agent_instance.set_execution_tracker(execution_tracker)
                
            configured_agents += 1
        
        self.logger.info(
            f"[GraphExecutionService] Configured {configured_agents} agents with selective services"
        )
        
        # Build graph from nodes using GraphAssemblyService
        graph_def = self._build_graph_definition_from_bundle(bundle, agents)
        graph = self.graph_factory_service.create_graph_from_definition(
            graph_def, graph_name
        )
        
        runnable_graph = self.graph_assembly_service.assemble_graph(
            graph_def,  # Pass the graph definition dictionary
            node_registry=None  # Node registry handled internally
        )
        
        return self._execute_graph(
            runnable_graph,
            graph_name,
            execution_tracker,
            state,
            "metadata",
            "METADATA BUNDLE"
        )

    def _execute_graph(
        self,
        runnable_graph: Any,
        graph_name: str,
        execution_tracker: Any,
        state: Dict[str, Any],
        compiled_from: str,
        execution_type: str
    ) -> ExecutionResult:
        """
        Common execution logic for all graph execution methods.
        
        Args:
            runnable_graph: The compiled/assembled graph ready for execution
            graph_name: Name of the graph being executed
            execution_tracker: The execution tracker instance
            state: Initial state dictionary
            compiled_from: Source descriptor ("memory", "metadata", "precompiled")
            execution_type: Execution type for logging ("DEFINITION GRAPH", "METADATA BUNDLE", etc.)
            
        Returns:
            ExecutionResult with complete execution details
        """
        start_time = time.time()
        execution_summary = None
        
        try:
            # Execute the graph with tracking (tracker already set on agents)
            self.logger.debug(
                f"[GraphExecutionService] Executing graph with tracking: {graph_name}"
            )
            final_state, execution_summary = self._execute_graph_with_tracking(
                runnable_graph, state, graph_name, execution_tracker
            )
            self.logger.debug(
                f"[GraphExecutionService] Graph execution complete: {graph_name}"
            )
            
            # Calculate execution time and evaluate policy
            execution_time = time.time() - start_time
            graph_success = self.execution_policy_service.evaluate_success_policy(
                execution_summary
            )
            
            # Update state with execution metadata
            final_state = self.state_adapter_service.set_value(
                final_state, "__execution_summary", execution_summary
            )
            final_state = self.state_adapter_service.set_value(
                final_state, "__policy_success", graph_success
            )
            
            # Create successful execution result
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=graph_success,
                final_state=final_state,
                execution_summary=execution_summary,
                total_duration=execution_time,
                compiled_from=compiled_from,
                error=None,
            )
            
            self.logger.info(
                f"✅ COMPLETED {execution_type}: '{graph_name}' in {execution_time:.2f}s"
            )
            return execution_result
            
        except ExecutionInterruptedException:
            # Re-raise ExecutionInterruptedException without wrapping it
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.logger.error(
                f"❌ {execution_type} EXECUTION FAILED: '{graph_name}' after {execution_time:.2f}s"
            )
            self.logger.error(f"[GraphExecutionService] Error: {str(e)}")
            
            # Log detailed error information for debugging
            import traceback
            self.logger.error(
                f"[GraphExecutionService] Full traceback:\n{traceback.format_exc()}"
            )
            
            # Try to create execution summary even in case of error
            try:
                if execution_tracker is not None:
                    self.logger.debug(
                        f"[GraphExecutionService] Creating execution summary from tracker after error"
                    )
                    # Complete execution tracking with error state
                    self.execution_tracking_service.complete_execution(
                        execution_tracker
                    )
                    execution_summary = self.execution_tracking_service.to_summary(
                        execution_tracker, graph_name
                    )
                    self.logger.debug(
                        f"[GraphExecutionService] Error execution summary created with "
                        f"{len(execution_summary.node_executions) if execution_summary else 0} node executions"
                    )
                else:
                    self.logger.warning(
                        f"[GraphExecutionService] No execution tracker available for error summary"
                    )
            except Exception as summary_error:
                self.logger.error(
                    f"[GraphExecutionService] Failed to create execution summary after error: {summary_error}"
                )
                execution_summary = None
            
            # Create error execution result
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=state,  # Return original state on error
                execution_summary=execution_summary,  # Now includes summary even on error
                total_duration=execution_time,
                compiled_from=compiled_from,
                error=str(e),
            )
            
            return execution_result

    def _load_runnable_graph_from_bundle(self, bundle_path: Path) -> Any:
        """
        Load compiled graph from bundle file.

        Args:
            bundle_path: Path to the bundle file

        Returns:
            Executable compiled graph

        Raises:
            FileNotFoundError: If bundle file doesn't exist
            ValueError: If bundle format is invalid
        """
        if not bundle_path.exists():
            raise FileNotFoundError(f"Compiled graph bundle not found: {bundle_path}")

        self.logger.debug(f"[GraphExecutionService] Loading bundle: {bundle_path}")

        try:
            # Try GraphBundle format first using GraphBundleService
            bundle = self.graph_bundle_service.load_bundle(bundle_path)
            if bundle and bundle.graph:
                self.logger.debug("[GraphExecutionService] Loaded GraphBundle format")
                return bundle.graph
            else:
                raise ValueError("Invalid or empty bundle format")

        except Exception as bundle_error:
            # Fallback to legacy pickle format
            raise BundleLoadError(
                f"GraphBundle error: {bundle_error}. Could not load Bundle"
            )

    def _assemble_graph_from_definition(
        self, graph_def: Dict[str, Any], graph_name: str, execution_tracker: Any
    ) -> Any:
        """
        Assemble an executable graph from a graph definition.

        Args:
            graph_def: Graph definition with nodes and configurations
            graph_name: Name of the graph for logging
            execution_tracker: Execution tracker to set on all agent instances

        Returns:
            Executable compiled graph

        Raises:
            ValueError: If graph definition is invalid or assembly fails
        """
        if not graph_def:
            raise ValueError(
                f"Invalid or empty graph definition for graph: {graph_name}"
            )

        self.logger.debug(
            f"[GraphExecutionService] Assembling graph from definition: {graph_name}"
        )

        try:
            # Set execution tracker on all agent instances BEFORE assembly
            self._set_tracker_on_agents(graph_def, execution_tracker)

            graph = self.graph_factory_service.create_graph_from_nodes(
                graph_name, graph_def
            )

            # Use GraphAssemblyService to assemble the graph
            # Note: This assumes the graph_def already has agent instances in context
            # The agent instantiation and service injection should be done by GraphRunnerService
            runnable_graph = self.graph_assembly_service.assemble_graph(
                graph=graph,
                node_registry=None,  # Node registry handled by calling service
            )

            self.logger.debug(
                f"[GraphExecutionService] Graph assembly complete: {graph_name}"
            )
            return runnable_graph

        except Exception as e:
            raise ValueError(f"Failed to assemble graph '{graph_name}': {str(e)}")

    def _execute_graph_with_tracking(
        self,
        runnable_graph: Any,
        state: Dict[str, Any],
        graph_name: str,
        execution_tracker: Any,
    ) -> tuple:
        """
        Execute a compiled graph with execution tracking.

        Args:
            runnable_graph: Executable graph object
            state: Initial state dictionary
            graph_name: Name of the graph for tracking
            execution_tracker: Pre-created execution tracker

        Returns:
            Tuple of (final_state, execution_summary)
        """
        self.logger.debug(
            f"[GraphExecutionService] Executing graph with tracking: {graph_name}"
        )

        # Use the provided execution tracker (already set on agents during assembly)
        # No need to create a new tracker here

        # Log initial state info
        self.logger.debug(f"[GraphExecutionService] Initial state type: {type(state)}")
        self.logger.debug(
            f"[GraphExecutionService] Initial state keys: "
            f"{list(state.keys()) if hasattr(state, 'keys') else 'N/A'}"
        )

        # Execute the graph
        try:
            final_state = runnable_graph.invoke(state)
        except ExecutionInterruptedException as e:
            # Log interruption
            self.logger.info(
                f"[GraphExecutionService] Execution interrupted for human interaction in thread: {e.thread_id}"
            )

            # Preserve exception data for checkpoint
            # The exception already contains checkpoint_data that can be used for resumption
            self.logger.debug(
                f"[GraphExecutionService] Interruption checkpoint data preserved for thread: {e.thread_id}"
            )

            # Re-raise exception for graph runner to handle
            raise

        # Log final state info
        self.logger.debug(
            f"[GraphExecutionService] Final state type: {type(final_state)}"
        )
        self.logger.debug(
            f"[GraphExecutionService] Final state keys: "
            f"{list(final_state.keys()) if hasattr(final_state, 'keys') else 'N/A'}"
        )

        # Complete execution tracking using service
        self.execution_tracking_service.complete_execution(execution_tracker)
        execution_summary = self.execution_tracking_service.to_summary(
            execution_tracker, graph_name
        )

        self.logger.debug(
            f"[GraphExecutionService] Execution tracking complete: {graph_name}"
        )

        return final_state, execution_summary

    def _set_tracker_on_agents(
        self, graph_def: Dict[str, Any], execution_tracker: Any
    ) -> None:
        """
        Set execution tracker on all agent instances in the graph definition.

        This happens BEFORE graph compilation, when agent instances are still accessible.

        Args:
            graph_def: Graph definition dictionary with nodes containing agent instances
            execution_tracker: Execution tracker to set on all agents
        """
        self.logger.debug(
            "[GraphExecutionService] Setting execution tracker on agent instances"
        )
        self.logger.debug(
            f"[GraphExecutionService] Graph definition contains {len(graph_def)} nodes"
        )
        self.logger.debug(
            f"[GraphExecutionService] Execution tracker type: {type(execution_tracker)}"
        )

        agent_count = 0
        for node_name, node in graph_def.items():
            try:
                self.logger.debug(
                    f"[GraphExecutionService] Processing node: {node_name}, type: {type(node)}"
                )

                # Get agent instance from node context
                agent_instance = None
                if hasattr(node, "context"):
                    self.logger.debug(
                        f"[GraphExecutionService] Node {node_name} has context: {node.context is not None}"
                    )
                    if node.context:
                        agent_instance = node.context.get("instance")
                        self.logger.debug(
                            f"[GraphExecutionService] Agent instance found for {node_name}: {agent_instance is not None}"
                        )
                        if agent_instance:
                            self.logger.debug(
                                f"[GraphExecutionService] Agent instance type: {type(agent_instance)}"
                            )
                            self.logger.debug(
                                f"[GraphExecutionService] Agent has set_execution_tracker method: {hasattr(agent_instance, 'set_execution_tracker')}"
                            )
                    else:
                        self.logger.debug(
                            f"[GraphExecutionService] Node {node_name} context is None"
                        )
                else:
                    self.logger.debug(
                        f"[GraphExecutionService] Node {node_name} has no context attribute"
                    )

                if agent_instance and hasattr(agent_instance, "set_execution_tracker"):
                    agent_instance.set_execution_tracker(execution_tracker)
                    agent_count += 1
                    self.logger.debug(
                        f"[GraphExecutionService] ✅ Set tracker for agent: {node_name}"
                    )
                else:
                    if agent_instance is None:
                        self.logger.warning(
                            f"[GraphExecutionService] ❌ No agent instance found for node: {node_name}"
                        )
                    else:
                        self.logger.warning(
                            f"[GraphExecutionService] ❌ Agent {node_name} missing set_execution_tracker method"
                        )

            except Exception as e:
                self.logger.error(
                    f"[GraphExecutionService] ❌ Error setting tracker for node {node_name}: {e}"
                )
                import traceback

                self.logger.error(
                    f"[GraphExecutionService] Traceback: {traceback.format_exc()}"
                )

        self.logger.info(
            f"[GraphExecutionService] Set tracker on {agent_count}/{len(graph_def)} agent instances"
        )

        if agent_count == 0:
            self.logger.error(
                "[GraphExecutionService] ❌ CRITICAL: No agent instances found to set tracker on - execution tracking will fail!"
            )
            # List all nodes and their context status for debugging
            for node_name, node in graph_def.items():
                has_context = hasattr(node, "context") and node.context is not None
                has_instance = has_context and "instance" in node.context
                self.logger.error(
                    f"[GraphExecutionService]   Node {node_name}: has_context={has_context}, has_instance={has_instance}"
                )
        else:
            self.logger.debug(
                f"[GraphExecutionService] ✅ Successfully set tracker on {agent_count} agents"
            )

    def _create_minimal_container(self, required_services: Set[str]) -> Any:
        """
        Create a minimal DI container with only required services.
        
        Args:
            required_services: Set of service names that should be loaded
            
        Returns:
            MinimalContainer instance with only required services
        """
        self.logger.debug(
            f"[GraphExecutionService] Creating minimal container with {len(required_services)} services"
        )
        
        # Import locally to avoid circular import
        from agentmap.di.containers import ApplicationContainer
        from agentmap.di.minimal_container import MinimalContainer
        
        # Create parent ApplicationContainer
        parent_container = ApplicationContainer()
        
        # Create minimal container with selective loading
        minimal_container = MinimalContainer(
            parent_container=parent_container,
            required_services=required_services,
            logging_service=None  # Let MinimalContainer get it from parent
        )
        
        self.logger.debug(
            "[GraphExecutionService] Minimal container created successfully"
        )
        
        return minimal_container
    
    def _get_agent_services(self, agent_class: type, container: Any) -> Dict[str, Any]:
        """
        Determine which services an agent needs based on its protocols.
        
        Args:
            agent_class: The agent class to analyze
            container: Container to get services from
            
        Returns:
            Dictionary of service_name -> service_instance for required services
        """
        services = {}
        
        # Common service names that agents might need
        # In a real implementation, this would use protocol inspection
        common_services = [
            'llm_service',
            'storage_service', 
            'state_adapter_service',
            'logging_service'
        ]
        
        for service_name in common_services:
            try:
                # Check if agent has a configure method for this service
                if hasattr(agent_class, f'configure_{service_name}'):
                    service_instance = container.get_service(service_name)
                    if service_instance:
                        services[service_name] = service_instance
                        self.logger.debug(
                            f"[GraphExecutionService] Found {service_name} for {agent_class.__name__}"
                        )
            except Exception as e:
                self.logger.warning(
                    f"[GraphExecutionService] Could not get {service_name}: {e}"
                )
        
        return services
    
    def _create_agents_from_metadata(
        self, nodes: Dict[str, Any], required_agents: Set[str], container: Any
    ) -> Dict[str, Any]:
        """
        Create fresh agent instances from metadata.
        
        Args:
            nodes: Dictionary of node metadata
            required_agents: Set of agent types that should be created
            container: Container to use for agent creation
            
        Returns:
            Dictionary of agent_type -> agent_instance
        """
        agents = {}
        
        self.logger.debug(
            f"[GraphExecutionService] Creating {len(required_agents)} agent types from metadata"
        )
        
        for agent_type in required_agents:
            try:
                # Use agent factory service to resolve agent class and create instance
                agent_class = self.agent_factory_service.resolve_agent_class(agent_type)
                
                # Create basic agent instance with minimal arguments
                # This is a simplified approach for metadata-based execution
                agent_instance = agent_class(
                    name=f"{agent_type}_instance",
                    prompt="",
                    context={},
                    logger=self.logger
                )
                
                agents[agent_type] = agent_instance
                
                self.logger.debug(
                    f"[GraphExecutionService] Created agent instance: {agent_type} ({agent_class.__name__})"
                )
                
            except Exception as e:
                self.logger.error(
                    f"[GraphExecutionService] Failed to create agent {agent_type}: {e}"
                )
                raise ValueError(f"Failed to create agent {agent_type}: {str(e)}")
        
        self.logger.info(
            f"[GraphExecutionService] Successfully created {len(agents)} agent instances"
        )
        
        return agents
    
    def _build_graph_definition_from_bundle(
        self, bundle: GraphBundle, agents: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build a graph definition from bundle metadata and agent instances.
        
        Args:
            bundle: GraphBundle with node metadata
            agents: Dictionary of created agent instances
            
        Returns:
            Graph definition dictionary compatible with existing graph execution
        """
        graph_def = {}
        
        for node_name, node in (bundle.nodes or {}).items():
            # Get the agent instance for this node's agent type
            agent_instance = agents.get(node.agent_type)
            if not agent_instance:
                raise ValueError(f"No agent instance found for type {node.agent_type}")
            
            # Create node with agent instance in context
            # This follows the existing pattern used in graph assembly
            graph_def[node_name] = type('GraphNode', (), {
                'context': {'instance': agent_instance},
                'name': node_name,
                'agent_type': node.agent_type
            })()
        
        self.logger.debug(
            f"[GraphExecutionService] Built graph definition with {len(graph_def)} nodes"
        )
        
        return graph_def

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the execution service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "GraphExecutionService",
            "execution_tracking_service_available": self.execution_tracking_service
            is not None,
            "execution_policy_service_available": self.execution_policy_service
            is not None,
            "state_adapter_service_available": self.state_adapter_service is not None,
            "graph_assembly_service_available": self.graph_assembly_service is not None,
            "graph_bundle_service_available": self.graph_bundle_service is not None,
            "dependencies_initialized": all(
                [
                    self.execution_tracking_service is not None,
                    self.execution_policy_service is not None,
                    self.state_adapter_service is not None,
                    self.graph_assembly_service is not None,
                    self.graph_bundle_service is not None,
                ]
            ),
            "capabilities": {
                "runnable_graph_execution": True,
                "definition_graph_execution": True,
                "execution_tracking_setup": True,
                "bundle_loading": True,
                "graph_assembly": True,
                "execution_coordination": True,
                "policy_evaluation": True,
                "state_management": True,
                "error_handling": True,
            },
            "execution_methods": [
                "execute_runnable_graph",
                "execute_from_definition",
                "setup_execution_tracking",
            ],
            "coordination_services": [
                "ExecutionTrackingService",
                "ExecutionPolicyService",
                "StateAdapterService",
                "GraphAssemblyService",
                "GraphBundleService",
            ],
        }
