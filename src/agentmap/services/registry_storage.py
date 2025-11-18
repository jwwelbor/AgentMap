"""
Storage management for HostServiceRegistry.

This module provides the base storage class and cleanup utilities
for the host service registry.
"""

from typing import Any, Dict, List, Type


class RegistryStorageMixin:
    """
    Mixin providing storage initialization and cleanup operations.

    This mixin manages the core data structures used by the registry
    and provides methods for cleaning up partial registrations.
    """

    def _init_storage(self) -> None:
        """Initialize all storage dictionaries for the registry."""
        # Core storage
        self._service_providers: Dict[str, Any] = {}
        self._protocol_implementations: Dict[Type, str] = {}
        self._service_metadata: Dict[str, Dict[str, Any]] = {}
        self._protocol_cache: Dict[str, List[Type]] = {}

    def _cleanup_partial_registration(self, service_name: str) -> None:
        """
        Clean up any partial registration data for a service.

        Args:
            service_name: Name of the service to clean up
        """
        try:
            # Remove from providers if present
            if service_name in self._service_providers:
                del self._service_providers[service_name]

            # Remove from metadata if present
            if service_name in self._service_metadata:
                del self._service_metadata[service_name]

            # Remove from protocol cache if present
            if service_name in self._protocol_cache:
                del self._protocol_cache[service_name]

            # Remove any protocol mappings pointing to this service
            protocols_to_remove = []
            for protocol, mapped_service in self._protocol_implementations.items():
                if mapped_service == service_name:
                    protocols_to_remove.append(protocol)

            for protocol in protocols_to_remove:
                del self._protocol_implementations[protocol]

            self.logger.debug(
                f"[HostServiceRegistry] Cleaned up partial registration for: {service_name}"
            )

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Error during cleanup for service '{service_name}': {e}"
            )
