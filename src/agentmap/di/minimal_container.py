"""
MinimalContainer for selective service initialization.

Provides selective service initialization that only creates services that are
explicitly required, avoiding the eager initialization of all services that
happens with the current DI container.
"""

from typing import Any, Dict, Optional, Set

from agentmap.di.containers import ApplicationContainer
from agentmap.services.di_container_analyzer import DIContainerAnalyzer
from agentmap.services.logging_service import LoggingService


class MinimalContainer:
    """
    Container that wraps ApplicationContainer and provides selective service initialization.

    Only creates services that are explicitly required, avoiding eager initialization
    of all services. Maintains dependency order and provides logging of what services
    are created vs skipped.
    """

    # Core services that are always required for basic functionality
    CORE_SERVICES = {"logging_service", "config_service", "app_config_service"}

    def __init__(
        self,
        parent_container: ApplicationContainer,
        required_services: Set[str],
        logging_service: Optional[LoggingService] = None,
    ):
        """
        Initialize MinimalContainer with parent container and required services.

        Args:
            parent_container: ApplicationContainer to wrap
            required_services: Set of service names that should be loaded
            logging_service: Optional logging service for logging (uses parent if None)

        Raises:
            ValueError: If parent_container or required_services is None
        """
        if parent_container is None:
            raise ValueError("Parent container cannot be None")
        if required_services is None:
            raise ValueError("Required services cannot be None")

        self.parent_container = parent_container

        # Always include core services
        self.required_services = set(required_services) | self.CORE_SERVICES

        # Track which services have been initialized
        self.initialized_services: Set[str] = set()

        # Cache for service instances
        self._service_instances: Dict[str, Any] = {}

        # Initialize logging
        self._setup_logging(logging_service)

        # Log initialization summary
        self.logger.info(
            f"MinimalContainer initialized with {len(self.required_services)} required services: "
            f"{sorted(self.required_services)}"
        )

    def _setup_logging(self, logging_service: Optional[LoggingService]) -> None:
        """Setup logging for the container."""
        if logging_service:
            self.logging_service = logging_service
        else:
            # Try to get logging service from parent container
            try:
                self.logging_service = self.parent_container.logging_service()
            except Exception:
                # Fallback if logging service can't be initialized
                self.logging_service = None

        if self.logging_service:
            self.logger = self.logging_service.get_class_logger(self)
        else:
            # Create a minimal logger as fallback
            import logging

            self.logger = logging.getLogger(self.__class__.__name__)

    def initialize_service(self, service_name: str) -> Optional[Any]:
        """
        Initialize a service if it's in the required set.

        Args:
            service_name: Name of the service to initialize

        Returns:
            Service instance if required and successfully initialized, None otherwise
        """
        # Check if service is required
        if service_name not in self.required_services:
            self.logger.debug(
                f"Service '{service_name}' not in required services, skipping"
            )
            return None

        # Check if already initialized
        if service_name in self.initialized_services:
            self.logger.debug(
                f"Service '{service_name}' already initialized, returning cached instance"
            )
            return self._service_instances.get(service_name)

        try:
            # Initialize dependencies first
            self._initialize_dependencies(service_name)

            # Get service provider from parent container
            provider = self._get_provider(service_name)
            if provider is None:
                self.logger.warning(
                    f"Provider for service '{service_name}' not found in parent container"
                )
                return None

            # Create service instance
            service_instance = provider()

            # Cache and track
            self._service_instances[service_name] = service_instance
            self.initialized_services.add(service_name)

            self.logger.debug(f"Successfully initialized service '{service_name}'")
            return service_instance

        except Exception as e:
            self.logger.error(f"Failed to initialize service '{service_name}': {e}")
            return None

    def _initialize_dependencies(self, service_name: str) -> None:
        """
        Initialize dependencies for a service.

        Args:
            service_name: Name of the service whose dependencies should be initialized
        """
        dependencies = self._get_service_dependencies(service_name)

        for dep_name in dependencies:
            if (
                dep_name in self.required_services
                and dep_name not in self.initialized_services
            ):
                self.logger.debug(
                    f"Initializing dependency '{dep_name}' for service '{service_name}'"
                )
                self.initialize_service(dep_name)

    def _get_provider(self, service_name: str) -> Optional[Any]:
        """
        Get service provider from parent container.

        Args:
            service_name: Name of the service

        Returns:
            Provider instance or None if not found
        """
        try:
            return getattr(self.parent_container, service_name, None)
        except Exception as e:
            self.logger.error(f"Error getting provider for '{service_name}': {e}")
            return None

    def _get_service_dependencies(self, service_name: str) -> Set[str]:
        """
        Get dependencies for a service using DIContainerAnalyzer.

        Args:
            service_name: Name of the service

        Returns:
            Set of dependency service names
        """
        try:
            analyzer = DIContainerAnalyzer(self.parent_container)
            return analyzer.get_service_dependencies(service_name)
        except Exception as e:
            self.logger.error(f"Error analyzing dependencies for '{service_name}': {e}")
            return set()

    def _resolve_all_dependencies(self, root_services: Set[str]) -> Set[str]:
        """
        Build complete dependency tree for root services.

        Args:
            root_services: Set of root service names

        Returns:
            Set of all services including transitive dependencies
        """
        try:
            analyzer = DIContainerAnalyzer(self.parent_container)
            return analyzer.build_full_dependency_tree(root_services)
        except Exception as e:
            self.logger.error(f"Error building dependency tree: {e}")
            return root_services.copy()

    def get_service(self, service_name: str) -> Optional[Any]:
        """
        Get a service instance, creating it if required and not already initialized.

        Args:
            service_name: Name of the service to get

        Returns:
            Service instance or None if not required or failed to initialize
        """
        if service_name not in self.required_services:
            self.logger.debug(
                f"Service '{service_name}' not in required services, returning None"
            )
            return None

        # Try to get from cache first
        if service_name in self.initialized_services:
            return self._service_instances.get(service_name)

        # Initialize if not already done
        return self.initialize_service(service_name)

    def has_service(self, service_name: str) -> bool:
        """
        Check if a service is in the required services set.

        Args:
            service_name: Name of the service to check

        Returns:
            True if service is required, False otherwise
        """
        return service_name in self.required_services

    def get_initialized_services(self) -> Set[str]:
        """
        Get set of services that have been initialized.

        Returns:
            Set of initialized service names
        """
        return self.initialized_services.copy()

    def get_required_services(self) -> Set[str]:
        """
        Get set of required services.

        Returns:
            Set of required service names
        """
        return self.required_services.copy()

    def get_initialization_stats(self) -> Dict[str, Any]:
        """
        Get statistics about service initialization.

        Returns:
            Dictionary with initialization statistics
        """
        return {
            "total_required": len(self.required_services),
            "total_initialized": len(self.initialized_services),
            "initialization_rate": (
                len(self.initialized_services) / len(self.required_services)
                if self.required_services
                else 0
            ),
            "required_services": sorted(self.required_services),
            "initialized_services": sorted(self.initialized_services),
            "uninitialized_services": sorted(
                self.required_services - self.initialized_services
            ),
        }
