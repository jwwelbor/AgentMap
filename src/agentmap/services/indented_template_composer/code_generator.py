"""
Code generation utilities for IndentedTemplateComposer.

Handles generation of class names, attributes, documentation, and other code snippets.
"""

from typing import Any, Dict, List

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

    def generate_services_documentation(
        self, attributes: List[ServiceAttribute]
    ) -> str:
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

    def generate_context_fields(
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

    def generate_multi_output_scaffold(
        self, output_fields: List[str]
    ) -> Dict[str, str]:
        """
        Generate scaffolding for multi-output process method.

        Args:
            output_fields: List of declared output field names

        Returns:
            Dict with 'return_type_hint', 'return_docstring', 'process_body'
        """
        if len(output_fields) <= 1:
            # Single output - existing behavior
            single_field = output_fields[0] if output_fields else "result"
            return {
                "return_type_hint": "Any",
                "return_docstring": f"Output value to store in graph state under '{single_field}'\n            (BaseAgent handles state management automatically)",
                "process_body": self._generate_single_output_body(single_field),
            }

        # Multi-output - generate dict return
        fields_doc = ", ".join(f"'{f}'" for f in output_fields)
        return_dict = (
            "{\n"
            + "\n".join(
                f'            "{f}": None,  # Required output' for f in output_fields
            )
            + "\n        }"
        )

        return {
            "return_type_hint": "Dict[str, Any]",
            "return_docstring": f"Dictionary with keys: {fields_doc}\n            All declared output fields should be included.",
            "process_body": self._generate_multi_output_body(
                output_fields, return_dict
            ),
        }

    def _generate_single_output_body(self, output_field: str) -> str:
        """Generate process body for single output."""
        return f"""        # Example implementation (REPLACE WITH YOUR LOGIC):
        try:
            # Your processing logic goes here
            result = {{
                "processed": True,
                "agent_type": "{{agent_type}}",
                "node": "{{node_name}}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }}

            # BaseAgent will automatically store this in state['{output_field}']
            return result

        except Exception as e:
            self.logger.error(f"Processing error in {{class_name}}: {{str(e)}}")
            return {{"error": str(e), "success": False}}"""

    def _generate_multi_output_body(
        self, output_fields: List[str], return_dict: str
    ) -> str:
        """Generate process body for multi-output."""
        return f"""        # Example implementation for MULTI-OUTPUT agent:
        # This agent must return a dict with ALL declared output fields.
        try:
            # Your processing logic goes here
            # Extract/compute values for each output field

            # Return dict with all declared fields
            return {return_dict}

        except Exception as e:
            self.logger.error(f"Processing error in {{class_name}}: {{str(e)}}")
            # On error, return dict with error info in each field
            return {{f: {{"error": str(e)}} for f in {output_fields}}}"""
