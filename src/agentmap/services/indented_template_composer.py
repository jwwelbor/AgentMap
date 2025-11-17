"""
IndentedTemplateComposer for AgentMap.

Service that provides template composition with proper indentation handling using
Python's built-in textwrap.indent(). Solves indentation issues in scaffold
template generation by processing each template section independently and
applying correct indentation levels.

This service replaces the complex templating logic in GraphScaffoldService,
following the Single Responsibility Principle by focusing solely on template
composition and indentation handling.

REFACTORED: This class now serves as a facade, delegating to specialized modules
for better maintainability and separation of concerns.
"""

from typing import Any, Dict, List, NamedTuple

from agentmap.models.scaffold_types import ServiceAttribute, ServiceRequirements
from agentmap.services.agent_template_composer import AgentTemplateComposer
from agentmap.services.agent_variable_generator import AgentVariableGenerator
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.function_template_composer import FunctionTemplateComposer
from agentmap.services.logging_service import LoggingService
from agentmap.services.template_loader import TemplateLoader
from agentmap.services.template_processor import INDENT_LEVELS, TemplateProcessor


# Define section specification for template composition (for backward compatibility)
class SectionSpec(NamedTuple):
    """Specification for a template section with indentation level."""

    name: str
    indent_spaces: int
    variables: Dict[str, str]


class IndentedTemplateComposer:
    """
    Template composer that handles proper Python indentation using textwrap.indent().

    Processes modular template sections independently and applies correct indentation
    levels to solve indentation issues in generated scaffold code.

    This service encapsulates all template composition logic that was previously
    scattered across GraphScaffoldService, providing a clean, focused API for
    generating agent templates with proper formatting.

    REFACTORED: Now acts as a facade, delegating to specialized components:
    - TemplateLoader: Template loading and caching
    - TemplateProcessor: Variable substitution and indentation
    - AgentVariableGenerator: Agent template variable generation
    - AgentTemplateComposer: Agent template composition
    - FunctionTemplateComposer: Function template composition
    """

    def __init__(
        self, app_config_service: AppConfigService, logging_service: LoggingService
    ):
        """
        Initialize composer with required dependencies.

        Args:
            app_config_service: Application configuration service
            logging_service: Logging service for error handling and debugging
        """
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)

        # Initialize specialized components
        self._template_loader = TemplateLoader(app_config_service, logging_service)
        self._template_processor = TemplateProcessor(logging_service)
        self._agent_variable_generator = AgentVariableGenerator(logging_service)
        self._agent_template_composer = AgentTemplateComposer(
            self._template_loader, self._template_processor, logging_service
        )
        self._function_template_composer = FunctionTemplateComposer(
            self._template_loader, self._template_processor, logging_service
        )

        self.logger.info(
            "[IndentedTemplateComposer] Initialized with modular architecture"
        )

    # =============================================================================
    # BACKWARD COMPATIBILITY PROPERTIES
    # =============================================================================

    @property
    def _template_cache(self):
        """Backward compatibility property for accessing template cache."""
        return self._template_loader._template_cache

    @property
    def _cache_stats(self):
        """Backward compatibility property for accessing cache stats."""
        return self._template_loader._cache_stats

    # =============================================================================
    # PUBLIC API - Template Composition Methods (Backward Compatible)
    # =============================================================================

    def compose_template(
        self, agent_type: str, info: Dict[str, Any], service_reqs: ServiceRequirements
    ) -> str:
        """
        Compose complete agent template with proper indentation.

        This method replaces the existing _compose_agent_template() method in
        GraphScaffoldService with proper indentation handling and cleaner structure.

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
            # Prepare comprehensive template variables using variable generator
            variables = self._agent_variable_generator.prepare_comprehensive_template_variables(
                agent_type, info, service_reqs
            )

            # Use agent template composer to compose the template
            return self._agent_template_composer.compose_with_master_template(
                variables, service_reqs
            )

        except Exception as e:
            self.logger.error(
                f"[IndentedTemplateComposer] Failed to compose template for {agent_type}: {e}"
            )
            raise

    def compose_function_template(self, func_name: str, info: Dict[str, Any]) -> str:
        """
        Compose function template with proper formatting.

        This method provides comprehensive function template composition that eliminates
        the need for PromptManagerService dependency in GraphScaffoldService.

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
        return self._function_template_composer.compose_function_template(
            func_name, info
        )

    # =============================================================================
    # PUBLIC API - Cache Management (Backward Compatible)
    # =============================================================================

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get template caching statistics.

        Returns:
            Dictionary with cache statistics
        """
        return self._template_loader.get_cache_stats()

    def clear_template_cache(self):
        """
        Clear template cache and reset statistics.
        """
        self._template_loader.clear_cache()
        self.logger.debug("[IndentedTemplateComposer] Template cache cleared")

    def get_function_template_info(self) -> Dict[str, Any]:
        """
        Get information about function template composition capabilities.

        Returns:
            Dictionary with function template status and configuration info
        """
        return self._function_template_composer.get_function_template_info()

    # =============================================================================
    # INTERNAL API - Delegated to Components (For Backward Compatibility)
    # =============================================================================

    def _load_template_internal(self, template_path: str) -> str:
        """
        Load template content internally with caching support.

        DELEGATED: Now delegates to TemplateLoader.

        Args:
            template_path: Template path

        Returns:
            Template content as string
        """
        return self._template_loader.load_template(template_path)

    def _apply_variable_substitution(
        self, content: str, variables: Dict[str, Any]
    ) -> str:
        """
        Apply variable substitution to template content.

        DELEGATED: Now delegates to TemplateProcessor.

        Args:
            content: Template content with variable placeholders
            variables: Dictionary of variables for substitution

        Returns:
            Content with variables substituted
        """
        return self._template_processor.apply_variable_substitution(content, variables)

    def _apply_indentation(self, content: str, spaces: int) -> str:
        """
        Apply consistent indentation to content.

        DELEGATED: Now delegates to TemplateProcessor.

        Args:
            content: Text content to indent
            spaces: Number of spaces for indentation

        Returns:
            Content with proper indentation applied
        """
        return self._template_processor.apply_indentation(content, spaces)

    def _process_section(
        self, section_name: str, variables: Dict[str, str], indent_spaces: int
    ) -> str:
        """
        Process individual template section with proper indentation.

        DELEGATED: Now delegates to AgentTemplateComposer.

        Args:
            section_name: Name of the template section file (without .txt)
            variables: Template variables for substitution
            indent_spaces: Number of spaces to indent this section

        Returns:
            Processed section content with correct indentation
        """
        return self._agent_template_composer._process_section(
            section_name, variables, indent_spaces
        )

    def _generate_agent_class_name(self, agent_type: str) -> str:
        """
        Generate proper PascalCase class name for agent.

        DELEGATED: Now delegates to AgentVariableGenerator.

        Args:
            agent_type: Agent type from CSV

        Returns:
            Properly formatted agent class name
        """
        return self._agent_variable_generator.generate_agent_class_name(agent_type)

    def _to_pascal_case(self, text: str) -> str:
        """
        Convert text to PascalCase for class names.

        DELEGATED: Now delegates to AgentVariableGenerator.

        Args:
            text: Input text

        Returns:
            PascalCase version of the text
        """
        return self._agent_variable_generator._to_pascal_case(text)

    def _prepare_comprehensive_template_variables(
        self, agent_type: str, info: Dict[str, Any], service_reqs: ServiceRequirements
    ) -> Dict[str, str]:
        """
        Prepare comprehensive template variables for substitution.

        DELEGATED: Now delegates to AgentVariableGenerator.

        Args:
            agent_type: Type of agent to scaffold
            info: Agent information dictionary
            service_reqs: Parsed service requirements

        Returns:
            Dictionary with comprehensive template variables
        """
        return self._agent_variable_generator.prepare_comprehensive_template_variables(
            agent_type, info, service_reqs
        )

    def _generate_service_attributes(self, attributes: List[ServiceAttribute]) -> str:
        """
        Generate service attribute declarations.

        DELEGATED: Now delegates to AgentVariableGenerator.

        Args:
            attributes: List of service attributes

        Returns:
            String containing service attribute declarations
        """
        return self._agent_variable_generator.generate_service_attributes(attributes)

    def _generate_services_documentation(
        self, attributes: List[ServiceAttribute]
    ) -> str:
        """
        Generate services documentation for class docstring.

        DELEGATED: Now delegates to AgentVariableGenerator.

        Args:
            attributes: List of service attributes to document

        Returns:
            String containing services documentation
        """
        return self._agent_variable_generator.generate_services_documentation(attributes)

    def _generate_input_field_access(self, input_fields: List[str]) -> str:
        """
        Generate input field access code.

        DELEGATED: Now delegates to AgentVariableGenerator.

        Args:
            input_fields: List of input field names

        Returns:
            String containing input field access code
        """
        return self._agent_variable_generator.generate_input_field_access(input_fields)

    def _generate_service_usage_examples(
        self, service_reqs: ServiceRequirements
    ) -> str:
        """
        Generate service usage examples.

        DELEGATED: Now delegates to AgentVariableGenerator.

        Args:
            service_reqs: Service requirements with usage examples

        Returns:
            String containing service usage examples
        """
        return self._agent_variable_generator.generate_service_usage_examples(service_reqs)

    def _prepare_function_template_variables(
        self, func_name: str, info: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Prepare template variables for function template.

        DELEGATED: Now delegates to FunctionTemplateComposer.

        Args:
            func_name: Name of function to scaffold
            info: Function information dictionary

        Returns:
            Dictionary with template variables
        """
        return self._function_template_composer._prepare_function_template_variables(
            func_name, info
        )

    def _generate_context_fields(
        self, input_fields: List[str], output_field: str
    ) -> str:
        """
        Generate context fields documentation.

        DELEGATED: Now delegates to FunctionTemplateComposer.

        Args:
            input_fields: List of input field names
            output_field: Output field name

        Returns:
            String containing field documentation
        """
        return self._function_template_composer._generate_context_fields(
            input_fields, output_field
        )
