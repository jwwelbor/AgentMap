"""
Simplified GraphRunnerService for AgentMap.

Orchestrates graph execution by coordinating:
1. Direct Import (default): declarative agent instantiation
2. Instantiation - create and configure agent instances
3. Assembly - build the executable graph
4. Execution - run the graph

Approach is configurable via execution.use_direct_import_agents setting.

Refactored: Large methods extracted to dedicated modules in runner/ package.
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from langgraph.errors import GraphInterrupt

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.execution.result import ExecutionResult
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.declaration_registry_service import DeclarationRegistryService
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.graph.graph_agent_instantiation_service import (
    GraphAgentInstantiationService,
)
from agentmap.services.graph.graph_assembly_service import GraphAssemblyService
from agentmap.services.graph.graph_bootstrap_service import GraphBootstrapService
from agentmap.services.graph.graph_bundle_service import GraphBundleService
from agentmap.services.graph.graph_checkpoint_service import GraphCheckpointService
from agentmap.services.graph.graph_execution_service import GraphExecutionService
from agentmap.services.graph.runner import (
    CheckpointManager,
    GraphInterruptHandler,
    create_bundle_context,
    create_node_registry_from_bundle,
)
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
        declaration_registry_service: DeclarationRegistryService,
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
        self.declaration_registry = declaration_registry_service

        # Initialize helper components (refactored from original methods)
        self.interrupt_handler = GraphInterruptHandler(
            logging_service=logging_service,
            interaction_handler_service=interaction_handler_service,
        )
        self.checkpoint_manager = CheckpointManager(
            logging_service=logging_service,
            graph_agent_instantiation_service=graph_agent_instantiation_service,
            graph_assembly_service=graph_assembly_service,
            graph_checkpoint_service=graph_checkpoint_service,
            execution_tracking_service=execution_tracking_service,
            interaction_handler_service=interaction_handler_service,
        )

        # Register self with instantiation service for GraphAgent injection
        # (late-bound to avoid circular dependency)
        self.graph_instantiation.set_graph_runner_service(self)

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
            # Phase 2: Create isolated scoped registry for this run (thread-safe)
            # This eliminates race conditions by giving each run its own immutable copy
            self.logger.debug(
                f"[GraphRunnerService] Phase 2: Creating scoped registry for {graph_name}"
            )
            scoped_registry = (
                self.declaration_registry.create_scoped_registry_for_bundle(bundle)
            )
            bundle.scoped_registry = scoped_registry
            self.logger.debug(
                f"[GraphRunnerService] Scoped registry created with "
                f"{len(scoped_registry.get_all_agent_types())} agents and "
                f"{len(scoped_registry.get_all_service_names())} services"
            )

            # Phase 3: Create execution tracker for this run
            self.logger.debug(
                f"[GraphRunnerService] Phase 3: Setting up execution tracking"
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

            # Phase 3.5: Pre-resolve subgraph bundles for GraphAgent nodes
            self._resolve_subgraph_bundles(bundle, initial_state)

            # Phase 4: Instantiate - create and configure agent instances
            self.logger.debug(
                f"[GraphRunnerService] Phase 4: Instantiating agents for {graph_name}"
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

            # Phase 5: Assembly - build the executable graph
            self.logger.debug(
                f"[GraphRunnerService] Phase 5: Assembling graph for {graph_name}"
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
            node_definitions = create_node_registry_from_bundle(
                bundle_with_instances, self.logger
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

            # Phase 6: Execution - run the graph
            self.logger.debug(
                f"[GraphRunnerService] Phase 6: Executing graph {graph_name}"
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
                        interrupt_details = (
                            self.interrupt_handler.handle_langgraph_interrupt(
                                state=state,
                                bundle=bundle,
                                thread_id=thread_id,
                                execution_tracker=execution_tracker,
                            )
                        )

                        interrupt_type = (
                            interrupt_details.get("type", "unknown")
                            if interrupt_details
                            else self.interrupt_handler.extract_interrupt_type_from_state(
                                state
                            )
                        )

                        self.interrupt_handler.display_resume_instructions(
                            thread_id=thread_id,
                            bundle=bundle,
                            interrupt_type=interrupt_type,
                        )

                        self.interrupt_handler.log_interrupt_status(
                            graph_name, thread_id, interrupt_type
                        )

                        return self.interrupt_handler.create_interrupt_result(
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
                interrupt_details = self.interrupt_handler.handle_langgraph_interrupt(
                    state=state,
                    bundle=bundle,
                    thread_id=thread_id,
                    execution_tracker=execution_tracker,
                )

                interrupt_type = (
                    interrupt_details.get("type", "unknown")
                    if interrupt_details
                    else self.interrupt_handler.extract_interrupt_type_from_state(state)
                )

                self.interrupt_handler.display_resume_instructions(
                    thread_id=thread_id,
                    bundle=bundle,
                    interrupt_type=interrupt_type,
                )
            else:
                interrupt_details = None
                interrupt_type = "unknown"

            self.interrupt_handler.log_interrupt_status(
                graph_name, thread_id, interrupt_type
            )

            # Return partial execution result indicating interruption
            return self.interrupt_handler.create_interrupt_result(
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
                        bundle_context=create_bundle_context(bundle),
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

    # --- Subgraph bundle pre-resolution ---

    _WORKFLOW_RE = re.compile(r"\{workflow=([^}]+)\}")
    _WORKFLOW_FIELD_RE = re.compile(r"\{workflow_field=([^}]+)\}")

    def _resolve_subgraph_bundles(
        self,
        bundle: GraphBundle,
        initial_state: Dict[str, Any],
    ) -> None:
        """
        Scan bundle nodes for graph-type agents and pre-resolve their subgraph bundles.

        Supported context syntaxes:
            {workflow=::InnerGraph}          — embedded subgraph in same CSV
            {workflow=other.csv::OtherGraph} — external CSV subgraph
            {workflow_field=state_key}       — dynamic: reads initial_state[key]

        Resolved bundles are stored in initial_state["subgraph_bundles"][node_name].
        """
        if not bundle.nodes:
            return

        subgraph_bundles: Dict[str, GraphBundle] = {}

        for node_name, node in bundle.nodes.items():
            if node.agent_type != "graph":
                continue

            # Extract the raw context string from the node's context dict
            raw_context = self._get_raw_context(node)
            if not raw_context:
                # Legacy path: no {workflow=...} syntax — fall back to prompt-based resolution
                self._resolve_legacy_subgraph(node_name, node, bundle, subgraph_bundles)
                continue

            # Try {workflow=...} syntax
            m = self._WORKFLOW_RE.search(raw_context)
            if m:
                workflow_ref = m.group(1)
                resolved = self._resolve_workflow_ref(workflow_ref, bundle)
                if resolved:
                    subgraph_bundles[node_name] = resolved
                    self.logger.debug(
                        f"[GraphRunnerService] Pre-resolved subgraph bundle for "
                        f"node '{node_name}' via {{workflow={workflow_ref}}}"
                    )
                else:
                    self.logger.warning(
                        f"[GraphRunnerService] Failed to resolve {{workflow={workflow_ref}}} "
                        f"for node '{node_name}'"
                    )
                continue

            # Try {workflow_field=...} syntax (dynamic)
            m = self._WORKFLOW_FIELD_RE.search(raw_context)
            if m:
                state_key = m.group(1)
                workflow_ref = initial_state.get(state_key)
                if not workflow_ref:
                    self.logger.warning(
                        f"[GraphRunnerService] Dynamic workflow_field '{state_key}' "
                        f"not found in initial_state for node '{node_name}'"
                    )
                    continue
                resolved = self._resolve_workflow_ref(str(workflow_ref), bundle)
                if resolved:
                    subgraph_bundles[node_name] = resolved
                    self.logger.debug(
                        f"[GraphRunnerService] Pre-resolved dynamic subgraph bundle for "
                        f"node '{node_name}' via state['{state_key}']={workflow_ref}"
                    )
                continue

            # No recognized syntax — fall back to legacy resolution
            self._resolve_legacy_subgraph(node_name, node, bundle, subgraph_bundles)

        if subgraph_bundles:
            initial_state["subgraph_bundles"] = subgraph_bundles
            self.logger.info(
                f"[GraphRunnerService] Pre-resolved {len(subgraph_bundles)} "
                f"subgraph bundle(s) for graph '{bundle.graph_name}'"
            )

    def _get_raw_context(self, node) -> Optional[str]:
        """Extract the raw context string from a node's context dict."""
        if not node.context:
            return None
        if isinstance(node.context, dict):
            return node.context.get("context")
        if isinstance(node.context, str):
            return node.context
        return None

    def _resolve_workflow_ref(
        self, workflow_ref: str, parent_bundle: GraphBundle
    ) -> Optional[GraphBundle]:
        """
        Resolve a workflow reference to a GraphBundle.

        Formats:
            ::GraphName         — embedded subgraph (same CSV)
            path.csv::GraphName — external CSV subgraph
        """
        if "::" in workflow_ref:
            csv_part, graph_name = workflow_ref.split("::", 1)
        else:
            # Bare name — treat as embedded subgraph
            csv_part = ""
            graph_name = workflow_ref

        if not csv_part:
            # Embedded subgraph — look up via parent's csv_hash
            if parent_bundle.csv_hash:
                resolved = self.graph_bundle_service.lookup_bundle(
                    parent_bundle.csv_hash, graph_name
                )
                if resolved:
                    return resolved

            # Hash lookup missed — try get_or_create_bundle if we can find the CSV
            # Fall through to external resolution with parent CSV path
            csv_path = self._get_csv_path_from_bundle(parent_bundle)
            if csv_path:
                try:
                    resolved, _ = self.graph_bundle_service.get_or_create_bundle(
                        csv_path=csv_path,
                        graph_name=graph_name,
                    )
                    return resolved
                except Exception as e:
                    self.logger.warning(
                        f"[GraphRunnerService] Failed to create bundle for "
                        f"embedded subgraph '{graph_name}': {e}"
                    )
            return None
        else:
            # External CSV subgraph
            csv_path = Path(csv_part)
            try:
                resolved, _ = self.graph_bundle_service.get_or_create_bundle(
                    csv_path=csv_path,
                    graph_name=graph_name,
                )
                return resolved
            except Exception as e:
                self.logger.warning(
                    f"[GraphRunnerService] Failed to create bundle for "
                    f"external subgraph '{csv_part}::{graph_name}': {e}"
                )
                return None

    def _resolve_legacy_subgraph(
        self,
        node_name: str,
        node,
        parent_bundle: GraphBundle,
        subgraph_bundles: Dict[str, GraphBundle],
    ) -> None:
        """
        Legacy resolution: subgraph name from prompt, CSV path from context.

        Falls back to embedded subgraph lookup via parent csv_hash.
        """
        subgraph_name = node.prompt
        if not subgraph_name:
            return

        raw_context = self._get_raw_context(node)

        # If context looks like a CSV path (not a {workflow=...} directive)
        if raw_context and not raw_context.startswith("{"):
            csv_path = Path(raw_context)
            try:
                resolved, _ = self.graph_bundle_service.get_or_create_bundle(
                    csv_path=csv_path,
                    graph_name=subgraph_name,
                )
                subgraph_bundles[node_name] = resolved
                self.logger.debug(
                    f"[GraphRunnerService] Legacy-resolved subgraph '{subgraph_name}' "
                    f"from CSV path '{raw_context}' for node '{node_name}'"
                )
                return
            except Exception as e:
                self.logger.warning(
                    f"[GraphRunnerService] Legacy resolution failed for "
                    f"'{subgraph_name}' from '{raw_context}': {e}"
                )

        # Embedded subgraph — look up via parent's csv_hash
        if parent_bundle.csv_hash:
            resolved = self.graph_bundle_service.lookup_bundle(
                parent_bundle.csv_hash, subgraph_name
            )
            if resolved:
                subgraph_bundles[node_name] = resolved
                self.logger.debug(
                    f"[GraphRunnerService] Legacy-resolved embedded subgraph "
                    f"'{subgraph_name}' via csv_hash for node '{node_name}'"
                )
                return

        # Final fallback — try get_or_create with parent CSV path
        csv_path = self._get_csv_path_from_bundle(parent_bundle)
        if csv_path:
            try:
                resolved, _ = self.graph_bundle_service.get_or_create_bundle(
                    csv_path=csv_path,
                    graph_name=subgraph_name,
                )
                subgraph_bundles[node_name] = resolved
                self.logger.debug(
                    f"[GraphRunnerService] Legacy-resolved subgraph '{subgraph_name}' "
                    f"via parent CSV for node '{node_name}'"
                )
            except Exception as e:
                self.logger.warning(
                    f"[GraphRunnerService] Could not resolve subgraph "
                    f"'{subgraph_name}' for node '{node_name}': {e}"
                )

    def _get_csv_path_from_bundle(self, bundle: GraphBundle) -> Optional[Path]:
        """Try to recover the CSV path for a bundle from the registry."""
        if not bundle.csv_hash:
            return None
        try:
            registry_service = self.graph_bundle_service.graph_registry_service
            # Access the registry cache directly to find the csv_path
            with registry_service._cache_lock:
                hash_entry = registry_service._registry_cache.get(bundle.csv_hash)
                if hash_entry:
                    # Get any entry under this hash — they all share the same CSV
                    first_entry = next(iter(hash_entry.values()), None)
                    if first_entry and "csv_path" in first_entry:
                        csv_path = Path(first_entry["csv_path"])
                        if csv_path.exists():
                            return csv_path
        except Exception:
            pass
        return None

    def resume_from_checkpoint(
        self,
        bundle: GraphBundle,
        thread_id: str,
        checkpoint_state: Dict[str, Any],
        resume_node: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Resume graph execution from a checkpoint with injected state.

        Delegates to CheckpointManager for implementation.

        Args:
            bundle: Graph bundle
            thread_id: Thread identifier
            checkpoint_state: State to resume with
            resume_node: Optional node to resume from

        Returns:
            ExecutionResult from resumed execution
        """
        return self.checkpoint_manager.resume_from_checkpoint(
            bundle=bundle,
            thread_id=thread_id,
            checkpoint_state=checkpoint_state,
            resume_node=resume_node,
        )
