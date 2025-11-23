"""
Template processing module for IndentedTemplateComposer.

Extracted from IndentedTemplateComposer to handle template processing,
variable substitution, and indentation logic.
"""

import textwrap
from typing import Any, Dict

from agentmap.services.logging_service import LoggingService

# Standard Python indentation levels following PEP 8
INDENT_LEVELS = {
    "module": 0,  # Module level (imports, class definitions)
    "class_body": 4,  # Inside class (method definitions)
    "method_body": 8,  # Inside methods (implementation code)
    "nested": 12,  # Nested blocks (if/for inside methods)
}


class TemplateProcessor:
    """
    Handles template processing, variable substitution, and indentation.

    This class encapsulates all template processing logic that was previously
    in IndentedTemplateComposer, providing clean separation of concerns.
    """

    def __init__(self, logging_service: LoggingService):
        """
        Initialize template processor.

        Args:
            logging_service: Logging service for error handling and debugging
        """
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[TemplateProcessor] Initialized")

    def apply_variable_substitution(
        self, content: str, variables: Dict[str, Any]
    ) -> str:
        """
        Apply variable substitution to template content.

        Args:
            content: Template content with variable placeholders
            variables: Dictionary of variables for substitution

        Returns:
            Content with variables substituted, or unchanged if variables are missing
        """
        try:
            return content.format(**variables)
        except KeyError as e:
            # Log missing variables but leave template unchanged
            missing_var = str(e).strip("'\"")
            self.logger.warning(
                f"[TemplateProcessor] Missing template variable: {missing_var}"
            )
            self.logger.debug(
                f"[TemplateProcessor] Available variables: {list(variables.keys())}"
            )
            # Return content unchanged when variables are missing
            return content
        except Exception as e:
            self.logger.error(f"[TemplateProcessor] Variable substitution error: {e}")
            # Return content unchanged on other errors
            return content

    def apply_indentation(self, content: str, spaces: int) -> str:
        """
        Apply consistent indentation to content using textwrap.indent().

        Args:
            content: Text content to indent
            spaces: Number of spaces for indentation

        Returns:
            Content with proper indentation applied
        """
        if spaces == 0:
            # No indentation needed for module level
            return content

        # Create indent prefix (e.g., "    " for 4 spaces)
        indent_prefix = " " * spaces

        # Apply indentation to all non-empty lines using textwrap.indent()
        return textwrap.indent(content, indent_prefix)
