"""
DIContainerAnalyzer service for AgentMap.

Service for analyzing dependency injection container structure and extracting
service dependency trees. Enables understanding of the complete dependency
graph without hardcoding service relationships.
"""

from typing import Set, Optional, Any
from collections import deque
from dependency_injector import providers

from agentmap.services.logging_service import LoggingService


class DIContainerAnalyzer:
    """
    Service for analyzing DI container structure and extracting dependency information.
    
    This service analyzes the dependency-injector container to determine the full
    dependency tree for any service, enabling discovery of all transitive 
    dependencies without hardcoding them.
    
    Capabilities:
    - Extract direct dependencies for any service
    - Build complete transitive dependency trees
    - Handle circular dependencies gracefully
    - Support various provider types (Singleton, Factory, etc.)
    """

    def __init__(self, container, logging_service: Optional[LoggingService] = None):
        """
        Initialize the DI container analyzer.
        
        Args:
            container: ApplicationContainer instance to analyze
            logging_service: Optional logging service for debug output
            
        Raises:
            ValueError: If container is None
        """
        if container is None:
            raise ValueError("Container cannot be None")
            
        self.container = container
        
        # Initialize logging
        if logging_service:
            self.logger = logging_service.get_class_logger(self)
        else:
            # Create a basic logger if none provided
            import logging
            self.logger = logging.getLogger(self.__class__.__name__)
            
        self.logger.debug("[DIContainerAnalyzer] Initialized with container analysis capabilities")

    def get_service_dependencies(self, service_name: str) -> Set[str]:
        """
        Extract dependencies for a specific service from the DI container.
        
        Analyzes the provider to determine all direct dependencies by examining:
        - Provider.dependencies attribute if available
        - Provider.args for Provider instances
        - Provider.kwargs for Provider instances
        
        Args:
            service_name: Name of the service to analyze
            
        Returns:
            Set of dependency service names
        """
        # Known non-service entries that should be filtered out
        NON_SERVICE_ENTRIES = {
            'config_path',      # Configuration value, not a service
            'routing_cache',    # Cache object, not a service  
            'logging_config',   # Configuration object
            'execution_config', # Configuration object
            'prompts_config',   # Configuration object
            'storage_available' # Boolean check, not a service
        }
        
        try:
            self.logger.debug(f"[DIContainerAnalyzer] Analyzing dependencies for service: {service_name}")
            
            provider = self._get_provider(service_name)
            if not provider:
                self.logger.debug(f"[DIContainerAnalyzer] No provider found for service: {service_name}")
                return set()
                
            # Debug logging
            self.logger.debug(f"[DIContainerAnalyzer] Provider found: {provider}")
            self.logger.debug(f"[DIContainerAnalyzer] Provider type: {type(provider)}")
            self.logger.debug(f"[DIContainerAnalyzer] Has dependencies attr: {hasattr(provider, 'dependencies')}")
            if hasattr(provider, 'dependencies'):
                self.logger.debug(f"[DIContainerAnalyzer] Dependencies value: {provider.dependencies}")
                self.logger.debug(f"[DIContainerAnalyzer] Dependencies truthy: {bool(provider.dependencies)}")
            
            dependencies = set()
            
            # Method 1: Check provider.dependencies attribute (for test compatibility)
            if hasattr(provider, 'dependencies') and provider.dependencies:
                # Handle both iterable and non-iterable dependencies
                if hasattr(provider.dependencies, '__iter__') and not isinstance(provider.dependencies, str):
                    dependencies.update(provider.dependencies)
                else:
                    dependencies.add(provider.dependencies)
                self.logger.debug(f"[DIContainerAnalyzer] Found dependencies from provider.dependencies: {provider.dependencies}")
            
            # Method 2: Check provider.args for Provider instances
            if hasattr(provider, 'args'):
                try:
                    # Ensure args is iterable before attempting to iterate
                    args = provider.args
                    if hasattr(args, '__iter__'):
                        for arg in args:
                            if self._is_provider_instance(arg):
                                dep_name = self._extract_provider_name(arg)
                                if dep_name:
                                    dependencies.add(dep_name)
                                    self.logger.debug(f"[DIContainerAnalyzer] Found dependency from args: {dep_name}")
                except (TypeError, AttributeError):
                    # Skip if args is not iterable or accessible
                    pass
            
            # Method 3: Check provider.kwargs for Provider instances
            if hasattr(provider, 'kwargs'):
                try:
                    # Ensure kwargs is a dict before attempting to iterate
                    kwargs = provider.kwargs
                    if hasattr(kwargs, 'items'):
                        for key, value in kwargs.items():
                            if self._is_provider_instance(value):
                                dep_name = self._extract_provider_name(value)
                                if dep_name:
                                    dependencies.add(dep_name)
                                    self.logger.debug(f"[DIContainerAnalyzer] Found dependency from kwargs[{key}]: {dep_name}")
                except (TypeError, AttributeError):
                    # Skip if kwargs is not iterable or accessible
                    pass
            
            # Filter out non-service entries
            filtered_dependencies = dependencies - NON_SERVICE_ENTRIES
            
            if dependencies != filtered_dependencies:
                self.logger.debug(
                    f"[DIContainerAnalyzer] Filtered out non-service entries: "
                    f"{dependencies - filtered_dependencies}"
                )
            
            self.logger.debug(f"[DIContainerAnalyzer] Total dependencies for {service_name}: {filtered_dependencies}")
            return filtered_dependencies
            
        except Exception as e:
            self.logger.debug(f"[DIContainerAnalyzer] Error analyzing dependencies for {service_name}: {e}")
            return set()

    def build_full_dependency_tree(self, root_services: Set[str]) -> Set[str]:
        """
        Build complete transitive dependency tree for the given root services.
        
        Uses breadth-first traversal to discover all dependencies recursively,
        with protection against circular dependencies. Filters out non-service
        entries like configuration values.
        
        Args:
            root_services: Set of root service names to start analysis from
            
        Returns:
            Complete set of all required services (including root services)
        """
        # Known non-service entries that should be filtered out
        NON_SERVICE_ENTRIES = {
            'config_path',      # Configuration value, not a service
            'routing_cache',    # Cache object, not a service  
            'logging_config',   # Configuration object
            'execution_config', # Configuration object
            'prompts_config',   # Configuration object
            'storage_available' # Boolean check, not a service
        }
        
        if not root_services:
            return set()
            
        self.logger.debug(f"[DIContainerAnalyzer] Building dependency tree for roots: {root_services}")
        
        # Use breadth-first search to handle circular dependencies
        visited = set()
        queue = deque(root_services)
        all_services = set(root_services)
        
        while queue:
            current_service = queue.popleft()
            
            if current_service in visited:
                continue  # Skip already processed services (handles circular deps)
                
            visited.add(current_service)
            self.logger.debug(f"[DIContainerAnalyzer] Processing service: {current_service}")
            
            # Get direct dependencies
            dependencies = self.get_service_dependencies(current_service)
            
            # Add new dependencies to queue and result set
            for dep in dependencies:
                if dep not in all_services:
                    all_services.add(dep)
                    queue.append(dep)
                    self.logger.debug(f"[DIContainerAnalyzer] Added new dependency: {dep}")
                elif dep in visited:
                    self.logger.debug(f"[DIContainerAnalyzer] Detected circular dependency: {current_service} -> {dep}")
        
        # Filter out non-service entries from the final result
        filtered_services = all_services - NON_SERVICE_ENTRIES
        
        if all_services != filtered_services:
            self.logger.debug(
                f"[DIContainerAnalyzer] Filtered out non-service entries from tree: "
                f"{all_services - filtered_services}"
            )
        
        self.logger.debug(f"[DIContainerAnalyzer] Complete dependency tree: {filtered_services}")
        return filtered_services

    def _get_provider(self, service_name: str) -> Optional[Any]:
        """
        Get provider instance for a service from the container.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Provider instance or None if not found
        """
        try:
            return getattr(self.container, service_name, None)
        except Exception as e:
            self.logger.debug(f"[DIContainerAnalyzer] Error getting provider for {service_name}: {e}")
            return None

    def _extract_provider_name(self, provider_instance: Any) -> Optional[str]:
        """
        Extract service name from a provider instance by matching against container providers.
        
        Args:
            provider_instance: Provider instance to identify
            
        Returns:
            Service name or None if not found
        """
        try:
            # Check all providers in the container to find a match
            if hasattr(self.container, 'providers'):
                for name, provider in self.container.providers.items():
                    if provider is provider_instance:
                        return name
                    # Also check for wrapped providers
                    if hasattr(provider, '_original_provider') and provider._original_provider is provider_instance:
                        return name
            
            # Fallback: check container attributes directly
            for attr_name in dir(self.container):
                if not attr_name.startswith('_'):
                    try:
                        attr_value = getattr(self.container, attr_name)
                        if attr_value is provider_instance:
                            return attr_name
                    except Exception:
                        continue
                        
            return None
            
        except Exception as e:
            self.logger.debug(f"[DIContainerAnalyzer] Error extracting provider name: {e}")
            return None

    def _is_provider_instance(self, obj: Any) -> bool:
        """
        Check if an object is a dependency-injector Provider instance.
        
        Args:
            obj: Object to check
            
        Returns:
            True if object is a Provider instance
        """
        try:
            return isinstance(obj, providers.Provider)
        except Exception:
            return False
    
    def get_dependency_tree(self, services: Set[str]) -> dict[str, Set[str]]:
        """Build a dependency tree for the given services.
        
        Args:
            services: Set of service names to analyze
            
        Returns:
            Dictionary mapping service names to their dependencies
        """
        dependency_tree = {}
        
        for service in services:
            dependencies = self.get_service_dependencies(service)
            dependency_tree[service] = dependencies
            
            # Recursively add dependencies of dependencies
            for dep in dependencies:
                if dep not in dependency_tree:
                    dependency_tree[dep] = self.get_service_dependencies(dep)
        
        self.logger.debug(
            f"[DIContainerAnalyzer] Built dependency tree for {len(services)} services"
        )
        return dependency_tree
    
    def topological_sort(self, dependency_tree: dict[str, Set[str]]) -> list[str]:
        """Perform topological sort on dependency tree.
        
        Returns services in order such that dependencies come before dependents.
        
        Args:
            dependency_tree: Dictionary mapping service names to their dependencies
            
        Returns:
            List of service names in dependency order
        """
        # Create a copy of the dependency tree to modify
        graph = {node: set(deps) for node, deps in dependency_tree.items()}
        
        # Add any missing nodes (dependencies that aren't in the tree)
        all_deps = set()
        for deps in graph.values():
            all_deps.update(deps)
        for dep in all_deps:
            if dep not in graph:
                graph[dep] = set()
        
        result = []
        no_deps = [node for node, deps in graph.items() if not deps]
        
        while no_deps:
            # Sort for deterministic ordering
            no_deps.sort()
            node = no_deps.pop(0)
            result.append(node)
            
            # Remove this node from dependencies of other nodes
            for other_node, deps in list(graph.items()):
                if node in deps:
                    deps.remove(node)
                    if not deps and other_node not in result:
                        no_deps.append(other_node)
        
        # Check for cycles
        remaining_nodes = [n for n in graph if n not in result]
        if remaining_nodes:
            self.logger.warning(
                f"[DIContainerAnalyzer] Circular dependencies detected: {remaining_nodes}"
            )
            # Add remaining nodes anyway
            result.extend(sorted(remaining_nodes))
        
        self.logger.debug(
            f"[DIContainerAnalyzer] Topological sort completed: {len(result)} services"
        )
        return result
    
    def get_protocol_mappings(self) -> dict[str, str]:
        """Extract protocol to implementation mappings from container.
        
        Returns:
            Dictionary mapping protocol names to implementation class names
        """
        mappings = {}
        
        try:
            # Iterate through container providers
            for service_name in dir(self.container):
                if service_name.startswith('_'):
                    continue
                    
                provider = getattr(self.container, service_name, None)
                if not provider:
                    continue
                
                # Check if the service name ends with 'Protocol'
                if 'protocol' in service_name.lower():
                    # Try to get the implementation class
                    try:
                        if hasattr(provider, 'cls'):
                            impl_class = provider.cls
                            if impl_class:
                                mappings[service_name] = impl_class.__name__
                                self.logger.debug(
                                    f"[DIContainerAnalyzer] Protocol mapping: "
                                    f"{service_name} -> {impl_class.__name__}"
                                )
                    except Exception as e:
                        self.logger.debug(
                            f"[DIContainerAnalyzer] Failed to extract implementation "
                            f"for protocol {service_name}: {e}"
                        )
            
            self.logger.debug(
                f"[DIContainerAnalyzer] Extracted {len(mappings)} protocol mappings"
            )
            
        except Exception as e:
            self.logger.warning(
                f"[DIContainerAnalyzer] Error extracting protocol mappings: {e}"
            )
        
        return mappings
