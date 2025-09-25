"""
Declaration registry service for AgentMap.

Main service that combines multiple declaration sources and provides requirement
resolution WITHOUT loading implementation classes. Eliminates circular dependencies
by resolving requirements at the declaration level only.
"""

from typing import Dict, List, Optional, Set

from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.declaration_sources import DeclarationSource
from agentmap.services.logging_service import LoggingService


class DeclarationRegistryService:
    """
    Main declaration registry service that combines multiple sources.

    Provides requirement resolution without loading implementation classes,
    eliminating circular dependencies through declaration-only analysis.
    """

    def __init__(
        self, app_config_service: AppConfigService, logging_service: LoggingService
    ):
        """Initialize with dependency injection."""
        self.app_config_service = app_config_service
        self.logger = logging_service.get_class_logger(self)

        # Core data storage
        self._sources: List[DeclarationSource] = []
        self._agents: Dict[str, AgentDeclaration] = {}
        self._services: Dict[str, ServiceDeclaration] = {}

    def add_source(self, source: DeclarationSource) -> None:
        """
        Add a declaration source to the registry.

        Args:
            source: Declaration source to add
        """
        self._sources.append(source)
        self.logger.debug(f"Added declaration source: {type(source).__name__}")

    def load_all(self) -> None:
        """
        Reload declarations from all sources.

        Later sources override earlier ones to enable customization.
        """
        self.logger.debug("Loading declarations from all sources")

        # Clear existing declarations
        self._agents.clear()
        self._services.clear()

        # Load from each source in order (later sources override)
        for source in self._sources:
            self._load_from_source(source)

        self.logger.info(
            f"Loaded {len(self._agents)} agents and {len(self._services)} services"
        )

    def get_agent_declaration(self, agent_type: str) -> Optional[AgentDeclaration]:
        """
        Get agent declaration by type.

        Args:
            agent_type: Type of agent to find

        Returns:
            AgentDeclaration if found, None otherwise
        """
        return self._agents.get(agent_type)

    def get_service_declaration(
        self, service_name: str
    ) -> Optional[ServiceDeclaration]:
        """
        Get service declaration by name.

        Args:
            service_name: Name of service to find

        Returns:
            ServiceDeclaration if found, None otherwise
        """
        return self._services.get(service_name)

    def resolve_agent_requirements(self, agent_types: Set[str]) -> Dict[str, any]:
        """
        Resolve all requirements for given agent types.

        Args:
            agent_types: Set of agent types to resolve requirements for

        Returns:
            Dictionary with 'services', 'protocols', and 'missing' keys
        """
        self.logger.debug(f"Resolving requirements for {len(agent_types)} agent types")

        required_services = set()
        required_protocols = set()
        missing_agents = set()

        # Collect requirements from all agents
        for agent_type in agent_types:
            agent_decl = self.get_agent_declaration(agent_type)
            if not agent_decl:
                missing_agents.add(agent_type)
                continue

            required_services.update(agent_decl.get_required_services())
            required_protocols.update(agent_decl.get_required_protocols())

        # Resolve service dependencies recursively
        agent_services = self._resolve_service_dependencies(required_services, set())
        protocol_services = self.get_services_by_protocols(required_protocols)
        all_services = agent_services | protocol_services

        return {
            "services": all_services,
            "protocols": required_protocols,
            "missing": missing_agents,
        }

    def get_all_agent_types(self) -> List[str]:
        """Get list of all available agent types."""
        return list(self._agents.keys())

    def get_all_service_names(self) -> List[str]:
        """Get list of all available service names."""
        return list(self._services.keys())

    def add_agent_declaration(self, declaration: AgentDeclaration) -> None:
        """
        Add agent declaration directly (for testing/dynamic scenarios).

        Args:
            declaration: Agent declaration to add
        """
        self._agents[declaration.agent_type] = declaration
        self.logger.debug(f"Added dynamic agent declaration: {declaration.agent_type}")

    def add_service_declaration(self, declaration: ServiceDeclaration) -> None:
        """
        Add service declaration directly (for testing/dynamic scenarios).

        Args:
            declaration: Service declaration to add
        """
        self._services[declaration.service_name] = declaration
        self.logger.debug(
            f"Added dynamic service declaration: {declaration.service_name}"
        )

    def _load_configured_sources(self) -> None:
        """Load declaration sources from configuration."""
        # TODO: Implement when app config structure is defined
        self.logger.debug("Configuration-based source loading not yet implemented")

    def _load_from_source(self, source: DeclarationSource) -> None:
        """
        Load declarations from a single source.

        Args:
            source: Declaration source to load from
        """
        try:
            # Load agents (later sources override)
            agents = source.load_agents()
            self._agents.update(agents)
            self.logger.debug(
                f"Loaded {len(agents)} agents from {type(source).__name__}"
            )

            # Load services (later sources override)
            services = source.load_services()
            self._services.update(services)
            self.logger.debug(
                f"Loaded {len(services)} services from {type(source).__name__}"
            )

        except Exception as e:
            self.logger.error(
                f"Failed to load from source {type(source).__name__}: {e}"
            )

    def _resolve_service_dependencies(
        self, service_names: Set[str], visited: Set[str]
    ) -> Set[str]:
        """
        Recursively resolve service dependencies with cycle detection.

        Args:
            service_names: Set of service names to resolve
            visited: Set of already visited services (for cycle detection)

        Returns:
            Set of all required service names including dependencies
        """
        all_services = set(service_names)

        for service_name in service_names:
            if service_name in visited:
                self.logger.warning(
                    f"Circular dependency detected for service: {service_name}"
                )
                continue

            service_decl = self.get_service_declaration(service_name)
            if not service_decl:
                self.logger.warning(f"Service declaration not found: {service_name}")
                continue

            # Mark as visited for cycle detection
            new_visited = visited | {service_name}

            # Recursively resolve dependencies
            dependencies = set(service_decl.required_dependencies)
            if dependencies:
                resolved_deps = self._resolve_service_dependencies(
                    dependencies, new_visited
                )
                all_services.update(resolved_deps)

        return all_services

    def get_services_by_protocols(self, protocols: set[str]) -> set[str]:
        """
        Returns a list of service names that implement any of the given protocols.

        Args:
            protocols: Set of protocol names to search for

        Returns:
            List of service names that implement at least one of the protocols
        """
        services = set()
        for service_name, service_config in self._services.items():
            service_protocols = set(service_config.implements_protocols)
            if protocols & service_protocols:  # Set intersection
                services.add(service_name)
        return services

    def resolve_service_dependencies(self, service_names: Set[str]) -> Set[str]:
        """
        Public method to resolve service dependencies.

        Args:
            service_names: Set of service names to resolve dependencies for

        Returns:
            Set of all required service names including dependencies
        """
        return self._resolve_service_dependencies(service_names, set())

    def calculate_load_order(self, service_names: Set[str]) -> List[str]:
        """
        Calculate the load order for services based on their dependencies.

        Args:
            service_names: Set of service names to calculate load order for

        Returns:
            List of service names in dependency order (dependencies first)
        """
        # Simple topological sort - for now just return sorted list
        # TODO: Implement proper topological sort based on dependencies
        return sorted(list(service_names))

    def get_protcol_service_map(self) -> dict[str, str]:
        """
        Builds a mapping from protocol names to sets of service names that implement them.

        Returns:
            Dict mapping protocol names to sets of implementing service names
        """
        protocol_mapping: dict[str, set[str]] = {}

        for service_name, service_config in self._services.items():
            for protocol in service_config.implements_protocols:
                protocol_mapping[protocol] = service_name

        return protocol_mapping

    def load_selective(
        self,
        required_agents: Optional[Set[str]] = None,
        required_services: Optional[Set[str]] = None,
    ) -> None:
        """
        Load only the specified agents and services from declaration sources.

        This method allows selective loading based on bundle requirements,
        significantly reducing memory usage and startup time.

        Args:
            required_agents: Set of agent types to load (None = load all)
            required_services: Set of service names to load (None = load all)
        """
        # If no requirements specified, fall back to loading all
        if required_agents is None and required_services is None:
            self.logger.debug(
                "No selective requirements provided, loading all declarations"
            )
            self.load_all()
            return

        self.logger.debug(
            f"Selective loading: {len(required_agents or [])} agents, {len(required_services or [])} services"
        )

        # Clear existing declarations
        self._agents.clear()
        self._services.clear()

        # Load from each source in order (later sources override)
        for source in self._sources:
            try:
                # Load only required agents
                if required_agents is not None:
                    agents = source.load_agents()
                    # Filter to only required agents
                    filtered_agents = {
                        agent_type: decl
                        for agent_type, decl in agents.items()
                        if agent_type in required_agents
                    }
                    self._agents.update(filtered_agents)
                    if filtered_agents:
                        self.logger.debug(
                            f"Loaded {len(filtered_agents)} agents from {type(source).__name__}"
                        )

                # Load only required services
                if required_services is not None:
                    services = source.load_services()
                    # Filter to only required services
                    filtered_services = {
                        service_name: decl
                        for service_name, decl in services.items()
                        if service_name in required_services
                    }
                    self._services.update(filtered_services)
                    if filtered_services:
                        self.logger.debug(
                            f"Loaded {len(filtered_services)} services from {type(source).__name__}"
                        )

            except Exception as e:
                self.logger.error(
                    f"Failed to load from source {type(source).__name__}: {e}"
                )

        self.logger.info(
            f"Selective load complete: {len(self._agents)} agents, {len(self._services)} services"
        )

    def load_for_bundle(self, bundle: GraphBundle) -> None:
        """
        Load only the declarations required by a specific graph bundle.

        This is a convenience method that extracts requirements from a bundle
        and performs selective loading.

        Args:
            bundle: GraphBundle containing required_agents and required_services
        """
        required_agents = getattr(bundle, "required_agents", None)
        required_services = getattr(bundle, "required_services", None)

        # Convert to sets if needed
        if required_agents and not isinstance(required_agents, set):
            required_agents = set(required_agents)
        if required_services and not isinstance(required_services, set):
            required_services = set(required_services)

        # Always include core infrastructure services even if not in bundle
        # These are needed for basic operation
        core_services = {
            "logging_service",
            "execution_tracking_service",
            "state_adapter_service",
            "prompt_manager_service",
        }

        if required_services:
            required_services = required_services | core_services
        else:
            # If no services specified but we have agents, include core services
            if required_agents:
                required_services = core_services

        self.load_selective(required_agents, required_services)
