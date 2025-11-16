# agentmap/agents/builtins/branching_agent.py
import logging
from typing import Any, Dict, List, Optional, Tuple

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class BranchingAgent(BaseAgent):
    """
    Configurable branching agent that determines success/failure based on input criteria.

    This agent can be configured to check specific fields and values, making it useful
    both for testing workflows and for real conditional logic in production systems.

    Configuration options:
    - input_fields: Fields to extract from state (first field automatically becomes success_field)
    - success_values: List of values that indicate success (default: [True, "true", "yes", "success", "1"])
    - failure_values: List of values that indicate failure (default: [False, "false", "no", "failure", "0"])
    - default_result: What to return if field not found or value not recognized (default: True)
    - fallback_fields: Additional fields to check if primary field not found
    - success_field: Override which field to check (defaults to first input_field)

    Simple examples:
        # Basic success/failure testing
        context = {"input_fields": ["success"]}  # Checks "success" field

        # API response validation
        context = {
            "input_fields": ["http_status"],
            "success_values": [200, 201, "OK"],
            "failure_values": [400, 404, 500]
        }

        # Task completion checking
        context = {
            "input_fields": ["task_status"],
            "success_values": ["COMPLETED", "DONE"],
            "fallback_fields": ["progress"]  # Check progress if task_status missing
        }
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
        """Initialize the branching agent with configurable success criteria."""
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # Extract configuration from context
        context = context or {}

        # Primary field to check for success criteria
        # Default to first input field, or "success" if no input fields defined
        if self.input_fields:
            default_success_field = self.input_fields[0]
        else:
            default_success_field = "success"

        self.success_field = context.get("success_field", default_success_field)

        # Values that indicate success (case-insensitive for strings)
        self.success_values = self._normalize_values(
            context.get(
                "success_values",
                [True, "true", "yes", "success", "succeed", "1", "t", "y"],
            )
        )

        # Values that indicate failure (case-insensitive for strings)
        self.failure_values = self._normalize_values(
            context.get(
                "failure_values",
                [False, "false", "no", "failure", "fail", "0", "f", "n"],
            )
        )

        # What to return if field not found or value not in success/failure lists
        self.default_result = context.get("default_result", True)

        # Fallback fields to check if primary field not found (for backward compatibility)
        self.fallback_fields = context.get(
            "fallback_fields", ["should_succeed", "succeed", "branch", "input"]
        )

        # Log configuration for debugging
        try:
            self.log_debug(
                f"BranchingAgent configured: field='{self.success_field}', "
                f"success_values={self.success_values}, default={self.default_result}"
            )
        except ValueError:
            # Logger not configured, skip logging
            pass

    def _normalize_values(self, values: List[Any]) -> List[Any]:
        """
        Normalize values for comparison, converting strings to lowercase.

        Args:
            values: List of values to normalize

        Returns:
            List with string values converted to lowercase
        """
        normalized = []
        for value in values:
            if isinstance(value, str):
                normalized.append(value.lower())
            else:
                normalized.append(value)
        return normalized

    def process(self, inputs: Dict[str, Any]) -> str:
        """
        Process the inputs and decide success or failure based on configured criteria.

        Args:
            inputs: Dictionary containing input values from input_fields

        Returns:
            String describing the branching decision
        """
        self.log_info(
            f"[BranchingAgent] {self.name} executed with inputs: {inputs} and prompt: {self.prompt}"
        )

        # Determine success based on configured criteria
        success, field_used, value_found = self._determine_success_detailed(inputs)
        action = "SUCCEED" if success else "FAIL"

        # Create descriptive message
        message = f"BRANCH: {self.name} will {action}"

        # Log the decision details
        if field_used:
            self.log_info(
                f"[BranchingAgent] Decision based on field '{field_used}' = {value_found}"
            )
        else:
            self.log_info(
                f"[BranchingAgent] No matching field found, using default: {self.default_result}"
            )

        # Include decision details in output if helpful
        if inputs:
            if field_used:
                message += f" based on '{field_used}' = {value_found}"
            else:
                message += (
                    f" using default behavior (no '{self.success_field}' field found)"
                )

            # Include all inputs for debugging
            input_str = ", ".join(f"{k}={v}" for k, v in inputs.items())
            message += f" [inputs: {input_str}]"

        # Include the prompt if available
        if self.prompt:
            message += f" with prompt: '{self.prompt}'"

        return message

    def _determine_success_detailed(
        self, inputs: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Any]:
        """
        Determine success with detailed information about which field and value were used.

        Args:
            inputs: Dictionary of input values

        Returns:
            Tuple of (success, field_used, value_found)
        """
        # Check primary field first
        if self.success_field in inputs:
            value = inputs[self.success_field]
            success = self._evaluate_value(value)
            return success, self.success_field, value

        # Check fallback fields if primary not found
        for field in self.fallback_fields:
            if field in inputs:
                value = inputs[field]
                success = self._evaluate_value(value)
                return success, field, value

        # No relevant field found, use default
        return self.default_result, None, None

    def _determine_success(self, inputs: Dict[str, Any], context: dict = None) -> bool:
        """
        Determine whether to succeed or fail based on configured criteria.

        Args:
            inputs: Dictionary of input values
            context: Additional context (unused, kept for compatibility)

        Returns:
            Boolean indicating success (True) or failure (False)
        """
        success, _, _ = self._determine_success_detailed(inputs)
        return success

    def _evaluate_value(self, value: Any) -> bool:
        """
        Evaluate a value against success/failure criteria.

        Args:
            value: Value to evaluate

        Returns:
            Boolean indicating success (True) or failure (False)
        """
        # Normalize value for comparison
        if isinstance(value, str):
            normalized_value = value.lower()
        else:
            normalized_value = value

        # Check if value indicates success
        if normalized_value in self.success_values:
            return True

        # Check if value indicates failure
        if normalized_value in self.failure_values:
            return False

        # Value not recognized, use default
        # For backward compatibility with numeric/boolean evaluation
        if isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return bool(value)

        # For unrecognized values, use default
        return self.default_result

    def _post_process(
        self, state: Any, inputs: Dict[str, Any], output: Any
    ) -> Tuple[Any, Any]:
        """
        Override the post-processing hook to set the success flag based on inputs.

        Args:
            state: Current state
            inputs: Input dictionary
            output: The output value from the process method

        Returns:
            Tuple of (state, output) with success flag set

        Note: For partial state update pattern (parallel execution), we return a dict
        with both the result message and the last_action_success flag.
        """
        # Determine success based on inputs
        success = self._determine_success(inputs)

        # Modify output to indicate branch direction
        if not success:
            result_message = f"{output} (Will trigger FAILURE branch)"
        else:
            result_message = f"{output} (Will trigger SUCCESS branch)"

        # Return a dict with state updates for parallel execution
        # BaseAgent will recognize the 'state_updates' key and merge all fields
        return state, {
            "state_updates": {
                self.output_field: result_message,
                "last_action_success": success,
            }
        }

    def get_configuration_info(self) -> Dict[str, Any]:
        """
        Get information about the agent's configuration for debugging.

        Returns:
            Dictionary with configuration details
        """
        return {
            "success_field": self.success_field,
            "success_values": self.success_values,
            "failure_values": self.failure_values,
            "default_result": self.default_result,
            "fallback_fields": self.fallback_fields,
        }

    def _get_child_service_info(self) -> Dict[str, Any]:
        """
        Provide BranchingAgent-specific service information.

        Returns:
            Dictionary with branching agent-specific service info
        """
        return {
            "services": {
                "branching_logic_configured": True,
                "has_success_criteria": len(self.success_values) > 0,
                "has_failure_criteria": len(self.failure_values) > 0,
                "has_fallback_fields": len(self.fallback_fields) > 0,
            },
            "configuration": {
                "success_field": self.success_field,
                "success_values_count": len(self.success_values),
                "failure_values_count": len(self.failure_values),
                "default_result": self.default_result,
                "fallback_fields_count": len(self.fallback_fields),
            },
            "capabilities": {
                "supports_boolean_logic": True,
                "supports_string_matching": True,
                "supports_numeric_evaluation": True,
                "supports_custom_criteria": True,
                "supports_fallback_logic": True,
            },
        }
