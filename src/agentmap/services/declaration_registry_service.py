"""
Declaration registry service for AgentMap.

Main service that combines multiple declaration sources and provides requirement
resolution WITHOUT loading implementation classes. Eliminates circular dependencies
by resolving requirements at the declaration level only.

This module also provides RunScopedDeclarationRegistry for thread-safe, isolated
per-graph-run declaration access that eliminates race conditions in concurrent execution.
"""

from types import MappingProxyType
from typing import Any, Callable, Dict, List, Mapping, Optional, Set

from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration
from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.declaration_sources import DeclarationSource
from agentmap.services.logging_service import LoggingService

# =============================================================================
# Shared Utility Functions
# =============================================================================
# These functions contain the core resolution logic shared between
# DeclarationRegistryService (mutable singleton) and RunScopedDeclarationRegistry
# (immutable per-run copy). Extracting them avoids code duplication.


def resolve_service_dependencies_recursive(
    service_names: Set[str],
    services: Mapping[str, ServiceDeclaration],
    visited: Set[str],
    get_declaration: Callable[[str], Optional[ServiceDeclaration]],
    log_warning: Optional[Callable[[str], None]] = None,
) -> Set[str]:
    """
    Recursively resolve service dependencies with cycle detection.

    Args:
        service_names: Set of service names to resolve
        services: Mapping of service name to ServiceDeclaration (read-only)
        visited: Set of already visited services (for cycle detection)
        get_declaration: Function to retrieve service declaration by name
        log_warning: Optional callback for logging warnings (circular deps, missing services)

    Returns:
        Set of all required service names including dependencies
    """
    all_services = set(service_names)

    for service_name in service_names:
        if service_name in visited:
            if log_warning:
                log_warning(f"Circular dependency detected for service: {service_name}")
            continue

        service_decl = get_declaration(service_name)
        if not service_decl:
            if log_warning:
                log_warning(f"Service declaration not found: {service_name}")
            continue

        # Mark as visited for cycle detection
        new_visited = visited | {service_name}

        # Recursively resolve dependencies
        dependencies = set(service_decl.required_dependencies)
        if dependencies:
            resolved_deps = resolve_service_dependencies_recursive(
                dependencies, services, new_visited, get_declaration, log_warning
            )
            all_services.update(resolved_deps)

    return all_services


def get_services_implementing_protocols(
    protocols: Set[str],
    services: Mapping[str, ServiceDeclaration],
) -> Set[str]:
    """
    Find services that implement any of the given protocols.

    Args:
        protocols: Set of protocol names to search for
        services: Mapping of service name to ServiceDeclaration (read-only)

    Returns:
        Set of service names that implement at least one of the protocols
    """
    result = set()
    for service_name, service_decl in services.items():
        service_protocols = set(service_decl.implements_protocols)
        if protocols & service_protocols:  # Set intersection
            result.add(service_name)
    return result


def resolve_agent_requirements_from_declarations(
    agent_types: Set[str],
    agents: Mapping[str, AgentDeclaration],
    services: Mapping[str, ServiceDeclaration],
    get_agent_decl: Callable[[str], Optional[AgentDeclaration]],
    get_service_decl: Callable[[str], Optional[ServiceDeclaration]],
    log_warning: Optional[Callable[[str], None]] = None,
    log_debug: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Resolve all requirements for given agent types.

    Args:
        agent_types: Set of agent types to resolve requirements for
        agents: Mapping of agent type to AgentDeclaration (read-only)
        services: Mapping of service name to ServiceDeclaration (read-only)
        get_agent_decl: Function to retrieve agent declaration by type
        get_service_decl: Function to retrieve service declaration by name
        log_warning: Optional callback for logging warnings
        log_debug: Optional callback for debug logging

    Returns:
        Dictionary with 'services', 'protocols', and 'missing' keys
    """
    if log_debug:
        log_debug(f"Resolving requirements for {len(agent_types)} agent types")

    required_services: Set[str] = set()
    required_protocols: Set[str] = set()
    missing_agents: Set[str] = set()

    # Collect requirements from all agents
    for agent_type in agent_types:
        agent_decl = get_agent_decl(agent_type)
        if not agent_decl:
            missing_agents.add(agent_type)
            continue

        required_services.update(agent_decl.get_required_services())
        required_protocols.update(agent_decl.get_required_protocols())

    # Resolve service dependencies recursively
    agent_services = resolve_service_dependencies_recursive(
        required_services, services, set(), get_service_decl, log_warning
    )
    protocol_services = get_services_implementing_protocols(
        required_protocols, services
    )
    all_services = agent_services | protocol_services

    return {
        "services": all_services,
        "protocols": required_protocols,
        "missing": missing_agents,
    }


def build_protocol_service_map(
    services: Mapping[str, ServiceDeclaration],
) -> Dict[str, str]:
    """
    Build a mapping from protocol names to implementing service names.

    Note: If multiple services implement the same protocol, the last one
    encountered will be used. This is intentional for scoped registries
    where each protocol should map to exactly one service.

    Args:
        services: Mapping of service name to ServiceDeclaration (read-only)

    Returns:
        Dict mapping protocol names to implementing service names
    """
    protocol_mapping: Dict[str, str] = {}
    for service_name, service_decl in services.items():
        for protocol in service_decl.implements_protocols:
            protocol_mapping[protocol] = service_name
    return protocol_mapping


# =============================================================================
# RunScopedDeclarationRegistry
# =============================================================================


class RunScopedDeclarationRegistry:
    """
    Immutable, thread-safe declaration registry for a single graph run.

    This class provides isolated access to declarations for a specific graph execution,
    eliminating race conditions that occur when multiple concurrent graph runs share
    the singleton DeclarationRegistryService.

    Key properties:
    - Immutable: Cannot be modified after creation (uses MappingProxyType)
    - Thread-safe: Safe for concurrent read access from multiple threads
    - Isolated: Each graph run gets its own filtered copy of declarations
    - Lightweight: Only contains declarations needed for the specific run

    Usage:
        # Created by DeclarationRegistryService.create_scoped_registry_for_bundle()
        scoped_registry = registry_service.create_scoped_registry_for_bundle(bundle)

        # Then used for read-only access during graph execution
        agent_decl = scoped_registry.get_agent_declaration("MyAgent")
        service_decl = scoped_registry.get_service_declaration("my_service")
    """

    def __init__(
        self,
        agents: Dict[str, AgentDeclaration],
        services: Dict[str, ServiceDeclaration],
    ):
        """
        Initialize with copies of agent and service declarations.

        Args:
            agents: Dictionary of agent type to AgentDeclaration (will be copied)
            services: Dictionary of service name to ServiceDeclaration (will be copied)
        """
        # Create immutable copies using MappingProxyType
        # This prevents any modifications after creation
        self._agents: MappingProxyType = MappingProxyType(dict(agents))
        self._services: MappingProxyType = MappingProxyType(dict(services))

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

    def get_all_agent_types(self) -> List[str]:
        """Get list of all available agent types."""
        return list(self._agents.keys())

    def get_all_service_names(self) -> List[str]:
        """Get list of all available service names."""
        return list(self._services.keys())

    def get_services_by_protocols(self, protocols: Set[str]) -> Set[str]:
        """
        Returns a set of service names that implement any of the given protocols.

        Args:
            protocols: Set of protocol names to search for

        Returns:
            Set of service names that implement at least one of the protocols
        """
        return get_services_implementing_protocols(protocols, self._services)

    def resolve_agent_requirements(self, agent_types: Set[str]) -> Dict[str, Any]:
        """
        Resolve all requirements for given agent types.

        Args:
            agent_types: Set of agent types to resolve requirements for

        Returns:
            Dictionary with 'services', 'protocols', and 'missing' keys
        """
        return resolve_agent_requirements_from_declarations(
            agent_types=agent_types,
            agents=self._agents,
            services=self._services,
            get_agent_decl=self.get_agent_declaration,
            get_service_decl=self.get_service_declaration,
        )

    def resolve_service_dependencies(self, service_names: Set[str]) -> Set[str]:
        """
        Resolve service dependencies recursively.

        Args:
            service_names: Set of service names to resolve dependencies for

        Returns:
            Set of all required service names including dependencies
        """
        return resolve_service_dependencies_recursive(
            service_names=service_names,
            services=self._services,
            visited=set(),
            get_declaration=self.get_service_declaration,
        )

    def get_protocol_service_map(self) -> Dict[str, str]:
        """
        Builds a mapping from protocol names to service names that implement them.

        Returns:
            Dict mapping protocol names to implementing service names
        """
        return build_protocol_service_map(self._services)


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

    def resolve_agent_requirements(self, agent_types: Set[str]) -> Dict[str, Any]:
        """
        Resolve all requirements for given agent types.

        Args:
            agent_types: Set of agent types to resolve requirements for

        Returns:
            Dictionary with 'services', 'protocols', and 'missing' keys
        """
        return resolve_agent_requirements_from_declarations(
            agent_types=agent_types,
            agents=self._agents,
            services=self._services,
            get_agent_decl=self.get_agent_declaration,
            get_service_decl=self.get_service_declaration,
            log_warning=self.logger.warning,
            log_debug=self.logger.debug,
        )

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

    def get_services_by_protocols(self, protocols: Set[str]) -> Set[str]:
        """
        Returns a set of service names that implement any of the given protocols.

        Args:
            protocols: Set of protocol names to search for

        Returns:
            Set of service names that implement at least one of the protocols
        """
        return get_services_implementing_protocols(protocols, self._services)

    def resolve_service_dependencies(self, service_names: Set[str]) -> Set[str]:
        """
        Resolve service dependencies recursively.

        Args:
            service_names: Set of service names to resolve dependencies for

        Returns:
            Set of all required service names including dependencies
        """
        return resolve_service_dependencies_recursive(
            service_names=service_names,
            services=self._services,
            visited=set(),
            get_declaration=self.get_service_declaration,
            log_warning=self.logger.warning,
        )

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

    def get_protocol_service_map(self) -> Dict[str, str]:
        """
        Builds a mapping from protocol names to implementing service names.

        Note: If multiple services implement the same protocol, the last one
        encountered will be used.

        Returns:
            Dict mapping protocol names to implementing service names
        """
        return build_protocol_service_map(self._services)

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

    def create_scoped_registry_for_bundle(
        self, bundle: GraphBundle
    ) -> RunScopedDeclarationRegistry:
        """
        Create an isolated, immutable registry scoped to a specific graph bundle.

        This method creates a new RunScopedDeclarationRegistry containing only the
        declarations needed for the given bundle. The scoped registry is:
        - Thread-safe: Safe for concurrent read access
        - Immutable: Cannot be modified after creation
        - Isolated: Does NOT affect the singleton's internal state

        This eliminates race conditions in concurrent graph execution by giving each
        run its own isolated copy of declarations.

        Args:
            bundle: GraphBundle containing required_agents and required_services

        Returns:
            RunScopedDeclarationRegistry with filtered declarations for the bundle
        """
        self.logger.debug(f"Creating scoped registry for bundle: {bundle.graph_name}")

        # Extract requirements from bundle
        required_agents = getattr(bundle, "required_agents", None)
        required_services = getattr(bundle, "required_services", None)

        # Convert to sets if needed
        if required_agents and not isinstance(required_agents, set):
            required_agents = set(required_agents)
        if required_services and not isinstance(required_services, set):
            required_services = set(required_services)

        # Always include core infrastructure services
        core_services = {
            "logging_service",
            "execution_tracking_service",
            "state_adapter_service",
            "prompt_manager_service",
        }

        if required_services:
            required_services = required_services | core_services
        else:
            if required_agents:
                required_services = core_services
            else:
                required_services = set()

        if required_agents is None:
            required_agents = set()

        # Filter agents from current singleton state (without modifying it)
        filtered_agents: Dict[str, AgentDeclaration] = {}
        for agent_type in required_agents:
            agent_decl = self._agents.get(agent_type)
            if agent_decl:
                filtered_agents[agent_type] = agent_decl

        # Filter services from current singleton state (without modifying it)
        filtered_services: Dict[str, ServiceDeclaration] = {}
        for service_name in required_services:
            service_decl = self._services.get(service_name)
            if service_decl:
                filtered_services[service_name] = service_decl

        self.logger.debug(
            f"Scoped registry created with {len(filtered_agents)} agents "
            f"and {len(filtered_services)} services for {bundle.graph_name}"
        )

        return RunScopedDeclarationRegistry(
            agents=filtered_agents,
            services=filtered_services,
        )
