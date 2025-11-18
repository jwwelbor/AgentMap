"""
Query operations for HostServiceRegistry.

This module provides mixins for service and protocol lookup operations.
"""

from typing import Any, Dict, List, Optional, Type


class QueryMixin:
    """
    Mixin providing service and protocol query operations.

    Requires RegistryStorageMixin to be present in the class hierarchy.
    """

    def get_service_provider(self, service_name: str) -> Optional[Any]:
        """
        Get service provider by name.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            Service provider if found, None otherwise
        """
        if service_name not in self._service_providers:
            self.logger.debug(
                f"[HostServiceRegistry] Service '{service_name}' not found"
            )
            return None

        try:
            provider = self._service_providers[service_name]
            self.logger.debug(
                f"[HostServiceRegistry] Retrieved service provider: {service_name}"
            )
            return provider

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Error retrieving service '{service_name}': {e}"
            )
            return None

    def get_protocol_implementation(self, protocol: Type) -> Optional[str]:
        """
        Get service name that implements the specified protocol.

        Args:
            protocol: Protocol type to look up

        Returns:
            Service name that implements the protocol, None if not found
        """
        if protocol not in self._protocol_implementations:
            self.logger.debug(
                f"[HostServiceRegistry] No implementation found for protocol: {protocol.__name__}"
            )
            return None

        try:
            service_name = self._protocol_implementations[protocol]
            self.logger.debug(
                f"[HostServiceRegistry] Protocol {protocol.__name__} implemented by: {service_name}"
            )
            return service_name

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Error getting protocol implementation for {protocol.__name__}: {e}"
            )
            return None

    def discover_services_by_protocol(self, protocol: Type) -> List[str]:
        """
        Discover all services that implement a specific protocol.

        Args:
            protocol: Protocol type to search for

        Returns:
            List of service names that implement the protocol
        """
        implementing_services = []

        try:
            # Check direct protocol mappings
            if protocol in self._protocol_implementations:
                implementing_services.append(self._protocol_implementations[protocol])

            # Also check protocol cache for comprehensive search
            for service_name, protocols in self._protocol_cache.items():
                if protocol in protocols and service_name not in implementing_services:
                    implementing_services.append(service_name)

            if implementing_services:
                self.logger.debug(
                    f"[HostServiceRegistry] Found {len(implementing_services)} services implementing {protocol.__name__}"
                )
            else:
                self.logger.debug(
                    f"[HostServiceRegistry] No services found implementing {protocol.__name__}"
                )

            return implementing_services

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Error discovering services for protocol {protocol.__name__}: {e}"
            )
            return []

    def list_registered_services(self) -> List[str]:
        """
        Get list of all registered service names.

        Returns:
            List of registered service names
        """
        try:
            service_names = list(self._service_providers.keys())
            self.logger.debug(
                f"[HostServiceRegistry] {len(service_names)} services registered"
            )
            return service_names

        except Exception as e:
            self.logger.error(f"[HostServiceRegistry] Error listing services: {e}")
            return []

    def get_service_metadata(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a registered service.

        Args:
            service_name: Name of the service

        Returns:
            Service metadata dictionary, None if service not found
        """
        if service_name not in self._service_metadata:
            self.logger.debug(
                f"[HostServiceRegistry] No metadata found for service: {service_name}"
            )
            return None

        try:
            metadata = self._service_metadata[service_name].copy()
            self.logger.debug(
                f"[HostServiceRegistry] Retrieved metadata for service: {service_name}"
            )
            return metadata

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Error getting metadata for service '{service_name}': {e}"
            )
            return None

    def update_service_metadata(
        self, service_name: str, metadata: Dict[str, Any]
    ) -> bool:
        """
        Update metadata for an existing service.

        Args:
            service_name: Name of the service
            metadata: New metadata to merge with existing

        Returns:
            True if metadata was updated successfully
        """
        if service_name not in self._service_providers:
            self.logger.warning(
                f"[HostServiceRegistry] Cannot update metadata for unregistered service: {service_name}"
            )
            return False

        try:
            if service_name not in self._service_metadata:
                self._service_metadata[service_name] = {}

            # Merge new metadata with existing
            self._service_metadata[service_name].update(metadata)

            self.logger.debug(
                f"[HostServiceRegistry] Updated metadata for service: {service_name}"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Failed to update metadata for service '{service_name}': {e}"
            )
            return False

    def get_service_protocols(self, service_name: str) -> List[Type]:
        """
        Get all protocols implemented by a service.

        Args:
            service_name: Name of the service

        Returns:
            List of protocol types implemented by the service
        """
        if service_name not in self._protocol_cache:
            self.logger.debug(
                f"[HostServiceRegistry] No protocols cached for service: {service_name}"
            )
            return []

        try:
            protocols = self._protocol_cache[service_name].copy()
            self.logger.debug(
                f"[HostServiceRegistry] Service '{service_name}' implements {len(protocols)} protocols"
            )
            return protocols

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Error getting protocols for service '{service_name}': {e}"
            )
            return []

    def is_service_registered(self, service_name: str) -> bool:
        """
        Check if a service is registered.

        Args:
            service_name: Name of the service to check

        Returns:
            True if service is registered
        """
        return service_name in self._service_providers

    def is_protocol_implemented(self, protocol: Type) -> bool:
        """
        Check if a protocol has any implementations.

        Args:
            protocol: Protocol type to check

        Returns:
            True if protocol has at least one implementation
        """
        return protocol in self._protocol_implementations
