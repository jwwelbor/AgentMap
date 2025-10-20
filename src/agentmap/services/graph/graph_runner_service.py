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

from langgraph.errors import GraphInterrupt

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
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.graph.graph_checkpoint_service import GraphCheckpointService
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
        graph_checkpoint_service: GraphCheckpointService,
        graph_bundle_service: GraphBundleService,
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
        self.graph_checkpoint = graph_checkpoint_service
        self.graph_bundle_service = graph_bundle_service

        # Check configuration for execution approach
        self.logger.info("GraphRunnerService initialized")

    def run(
        self,
        bundle: GraphBundle,
        initial_state: dict = None,
        parent_graph_name: Optional[str] = None,
        parent_tracker: Optional[Any] = None,
        is_subgraph: bool = False,
        validate_agents: bool = False,
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

            if validate_agents:
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
            # TODO: Only create and pass node_definitions if needed for orchestrator
            node_definitions = self._create_node_registry_from_bundle(
                bundle_with_instances
            )

            requires_checkpoint = self.graph_bundle_service.requires_checkpoint_support(
                bundle
            )

            execution_config = None

            if requires_checkpoint:
                self.logger.debug(
                    f"[GraphRunnerService] Assembling graph '{graph_name}' WITH checkpoint support"
                )

                thread_id = getattr(execution_tracker, "thread_id", None)
                self.logger.debug(
                    f"[GraphRunnerService] Thread ID for graph '{thread_id}'"
                )
                if not thread_id:
                    raise RuntimeError(
                        "Checkpoint execution requires execution tracker with thread_id"
                    )

                execution_config = {"configurable": {"thread_id": thread_id}}
                self.logger.debug(
                    f"[GraphRunnerService] Using checkpoint execution config with thread_id={thread_id}"
                )

                executable_graph = self.graph_assembly.assemble_with_checkpoint(
                    graph=graph,
                    agent_instances=bundle_with_instances.node_instances,
                    node_definitions=node_definitions,
                    checkpointer=self.graph_checkpoint,
                )
            else:
                self.logger.debug(
                    f"[GraphRunnerService] Assembling graph '{graph_name}' WITHOUT checkpoint support"
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
                config=execution_config,
            )

            # Check for suspended state even when invocation returns normally
            if requires_checkpoint and execution_config:
                thread_id = getattr(execution_tracker, "thread_id", None)
                if not thread_id:
                    self.logger.warning(
                        "⚠️ Missing thread_id after checkpoint execution; cannot inspect state"
                    )
                else:
                    state = executable_graph.get_state(execution_config)

                    if state.tasks:
                        interrupt_details = self._handle_langgraph_interrupt(
                            state=state,
                            bundle=bundle,
                            thread_id=thread_id,
                            execution_tracker=execution_tracker,
                        )

                        interrupt_type = (
                            interrupt_details.get("type", "unknown")
                            if interrupt_details
                            else self._extract_interrupt_type_from_state(state)
                        )

                        self._display_resume_instructions(
                            thread_id=thread_id,
                            bundle=bundle,
                            interrupt_type=interrupt_type,
                        )

                        self._log_interrupt_status(
                            graph_name, thread_id, interrupt_type
                        )

                        return self._create_interrupt_result(
                            graph_name=graph_name,
                            thread_id=thread_id,
                            state=state,
                            interrupt_type=interrupt_type,
                            interrupt_info=interrupt_details,
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

        except GraphInterrupt as e:
            # Handle LangGraph interrupt (from interrupt() call in agents)
            self.logger.info(f"🔄 Graph execution interrupted (LangGraph pattern)")

            # Get thread_id from execution tracker
            thread_id = execution_tracker.thread_id if execution_tracker else None

            if not thread_id:
                self.logger.error("❌ Cannot handle interrupt: no thread_id available")
                raise RuntimeError("Cannot handle interrupt: no thread_id") from e

            # Get graph state to extract interrupt metadata
            config = {"configurable": {"thread_id": thread_id}}
            state = executable_graph.get_state(config)

            # Process the interrupt if we have task information
            interrupt_details = None
            if state.tasks:
                interrupt_details = self._handle_langgraph_interrupt(
                    state=state,
                    bundle=bundle,
                    thread_id=thread_id,
                    execution_tracker=execution_tracker,
                )

                interrupt_type = (
                    interrupt_details.get("type", "unknown")
                    if interrupt_details
                    else self._extract_interrupt_type_from_state(state)
                )

                self._display_resume_instructions(
                    thread_id=thread_id,
                    bundle=bundle,
                    interrupt_type=interrupt_type,
                )
            else:
                interrupt_details = None
                interrupt_type = "unknown"

            self._log_interrupt_status(graph_name, thread_id, interrupt_type)

            # Return partial execution result indicating interruption
            return self._create_interrupt_result(
                graph_name=graph_name,
                thread_id=thread_id,
                state=state,
                interrupt_type=interrupt_type,
                interrupt_info=interrupt_details,
            )

        except ExecutionInterruptedException as e:
            # Legacy: Handle old custom exception (for backwards compatibility)
            self.logger.info(
                f"🔄 Graph execution interrupted (legacy pattern) in thread: {e.thread_id}"
            )

            # If interaction handler is available, process the interruption
            if self.interaction_handler:
                try:
                    # Handle the interruption (stores metadata and displays interaction)
                    self.interaction_handler.handle_execution_interruption(
                        exception=e,
                        bundle=bundle,
                        bundle_context=self._create_bundle_context(bundle),
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
        """Resume graph execution from a checkpoint with injected state."""
        import time

        from agentmap.models.execution.summary import ExecutionSummary

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

            from agentmap.models.graph import Graph

            graph = Graph(
                name=bundle_with_instances.graph_name,
                nodes=bundle_with_instances.nodes,
                entry_point=bundle_with_instances.entry_point,
            )

            executable_graph = self.graph_assembly.assemble_with_checkpoint(
                graph=graph,
                agent_instances=bundle_with_instances.node_instances,
                node_definitions=self._create_node_registry_from_bundle(
                    bundle_with_instances
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

    def _log_interrupt_status(
        self, graph_name: str, thread_id: str, interrupt_type: str
    ) -> None:
        """Log interrupt/suspend status with appropriate emoji and message."""
        if interrupt_type in {"suspend", "human_interaction"}:
            self.logger.info(
                f"⏸️  Graph execution suspended for '{graph_name}' "
                f"(thread: {thread_id}, type: {interrupt_type})"
            )
        else:
            self.logger.info(
                f"⏸️  Graph execution interrupted for '{graph_name}' "
                f"(thread: {thread_id}, type: {interrupt_type})"
            )

    def _extract_interrupt_type_from_state(self, state: Any) -> str:
        """Extract interrupt type from state tasks, returning 'unknown' if not found."""
        if not state or not getattr(state, "tasks", None):
            return "unknown"

        first_task = state.tasks[0]
        interrupts = getattr(first_task, "interrupts", None)
        if not interrupts:
            return "unknown"

        interrupt_value = getattr(interrupts[0], "value", {}) or {}
        if isinstance(interrupt_value, dict):
            return interrupt_value.get("type", "unknown")

        return "unknown"

    def _create_bundle_context(self, bundle: GraphBundle) -> Dict[str, Any]:
        """Create bundle context dict for interrupt handling."""
        return {
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

    def _extract_interrupt_metadata(
        self,
        state: Any,
        execution_tracker: Any,
        bundle: GraphBundle,
    ) -> Optional[Dict[str, Any]]:
        """Extract interrupt metadata from LangGraph state or execution tracker."""
        if state and getattr(state, "tasks", None):
            first_task = state.tasks[0]
            interrupts = getattr(first_task, "interrupts", None)
            if interrupts:
                interrupt = interrupts[0]
                interrupt_value = getattr(interrupt, "value", None)
                if isinstance(interrupt_value, dict):
                    return {
                        "type": interrupt_value.get("type", "unknown"),
                        "node_name": interrupt_value.get("node_name", "unknown"),
                        "raw": interrupt_value,
                    }

        if execution_tracker and getattr(execution_tracker, "node_executions", None):
            pending_node = None
            for node in reversed(execution_tracker.node_executions):
                if getattr(node, "success", None) is None:
                    pending_node = node
                    break
            if not pending_node and execution_tracker.node_executions:
                pending_node = execution_tracker.node_executions[-1]

            if pending_node:
                node_name = getattr(pending_node, "node_name", "unknown")
                node_config = None
                if bundle and getattr(bundle, "nodes", None):
                    node_config = bundle.nodes.get(node_name)

                agent_type = (getattr(node_config, "agent_type", "") or "").lower()
                if "suspend" in agent_type:
                    interrupt_type = "suspend"
                elif "human" in agent_type:
                    interrupt_type = "human_interaction"
                else:
                    interrupt_type = "unknown"

                inputs = getattr(pending_node, "inputs", None) or {}
                context = getattr(node_config, "context", {}) if node_config else {}
                if not isinstance(context, dict):
                    context = {}

                return {
                    "type": interrupt_type,
                    "node_name": node_name,
                    "inputs": inputs,
                    "agent_context": context,
                    "fallback": True,
                }

        return None

    def _handle_langgraph_interrupt(
        self,
        state: Any,
        bundle: GraphBundle,
        thread_id: str,
        execution_tracker: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle LangGraph GraphInterrupt by extracting and storing metadata.

        Returns
            Minimal interrupt info dict for downstream handling when available.
        """
        interrupt_metadata = self._extract_interrupt_metadata(
            state=state, execution_tracker=execution_tracker, bundle=bundle
        )

        if not interrupt_metadata:
            self.logger.warning(
                "No interrupt metadata found during interrupt handling for thread: %s",
                thread_id,
            )
            return None

        interrupt_type = interrupt_metadata.get("type", "unknown")
        node_name = interrupt_metadata.get("node_name", "unknown")
        interrupt_value = interrupt_metadata.get("raw") or {}

        self.logger.debug(
            f"Processing interrupt via metadata: type={interrupt_type}, node={node_name}"
        )

        bundle_context = self._create_bundle_context(bundle)
        summary_info = {
            "type": interrupt_type,
            "node_name": node_name,
            "thread_id": thread_id,
        }

        if interrupt_type == "human_interaction":
            if not interrupt_value:
                self.logger.warning(
                    "Missing human interaction metadata for node '%s'; skipping interaction storage",
                    node_name,
                )
                return summary_info

            from agentmap.models.human_interaction import (
                HumanInteractionRequest,
                InteractionType,
            )

            interaction_request = HumanInteractionRequest(
                thread_id=thread_id,
                node_name=node_name,
                interaction_type=InteractionType(
                    interrupt_value.get("interaction_type", "text_input")
                ),
                prompt=interrupt_value.get("prompt", ""),
                context=interrupt_value.get("context", {}),
                options=interrupt_value.get("options", []),
                timeout_seconds=interrupt_value.get("timeout_seconds"),
            )

            self.interaction_handler._store_interaction_request(interaction_request)
            self.interaction_handler._store_thread_metadata(
                thread_id=thread_id,
                interaction_request=interaction_request,
                checkpoint_data={
                    "node_name": node_name,
                    "inputs": interrupt_value.get("context", {}),
                    "agent_context": {},
                    "execution_tracker": execution_tracker,
                },
                bundle=bundle,
                bundle_context=bundle_context,
            )

            from agentmap.deployment.cli.display_utils import (
                display_interaction_request,
            )

            display_interaction_request(interaction_request)
            summary_info["interaction_id"] = str(interaction_request.id)

            self.logger.info(
                "✅ Human interaction stored and displayed for thread: %s", thread_id
            )

        elif interrupt_type == "suspend":
            checkpoint_inputs = (
                interrupt_value.get("inputs", {})
                if isinstance(interrupt_value, dict)
                else {}
            )
            if not checkpoint_inputs:
                checkpoint_inputs = interrupt_metadata.get("inputs", {})

            agent_context = (
                interrupt_value.get("agent_context", {})
                if isinstance(interrupt_value, dict)
                else {}
            )
            if not agent_context:
                agent_context = interrupt_metadata.get("agent_context", {})

            checkpoint_payload = {
                "node_name": node_name,
                "inputs": checkpoint_inputs,
                "agent_context": agent_context,
                "execution_tracker": execution_tracker,
            }
            if isinstance(interrupt_value, dict):
                if "reason" in interrupt_value:
                    checkpoint_payload["reason"] = interrupt_value.get("reason")
                if "external_ref" in interrupt_value:
                    checkpoint_payload["external_ref"] = interrupt_value.get(
                        "external_ref"
                    )

            self.interaction_handler._store_thread_metadata_suspend_only(
                thread_id=thread_id,
                checkpoint_data=checkpoint_payload,
                bundle=bundle,
                bundle_context=bundle_context,
            )

            self.logger.info("✅ Suspend checkpoint stored for thread: %s", thread_id)

        else:
            self.logger.warning(
                "⚠️ Unknown interrupt type '%s' for thread: %s",
                interrupt_type,
                thread_id,
            )

        return summary_info

    def _create_interrupt_result(
        self,
        graph_name: str,
        thread_id: str,
        state: Any,
        interrupt_type: str = "unknown",
        interrupt_info: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """Create an ExecutionResult for an interrupted execution."""
        from agentmap.models.execution.summary import ExecutionSummary

        # Build interrupt info from provided data or extract from state
        info = dict(interrupt_info) if interrupt_info else {}
        if not info and state and getattr(state, "tasks", None):
            first_task = state.tasks[0]
            interrupts = getattr(first_task, "interrupts", None)
            if interrupts:
                interrupt_value = getattr(interrupts[0], "value", {})
                if isinstance(interrupt_value, dict):
                    info = {
                        "type": interrupt_value.get("type", "unknown"),
                        "node_name": interrupt_value.get("node_name", "unknown"),
                    }

        # Fill in defaults
        info.setdefault("type", interrupt_type)
        info.setdefault("node_name", "unknown")
        info.setdefault("thread_id", thread_id)

        status = (
            "suspended"
            if interrupt_type in {"suspend", "human_interaction"}
            else "interrupted"
        )

        execution_summary = ExecutionSummary(
            graph_name=graph_name,
            status=status,
            graph_success=False,
        )

        final_state = {
            "__interrupted": True,
            "__thread_id": thread_id,
            "__interrupt_info": info,
            "__execution_summary": execution_summary,
            "__interrupt_type": info["type"],
        }

        self.logger.info(
            f"🔄 Returning {status} execution result for thread: {thread_id}"
        )

        return ExecutionResult(
            graph_name=graph_name,
            success=False,
            final_state=final_state,
            execution_summary=execution_summary,
            total_duration=0.0,
            error=None,
        )

    def _display_resume_instructions(
        self,
        thread_id: str,
        bundle: GraphBundle,
        interrupt_type: str,
    ) -> None:
        """Emit resume instructions via logger and CLI helpers."""

        graph_name = getattr(bundle, "graph_name", "unknown")
        config_file = getattr(bundle, "config_path", None)
        if config_file is not None:
            config_file = str(config_file)
        header = "=" * 60
        config_arg = f" --config {config_file}" if config_file else ""
        base_command = f'agentmap resume {thread_id} "<response>"{config_arg}'

        lines = [
            "",
            header,
            (
                "⏸️  EXECUTION PAUSED - HUMAN INTERACTION REQUIRED"
                if interrupt_type == "human_interaction"
                else "⏸️  EXECUTION SUSPENDED"
            ),
            header,
            f"Thread ID: {thread_id}",
            f"Graph: {graph_name}",
            "",
        ]

        if interrupt_type == "human_interaction":
            lines.extend(
                [
                    "To resume execution, respond with:",
                    f"  {base_command}",
                    "",
                    "Examples:",
                    (
                        f"  • Approve: agentmap resume {thread_id} "
                        f'"approve"{config_arg}'
                    ),
                    (
                        f"  • Reject: agentmap resume {thread_id} "
                        f'"reject"{config_arg}'
                    ),
                    (
                        f"  • Text: agentmap resume {thread_id} "
                        f'"your response"{config_arg}'
                    ),
                ]
            )
        else:
            lines.extend(
                [
                    "To resume execution, provide the external result and run:",
                    f"  {base_command}",
                ]
            )

        lines.append(header)

        self.logger.info("\n".join(lines))

        try:
            from agentmap.deployment.cli.display_utils import (
                display_resume_instructions as cli_display_resume,
            )

            cli_display_resume(
                thread_id=thread_id,
                graph_name=graph_name,
                interrupt_type=interrupt_type,
                config_file=config_file,
            )
        except ImportError:
            self.logger.debug(
                "[GraphRunnerService] CLI display utilities unavailable; "
                "logger output provided"
            )
        except Exception as display_error:
            self.logger.debug(
                "[GraphRunnerService] Failed to display CLI resume instructions:"
                f" {display_error}"
            )
