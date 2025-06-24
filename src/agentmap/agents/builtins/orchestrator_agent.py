"""
Modernized OrchestratorAgent with protocol-based dependency injection.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import LLMCapableAgent, LLMServiceProtocol
from agentmap.services.state_adapter_service import StateAdapterService


class OrchestratorAgent(BaseAgent, LLMCapableAgent):
    """
    Agent that orchestrates workflow by selecting the best matching node based on input.

    Follows the modernized protocol-based pattern where:
    - Infrastructure services are injected via constructor
    - Business services (LLM) are configured post-construction via protocols
    - Implements LLMCapableAgent protocol for service configuration

    Uses LLM Service to perform intent matching with standardized prompt resolution.
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
        Initialize orchestrator agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including orchestration configuration
            logger: Logger instance for logging operations
            execution_tracker: ExecutionTrackingService instance for tracking
            state_adapter: StateAdapterService instance for state operations
        """
        # Call new BaseAgent constructor (infrastructure services only)
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # Configuration from context
        context = context or {}

        # Selection criteria for node scoring
        self.selection_criteria = context.get("selection_criteria", [])

        # Matching strategy configuration with validation
        raw_strategy = context.get("matching_strategy", "tiered")
        valid_strategies = ["algorithm", "llm", "tiered"]

        if raw_strategy in valid_strategies:
            self.matching_strategy = raw_strategy
        else:
            if self._logger:  # Only log if logger is available
                self.log_warning(
                    f"Invalid matching strategy '{raw_strategy}', defaulting to 'tiered'"
                )
            self.matching_strategy = "tiered"  # Invalid strategies default to tiered

        self.confidence_threshold = float(context.get("confidence_threshold", 0.8))

        # Business services will be configured via protocols
        # Node Registry - will be injected separately (not part of standard protocols yet)
        self.node_registry = None

        # Core configuration options
        self.llm_type = context.get("llm_type", "openai")
        self.temperature = float(context.get("temperature", 0.2))
        self.default_target = context.get("default_target", None)

        # Node filtering configuration
        self.node_filter = self._parse_node_filter(context)

        # Note: LLM availability validation removed as it requires DI container access
        # LLM service availability will be validated at runtime when configure_llm_service() is called
        # This follows clean architecture - agents should not directly access DI container

        if self._logger:  # Only log if logger is available
            self.log_debug(
                f"Initialized with: matching_strategy={self.matching_strategy}, "
                f"node_filter={self.node_filter}, llm_type={self.llm_type}"
            )

    # Properties for test compatibility
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
        if self._logger:  # Only log if logger is available
            self.log_debug("LLM service configured")

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

    # PromptResolutionMixin implementation
    def _get_default_template_file(self) -> str:
        """Get default template file for orchestrator prompts."""
        return "file:orchestrator/intent_matching_v1.txt"

    def _get_default_template_text(self) -> str:
        """Get default template text for orchestrator prompts."""
        return (
            "You are an intent router that selects the most appropriate node to handle a user request.\n"
            "Available nodes:\n{nodes_text}\n\n"
            "User input: '{input_text}'\n\n"
            "Consider the semantics and intent of the user request then select the SINGLE BEST node.\n"
            "Output a JSON object with a 'selectedNode' field containing your selection, confidence level, and reasoning:\n\n"
            "Output format:\n"
            "{{\n"
            '  "selectedNode": "node_name",\n'
            '  "confidence": 0.8,\n'
            '  "reasoning": "your reasoning"\n'
            "}}"
        )

    def _extract_template_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract template variables specific to orchestrator needs."""
        # Get input text for intent matching
        input_text = self._get_input_text(inputs)

        # Get available nodes using same priority as process() method
        available_nodes = self._get_nodes_from_inputs(inputs) or self.node_registry

        # Format node descriptions for template
        nodes_text = self._format_node_descriptions(available_nodes)

        return {"input_text": input_text, "nodes_text": nodes_text}

    def _format_node_descriptions(self, nodes: Dict[str, Dict[str, Any]]) -> str:
        """Format node descriptions for template substitution."""
        if not nodes:
            return "No nodes available"

        descriptions = []
        for node_name, node_info in nodes.items():
            # Skip invalid node formats gracefully
            if not isinstance(node_info, dict):
                descriptions.append(f"- Node: {node_name}\n  Status: Invalid format")
                continue

            description = node_info.get("description", "")
            prompt = node_info.get("prompt", "")
            node_type = node_info.get("type", "")

            descriptions.append(
                f"- Node: {node_name}\n"
                f"  Description: {description}\n"
                f"  Prompt: {prompt}\n"
                f"  Type: {node_type}"
            )

        return "\n".join(descriptions)

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

    def process(self, inputs: Dict[str, Any]) -> str:
        """Process inputs and select the best matching node."""
        # Get input text for intent matching
        input_text = self._get_input_text(inputs)
        self.log_debug(f"Input text: '{input_text}'")

        # Primary: Check for CSV runtime inputs first (allows execution-specific node lists)
        available_nodes = self._get_nodes_from_inputs(inputs)

        # Fallback: Use injected registry if no CSV nodes found
        if not available_nodes:
            available_nodes = self.node_registry
            if available_nodes:
                self.log_debug("Using injected node registry as no CSV nodes provided")
        else:
            self.log_debug(f"Using CSV-provided nodes: {list(available_nodes.keys())}")

        if not available_nodes:
            error_msg = "No nodes available"
            self.log_error(f"{error_msg} - cannot perform orchestration")
            return self.default_target or error_msg

        # Apply filtering based on context options
        filtered_nodes = self._apply_node_filter(available_nodes)
        self.log_debug(
            f"Available nodes after filtering: {list(filtered_nodes.keys())}"
        )

        if not filtered_nodes:
            self.log_warning(
                f"No nodes available after filtering. Using default: {self.default_target}"
            )
            return self.default_target or ""

        # Handle single node case
        if len(filtered_nodes) == 1:
            node_name = next(iter(filtered_nodes.keys()))
            self.log_debug(
                f"Only one node available, selecting '{node_name}' without matching"
            )
            return node_name

        # Select node based on matching strategy
        selected_node = self._match_intent(input_text, filtered_nodes, inputs)
        self.log_info(f"Selected node: '{selected_node}'")
        return selected_node

    def _match_intent(
        self,
        input_text: str,
        available_nodes: Dict[str, Dict[str, Any]],
        inputs: Dict[str, Any],
    ) -> str:
        """Match input to the best node using the configured strategy."""
        if self.matching_strategy == "algorithm":
            self.log_info(
                f"Using algorithm-based orchestration for request: {input_text}"
            )
            node, confidence = self._simple_match(input_text, available_nodes)

            # Log warning if no good match found
            if confidence < 0.1:  # Very low confidence indicates no specific match
                self.log_warning(
                    f"No specific match found for request '{input_text}', using fallback node '{node}'"
                )

            self.log_debug(
                f"Using algorithm matching, selected '{node}' with confidence {confidence:.2f}"
            )
            return node
        elif self.matching_strategy == "llm":
            self.log_info(f"Using LLM-based orchestration for request: {input_text}")
            return self._llm_match(inputs, available_nodes)
        else:  # "tiered" - default approach
            node, confidence = self._simple_match(input_text, available_nodes)
            if confidence >= self.confidence_threshold:
                self.log_info(
                    f"Algorithmic match confidence {confidence:.2f} exceeds threshold. Using '{node}'"
                )
                return node
            self.log_info(
                f"Algorithmic match confidence {confidence:.2f} below threshold. Using LLM."
            )
            return self._llm_match(inputs, available_nodes)

    def _llm_match(
        self, inputs: Dict[str, Any], available_nodes: Dict[str, Dict[str, Any]]
    ) -> str:
        """Use LLM Service to match input to the best node with standardized prompt resolution."""
        # Get input text and format nodes
        input_text = self._get_input_text(inputs)
        nodes_text = self._format_node_descriptions(available_nodes)

        # Get additional context if provided
        additional_context = ""
        if "routing_context" in inputs and inputs["routing_context"]:
            additional_context = f"\n\nAdditional context: {inputs['routing_context']}"

        # Construct prompt for LLM-based node selection
        llm_prompt = f"""You are an intent router that selects the most appropriate node to handle a user request.
Available nodes:
{nodes_text}

User input: '{input_text}'{additional_context}

Consider the semantics and intent of the user request then select the SINGLE BEST node.
Output a JSON object with a 'selectedNode' field containing your selection, confidence level, and reasoning:

Output format:
{{
  "selectedNode": "node_name",
  "confidence": 0.8,
  "reasoning": "your reasoning"
}}"""

        # Build messages for LLM call
        messages = [{"role": "user", "content": llm_prompt}]

        # Use injected LLM service (will raise ValueError if not configured)
        llm_service = self.llm_service  # Let configuration errors propagate

        # Call LLM service (let API errors propagate too)
        llm_response = llm_service.call_llm(
            provider=self.llm_type, messages=messages, temperature=self.temperature
        )

        # Extract selected node from response
        return self._extract_node_from_response(llm_response, available_nodes)

    def _extract_node_from_response(
        self, llm_response: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> str:
        """Extract the selected node from LLM response."""
        # Try to parse JSON response first
        try:
            import json

            if isinstance(llm_response, str) and llm_response.strip().startswith("{"):
                parsed = json.loads(llm_response.strip())
                if "selectedNode" in parsed:
                    selected = parsed["selectedNode"]
                    if selected in available_nodes:
                        return selected
        except json.JSONDecodeError:
            pass

        # Fallback: look for exact node name in response
        llm_response_str = str(llm_response).strip()

        # First try exact match
        if llm_response_str in available_nodes:
            return llm_response_str

        # Then try substring matching (but prioritize longer matches)
        matches = []
        for node_name in available_nodes.keys():
            if node_name in llm_response_str:
                matches.append(node_name)

        if matches:
            # Return the longest match (most specific)
            return max(matches, key=len)

        # Last resort: return first available
        self.log_warning(
            "Couldn't extract node from LLM response. Using first available."
        )
        return next(iter(available_nodes.keys()))

    # Keep existing helper methods unchanged
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

    def _apply_node_filter(
        self, nodes: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Apply node filtering based on context options."""
        if not nodes:
            return {}

        if self.node_filter.count("|") > 0:
            node_names = [n.strip() for n in self.node_filter.split("|")]
            return {name: info for name, info in nodes.items() if name in node_names}
        elif self.node_filter.startswith("nodeType:"):
            type_filter = self.node_filter.split(":", 1)[1].strip()
            return {
                name: info
                for name, info in nodes.items()
                if info.get("type", "").lower() == type_filter.lower()
            }

        return nodes

    @staticmethod
    def _simple_match(
        input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        """Fast algorithmic matching for obvious cases."""
        input_lower = input_text.lower()

        # Check for exact node name match
        for node_name in available_nodes:
            if node_name.lower() in input_lower:
                return node_name, 1.0

        # Keyword matching - check multiple fields
        best_match = None
        best_score = 0.0

        for node_name, node_info in available_nodes.items():
            # Skip invalid node formats gracefully
            if not isinstance(node_info, dict):
                continue

            # Combine text from multiple fields for matching
            text_fields = [
                node_info.get("intent", ""),
                node_info.get("prompt", ""),
                node_info.get("description", ""),
                node_info.get("name", ""),
            ]

            # Create combined text for keyword matching
            combined_text = " ".join(field for field in text_fields if field)
            keywords = combined_text.lower().split()

            if keywords:
                matches = sum(1 for kw in keywords if kw in input_lower)
                score = matches / len(keywords)
                if score > best_score:
                    best_score = score
                    best_match = node_name

        return best_match or next(iter(available_nodes)), best_score
