"""
Function template composition module.

Extracted from IndentedTemplateComposer to handle all function template
composition logic, following the Single Responsibility Principle.
"""

from typing import Any, Dict, List

from agentmap.services.logging_service import LoggingService
from agentmap.services.template_loader import TemplateLoader
from agentmap.services.template_processor import TemplateProcessor


class FunctionTemplateComposer:
    """
    Composes function templates with proper variable substitution.

    This class encapsulates all function template composition logic that was
    previously in IndentedTemplateComposer, providing clean separation of concerns.
    """

    def __init__(
        self,
        template_loader: TemplateLoader,
        template_processor: TemplateProcessor,
        logging_service: LoggingService,
    ):
        """
        Initialize function template composer.

        Args:
            template_loader: Template loader instance
            template_processor: Template processor instance
            logging_service: Logging service for error handling and debugging
        """
        self.template_loader = template_loader
        self.template_processor = template_processor
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[FunctionTemplateComposer] Initialized")

    def compose_function_template(self, func_name: str, info: Dict[str, Any]) -> str:
        """
        Compose function template with proper formatting using internal template loading.

        This method provides comprehensive function template composition that eliminates
        the need for PromptManagerService dependency.

        Args:
            func_name: Name of function to scaffold
            info: Function information dictionary containing:
                - node_name: Name of the source node
                - context: Context information from CSV
                - input_fields: List of input field names
                - output_field: Output field name
                - success_next: Success routing target
                - failure_next: Failure routing target
                - description: Function description

        Returns:
            Complete function template string with variables substituted

        Raises:
            Exception: If template composition fails
        """
        try:
            self.logger.debug(
                f"[FunctionTemplateComposer] Composing function template for: {func_name}"
            )

            # Prepare comprehensive template variables
            template_vars = self._prepare_function_template_variables(func_name, info)

            # Load function template using template loader
            template_content = self.template_loader.load_template(
                "function_template.txt"
            )

            # Apply variable substitution
            formatted_template = self.template_processor.apply_variable_substitution(
                template_content, template_vars
            )

            self.logger.debug(
                f"[FunctionTemplateComposer] Successfully composed function template for: {func_name}"
            )
            return formatted_template

        except Exception as e:
            self.logger.error(
                f"[FunctionTemplateComposer] Failed to compose function template for {func_name}: {e}"
            )
            raise

    def _prepare_function_template_variables(
        self, func_name: str, info: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Prepare comprehensive template variables for function template substitution.

        Now includes parallel routing metadata for generating list-returning functions.

        Args:
            func_name: Name of function to scaffold
            info: Function information dictionary

        Returns:
            Dictionary with comprehensive template variables matching function_template.txt
        """
        # Generate context fields documentation
        context_fields = self._generate_context_fields(
            info.get("input_fields", []), info.get("output_field", "")
        )

        # Extract parallel routing flags
        success_parallel = info.get("success_parallel", False)
        failure_parallel = info.get("failure_parallel", False)
        has_parallel = info.get("has_parallel", False)

        # Format targets for display and code generation
        success_next = info.get("success_next", "") or ""
        failure_next = info.get("failure_next", "") or ""

        # Format success target(s)
        if success_parallel:
            success_display = f"{success_next} (parallel)"
            success_code = repr(success_next)  # Generates ["A", "B", "C"]
        else:
            # Provide string default values for template substitution
            success_display = success_next if success_next else "None"
            success_code = f'"{success_next}"' if success_next else '""'

        # Format failure target(s)
        if failure_parallel:
            failure_display = f"{failure_next} (parallel)"
            failure_code = repr(failure_next)  # Generates ["A", "B", "C"]
        else:
            # Provide string default values for template substitution
            failure_display = failure_next if failure_next else "None"
            failure_code = f'"{failure_next}"' if failure_next else '""'

        # Prepare all template variables expected by function_template.txt
        template_vars = {
            "func_name": func_name,
            "context": info.get("context", "") or "No context provided",
            "context_fields": context_fields,
            "success_node": success_display,  # For documentation
            "failure_node": failure_display,  # For documentation
            "success_code": success_code,  # For code generation
            "failure_code": failure_code,  # For code generation
            "success_parallel": str(success_parallel),  # Template flag
            "failure_parallel": str(failure_parallel),  # Template flag
            "has_parallel": str(has_parallel),  # Template flag
            "node_name": info.get("node_name", "") or "Unknown",
            "description": info.get("description", "") or "No description provided",
            "output_field": info.get("output_field", "") or "None",
        }

        self.logger.debug(
            f"[FunctionTemplateComposer] Prepared template variables for {func_name}: "
            f"success={success_display}, failure={failure_display}, "
            f"parallel={has_parallel}"
        )

        return template_vars

    def _generate_context_fields(
        self, input_fields: List[str], output_field: str
    ) -> str:
        """
        Generate documentation about available fields in the state for function templates.

        Args:
            input_fields: List of input field names
            output_field: Output field name

        Returns:
            String containing formatted field documentation
        """
        context_fields = []

        # Add input field documentation
        for field in input_fields or []:
            if field:  # Skip empty fields
                context_fields.append(f"    - {field}: Input from previous node")

        # Add output field documentation
        if output_field:
            context_fields.append(f"    - {output_field}: Expected output to generate")

        # Add common state fields documentation
        context_fields.extend(
            [
                "    - last_action_success: Boolean indicating if previous action succeeded",
                "    - error: Error message if previous action failed",
                "    - routing_error: Error message from routing function itself",
            ]
        )

        if not context_fields:
            context_fields = ["    No specific fields defined in the CSV"]

        return "\n".join(context_fields)

    def get_function_template_info(self) -> Dict[str, Any]:
        """
        Get information about function template composition capabilities.

        Returns:
            Dictionary with function template status and configuration info
        """
        return {
            "function_template_support": True,
            "template_loading_method": "internal",
            "template_path": "function_template.txt",
            "variable_substitution_method": "string.format",
            "supported_variables": [
                "func_name",
                "context",
                "context_fields",
                "success_node",
                "failure_node",
                "node_name",
                "description",
                "output_field",
            ],
            "cache_enabled": True,
            "cache_stats": self.template_loader.get_cache_stats(),
        }
