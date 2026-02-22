# agentmap/agents/builtins/graph_agent.py
import logging
import re
from typing import Any, Dict, Optional, Tuple

from agentmap.agents.base_agent import BaseAgent
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.protocols import (
    GraphBundleCapableAgent,
    GraphBundleServiceProtocol,
    GraphRunnerCapableAgent,
    GraphRunnerServiceProtocol,
)
from agentmap.services.state_adapter_service import StateAdapterService


class GraphAgent(BaseAgent, GraphBundleCapableAgent, GraphRunnerCapableAgent):
    """
    Agent that executes a subgraph and returns its result.

    This agent allows for composing multiple graphs into larger workflows
    by running a subgraph as part of a parent graph's execution.

    Subgraph bundles are pre-resolved by GraphRunnerService and passed via
    state["subgraph_bundles"][node_name]. The agent reads its bundle from
    there, prepares input state, and delegates execution to GraphRunnerService.

    Supports flexible input/output mapping and nested execution tracking.
    Implements GraphBundleCapableAgent protocol for proper service injection.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only
        logger: Optional[logging.Logger] = None,
        execution_tracking_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
    ):
        """
        Initialize the graph agent.

        Args:
            name: Name of the agent node
            prompt: Subgraph name (legacy) or descriptive prompt
            context: Additional context (may contain {workflow=...} directives)
        """
        # Handle string context by converting to dict for BaseAgent
        if isinstance(context, str):
            context = {}

        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracking_service,
            state_adapter_service=state_adapter_service,
        )

        # Business services — injected via DI protocols
        self._graph_runner_service = None
        self._function_resolution_service = None
        self._graph_bundle_service = None

    # --- Protocol-based service configuration ---

    def configure_graph_bundle_service(
        self, graph_bundle_service: GraphBundleServiceProtocol
    ) -> None:
        """Configure graph bundle service for this agent (protocol-based)."""
        self._graph_bundle_service = graph_bundle_service
        self.log_debug("Graph bundle service configured")

    def configure_graph_runner_service(
        self, graph_runner_service: GraphRunnerServiceProtocol
    ) -> None:
        """Configure graph runner service for this agent."""
        self._graph_runner_service = graph_runner_service
        self.log_debug("Graph runner service configured")

    def configure_function_resolution_service(
        self, function_resolution_service: FunctionResolutionService
    ) -> None:
        """Configure function resolution service for this agent."""
        self._function_resolution_service = function_resolution_service
        self.log_debug("Function resolution service configured")

    @property
    def graph_bundle_service(self) -> GraphBundleServiceProtocol:
        """Get graph bundle service, raising clear error if not configured."""
        if self._graph_bundle_service is None:
            raise ValueError(
                f"Graph bundle service not configured for agent '{self.name}'"
            )
        return self._graph_bundle_service

    @property
    def graph_runner_service(self) -> GraphRunnerServiceProtocol:
        """Get graph runner service, raising clear error if not configured."""
        if self._graph_runner_service is None:
            raise ValueError(
                f"Graph runner service not configured for agent '{self.name}'"
            )
        return self._graph_runner_service

    @property
    def function_resolution_service(self) -> FunctionResolutionService:
        """Get function resolution service, raising clear error if not configured."""
        if self._function_resolution_service is None:
            raise ValueError(
                f"Function resolution service not configured for agent '{self.name}'"
            )
        return self._function_resolution_service

    def _pre_process(
        self, state: Any, inputs: Dict[str, Any]
    ) -> Tuple[Any, Dict[str, Any]]:
        """Inject subgraph_bundles from state into inputs for process()."""
        if isinstance(state, dict) and "subgraph_bundles" in state:
            inputs["subgraph_bundles"] = state["subgraph_bundles"]
        return state, inputs

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs by running the subgraph using a pre-resolved bundle.

        The bundle is expected in inputs["subgraph_bundles"][self.name],
        placed there by GraphRunnerService._resolve_subgraph_bundles().

        Args:
            inputs: Dictionary containing input values from input_fields

        Returns:
            Output from the subgraph execution
        """
        self.log_info(f"[GraphAgent] Executing subgraph for node: {self.name}")

        # Read pre-resolved bundle from state
        bundle = inputs.get("subgraph_bundles", {}).get(self.name)
        if not bundle:
            raise RuntimeError(
                f"No pre-resolved subgraph bundle for node '{self.name}'. "
                f"Ensure the Context column uses {{workflow=...}} syntax or "
                f"the Prompt column names the subgraph."
            )

        self.log_debug(
            f"[GraphAgent] Got pre-resolved bundle for '{bundle.graph_name}' "
            f"with {len(bundle.nodes) if bundle.nodes else 0} nodes"
        )

        # Check service configuration (let configuration errors bubble up)
        graph_runner = self.graph_runner_service

        # Prepare the initial state for the subgraph
        subgraph_state = self._prepare_subgraph_state(inputs)

        try:
            # Get parent tracker if available for nested tracking
            parent_tracker = getattr(self, "current_execution_tracker", None)

            # Execute the subgraph
            result = graph_runner.run(
                bundle=bundle,
                initial_state=subgraph_state,
                is_subgraph=True,
                parent_tracker=parent_tracker,
                parent_graph_name=getattr(self, "parent_graph_name", None),
            )

            # Extract final_state from ExecutionResult
            from agentmap.models.execution.result import ExecutionResult

            if isinstance(result, ExecutionResult):
                if not result.success:
                    self.log_error(
                        f"[GraphAgent] Subgraph '{bundle.graph_name}' failed: {result.error}"
                    )
                    return {
                        "error": f"Subgraph '{bundle.graph_name}' failed: {result.error}",
                        "last_action_success": False,
                    }
                result = result.final_state or {}

            self.log_info(f"[GraphAgent] Subgraph execution completed successfully")
            return self._process_subgraph_result(result)

        except Exception as e:
            self.log_error(f"[GraphAgent] Error executing subgraph: {str(e)}")
            return {
                "error": f"Failed to execute subgraph for node '{self.name}': {str(e)}",
                "last_action_success": False,
            }

    def _post_process(
        self, state: Any, inputs: Dict[str, Any], output: Any
    ) -> Tuple[Any, Any]:
        """
        Enhanced post-processing to integrate subgraph execution tracking.

        Args:
            state: Current state
            inputs: Input values used for processing
            output: Output from process method

        Returns:
            Tuple of (updated_state, processed_output)
        """
        # Get parent execution tracker (instance, not service)
        parent_tracker = self.current_execution_tracker

        # If output contains execution summary from subgraph, record it
        if isinstance(output, dict) and "__execution_summary" in output:
            subgraph_summary = output["__execution_summary"]

            if parent_tracker and hasattr(parent_tracker, "record_subgraph_execution"):
                parent_tracker.record_subgraph_execution(
                    self.name, subgraph_summary
                )
                self.log_debug(
                    f"[GraphAgent] Recorded subgraph execution in parent tracker"
                )

            # Remove execution summary from output to avoid polluting final state
            if isinstance(output, dict) and "__execution_summary" in output:
                output = {k: v for k, v in output.items() if k != "__execution_summary"}

        # Set success based on subgraph result and use state_updates pattern
        if isinstance(output, dict):
            graph_success = output.get(
                "graph_success", output.get("last_action_success", True)
            )

            state_updates = {
                self.output_field: output,
                "last_action_success": graph_success,
            }

            return state, {"state_updates": state_updates}

        return state, output

    def _prepare_subgraph_state(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare the initial state for the subgraph based on input mappings.

        Filters out internal keys (like subgraph_bundles) from the subgraph state.

        Args:
            inputs: Input values from the parent graph

        Returns:
            Initial state for the subgraph
        """
        # Case 1: Function mapping
        if len(self.input_fields) == 1 and self.input_fields[0].startswith("func:"):
            return self._apply_function_mapping(inputs)

        # Case 2: Field mapping
        if any("=" in field for field in self.input_fields):
            return self._apply_field_mapping(inputs)

        # Case 3: No mapping or direct field passthrough
        if not self.input_fields:
            # Pass entire state, filtering internal keys
            return {
                k: v for k, v in inputs.items()
                if k != "subgraph_bundles"
            }
        else:
            # Pass only specified fields
            return {
                field: inputs.get(field)
                for field in self.input_fields
                if field in inputs and field != "subgraph_bundles"
            }

    def _apply_field_mapping(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Apply field-to-field mapping."""
        subgraph_state = {}

        for field_spec in self.input_fields:
            if "=" in field_spec:
                # This is a mapping (target=source)
                target_field, source_field = field_spec.split("=", 1)
                if source_field in inputs:
                    subgraph_state[target_field] = inputs[source_field]
                    self.log_debug(
                        f"[GraphAgent] Mapped {source_field} -> {target_field}"
                    )
            else:
                # Direct passthrough
                if field_spec in inputs and field_spec != "subgraph_bundles":
                    subgraph_state[field_spec] = inputs[field_spec]
                    self.log_debug(f"[GraphAgent] Passed through {field_spec}")

        return subgraph_state

    def _apply_function_mapping(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Apply function-based mapping."""
        func_ref = self.function_resolution_service.extract_func_ref(
            self.input_fields[0]
        )
        if not func_ref:
            self.log_warning(
                f"[GraphAgent] Invalid function reference: {self.input_fields[0]}"
            )
            return {k: v for k, v in inputs.items() if k != "subgraph_bundles"}

        try:
            mapping_func = self.function_resolution_service.import_function(func_ref)
            mapped_state = mapping_func(inputs)

            if not isinstance(mapped_state, dict):
                self.log_warning(
                    f"[GraphAgent] Mapping function {func_ref} returned non-dict: {type(mapped_state)}"
                )
                return {k: v for k, v in inputs.items() if k != "subgraph_bundles"}

            self.log_debug(f"[GraphAgent] Applied function mapping: {func_ref}")
            return mapped_state

        except Exception as e:
            self.log_error(f"[GraphAgent] Error in mapping function: {str(e)}")
            return {k: v for k, v in inputs.items() if k != "subgraph_bundles"}

    def _process_subgraph_result(self, result: Dict[str, Any]) -> Any:
        """
        Process the subgraph result based on output field configuration.

        Args:
            result: Complete result from subgraph execution

        Returns:
            Processed result for parent graph
        """
        # Handle output field mapping
        if self.output_field and "=" in self.output_field:
            target_field, source_field = self.output_field.split("=", 1)
            if source_field in result:
                processed = {target_field: result[source_field]}
                self.log_debug(
                    f"[GraphAgent] Output mapping: {source_field} -> {target_field}"
                )
                return processed

        # Handle specific output field
        elif self.output_field and self.output_field in result:
            return result[self.output_field]

        # Default: return entire result
        return result
