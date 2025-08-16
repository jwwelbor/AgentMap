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
from agentmap.services.graph.graph_assembly_service import GraphAssemblyService
from agentmap.services.graph.graph_bundle_service import GraphBundleService
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