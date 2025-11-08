import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.scaffold_types import (
    ScaffoldOptions,
    ScaffoldResult,
    ServiceAttribute,
    ServiceRequirements,
)
from agentmap.services.agent.agent_registry_service import AgentRegistryService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.custom_agent_declaration_manager import (
    CustomAgentDeclarationManager,
)
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.graph.bundle_update_service import BundleUpdateService
from agentmap.services.graph.scaffold.service_requirements_parser import (
    ServiceRequirementsParser,
)
from agentmap.services.indented_template_composer import IndentedTemplateComposer
from agentmap.services.logging_service import LoggingService


class GraphScaffoldService:
    """
    Service for scaffolding agent classes and edge functions from CSV graph definitions.

    Provides service-aware scaffolding capabilities with automatic service integration,
    template management, and comprehensive error handling.
    """

    def __init__(
        self,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
        function_resolution_service: FunctionResolutionService,
        agent_registry_service: AgentRegistryService,
        template_composer: IndentedTemplateComposer,
        custom_agent_declaration_manager: CustomAgentDeclarationManager,
        bundle_update_service: BundleUpdateService,
    ):
        """Initialize service with dependency injection."""
        self.config = app_config_service
        self.logger = logging_service.get_class_logger(self)
        self.function_service = function_resolution_service
        self.agent_registry = agent_registry_service
        self.template_composer = template_composer
        self.custom_agent_declaration_manager = custom_agent_declaration_manager
        self.bundle_update_service = bundle_update_service
        self.service_parser = ServiceRequirementsParser()

        self.logger.info(
            "[GraphScaffoldService] Initialized with unified IndentedTemplateComposer and BundleUpdateService for automatic bundle updates"
        )

    def scaffold_agent_class(
        self, agent_type: str, info: Dict[str, Any], output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Scaffold individual agent class file.

        Args:
            agent_type: Type of agent to scaffold
            info: Agent information dictionary
            output_path: Optional custom output path

        Returns:
            Path to created file, or None if file already exists
        """
        output_path = output_path or self.config.custom_agents_path
        return self._scaffold_agent(agent_type, info, output_path, overwrite=False)

    def scaffold_edge_function(
        self, func_name: str, info: Dict[str, Any], func_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        Scaffold edge function file.

        Args:
            func_name: Name of function to scaffold
            info: Function information dictionary
            func_path: Optional custom function path

        Returns:
            Path to created file, or None if file already exists
        """
        func_path = func_path or self.config.functions_path
        return self._scaffold_function(func_name, info, func_path, overwrite=False)

    def scaffold_from_bundle(
        self, bundle: GraphBundle, options: Optional[ScaffoldOptions] = None
    ) -> ScaffoldResult:
        """
        Scaffold agents and functions directly from a GraphBundle.

        This method avoids CSV re-parsing by using the already-processed
        bundle information, following DRY principle. The service updates
        bundle declarations but does NOT persist the bundle - persistence
        is left to the caller to avoid interfering with bundle caching.

        Args:
            bundle: GraphBundle containing nodes and missing declarations
            options: Scaffolding options (uses defaults if None)

        Returns:
            ScaffoldResult with scaffolding details and updated bundle
            (caller responsible for persistence if needed)
        """
        options = options or ScaffoldOptions()
        self.logger.info(
            f"[GraphScaffoldService] Scaffolding from bundle: {bundle.graph_name or 'default'}"
        )

        try:
            # Get scaffold paths from options or app config
            agents_path = options.output_path or self.config.get_custom_agents_path()
            functions_path = options.function_path or self.config.get_functions_path()

            # Create directories if they don't exist
            agents_path.mkdir(parents=True, exist_ok=True)
            functions_path.mkdir(parents=True, exist_ok=True)

            # Initialize result tracking
            result = ScaffoldResult(
                scaffolded_count=0,
                service_stats={"with_services": 0, "without_services": 0},
            )

            # Process missing agent declarations from bundle
            if options.force_rescaffold:
                # Force rescaffold: use existing custom_agents set from bundle
                agents_to_scaffold = list(bundle.custom_agents or set())
                self.logger.info(
                    f"[GraphScaffoldService] Force rescaffold enabled: processing {len(agents_to_scaffold)} custom agents"
                )
            else:
                # Normal behavior: only missing declarations
                agents_to_scaffold = list(bundle.missing_declarations or set())
                self.logger.info(
                    f"[GraphScaffoldService] Found {len(agents_to_scaffold)} missing agents to scaffold"
                )

            # Rest of method remains the same...
            for agent_type in agents_to_scaffold:
                agent_info = self._extract_agent_info_from_bundle(agent_type, bundle)

                if not agent_info:
                    self.logger.warning(
                        f"[GraphScaffoldService] No node found for agent type: {agent_type}"
                    )
                    continue

                try:
                    created_path = self._scaffold_agent(
                        agent_type,
                        agent_info,
                        agents_path,
                        options.overwrite_existing,
                    )

                    if created_path:
                        result.created_files.append(created_path)
                        result.scaffolded_count += 1

                        # Track service stats
                        service_reqs = self.service_parser.parse_services(
                            agent_info.get("context")
                        )
                        if service_reqs.services:
                            result.service_stats["with_services"] += 1
                        else:
                            result.service_stats["without_services"] += 1
                    else:
                        result.skipped_files.append(
                            agents_path / f"{agent_type.lower()}_agent.py"
                        )

                except Exception as e:
                    error_msg = f"Failed to scaffold agent {agent_type}: {str(e)}"
                    self.logger.error(f"[GraphScaffoldService] {error_msg}")
                    result.errors.append(error_msg)

            # Process edge functions from bundle
            func_info = self._extract_functions_from_bundle(bundle)
            for func_name, info in func_info.items():
                # Check if function already exists
                if not self.function_service.has_function(func_name):
                    try:
                        created_path = self._scaffold_function(
                            func_name, info, functions_path, options.overwrite_existing
                        )

                        if created_path:
                            result.created_files.append(created_path)
                            result.scaffolded_count += 1
                        else:
                            result.skipped_files.append(
                                functions_path / f"{func_name}.py"
                            )

                    except Exception as e:
                        error_msg = f"Failed to scaffold function {func_name}: {str(e)}"
                        self.logger.error(f"[GraphScaffoldService] {error_msg}")
                        result.errors.append(error_msg)

            # Log service statistics
            if (
                result.service_stats["with_services"] > 0
                or result.service_stats["without_services"] > 0
            ):
                self.logger.info(
                    f"[GraphScaffoldService] ✅ Scaffolded agents: "
                    f"{result.service_stats['with_services']} with services, "
                    f"{result.service_stats['without_services']} without services"
                )

            # Update bundle with current declarations after scaffolding
            # NOTE: Persistence is caller's responsibility to avoid cache interference
            try:
                updated_bundle = (
                    self.bundle_update_service.update_bundle_from_declarations(
                        bundle, persist=False
                    )
                )

                # Log bundle update results
                current_mappings = (
                    len(updated_bundle.agent_mappings)
                    if updated_bundle.agent_mappings
                    else 0
                )
                missing_count = (
                    len(updated_bundle.missing_declarations)
                    if updated_bundle.missing_declarations
                    else 0
                )

                self.logger.info(
                    f"[GraphScaffoldService] ✅ Updated bundle '{updated_bundle.graph_name}': "
                    f"{current_mappings} agent mappings, {missing_count} still missing"
                )
                self.logger.debug(
                    f"[GraphScaffoldService] Bundle persistence left to caller to avoid cache interference"
                )

                # Update result with the updated bundle
                result.updated_bundle = updated_bundle

            except Exception as e:
                self.logger.warning(
                    f"[GraphScaffoldService] Failed to update bundle after scaffolding: {e}"
                )
                # Continue with original bundle
                result.updated_bundle = bundle

            self.logger.info(
                f"[GraphScaffoldService] ✅ Bundle scaffolding complete: "
                f"{result.scaffolded_count} created, {len(result.skipped_files)} skipped, "
                f"{len(result.errors)} errors"
            )

            return result

        except Exception as e:
            error_msg = f"Failed to scaffold from bundle: {str(e)}"
            self.logger.error(f"[GraphScaffoldService] {error_msg}")
            return ScaffoldResult(scaffolded_count=0, errors=[error_msg])

    def get_scaffold_paths(self, graph_name: Optional[str] = None) -> Dict[str, Path]:
        """
        Get standard scaffold paths using app config.

        Args:
            graph_name: Optional graph name (unused but kept for API consistency)

        Returns:
            Dictionary with scaffold paths
        """
        return {
            "agents_path": self.config.get_custom_agents_path(),
            "functions_path": self.config.get_functions_path(),
            "csv_path": self.config.csv_path,
        }

    def _collect_agent_info(
        self, csv_path: Path, graph_name: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        Collect information about agents from the CSV file.

        Args:
            csv_path: Path to the CSV file
            graph_name: Optional graph name to filter by

        Returns:
            Dictionary mapping agent types to their information
        """
        agent_info: Dict[str, Dict] = {}

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows that don't match our graph filter
                if graph_name and row.get("GraphName", "").strip() != graph_name:
                    continue

                # Collect agent information
                agent_type = row.get("AgentType", "").strip()

                # FIXED: Check agent registry to see if agent is already registered
                # If agent is already in registry (builtin or custom), don't scaffold it
                if agent_type and not self.agent_registry.has_agent(agent_type):
                    self.logger.debug(
                        f"[GraphScaffoldService] Found unregistered agent type '{agent_type}' - will scaffold"
                    )
                    node_name = row.get("Node", "").strip()
                    context = row.get("Context", "").strip()
                    prompt = row.get("Prompt", "").strip()
                    input_fields = [
                        x.strip()
                        for x in row.get("Input_Fields", "").split("|")
                        if x.strip()
                    ]
                    output_field = row.get("Output_Field", "").strip()
                    description = row.get("Description", "").strip()

                    if agent_type not in agent_info:
                        agent_info[agent_type] = {
                            "agent_type": agent_type,
                            "node_name": node_name,
                            "context": context,
                            "prompt": prompt,
                            "input_fields": input_fields,
                            "output_field": output_field,
                            "description": description,
                        }
                elif agent_type:
                    # Agent is already registered, skip scaffolding
                    self.logger.debug(
                        f"[GraphScaffoldService] Skipping registered agent type '{agent_type}' - already available"
                    )

        return agent_info

    def _collect_function_info(
        self, csv_path: Path, graph_name: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        Collect information about functions from the CSV file.

        Args:
            csv_path: Path to the CSV file
            graph_name: Optional graph name to filter by

        Returns:
            Dictionary mapping function names to their information
        """

        func_info: Dict[str, Dict] = {}

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows that don't match our graph filter
                if graph_name and row.get("GraphName", "").strip() != graph_name:
                    continue

                # Collect function information
                for col in ["Edge", "Success_Next", "Failure_Next"]:
                    func = self.function_service.extract_func_ref(row.get(col, ""))
                    if func:
                        node_name = row.get("Node", "").strip()
                        context = row.get("Context", "").strip()
                        input_fields = [
                            x.strip()
                            for x in row.get("Input_Fields", "").split("|")
                            if x.strip()
                        ]
                        output_field = row.get("Output_Field", "").strip()
                        success_next = row.get("Success_Next", "").strip()
                        failure_next = row.get("Failure_Next", "").strip()
                        description = row.get("Description", "").strip()

                        if func not in func_info:
                            func_info[func] = {
                                "node_name": node_name,
                                "context": context,
                                "input_fields": input_fields,
                                "output_field": output_field,
                                "success_next": success_next,
                                "failure_next": failure_next,
                                "description": description,
                            }

        return func_info

    def _scaffold_agent(
        self, agent_type: str, info: Dict, output_path: Path, overwrite: bool = False
    ) -> Optional[Path]:
        """
        Scaffold agent class file with service awareness.

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
                    f"[GraphScaffoldService] Scaffolding {agent_type} with services: "
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
            class_name = self._generate_agent_class_name(agent_type)
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
                    f"[GraphScaffoldService] ✅ Generated declaration for {agent_type}"
                )
            except Exception as e:
                self.logger.warning(
                    f"[GraphScaffoldService] Failed to generate declaration for {agent_type}: {e}"
                )

            services_info = (
                f" with services: {', '.join(service_reqs.services)}"
                if service_reqs.services
                else ""
            )
            self.logger.debug(
                f"[GraphScaffoldService] ✅ Scaffolded agent: {file_path}{services_info}"
            )

            return file_path

        except Exception as e:
            self.logger.error(
                f"[GraphScaffoldService] Failed to scaffold agent {agent_type}: {e}"
            )
            raise

    def _scaffold_function(
        self, func_name: str, info: Dict, func_path: Path, overwrite: bool = False
    ) -> Optional[Path]:
        """
        Create a scaffold file for a function.

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

        self.logger.debug(f"[GraphScaffoldService] ✅ Scaffolded function: {file_path}")
        return file_path

    def _generate_agent_class_name(self, agent_type: str) -> str:
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

    def _extract_agent_info_from_bundle(
        self, agent_type: str, bundle: GraphBundle
    ) -> Optional[Dict[str, Any]]:
        """
        Extract agent information from bundle nodes.

        Args:
            agent_type: Agent type to find
            bundle: GraphBundle containing nodes

        Returns:
            Agent info dict or None if not found
        """
        # Search through bundle nodes for matching agent type
        for node_name, node in bundle.nodes.items():
            if node.agent_type.lower() == agent_type.lower():
                # Convert Node object to info dict format expected by _scaffold_agent
                return {
                    "agent_type": agent_type,
                    "node_name": node_name,
                    "context": node.context or "",
                    "prompt": node.prompt or "",
                    "input_fields": node.inputs or [],
                    "output_field": node.output or "",
                    "description": node.description or "",
                }

        return None

    def _extract_functions_from_bundle(
        self, bundle: GraphBundle
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract function information from bundle nodes' edges.

        Args:
            bundle: GraphBundle containing nodes with edges

        Returns:
            Dictionary mapping function names to their info
        """
        func_info = {}

        # Process each node's edges for function references
        for node_name, node in bundle.nodes.items():
            for condition, target in node.edges.items():
                # Check if edge condition is a function reference
                func_name = self.function_service.extract_func_ref(condition)
                if func_name and func_name not in func_info:
                    func_info[func_name] = {
                        "node_name": node_name,
                        "context": node.context or "",
                        "input_fields": node.inputs or [],
                        "output_field": node.output or "",
                        "success_next": (
                            target if condition == f"func:{func_name}" else ""
                        ),
                        "failure_next": "",  # Would need more edge analysis
                        "description": f"Edge function for {node_name} -> {target}",
                    }

        return func_info

    def _to_pascal_case(self, text: str) -> str:
        """
        Convert text to PascalCase, handling underscores and preserving existing case.

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

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the scaffold service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "GraphScaffoldService",
            "config_available": self.config is not None,
            "template_composer_available": self.template_composer is not None,
            "custom_agents_path": str(self.config.get_custom_agents_path()),
            "functions_path": str(self.config.get_functions_path()),
            "csv_path": str(self.config.csv_path),
            "service_parser_available": self.service_parser is not None,
            "architecture_approach": "unified_template_composition",
            "supported_services": list(self.service_parser.separate_service_map.keys()),
            "unified_services": list(self.service_parser.unified_service_map.keys()),
            "template_composer_handles": ["agent_templates", "function_templates"],
        }
