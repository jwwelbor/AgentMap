"""
HostServiceRegistry for AgentMap host application integration.

Service for managing dynamic registration of host services and protocols.
This class provides the core functionality for storing service providers,
protocol implementations, and metadata without affecting AgentMap's core DI container.
"""

import importlib
from typing import Any, Dict, List, Optional, Type

from agentmap.services.logging_service import LoggingService

# Import all mixins and utilities
from agentmap.services.protocol_validation import is_valid_protocol
from agentmap.services.registry_diagnostics import DiagnosticsMixin
from agentmap.services.registry_operations import RegistrationMixin
from agentmap.services.registry_queries import QueryMixin
from agentmap.services.registry_storage import RegistryStorageMixin


class HostServiceRegistry(
    RegistryStorageMixin, RegistrationMixin, QueryMixin, DiagnosticsMixin
):
    """
    Service for managing host service and protocol registration and lookup.

    This registry manages dynamic registration of host services and protocols,
    enabling host applications to extend AgentMap's service injection system
    while maintaining separation from core AgentMap functionality.
    """

    def __init__(self, logging_service: LoggingService):
        """
        Initialize registry with dependency injection.

        Args:
            logging_service: LoggingService instance for consistent logging
        """
        self.logger = logging_service.get_class_logger(self)

        # Initialize storage from mixin
        self._init_storage()

        self.logger.debug("[HostServiceRegistry] Initialized")

    def _is_valid_protocol(self, protocol: Type) -> bool:
        """
        Validate that an object is a proper protocol type.

        This method wraps the standalone is_valid_protocol function
        for backwards compatibility.

        Args:
            protocol: Object to validate as a protocol

        Returns:
            True if the object is a valid protocol type
        """
        return is_valid_protocol(protocol, self.logger)


def _import_class(class_path: str) -> type:
    """
    Dynamically import a class from its fully-qualified path.

    Args:
        class_path: Fully-qualified class path (e.g., 'myapp.services.MyService')

    Returns:
        The imported class

    Raises:
        ImportError: If the module or class cannot be found
    """
    module_path, _, class_name = class_path.rpartition(".")
    if not module_path:
        raise ImportError(f"Invalid class path (no module): {class_path}")
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name, None)
    if cls is None:
        raise ImportError(f"Class '{class_name}' not found in module '{module_path}'")
    return cls


def _topological_sort(
    declarations: Dict[str, Any],
) -> List[str]:
    """
    Topologically sort service names by their dependencies.

    Args:
        declarations: Dict mapping service names to ServiceDeclaration objects

    Returns:
        List of service names in dependency order (dependencies first)

    Raises:
        ValueError: If a circular dependency is detected
    """
    visited: Dict[str, int] = {}  # 0=visiting, 1=visited
    result: List[str] = []

    def visit(name: str) -> None:
        if name in visited:
            if visited[name] == 0:
                raise ValueError(f"Circular dependency detected involving '{name}'")
            return
        visited[name] = 0
        decl = declarations.get(name)
        if decl:
            for dep in decl.required_dependencies:
                if dep in declarations:
                    visit(dep)
        visited[name] = 1
        result.append(name)

    for name in declarations:
        visit(name)

    return result


def bootstrap_from_declarations(
    declaration_registry_service: Any,
    host_service_registry: "HostServiceRegistry",
    app_config_service: Optional[Any] = None,
    logger: Optional[Any] = None,
) -> int:
    """
    Bootstrap host services from declarative YAML sources.

    Queries the DeclarationRegistryService for service declarations sourced from
    host_services.yaml, topologically sorts them by dependencies, dynamically imports
    and instantiates each service class, resolves protocol types, and registers
    everything in the HostServiceRegistry.

    Args:
        declaration_registry_service: The declaration registry containing service declarations
        host_service_registry: The host service registry to populate
        app_config_service: Optional app config for merging host service configuration
        logger: Optional logger for diagnostic output

    Returns:
        Number of host services successfully bootstrapped
    """
    from agentmap.services.declaration_sources import HostServiceYAMLSource

    # Collect host service declarations (those sourced from host_services.yaml)
    all_service_names = declaration_registry_service.get_all_service_names()
    host_declarations: Dict[str, Any] = {}

    for service_name in all_service_names:
        decl = declaration_registry_service.get_service_declaration(service_name)
        if decl and decl.source.startswith(
            HostServiceYAMLSource.HOST_SERVICES_SOURCE_PREFIX
        ):
            host_declarations[service_name] = decl

    if not host_declarations:
        if logger:
            logger.debug("No host service declarations found to bootstrap")
        return 0

    if logger:
        logger.info(
            f"Bootstrapping {len(host_declarations)} host services from declarations"
        )

    # Topologically sort by dependencies
    try:
        sorted_names = _topological_sort(host_declarations)
    except ValueError as e:
        if logger:
            logger.error(f"Host service dependency error: {e}")
        return 0

    # Cache of instantiated services for dependency injection
    instances: Dict[str, Any] = {}
    bootstrapped = 0

    for service_name in sorted_names:
        decl = host_declarations[service_name]
        try:
            # Import the service class
            service_class = _import_class(decl.class_path)

            # Build config: start with declaration config, merge app config overrides
            config = dict(decl.config) if decl.config else {}
            if app_config_service:
                try:
                    app_host_config = app_config_service.get_host_service_config(
                        service_name
                    )
                    yaml_config = app_host_config.get("configuration", {})
                    # App config values are defaults; declaration config wins
                    merged = dict(yaml_config)
                    merged.update(config)
                    config = merged
                except Exception as e:
                    if logger:
                        logger.debug(f"Could not get app config override for '{service_name}': {e}")
                    # No app config override, use declaration config only

            # Resolve dependency instances
            dep_instances = {}
            for dep_name in decl.required_dependencies:
                if dep_name in instances:
                    dep_instances[dep_name] = instances[dep_name]
                elif host_service_registry.is_service_registered(dep_name):
                    provider = host_service_registry.get_service_provider(dep_name)
                    if callable(provider):
                        dep_instances[dep_name] = provider()
                    else:
                        dep_instances[dep_name] = provider

            # Instantiate the service
            if decl.factory_method:
                factory = getattr(service_class, decl.factory_method)
                instance = factory(**config, **dep_instances)
            else:
                instance = service_class(**config, **dep_instances)

            instances[service_name] = instance

            # Resolve protocol types
            resolved_protocols: List[type] = []
            for protocol_path in decl.implements_protocols:
                try:
                    protocol_type = _import_class(protocol_path)
                    resolved_protocols.append(protocol_type)
                except ImportError as ie:
                    if logger:
                        logger.warning(
                            f"Could not import protocol '{protocol_path}' "
                            f"for service '{service_name}': {ie}"
                        )

            # Register in the host service registry
            host_service_registry.register_service_provider(
                service_name,
                instance,
                protocols=resolved_protocols if resolved_protocols else None,
                metadata={
                    "source": "host_services.yaml",
                    "class_path": decl.class_path,
                },
            )

            bootstrapped += 1
            if logger:
                logger.info(
                    f"Bootstrapped host service '{service_name}' "
                    f"({decl.class_path}) with {len(resolved_protocols)} protocols"
                )

        except Exception as e:
            if logger:
                logger.error(f"Failed to bootstrap host service '{service_name}': {e}")

    if logger:
        logger.info(
            f"Host service bootstrap complete: {bootstrapped}/{len(host_declarations)} services"
        )

    return bootstrapped


# Re-export components for backwards compatibility and external use
__all__ = [
    "HostServiceRegistry",
    "bootstrap_from_declarations",
    "is_valid_protocol",
    "RegistryStorageMixin",
    "RegistrationMixin",
    "QueryMixin",
    "DiagnosticsMixin",
]
