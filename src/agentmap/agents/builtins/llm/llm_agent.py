"""
Modernized LLM Agent with protocol-based dependency injection.
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple

from agentmap.agents.base_agent import BaseAgent

# Import memory utilities
from agentmap.agents.builtins.llm.memory import (
    add_assistant_message,
    add_system_message,
    add_user_message,
    get_memory,
    truncate_memory,
)
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import (
    LLMCapableAgent,
    LLMServiceProtocol,
    PromptCapableAgent,
)
from agentmap.services.state_adapter_service import StateAdapterService


class LLMAgent(BaseAgent, LLMCapableAgent, PromptCapableAgent):
    """
    Modernized LLM agent with protocol-based dependency injection.

    Follows the new DI pattern where:
    - Infrastructure services are injected via constructor
    - Business services (LLM) are configured post-construction via protocols
    - Implements LLMCapableAgent protocol for service configuration

    This agent can work in two modes:
    1. Legacy mode: Direct provider specification (backward compatible)
    2. Routing mode: Intelligent provider/model selection based on task complexity

    The mode is determined by the 'routing_enabled' context parameter.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only - core services ALL agents need
        logger: Optional[logging.Logger] = None,
        execution_tracker_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
        # LLMAgent-specific infrastructure services
        prompt_manager_service: Optional[Any] = None,  # PromptManagerService
    ):
        """
        Initialize LLM agent with new protocol-based pattern.

        Args:
            name: Name of the agent node
            prompt: Prompt or instruction for the agent
            context: Additional context including input/output configuration
            logger: Logger instance for logging operations
            execution_tracker: ExecutionTrackingService instance for tracking
            state_adapter: StateAdapterService instance for state operations
        """
        # Call BaseAgent constructor with core infrastructure services only
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # LLMAgent-specific infrastructure services
        self._prompt_manager_service = prompt_manager_service

        # Configuration from context with sensible defaults
        self.routing_enabled = self.context.get("routing_enabled", False)

        if self.routing_enabled:
            # Routing mode: Provider will be determined dynamically
            self.provider_name = "auto"  # Placeholder for routing
            self.model = None  # Will be determined by routing
            self.temperature = self.context.get("temperature", 0.7)
            self.api_key = None  # Not needed in routing mode
        else:
            # Legacy mode: Use specified provider or default to anthropic
            self.provider_name = self.context.get("provider", "anthropic")
            self.model = self.context.get("model")
            self.temperature = float(self.context.get("temperature", 0.7))
            self.api_key = self.context.get("api_key") or os.environ.get(
                self._get_api_key_env_var(), ""
            )

        # Memory configuration
        self.memory_key = self.context.get("memory_key", "memory")
        self.max_memory_messages = self.context.get("max_memory_messages", None)

        # Additional configuration properties for backward compatibility
        self.max_tokens = self.context.get("max_tokens")

        # Add memory_key to input_fields if not already present
        if self.memory_key and self.memory_key not in self.input_fields:
            self.input_fields.append(self.memory_key)

        # Resolve the prompt using PromptManagerService if available
        self.resolved_prompt = self._resolve_prompt(prompt)

    # LLMAgent-specific properties
    @property
    def prompt_manager_service(self) -> Optional[Any]:  # PromptManagerService
        """Get prompt manager service (optional for LLMAgent)."""
        return self._prompt_manager_service

    # Properties for backward compatibility
    @property
    def provider(self) -> str:
        """Get provider name for backward compatibility."""
        return self.provider_name

    # Protocol Implementation (Required by LLMCapableAgent)
    def configure_llm_service(self, llm_service: LLMServiceProtocol) -> None:
        """
        Configure LLM service for this agent.

        This method is called by GraphRunnerService during agent setup.

        Args:
            llm_service: LLM service instance to configure
        """
        self._llm_service = llm_service
        self.log_debug("LLM service configured")

    # Protocol Implementation (Required by PromptCapableAgent)
    def configure_prompt_service(
        self, prompt_service: Any
    ) -> None:  # PromptManagerServiceProtocol
        """
        Configure prompt manager service for this agent.

        This method is called by GraphRunnerService during agent setup.
        Note: This is mainly for protocol compliance. PromptManagerService
        is typically injected via constructor as an infrastructure service.

        Args:
            prompt_service: PromptManagerService instance to configure
        """
        # Update the prompt manager service if provided post-construction
        if prompt_service and not self.prompt_manager_service:
            self._prompt_manager_service = prompt_service
            # Re-resolve prompt with the new service
            self.resolved_prompt = self._resolve_prompt(self.prompt)
            self.log_debug("Prompt service configured post-construction")

    def _get_api_key_env_var(self, provider: Optional[str] = None) -> str:
        """
        Get the environment variable name for the API key.

        Args:
            provider: Optional provider name (uses self.provider_name if not provided)

        Returns:
            Environment variable name (e.g., "ANTHROPIC_API_KEY")
        """
        if not provider:
            provider = self.provider_name

        env_vars = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        return env_vars.get(provider, f"{provider.upper()}_API_KEY")

    def _resolve_prompt(self, prompt: str) -> str:
        """
        Resolve prompt using PromptManagerService if available.

        Args:
            prompt: Raw prompt string or prompt reference

        Returns:
            Resolved prompt text
        """
        if not prompt:
            return ""

        # If we have a prompt manager service, use it to resolve the prompt
        if self.prompt_manager_service:
            try:
                resolved = self.prompt_manager_service.resolve_prompt(prompt)
                if (
                    resolved != prompt
                ):  # Only log if resolution actually changed the prompt
                    self.log_debug(
                        f"Resolved prompt reference '{prompt}' to {len(resolved)} characters"
                    )
                return resolved
            except Exception as e:
                self.log_warning(
                    f"Failed to resolve prompt '{prompt}': {e}. Using original prompt."
                )
                return prompt
        else:
            # No prompt manager service available, use prompt as-is
            return prompt

    def is_routing_enabled(self) -> bool:
        """
        Check if routing is enabled for this agent.

        Returns:
            True if routing is enabled
        """
        return self.routing_enabled

    def get_effective_provider(self) -> str:
        """
        Get the effective provider name (for logging/debugging).

        Returns:
            Provider name or "routing" if routing is enabled
        """
        return "routing" if self.routing_enabled else self.provider_name

    def _prepare_routing_context(
        self, inputs: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Prepare routing context based on agent configuration and inputs.

        Returns:
            Routing context dictionary or None for legacy mode
        """
        if not self.routing_enabled:
            # Legacy mode: return None to use direct calling
            return None

        # Build a condensed user_input from non-memory fields for complexity analyzer
        input_parts = []
        for field in self.input_fields:
            if field != self.memory_key and inputs.get(field):
                input_parts.append(str(inputs.get(field)))
        user_input = " ".join(input_parts) if input_parts else ""

        routing_context = {
            "routing_enabled": True,
            # existing fields
            "task_type": self.context.get("task_type", "general"),
            "complexity_override": self.context.get("complexity_override"),
            "auto_detect_complexity": self.context.get("auto_detect_complexity", True),
            "provider_preference": self.context.get("provider_preference", []),
            "exclude_providers": self.context.get("exclude_providers", []),
            "fallback_provider": self.context.get("fallback_provider"),
            "fallback_model": self.context.get("fallback_model"),
            "max_cost_tier": self.context.get("max_cost_tier"),
            "retry_with_lower_complexity": self.context.get(
                "retry_with_lower_complexity", True
            ),
            "activity": self.context.get(
                "activity"
            ),  # e.g., "narrative", "code_review"
            "router_profile": self.context.get(
                "router_profile"
            ),  # e.g., "quality_first", "cost_saver"
            # Analyzer input context
            "input_context": {
                "user_input": user_input,
                "input_field_count": len(
                    [f for f in self.input_fields if f != self.memory_key]
                ),
                "memory_size": len(inputs.get(self.memory_key, [])),
                **self.context.get("input_context", {}),
            },
        }
        return routing_context

    def _pre_process(
        self, state: Any, inputs: Dict[str, Any]
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Pre-process hook - memory initialization is now handled in process().

        Args:
            state: Current state
            inputs: Input values for this node

        Returns:
            Tuple of (updated_state, updated_inputs)
        """
        # Memory initialization is now handled in process() for better encapsulation
        return state, inputs

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process inputs with LLM, supporting both routing and legacy modes.

        Args:
            inputs: Dictionary of input values

        Returns:
            Response from LLM including updated memory
        """
        # Check service configuration first (let configuration errors bubble up)
        llm_service = self.llm_service

        try:
            # Initialize memory if needed (handle both direct process() calls and run() calls)
            if self.memory_key not in inputs:
                inputs[self.memory_key] = []

                # Add system message from resolved prompt if available
                if self.resolved_prompt:
                    add_system_message(inputs, self.resolved_prompt, self.memory_key)

            # Get relevant input fields (excluding memory) and apply conditional formatting
            relevant_fields = [
                field
                for field in self.input_fields
                if field != self.memory_key and inputs.get(field)
            ]

            if len(relevant_fields) == 1:
                # Single field: use value directly without prefix for cleaner LLM input
                user_input = str(inputs.get(relevant_fields[0]))
            elif len(relevant_fields) > 1:
                # Multiple fields: use prefixed structure for clarity
                input_parts = [
                    f"{field}: {inputs.get(field)}" for field in relevant_fields
                ]
                user_input = "\n".join(input_parts)
            else:
                user_input = ""

            if not user_input:
                self.log_warning("No input found in inputs")
            else:
                self.log_info(f"Processing LLM request with input: {user_input}")

            # Get memory from inputs
            messages = get_memory(inputs, self.memory_key)

            # Add user message to memory (only if we have input)
            if user_input:
                add_user_message(inputs, user_input, self.memory_key)

                # Get updated messages
                messages = get_memory(inputs, self.memory_key)

            # Prepare routing context
            routing_context = self._prepare_routing_context(inputs)

            if routing_context:
                # Routing mode: Let the routing service decide provider/model
                self.log_debug(
                    f"Using routing mode for task_type: {routing_context.get('task_type')}"
                )
                result = llm_service.call_llm(
                    provider="auto",  # Will be determined by routing
                    messages=messages,
                    routing_context=routing_context,
                )
            else:
                # Legacy mode: Use specified provider and model
                self.log_debug(f"Using legacy mode with provider: {self.provider_name}")

                # Build call parameters
                call_params = {
                    "provider": self.provider_name,
                    "messages": messages,
                    "model": self.model,
                    "temperature": self.temperature,
                }

                # Add max_tokens if specified
                if self.max_tokens is not None:
                    call_params["max_tokens"] = self.max_tokens

                result = llm_service.call_llm(**call_params)

            # Add assistant response to memory
            add_assistant_message(inputs, result, self.memory_key)

            # Apply message limit if configured
            if self.max_memory_messages:
                truncate_memory(inputs, self.max_memory_messages, self.memory_key)

            # Log successful completion
            self.log_info(f"LLM processing completed successfully")

            # Return result with memory included
            return {"output": result, self.memory_key: inputs.get(self.memory_key, [])}

        except Exception as e:
            provider_name = (
                self.provider_name if not self.routing_enabled else "routing"
            )
            self.log_error(f"Error in {provider_name} processing: {e}")
            return {"error": str(e), "last_action_success": False}

    def _post_process(
        self, state: Any, inputs: Dict[str, Any], output: Any
    ) -> Tuple[Any, Any]:
        """
        Post-processing hook to ensure memory is in the state.

        Args:
            state: Current state
            inputs: Input values used for processing
            output: Output from process method

        Returns:
            Tuple of (updated_state, updated_output)
        """
        # Handle case where output is a dictionary with memory
        if isinstance(output, dict) and self.memory_key in output:
            memory = output.pop(self.memory_key, None)

            # Update memory in state
            if memory is not None:
                state = self.state_adapter_service.set_value(
                    state, self.memory_key, memory
                )

            # Extract output value if available
            if self.output_field and self.output_field in output:
                output = output[self.output_field]
            elif "output" in output:
                output = output["output"]

        return state, output

    def _get_child_service_info(self) -> Dict[str, Any]:
        """
        Provide LLMAgent-specific service information.

        Returns:
            Dictionary with LLMAgent-specific service info
        """
        return {
            "services": {
                "prompt_manager_available": self._prompt_manager_service is not None,
            },
            "protocols": {"implements_prompt_capable": True},
            "llm_configuration": {
                "routing_enabled": self.routing_enabled,
                "provider_name": self.provider_name,
                "model": self.model,
                "temperature": self.temperature,
                "memory_key": self.memory_key,
                "max_memory_messages": self.max_memory_messages,
                "prompt_resolved": (
                    self.resolved_prompt != self.prompt
                    if hasattr(self, "resolved_prompt")
                    else False
                ),
            },
        }
