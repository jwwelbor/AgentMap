"""Scaffolding helper functions for graph scaffolding.

This module provides helper functions for scaffolding agents and functions,
handling file creation, template composition, and declaration management.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.services.custom_agent_declaration_manager import (
    CustomAgentDeclarationManager,
)
from agentmap.services.graph.scaffold.naming_utils import generate_agent_class_name
from agentmap.services.graph.scaffold.service_requirements_parser import (
    ServiceRequirementsParser,
)
from agentmap.services.indented_template_composer import IndentedTemplateComposer
from agentmap.services.logging_service import LoggingService


class ScaffoldingHelpers:
    """Helper class for agent and function scaffolding operations."""

    def __init__(
        self,
        template_composer: IndentedTemplateComposer,
        custom_agent_declaration_manager: CustomAgentDeclarationManager,
        service_parser: ServiceRequirementsParser,
        logger: LoggingService,
    ):
        """Initialize scaffolding helpers with required services.

        Args:
            template_composer: Service for composing templates
            custom_agent_declaration_manager: Manager for agent declarations
            service_parser: Parser for service requirements
            logger: Logging service for debug/info messages
        """
        self.template_composer = template_composer
        self.custom_agent_declaration_manager = custom_agent_declaration_manager
        self.service_parser = service_parser
        self.logger = logger.get_class_logger(self)

    def scaffold_agent(
        self, agent_type: str, info: Dict, output_path: Path, overwrite: bool = False
    ) -> Optional[Path]:
        """Scaffold agent class file with service awareness.

        Creates an agent class file based on the provided information,
        parses service requirements, generates appropriate templates,
        and updates agent declarations.

        Args:
            agent_type: Type of agent to scaffold
            info: Information about the agent
            output_path: Directory to create agent class in
            overwrite: Whether to overwrite existing files

        Returns:
            Path to created file, or None if file already exists and overwrite=False
        """
        agent_type + "Agent"
        file_name = f"{agent_type.lower()}_agent.py"
        file_path = output_path / file_name

        if file_path.exists() and not overwrite:
            return None

        try:
            # Parse service requirements from context
            service_reqs = self.service_parser.parse_services(info.get("context"))

            if service_reqs.services:
                self.logger.debug(
                    f"[ScaffoldingHelpers] Scaffolding {agent_type} with services: "
                    f"{', '.join(service_reqs.services)}"
                )

            # Use IndentedTemplateComposer for clean template generation
            formatted_template = self.template_composer.compose_template(
                agent_type, info, service_reqs
            )

            # Write enhanced template
            with file_path.open("w") as out:
                out.write(formatted_template)

            # Generate class path for declaration
            # Use simple module path since custom agents are external to the package
            class_name = generate_agent_class_name(agent_type)
            class_path = f"{agent_type.lower()}_agent.{class_name}"

            # Add/update agent declaration
            try:
                self.custom_agent_declaration_manager.add_or_update_agent(
                    agent_type=agent_type,
                    class_path=class_path,
                    services=service_reqs.services,
                    protocols=service_reqs.protocols,
                )
                self.logger.debug(
                    f"[ScaffoldingHelpers] ✅ Generated declaration for {agent_type}"
                )
            except Exception as e:
                self.logger.warning(
                    f"[ScaffoldingHelpers] Failed to generate declaration for {agent_type}: {e}"
                )

            services_info = (
                f" with services: {', '.join(service_reqs.services)}"
                if service_reqs.services
                else ""
            )
            self.logger.debug(
                f"[ScaffoldingHelpers] ✅ Scaffolded agent: {file_path}{services_info}"
            )

            return file_path

        except Exception as e:
            self.logger.error(
                f"[ScaffoldingHelpers] Failed to scaffold agent {agent_type}: {e}"
            )
            raise

    def scaffold_function(
        self, func_name: str, info: Dict, func_path: Path, overwrite: bool = False
    ) -> Optional[Path]:
        """Create a scaffold file for a function.

        Creates a function file based on the provided information,
        using the template composer for consistent formatting.

        Args:
            func_name: Name of function to scaffold
            info: Information about the function
            func_path: Directory to create function module in
            overwrite: Whether to overwrite existing files

        Returns:
            Path to created file, or None if file already exists and overwrite=False
        """
        file_name = f"{func_name}.py"
        file_path = func_path / file_name

        if file_path.exists() and not overwrite:
            return None

        # Use IndentedTemplateComposer for unified template composition
        formatted_template = self.template_composer.compose_function_template(
            func_name, info
        )

        # Create function file
        with file_path.open("w") as out:
            out.write(formatted_template)

        self.logger.debug(
            f"[ScaffoldingHelpers] ✅ Scaffolded function: {file_path}"
        )
        return file_path
