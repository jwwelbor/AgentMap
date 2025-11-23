"""
Agent template composition module.

Extracted from IndentedTemplateComposer to handle all agent template
composition logic, following the Single Responsibility Principle.
"""

from typing import Any, Dict

from agentmap.models.scaffold_types import ServiceRequirements
from agentmap.services.logging_service import LoggingService
from agentmap.services.template_loader import TemplateLoader
from agentmap.services.template_processor import TemplateProcessor


class AgentTemplateComposer:
    """
    Composes agent templates with proper indentation and variable substitution.

    This class encapsulates all agent template composition logic that was
    previously in IndentedTemplateComposer, providing clean separation of concerns.
    """

    def __init__(
        self,
        template_loader: TemplateLoader,
        template_processor: TemplateProcessor,
        logging_service: LoggingService,
    ):
        """
        Initialize agent template composer.

        Args:
            template_loader: Template loader instance
            template_processor: Template processor instance
            logging_service: Logging service for error handling and debugging
        """
        self.template_loader = template_loader
        self.template_processor = template_processor
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[AgentTemplateComposer] Initialized")

    def compose_with_master_template(
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
            "header": self._process_section(
                "header", variables, 0
            ),  # No additional indentation
            "class_definition": self._process_section(
                "class_definition", variables, 0
            ),  # No additional indentation
            "init_method": self._process_section(
                "init_method", variables, 0
            ),  # No additional indentation
            "process_method": self._process_section(
                "process_method", variables, 0
            ),  # No additional indentation
            "helper_methods": self._process_section(
                "helper_methods", variables, 0
            ),  # No additional indentation
            "footer": self._process_section(
                "footer", variables, 0
            ),  # No additional indentation
        }

        # Add service usage examples section if services are configured
        if service_reqs.services:
            processed_sections["service_examples"] = (
                self._load_service_examples_section(service_reqs)
            )
        else:
            processed_sections["service_examples"] = ""

        # Load master template and insert processed sections
        master_template = self.template_loader.load_template("master_template.txt")
        return self.template_processor.apply_variable_substitution(
            master_template, processed_sections
        )

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
            # Load template section using template loader
            template_path = f"modular/{section_name}.txt"
            template_content = self.template_loader.load_template(template_path)

            # Apply variable substitution
            formatted_content = self.template_processor.apply_variable_substitution(
                template_content, variables
            )

            # Apply indentation
            return self.template_processor.apply_indentation(
                formatted_content, indent_spaces
            )

        except Exception as e:
            self.logger.error(
                f"[AgentTemplateComposer] Failed to process section '{section_name}': {e}"
            )
            # No fallback - templates are shipped with solution, so this should fail
            raise

    def _load_service_examples_section(self, service_reqs: ServiceRequirements) -> str:
        """
        Load service usage examples section from template files.

        This method provides improved error handling and cleaner structure.

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
                    usage_content = self.template_loader.load_template(usage_path)

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
