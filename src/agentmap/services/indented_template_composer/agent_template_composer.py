"""
Agent template composition for IndentedTemplateComposer.

Handles composition of complete agent templates with proper indentation and structure.
"""

import textwrap
from typing import Any, Callable, Dict

from agentmap.models.scaffold_types import ServiceRequirements
from agentmap.services.logging_service import LoggingService

from .code_generator import CodeGenerator
from .template_loader import TemplateLoader


class AgentTemplateComposer:
    """
    Composes complete agent templates using modular sections.

    Responsibilities:
    - Compose master template with sections
    - Apply proper indentation
    - Load service examples
    - Prepare comprehensive template variables
    """

    def __init__(
        self,
        template_loader: TemplateLoader,
        code_generator: CodeGenerator,
        logging_service: LoggingService,
        load_template_fn: Callable[[str], str] = None,
    ):
        """
        Initialize agent template composer.

        Args:
            template_loader: Template loader for loading template files
            code_generator: Code generator for generating code snippets
            logging_service: Logging service for debugging
            load_template_fn: Optional template loading function (for backwards compat with mocking)
        """
        self.template_loader = template_loader
        self.code_generator = code_generator
        self.logger = logging_service.get_class_logger(self)
        # Use provided function or default to template_loader.load_template
        self._load_template = load_template_fn or template_loader.load_template

    def compose_template(
        self, agent_type: str, info: Dict[str, Any], service_reqs: ServiceRequirements
    ) -> str:
        """
        Compose complete agent template with proper indentation.

        Args:
            agent_type: Type of agent to scaffold
            info: Agent information dictionary
            service_reqs: Parsed service requirements

        Returns:
            Complete agent template string with correct indentation

        Raises:
            Exception: If template composition fails
        """
        try:
            # Prepare comprehensive template variables
            variables = self._prepare_template_variables(
                agent_type, info, service_reqs
            )

            # Use master template approach
            return self._compose_with_master_template(variables, service_reqs)

        except Exception as e:
            self.logger.error(
                f"[AgentTemplateComposer] Failed to compose template for {agent_type}: {e}"
            )
            raise

    def _compose_with_master_template(
        self, variables: Dict[str, str], service_reqs: ServiceRequirements
    ) -> str:
        """
        Compose template using master template with section insertion.

        Args:
            variables: Template variables for substitution
            service_reqs: Service requirements for examples

        Returns:
            Complete template using master template approach
        """
        # Load and process each modular section WITHOUT additional indentation
        # since the master template already provides the correct structural indentation
        processed_sections = {
            "header": self._process_section("header", variables, 0),
            "class_definition": self._process_section("class_definition", variables, 0),
            "init_method": self._process_section("init_method", variables, 0),
            "process_method": self._process_section("process_method", variables, 0),
            "helper_methods": self._process_section("helper_methods", variables, 0),
            "footer": self._process_section("footer", variables, 0),
        }

        # Add service usage examples section if services are configured
        if service_reqs.services:
            processed_sections["service_examples"] = (
                self._load_service_examples_section(service_reqs)
            )
        else:
            processed_sections["service_examples"] = ""

        # Load master template and insert processed sections
        master_template = self._load_template("master_template.txt")
        return self._apply_variable_substitution(master_template, processed_sections)

    def _process_section(
        self, section_name: str, variables: Dict[str, str], indent_spaces: int
    ) -> str:
        """
        Process individual template section with proper indentation.

        Args:
            section_name: Name of the template section file (without .txt)
            variables: Template variables for substitution
            indent_spaces: Number of spaces to indent this section

        Returns:
            Processed section content with correct indentation

        Raises:
            Exception: If template loading fails
        """
        try:
            # Load template section
            template_path = f"modular/{section_name}.txt"
            template_content = self._load_template(template_path)

            # Apply variable substitution
            formatted_content = self._apply_variable_substitution(
                template_content, variables
            )

            # Apply indentation
            return self._apply_indentation(formatted_content, indent_spaces)

        except Exception as e:
            self.logger.error(
                f"[AgentTemplateComposer] Failed to process section '{section_name}': {e}"
            )
            raise

    def _apply_indentation(self, content: str, spaces: int) -> str:
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

    def _load_service_examples_section(self, service_reqs: ServiceRequirements) -> str:
        """
        Load service usage examples section from template files.

        Args:
            service_reqs: Parsed service requirements

        Returns:
            Combined service usage examples section
        """
        if not service_reqs.services:
            return ""

        try:
            sections = [
                "",
                "# ===== SERVICE USAGE EXAMPLES =====",
                "#",
                "# This agent has access to the following services:",
                "#",
            ]

            for service in service_reqs.services:
                sections.append(f"# {service.upper()} SERVICE:")

                # Load usage example from services/ directory
                try:
                    usage_path = f"services/{service}_usage.txt"
                    usage_content = self._load_template(usage_path)

                    # Add each line as a comment
                    for line in usage_content.split("\n"):
                        sections.append(f"# {line}")

                except Exception as e:
                    self.logger.warning(
                        f"[AgentTemplateComposer] Could not load usage example for {service}: {e}"
                    )
                    sections.append(f"# Usage example for {service} not available")

                sections.append("#")

            return "\n".join(sections)

        except Exception as e:
            self.logger.error(
                f"[AgentTemplateComposer] Failed to load service examples: {e}"
            )
            return "# Error loading service examples"

    def _prepare_template_variables(
        self, agent_type: str, info: Dict[str, Any], service_reqs: ServiceRequirements
    ) -> Dict[str, str]:
        """
        Prepare comprehensive template variables for substitution.

        Args:
            agent_type: Type of agent to scaffold
            info: Agent information dictionary
            service_reqs: Parsed service requirements

        Returns:
            Dictionary with comprehensive template variables
        """
        # Generate proper PascalCase class name
        class_name = self.code_generator.generate_agent_class_name(agent_type)
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
        service_attributes = self.code_generator.generate_service_attributes(
            service_reqs.attributes
        )

        # Services documentation
        services_doc = self.code_generator.generate_services_documentation(
            service_reqs.attributes
        )

        # Input field access code
        input_field_access = self.code_generator.generate_input_field_access(
            info["input_fields"]
        )

        # Service usage examples in method body
        service_usage_examples = self.code_generator.generate_service_usage_examples(
            service_reqs
        )

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

    def _apply_variable_substitution(
        self, content: str, variables: Dict[str, Any]
    ) -> str:
        """
        Apply variable substitution to template content.

        Args:
            content: Template content with variable placeholders
            variables: Dictionary of variables for substitution

        Returns:
            Content with variables substituted

        Raises:
            ValueError: If required template variable is missing
        """
        try:
            return content.format(**variables)
        except KeyError as e:
            # Log missing variables and raise an exception for visibility
            missing_var = str(e).strip("'\"")
            self.logger.error(
                f"[AgentTemplateComposer] Missing required template variable: {missing_var}"
            )
            self.logger.debug(
                f"[AgentTemplateComposer] Available variables: {list(variables.keys())}"
            )
            # Re-raise or raise a custom exception to prevent silent failure
            raise ValueError(f"Missing template variable: {missing_var}") from e
        except Exception as e:
            self.logger.error(
                f"[AgentTemplateComposer] Variable substitution error: {e}"
            )
            # Re-raise to ensure failure is not silent
            raise
