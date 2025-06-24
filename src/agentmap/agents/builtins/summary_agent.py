"""
Standardized SummaryAgent with consistent prompt resolution.
"""

import logging
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.protocols import LLMCapableAgent, LLMServiceProtocol
from agentmap.services.state_adapter_service import StateAdapterService


class SummaryAgent(BaseAgent, LLMCapableAgent):
    """
    Agent that summarizes multiple input fields into a single output.

    Operates in two modes:
    1. Basic mode (default): Formats and concatenates inputs with templates
    2. LLM mode (optional): Uses LLM to create an intelligent summary
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
        prompt_manager_service: Optional[Any] = None,  # PromptManagerService
    ):
        """Initialize the summary agent with new protocol-based pattern."""
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # Infrastructure services
        self._prompt_manager_service = prompt_manager_service

        # LLM Service - configured via protocol
        self._llm_service = None

        # Configuration options
        self.llm_type = self.context.get("llm")
        self.use_llm = bool(self.llm_type)

        # Formatting configuration
        self.format_template = self.context.get("format", "{key}: {value}")
        self.separator = self.context.get("separator", "\n\n")
        self.include_keys = self.context.get("include_keys", True)

        # Resolve the prompt using PromptManagerService if available
        self.resolved_prompt = self._resolve_prompt(prompt)

        if self.use_llm:
            self.log_debug(f"SummaryAgent '{name}' using LLM mode: {self.llm_type}")
        else:
            self.log_debug(f"SummaryAgent '{name}' using basic concatenation mode")

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

    @property
    def prompt_manager_service(self) -> Optional[Any]:  # PromptManagerService
        """Get prompt manager service (optional for SummaryAgent)."""
        return self._prompt_manager_service

    @property
    def llm_service(self) -> LLMServiceProtocol:
        """Get LLM service, raising clear error if not configured."""
        if self._llm_service is None:
            raise ValueError(f"LLM service not configured for agent '{self.name}'")
        return self._llm_service

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

    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process inputs and generate a summary."""
        if not inputs:
            self.log_warning(f"SummaryAgent '{self.name}' received empty inputs")
            return ""

        # Use LLM mode if enabled, otherwise basic concatenation
        if self.use_llm:
            return self._summarize_with_llm(inputs)
        else:
            return self._basic_concatenation(inputs)

    def _basic_concatenation(self, inputs: Dict[str, Any]) -> str:
        """Format and concatenate inputs using simple templates."""
        formatted_items = []

        for key, value in inputs.items():
            # Skip None values
            if value is None:
                continue

            if self.include_keys:
                try:
                    formatted = self.format_template.format(key=key, value=value)
                except Exception as e:
                    self.log_warning(f"Error formatting {key}: {str(e)}")
                    formatted = f"{key}: {value}"
            else:
                formatted = str(value)
            formatted_items.append(formatted)

        return self.separator.join(formatted_items)

    def _summarize_with_llm(self, inputs: Dict[str, Any]) -> str:
        """Use LLM to generate an intelligent summary with resolved prompt."""
        # Check if LLM service is configured first (fail fast for configuration issues)
        if self._llm_service is None:
            raise ValueError(f"LLM service not configured for agent '{self.name}'")

        try:
            # Prepare the content to summarize
            content_to_summarize = self._basic_concatenation(inputs)

            # Build messages for LLM call
            messages = [
                {"role": "system", "content": self.resolved_prompt},
                {"role": "user", "content": content_to_summarize},
            ]

            # Use LLM Service
            result = self.llm_service.call_llm(
                provider=self.llm_type,
                messages=messages,
                model=self.context.get("model"),
                temperature=self.context.get("temperature"),
            )

            return result

        except Exception as e:
            # Only catch runtime errors (API failures, etc.) - not configuration errors
            self.log_error(f"Error in LLM summarization: {str(e)}")
            # Fallback to basic concatenation on runtime error
            concatenated = self._basic_concatenation(inputs)
            return (
                f"ERROR in summarization: {str(e)}\n\nOriginal content:\n{concatenated}"
            )
