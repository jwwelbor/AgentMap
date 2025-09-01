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

from agentmap.models.execution_result import ExecutionResult
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
            # Phase 1: Bootstrap - register agent classes (conditional)
            # if self.use_direct_import:
            #     self.logger.debug(f"[GraphRunnerService] Phase 1: Skipping bootstrap (direct import enabled)")
            # else:
            #     self.logger.debug(f"[GraphRunnerService] Phase 1: Bootstrapping agents for {graph_name}")
            #     bootstrap_summary = self.graph_bootstrap.bootstrap_from_bundle(bundle)
            #     self.logger.debug(
            #         f"[GraphRunnerService] Bootstrap completed: "
            #         f"{bootstrap_summary['loaded_agents']} agents registered"
            #     )

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
            from agentmap.models.execution_summary import ExecutionSummary

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
