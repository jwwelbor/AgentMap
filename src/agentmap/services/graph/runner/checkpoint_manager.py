"""
Checkpoint management for graph execution.

Handles checkpoint resume operations for interrupted graph executions.
Extracted from GraphRunnerService to improve separation of concerns.
"""

import time
from typing import Any, Dict, Optional

from agentmap.models.execution.result import ExecutionResult
from agentmap.models.execution.summary import ExecutionSummary
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.graph.graph_agent_instantiation_service import (
    GraphAgentInstantiationService,
)
from agentmap.services.graph.graph_assembly_service import GraphAssemblyService
from agentmap.services.graph.graph_checkpoint_service import GraphCheckpointService
from agentmap.services.interaction_handler_service import InteractionHandlerService
from agentmap.services.logging_service import LoggingService


class CheckpointManager:
    """Manages checkpoint operations for graph execution."""

    def __init__(
        self,
        logging_service: LoggingService,
        graph_agent_instantiation_service: GraphAgentInstantiationService,
        graph_assembly_service: GraphAssemblyService,
        graph_checkpoint_service: GraphCheckpointService,
        execution_tracking_service: ExecutionTrackingService,
        interaction_handler_service: InteractionHandlerService,
    ):
        """
        Initialize checkpoint manager.

        Args:
            logging_service: Service for logging operations
            graph_agent_instantiation_service: Service for agent instantiation
            graph_assembly_service: Service for graph assembly
            graph_checkpoint_service: Service for checkpoint operations
            execution_tracking_service: Service for tracking execution
            interaction_handler_service: Service for handling user interactions
        """
        self.logging_service = logging_service
        self.graph_instantiation = graph_agent_instantiation_service
        self.graph_assembly = graph_assembly_service
        self.graph_checkpoint = graph_checkpoint_service
        self.execution_tracking = execution_tracking_service
        self.interaction_handler = interaction_handler_service
        self.logger = logging_service.get_class_logger(self)

    def resume_from_checkpoint(
        self,
        bundle: GraphBundle,
        thread_id: str,
        checkpoint_state: Dict[str, Any],
        resume_node: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Resume graph execution from a checkpoint with injected state.

        Args:
            bundle: Graph bundle
            thread_id: Thread identifier
            checkpoint_state: State to resume with
            resume_node: Optional node to resume from

        Returns:
            ExecutionResult from resumed execution
        """
        from agentmap.models.graph import Graph

        from agentmap.services.graph.runner.utils import (
            create_node_registry_from_bundle,
        )

        graph_name = bundle.graph_name or "unknown"
        self.logger.info(
            f"⭐ Resuming graph execution from checkpoint: {graph_name} "
            f"(thread: {thread_id}, node: {resume_node})"
        )

        start_time = time.time()

        try:
            # Create execution tracker
            execution_tracker = self.execution_tracking.create_tracker(thread_id)

            # Instantiate agents
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

            # Assemble graph with checkpoint support
            self.logger.debug(
                f"Reassembling graph for checkpoint resume WITH checkpointer"
            )

            graph = Graph(
                name=bundle_with_instances.graph_name,
                nodes=bundle_with_instances.nodes,
                entry_point=bundle_with_instances.entry_point,
            )

            executable_graph = self.graph_assembly.assemble_with_checkpoint(
                graph=graph,
                agent_instances=bundle_with_instances.node_instances,
                node_definitions=create_node_registry_from_bundle(
                    bundle_with_instances, self.logger
                ),
                checkpointer=self.graph_checkpoint,
            )

            # Resume execution
            self.logger.debug(
                f"Resuming execution from checkpoint for thread: {thread_id}"
            )
            self.interaction_handler.mark_thread_resuming(thread_id)

            langgraph_config = {"configurable": {"thread_id": thread_id}}

            # Resume with Command pattern (None for suspend, value for human_interaction)
            from langgraph.types import Command

            # Check for both human interaction response and suspend resume value
            resume_value = checkpoint_state.get(
                "__human_response"
            ) or checkpoint_state.get("__resume_value")
            self.logger.debug(
                f"Resuming with value: {resume_value} (type: {type(resume_value).__name__})"
            )

            if resume_value is None:
                self.logger.debug(
                    "No explicit resume payload provided; injecting default resume marker"
                )
                resume_payload = {"__resume_marker": True}
            else:
                resume_payload = resume_value

            command_input = Command(resume=resume_payload)

            final_state = executable_graph.invoke(
                command_input, config=langgraph_config
            )

            # Build execution result
            summary_final_output = (
                final_state.copy() if isinstance(final_state, dict) else final_state
            )

            self.execution_tracking.complete_execution(execution_tracker)
            execution_summary = self.execution_tracking.to_summary(
                execution_tracker, graph_name, summary_final_output
            )

            execution_time = time.time() - start_time
            self.interaction_handler.mark_thread_completed(thread_id)

            graph_success = not final_state.get("__error", False)

            # Update state with metadata
            final_state.update(
                {
                    "__execution_summary": execution_summary,
                    "__graph_success": graph_success,
                    "__thread_id": thread_id,
                    "__resumed_from_node": resume_node,
                }
            )

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
