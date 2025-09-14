"""
Simplified GraphRunnerService for AgentMap.

Orchestrates graph execution by coordinating:
1. Direct Import (default): Skip bootstrap and use direct agent instantiation
2. Legacy Bootstrap: Register agent classes then instantiate
3. Instantiation - create and configure agent instances
4. Assembly - build the executable graph
5. Execution - run the graph

Approach is configurable via execution.use_direct_import_agents setting.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.execution.config import ExecutionConfig
from agentmap.models.execution.result import ExecutionResult
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.graph.graph_agent_instantiation_service import (
    GraphAgentInstantiationService,
)
from agentmap.services.graph.graph_assembly_service import GraphAssemblyService
from agentmap.services.graph.graph_bootstrap_service import GraphBootstrapService
from agentmap.services.graph.graph_execution_service import GraphExecutionService
from agentmap.services.logging_service import LoggingService


class RunOptions:
    """Simple options container for graph execution."""

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        self.initial_state = initial_state or {}


class GraphRunnerService:
    """
    Simplified facade service for graph execution orchestration.

    Coordinates the complete graph execution pipeline with configurable approaches:
    1. Direct Import (default): Skip bootstrap and use direct agent instantiation
    2. Legacy Bootstrap: Register agent classes then instantiate

    Supports both approaches based on configuration for backwards compatibility.
    """

    def __init__(
        self,
        app_config_service: AppConfigService,
        graph_bootstrap_service: Optional[GraphBootstrapService],
        graph_agent_instantiation_service: GraphAgentInstantiationService,
        graph_assembly_service: GraphAssemblyService,
        graph_execution_service: GraphExecutionService,
        execution_tracking_service: ExecutionTrackingService,
        logging_service: LoggingService,
        interaction_handler_service: Optional[Any] = None,
    ):
        """Initialize orchestration service with all pipeline services."""
        self.app_config = app_config_service
        self.graph_bootstrap = (
            graph_bootstrap_service  # Optional for direct import mode
        )
        self.graph_instantiation = graph_agent_instantiation_service
        self.graph_assembly = graph_assembly_service
        self.graph_execution = graph_execution_service
        self.execution_tracking = execution_tracking_service
        self.logging_service = logging_service  # Store logging service for internal use
        self.logger = logging_service.get_class_logger(self)
        self.interaction_handler = interaction_handler_service

        # Check configuration for execution approach
        self.logger.info(
            "GraphRunnerService initialized with direct import approach (no bootstrap)"
        )

    def run(
        self,
        bundle: GraphBundle,
        initial_state: dict = None,
        parent_graph_name: Optional[str] = None,
        parent_tracker: Optional[Any] = None,
        is_subgraph: bool = False,
    ) -> ExecutionResult:
        """
        Run graph execution using a prepared bundle.

        Supports both execution approaches based on configuration:
        1. Direct Import: Skip bootstrap, instantiate agents directly
        2. Legacy Bootstrap: Register agent classes then instantiate

        Args:
            bundle: Prepared GraphBundle with all metadata
            initial_state: Optional initial state for execution
            parent_graph_name: Name of parent graph (for subgraph execution)
            parent_tracker: Parent execution tracker (for subgraph tracking)
            is_subgraph: Whether this is a subgraph execution

        Returns:
            ExecutionResult from graph execution

        Raises:
            Exception: Any errors from pipeline stages (not swallowed)
        """
        graph_name = bundle.graph_name or "unknown"
        approach = "direct import"  # if self.use_direct_import else "bootstrap"

        # Add contextual logging for subgraph execution
        if is_subgraph and parent_graph_name:
            self.logger.info(
                f"⭐ Starting subgraph pipeline for: {graph_name} "
                f"(parent: {parent_graph_name}, using {approach} approach)"
            )
        else:
            self.logger.info(
                f"⭐ Starting graph pipeline for: {graph_name} (using {approach} approach)"
            )

        if initial_state is None:
            initial_state = {}

        try:
            # Phase 2: Create execution tracker for this run
            self.logger.debug(
                f"[GraphRunnerService] Phase 2: Setting up execution tracking"
            )

            # Create execution tracker - always create a new tracker
            # For subgraphs, we'll link it to the parent tracker after execution
            execution_tracker = self.execution_tracking.create_tracker()

            if is_subgraph and parent_tracker:
                self.logger.debug(
                    f"[GraphRunnerService] Created tracker for subgraph: {graph_name} "
                    f"(will be linked to parent tracker)"
                )
            else:
                self.logger.debug(
                    f"[GraphRunnerService] Created root tracker for graph: {graph_name}"
                )

            # Phase 3: Instantiate - create and configure agent instances
            self.logger.debug(
                f"[GraphRunnerService] Phase 3: Instantiating agents for {graph_name}"
            )
            bundle_with_instances = self.graph_instantiation.instantiate_agents(
                bundle, execution_tracker
            )

            # Validate instantiation
            validation = self.graph_instantiation.validate_instantiation(
                bundle_with_instances
            )
            if not validation["valid"]:
                raise RuntimeError(
                    f"Agent instantiation validation failed: {validation}"
                )

            self.logger.debug(
                f"[GraphRunnerService] Instantiation completed: "
                f"{validation['instantiated_nodes']} agents ready"
            )

            # Phase 4: Assembly - build the executable graph
            self.logger.debug(
                f"[GraphRunnerService] Phase 4: Assembling graph for {graph_name}"
            )

            # Create Graph model from bundle for assembly
            from agentmap.models.graph import Graph

            graph = Graph(
                name=bundle_with_instances.graph_name,
                nodes=bundle_with_instances.nodes,
                entry_point=bundle_with_instances.entry_point,
            )

            # Get agent instances from bundle's node_registry
            if not bundle_with_instances.node_instances:
                raise RuntimeError("No agent instances found in bundle.node_registry")

            # Create node definitions registry for orchestrators
            node_definitions = self._create_node_registry_from_bundle(
                bundle_with_instances
            )

            executable_graph = self.graph_assembly.assemble_graph(
                graph=graph,
                agent_instances=bundle_with_instances.node_instances,  # Pass agent instances
                orchestrator_node_registry=node_definitions,  # Pass node definitions for orchestrators
            )
            self.logger.debug(f"[GraphRunnerService] Graph assembly completed")

            # Phase 5: Execution - run the graph
            self.logger.debug(
                f"[GraphRunnerService] Phase 5: Executing graph {graph_name}"
            )
            result = self.graph_execution.execute_compiled_graph(
                executable_graph=executable_graph,
                graph_name=graph_name,
                initial_state=initial_state,
                execution_tracker=execution_tracker,
            )

            # Link subgraph tracker to parent if this is a subgraph execution
            if is_subgraph and parent_tracker:
                self.execution_tracking.record_subgraph_execution(
                    tracker=parent_tracker,
                    subgraph_name=graph_name,
                    subgraph_tracker=execution_tracker,
                )
                self.logger.debug(
                    f"[GraphRunnerService] Linked subgraph tracker to parent for: {graph_name}"
                )

            # Log final status with subgraph context
            if result.success:
                if is_subgraph and parent_graph_name:
                    self.logger.info(
                        f"✅ Subgraph pipeline completed successfully for: {graph_name} "
                        f"(parent: {parent_graph_name}, duration: {result.total_duration:.2f}s)"
                    )
                else:
                    self.logger.info(
                        f"✅ Graph pipeline completed successfully for: {graph_name} "
                        f"(duration: {result.total_duration:.2f}s)"
                    )
            else:
                if is_subgraph and parent_graph_name:
                    self.logger.error(
                        f"❌ Subgraph pipeline failed for: {graph_name} "
                        f"(parent: {parent_graph_name}) - {result.error}"
                    )
                else:
                    self.logger.error(
                        f"❌ Graph pipeline failed for: {graph_name} - {result.error}"
                    )

            return result

        except ExecutionInterruptedException as e:
            # Handle human interaction interruption
            self.logger.info(
                f"🔄 Graph execution interrupted for human interaction in thread: {e.thread_id}"
            )

            # If interaction handler is available, process the interruption
            if self.interaction_handler:
                try:
                    # Extract bundle context for rehydration
                    bundle_context = {
                        "csv_hash": getattr(bundle, "csv_hash", None),
                        "bundle_path": (
                            str(bundle.bundle_path)
                            if hasattr(bundle, "bundle_path") and bundle.bundle_path
                            else None
                        ),
                        "csv_path": (
                            str(bundle.csv_path)
                            if hasattr(bundle, "csv_path") and bundle.csv_path
                            else None
                        ),
                        "graph_name": bundle.graph_name,
                    }

                    # Handle the interruption (stores metadata and displays interaction)
                    self.interaction_handler.handle_execution_interruption(
                        exception=e,
                        bundle=bundle,
                        bundle_context=bundle_context,
                    )

                    self.logger.info(
                        f"✅ Interaction handling completed for thread: {e.thread_id}. "
                        f"Execution paused pending user response."
                    )

                except Exception as handler_error:
                    self.logger.error(
                        f"❌ Failed to handle interaction for thread {e.thread_id}: {str(handler_error)}"
                    )
            else:
                self.logger.warning(
                    f"⚠️ No interaction handler configured. Interaction for thread {e.thread_id} not handled."
                )

            # Re-raise the exception for higher-level handling
            raise

        except Exception as e:
            # Log with subgraph context if applicable
            if is_subgraph and parent_graph_name:
                self.logger.error(
                    f"❌ Subgraph pipeline failed for '{graph_name}' "
                    f"(parent: {parent_graph_name}): {str(e)}"
                )
            else:
                self.logger.error(
                    f"❌ Pipeline failed for graph '{graph_name}': {str(e)}"
                )

            # Return error result with minimal execution summary
            from agentmap.models.execution.summary import ExecutionSummary

            error_summary = ExecutionSummary(
                graph_name=graph_name, status="failed", graph_success=False
            )

            return ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=initial_state,
                execution_summary=error_summary,
                total_duration=0.0,
                compiled_from="pipeline",
                error=str(e),
            )

    def _create_node_registry_from_bundle(self, bundle: GraphBundle) -> dict:
        """
        Create node registry from bundle for orchestrator agents.

        Transforms Node objects into the metadata format expected by OrchestratorService
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
            f"[GraphRunnerService] Created node registry with {len(registry)} nodes "
            f"for orchestrator routing"
        )

        return registry

    def get_pipeline_status(self) -> dict:
        """
        Get status of all pipeline services and execution approach.

        Returns:
            Dictionary with service availability status and configuration
        """
        # Determine required services based on execution approach
        required_services = [
            self.graph_instantiation is not None,
            self.graph_assembly is not None,
            self.graph_execution is not None,
            self.execution_tracking is not None,
        ]

        # Determine pipeline stages based on approach
        pipeline_stages = [
            "1. Skip bootstrap (direct import enabled)",
            "2. Create execution tracker",
            "3. Instantiate agents (direct import)",
            "4. Assemble executable graph",
            "5. Execute graph",
        ]

        return {
            "service": "GraphRunnerService",
            "execution_approach": "direct_import",
            "pipeline_ready": all(required_services),
            "services": {
                "config": self.app_config is not None,
                "instantiation": self.graph_instantiation is not None,
                "assembly": self.graph_assembly is not None,
                "execution": self.graph_execution is not None,
                "tracking": self.execution_tracking is not None,
            },
            "pipeline_stages": pipeline_stages,
        }

    def get_default_options(self) -> RunOptions:
        """
        Create default options for graph execution.

        Returns:
            RunOptions with default settings
        """
        return RunOptions()

    def run_with_config(
        self, bundle: GraphBundle, config: ExecutionConfig
    ) -> ExecutionResult:
        """
        Run graph execution with checkpoint configuration support.

        This method extends the standard run() method to support:
        - Checkpoint service configuration
        - Thread-based state management
        - Resumption from saved checkpoints

        Args:
            bundle: Prepared GraphBundle with all metadata
            config: ExecutionConfig with checkpoint and thread settings

        Returns:
            ExecutionResult from graph execution
        """
        graph_name = bundle.graph_name or "unknown"

        # Log execution mode
        if config.resume_from_checkpoint:
            self.logger.info(
                f"⭐ Resuming graph execution for: {graph_name} "
                f"(thread: {config.thread_id})"
            )
        else:
            self.logger.info(
                f"⭐ Starting new graph execution for: {graph_name} "
                f"(thread: {config.thread_id})"
            )

        try:
            # Phase 1: Create execution tracker
            execution_tracker = self.execution_tracking.create_tracker()

            # Phase 2: Instantiate agents
            self.logger.debug(f"Instantiating agents for {graph_name}")
            bundle_with_instances = self.graph_instantiation.instantiate_agents(
                bundle, execution_tracker
            )

            # Validate instantiation
            validation = self.graph_instantiation.validate_instantiation(
                bundle_with_instances
            )
            if not validation["valid"]:
                raise RuntimeError(
                    f"Agent instantiation validation failed: {validation}"
                )

            # Phase 3: Assembly with checkpoint support
            self.logger.debug(f"Assembling graph with checkpoint support")

            from agentmap.models.graph import Graph

            graph = Graph(
                name=bundle_with_instances.graph_name,
                nodes=bundle_with_instances.nodes,
                entry_point=bundle_with_instances.entry_point,
            )

            # Check if assembly service supports checkpointing
            if config.checkpointer and hasattr(
                self.graph_assembly, "assemble_with_checkpoint"
            ):
                executable_graph = self.graph_assembly.assemble_with_checkpoint(
                    graph=graph,
                    agent_instances=bundle_with_instances.node_instances,
                    node_definitions=self._create_node_registry_from_bundle(
                        bundle_with_instances
                    ),
                    checkpointer=config.checkpointer,
                )
            else:
                # Fallback to standard assembly
                executable_graph = self.graph_assembly.assemble_graph(
                    graph=graph,
                    agent_instances=bundle_with_instances.node_instances,
                    orchestrator_node_registry=self._create_node_registry_from_bundle(
                        bundle_with_instances
                    ),
                )

                if config.checkpointer:
                    self.logger.warning(
                        "GraphAssemblyService doesn't support checkpointing. "
                        "Checkpoint functionality will be limited."
                    )

            # Phase 4: Execution with config
            self.logger.debug(f"Executing graph with thread_id: {config.thread_id}")

            # Prepare initial state
            initial_state = config.get_merged_initial_state()

            # Execute with LangGraph config
            if config.checkpointer:
                # Execute with checkpoint configuration
                result = self._execute_with_checkpoint(
                    executable_graph=executable_graph,
                    graph_name=graph_name,
                    initial_state=initial_state,
                    execution_tracker=execution_tracker,
                    config=config,
                )
            else:
                # Standard execution
                result = self.graph_execution.execute_compiled_graph(
                    executable_graph=executable_graph,
                    graph_name=graph_name,
                    initial_state=initial_state,
                    execution_tracker=execution_tracker,
                )

            # Log result
            if result.success:
                self.logger.info(
                    f"✅ Graph execution completed for: {graph_name} "
                    f"(thread: {config.thread_id}, duration: {result.total_duration:.2f}s)"
                )
            else:
                self.logger.error(
                    f"❌ Graph execution failed for: {graph_name} "
                    f"(thread: {config.thread_id}) - {result.error}"
                )

            return result

        except ExecutionInterruptedException as e:
            # Handle human interaction interruption in checkpoint execution
            self.logger.info(
                f"🔄 Checkpointed graph execution interrupted for human interaction in thread: {e.thread_id}"
            )

            # If interaction handler is available, process the interruption
            if self.interaction_handler:
                try:
                    # Extract bundle context for rehydration
                    bundle_context = {
                        "csv_hash": getattr(bundle, "csv_hash", None),
                        "bundle_path": (
                            str(bundle.bundle_path)
                            if hasattr(bundle, "bundle_path") and bundle.bundle_path
                            else None
                        ),
                        "csv_path": (
                            str(bundle.csv_path)
                            if hasattr(bundle, "csv_path") and bundle.csv_path
                            else None
                        ),
                        "graph_name": bundle.graph_name,
                    }

                    # Handle the interruption (stores metadata and displays interaction)
                    self.interaction_handler.handle_execution_interruption(
                        exception=e,
                        bundle=bundle,
                        bundle_context=bundle_context,
                    )

                    self.logger.info(
                        f"✅ Interaction handling completed for thread: {e.thread_id}. "
                        f"Checkpointed execution paused pending user response."
                    )

                except Exception as handler_error:
                    self.logger.error(
                        f"❌ Failed to handle checkpointed interaction for thread {e.thread_id}: {str(handler_error)}"
                    )
            else:
                self.logger.warning(
                    f"⚠️ No interaction handler configured. Checkpointed interaction for thread {e.thread_id} not handled."
                )

            # Re-raise the exception for higher-level handling
            raise

        except Exception as e:
            self.logger.error(
                f"❌ Execution failed for graph '{graph_name}' "
                f"(thread: {config.thread_id}): {str(e)}"
            )

            from agentmap.models.execution.summary import ExecutionSummary

            error_summary = ExecutionSummary(
                graph_name=graph_name, status="failed", graph_success=False
            )

            return ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=config.initial_state or {},
                execution_summary=error_summary,
                total_duration=0.0,
                compiled_from="pipeline",
                error=str(e),
            )

    def _execute_with_checkpoint(
        self,
        executable_graph: Any,
        graph_name: str,
        initial_state: Dict[str, Any],
        execution_tracker: Any,
        config: ExecutionConfig,
    ) -> ExecutionResult:
        """
        Execute graph with checkpoint support.

        This method wraps the standard execution with LangGraph
        checkpoint configuration.
        """
        import time

        start_time = time.time()

        try:
            # Create LangGraph config
            langgraph_config = config.to_langgraph_config()

            # Log checkpoint status
            if config.resume_from_checkpoint:
                self.logger.info(
                    f"Resuming from checkpoint for thread: {config.thread_id}"
                )
            else:
                self.logger.info(
                    f"Starting new checkpointed execution for thread: {config.thread_id}"
                )

            # Invoke with checkpoint config
            # LangGraph will automatically load checkpoint if it exists
            final_state = executable_graph.invoke(
                initial_state, config=langgraph_config
            )

            # Complete tracking
            self.execution_tracking.complete_execution(execution_tracker)
            execution_summary = self.execution_tracking.to_summary(
                execution_tracker, graph_name, final_state
            )

            # Calculate execution time
            execution_time = time.time() - start_time

            # For now, assume success unless there's an error in final_state
            graph_success = not final_state.get("__error", False)

            # Update state with execution metadata
            final_state["__execution_summary"] = execution_summary
            final_state["__graph_success"] = graph_success
            final_state["__thread_id"] = config.thread_id

            return ExecutionResult(
                graph_name=graph_name,
                success=graph_success,
                final_state=final_state,
                execution_summary=execution_summary,
                total_duration=execution_time,
                compiled_from="checkpointed",
                error=None,
            )

        except Exception as e:
            execution_time = time.time() - start_time

            self.logger.error(
                f"Checkpointed execution failed for '{graph_name}' "
                f"(thread: {config.thread_id}): {str(e)}"
            )

            # Create error summary
            from agentmap.models.execution.summary import ExecutionSummary

            execution_summary = ExecutionSummary(
                graph_name=graph_name, status="failed", graph_success=False
            )

            return ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=initial_state,
                execution_summary=execution_summary,
                total_duration=execution_time,
                compiled_from="checkpointed",
                error=str(e),
            )
