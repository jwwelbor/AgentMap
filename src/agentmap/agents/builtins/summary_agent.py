# agentmap/agents/builtins/summary_agent.py
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent
from agentmap.config import get_llm_config
from agentmap.logging import get_logger
from agentmap.agents import HAS_LLM_AGENTS

logger = get_logger(__name__, False)


class SummaryAgent(BaseAgent):
    """
    Agent that summarizes multiple input fields into a single output.

    Operates in two modes:
    1. Basic mode (default): Formats and concatenates inputs with templates
    2. LLM mode (optional): Uses LLM to create an intelligent summary
    """

    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the summary agent.

        Args:
            name: Name of the agent node
            prompt: Instructions for summarization (used by LLM mode)
            context: Additional configuration including:
                - format: Template for formatting items (default: "{key}: {value}")
                - separator: String to join items (default: "\n\n")
                - include_keys: Whether to include keys in output (default: True)
                - llm: Optional LLM to use ("openai", "anthropic", "google")
                - model: Optional specific model name
                - temperature: Optional temperature for LLM
        """
        super().__init__(name, prompt, context or {})

        # Extract configuration with defaults
        self.format_template = self.context.get("format", "{key}: {value}")
        self.separator = self.context.get("separator", "\n\n")
        self.include_keys = self.context.get("include_keys", True)

        # Check if LLM mode is enabled
        self.llm_type = self.context.get("llm")
        self.use_llm = bool(self.llm_type)

        if bool(self.llm_type) and not HAS_LLM_AGENTS:
            self.log_warning(f"SummaryAgent '{name}' requested LLM mode but LLM dependencies are not installed.")
            self.log_warning("Falling back to basic concatenation mode. Install with: pip install agentmap[llm]")

        if self.use_llm:
            self.log_debug(f"SummaryAgent '{name}' using LLM mode: {self.llm_type}")
        else:
            self.log_debug(f"SummaryAgent '{name}' using basic concatenation mode")
            
        # LLM Service (will be injected or created)
        self.llm_service = None

    def _get_llm_service(self):
        """Get LLM service via DI or direct creation."""
        if self.llm_service is None:
            try:
                from agentmap.di import application
                self.llm_service = application.llm_service()
            except Exception:
                # Fallback for non-DI usage
                from agentmap.services.llm_service import LLMService
                self.llm_service = LLMService()
        return self.llm_service

    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process the inputs and generate a summary.

        Args:
            inputs: Dictionary containing input values

        Returns:
            Summarized output as string
        """
        if not inputs:
            self.log_warning(f"SummaryAgent '{self.name}' received empty inputs")
            return ""

        # If LLM mode is enabled, use that
        if self.use_llm:
            return self._summarize_with_llm(inputs)

        # Otherwise use basic concatenation
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
        """Use LLM to generate an intelligent summary."""
        # Prepare basic concatenation as input for the LLM
        concatenated = self._basic_concatenation(inputs)

        try:
            llm_prompt = self._get_llm_prompt(concatenated)
            
            # Build messages for LLM call
            messages = [
                {"role": "system", "content": llm_prompt},
                {"role": "user", "content": concatenated}
            ]
            
            # Use LLM Service
            llm_service = self._get_llm_service()
            result = llm_service.call_llm(
                provider=self.llm_type,
                messages=messages,
                model=self.context.get("model"),
                temperature=self.context.get("temperature")
            )

            return result

        except Exception as e:
            self.log_error(f"Error in LLM summarization: {str(e)}")
            return f"ERROR in summarization: {str(e)}\n\nOriginal content:\n{concatenated}"

    def _get_llm_prompt(self, content: str) -> str:
        """Create a prompt for the LLM based on the agent's prompt and content."""
        from agentmap.prompts import get_formatted_prompt
        
        template_values = {"content": content}
        default_template = "Please summarize the following information:\n\n{content}"
        
        # Get formatted prompt with all fallbacks handled internally
        return get_formatted_prompt(
            primary_prompt=self.prompt,
            template_file="file:summary/summarization_v1.txt",
            default_template=default_template,
            values=template_values,
            logger=self._logger,
            context_name="SummaryAgent"
        )