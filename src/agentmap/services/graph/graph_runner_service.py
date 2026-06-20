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

import asyncio
import re
import threading
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional

from langgraph.errors import GraphInterrupt

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.exceptions.graph_exceptions import MissingServiceDeclarationError
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
        telemetry_service: Optional[Any] = None,
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
        self._telemetry_service = telemetry_service

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

    def _check_missing_services(self, bundle: GraphBundle) -> None:
        """Hard-fail if the bundle requires services with no declaration.

        Args:
            bundle: Prepared GraphBundle to validate

        Raises:
            MissingServiceDeclarationError: If ``bundle.missing_services`` is
                non-empty.
        """
        missing_services = getattr(bundle, "missing_services", None)
        if not missing_services:
            return

        services = ", ".join(sorted(missing_services))
        raise MissingServiceDeclarationError(
            f"Cannot run graph '{bundle.graph_name}': required service(s) not "
            f"declared/registered: {services} (declare it as a builtin service "
            f"or register it as a host service)."
        )

    def run(
        self,
        bundle: GraphBundle,
        initial_state: Optional[dict] = None,
        parent_graph_name: Optional[str] = None,
        parent_tracker: Optional[Any] = None,
        is_subgraph: bool = False,
        validate_agents: bool = False,
    ) -> ExecutionResult:
        """
        Run graph execution using a prepared bundle.

        Dispatches to the instrumented or uninstrumented path based on
        whether a telemetry service is available.

        Args:
            bundle: Prepared GraphBundle with all metadata
            initial_state: Optional initial state for execution
            parent_graph_name: Name of parent graph (for subgraph execution)
            parent_tracker: Parent execution tracker (for subgraph tracking)
            is_subgraph: Whether this is a subgraph execution
            validate_agents: Whether to validate agent instantiation

        Returns:
            ExecutionResult from graph execution

        Raises:
            Exception: Any errors from pipeline stages (not swallowed)
        """
        graph_name = bundle.graph_name

        # Wiring gate: refuse to run a graph whose declared agents require a
        # service that is declared in neither the builtin nor host namespace.
        # Assembly records this (bundle.missing_services); execution enforces it.
        # Scaffold/update/validate paths do not pass through run(), so they can
        # still assemble an incomplete bundle to repair it.
        self._check_missing_services(bundle)

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

        if self._telemetry_service is not None:
            return self._run_with_telemetry(
                bundle,
                initial_state,
                parent_graph_name,
                parent_tracker,
                is_subgraph,
                validate_agents,
            )
        return self._run_core(
            bundle,
            initial_state,
            parent_graph_name,
            parent_tracker,
            is_subgraph,
            validate_agents,
        )

    def _run_with_telemetry(
        self,
        bundle: GraphBundle,
        initial_state: dict,
        parent_graph_name: Optional[str],
        parent_tracker: Optional[Any],
        is_subgraph: bool,
        validate_agents: bool,
    ) -> ExecutionResult:
        """Run workflow wrapped in a telemetry span.

        Falls back to ``_run_core`` if span creation fails (Layer 1 isolation).
        Workflow exceptions (including GraphInterrupt) propagate normally --
        only telemetry infrastructure failures trigger the fallback.
        """
        assert (
            self._telemetry_service is not None
        )  # only called when telemetry is active
        from agentmap.services.telemetry.constants import (
            GRAPH_AGENT_COUNT,
            GRAPH_NAME,
            GRAPH_NODE_COUNT,
            GRAPH_PARENT_NAME,
            WORKFLOW_RUN_SPAN,
        )

        graph_name = bundle.graph_name
        node_count = len(bundle.nodes) if bundle.nodes else 0

        span_attributes: Dict[str, Any] = {
            GRAPH_NAME: graph_name,
            GRAPH_NODE_COUNT: node_count,
        }

        # Only set parent name for subgraph executions
        if parent_graph_name:
            span_attributes[GRAPH_PARENT_NAME] = parent_graph_name

        try:
            with self._telemetry_service.start_span(
                WORKFLOW_RUN_SPAN,
                attributes=span_attributes,
            ) as span:
                try:
                    result = self._run_core(
                        bundle,
                        initial_state,
                        parent_graph_name,
                        parent_tracker,
                        is_subgraph,
                        validate_agents,
                    )

                    # Set agent count after instantiation (not available before run)
                    if bundle.node_instances:
                        try:
                            self._telemetry_service.set_span_attributes(
                                span,
                                {GRAPH_AGENT_COUNT: len(bundle.node_instances)},
                            )
                        except Exception:
                            pass

                    # Set span status based on result
                    if result.success:
                        self._set_span_status_ok(span)
                    else:
                        try:
                            from opentelemetry.trace import StatusCode

                            span.set_status(
                                StatusCode.ERROR,
                                result.error or "Unknown error",
                            )
                        except Exception:
                            pass

                    return result

                except GraphInterrupt:
                    # Not an error -- intentional suspension
                    self._record_span_event_safe(span, "workflow.interrupted")
                    raise

                except ExecutionInterruptedException:
                    # Legacy interrupt -- not an error
                    self._record_span_event_safe(span, "workflow.interrupted.legacy")
                    raise

                except Exception as e:
                    self._record_span_exception_safe(span, e)
                    raise

        except (GraphInterrupt, ExecutionInterruptedException):
            # Workflow exceptions must propagate, not trigger fallback
            raise
        except Exception as telemetry_error:
            # Only catches telemetry setup errors (start_span failure)
            # Check if this is actually a workflow error that propagated
            # through the telemetry layer
            self.logger.warning(
                f"Telemetry error, executing without instrumentation: "
                f"{telemetry_error}"
            )
            return self._run_core(
                bundle,
                initial_state,
                parent_graph_name,
                parent_tracker,
                is_subgraph,
                validate_agents,
            )

    def _run_core(
        self,
        bundle: GraphBundle,
        initial_state: dict,
        parent_graph_name: Optional[str],
        parent_tracker: Optional[Any],
        is_subgraph: bool,
        validate_agents: bool,
    ) -> ExecutionResult:
        """Execute the workflow pipeline without telemetry wrapping.

        Contains the original ``run()`` body, unchanged except for phase
        event recording calls.
        """
        graph_name = bundle.graph_name or ""
        execution_tracker = None
        executable_graph = None

        try:
            # Phase 2: Create isolated scoped registry for this run (thread-safe)
            # This eliminates race conditions by giving each run its own immutable copy
            self._record_phase_event("workflow.phase.registry_creation")
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
            self._record_phase_event("workflow.phase.tracker_creation")
            self.logger.debug(
                "[GraphRunnerService] Phase 3: Setting up execution tracking"
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
            self._record_phase_event("workflow.phase.agent_instantiation")
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
            self._record_phase_event("workflow.phase.graph_assembly")
            self.logger.debug(
                f"[GraphRunnerService] Phase 5: Assembling graph for {graph_name}"
            )

            # Create Graph model from bundle for assembly
            from agentmap.models.graph import Graph

            graph = Graph(
                name=bundle_with_instances.graph_name or "",
                nodes=bundle_with_instances.nodes or {},
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
                    f"[GraphRunnerService] Assembling graph '{graph_name}' "
                    f"WITH checkpoint support"
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
                    f"[GraphRunnerService] Using checkpoint execution config "
                    f"with thread_id={thread_id}"
                )

                executable_graph = self.graph_assembly.assemble_with_checkpoint(
                    graph=graph,
                    agent_instances=bundle_with_instances.node_instances,
                    node_definitions=node_definitions,
                    checkpointer=self.graph_checkpoint,
                )
            else:
                self.logger.debug(
                    f"[GraphRunnerService] Assembling graph '{graph_name}' "
                    f"WITHOUT checkpoint support"
                )
                executable_graph = self.graph_assembly.assemble_graph(
                    graph=graph,
                    agent_instances=bundle_with_instances.node_instances,
                    orchestrator_node_registry=node_definitions,
                )

            self.logger.debug("[GraphRunnerService] Graph assembly completed")

            # Phase 6: Execution - run the graph
            self._record_phase_event("workflow.phase.execution")
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

            # Phase 7: Finalization - execution complete, inspect results
            self._record_phase_event("workflow.phase.finalization")

            # Check for suspended state even when invocation returns normally
            if requires_checkpoint and execution_config:
                thread_id = getattr(execution_tracker, "thread_id", None)
                if not thread_id:
                    self.logger.warning(
                        "Missing thread_id after checkpoint execution; "
                        "cannot inspect state"
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
                    f"[GraphRunnerService] Linked subgraph tracker to parent "
                    f"for: {graph_name}"
                )

            # Log final status with subgraph context
            if result.success:
                if is_subgraph and parent_graph_name:
                    self.logger.info(
                        f"Subgraph pipeline completed successfully for: {graph_name} "
                        f"(parent: {parent_graph_name}, "
                        f"duration: {result.total_duration:.2f}s)"
                    )
                else:
                    self.logger.info(
                        f"Graph pipeline completed successfully for: {graph_name} "
                        f"(duration: {result.total_duration:.2f}s)"
                    )
            else:
                if is_subgraph and parent_graph_name:
                    self.logger.error(
                        f"Subgraph pipeline failed for: {graph_name} "
                        f"(parent: {parent_graph_name}) - {result.error}"
                    )
                else:
                    self.logger.error(
                        f"Graph pipeline failed for: {graph_name} - {result.error}"
                    )

            return result

        except GraphInterrupt as e:
            # Handle LangGraph interrupt (from interrupt() call in agents)
            self.logger.info("Graph execution interrupted (LangGraph pattern)")

            # Get thread_id from execution tracker
            thread_id = execution_tracker.thread_id if execution_tracker else None

            if not thread_id:
                self.logger.error("Cannot handle interrupt: no thread_id available")
                raise RuntimeError("Cannot handle interrupt: no thread_id") from e

            # Get graph state to extract interrupt metadata
            if executable_graph is None:
                raise RuntimeError(
                    "Cannot handle interrupt: graph not assembled"
                ) from e
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
                f"Graph execution interrupted (legacy pattern) "
                f"in thread: {e.thread_id}"
            )

            # If interaction handler is available, process the interruption.
            # Do NOT catch exceptions here — if metadata storage fails the caller
            # must know; swallowing the error causes resume_workflow to raise a
            # misleading "Thread not found in storage" instead of the real cause.
            if self.interaction_handler:
                self.interaction_handler.handle_execution_interruption(
                    exception=e,
                    bundle=bundle,
                    bundle_context=create_bundle_context(bundle),
                )
                self.logger.info(
                    f"Interaction handling completed for thread: "
                    f"{e.thread_id}. "
                    f"Execution paused pending user response."
                )
            else:
                self.logger.warning(
                    f"No interaction handler configured. Interaction "
                    f"for thread {e.thread_id} not handled."
                )

            # Re-raise the exception for higher-level handling
            raise

        except Exception as e:
            # Log with subgraph context if applicable
            if is_subgraph and parent_graph_name:
                self.logger.error(
                    f"Subgraph pipeline failed for '{graph_name}' "
                    f"(parent: {parent_graph_name}): {str(e)}"
                )
            else:
                self.logger.error(f"Pipeline failed for graph '{graph_name}': {str(e)}")

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

    # ------------------------------------------------------------------
    # Telemetry helpers (error-isolated, silent no-op when disabled)
    # ------------------------------------------------------------------

    def _set_span_status_ok(self, span: Any) -> None:
        """Set span status to OK. No-op if span is None."""
        if span is not None:
            try:
                from opentelemetry.trace import StatusCode

                span.set_status(StatusCode.OK)
            except Exception:
                pass

    def _record_span_event_safe(
        self,
        span: Any,
        event_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a span event safely. No-op on failure."""
        if span is not None and self._telemetry_service is not None:
            try:
                self._telemetry_service.add_span_event(span, event_name, attributes)
            except Exception:
                pass

    def _record_span_exception_safe(self, span: Any, exception: Exception) -> None:
        """Record exception on span safely. No-op on failure."""
        if span is not None and self._telemetry_service is not None:
            try:
                self._telemetry_service.record_exception(span, exception)
            except Exception:
                pass

    def _record_phase_event(
        self,
        event_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a phase event on the current span. No-op if telemetry unavailable."""
        if self._telemetry_service is None:
            return
        try:
            import opentelemetry.trace as trace_api

            current_span = trace_api.get_current_span()
            if current_span and current_span.is_recording():
                self._telemetry_service.add_span_event(
                    current_span, event_name, attributes
                )
        except Exception:
            pass  # Telemetry failures silently ignored

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
            return self.graph_bundle_service.graph_registry_service.get_csv_path(
                bundle.csv_hash
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Async runner path (REQ-F-004, REQ-F-006, REQ-F-007, REQ-F-008)
    # ------------------------------------------------------------------

    async def run_async(
        self,
        bundle: GraphBundle,
        initial_state: Optional[dict] = None,
        parent_graph_name: Optional[str] = None,
        parent_tracker: Optional[Any] = None,
        is_subgraph: bool = False,
        validate_agents: bool = False,
    ) -> ExecutionResult:
        """Run graph execution asynchronously using a prepared bundle.

        Async sibling of ``run()``.  Preserves the same orchestration
        sequence — bundle normalization, scoped registry, tracker creation,
        subgraph bundle resolution, agent instantiation, checkpoint gating,
        async graph assembly, async graph execution, interrupt detection, and
        subgraph tracker linkage — while routing through async assembly and
        async execution primitives (REQ-F-004, REQ-F-006, REQ-F-008).

        Args:
            bundle: Prepared GraphBundle with all metadata.
            initial_state: Optional initial state for execution.
            parent_graph_name: Name of parent graph (for subgraph execution).
            parent_tracker: Parent execution tracker (for subgraph tracking).
            is_subgraph: Whether this is a subgraph execution.
            validate_agents: Whether to validate agent instantiation.

        Returns:
            ExecutionResult from graph execution.

        Raises:
            asyncio.CancelledError: Propagated without swallowing (REQ-F-009).
        """
        graph_name = bundle.graph_name
        self._check_missing_services(bundle)

        if is_subgraph and parent_graph_name:
            self.logger.info(
                f"⭐ Starting async subgraph pipeline for: {graph_name} "
                f"(parent: {parent_graph_name})"
            )
        else:
            self.logger.info(f"⭐ Starting async graph pipeline for: {graph_name}")

        if initial_state is None:
            initial_state = {}

        if self._telemetry_service is not None:
            return await self._run_async_with_telemetry(
                bundle,
                initial_state,
                parent_graph_name,
                parent_tracker,
                is_subgraph,
                validate_agents,
            )
        return await self._run_core_async(
            bundle,
            initial_state,
            parent_graph_name,
            parent_tracker,
            is_subgraph,
            validate_agents,
        )

    async def _run_async_with_telemetry(
        self,
        bundle: GraphBundle,
        initial_state: dict,
        parent_graph_name: Optional[str],
        parent_tracker: Optional[Any],
        is_subgraph: bool,
        validate_agents: bool,
    ) -> ExecutionResult:
        """Run async workflow wrapped in a telemetry span.

        Falls back to ``_run_core_async`` if span creation fails (same
        Layer 1 isolation as the sync ``_run_with_telemetry``).  Workflow
        exceptions (including GraphInterrupt and CancelledError) propagate
        normally — only telemetry infrastructure failures trigger the
        fallback (REQ-NF-002).
        """
        assert (
            self._telemetry_service is not None
        )  # only called when telemetry is active
        from agentmap.services.telemetry.constants import (
            GRAPH_AGENT_COUNT,
            GRAPH_NAME,
            GRAPH_NODE_COUNT,
            GRAPH_PARENT_NAME,
            WORKFLOW_RUN_SPAN,
        )

        graph_name = bundle.graph_name
        node_count = len(bundle.nodes) if bundle.nodes else 0

        span_attributes: Dict[str, Any] = {
            GRAPH_NAME: graph_name,
            GRAPH_NODE_COUNT: node_count,
        }
        if parent_graph_name:
            span_attributes[GRAPH_PARENT_NAME] = parent_graph_name

        try:
            with self._telemetry_service.start_span(
                WORKFLOW_RUN_SPAN,
                attributes=span_attributes,
            ) as span:
                try:
                    result = await self._run_core_async(
                        bundle,
                        initial_state,
                        parent_graph_name,
                        parent_tracker,
                        is_subgraph,
                        validate_agents,
                    )

                    # Set agent count after instantiation (not available before)
                    if bundle.node_instances:
                        try:
                            self._telemetry_service.set_span_attributes(
                                span,
                                {GRAPH_AGENT_COUNT: len(bundle.node_instances)},
                            )
                        except Exception:
                            pass

                    # Set span status based on result.
                    # Interrupt results (GraphInterrupt handled by _run_core_async)
                    # must not set ERROR status — they are workflow suspensions, not
                    # failures (AC-011 / telemetry parity matrix interrupt row).
                    try:
                        is_interrupt = isinstance(
                            result.final_state, dict
                        ) and result.final_state.get("__interrupted", False)
                    except Exception:
                        is_interrupt = False
                    if result.success:
                        self._set_span_status_ok(span)
                    elif not is_interrupt:
                        try:
                            from opentelemetry.trace import StatusCode

                            span.set_status(
                                StatusCode.ERROR,
                                result.error or "Unknown error",
                            )
                        except Exception:
                            pass

                    return result

                except GraphInterrupt:
                    # _run_core_async already emitted workflow.interrupted via
                    # _record_phase_event, but emit here too in case GraphInterrupt
                    # escapes _run_core_async (e.g. when no thread_id is available
                    # and RuntimeError is suppressed).
                    self._record_span_event_safe(span, "workflow.interrupted")
                    raise

                except ExecutionInterruptedException:
                    # _run_core_async already emitted workflow.interrupted.legacy;
                    # record here too for defence-in-depth at the telemetry seam.
                    self._record_span_event_safe(span, "workflow.interrupted.legacy")
                    raise

                except asyncio.CancelledError:
                    # CancelledError must not be swallowed by telemetry layer
                    # (REQ-F-009); span closes without OK status.
                    raise

                except Exception as e:
                    self._record_span_exception_safe(span, e)
                    raise

        except (GraphInterrupt, ExecutionInterruptedException, asyncio.CancelledError):
            raise
        except Exception as telemetry_error:
            self.logger.warning(
                f"Telemetry error, executing without instrumentation: "
                f"{telemetry_error}"
            )
            return await self._run_core_async(
                bundle,
                initial_state,
                parent_graph_name,
                parent_tracker,
                is_subgraph,
                validate_agents,
            )

    async def _assemble_for_async_run(
        self,
        bundle: GraphBundle,
        initial_state: dict,
        validate_agents: bool,
    ) -> tuple:
        """Shared assembly helper for async run paths (D-7 extract).

        Covers phases 2–5 of the async pipeline — scoped registry creation,
        execution tracker creation, subgraph bundle resolution, agent
        instantiation (+ optional validation), async graph assembly, and
        checkpoint config derivation — so that both ``_run_core_async`` and
        the upcoming ``run_stream_async`` share identical assembly behaviour
        with no code duplication.

        This is a pure refactor of what ``_run_core_async`` previously did
        inline; no behavioral change to the non-streaming path (REQ-NF-001,
        AC-10, T-E06-F04-003).

        Args:
            bundle: Prepared GraphBundle with all metadata.
            initial_state: Initial state dict for the run (used to pre-resolve
                subgraph bundles).
            validate_agents: If True, validate agent instantiation and raise
                RuntimeError on failure.

        Returns:
            A 4-tuple ``(executable_graph, execution_tracker,
            execution_config, requires_checkpoint)`` where:

            - ``executable_graph``: the compiled LangGraph graph object ready
              for ``ainvoke`` / ``astream``.
            - ``execution_tracker``: the execution tracker for this run.
            - ``execution_config``: ``{"configurable": {"thread_id": ...}}``
              when checkpoint support is active, otherwise ``None``.
            - ``requires_checkpoint``: ``True`` when the bundle requires
              checkpoint support, ``False`` otherwise.

        Raises:
            RuntimeError: If agent instantiation validation fails, if
                checkpoint mode is required but no thread_id is available,
                or if no agent instances are found in the bundle.
        """
        graph_name = bundle.graph_name or ""

        # Phase 2: Create isolated scoped registry for this run.
        # NOTE: scoped_registry is stored in a run-local variable only.
        # Writing it back to the shared ``bundle`` object is concurrency-
        # unsafe: two concurrent run_async calls on the same bundle would
        # overwrite each other's registry (NB-B / AC-009 fix).
        self._record_phase_event("workflow.phase.registry_creation")
        self.logger.debug(
            f"[GraphRunnerService] Async Phase 2: Creating scoped registry "
            f"for {graph_name}"
        )
        scoped_registry = self.declaration_registry.create_scoped_registry_for_bundle(
            bundle
        )
        # Do NOT write back to bundle.scoped_registry (concurrency safety).
        self.logger.debug(
            f"[GraphRunnerService] Scoped registry created with "
            f"{len(scoped_registry.get_all_agent_types())} agents and "
            f"{len(scoped_registry.get_all_service_names())} services"
        )

        # Phase 3: Create execution tracker
        self._record_phase_event("workflow.phase.tracker_creation")
        self.logger.debug(
            "[GraphRunnerService] Async Phase 3: Setting up execution tracking"
        )
        execution_tracker = self.execution_tracking.create_tracker()

        # Phase 3.5: Pre-resolve subgraph bundles
        self._resolve_subgraph_bundles(bundle, initial_state)

        # Phase 4: Instantiate agents
        self._record_phase_event("workflow.phase.agent_instantiation")
        self.logger.debug(
            f"[GraphRunnerService] Async Phase 4: Instantiating agents "
            f"for {graph_name}"
        )
        bundle_with_instances = self.graph_instantiation.instantiate_agents(
            bundle, execution_tracker
        )

        if validate_agents:
            validation = self.graph_instantiation.validate_instantiation(
                bundle_with_instances
            )
            if not validation["valid"]:
                raise RuntimeError(
                    f"Agent instantiation validation failed: {validation}"
                )

        # Phase 5: Assembly — async path
        self._record_phase_event("workflow.phase.graph_assembly")
        self.logger.debug(
            f"[GraphRunnerService] Async Phase 5: Assembling graph " f"for {graph_name}"
        )

        from agentmap.models.graph import Graph

        graph = Graph(
            name=bundle_with_instances.graph_name or "",
            nodes=bundle_with_instances.nodes or {},
            entry_point=bundle_with_instances.entry_point,
        )

        if not bundle_with_instances.node_instances:
            raise RuntimeError("No agent instances found in bundle.node_registry")

        node_definitions = create_node_registry_from_bundle(
            bundle_with_instances, self.logger
        )

        requires_checkpoint = self.graph_bundle_service.requires_checkpoint_support(
            bundle
        )

        execution_config = None

        if requires_checkpoint:
            thread_id = getattr(execution_tracker, "thread_id", None)
            if not thread_id:
                raise RuntimeError(
                    "Checkpoint execution requires execution tracker with thread_id"
                )

            execution_config = {"configurable": {"thread_id": thread_id}}
            self.logger.debug(
                f"[GraphRunnerService] Async assembling graph '{graph_name}' "
                f"WITH checkpoint support (thread_id={thread_id})"
            )
            executable_graph = self.graph_assembly.assemble_with_checkpoint_async(
                graph=graph,
                agent_instances=bundle_with_instances.node_instances,
                node_definitions=node_definitions,
                checkpointer=self.graph_checkpoint,
            )
        else:
            self.logger.debug(
                f"[GraphRunnerService] Async assembling graph '{graph_name}' "
                f"WITHOUT checkpoint support"
            )
            executable_graph = self.graph_assembly.assemble_graph_async(
                graph=graph,
                agent_instances=bundle_with_instances.node_instances,
                orchestrator_node_registry=node_definitions,
            )

        self.logger.debug("[GraphRunnerService] Async graph assembly completed")

        return (
            executable_graph,
            execution_tracker,
            execution_config,
            requires_checkpoint,
        )

    async def _run_core_async(
        self,
        bundle: GraphBundle,
        initial_state: dict,
        parent_graph_name: Optional[str],
        parent_tracker: Optional[Any],
        is_subgraph: bool,
        validate_agents: bool,
    ) -> ExecutionResult:
        """Execute the async workflow pipeline without telemetry wrapping.

        Mirrors ``_run_core`` phase-by-phase, substituting async assembly
        and async execution calls (REQ-F-004, REQ-NF-002).

        Phases 2–5 (scoped registry → tracker → subgraph bundles → agent
        instantiation → async assembly → checkpoint config) are delegated to
        ``_assemble_for_async_run`` so that the streaming sibling method
        can share identical assembly behaviour (D-7 extract, T-E06-F04-003).
        """
        graph_name = bundle.graph_name or ""
        execution_tracker = None
        executable_graph = None

        try:
            # Phases 2–5: shared assembly (D-7 extract)
            (
                executable_graph,
                execution_tracker,
                execution_config,
                requires_checkpoint,
            ) = await self._assemble_for_async_run(
                bundle=bundle,
                initial_state=initial_state,
                validate_agents=validate_agents,
            )

            # Phase 6: Execution — async
            self._record_phase_event("workflow.phase.execution")
            self.logger.debug(
                f"[GraphRunnerService] Async Phase 6: Executing graph {graph_name}"
            )
            result = await self.graph_execution.execute_compiled_graph_async(
                executable_graph=executable_graph,
                graph_name=graph_name,
                initial_state=initial_state,
                execution_tracker=execution_tracker,
                config=execution_config,
            )

            # Phase 7: Finalization
            self._record_phase_event("workflow.phase.finalization")

            # Check for suspended state when checkpoint enabled
            if requires_checkpoint and execution_config:
                thread_id = getattr(execution_tracker, "thread_id", None)
                if not thread_id:
                    self.logger.warning(
                        "Missing thread_id after async checkpoint execution; "
                        "cannot inspect state"
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

            # Link subgraph tracker to parent
            if is_subgraph and parent_tracker:
                self.execution_tracking.record_subgraph_execution(
                    tracker=parent_tracker,
                    subgraph_name=graph_name,
                    subgraph_tracker=execution_tracker,
                )
                self.logger.debug(
                    f"[GraphRunnerService] Linked async subgraph tracker to parent "
                    f"for: {graph_name}"
                )

            if result.success:
                if is_subgraph and parent_graph_name:
                    self.logger.info(
                        f"Async subgraph pipeline completed successfully for: "
                        f"{graph_name} (parent: {parent_graph_name}, "
                        f"duration: {result.total_duration:.2f}s)"
                    )
                else:
                    self.logger.info(
                        f"Async graph pipeline completed successfully for: "
                        f"{graph_name} (duration: {result.total_duration:.2f}s)"
                    )
            else:
                if is_subgraph and parent_graph_name:
                    self.logger.error(
                        f"Async subgraph pipeline failed for: {graph_name} "
                        f"(parent: {parent_graph_name}) - {result.error}"
                    )
                else:
                    self.logger.error(
                        f"Async graph pipeline failed for: {graph_name} "
                        f"- {result.error}"
                    )

            return result

        except asyncio.CancelledError:
            # Propagate cancellation — do not swallow (REQ-F-009)
            self.logger.info(
                f"[GraphRunnerService] Async run cancelled for graph '{graph_name}'"
            )
            raise

        except GraphInterrupt as e:
            self.logger.info("Async graph execution interrupted (LangGraph pattern)")
            # Emit telemetry interrupt event while the span context is still active
            # (AC-011 / telemetry parity matrix: interrupt row).  _record_phase_event
            # writes to the current OTel span, which is still open here because
            # _run_async_with_telemetry's `with start_span(...)` block is an ancestor
            # frame on the call stack.
            self._record_phase_event("workflow.interrupted")

            thread_id = execution_tracker.thread_id if execution_tracker else None
            if not thread_id:
                self.logger.error(
                    "Cannot handle async interrupt: no thread_id available"
                )
                raise RuntimeError("Cannot handle interrupt: no thread_id") from e
            if executable_graph is None:
                raise RuntimeError(
                    "Cannot handle interrupt: graph not assembled"
                ) from e

            config = {"configurable": {"thread_id": thread_id}}
            state = executable_graph.get_state(config)

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

            return self.interrupt_handler.create_interrupt_result(
                graph_name=graph_name,
                thread_id=thread_id,
                state=state,
                interrupt_type=interrupt_type,
                interrupt_info=interrupt_details,
            )

        except ExecutionInterruptedException as e:
            self.logger.info(
                f"Async graph execution interrupted (legacy pattern) "
                f"in thread: {e.thread_id}"
            )
            # Emit telemetry legacy-interrupt event before re-raising (AC-011).
            self._record_phase_event("workflow.interrupted.legacy")
            if self.interaction_handler:
                self.interaction_handler.handle_execution_interruption(
                    exception=e,
                    bundle=bundle,
                    bundle_context=create_bundle_context(bundle),
                )
            else:
                self.logger.warning(
                    f"No interaction handler configured. Interaction "
                    f"for thread {e.thread_id} not handled."
                )
            raise

        except Exception as e:
            if is_subgraph and parent_graph_name:
                self.logger.error(
                    f"Async subgraph pipeline failed for '{graph_name}' "
                    f"(parent: {parent_graph_name}): {str(e)}"
                )
            else:
                self.logger.error(
                    f"Async pipeline failed for graph '{graph_name}': {str(e)}"
                )

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

    async def run_stream_async(
        self,
        bundle: GraphBundle,
        initial_state: Optional[dict] = None,
        *,
        validate_agents: bool = False,
        profile: Optional[str] = None,
        graph_name: Optional[str] = None,
    ) -> AsyncGenerator[Any, None]:
        """Stream graph execution as ordered WorkflowProgressEvents (E06-F04, T-005).

        Streaming sibling of ``run_async``.  Reuses ``_assemble_for_async_run``
        (D-7) for identical assembly, then drives
        ``GraphExecutionService.stream_compiled_graph_async`` instead of
        ``execute_compiled_graph_async`` (D-2, D-3).

        Args:
            bundle: Prepared GraphBundle for the run.
            initial_state: Initial state dict (defaults to ``{}``).
            validate_agents: If True, validate agent instantiation during assembly.
            profile: Optional profile/environment name threaded into the terminal
                event's ``metadata`` so the streaming terminal result matches the
                ``run_workflow_async`` return for the same input (AC-3, B-5).
            graph_name: Optional caller-supplied identifier for the run.  Defaults
                to ``bundle.graph_name``.  Threaded into the terminal event's
                ``metadata.graph_name`` so a ``workflow::graph``-form caller name
                matches the non-streaming ``run_workflow_async`` return, which
                echoes the raw caller identifier rather than the resolved bundle
                name (NB-1).

        Yields:
            ``WorkflowProgressEvent`` — one per completed node with
            ``event_type="node_progress"`` and ``is_terminal=False``, followed
            by exactly one terminal event (``is_terminal=True``) with
            ``event_type`` one of ``"completed"``, ``"failed"``, or
            ``"suspended"``.

        Terminal result dict shape is identical to ``run_workflow_async``
        for the same input (SC-3, C1, D-4).

        Suspension (REQ-F-007 / AC-8b) is detected on all three paths the
        non-streaming run uses, and each yields a *resumable* ``suspended``
        terminal carrying a real ``thread_id`` and populated ``interrupt_info``:
          1. ``GraphInterrupt`` raised mid-stream (LangGraph pattern).
          2. ``ExecutionInterruptedException`` raised mid-stream (legacy
             human-interaction pattern).
          3. A checkpoint interrupt that lets ``.astream()`` complete normally,
             detected post-stream via ``get_state()`` when checkpointing is active.

        Raises:
            asyncio.CancelledError: Propagated without swallowing (REQ-F-006).
            GeneratorExit: Not swallowed — propagates to cancel the upstream
                ``.astream()`` loop (REQ-F-006).
        """
        from agentmap.models.execution import WorkflowProgressEvent
        from agentmap.services.graph.graph_execution_service import (
            _TerminalStreamResult,
        )

        # NB-1: the raw caller identifier (``graph_name`` arg) shapes ONLY the
        # terminal event's ``metadata.graph_name`` — matching the non-streaming
        # facade, which echoes the caller name (workflow_ops.py).  The resolved
        # ``bundle.graph_name`` drives execution, telemetry, logging, and the
        # ``execution_summary`` (via ``create_interrupt_result``) — matching the
        # non-streaming runner (``_run_core_async`` :1346), so a
        # ``workflow::graph`` caller name matches non-streaming on BOTH fields.
        metadata_graph_name = graph_name or bundle.graph_name or ""
        graph_name = bundle.graph_name or ""
        self._check_missing_services(bundle)
        self.logger.info(f"⭐ Starting async streaming pipeline for: {graph_name}")

        if initial_state is None:
            initial_state = {}

        sequence = 0
        # Pre-declare so the except handlers can reference these even if assembly
        # has not yet completed (avoids UnboundLocalError on an early raise — e.g.
        # the GeneratorExit/CancelledError handlers, and the except-GraphInterrupt
        # handler which reads executable_graph via _build_graph_interrupt_result).
        # executable_graph=None also makes the "graph not assembled" guard in
        # _build_graph_interrupt_result provably reachable.
        execution_tracker: Any = None
        executable_graph: Any = None
        execution_config: Optional[Dict[str, Any]] = None
        requires_checkpoint: bool = False

        # Telemetry: open span explicitly before the iteration so it wraps
        # the full stream lifetime.  Use explicit open/close (not a `with` block)
        # to avoid closing the span before the stream drains (spec §3.6 telemetry
        # note; AC-11).
        span = None
        if self._telemetry_service is not None:
            try:
                from agentmap.services.telemetry.constants import (
                    GRAPH_NAME,
                    WORKFLOW_RUN_SPAN,
                )

                span = self._telemetry_service.start_span(
                    WORKFLOW_RUN_SPAN,
                    attributes={GRAPH_NAME: graph_name},
                )
                # Enter the context manager manually
                span.__enter__()
            except Exception:
                span = None

        try:
            # Phases 2–5: shared assembly (D-7, D-3)
            (
                executable_graph,
                execution_tracker,
                execution_config,
                requires_checkpoint,
            ) = await self._assemble_for_async_run(
                bundle=bundle,
                initial_state=initial_state,
                validate_agents=validate_agents,
            )

            # Phase 6: drive streaming execution
            self._record_phase_event("workflow.phase.execution")
            self.logger.debug(
                f"[GraphRunnerService] Streaming Phase 6: Executing graph {graph_name}"
            )

            async for item in self.graph_execution.stream_compiled_graph_async(
                executable_graph=executable_graph,
                graph_name=graph_name,
                initial_state=initial_state,
                execution_tracker=execution_tracker,
                config=execution_config,
            ):
                if isinstance(item, _TerminalStreamResult):
                    # D-8: terminal ExecutionResult — build and yield terminal event
                    result = item.result

                    # B-3 (REQ-F-007 / AC-8b): post-stream suspension detection.
                    # A checkpoint interrupt can let .astream() complete normally
                    # (no GraphInterrupt raised); the suspension is only visible in
                    # the checkpoint state.  Mirror the non-streaming post-execution
                    # check (_run_core_async :1380): when checkpointing is active
                    # and get_state() shows pending tasks, emit a resumable
                    # 'suspended' terminal instead of 'completed'/'failed'.  The
                    # gate is unconditional of result.success (Blocker #1): a
                    # checkpoint interrupt whose success policy evaluates False
                    # must still stream 'suspended', not 'failed' — exactly as the
                    # non-streaming reference at :1380 (also success-unconditional).
                    if requires_checkpoint and execution_config:
                        suspended = self._detect_post_stream_suspension(
                            bundle=bundle,
                            graph_name=graph_name,
                            metadata_graph_name=metadata_graph_name,
                            executable_graph=executable_graph,
                            execution_config=execution_config,
                            execution_tracker=execution_tracker,
                            profile=profile,
                        )
                        if suspended is not None:
                            # NB: the stream loop completed normally, so
                            # stream_compiled_graph_async already finalized the
                            # tracker (graph_execution_service.py:522).  Do NOT
                            # re-finalize here — that matches the non-streaming
                            # post-stream suspension path, which also does not
                            # re-finalize (avoids the N-1 double-finalize).
                            yield WorkflowProgressEvent(
                                event_type="suspended",
                                sequence=sequence,
                                is_terminal=True,
                                result=suspended,
                            )
                            return

                    result_dict = self._shape_streaming_result(
                        result, metadata_graph_name, profile=profile
                    )
                    event_type = "completed" if result.success else "failed"
                    yield WorkflowProgressEvent(
                        event_type=event_type,
                        sequence=sequence,
                        is_terminal=True,
                        result=result_dict,
                        error=result.error if not result.success else None,
                    )
                    return
                else:
                    # (node_name, state_delta) tuple from stream_compiled_graph_async
                    node_name, state_delta = item
                    yield WorkflowProgressEvent(
                        event_type="node_progress",
                        sequence=sequence,
                        is_terminal=False,
                        node_name=node_name,
                        state_delta=state_delta,
                    )
                    sequence += 1

        except GraphInterrupt as e:
            # Suspension (LangGraph pattern): build a *resumable* suspended terminal
            # carrying the real thread_id + interrupt_info, then finalize the tracker
            # (AC-11) and yield it (REQ-F-007, AC-8b, B-2).  Mirrors the non-streaming
            # except-GraphInterrupt block (_run_core_async :1471-1526).
            self.logger.info(
                f"[GraphRunnerService] Streaming graph interrupted: {graph_name}"
            )
            self._record_phase_event("workflow.interrupted")
            result_dict = self._build_graph_interrupt_result(
                error=e,
                bundle=bundle,
                graph_name=graph_name,
                metadata_graph_name=metadata_graph_name,
                executable_graph=executable_graph,
                execution_tracker=execution_tracker,
                profile=profile,
            )
            self._finalize_tracker_safe(execution_tracker)
            yield WorkflowProgressEvent(
                event_type="suspended",
                sequence=sequence,
                is_terminal=True,
                result=result_dict,
            )
            return

        except ExecutionInterruptedException as e:
            # Suspension (legacy human-interaction pattern, B-1): an Exception
            # subclass that MUST map to 'suspended', not 'failed'.  Persist the
            # interaction for resume (parity with the non-streaming runner
            # :1528-1546), finalize the tracker (AC-11), then yield a resumable
            # suspended terminal carrying thread_id + interaction_request (parity
            # with the run_workflow_async facade handler).
            self.logger.info(
                f"[GraphRunnerService] Streaming graph interrupted (legacy "
                f"pattern) in thread: {e.thread_id}"
            )
            self._record_phase_event("workflow.interrupted.legacy")
            if self.interaction_handler:
                self.interaction_handler.handle_execution_interruption(
                    exception=e,
                    bundle=bundle,
                    bundle_context=create_bundle_context(bundle),
                )
            else:
                self.logger.warning(
                    f"No interaction handler configured. Interaction "
                    f"for thread {e.thread_id} not handled."
                )
            self._finalize_tracker_safe(execution_tracker)
            yield WorkflowProgressEvent(
                event_type="suspended",
                sequence=sequence,
                is_terminal=True,
                result={
                    "success": False,
                    "interrupted": True,
                    "thread_id": e.thread_id,
                    "interaction_request": e.interaction_request,
                    "message": (
                        f"Execution interrupted for human interaction in "
                        f"thread: {e.thread_id}"
                    ),
                    "metadata": {
                        "graph_name": metadata_graph_name,
                        "profile": profile,
                        "checkpoint_available": True,
                    },
                },
            )
            return

        except GeneratorExit:
            # Consumer called aclose() — finalize tracker to avoid leaks (AC-6, AC-11),
            # then propagate (REQ-F-006: GeneratorExit must not be swallowed).
            self._finalize_tracker_safe(execution_tracker)
            raise

        except asyncio.CancelledError:
            # Task cancellation — finalize tracker, then propagate (REQ-F-006).
            self._finalize_tracker_safe(execution_tracker)
            raise

        except Exception as exc:
            # Mid-run failure: finalize tracker (AC-11), then yield a failed terminal
            # event (REQ-F-005, AC-5).  No exception propagates out of the generator.
            self.logger.error(
                f"[GraphRunnerService] Streaming graph failed: {graph_name} — {exc}"
            )
            self._finalize_tracker_safe(execution_tracker)
            error_str = str(exc)
            yield WorkflowProgressEvent(
                event_type="failed",
                sequence=sequence,
                is_terminal=True,
                result={
                    "success": False,
                    "outputs": initial_state,
                    "execution_id": None,
                    "execution_summary": None,
                    "metadata": {"graph_name": metadata_graph_name, "profile": profile},
                    "error": error_str,
                },
                error=error_str,
            )

        finally:
            # Close the telemetry span on every terminal path including GeneratorExit.
            if span is not None:
                try:
                    span.__exit__(None, None, None)
                except Exception:
                    pass

    def _finalize_tracker_safe(self, execution_tracker: Any) -> None:
        """Finalize the execution tracker without raising (best-effort).

        Called from the GeneratorExit / CancelledError handlers of
        ``run_stream_async`` to ensure the tracker is not leaked when the
        consumer cancels the stream (AC-6, AC-11).
        """
        if execution_tracker is None:
            return
        try:
            self.execution_tracking.complete_execution(execution_tracker)
        except Exception as finalize_err:
            self.logger.warning(
                f"[GraphRunnerService] Tracker finalization failed on "
                f"stream cancellation: {finalize_err}"
            )

    def _detect_post_stream_suspension(
        self,
        bundle: GraphBundle,
        graph_name: str,
        metadata_graph_name: str,
        executable_graph: Any,
        execution_config: Dict[str, Any],
        execution_tracker: Any,
        profile: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Detect a checkpoint suspension after a normal stream completion (B-3).

        Mirrors the non-streaming post-execution suspension check
        (``_run_core_async`` :1380-1424): when checkpointing is active, a
        checkpoint interrupt can let ``.astream()`` finish without raising
        ``GraphInterrupt`` — the only evidence is a pending task in the
        checkpoint state.  Returns a resumable ``suspended`` result dict when a
        pending interrupt is found, otherwise ``None`` (the run truly completed).

        Args:
            graph_name: Resolved bundle name — drives ``create_interrupt_result``
                (hence ``execution_summary.graph_name``), matching non-streaming.
            metadata_graph_name: Raw caller identifier — shapes only the terminal
                dict's ``metadata.graph_name`` (NB-1).

        Returns:
            A suspended result dict (parity with ``run_workflow_async``), or
            ``None`` when there is no pending interrupt.
        """
        thread_id = getattr(execution_tracker, "thread_id", None)
        if not thread_id:
            self.logger.warning(
                "Missing thread_id after async streaming checkpoint execution; "
                "cannot inspect state"
            )
            return None

        state = executable_graph.get_state(execution_config)
        if not getattr(state, "tasks", None):
            return None

        result = self._create_streaming_interrupt_result(
            bundle=bundle,
            graph_name=graph_name,
            thread_id=thread_id,
            state=state,
            execution_tracker=execution_tracker,
        )
        return self._shape_streaming_result(
            result, metadata_graph_name, profile=profile
        )

    def _build_graph_interrupt_result(
        self,
        error: GraphInterrupt,
        bundle: GraphBundle,
        graph_name: str,
        metadata_graph_name: str,
        executable_graph: Any,
        execution_tracker: Any,
        profile: Optional[str],
    ) -> Dict[str, Any]:
        """Build a resumable suspended result for a mid-stream GraphInterrupt (B-2).

        Mirrors the non-streaming ``except GraphInterrupt`` block
        (``_run_core_async`` :1471-1526): pull the real ``thread_id`` from the
        tracker, read ``get_state``, and populate the interrupt payload via the
        interrupt handler so the streamed suspension is resumable.

        Args:
            graph_name: Resolved bundle name — drives ``create_interrupt_result``
                (hence ``execution_summary.graph_name``), matching non-streaming.
            metadata_graph_name: Raw caller identifier — shapes only the terminal
                dict's ``metadata.graph_name`` (NB-1).
        """
        thread_id = execution_tracker.thread_id if execution_tracker else None
        if not thread_id:
            self.logger.error(
                "Cannot handle streaming interrupt: no thread_id available"
            )
            raise RuntimeError("Cannot handle interrupt: no thread_id") from error
        if executable_graph is None:
            raise RuntimeError(
                "Cannot handle interrupt: graph not assembled"
            ) from error

        config = {"configurable": {"thread_id": thread_id}}
        state = executable_graph.get_state(config)
        result = self._create_streaming_interrupt_result(
            bundle=bundle,
            graph_name=graph_name,
            thread_id=thread_id,
            state=state,
            execution_tracker=execution_tracker,
        )
        return self._shape_streaming_result(
            result, metadata_graph_name, profile=profile
        )

    def _create_streaming_interrupt_result(
        self,
        bundle: GraphBundle,
        graph_name: str,
        thread_id: str,
        state: Any,
        execution_tracker: Any,
    ) -> ExecutionResult:
        """Run the canonical interrupt sequence and return an ExecutionResult.

        Single shared builder for both streaming LangGraph-suspension paths —
        the mid-stream ``GraphInterrupt`` (via ``_build_graph_interrupt_result``)
        and the post-stream ``get_state`` check (via
        ``_detect_post_stream_suspension``).  Mirrors the non-streaming
        ``_run_core_async`` sequence (:1390-1424 / :1495-1526) exactly:
        ``handle_langgraph_interrupt`` → derive ``interrupt_type`` →
        ``display_resume_instructions`` → ``log_interrupt_status`` →
        ``create_interrupt_result``.

        The returned ``ExecutionResult`` is shaped into the consumer dict by
        ``_shape_streaming_result`` (its ``__interrupted`` branch).  Deriving the
        suspended terminal through the canonical builder + shaper — instead of
        hand-mirroring the dict — makes it byte-identical to
        ``run_workflow_async``'s interrupted return *by construction*: a dropped
        field (``execution_summary``, ``interrupt_info.thread_id``, …) becomes
        structurally impossible (D-4, AC-3, AC-8b; Blockers #2/#3).
        """
        interrupt_details: Optional[Dict[str, Any]] = None
        if getattr(state, "tasks", None):
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
            interrupt_type = "unknown"

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

    def _shape_streaming_result(
        self,
        result: ExecutionResult,
        graph_name: str,
        profile: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Map ExecutionResult to a result dict identical to run_workflow_async (D-4).

        This is the single source of truth for terminal-event result shaping
        in the streaming path (spec §3.6 terminal-result shaping).  ``profile``
        is threaded into ``metadata`` for parity with ``run_workflow_async``
        (B-5, AC-3).
        """
        if result.success:
            return {
                "success": True,
                "outputs": result.final_state,
                "execution_id": getattr(result, "execution_id", None),
                "execution_summary": result.execution_summary,
                "metadata": {"graph_name": graph_name, "profile": profile},
            }

        # Check for suspended/interrupted state
        if isinstance(result.final_state, dict) and result.final_state.get(
            "__interrupted"
        ):
            thread_id = result.final_state.get("__thread_id")
            interrupt_info = result.final_state.get("__interrupt_info", {})
            return {
                "success": False,
                "interrupted": True,
                "thread_id": thread_id,
                "message": f"Execution interrupted in thread: {thread_id}",
                "interrupt_info": interrupt_info,
                "execution_summary": result.execution_summary,
                "metadata": {
                    "graph_name": graph_name,
                    "profile": profile,
                    "checkpoint_available": True,
                    "interrupt_type": interrupt_info.get("type", "unknown"),
                    "node_name": interrupt_info.get("node_name", "unknown"),
                },
            }

        # Standard failure
        return {
            "success": False,
            "outputs": result.final_state,
            "execution_id": getattr(result, "execution_id", None),
            "execution_summary": result.execution_summary,
            "metadata": {"graph_name": graph_name, "profile": profile},
            "error": result.error,
        }

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

    async def resume_from_checkpoint_async(
        self,
        bundle: GraphBundle,
        thread_id: str,
        checkpoint_state: Dict[str, Any],
        resume_node: Optional[str] = None,
        _cancel_unmark_claimed: Optional[threading.Event] = None,
    ) -> ExecutionResult:
        """Resume graph execution from a checkpoint asynchronously.

        Async sibling of ``resume_from_checkpoint()``.  Delegates to
        ``CheckpointManager.resume_from_checkpoint_async`` (REQ-F-005,
        REQ-F-008).

        Args:
            bundle: Graph bundle.
            thread_id: Thread identifier.
            checkpoint_state: State to resume with.
            resume_node: Optional node to resume from.
            _cancel_unmark_claimed: Event set by the manager once it has claimed
                ownership of the cancel-unmark.  The caller (facade) uses this to
                avoid racing with the manager's deferred-unmark task (B-3 fix).

        Returns:
            ExecutionResult from resumed execution.

        Raises:
            asyncio.CancelledError: Propagated without swallowing (REQ-F-009).
        """
        return await self.checkpoint_manager.resume_from_checkpoint_async(
            bundle=bundle,
            thread_id=thread_id,
            checkpoint_state=checkpoint_state,
            resume_node=resume_node,
            _cancel_unmark_claimed=_cancel_unmark_claimed,
        )
