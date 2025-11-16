"""
IndentedTemplateComposer for AgentMap.

Service that provides template composition with proper indentation handling using
Python's built-in textwrap.indent(). Solves indentation issues in scaffold
template generation by processing each template section independently and
applying correct indentation levels.

This service replaces the complex templating logic in GraphScaffoldService,
following the Single Responsibility Principle by focusing solely on template
composition and indentation handling.
"""

import importlib.resources
import importlib.util
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, NamedTuple

from agentmap.models.scaffold_types import ServiceAttribute, ServiceRequirements
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService


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

    Processes modular template sections independently and applies correct indentation
    levels to solve indentation issues in generated scaffold code.

    This service encapsulates all template composition logic that was previously
    scattered across GraphScaffoldService, providing a clean, focused API for
    generating agent templates with proper formatting.
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

        # Internal template loading capabilities
        self._template_cache: Dict[str, str] = {}  # Simple template caching
        self._cache_stats = {"hits": 0, "misses": 0}  # Cache statistics
        self._template_base_package = "agentmap.templates.system.scaffold"

        self.logger.info(
            "[IndentedTemplateComposer] Initialized with internal template loading capabilities"
        )

    def _load_template_internal(self, template_path: str) -> str:
        """
        Load template content internally with caching support.

        Args:
            template_path: Template path (e.g., "scaffold/master_template.txt" or "file:scaffold/master_template.txt")

        Returns:
            Template content as string

        Raises:
            Exception: If template cannot be loaded from any source
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

        Args:
            template_path: Relative template path (e.g., "scaffold/master_template.txt")

        Returns:
            Template content as string

        Raises:
            Exception: If template cannot be found in any location
        """
        # Try loading from embedded resources first
        try:
            content = self._load_from_embedded_resources(template_path)
            if content:
                return content
        except Exception as e:
            self.logger.debug(
                f"[IndentedTemplateComposer] Embedded resource loading failed for {template_path}: {e}"
            )

        # Try loading from prompts directory
        try:
            prompts_config = self.config.get_prompts_config()
            prompts_dir = Path(prompts_config.get("directory", "prompts"))
            # Add back scaffold/ for prompts directory since it expects full path
            file_path = (
                prompts_dir / f"scaffold/{template_path}"
                if not template_path.startswith("scaffold/")
                else prompts_dir / template_path
            )

            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    self.logger.debug(
                        f"[IndentedTemplateComposer] Loaded from prompts directory: {file_path}"
                    )
                    return content
        except Exception as e:
            self.logger.debug(
                f"[IndentedTemplateComposer] Prompts directory loading failed for {template_path}: {e}"
            )

        # If all methods fail, raise exception
        raise FileNotFoundError(f"Template not found: {template_path}")

    def _load_from_embedded_resources(self, template_path: str) -> str:
        """
        Load template from embedded package resources.

        Args:
            template_path: Relative template path within the scaffold package

        Returns:
            Template content as string

        Raises:
            Exception: If template cannot be loaded from embedded resources
        """
        # Remove leading "scaffold/" since base package already points to scaffold directory
        if template_path.startswith("scaffold/"):
            template_path = template_path[len("scaffold/") :]

        # Split path to determine package and resource
        path_parts = template_path.split("/")

        if len(path_parts) == 1:
            # Direct file in scaffold directory
            package = self._template_base_package
            resource_name = path_parts[0]
        else:
            # File in subdirectory (e.g., modular/header.txt)
            subdir = ".".join(path_parts[:-1])
            package = f"{self._template_base_package}.{subdir}"
            resource_name = path_parts[-1]

        try:
            # Use importlib.resources to load the template
            if sys.version_info >= (3, 9):
                # Python 3.9+ method
                try:
                    files = importlib.resources.files(package)
                    template_file = files.joinpath(resource_name)
                    if template_file.exists():
                        content = template_file.read_text(encoding="utf-8")
                        return content.strip()
                except (ImportError, AttributeError, ValueError):
                    pass

            # Fallback for Python 3.7-3.8
            if sys.version_info >= (3, 7):
                try:
                    with importlib.resources.path(
                        package, resource_name
                    ) as template_path_obj:
                        if template_path_obj.exists():
                            with open(template_path_obj, "r", encoding="utf-8") as f:
                                content = f.read().strip()
                                return content
                except (ImportError, FileNotFoundError):
                    pass

            # Final fallback using spec location
            spec = importlib.util.find_spec(package)
            if spec and spec.origin:
                package_dir = Path(os.path.dirname(spec.origin))
                template_file_path = package_dir / resource_name
                if template_file_path.exists():
                    with open(template_file_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        return content

            raise FileNotFoundError(
                f"Template resource not found: {package}/{resource_name}"
            )

        except Exception as e:
            self.logger.debug(
                f"[IndentedTemplateComposer] Embedded resource loading error: {e}"
            )
            raise

    def _apply_variable_substitution(
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
                f"[IndentedTemplateComposer] Missing template variable: {missing_var}"
            )
            self.logger.debug(
                f"[IndentedTemplateComposer] Available variables: {list(variables.keys())}"
            )
            # Return content unchanged when variables are missing
            return content
        except Exception as e:
            self.logger.error(
                f"[IndentedTemplateComposer] Variable substitution error: {e}"
            )
            # Return content unchanged on other errors
            return content

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get template caching statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = (
            self._cache_stats["hits"] / total_requests if total_requests > 0 else 0.0
        )

        return {
            "cache_size": len(self._template_cache),
            "hits": self._cache_stats["hits"],
            "misses": self._cache_stats["misses"],
            "hit_rate": hit_rate,
            "total_requests": total_requests,
            "cached_templates": list(self._template_cache.keys()),
        }

    def clear_template_cache(self):
        """
        Clear template cache and reset statistics.
        """
        self._template_cache.clear()
        self._cache_stats = {"hits": 0, "misses": 0}
        self.logger.debug("[IndentedTemplateComposer] Template cache cleared")

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
            # Prepare comprehensive template variables
            variables = self._prepare_comprehensive_template_variables(
                agent_type, info, service_reqs
            )

            # Use master template approach (no fallbacks - templates are shipped with solution)
            return self._compose_with_master_template(variables, service_reqs)

        except Exception as e:
            self.logger.error(
                f"[IndentedTemplateComposer] Failed to compose template for {agent_type}: {e}"
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
        master_template = self._load_template_internal("master_template.txt")
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
            # Load template section using internal template loading
            template_path = f"modular/{section_name}.txt"
            template_content = self._load_template_internal(template_path)

            # Apply variable substitution
            formatted_content = self._apply_variable_substitution(
                template_content, variables
            )

            # Apply indentation using textwrap.indent()
            return self._apply_indentation(formatted_content, indent_spaces)

        except Exception as e:
            self.logger.error(
                f"[IndentedTemplateComposer] Failed to process section '{section_name}': {e}"
            )
            # No fallback - templates are shipped with solution, so this should fail
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

        This method replaces _load_service_examples_directly() from GraphScaffoldService
        with improved error handling and cleaner structure.

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
                    usage_content = self._load_template_internal(usage_path)

                    # Add each line as a comment
                    for line in usage_content.split("\n"):
                        sections.append(f"# {line}")

                except Exception as e:
                    self.logger.warning(
                        f"[IndentedTemplateComposer] Could not load usage example for {service}: {e}"
                    )
                    sections.append(f"# Usage example for {service} not available")

                sections.append("#")

            return "\n".join(sections)

        except Exception as e:
            self.logger.error(
                f"[IndentedTemplateComposer] Failed to load service examples: {e}"
            )
            return "# Error loading service examples"

    def _prepare_comprehensive_template_variables(
        self, agent_type: str, info: Dict[str, Any], service_reqs: ServiceRequirements
    ) -> Dict[str, str]:
        """
        Prepare comprehensive template variables for substitution.

        This method consolidates and enhances the template variable preparation
        logic from GraphScaffoldService, providing all variables needed for
        complete template composition.

        Args:
            agent_type: Type of agent to scaffold
            info: Agent information dictionary
            service_reqs: Parsed service requirements

        Returns:
            Dictionary with comprehensive template variables
        """
        # Generate proper PascalCase class name
        class_name = self._generate_agent_class_name(agent_type)
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
        service_attributes = self._generate_service_attributes(service_reqs.attributes)

        # Services documentation
        services_doc = self._generate_services_documentation(service_reqs.attributes)

        # Input field access code
        input_field_access = self._generate_input_field_access(info["input_fields"])

        # Service usage examples in method body
        service_usage_examples = self._generate_service_usage_examples(service_reqs)

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

    def _generate_agent_class_name(self, agent_type: str) -> str:
        """
        Generate proper PascalCase class name for agent.

        Converts to PascalCase and adds 'Agent' suffix only if not already present.
        This method is moved from GraphScaffoldService for better organization.

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

    def _generate_service_attributes(self, attributes: List[ServiceAttribute]) -> str:
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

    def _generate_services_documentation(
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

    def _generate_input_field_access(self, input_fields: List[str]) -> str:
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

    def _generate_service_usage_examples(
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

    def compose_function_template(self, func_name: str, info: Dict[str, Any]) -> str:
        """
        Compose function template with proper formatting using internal template loading.

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
            Exception: If template composition fails (returns fallback template)
        """
        try:
            self.logger.debug(
                f"[IndentedTemplateComposer] Composing function template for: {func_name}"
            )

            # Prepare comprehensive template variables
            template_vars = self._prepare_function_template_variables(func_name, info)

            # Load function template using internal template loading
            template_content = self._load_template_internal("function_template.txt")

            # Apply variable substitution
            formatted_template = self._apply_variable_substitution(
                template_content, template_vars
            )

            self.logger.debug(
                f"[IndentedTemplateComposer] Successfully composed function template for: {func_name}"
            )
            return formatted_template

        except Exception as e:
            self.logger.error(
                f"[IndentedTemplateComposer] Failed to compose function template for {func_name}: {e}"
            )
            # Return fallback template to ensure operation doesn't fail
            # return self._generate_fallback_function_template(func_name, info)

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
            f"[IndentedTemplateComposer] Prepared template variables for {func_name}: "
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
            "cache_stats": self.get_cache_stats(),
        }
