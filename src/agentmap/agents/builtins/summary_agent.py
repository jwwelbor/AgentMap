"""
Standardized SummaryAgent with consistent prompt resolution.
"""
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.agents.mixins import PromptResolutionMixin
from agentmap.agents.features import is_llm_enabled
from agentmap.logging.tracking.execution_tracker import ExecutionTracker
import logging

class SummaryAgent(BaseAgent, PromptResolutionMixin):
    """
    Agent that summarizes multiple input fields into a single output.
    
    Operates in two modes:
    1. Basic mode (default): Formats and concatenates inputs with templates
    2. LLM mode (optional): Uses LLM to create an intelligent summary
    """

    def __init__(self, name: str, prompt: str, logger: logging.Logger, execution_tracker: ExecutionTracker, context: dict = None):
        """Initialize the success agent with the required dependencies."""
        super().__init__(name, prompt, context, logger=logger, execution_tracker=execution_tracker)

        # LLM Service - implements LLMServiceUser protocol
        self.llm_service = None

        # Configuration options
        self.llm_type = self.context.get("llm")
        self.use_llm = bool(self.llm_type)
        
        # Formatting configuration
        self.format_template = self.context.get("format", "{key}: {value}")
        self.separator = self.context.get("separator", "\n\n")
        self.include_keys = self.context.get("include_keys", True)

        # Validate LLM availability
        if self.use_llm and not is_llm_enabled() and not self.llm_service:
            self.log_warning(f"SummaryAgent '{name}' requested LLM mode but LLM dependencies are not installed.")
            self.log_warning("Falling back to basic concatenation mode. Install with: pip install agentmap[llm]")
            self.use_llm = False

        if self.use_llm:
            self.log_debug(f"SummaryAgent '{name}' using LLM mode: {self.llm_type}")
        else:
            self.log_debug(f"SummaryAgent '{name}' using basic concatenation mode")

    # PromptResolutionMixin implementation
    def _get_default_template_file(self) -> str:
        """Get default template file for summary prompts."""
        return "file:summary/summarization_v1.txt"
    
    def _get_default_template_text(self) -> str:
        """Get default template text for summary prompts."""
        return "Please summarize the following information:\n\n{content}"
    
    def _extract_template_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract template variables specific to summary needs."""
        # Prepare basic concatenation as content for LLM
        concatenated = self._basic_concatenation(inputs)
        
        return {"content": concatenated}

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
        """Use LLM to generate an intelligent summary with standardized prompt resolution."""
        try:
            # Get formatted prompt using standardized method
            llm_prompt = self._get_formatted_prompt(inputs)
            
            # Build messages for LLM call
            messages = [
                {"role": "system", "content": llm_prompt},
                {"role": "user", "content": self._basic_concatenation(inputs)}
            ]
            
            # Use LLM Service
            result = self.llm_service.call_llm(
                provider=self.llm_type,
                messages=messages,
                model=self.context.get("model"),
                temperature=self.context.get("temperature")
            )

            return result

        except Exception as e:
            self.log_error(f"Error in LLM summarization: {str(e)}")
            # Fallback to basic concatenation on error
            concatenated = self._basic_concatenation(inputs)
            return f"ERROR in summarization: {str(e)}\n\nOriginal content:\n{concatenated}"