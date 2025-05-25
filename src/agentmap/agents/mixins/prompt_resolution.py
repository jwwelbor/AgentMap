"""
Mixin for standardizing prompt resolution in agents that optionally use LLM services.
"""
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod


class PromptResolutionMixin(ABC):
    """
    Mixin to standardize prompt resolution for agents that optionally use LLM.
    
    Provides a consistent pattern for:
    1. Default template file specification
    2. Default template text fallback
    3. Template variable extraction from inputs
    4. Formatted prompt generation
    
    Usage:
        class MyAgent(BaseAgent, PromptResolutionMixin):
            def _get_default_template_file(self) -> str:
                return "file:my_agent/template.txt"
            
            def _get_default_template_text(self) -> str:
                return "Default template with {variable}"
            
            def process(self, inputs: Dict[str, Any]) -> Any:
                prompt = self._get_formatted_prompt(inputs)
                # Use prompt with LLM...
    """
    
    @abstractmethod
    def _get_default_template_file(self) -> str:
        """
        Get the default template file path for this agent.
        
        Returns:
            Template file reference (e.g., "file:orchestrator/intent_matching_v1.txt")
        """
        pass
    
    @abstractmethod
    def _get_default_template_text(self) -> str:
        """
        Get the default template text as fallback.
        
        Returns:
            Default template string with placeholder variables
        """
        pass
    
    def _extract_template_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract variables from inputs for template substitution.
        
        Override this method to customize which input fields are used
        and how they're formatted for template variables.
        
        Args:
            inputs: Input dictionary from process method
            
        Returns:
            Dictionary of template variables
        """
        # Default implementation: use all input fields as template variables
        return inputs.copy()
    
    def _get_formatted_prompt(self, inputs: Dict[str, Any]) -> str:
        """
        Get formatted prompt using standardized resolution approach.
        
        This method implements the 3-tier fallback system:
        1. Use self.prompt (from CSV or constructor) if available
        2. Fall back to template file specified by _get_default_template_file()
        3. Fall back to default template text from _get_default_template_text()
        
        Args:
            inputs: Input dictionary to extract template variables from
            
        Returns:
            Fully formatted prompt text ready for LLM
        """
        from agentmap.prompts import get_formatted_prompt
        
        # Extract template variables from inputs
        template_values = self._extract_template_variables(inputs)
        
        # Get logger if available
        logger = getattr(self, '_logger', None) or getattr(self, 'logger', None)
        
        # Use standardized prompt resolution with 3-tier fallback
        return get_formatted_prompt(
            primary_prompt=self.prompt,  # From CSV or constructor
            template_file=self._get_default_template_file(),
            default_template=self._get_default_template_text(),
            values=template_values,
            logger=logger,
            context_name=self.__class__.__name__
        )