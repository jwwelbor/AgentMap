"""
GraphExecutionService for AgentMap.

Service that provides clean execution orchestration by coordinating with existing
ExecutionTrackingService and ExecutionPolicyService. Extracted from GraphRunnerService
to separate execution concerns from graph building and compilation.
"""

import time
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.models.execution_result import ExecutionResult
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.execution_policy_service import ExecutionPolicyService
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.graph_assembly_service import GraphAssemblyService
from agentmap.services.graph_bundle_service import GraphBundleService
from agentmap.services.logging_service import LoggingService


class GraphExecutionService:
    """
    Service for clean graph execution orchestration.
    
    Coordinates execution flow by working with existing execution-related services:
    - ExecutionTrackingService for tracking creation and management
    - ExecutionPolicyService for success evaluation  
    - StateAdapterService for state management
    - GraphAssemblyService for in-memory graph compilation
    - GraphBundleService for bundle loading
    
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
        logging_service: LoggingService
    ):
        """Initialize service with dependency injection.
        
        Args:
            execution_tracking_service: Service for creating execution trackers
            execution_policy_service: Service for policy evaluation
            state_adapter_service: Service for state management
            graph_assembly_service: Service for graph assembly from definitions
            graph_bundle_service: Service for graph bundle operations
            logging_service: Service for logging operations
        """
        self.execution_tracking_service = execution_tracking_service
        self.execution_policy_service = execution_policy_service
        self.state_adapter_service = state_adapter_service
        self.graph_assembly_service = graph_assembly_service
        self.graph_bundle_service = graph_bundle_service
        self.logger = logging_service.get_class_logger(self)
        
        self.logger.info("[GraphExecutionService] Initialized with execution coordination services")
    
    def setup_execution_tracking(self, graph_name: str) -> Any:
        """
        Setup execution tracking for a graph execution.
        
        Args:
            graph_name: Name of the graph for tracking context
            
        Returns:
            ExecutionTracker instance
        """
        self.logger.debug(f"[GraphExecutionService] Setting up execution tracking for: {graph_name}")
        
        # Use ExecutionTrackingService to create tracker
        execution_tracker = self.execution_tracking_service.create_tracker()
        
        self.logger.debug(f"[GraphExecutionService] Execution tracking setup complete for: {graph_name}")
        return execution_tracker
    
    def execute_compiled_graph(self, bundle_path: Path, state: Dict[str, Any]) -> ExecutionResult:
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
        
        self.logger.info(f"[GraphExecutionService] Executing compiled graph: {graph_name}")
        
        start_time = time.time()
        
        try:
            # Load the compiled graph bundle
            compiled_graph = self._load_compiled_graph_from_bundle(bundle_path)
            
            # Execute the graph with tracking
            final_state, execution_summary = self._execute_graph_with_tracking(
                compiled_graph, state, graph_name
            )
            
            # Calculate execution time and evaluate policy
            execution_time = time.time() - start_time
            graph_success = self.execution_policy_service.evaluate_success_policy(execution_summary)
            
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
                compiled_from="precompiled",
                error=None
            )
            
            self.logger.info(
                f"✅ COMPLETED COMPILED GRAPH: '{graph_name}' in {execution_time:.2f}s"
            )
            return execution_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.logger.error(
                f"❌ COMPILED GRAPH EXECUTION FAILED: '{graph_name}' after {execution_time:.2f}s"
            )
            self.logger.error(f"[GraphExecutionService] Error: {str(e)}")
            
            # Create error execution result
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=state,  # Return original state on error
                execution_summary=None,
                total_duration=execution_time,
                compiled_from="precompiled",
                error=str(e)
            )
            
            return execution_result
    
    def execute_from_definition(self, graph_def: Dict[str, Any], state: Dict[str, Any]) -> ExecutionResult:
        """
        Execute a graph from an in-memory graph definition.
        
        Args:
            graph_def: Graph definition dictionary with nodes and their configurations
            state: Initial state dictionary
            
        Returns:
            ExecutionResult with complete execution details
        """
        # Extract graph name from definition if available
        graph_name = self._extract_graph_name_from_definition(graph_def)
        
        self.logger.info(f"[GraphExecutionService] Executing from definition: {graph_name}")
        
        start_time = time.time()
        
        try:
            # Assemble the graph from definition using GraphAssemblyService
            compiled_graph = self._assemble_graph_from_definition(graph_def, graph_name)
            
            # Execute the graph with tracking
            final_state, execution_summary = self._execute_graph_with_tracking(
                compiled_graph, state, graph_name
            )
            
            # Calculate execution time and evaluate policy
            execution_time = time.time() - start_time
            graph_success = self.execution_policy_service.evaluate_success_policy(execution_summary)
            
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
                compiled_from="memory",
                error=None
            )
            
            self.logger.info(
                f"✅ COMPLETED DEFINITION GRAPH: '{graph_name}' in {execution_time:.2f}s"
            )
            return execution_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            self.logger.error(
                f"❌ DEFINITION GRAPH EXECUTION FAILED: '{graph_name}' after {execution_time:.2f}s"
            )
            self.logger.error(f"[GraphExecutionService] Error: {str(e)}")
            
            # Create error execution result
            execution_result = ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=state,  # Return original state on error
                execution_summary=None,
                total_duration=execution_time,
                compiled_from="memory",
                error=str(e)
            )
            
            return execution_result
    
    def _load_compiled_graph_from_bundle(self, bundle_path: Path) -> Any:
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
            self.logger.debug(
                f"[GraphExecutionService] GraphBundle loading failed, trying legacy format: {bundle_error}"
            )
            
            try:
                import pickle
                with open(bundle_path, "rb") as f:
                    compiled_graph = pickle.load(f)
                    self.logger.debug("[GraphExecutionService] Loaded legacy pickle format")
                    return compiled_graph
            except Exception as pickle_error:
                raise ValueError(
                    f"Could not load bundle in either GraphBundle or legacy format. "
                    f"GraphBundle error: {bundle_error}. Pickle error: {pickle_error}"
                )
    
    def _assemble_graph_from_definition(self, graph_def: Dict[str, Any], graph_name: str) -> Any:
        """
        Assemble an executable graph from a graph definition.
        
        Args:
            graph_def: Graph definition with nodes and configurations
            graph_name: Name of the graph for logging
            
        Returns:
            Executable compiled graph
            
        Raises:
            ValueError: If graph definition is invalid or assembly fails
        """
        if not graph_def:
            raise ValueError(f"Invalid or empty graph definition for graph: {graph_name}")
        
        self.logger.debug(f"[GraphExecutionService] Assembling graph from definition: {graph_name}")
        
        try:
            # Use GraphAssemblyService to assemble the graph
            # Note: This assumes the graph_def already has agent instances in context
            # The agent instantiation and service injection should be done by GraphRunnerService
            compiled_graph = self.graph_assembly_service.assemble_graph(
                graph_def=graph_def,
                node_registry=None,  # Node registry handled by calling service
                enable_logging=True
            )
            
            self.logger.debug(f"[GraphExecutionService] Graph assembly complete: {graph_name}")
            return compiled_graph
            
        except Exception as e:
            raise ValueError(f"Failed to assemble graph '{graph_name}': {str(e)}")
    
    def _execute_graph_with_tracking(
        self, 
        compiled_graph: Any, 
        state: Dict[str, Any], 
        graph_name: str
    ) -> tuple:
        """
        Execute a compiled graph with execution tracking.
        
        Args:
            compiled_graph: Executable graph object
            state: Initial state dictionary
            graph_name: Name of the graph for tracking
            
        Returns:
            Tuple of (final_state, execution_summary)
        """
        self.logger.debug(f"[GraphExecutionService] Executing graph with tracking: {graph_name}")
        
        # Initialize execution tracking
        execution_tracker = self.setup_execution_tracking(graph_name)
        
        # Log initial state info
        self.logger.debug(f"[GraphExecutionService] Initial state type: {type(state)}")
        self.logger.debug(
            f"[GraphExecutionService] Initial state keys: "
            f"{list(state.keys()) if hasattr(state, 'keys') else 'N/A'}"
        )
        
        # Execute the graph
        final_state = compiled_graph.invoke(state)
        
        # Log final state info
        self.logger.debug(f"[GraphExecutionService] Final state type: {type(final_state)}")
        self.logger.debug(
            f"[GraphExecutionService] Final state keys: "
            f"{list(final_state.keys()) if hasattr(final_state, 'keys') else 'N/A'}"
        )
        
        # Complete execution tracking
        execution_tracker.complete_execution()
        execution_summary = execution_tracker.get_summary()
        
        self.logger.debug(f"[GraphExecutionService] Execution tracking complete: {graph_name}")
        
        return final_state, execution_summary
    
    def _extract_graph_name_from_definition(self, graph_def: Dict[str, Any]) -> str:
        """
        Extract graph name from definition or generate a default.
        
        Args:
            graph_def: Graph definition dictionary
            
        Returns:
            Graph name string
        """
        # Try to find a name in the definition metadata
        if hasattr(graph_def, 'get') and graph_def.get('__graph_name'):
            return graph_def['__graph_name']
        
        # Generate name based on nodes
        if graph_def:
            node_names = list(graph_def.keys())
            return f"graph_{len(node_names)}_nodes"
        
        # Fallback name
        return "unknown_graph"
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the execution service for debugging.
        
        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "GraphExecutionService",
            "execution_tracking_service_available": self.execution_tracking_service is not None,
            "execution_policy_service_available": self.execution_policy_service is not None,
            "state_adapter_service_available": self.state_adapter_service is not None,
            "graph_assembly_service_available": self.graph_assembly_service is not None,
            "graph_bundle_service_available": self.graph_bundle_service is not None,
            "dependencies_initialized": all([
                self.execution_tracking_service is not None,
                self.execution_policy_service is not None,
                self.state_adapter_service is not None,
                self.graph_assembly_service is not None,
                self.graph_bundle_service is not None
            ]),
            "capabilities": {
                "compiled_graph_execution": True,
                "definition_graph_execution": True,
                "execution_tracking_setup": True,
                "bundle_loading": True,
                "graph_assembly": True,
                "execution_coordination": True,
                "policy_evaluation": True,
                "state_management": True,
                "error_handling": True
            },
            "execution_methods": [
                "execute_compiled_graph",
                "execute_from_definition",
                "setup_execution_tracking"
            ],
            "coordination_services": [
                "ExecutionTrackingService",
                "ExecutionPolicyService", 
                "StateAdapterService",
                "GraphAssemblyService",
                "GraphBundleService"
            ]
        }
