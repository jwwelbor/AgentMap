"""
HostServiceRegistry for AgentMap host application integration.

Service for managing dynamic registration of host services and protocols.
This class provides the core functionality for storing service providers,
protocol implementations, and metadata without affecting AgentMap's core DI container.
"""

from agentmap.services.logging_service import LoggingService

# Import all mixins and utilities
from agentmap.services.protocol_validation import is_valid_protocol
from agentmap.services.registry_storage import RegistryStorageMixin
from agentmap.services.registry_operations import RegistrationMixin
from agentmap.services.registry_queries import QueryMixin
from agentmap.services.registry_diagnostics import DiagnosticsMixin


class HostServiceRegistry(
    RegistryStorageMixin,
    RegistrationMixin,
    QueryMixin,
    DiagnosticsMixin
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

    def _is_valid_protocol(self, protocol):
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


# Re-export components for backwards compatibility and external use
__all__ = [
    "HostServiceRegistry",
    "is_valid_protocol",
    "RegistryStorageMixin",
    "RegistrationMixin",
    "QueryMixin",
    "DiagnosticsMixin",
]
