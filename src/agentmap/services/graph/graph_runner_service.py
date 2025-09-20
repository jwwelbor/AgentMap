"""
Simplified GraphRunnerService for AgentMap.

Orchestrates graph execution by coordinating:
1. Direct Import (default): declarative agent instantiation
2. Instantiation - create and configure agent instances
3. Assembly - build the executable graph
4. Execution - run the graph

Approach is configurable via execution.use_direct_import_agents setting.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
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
from agentmap.services.interaction_handler_service import InteractionHandlerService
from agentmap.services.logging_service import LoggingService


class RunOptions:
    """Simple options container for graph execution."""

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        self.initial_state = initial_state or {}


class GraphRunnerService:
    """
    Simplified facade service for graph execution orchestration.

    Coordinates the complete graph execution pipeline

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
        interaction_handler_service: InteractionHandlerService,
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
        self.logger.info("GraphRunnerService initialized")

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
        graph_name = bundle.graph_name

        # Add contextual logging for subgraph execution
        if is_subgraph and parent_graph_name:
            self.logger.info(
                f"⭐ Starting subgraph pipeline for: {graph_name} "
                f"(parent: {parent_graph_name})"
            )
        else:
            self.logger.info(f"⭐ Starting graph pipeline for: {graph_name}")

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
                # TODO: Only create and pass node_definitions if needed
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

    def resume_from_checkpoint(
        self,
        bundle: GraphBundle,
        thread_id: str,
        checkpoint_state: Dict[str, Any],
        resume_node: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Resume graph execution from a checkpoint with injected state.

        This method:
        1. Recreates the executable graph
        2. Uses LangGraph's checkpoint loading
        3. Continues execution from the interruption point

        Args:
            bundle: GraphBundle to execute
            thread_id: Thread ID for checkpoint retrieval
            checkpoint_state: State from checkpoint with human response injected
            resume_node: Node where execution was interrupted

        Returns:
            ExecutionResult from the resumed execution
        """
        import time

        from agentmap.models.execution.summary import ExecutionSummary

        graph_name = bundle.graph_name or "unknown"

        self.logger.info(
            f"⭐ Resuming graph execution from checkpoint: {graph_name} "
            f"(thread: {thread_id}, node: {resume_node})"
        )

        start_time = time.time()

        try:
            # Phase 1: Create execution tracker
            execution_tracker = self.execution_tracking.create_tracker()

            # Phase 2: Instantiate agents (same as normal run)
            self.logger.debug(f"Re-instantiating agents for checkpoint resume")
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
            self.logger.debug(f"Reassembling graph for checkpoint resume")

            from agentmap.models.graph import Graph

            graph = Graph(
                name=bundle_with_instances.graph_name,
                nodes=bundle_with_instances.nodes,
                entry_point=bundle_with_instances.entry_point,
            )

            # Assemble with checkpoint service
            executable_graph = self.graph_assembly.assemble_graph(
                graph=graph,
                agent_instances=bundle_with_instances.node_instances,
                orchestrator_node_registry=self._create_node_registry_from_bundle(
                    bundle_with_instances
                ),
            )

            # Phase 4: Resume execution with checkpoint
            self.logger.debug(
                f"Resuming execution from checkpoint for thread: {thread_id}"
            )
            self.interaction_handler.mark_thread_resuming(thread_id)

            # Create LangGraph config pointing to existing checkpoint
            langgraph_config = {
                "configurable": {
                    "thread_id": thread_id,
                    # This tells LangGraph to load from checkpoint
                    "checkpoint_namespace": "agentmap",
                    "checkpoint_id": checkpoint_state.get("__checkpoint_id"),
                }
            }

            # === KEY DIFFERENCE: Pass checkpoint state, not initial state ===
            # LangGraph will merge this with the loaded checkpoint
            final_state = executable_graph.invoke(
                checkpoint_state,  # State with optional human response injected
                config=langgraph_config,
            )

            # Complete tracking and create result
            self.execution_tracking.complete_execution(execution_tracker)
            execution_summary = self.execution_tracking.to_summary(
                execution_tracker, graph_name, final_state
            )

            execution_time = time.time() - start_time

            self.interaction_handler.mark_thread_completed(thread_id)

            # Evaluate success
            graph_success = not final_state.get("__error", False)

            # Update state with metadata
            final_state["__execution_summary"] = execution_summary
            final_state["__graph_success"] = graph_success
            final_state["__thread_id"] = thread_id
            final_state["__resumed_from_node"] = resume_node

            self.logger.info(
                f"✅ Graph resumed successfully: '{graph_name}' "
                f"(thread: {thread_id}, duration: {execution_time:.2f}s)"
            )

            return ExecutionResult(
                graph_name=graph_name,
                success=graph_success,
                final_state=final_state,
                execution_summary=execution_summary,
                total_duration=execution_time,
                error=None,
            )

        except Exception as e:
            execution_time = time.time() - start_time

            self.logger.error(
                f"❌ Resume from checkpoint failed for '{graph_name}' "
                f"(thread: {thread_id}): {str(e)}"
            )

            # Create error summary
            execution_summary = ExecutionSummary(
                graph_name=graph_name, status="failed", graph_success=False
            )

            return ExecutionResult(
                graph_name=graph_name,
                success=False,
                final_state=checkpoint_state,
                execution_summary=execution_summary,
                total_duration=execution_time,
                error=str(e),
            )
