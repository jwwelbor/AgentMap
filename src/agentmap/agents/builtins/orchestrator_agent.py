"""
Refactored OrchestratorAgent as pure data container with service delegation.

Following Domain Model Principles where models are data containers and services
contain business logic. All orchestration logic moved to OrchestratorService.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.orchestrator_service import OrchestratorService
from agentmap.services.protocols import (
    LLMCapableAgent,
    LLMServiceProtocol,
    OrchestrationCapableAgent,
)
from agentmap.services.state_adapter_service import StateAdapterService


class OrchestratorAgent(BaseAgent, LLMCapableAgent, OrchestrationCapableAgent):
    """
    Agent that orchestrates workflow by selecting the best matching node based on input.

    Pure data container following Domain Model Principles. All business logic
    has been moved to OrchestratorService. This agent simply:
    - Stores configuration data from CSV
    - Delegates orchestration business logic to OrchestratorService
    - Maintains protocol compliance for LLM service configuration
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
        Initialize orchestrator agent as data container with service delegation.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including orchestration configuration
            logger: Logger instance for logging operations
            execution_tracker_service: ExecutionTrackingService instance for tracking
            state_adapter_service: StateAdapterService instance for state operations
        """
        # Call BaseAgent constructor (infrastructure services only)
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # Configuration data from CSV context
        context = context or {}

        # Orchestration configuration (data properties only)
        self.selection_criteria = context.get("selection_criteria", [])
        self.matching_strategy = self._validate_strategy(
            context.get("matching_strategy", "tiered")
        )
        self.confidence_threshold = float(context.get("confidence_threshold", 0.8))
        self.node_filter = self._parse_node_filter(context)
        self.default_target = context.get("default_target", None)

        # LLM configuration data
        self.llm_type = context.get("llm_type", "openai")
        self.temperature = float(context.get("temperature", 0.2))

        # Business service for delegation (will be injected via protocol)
        self.orchestrator_service = (
            None  # Will be configured via configure_orchestrator_service()
        )

        # Node Registry - will be injected separately (not part of standard protocols yet)
        self.node_registry = None

        if self._logger:
            self.log_debug(
                f"Initialized with: matching_strategy={self.matching_strategy}, "
                f"node_filter={self.node_filter}, llm_type={self.llm_type}"
            )

    def _validate_strategy(self, strategy: str) -> str:
        """Validate matching strategy and provide safe fallback."""
        valid_strategies = ["algorithm", "llm", "tiered"]

        if strategy in valid_strategies:
            return strategy
        else:
            if self._logger:
                self.log_warning(
                    f"Invalid matching strategy '{strategy}', defaulting to 'tiered'"
                )
            return "tiered"

    def _parse_node_filter(self, context: dict) -> str:
        """Parse node filter from various context formats."""
        if "nodes" in context:
            return context["nodes"]
        elif "node_type" in context:
            return f"nodeType:{context['node_type']}"
        elif "nodeType" in context:
            return f"nodeType:{context['nodeType']}"
        else:
            return "all"

    # Properties for service coordination
    @property
    def requires_llm(self) -> bool:
        """Check if the current matching strategy requires LLM service."""
        return self.matching_strategy in ["llm", "tiered"]

    # Protocol Implementation (Required by LLMCapableAgent)
    def configure_llm_service(self, llm_service: LLMServiceProtocol) -> None:
        """
        Configure LLM service for this agent.

        This method is called by GraphRunnerService during agent setup.

        Args:
            llm_service: LLM service instance to configure
        """
        self._llm_service = llm_service

        # Also configure the orchestrator service if available
        if self.orchestrator_service:
            self.orchestrator_service.llm_service = llm_service

        if self._logger:
            self.log_debug("LLM service configured")

    def configure_orchestrator_service(
        self, orchestrator_service: OrchestratorService
    ) -> None:
        """
        Configure orchestrator service for this agent.

        This method is called by GraphRunnerService during agent setup
        following the protocol-based dependency injection pattern.

        Args:
            orchestrator_service: OrchestratorService instance for business logic delegation
        """
        self.orchestrator_service = orchestrator_service

        if self._logger:
            self.log_debug("Orchestrator service configured")

    def process(self, inputs: Dict[str, Any]) -> str:
        """
        Process inputs and select the best matching node.

        Delegates all business logic to OrchestratorService.
        """
        if not self.orchestrator_service:
            error_msg = "OrchestratorService not configured"
            self.log_error(f"{error_msg} - cannot perform orchestration")
            return self.default_target or error_msg

        # Extract input text and available nodes (data extraction only)
        input_text = self._get_input_text(inputs)
        self.log_debug(f"Input text: '{input_text}'")

        # Get available nodes (primary: CSV runtime, fallback: injected registry)
        available_nodes = self._get_nodes_from_inputs(inputs)
        if not available_nodes:
            available_nodes = self.node_registry
            if available_nodes:
                self.log_debug("Using injected node registry as no CSV nodes provided")
        else:
            self.log_debug(f"Using CSV-provided nodes: {list(available_nodes.keys())}")

        # Prepare LLM configuration
        llm_config = {
            "provider": self.llm_type,
            "temperature": self.temperature,
        }

        # Prepare additional context
        context = {
            "routing_context": inputs.get("routing_context"),
            "default_target": self.default_target,
        }

        # Delegate to OrchestratorService for all business logic
        try:
            selected_node = self.orchestrator_service.select_best_node(
                input_text=input_text,
                available_nodes=available_nodes,
                strategy=self.matching_strategy,
                confidence_threshold=self.confidence_threshold,
                node_filter=self.node_filter,
                llm_config=llm_config,
                context=context,
            )

            self.log_info(f"Selected node: '{selected_node}'")
            return selected_node

        except Exception as e:
            self.log_error(f"Error in orchestration: {e}")
            return self.default_target or str(e)

    def _post_process(
        self, state: Any, inputs: Dict[str, Any], output: Any
    ) -> Tuple[Any, Any]:
        """Post-process output to extract node name and set routing directive."""

        # Extract selectedNode from output if needed
        if isinstance(output, dict) and "selectedNode" in output:
            selected_node = output["selectedNode"]
            self.log_info(f"Extracted selected node '{selected_node}' from result dict")
        else:
            selected_node = output

        state = StateAdapterService.set_value(state, "__next_node", selected_node)
        self.log_info(f"Setting __next_node to '{selected_node}'")

        return state, output

    # Simple data extraction helpers (no business logic)
    def _get_input_text(self, inputs: Dict[str, Any]) -> str:
        """Extract input text from inputs using the configured input field."""
        # First try the configured input fields (typically the first field is the input text)
        for field in self.input_fields:
            if field in inputs and field not in [
                "available_nodes",
                "nodes",
                "__node_registry",
            ]:
                value = inputs[field]
                if isinstance(value, str):
                    return value

        # Fallback to common input field names
        for field in ["input", "query", "text", "message", "user_input", "request"]:
            if field in inputs:
                return str(inputs[field])

        # Last resort: use any string field that's not a node field
        for field, value in inputs.items():
            if field not in [
                "available_nodes",
                "nodes",
                "__node_registry",
            ] and isinstance(value, str):
                if self._logger:
                    self.log_debug(
                        f"Using fallback input field '{field}' for input text"
                    )
                return str(value)

        if self._logger:
            self.log_warning("No input text found in inputs")
        return ""

    def _get_nodes_from_inputs(
        self, inputs: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Get node dictionary from inputs when available."""
        # First check standard field names for nodes
        for field_name in ["available_nodes", "nodes", "__node_registry"]:
            if field_name in inputs and isinstance(inputs[field_name], dict):
                return inputs[field_name]

        # Then check configured input fields for nodes (skip text fields)
        for field in self.input_fields:
            if field in inputs and field not in [
                "request",
                "input",
                "query",
                "text",
                "message",
                "user_input",
            ]:
                value = inputs[field]
                if isinstance(value, dict):
                    return value

        return {}

    def get_service_info(self) -> Dict[str, Any]:
        """Get information about agent configuration and service delegation."""
        base_info = super().get_service_info()

        orchestrator_info = {
            "orchestration_config": {
                "matching_strategy": self.matching_strategy,
                "confidence_threshold": self.confidence_threshold,
                "node_filter": self.node_filter,
                "llm_type": self.llm_type,
                "temperature": self.temperature,
            },
            "orchestrator_service_configured": self.orchestrator_service is not None,
        }

        base_info.update(orchestrator_info)
        return base_info
