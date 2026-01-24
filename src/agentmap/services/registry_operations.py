"""
Registration operations for HostServiceRegistry.

This module provides mixins for service registration, unregistration,
and registry management operations.
"""

from typing import Any, Dict, List, Optional, Type


class RegistrationMixin:
    """
    Mixin providing service registration and unregistration operations.

    Requires the following to be present in the class hierarchy:
    - `RegistryStorageMixin` for storage attributes and cleanup.
    - A `self.logger` attribute for logging.
    - A `self._is_valid_protocol(protocol)` method for protocol validation.
    """

    def register_service_provider(
        self,
        service_name: str,
        provider: Any,
        protocols: Optional[List[Type]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a service provider with optional protocol implementations.

        Args:
            service_name: Unique name for the service
            provider: Service provider (DI provider, factory function, or instance)
            protocols: Optional list of protocols this service implements
            metadata: Optional metadata about the service
        """
        if not service_name:
            self.logger.warning("[HostServiceRegistry] Empty service name provided")
            return

        # Allow None provider for protocol discovery use case
        if (
            provider is None
            and metadata
            and metadata.get("type") == "discovered_protocol"
        ):
            self.logger.debug(
                f"[HostServiceRegistry] Registering protocol placeholder for '{service_name}'"
            )
        elif not provider:
            self.logger.warning(
                f"[HostServiceRegistry] Empty provider provided for service '{service_name}'"
            )
            return

        try:
            # Check if service already registered
            if service_name in self._service_providers:
                self.logger.warning(
                    f"[HostServiceRegistry] Service '{service_name}' already registered, overwriting"
                )

            # Store the service provider
            self._service_providers[service_name] = provider

            # Store metadata if provided
            if metadata:
                self._service_metadata[service_name] = metadata.copy()
            else:
                self._service_metadata[service_name] = {}

            # Register protocol implementations if provided
            valid_protocols = []
            if protocols:
                for protocol in protocols:
                    if self._is_valid_protocol(protocol):
                        self._protocol_implementations[protocol] = service_name
                        valid_protocols.append(protocol)
                        self.logger.debug(
                            f"[HostServiceRegistry] Registered protocol {protocol.__name__} -> {service_name}"
                        )
                    else:
                        self.logger.warning(
                            f"[HostServiceRegistry] Invalid protocol provided: {protocol}"
                        )

            # Cache only valid protocols for this service
            if valid_protocols:
                self._protocol_cache[service_name] = valid_protocols

            self.logger.info(
                f"[HostServiceRegistry] Registered service provider: {service_name}"
            )

            # Log protocol count for debugging
            if valid_protocols:
                self.logger.debug(
                    f"[HostServiceRegistry] Service '{service_name}' implements {len(valid_protocols)} valid protocols"
                )
            elif protocols:
                self.logger.debug(
                    f"[HostServiceRegistry] Service '{service_name}' had {len(protocols)} protocols provided, but none were valid"
                )

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Failed to register service '{service_name}': {e}"
            )
            # Clean up partial registration
            self._cleanup_partial_registration(service_name)

    def register_protocol_implementation(
        self, protocol: Type, service_name: str
    ) -> None:
        """
        Register a protocol implementation for an existing service.

        Args:
            protocol: Protocol type to register
            service_name: Name of service that implements this protocol
        """
        if not self._is_valid_protocol(protocol):
            self.logger.warning(f"[HostServiceRegistry] Invalid protocol: {protocol}")
            return

        if service_name not in self._service_providers:
            self.logger.warning(
                f"[HostServiceRegistry] Service '{service_name}' not registered"
            )
            return

        try:
            # Register the protocol mapping
            self._protocol_implementations[protocol] = service_name

            # Update protocol cache
            if service_name not in self._protocol_cache:
                self._protocol_cache[service_name] = []

            if protocol not in self._protocol_cache[service_name]:
                self._protocol_cache[service_name].append(protocol)

            self.logger.debug(
                f"[HostServiceRegistry] Registered protocol {protocol.__name__} -> {service_name}"
            )

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Failed to register protocol {protocol.__name__}: {e}"
            )

    def unregister_service(self, service_name: str) -> bool:
        """
        Unregister a service and clean up all related data.

        Args:
            service_name: Name of the service to unregister

        Returns:
            True if service was unregistered successfully
        """
        if service_name not in self._service_providers:
            self.logger.debug(
                f"[HostServiceRegistry] Service '{service_name}' not registered"
            )
            return False

        try:
            # Remove service provider
            del self._service_providers[service_name]

            # Remove metadata
            if service_name in self._service_metadata:
                del self._service_metadata[service_name]

            # Remove protocol mappings
            protocols_to_remove = []
            for protocol, mapped_service in self._protocol_implementations.items():
                if mapped_service == service_name:
                    protocols_to_remove.append(protocol)

            for protocol in protocols_to_remove:
                del self._protocol_implementations[protocol]

            # Remove protocol cache
            if service_name in self._protocol_cache:
                del self._protocol_cache[service_name]

            self.logger.info(
                f"[HostServiceRegistry] Unregistered service: {service_name}"
            )
            if protocols_to_remove:
                self.logger.debug(
                    f"[HostServiceRegistry] Removed {len(protocols_to_remove)} protocol mappings"
                )

            return True

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Error unregistering service '{service_name}': {e}"
            )
            return False

    def clear_registry(self) -> None:
        """
        Clear all registered services and protocol mappings.

        Use with caution - this removes all host service registrations.
        """
        try:
            service_count = len(self._service_providers)
            protocol_count = len(self._protocol_implementations)

            # Clear all storage
            self._service_providers.clear()
            self._protocol_implementations.clear()
            self._service_metadata.clear()
            self._protocol_cache.clear()

            self.logger.info(
                f"[HostServiceRegistry] Cleared registry: {service_count} services, {protocol_count} protocols"
            )

        except Exception as e:
            self.logger.error(f"[HostServiceRegistry] Error clearing registry: {e}")
