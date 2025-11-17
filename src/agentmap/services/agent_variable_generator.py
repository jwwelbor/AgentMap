"""
Agent template variable generation module.

Extracted from IndentedTemplateComposer to handle all agent template
variable generation logic, following the Single Responsibility Principle.
"""

from typing import Any, Dict, List

from agentmap.models.scaffold_types import ServiceAttribute, ServiceRequirements
from agentmap.services.logging_service import LoggingService


class AgentVariableGenerator:
    """
    Generates template variables for agent template composition.

    This class encapsulates all agent variable generation logic that was
    previously in IndentedTemplateComposer, providing clean separation of concerns.
    """

    def __init__(self, logging_service: LoggingService):
        """
        Initialize agent variable generator.

        Args:
            logging_service: Logging service for error handling and debugging
        """
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[AgentVariableGenerator] Initialized")

    def prepare_comprehensive_template_variables(
        self, agent_type: str, info: Dict[str, Any], service_reqs: ServiceRequirements
    ) -> Dict[str, str]:
        """
        Prepare comprehensive template variables for substitution.

        This method consolidates and enhances the template variable preparation
        logic from IndentedTemplateComposer, providing all variables needed for
        complete template composition.

        Args:
            agent_type: Type of agent to scaffold
            info: Agent information dictionary
            service_reqs: Parsed service requirements

        Returns:
            Dictionary with comprehensive template variables
        """
        # Generate proper PascalCase class name
        class_name = self.generate_agent_class_name(agent_type)
        input_fields = (
            ", ".join(info["input_fields"])
            if info["input_fields"]
            else "None specified"
        )
        output_field = info["output_field"] or "None specified"

        # Service-related variables
        if service_reqs.protocols:
            protocols_str = ", " + ", ".join(service_reqs.protocols)
            class_definition = f"class {class_name}(BaseAgent{protocols_str}):"
            service_description = (
                f" with {', '.join(service_reqs.services)} capabilities"
            )
        else:
            class_definition = f"class {class_name}(BaseAgent):"
            service_description = ""

        # Imports
        imports = "\n" + "\n".join(service_reqs.imports) if service_reqs.imports else ""

        # Service attributes
        service_attributes = self.generate_service_attributes(service_reqs.attributes)

        # Services documentation
        services_doc = self.generate_services_documentation(service_reqs.attributes)

        # Input field access code
        input_field_access = self.generate_input_field_access(info["input_fields"])

        # Service usage examples in method body
        service_usage_examples = self.generate_service_usage_examples(service_reqs)

        return {
            "agent_type": agent_type,
            "class_name": class_name,
            "class_definition": class_definition,
            "service_description": service_description,
            "imports": imports,
            "description": info.get("description", "") or "No description provided",
            "node_name": info["node_name"],
            "input_fields": input_fields,
            "output_field": output_field,
            "services_doc": services_doc,
            "prompt_doc": (
                f"\n    Default prompt: {info['prompt']}" if info.get("prompt") else ""
            ),
            "service_attributes": service_attributes,
            "input_field_access": input_field_access,
            "service_usage_examples": service_usage_examples,
            "context": info.get("context", "") or "No context provided",
        }

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
            # Use clean type hints without complex escaping
            type_hint = attr.type_hint.replace("Any  # ", "Any  # ")
            service_attrs.append(f"        self.{attr.name}: {type_hint} = None")

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

    def generate_service_usage_examples(
        self, service_reqs: ServiceRequirements
    ) -> str:
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
