"""
Intelligent tool selection and execution agent.

Follows OrchestratorAgent pattern: data container with service delegation.
Delegates tool selection to OrchestratorService and executes via LangGraph ToolNode.
"""

import inspect
import re
import uuid
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage
from langgraph.prebuilt import ToolNode

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.protocols import LLMCapableAgent, ToolSelectionCapableAgent


class ToolAgent(BaseAgent, LLMCapableAgent, ToolSelectionCapableAgent):
    """
    Intelligent tool selection and execution agent.

    Follows OrchestratorAgent pattern: data container with service delegation.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[list] = None,
        logger=None,
        execution_tracking_service=None,
        state_adapter_service=None,
    ):
        """
        Initialize tool agent as data container with service delegation.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including tool configuration
            tools: List of LangChain tools
            logger: Logger instance for logging operations
            execution_tracking_service: ExecutionTrackingService instance
            state_adapter_service: StateAdapterService instance
        """
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracking_service,
            state_adapter_service=state_adapter_service,
        )

        # Tool configuration (data properties)
        self.tools = tools or []
        self.tool_descriptions = self._resolve_tool_descriptions(
            self.tools, context or {}
        )
        self.matching_strategy = (
            context.get("matching_strategy", "tiered") if context else "tiered"
        )
        self.confidence_threshold = float(
            context.get("confidence_threshold", 0.8) if context else 0.8
        )

        # LLM configuration (for tool selection)
        self.llm_type = context.get("llm_type", "openai") if context else "openai"
        self.temperature = float(context.get("temperature", 0.2) if context else 0.2)

        # Business service (injected via protocol)
        self.orchestrator_service = None

        # LangGraph ToolNode for execution
        self.tool_node = ToolNode(self.tools) if self.tools else None

        if logger:
            self.log_debug(
                f"Initialized with {len(self.tools)} tools, "
                f"strategy={self.matching_strategy}"
            )

    def configure_orchestrator_service(self, orchestrator_service) -> None:
        """Configure orchestrator service for tool selection (protocol method)."""
        self.orchestrator_service = orchestrator_service
        if self._logger:
            self.log_debug("Orchestrator service configured")

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process inputs and execute the best matching tool.

        Delegates selection to OrchestratorService.
        """
        # Extract input text
        input_text = self._get_input_text(inputs)
        self.log_debug(f"Input text: '{input_text}'")

        # Single tool optimization
        if len(self.tools) == 1:
            self.log_debug("Only one tool, bypassing selection")
            return self._execute_tool(self.tools[0], inputs)

        # Ensure orchestrator service is configured
        if not self.orchestrator_service:
            error_msg = "OrchestratorService not configured"
            self.log_error(f"{error_msg} - cannot perform tool selection")
            raise ValueError(error_msg)

        # Transform tools to node format for OrchestratorService
        tools_as_nodes = self._tools_to_node_format(self.tool_descriptions)

        # Prepare LLM configuration
        llm_config = {
            "provider": self.llm_type,
            "temperature": self.temperature,
        }

        # Delegate to OrchestratorService
        selected_tool_name = self.orchestrator_service.select_best_node(
            input_text=input_text,
            available_nodes=tools_as_nodes,
            strategy=self.matching_strategy,
            confidence_threshold=self.confidence_threshold,
            llm_config=llm_config,
        )

        self.log_info(f"Selected tool: '{selected_tool_name}'")

        # Execute selected tool
        tool = self._get_tool_by_name(selected_tool_name)
        return self._execute_tool(tool, inputs)

    def _execute_tool(self, tool, inputs):
        """Execute tool using LangGraph's ToolNode with parameter mapping."""
        # Map state field names to tool parameter names
        mapped_args = self._map_inputs_to_tool_params(tool, inputs)

        tool_call = {
            "name": tool.name,
            "args": mapped_args,
            "id": str(uuid.uuid4()),
        }
        ai_message = AIMessage(content="", tool_calls=[tool_call])
        result = self.tool_node.invoke({"messages": [ai_message]})
        return result["messages"][-1].content

    def _map_inputs_to_tool_params(
        self, tool, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Map state field names to tool parameter names.

        For single-parameter tools, maps the input field value to the tool's parameter name.
        For multi-parameter tools, attempts to match by name or position.

        Args:
            tool: The tool to execute
            inputs: Dictionary of input values from state (using state field names)

        Returns:
            Dictionary with keys matching the tool's expected parameter names
        """
        # Get tool's expected parameters
        try:
            tool_params = list(inspect.signature(tool.func).parameters.keys())
        except (AttributeError, ValueError, TypeError):
            # If we can't inspect, return inputs as-is
            self.log_debug("Could not inspect tool signature, using raw inputs")
            return inputs

        # If no parameters expected, return empty dict
        if not tool_params:
            return {}

        # If tool expects exactly what we have (parameter names match), use as-is
        if set(tool_params) == set(inputs.keys()):
            self.log_debug(f"Parameter names match exactly: {tool_params}")
            return inputs

        # Single-parameter tool optimization
        if len(tool_params) == 1:
            param_name = tool_params[0]
            # Use the first input field value mapped to the tool's parameter name
            if self.input_fields and len(self.input_fields) > 0:
                input_field = self.input_fields[0]
                if input_field in inputs:
                    mapped = {param_name: inputs[input_field]}
                    self.log_debug(
                        f"Mapped single parameter: '{input_field}' → '{param_name}'"
                    )
                    return mapped

            # Fallback: use first available input value
            if inputs:
                first_value = next(iter(inputs.values()))
                self.log_debug(
                    f"Single parameter fallback: using first input as '{param_name}'"
                )
                return {param_name: first_value}

        # Multi-parameter tool: try to match by name, then by position
        mapped = {}
        remaining_inputs = list(inputs.items())

        for i, param_name in enumerate(tool_params):
            # Try exact name match first
            if param_name in inputs:
                mapped[param_name] = inputs[param_name]
            # Try positional mapping using input_fields order
            elif self.input_fields and i < len(self.input_fields):
                input_field = self.input_fields[i]
                if input_field in inputs:
                    mapped[param_name] = inputs[input_field]
                    self.log_debug(
                        f"Positional mapping: '{input_field}' → '{param_name}'"
                    )
            # Fallback: use remaining inputs in order
            elif i < len(remaining_inputs):
                mapped[param_name] = remaining_inputs[i][1]

        self.log_debug(
            f"Multi-parameter mapping complete: {len(mapped)}/{len(tool_params)} parameters mapped"
        )
        return mapped

    def _resolve_tool_descriptions(self, tools, context):
        """
        Resolve tool descriptions with priority:
        1. Extract from tool definitions (baseline)
        2. Override with CSV inline descriptions (higher priority)
        """
        descriptions = {}

        # Baseline: Extract from tools
        for tool in tools:
            descriptions[tool.name] = {
                "description": tool.description or tool.__doc__ or "",
                "name": tool.name,
            }

        # Override: Parse CSV inline descriptions if present
        available_tools = context.get("available_tools", "")
        if "|" in available_tools and "(" in available_tools:
            for tool_spec in available_tools.split("|"):
                match = re.match(r'(\w+)\("([^"]+)"\)', tool_spec.strip())
                if match:
                    tool_name, csv_description = match.groups()
                    if tool_name in descriptions:
                        descriptions[tool_name]["description"] = csv_description

        return descriptions

    def _tools_to_node_format(self, tool_descriptions):
        """Transform tools to node format for OrchestratorService."""
        return {
            name: {
                "description": info["description"],
                "type": "tool",
                "prompt": info["description"],
            }
            for name, info in tool_descriptions.items()
        }

    def _get_tool_by_name(self, tool_name: str):
        """Get tool by name."""
        for tool in self.tools:
            if tool.name == tool_name:
                return tool
        raise ValueError(f"Tool '{tool_name}' not found")

    def _get_input_text(self, inputs: Dict[str, Any]) -> str:
        """Extract input text from inputs using the configured input field."""
        # First try the configured input fields
        for field in self.input_fields:
            if field in inputs and field not in ["available_tools", "tools"]:
                value = inputs[field]
                if isinstance(value, str):
                    return value

        # Fallback to common input field names
        for field in ["input", "query", "text", "message", "user_input", "request"]:
            if field in inputs:
                return str(inputs[field])

        # Last resort: use any string field
        for field, value in inputs.items():
            if field not in ["available_tools", "tools"] and isinstance(value, str):
                self.log_debug(f"Using fallback input field '{field}' for input text")
                return str(value)

        self.log_warning("No input text found in inputs")
        return ""
