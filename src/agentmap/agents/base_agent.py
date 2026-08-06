"""
Modernized Base agent class for all AgentMap agents.

Updated to use protocol-based dependency injection following clean architecture patterns.
Infrastructure services are injected via constructor, business services via post-construction configuration.
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from agentmap.agents.agent_lifecycle_mixin import AgentLifecycleMixin
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import (
    LLMCapableAgent,
    LLMServiceProtocol,
    StorageCapableAgent,
    StorageServiceProtocol,
)
from agentmap.services.state_adapter_service import StateAdapterService
from agentmap.services.telemetry.constants import AGENT_INPUTS, AGENT_OUTPUTS


class BaseAgent(AgentLifecycleMixin):
    """
    Modernized base class for all agents in AgentMap.

    Uses protocol-based dependency injection for clean service management.
    Infrastructure services are injected via constructor, business services
    are configured post-construction via configure_*_service() methods.
    """

    # Positional binding: subclasses declare expected parameter names so the
    # framework can map CSV input fields to agent parameters by position.
    expected_params: Optional[List[str]] = None

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only - core services that ALL agents need
        logger: Optional[logging.Logger] = None,
        execution_tracking_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
        # BACKWARD COMPATIBILITY: Support old parameter name from auto-generated agents
        execution_tracker_service: Optional[ExecutionTrackingService] = None,
        # Telemetry instrumentation (optional -- silent degradation when absent)
        telemetry_service: Optional[Any] = None,
    ):
        """
        Initialize the agent with infrastructure dependency injection.

        Business services (LLM, storage) are configured post-construction
        via configure_*_service() methods using protocol-based injection.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction for the agent
            context: Additional context including input/output configuration
            logger: Logger instance (required for proper operation)
            execution_tracking_service: ExecutionTrackingService instance (preferred)
            state_adapter_service: StateAdapterService instance
            execution_tracker_service: DEPRECATED - Use execution_tracking_service instead
                (kept for backward compatibility with auto-generated agents)
            telemetry_service: Optional telemetry service for span management.
                When None, all telemetry helpers silently no-op.
        """
        # Core agent configuration
        self.name = name
        self.prompt = prompt
        self.context = context or {}
        self.prompt_template = prompt

        # Extract input_fields and output_field from context
        self.input_fields = self.context.get("input_fields", [])
        self.output_field = self.context.get("output_field", None)
        self.description = self.context.get("description", "")

        # if self.input_fields is a delimited string, convert to list
        if len(self.input_fields) == 1 and self.input_fields[0].find(",") != -1:
            self.input_fields = str(self.input_fields[0]).split(",")

        if len(self.input_fields) == 1 and self.input_fields[0].find("|") != -1:
            self.input_fields = str(self.input_fields[0]).split("|")

        # Parse output_field into output_fields list for multi-output support
        # Store both raw and parsed values for backward compatibility
        if self.output_field and "|" in self.output_field:
            # Pipe-delimited: split and strip whitespace
            self.output_fields = [
                f.strip() for f in self.output_field.split("|") if f.strip()
            ]
        elif self.output_field:
            # Single output field: wrap in list
            self.output_fields = [self.output_field]
        else:
            # No output field specified
            self.output_fields = []

        # Infrastructure services (required) - only core services ALL agents need
        self._logger = logger

        # BACKWARD COMPATIBILITY: Support both old and new parameter names
        # Prefer new name, fall back to old name if provided
        self._execution_tracking_service = (
            execution_tracking_service or execution_tracker_service
        )

        self._state_adapter_service = state_adapter_service
        self._telemetry_service = telemetry_service
        self._log_prefix = f"[{self.__class__.__name__}:{self.name}]"

        # Business services (configured post-construction)
        self._llm_service: Optional[LLMServiceProtocol] = None
        self._storage_service: Optional[StorageServiceProtocol] = None

        # Current execution tracker (set during graph execution)
        self._current_execution_tracker = None

        # Log initialization
        if logger:
            self.log_debug("Agent initialized with infrastructure services")

    # Service Access Properties
    @property
    def logger(self) -> logging.Logger:
        """Get logger instance, raising if not available."""
        if self._logger is None:
            raise ValueError(
                f"Logger not provided to agent '{self.name}'. "
                "Please inject logger dependency via constructor."
            )
        return self._logger

    @property
    def execution_tracking_service(self) -> ExecutionTrackingService:
        """Get execution tracker instance, raising if not available."""
        if self._execution_tracking_service is None:
            raise ValueError(
                f"ExecutionTrackingService not provided to agent '{self.name}'. "
                "Please inject execution_tracker dependency via constructor."
            )
        return self._execution_tracking_service

    @property
    def state_adapter_service(self) -> StateAdapterService:
        """Get state adapter service."""
        return self._state_adapter_service

    @property
    def llm_service(self) -> LLMServiceProtocol:
        """Get LLM service, raising clear error if not configured."""
        if self._llm_service is None:
            raise ValueError(f"LLM service not configured for agent '{self.name}'")
        return self._llm_service

    @property
    def storage_service(self) -> StorageServiceProtocol:
        """Get storage service, raising clear error if not configured."""
        if self._storage_service is None:
            raise ValueError(f"Storage service not configured for agent '{self.name}'")
        return self._storage_service

    def set_execution_tracker(self, tracker):
        """Set the current execution tracker for this agent during graph execution."""
        self._current_execution_tracker = tracker

    @property
    def current_execution_tracker(self):
        """Get the current execution tracker."""
        return self._current_execution_tracker

    # Logging Methods (updated for better unknown level handling)
    def log(self, level: str, message: str, *args, **kwargs):
        """Log a message with the specified level and proper agent context."""
        # Define valid logging levels
        valid_levels = ["debug", "info", "warning", "error", "trace"]

        # Use the specified level if valid, otherwise default to info
        if level in valid_levels:
            logger_method = getattr(self.logger, level)
        else:
            logger_method = self.logger.info

        logger_method(f"{self._log_prefix} {message}", *args, **kwargs)

    def log_debug(self, message: str, *args, **kwargs):
        """Log a debug message with agent context."""
        self.log("debug", message, *args, **kwargs)

    def log_info(self, message: str, *args, **kwargs):
        """Log an info message with agent context."""
        self.log("info", message, *args, **kwargs)

    def log_warning(self, message: str, *args, **kwargs):
        """Log a warning message with agent context."""
        self.log("warning", message, *args, **kwargs)

    def log_error(self, message: str, *args, **kwargs):
        """Log an error message with agent context."""
        self.log("error", message, *args, **kwargs)

    def log_trace(self, message: str, *args, **kwargs):
        """Log a trace message with agent context."""
        self.log("trace", message, *args, **kwargs)

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and return an output value.
        Subclasses must implement this method.

        Args:
            inputs: Dictionary of input values

        Returns:
            Output value for the output_field
        """
        raise NotImplementedError("Subclasses must implement process()")

    async def process_async(self, inputs: Dict[str, Any]) -> Any:
        """
        Async sibling to process(). Subclasses may override this to provide
        native async work without modifying the sync process() contract.

        Default behaviour (REQ-NF-001): runs the sync process() in the default
        executor so the event loop remains responsive for sync-only subclasses.
        This means sync-only subclasses gain async compatibility for free, while
        native-async subclasses can override this method to avoid the executor
        overhead.

        Args:
            inputs: Dictionary of input values

        Returns:
            Output value, same logical shape as process() for equivalent inputs.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.process, inputs)

    async def run_async(self, state: Any) -> Dict[str, Any]:
        """
        Async entrypoint for agent execution.  Returns the same state-update
        contract as run() and can be awaited by LangGraph node execution
        (REQ-F-001).

        Dispatches to the instrumented or uninstrumented async path based on
        whether a telemetry service is available, mirroring the sync run()
        dispatch pattern.

        Args:
            state: Current state object (LangGraph node state dict)

        Returns:
            Updated state dictionary — same shape as run() for equivalent inputs
        """
        execution_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        self.log_trace(f"\n*** AGENT {self.name} RUN_ASYNC START [{execution_id}] ***")

        if self._telemetry_service is not None:
            return await self._run_async_with_telemetry(state, execution_id, start_time)
        return await self._run_async_core(state, execution_id, start_time)

    def run(self, state: Any) -> Dict[str, Any]:
        """
        Run the agent and return the updated state.

        Dispatches to the instrumented or uninstrumented path based on
        whether a telemetry service is available (ADR-E02F02-001).

        Args:
            state: Current state object

        Returns:
            Updated state dictionary
        """
        execution_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        self.log_trace(f"\n*** AGENT {self.name} RUN START [{execution_id}] ***")

        if self._telemetry_service is not None:
            return self._run_with_telemetry(state, execution_id, start_time)
        return self._run_core(state, execution_id, start_time)

    def _pre_process(
        self, state: Any, inputs: Dict[str, Any]
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Pre-processing hook that can be overridden by subclasses.

        Args:
            state: Current state
            inputs: Extracted input values

        Returns:
            Tuple of (state, processed_inputs)
        """
        return state, inputs

    def _post_process(
        self, state: Any, inputs: Dict[str, Any], output: Any
    ) -> Tuple[Any, Any]:
        """
        Post-processing hook that can be overridden by subclasses.

        CRITICAL - LangGraph 1.x State Update Pattern:
        ==============================================
        ⚠️  State modifications via state parameter are IGNORED!

        To update state fields, use the 'state_updates' pattern by returning:
            return state, {"state_updates": {
                self.output_field: your_output,
                "other_field": other_value,
            }}

        The BaseAgent.run() method recognizes 'state_updates' and returns
        all fields to LangGraph for merging into state.

        Args:
            state: Current state (READ-ONLY - modifications discarded in run())
            inputs: Input values used for processing
            output: Output value from the process method

        Returns:
            Tuple of (state, modified_output) where:
            - state: Passed through unchanged (modifications are ignored)
            - modified_output: Either:
              * A single value (only self.output_field will be updated)
              * {"state_updates": {...}} dict (multiple fields updated)

        Examples:
            # Simple: Just return processed output
            return state, processed_value

            # Update multiple state fields (required for state changes!)
            return state, {
                "state_updates": {
                    self.output_field: result,
                    "last_action_success": True,
                    "__next_node": "NextNode",
                }
            }

        See: OrchestratorAgent, BranchingAgent, FailureAgent for examples.
        """
        return state, output

    # ------------------------------------------------------------------
    # Telemetry helpers (error-isolated, silent no-op when disabled)
    # ------------------------------------------------------------------

    def _record_lifecycle_event(self, span: Any, event_name: str) -> None:
        """Add a lifecycle event to *span* via the telemetry service.

        Guards: short-circuits if span or telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if span is None or self._telemetry_service is None:
            return
        try:
            self._telemetry_service.add_span_event(span, event_name)
        except Exception:
            pass

    def _set_span_status_ok(self, span: Any) -> None:
        """Set span status to OK using a function-level OTEL import.

        The ``from opentelemetry.trace import StatusCode`` import is
        deliberately function-level (ADR-E02F02-005) so that base_agent.py
        has zero module-level OTEL dependencies.

        Guards: short-circuits if span is None.
        Error isolation: catches all exceptions (including ImportError).
        """
        if span is None:
            return
        try:
            from opentelemetry.trace import StatusCode

            span.set_status(StatusCode.OK)
        except Exception:
            pass

    def _record_span_exception(self, span: Any, exception: Exception) -> None:
        """Record an exception on *span* via the telemetry service.

        Guards: short-circuits if span or telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if span is None or self._telemetry_service is None:
            return
        try:
            self._telemetry_service.record_exception(span, exception)
        except Exception:
            pass

    def _capture_io_attributes(
        self, span: Any, inputs: Any = None, output: Any = None
    ) -> None:
        """Optionally capture agent inputs/outputs as span attributes.

        Reads ``capture_agent_inputs`` and ``capture_agent_outputs`` from
        ``self.context`` (default ``False``).  When enabled, values are
        serialised via ``str()`` and truncated to 1024 characters.

        Guards: short-circuits if span or telemetry_service is None.
        Error isolation: catches all exceptions silently.
        """
        if span is None or self._telemetry_service is None:
            return
        try:
            capture_inputs = self.context.get("capture_agent_inputs", False)
            capture_outputs = self.context.get("capture_agent_outputs", False)

            if not capture_inputs and not capture_outputs:
                return

            attrs: Dict[str, Any] = {}
            if capture_inputs and inputs is not None:
                val = str(inputs)[:1024]
                attrs[AGENT_INPUTS] = val
            if capture_outputs and output is not None:
                val = str(output)[:1024]
                attrs[AGENT_OUTPUTS] = val
            # Edge case 4: empty string "" is a valid value — captured as-is
            # because str("") == "" which is <= 1024

            if attrs:
                self._telemetry_service.set_span_attributes(span, attrs)
        except Exception:
            pass

    def invoke(self, state: Any) -> Dict[str, Any]:
        """
        LangGraph compatibility method.

        Args:
            state: Current state object

        Returns:
            Updated state dictionary
        """
        return self.run(state)

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about injected services for debugging.

        Child classes should override this method to add their specific service info.

        Returns:
            Dictionary with service availability and configuration
        """
        base_info = {
            "agent_name": self.name,
            "agent_type": self.__class__.__name__,
            "services": {
                "logger_available": self._logger is not None,
                "execution_tracker_available": self._execution_tracking_service
                is not None,
                "state_adapter_available": self._state_adapter_service is not None,
                "llm_service_configured": self._llm_service is not None,
                "storage_service_configured": self._storage_service is not None,
                "telemetry_service_available": self._telemetry_service is not None,
            },
            "protocols": {
                "implements_llm_capable": isinstance(self, LLMCapableAgent),
                "implements_storage_capable": isinstance(self, StorageCapableAgent),
            },
            "configuration": {
                "input_fields": self.input_fields,
                "output_field": self.output_field,
                "output_fields": self.output_fields,
                "description": self.description,
            },
        }

        # Allow child classes to extend service info
        child_info = self._get_child_service_info()
        if child_info:
            # Merge child-specific service info
            if "services" in child_info:
                base_info["services"].update(child_info["services"])
            if "protocols" in child_info:
                base_info["protocols"].update(child_info["protocols"])
            if "configuration" in child_info:
                base_info["configuration"].update(child_info["configuration"])
            # Add any additional child-specific sections
            for key, value in child_info.items():
                if key not in base_info:
                    base_info[key] = value

        return base_info

    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """
        Hook for child classes to provide their specific service information.

        Child classes should override this method to provide information about
        their specialized services and capabilities.

        Returns:
            Dictionary with child-specific service info, or None
        """
        return None

    def _validate_multi_output(self, output: Any) -> Dict[str, Any]:
        """
        Validate and filter multi-output return value.

        Validates dict returns for multi-output agents, handles missing/extra
        fields, and supports configurable validation modes (ignore/warn/error).

        Args:
            output: Value returned from process() - expected to be dict for multi-output

        Returns:
            Filtered dict containing only declared output fields

        Raises:
            ValueError: If validation mode is 'error' and validation fails
        """
        # Get validation mode from context or default to 'warn'
        validation_mode = self.context.get("output_validation", "warn")

        # Handle non-dict returns: wrap scalar in first output field (graceful degradation)
        if not isinstance(output, dict):
            msg = (
                f"Agent {self.name} declares multiple outputs {self.output_fields} "
                f"but returned {type(output).__name__} instead of dict. "
                f"Assigning to first output field '{self.output_fields[0]}'."
            )
            if validation_mode == "error":
                raise ValueError(msg)
            elif validation_mode == "warn":
                self.log_warning(msg)
            # Return scalar wrapped in first output field only
            return {self.output_fields[0]: output}

        # Check for missing declared fields
        missing_fields = [f for f in self.output_fields if f not in output]
        if missing_fields:
            msg = (
                f"Agent {self.name} missing declared output fields: {missing_fields}. "
                f"Returned keys: {list(output.keys())}"
            )
            if validation_mode == "error":
                raise ValueError(msg)
            elif validation_mode == "warn":
                self.log_warning(msg)

        # Handle extra fields based on validation mode
        extra_fields = [k for k in output.keys() if k not in self.output_fields]
        if extra_fields:
            msg = (
                f"Agent {self.name} returned extra fields not declared in output_fields: {extra_fields}. "
                f"Declared fields are: {self.output_fields}."
            )
            if validation_mode == "error":
                raise ValueError(msg)
            elif validation_mode == "warn":
                # Keep extra fields in state but warn about them
                self.log_warning(f"{msg} Extra fields will be included in state.")
                # Build result with declared fields + extras, adding None for missing declared fields
                result = {k: output.get(k) for k in self.output_fields}
                # Add the extra fields
                for k in extra_fields:
                    result[k] = output[k]
                return result
            else:  # 'ignore' mode - filter out extras silently
                self.log_debug(f"Filtering extra output fields: {extra_fields}")

        # Return only declared fields, including missing ones as None
        return {k: output.get(k) for k in self.output_fields}
