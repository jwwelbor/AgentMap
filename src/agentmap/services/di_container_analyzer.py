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
            
            self.logger.debug(f"[DIContainerAnalyzer] Total dependencies for {service_name}: {dependencies}")
            return dependencies
            
        except Exception as e:
            self.logger.debug(f"[DIContainerAnalyzer] Error analyzing dependencies for {service_name}: {e}")
            return set()

    def build_full_dependency_tree(self, root_services: Set[str]) -> Set[str]:
        """
        Build complete transitive dependency tree for the given root services.
        
        Uses breadth-first traversal to discover all dependencies recursively,
        with protection against circular dependencies.
        
        Args:
            root_services: Set of root service names to start analysis from
            
        Returns:
            Complete set of all required services (including root services)
        """
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
        
        self.logger.debug(f"[DIContainerAnalyzer] Complete dependency tree: {all_services}")
        return all_services

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
