"""
Graph scaffold coordinator service.

This module provides the main orchestration service for scaffolding
agent classes and edge functions from graph definitions.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.scaffold_types import (
    ScaffoldOptions,
    ScaffoldResult,
)
from agentmap.services.agent.agent_registry_service import AgentRegistryService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.custom_agent_declaration_manager import (
    CustomAgentDeclarationManager,
)
from agentmap.services.function_resolution_service import FunctionResolutionService
from agentmap.services.graph.bundle_update_service import BundleUpdateService
from agentmap.services.graph.scaffold.bundle_extractor import BundleExtractor
from agentmap.services.graph.scaffold.csv_collector import CSVCollector
from agentmap.services.graph.scaffold.name_utils import generate_agent_class_name
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

        # Initialize extracted components
        self.bundle_extractor = BundleExtractor(function_resolution_service)
        self.csv_collector = CSVCollector(
            agent_registry_service, function_resolution_service, logging_service
        )

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

            # Process agents
            agents_to_scaffold = self._get_agents_to_scaffold(bundle, options)
            self._scaffold_agents(
                agents_to_scaffold, bundle, agents_path, options, result
            )

            # Process edge functions from bundle
            self._scaffold_functions_from_bundle(bundle, functions_path, options, result)

            # Log service statistics
            self._log_service_stats(result)

            # Update bundle with current declarations after scaffolding
            result.updated_bundle = self._update_bundle_declarations(bundle)

            self.logger.info(
                f"[GraphScaffoldService] Bundle scaffolding complete: "
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

    # Delegate methods to extracted components for backwards compatibility

    def _collect_agent_info(
        self, csv_path: Path, graph_name: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        Collect information about agents from the CSV file.

        Delegates to CSVCollector for implementation.
        """
        return self.csv_collector.collect_agent_info(csv_path, graph_name)

    def _collect_function_info(
        self, csv_path: Path, graph_name: Optional[str] = None
    ) -> Dict[str, Dict]:
        """
        Collect information about functions from the CSV file.

        Delegates to CSVCollector for implementation.
        """
        return self.csv_collector.collect_function_info(csv_path, graph_name)

    def _extract_agent_info_from_bundle(
        self, agent_type: str, bundle: GraphBundle
    ) -> Optional[Dict[str, Any]]:
        """
        Extract agent information from bundle nodes.

        Delegates to BundleExtractor for implementation.
        """
        return self.bundle_extractor.extract_agent_info(agent_type, bundle)

    def _extract_functions_from_bundle(
        self, bundle: GraphBundle
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract function information from bundle nodes' edges.

        Delegates to BundleExtractor for implementation.
        """
        return self.bundle_extractor.extract_functions(bundle)

    def _generate_agent_class_name(self, agent_type: str) -> str:
        """
        Generate proper PascalCase class name for agent.

        Delegates to name_utils module for implementation.
        """
        return generate_agent_class_name(agent_type)

    def _to_pascal_case(self, text: str) -> str:
        """
        Convert text to PascalCase.

        Delegates to name_utils module for implementation.
        """
        from agentmap.services.graph.scaffold.name_utils import to_pascal_case
        return to_pascal_case(text)

    # Private helper methods

    def _get_agents_to_scaffold(
        self, bundle: GraphBundle, options: ScaffoldOptions
    ) -> List[str]:
        """Determine which agents need to be scaffolded."""
        if options.force_rescaffold:
            agents = list(bundle.custom_agents or set())
            self.logger.info(
                f"[GraphScaffoldService] Force rescaffold enabled: processing {len(agents)} custom agents"
            )
        else:
            agents = list(bundle.missing_declarations or set())
            self.logger.info(
                f"[GraphScaffoldService] Found {len(agents)} missing agents to scaffold"
            )
        return agents

    def _scaffold_agents(
        self,
        agents_to_scaffold: List[str],
        bundle: GraphBundle,
        agents_path: Path,
        options: ScaffoldOptions,
        result: ScaffoldResult,
    ) -> None:
        """Scaffold all agents in the list."""
        for agent_type in agents_to_scaffold:
            agent_info = self._extract_agent_info_from_bundle(agent_type, bundle)

            if not agent_info:
                self.logger.warning(
                    f"[GraphScaffoldService] No node found for agent type: {agent_type}"
                )
                continue

            try:
                created_path = self._scaffold_agent(
                    agent_type, agent_info, agents_path, options.overwrite_existing
                )

                if created_path:
                    result.created_files.append(created_path)
                    result.scaffolded_count += 1

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

    def _scaffold_functions_from_bundle(
        self,
        bundle: GraphBundle,
        functions_path: Path,
        options: ScaffoldOptions,
        result: ScaffoldResult,
    ) -> None:
        """Scaffold all functions extracted from the bundle."""
        func_info = self._extract_functions_from_bundle(bundle)
        for func_name, info in func_info.items():
            if not self.function_service.has_function(func_name):
                try:
                    created_path = self._scaffold_function(
                        func_name, info, functions_path, options.overwrite_existing
                    )

                    if created_path:
                        result.created_files.append(created_path)
                        result.scaffolded_count += 1
                    else:
                        result.skipped_files.append(functions_path / f"{func_name}.py")

                except Exception as e:
                    error_msg = f"Failed to scaffold function {func_name}: {str(e)}"
                    self.logger.error(f"[GraphScaffoldService] {error_msg}")
                    result.errors.append(error_msg)

    def _log_service_stats(self, result: ScaffoldResult) -> None:
        """Log service statistics from scaffolding result."""
        if (
            result.service_stats["with_services"] > 0
            or result.service_stats["without_services"] > 0
        ):
            self.logger.info(
                f"[GraphScaffoldService] Scaffolded agents: "
                f"{result.service_stats['with_services']} with services, "
                f"{result.service_stats['without_services']} without services"
            )

    def _update_bundle_declarations(self, bundle: GraphBundle) -> GraphBundle:
        """Update bundle with current declarations after scaffolding."""
        try:
            updated_bundle = (
                self.bundle_update_service.update_bundle_from_declarations(
                    bundle, persist=False
                )
            )

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
                f"[GraphScaffoldService] Updated bundle '{updated_bundle.graph_name}': "
                f"{current_mappings} agent mappings, {missing_count} still missing"
            )
            self.logger.debug(
                f"[GraphScaffoldService] Bundle persistence left to caller to avoid cache interference"
            )

            return updated_bundle

        except Exception as e:
            self.logger.warning(
                f"[GraphScaffoldService] Failed to update bundle after scaffolding: {e}"
            )
            return bundle

    def _scaffold_agent(
        self, agent_type: str, info: Dict, output_path: Path, overwrite: bool = False
    ) -> Optional[Path]:
        """Scaffold agent class file with service awareness."""
        file_name = f"{agent_type.lower()}_agent.py"
        file_path = output_path / file_name

        if file_path.exists() and not overwrite:
            return None

        try:
            service_reqs = self.service_parser.parse_services(info.get("context"))

            if service_reqs.services:
                self.logger.debug(
                    f"[GraphScaffoldService] Scaffolding {agent_type} with services: "
                    f"{', '.join(service_reqs.services)}"
                )

            formatted_template = self.template_composer.compose_template(
                agent_type, info, service_reqs
            )

            with file_path.open("w") as out:
                out.write(formatted_template)

            class_name = self._generate_agent_class_name(agent_type)
            class_path = f"{agent_type.lower()}_agent.{class_name}"

            try:
                self.custom_agent_declaration_manager.add_or_update_agent(
                    agent_type=agent_type,
                    class_path=class_path,
                    services=service_reqs.services,
                    protocols=service_reqs.protocols,
                )
                self.logger.debug(
                    f"[GraphScaffoldService] Generated declaration for {agent_type}"
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
                f"[GraphScaffoldService] Scaffolded agent: {file_path}{services_info}"
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
        """Create a scaffold file for a function."""
        file_name = f"{func_name}.py"
        file_path = func_path / file_name

        if file_path.exists() and not overwrite:
            return None

        formatted_template = self.template_composer.compose_function_template(
            func_name, info
        )

        with file_path.open("w") as out:
            out.write(formatted_template)

        self.logger.debug(f"[GraphScaffoldService] Scaffolded function: {file_path}")
        return file_path
