# agentmap/agents/builtins/graph_agent.py
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from agentmap.agents.base_agent import BaseAgent
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.graph.graph_runner_service import GraphRunnerService
from agentmap.services.protocols import (
    GraphBundleCapableAgent,
    GraphBundleServiceProtocol,
)
from agentmap.services.state_adapter_service import StateAdapterService

# from agentmap.utils.function_utils import import_function


class GraphAgent(BaseAgent, GraphBundleCapableAgent):
    """
    Agent that executes a subgraph and returns its result.

    This agent allows for composing multiple graphs into larger workflows
    by running a subgraph as part of a parent graph's execution.

    Supports flexible input/output mapping and nested execution tracking.
    Uses GraphBundleService for efficient bundle-based subgraph execution.

    Implements GraphBundleCapableAgent protocol for proper service injection.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only
        logger: Optional[logging.Logger] = None,
        execution_tracker_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
    ):
        """
        Initialize the graph agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Name of the subgraph to execute
            context: Additional context (CSV path string or config dict)
        """
        # Handle string context (CSV path) by converting to dict for BaseAgent
        original_context = context
        if isinstance(context, str):
            # Convert any string context to dict for BaseAgent compatibility
            context = {}

        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # The subgraph name comes from the prompt field
        self.subgraph_name = prompt

        # Business services - these will need to be injected via DI
        # TODO: Consider creating protocols for these services in future
        self._graph_runner_service = None
        self._function_resolution_service = None
        self._graph_bundle_service = None  # For bundle-based execution

        # Handle context as either string (CSV path) or dict (config)
        if isinstance(original_context, str) and original_context.strip():
            self.csv_path = original_context.strip()
            self.execution_mode = "separate"  # Default: separate execution
        elif isinstance(original_context, dict):
            self.csv_path = original_context.get("csv_path")
            self.execution_mode = original_context.get(
                "execution_mode", "separate"
            )  # "separate" or "native"
        else:
            self.csv_path = None
            self.execution_mode = "separate"

    # Business service configuration (protocol-based and legacy)
    def configure_graph_bundle_service(
        self, graph_bundle_service: GraphBundleServiceProtocol
    ) -> None:
        """Configure graph bundle service for this agent (protocol-based)."""
        self._graph_bundle_service = graph_bundle_service
        self.log_debug("Graph bundle service configured")

    def configure_graph_runner_service(
        self, graph_runner_service: GraphRunnerService
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
    def graph_runner_service(self) -> GraphRunnerService:
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

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs by running the subgraph using bundles.

        Args:
            inputs: Dictionary containing input values from input_fields

        Returns:
            Output from the subgraph execution
        """
        self.log_info(f"[GraphAgent] Executing subgraph: {self.subgraph_name}")

        # Check service configuration first (let configuration errors bubble up)
        graph_runner = self.graph_runner_service
        bundle_service = self.graph_bundle_service

        # Determine and prepare the initial state for the subgraph
        subgraph_state = self._prepare_subgraph_state(inputs)

        try:
            # Get or create the bundle for the subgraph
            bundle = self._get_subgraph_bundle()

            if not bundle:
                raise RuntimeError(
                    f"Failed to get or create bundle for subgraph '{self.subgraph_name}'"
                )

            self.log_debug(
                f"[GraphAgent] Got bundle for subgraph '{self.subgraph_name}' "
                f"with {len(bundle.nodes) if bundle.nodes else 0} nodes"
            )

            # Get parent tracker if available for nested tracking
            parent_tracker = getattr(self, "current_execution_tracker", None)

            # Execute the subgraph using the bundle (not run_graph)
            result = graph_runner.run(
                bundle=bundle,
                initial_state=subgraph_state,
                is_subgraph=True,
                parent_tracker=parent_tracker,
                parent_graph_name=getattr(self, "parent_graph_name", None),
            )

            self.log_info(f"[GraphAgent] Subgraph execution completed successfully")

            # Process the result based on output field mapping
            processed_result = self._process_subgraph_result(result)

            return processed_result

        except Exception as e:
            self.log_error(f"[GraphAgent] Error executing subgraph: {str(e)}")
            return {
                "error": f"Failed to execute subgraph '{self.subgraph_name}': {str(e)}",
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
                    self.subgraph_name, subgraph_summary
                )
                self.log_debug(
                    f"[GraphAgent] Recorded subgraph execution in parent tracker"
                )

            # Remove execution summary from output to avoid polluting final state
            if isinstance(output, dict) and "__execution_summary" in output:
                output = {k: v for k, v in output.items() if k != "__execution_summary"}

        # Set success based on subgraph result
        if isinstance(output, dict):
            graph_success = output.get(
                "graph_success", output.get("last_action_success", True)
            )
            state = self.state_adapter_service.set_value(
                state, "last_action_success", graph_success
            )

        return state, output

    def _prepare_subgraph_state(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare the initial state for the subgraph based on input mappings.

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
            # Pass entire state
            return inputs.copy()
        else:
            # Pass only specified fields
            return {
                field: inputs.get(field)
                for field in self.input_fields
                if field in inputs
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
                if field_spec in inputs:
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
            return inputs.copy()

        try:
            # Import the mapping function
            mapping_func = self.function_resolution_service.import_function(func_ref)

            # Execute the function to transform the state
            mapped_state = mapping_func(inputs)

            # Ensure we got a dictionary back
            if not isinstance(mapped_state, dict):
                self.log_warning(
                    f"[GraphAgent] Mapping function {func_ref} returned non-dict: {type(mapped_state)}"
                )
                return inputs.copy()

            self.log_debug(f"[GraphAgent] Applied function mapping: {func_ref}")
            return mapped_state

        except Exception as e:
            self.log_error(f"[GraphAgent] Error in mapping function: {str(e)}")
            return inputs.copy()

    def _get_subgraph_bundle(self) -> Optional[GraphBundle]:
        """
        Get or create the bundle for the subgraph execution.

        Determines the CSV path from either:
        1. self.csv_path (external CSV subgraph)
        2. Current bundle's csv_path (embedded subgraph in same CSV)

        Returns:
            GraphBundle for the subgraph, or None if failed
        """
        bundle_service = self.graph_bundle_service

        # Determine CSV path
        if self.csv_path:
            # External CSV specified in context
            csv_path = Path(self.csv_path)
            self.log_debug(
                f"[GraphAgent] Using external CSV path: {csv_path} "
                f"for subgraph '{self.subgraph_name}'"
            )
        else:
            # Try to get CSV path from current bundle (embedded subgraph)
            # This would be set by the parent graph runner when it creates this agent
            current_bundle = getattr(self, "current_bundle", None)
            if current_bundle and hasattr(current_bundle, "csv_path"):
                csv_path = Path(current_bundle.csv_path)
                self.log_debug(
                    f"[GraphAgent] Using current bundle's CSV path: {csv_path} "
                    f"for embedded subgraph '{self.subgraph_name}'"
                )
            else:
                # Fallback: try to get from parent context if available
                parent_csv_path = getattr(self, "parent_csv_path", None)
                if parent_csv_path:
                    csv_path = Path(parent_csv_path)
                    self.log_debug(
                        f"[GraphAgent] Using parent CSV path: {csv_path} "
                        f"for subgraph '{self.subgraph_name}'"
                    )
                else:
                    self.log_error(
                        f"[GraphAgent] No CSV path available for subgraph '{self.subgraph_name}'"
                    )
                    return None

        # Get or create bundle using the service
        try:
            bundle, _ = bundle_service.get_or_create_bundle(
                csv_path=csv_path,
                graph_name=self.subgraph_name,
                config_path=getattr(self, "config_path", None),
            )
            return bundle
        except Exception as e:
            self.log_error(
                f"[GraphAgent] Failed to get bundle for subgraph '{self.subgraph_name}': {e}"
            )
            return None

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

        # Default: return entire result (your current behavior)
        return result
