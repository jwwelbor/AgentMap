"""
IndentedTemplateComposer for AgentMap.

Main orchestrator that coordinates template composition with proper indentation handling.
This refactored version delegates responsibilities to focused, single-purpose classes.
"""

from typing import Any, Dict, NamedTuple

from agentmap.models.scaffold_types import ServiceRequirements
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService

from .agent_template_composer import AgentTemplateComposer
from .code_generator import CodeGenerator
from .function_template_composer import FunctionTemplateComposer
from .template_loader import TemplateLoader


# Define section specification for template composition
class SectionSpec(NamedTuple):
    """Specification for a template section with indentation level."""

    name: str
    indent_spaces: int
    variables: Dict[str, str]


# Standard Python indentation levels following PEP 8
INDENT_LEVELS = {
    "module": 0,  # Module level (imports, class definitions)
    "class_body": 4,  # Inside class (method definitions)
    "method_body": 8,  # Inside methods (implementation code)
    "nested": 12,  # Nested blocks (if/for inside methods)
}


class IndentedTemplateComposer:
    """
    Template composer that handles proper Python indentation using textwrap.indent().

    This refactored version delegates responsibilities to specialized classes:
    - TemplateLoader: Template loading and caching
    - CodeGenerator: Code snippet generation
    - AgentTemplateComposer: Agent template composition
    - FunctionTemplateComposer: Function template composition

    Processes modular template sections independently and applies correct indentation
    levels to solve indentation issues in generated scaffold code.
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
        self._code_generator = CodeGenerator(logging_service)

        # Pass _load_template_internal as callback to enable test mocking
        self._agent_composer = AgentTemplateComposer(
            self._template_loader,
            self._code_generator,
            logging_service,
            load_template_fn=lambda path: self._load_template_internal(path)
        )
        self._function_composer = FunctionTemplateComposer(
            self._template_loader,
            self._code_generator,
            logging_service,
            load_template_fn=lambda path: self._load_template_internal(path)
        )

        # Maintain backwards compatibility - expose template loader's internal state
        # as properties so they stay synchronized
        self._template_base_package = self._template_loader._template_base_package

        self.logger.info(
            "[IndentedTemplateComposer] Initialized with modular architecture"
        )

    @property
    def _template_cache(self):
        """Access template cache from loader (backwards compatibility)."""
        return self._template_loader._template_cache

    @property
    def _cache_stats(self):
        """Access cache stats from loader (backwards compatibility)."""
        return self._template_loader._cache_stats

    # =========================================================================
    # Public API Methods (Maintained for Backwards Compatibility)
    # =========================================================================

    def compose_template(
        self, agent_type: str, info: Dict[str, Any], service_reqs: ServiceRequirements
    ) -> str:
        """
        Compose complete agent template with proper indentation.

        This method delegates to AgentTemplateComposer for actual composition.

        Args:
            agent_type: Type of agent to scaffold
            info: Agent information dictionary
            service_reqs: Parsed service requirements

        Returns:
            Complete agent template string with correct indentation

        Raises:
            Exception: If template composition fails
        """
        return self._agent_composer.compose_template(agent_type, info, service_reqs)

    def compose_function_template(self, func_name: str, info: Dict[str, Any]) -> str:
        """
        Compose function template with proper formatting.

        This method delegates to FunctionTemplateComposer for actual composition.

        Args:
            func_name: Name of function to scaffold
            info: Function information dictionary

        Returns:
            Complete function template string with variables substituted

        Raises:
            Exception: If template composition fails
        """
        return self._function_composer.compose_function_template(func_name, info)

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get template caching statistics.

        Delegates to TemplateLoader for cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return self._template_loader.get_cache_stats()

    def clear_template_cache(self):
        """
        Clear template cache and reset statistics.

        Delegates to TemplateLoader for cache management.
        """
        self._template_loader.clear_cache()
        self.logger.debug("[IndentedTemplateComposer] Template cache cleared")

    def get_function_template_info(self) -> Dict[str, Any]:
        """
        Get information about function template composition capabilities.

        Delegates to FunctionTemplateComposer for template info.

        Returns:
            Dictionary with function template status and configuration info
        """
        return self._function_composer.get_template_info()

    # =========================================================================
    # Legacy Methods (Maintained for Backwards Compatibility)
    # =========================================================================
    # These methods maintain the original interface for external callers
    # but delegate to the appropriate specialized classes internally.
    # =========================================================================

    def _load_template_internal(self, template_path: str) -> str:
        """
        Load template content internally with caching support.

        Legacy method maintained for backwards compatibility.
        Uses the same implementation as the original for test compatibility.

        Args:
            template_path: Template path

        Returns:
            Template content as string
        """
        # Normalize template path (remove "file:" prefix if present)
        normalized_path = template_path.replace("file:", "").strip()

        # Check cache first
        if normalized_path in self._template_cache:
            self._cache_stats["hits"] += 1
            self.logger.trace(
                f"[IndentedTemplateComposer] Cache hit for template: {normalized_path}"
            )
            return self._template_cache[normalized_path]

        # Cache miss - load template
        self._cache_stats["misses"] += 1
        self.logger.debug(
            f"[IndentedTemplateComposer] Loading template: {normalized_path}"
        )

        try:
            content = self._discover_and_load_template(normalized_path)

            # Cache the loaded content
            self._template_cache[normalized_path] = content

            self.logger.debug(
                f"[IndentedTemplateComposer] Successfully loaded and cached template: {normalized_path}"
            )
            return content

        except Exception as e:
            self.logger.error(
                f"[IndentedTemplateComposer] Failed to load template {normalized_path}: {e}"
            )
            raise

    def _discover_and_load_template(self, template_path: str) -> str:
        """
        Discover and load template from embedded resources or filesystem.

        Legacy method maintained for backwards compatibility.
        Delegates to TemplateLoader.

        Args:
            template_path: Relative template path

        Returns:
            Template content as string
        """
        return self._template_loader._discover_and_load(template_path)

    def _load_from_embedded_resources(self, template_path: str) -> str:
        """
        Load template from embedded package resources.

        Legacy method maintained for backwards compatibility.
        Delegates to TemplateLoader.

        Args:
            template_path: Relative template path

        Returns:
            Template content as string
        """
        return self._template_loader._load_from_embedded_resources(template_path)

    def _apply_variable_substitution(
        self, content: str, variables: Dict[str, Any]
    ) -> str:
        """
        Apply variable substitution to template content.

        Legacy method maintained for backwards compatibility.
        Delegates to AgentTemplateComposer.

        Args:
            content: Template content with variable placeholders
            variables: Dictionary of variables for substitution

        Returns:
            Content with variables substituted
        """
        return self._agent_composer._apply_variable_substitution(content, variables)

    def _compose_with_master_template(
        self, variables: Dict[str, str], service_reqs: ServiceRequirements
    ) -> str:
        """
        Compose template using master template with section insertion.

        Legacy method maintained for backwards compatibility.
        Delegates to AgentTemplateComposer.

        Args:
            variables: Template variables for substitution
            service_reqs: Service requirements for examples

        Returns:
            Complete template using master template approach
        """
        return self._agent_composer._compose_with_master_template(
            variables, service_reqs
        )

    def _process_section(
        self, section_name: str, variables: Dict[str, str], indent_spaces: int
    ) -> str:
        """
        Process individual template section with proper indentation.

        Legacy method maintained for backwards compatibility.
        Delegates to AgentTemplateComposer.

        Args:
            section_name: Name of the template section file
            variables: Template variables for substitution
            indent_spaces: Number of spaces to indent this section

        Returns:
            Processed section content with correct indentation
        """
        return self._agent_composer._process_section(
            section_name, variables, indent_spaces
        )

    def _apply_indentation(self, content: str, spaces: int) -> str:
        """
        Apply consistent indentation to content.

        Legacy method maintained for backwards compatibility.
        Delegates to AgentTemplateComposer.

        Args:
            content: Text content to indent
            spaces: Number of spaces for indentation

        Returns:
            Content with proper indentation applied
        """
        return self._agent_composer._apply_indentation(content, spaces)

    def _load_service_examples_section(self, service_reqs: ServiceRequirements) -> str:
        """
        Load service usage examples section from template files.

        Legacy method maintained for backwards compatibility.
        Delegates to AgentTemplateComposer.

        Args:
            service_reqs: Parsed service requirements

        Returns:
            Combined service usage examples section
        """
        return self._agent_composer._load_service_examples_section(service_reqs)

    def _prepare_comprehensive_template_variables(
        self, agent_type: str, info: Dict[str, Any], service_reqs: ServiceRequirements
    ) -> Dict[str, str]:
        """
        Prepare comprehensive template variables for substitution.

        Legacy method maintained for backwards compatibility.
        Delegates to AgentTemplateComposer.

        Args:
            agent_type: Type of agent to scaffold
            info: Agent information dictionary
            service_reqs: Parsed service requirements

        Returns:
            Dictionary with comprehensive template variables
        """
        return self._agent_composer._prepare_template_variables(
            agent_type, info, service_reqs
        )

    def _generate_agent_class_name(self, agent_type: str) -> str:
        """
        Generate proper PascalCase class name for agent.

        Legacy method maintained for backwards compatibility.
        Delegates to CodeGenerator.

        Args:
            agent_type: Agent type from CSV

        Returns:
            Properly formatted agent class name
        """
        return self._code_generator.generate_agent_class_name(agent_type)

    def _to_pascal_case(self, text: str) -> str:
        """
        Convert text to PascalCase for class names.

        Legacy method maintained for backwards compatibility.
        Delegates to CodeGenerator.

        Args:
            text: Input text

        Returns:
            PascalCase version of the text
        """
        return self._code_generator._to_pascal_case(text)

    def _generate_service_attributes(self, attributes) -> str:
        """
        Generate service attribute declarations.

        Legacy method maintained for backwards compatibility.
        Delegates to CodeGenerator.

        Args:
            attributes: List of service attributes

        Returns:
            String containing service attribute declarations
        """
        return self._code_generator.generate_service_attributes(attributes)

    def _generate_services_documentation(self, attributes) -> str:
        """
        Generate services documentation for class docstring.

        Legacy method maintained for backwards compatibility.
        Delegates to CodeGenerator.

        Args:
            attributes: List of service attributes

        Returns:
            String containing services documentation
        """
        return self._code_generator.generate_services_documentation(attributes)

    def _generate_input_field_access(self, input_fields) -> str:
        """
        Generate input field access code for process method.

        Legacy method maintained for backwards compatibility.
        Delegates to CodeGenerator.

        Args:
            input_fields: List of input field names

        Returns:
            String containing input field access code
        """
        return self._code_generator.generate_input_field_access(input_fields)

    def _generate_service_usage_examples(self, service_reqs: ServiceRequirements) -> str:
        """
        Generate service usage examples for method body comments.

        Legacy method maintained for backwards compatibility.
        Delegates to CodeGenerator.

        Args:
            service_reqs: Service requirements

        Returns:
            String containing service usage examples
        """
        return self._code_generator.generate_service_usage_examples(service_reqs)

    def _prepare_function_template_variables(
        self, func_name: str, info: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Prepare template variables for function template substitution.

        Legacy method maintained for backwards compatibility.
        Delegates to FunctionTemplateComposer.

        Args:
            func_name: Name of function to scaffold
            info: Function information dictionary

        Returns:
            Dictionary with template variables
        """
        return self._function_composer._prepare_template_variables(func_name, info)

    def _generate_context_fields(self, input_fields, output_field: str) -> str:
        """
        Generate documentation about available fields in the state.

        Legacy method maintained for backwards compatibility.
        Delegates to CodeGenerator.

        Args:
            input_fields: List of input field names
            output_field: Output field name

        Returns:
            String containing formatted field documentation
        """
        return self._code_generator.generate_context_fields(input_fields, output_field)
