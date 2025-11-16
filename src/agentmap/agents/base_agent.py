"""
Modernized Base agent class for all AgentMap agents.

Updated to use protocol-based dependency injection following clean architecture patterns.
Infrastructure services are injected via constructor, business services via post-construction configuration.
"""

import logging
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from langgraph.errors import GraphInterrupt

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import (
    LLMCapableAgent,
    LLMServiceProtocol,
    StorageCapableAgent,
    StorageServiceProtocol,
)
from agentmap.services.state_adapter_service import StateAdapterService


class BaseAgent:
    """
    Modernized base class for all agents in AgentMap.

    Uses protocol-based dependency injection for clean service management.
    Infrastructure services are injected via constructor, business services
    are configured post-construction via configure_*_service() methods.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only - core services that ALL agents need
        logger: Optional[logging.Logger] = None,
        execution_tracking_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
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
            execution_tracker: ExecutionTrackingService instance (required for proper operation)
            state_adapter: StateAdapterService instance
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

        # Infrastructure services (required) - only core services ALL agents need
        self._logger = logger
        self._execution_tracking_service = execution_tracking_service
        self._state_adapter_service = state_adapter_service
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

    def run(self, state: Any) -> Dict[str, Any]:
        """
        Run the agent and return the updated state.

        Uses dependency-injected services for clean execution flow.

        Args:
            state: Current state object

        Returns:
            Updated state dictionary
        """
        # Generate execution ID for tracking
        execution_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        self.log_trace(f"\n*** AGENT {self.name} RUN START [{execution_id}] ***")

        # Get required services (will raise if not available)
        tracking_service = self.execution_tracking_service

        # Get the shared execution tracker object (must be set before execution)
        tracker = self.current_execution_tracker
        if tracker is None:
            raise ValueError(
                f"No ExecutionTracker set for agent '{self.name}'. "
                "Tracker must be distributed to agents before graph execution starts."
            )

        # Extract inputs using state adapter
        inputs = self.state_adapter_service.get_inputs(state, self.input_fields)

        # Record node start using service
        tracking_service.record_node_start(tracker, self.name, inputs)

        try:
            # Pre-processing hook for subclasses
            self.log_trace(
                f"\n*** AGENT {self.name} PRE-PROCESS START [{execution_id}] ***"
            )
            state, inputs = self._pre_process(state, inputs)

            self.log_trace(
                f"\n*** AGENT {self.name} PROCESS START [{execution_id}] ***"
            )
            # Process inputs to get output
            output = self.process(inputs)

            # Post-processing hook for subclasses
            self.log_trace(
                f"\n*** AGENT {self.name} POST-PROCESS START [{execution_id}] ***"
            )
            state, output = self._post_process(state, inputs, output)

            # Record success using service
            tracking_service.record_node_result(tracker, self.name, True, result=output)

            # Return partial state update (supports multiple fields for parallel execution)
            # This enables parallel execution - LangGraph merges partial updates
            # from concurrent nodes without conflicts

            # SPECIAL CASE: If output is a dict with 'state_updates' key,
            # the agent wants to update multiple state fields (e.g., BranchingAgent)
            if isinstance(output, dict) and "state_updates" in output:
                state_updates = output["state_updates"]
                self.log_debug(
                    f"Returning multiple state updates: {list(state_updates.keys())}"
                )
                end_time = time.time()
                duration = end_time - start_time
                self.log_trace(
                    f"\n*** AGENT {self.name} RUN COMPLETED [{execution_id}] in {duration:.4f}s ***"
                )
                return state_updates

            # NORMAL CASE: Return only the output field
            if self.output_field and output is not None:
                self.log_debug(f"Set output field '{self.output_field}' = {output}")
                end_time = time.time()
                duration = end_time - start_time
                self.log_trace(
                    f"\n*** AGENT {self.name} RUN COMPLETED [{execution_id}] in {duration:.4f}s ***"
                )
                # Return only the updated field (partial update pattern)
                return {self.output_field: output}

            # No output field - return empty dict (no updates)
            end_time = time.time()
            duration = end_time - start_time
            self.log_trace(
                f"\n*** AGENT {self.name} RUN COMPLETED [{execution_id}] in {duration:.4f}s ***"
            )
            return {}

        except GraphInterrupt:
            # LangGraph interrupt pattern - re-raise to let LangGraph handle checkpoint
            tracking_service.record_node_result(
                tracker, self.name, True, result={"status": "suspended"}
            )
            self.log_info(f"Graph execution suspended in {self.name}")
            raise

        except Exception as e:
            # Handle errors
            error_msg = f"Error in {self.name}: {str(e)}"
            self.log_error(error_msg)

            # Record failure using service
            tracking_service.record_node_result(
                tracker, self.name, False, error=error_msg
            )
            graph_success = tracking_service.update_graph_success(tracker)

            # Prepare error updates
            error_updates = {
                "graph_success": graph_success,
                "last_action_success": False,
                "errors": [error_msg],
            }

            # Try to run post-process for error handling
            try:
                state, output = self._post_process(state, inputs, error_updates)
            except Exception as post_error:
                self.log_error(f"Error in post-processing: {str(post_error)}")

            end_time = time.time()
            duration = end_time - start_time
            self.log_trace(
                f"\n*** AGENT {self.name} RUN FAILED [{execution_id}] in {duration:.4f}s ***"
            )

            # Return error updates as partial state update
            return error_updates

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

        Args:
            state: Current state
            inputs: Input values used for processing
            output: Output value from the process method

        Returns:
            Tuple of (state, modified_output)
        """
        return state, output

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
            },
            "protocols": {
                "implements_llm_capable": isinstance(self, LLMCapableAgent),
                "implements_storage_capable": isinstance(self, StorageCapableAgent),
            },
            "configuration": {
                "input_fields": self.input_fields,
                "output_field": self.output_field,
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
