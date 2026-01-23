"""
Code generation utilities for IndentedTemplateComposer.

Handles generation of class names, attributes, documentation, and other code snippets.
"""

from typing import List

from agentmap.models.scaffold_types import ServiceAttribute, ServiceRequirements
from agentmap.services.logging_service import LoggingService


class CodeGenerator:
    """
    Generates code snippets for template composition.

    Responsibilities:
    - Generate PascalCase class names
    - Generate service attributes
    - Generate documentation strings
    - Generate input field access code
    - Generate service usage examples
    """

    def __init__(self, logging_service: LoggingService):
        """
        Initialize code generator.

        Args:
            logging_service: Logging service for debugging
        """
        self.logger = logging_service.get_class_logger(self)

    def generate_agent_class_name(self, agent_type: str) -> str:
        """
        Generate proper PascalCase class name for agent.

        Converts to PascalCase and adds 'Agent' suffix only if not already present.

        Examples:
        - 'test' → 'TestAgent'
        - 'input' → 'InputAgent'
        - 'some_class' → 'SomeClassAgent'
        - 'test_agent' → 'TestAgent' (no double suffix)
        - 'ThisNamedAgent' → 'ThisNamedAgent' (preserved)

        Args:
            agent_type: Agent type from CSV (may be any case, with underscores or hyphens)

        Returns:
            Properly formatted agent class name in PascalCase with Agent suffix
        """
        if not agent_type:
            return "Agent"

        # Convert to PascalCase
        pascal_case_name = self._to_pascal_case(agent_type)

        # Only add Agent suffix if not already present
        if not pascal_case_name.endswith("Agent"):
            pascal_case_name += "Agent"

        return pascal_case_name

    def _to_pascal_case(self, text: str) -> str:
        """
        Convert text to PascalCase for class names.

        Args:
            text: Input text (may contain underscores, hyphens, or mixed case)

        Returns:
            PascalCase version of the text
        """
        if not text:
            return ""

        # If text has no underscores/hyphens and starts with uppercase, preserve it
        if "_" not in text and "-" not in text and text[0].isupper():
            return text

        # Split on underscores/hyphens and capitalize each part
        parts = text.replace("-", "_").split("_")
        pascal_parts = []

        for part in parts:
            if part:  # Skip empty parts
                # Capitalize first letter, preserve the rest
                pascal_parts.append(
                    part[0].upper() + part[1:] if len(part) > 1 else part.upper()
                )

        return "".join(pascal_parts)

    def generate_service_attributes(self, attributes: List[ServiceAttribute]) -> str:
        """
        Generate service attribute declarations for __init__ method.

        Args:
            attributes: List of service attributes to generate

        Returns:
            String containing service attribute declarations
        """
        if not attributes:
            return ""

        service_attrs = [
            "\n        # Service attributes (automatically injected during graph building)"
        ]
        for attr in attributes:
            # Use clean type hints
            service_attrs.append(f"        self.{attr.name}: {attr.type_hint} = None")

        return "\n".join(service_attrs)

    def generate_services_documentation(self, attributes: List[ServiceAttribute]) -> str:
        """
        Generate services documentation for class docstring.

        Args:
            attributes: List of service attributes to document

        Returns:
            String containing services documentation
        """
        if not attributes:
            return ""

        services_doc_lines = ["", "    Available Services:"]
        for attr in attributes:
            services_doc_lines.append(f"    - self.{attr.name}: {attr.documentation}")

        return "\n".join(services_doc_lines)

    def generate_input_field_access(self, input_fields: List[str]) -> str:
        """
        Generate input field access code for process method.

        Args:
            input_fields: List of input field names

        Returns:
            String containing input field access code
        """
        if input_fields:
            access_lines = []
            for field in input_fields:
                access_lines.append(f'        {field}_value = inputs.get("{field}")')
            return "\n".join(access_lines)
        else:
            return "        # No specific input fields defined in the CSV"

    def generate_service_usage_examples(self, service_reqs: ServiceRequirements) -> str:
        """
        Generate service usage examples for method body comments.

        Args:
            service_reqs: Service requirements with usage examples

        Returns:
            String containing service usage examples
        """
        if not service_reqs.services:
            return "            # No services configured"

        usage_lines = []
        for service in service_reqs.services:
            if service in service_reqs.usage_examples:
                usage_lines.append(f"            # {service.upper()} SERVICE:")
                example_content = service_reqs.usage_examples[service]

                # Process each line of the example
                example_lines = example_content.split("\n")
                for example_line in example_lines:
                    if example_line.strip():
                        usage_lines.append(f"            {example_line}")
                usage_lines.append("")

        return "\n".join(usage_lines)

    def generate_context_fields(self, input_fields: List[str], output_field: str) -> str:
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
