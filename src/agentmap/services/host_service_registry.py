"""
HostServiceRegistry for AgentMap host application integration.

Service for managing dynamic registration of host services and protocols.
This class provides the core functionality for storing service providers,
protocol implementations, and metadata without affecting AgentMap's core DI container.
"""

import inspect
from typing import Any, Dict, List, Optional, Type

from agentmap.services.logging_service import LoggingService


class HostServiceRegistry:
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

        # Core storage
        self._service_providers: Dict[str, Any] = {}
        self._protocol_implementations: Dict[Type, str] = {}
        self._service_metadata: Dict[str, Dict[str, Any]] = {}
        self._protocol_cache: Dict[str, List[Type]] = {}

        self.logger.debug("[HostServiceRegistry] Initialized")

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
                f"[HostServiceRegistry] ✅ Registered service provider: {service_name}"
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
                f"[HostServiceRegistry] ✅ Registered protocol {protocol.__name__} -> {service_name}"
            )

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Failed to register protocol {protocol.__name__}: {e}"
            )

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
                f"[HostServiceRegistry] ✅ Updated metadata for service: {service_name}"
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
                f"[HostServiceRegistry] ✅ Unregistered service: {service_name}"
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
                f"[HostServiceRegistry] ✅ Cleared registry: {service_count} services, {protocol_count} protocols"
            )

        except Exception as e:
            self.logger.error(f"[HostServiceRegistry] Error clearing registry: {e}")

    def get_registry_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of registry state for debugging.

        Returns:
            Dictionary with registry status and statistics
        """
        try:
            service_names = list(self._service_providers.keys())
            protocol_names = [p.__name__ for p in self._protocol_implementations.keys()]

            # Count services by protocol implementation
            protocol_stats = {}
            for service_name, protocols in self._protocol_cache.items():
                for protocol in protocols:
                    protocol_name = protocol.__name__
                    if protocol_name not in protocol_stats:
                        protocol_stats[protocol_name] = 0
                    protocol_stats[protocol_name] += 1

            summary = {
                "service": "HostServiceRegistry",
                "total_services": len(service_names),
                "total_protocols": len(protocol_names),
                "registered_services": service_names,
                "implemented_protocols": protocol_names,
                "protocol_implementation_count": protocol_stats,
                "services_with_metadata": len(self._service_metadata),
                "services_with_protocols": len(self._protocol_cache),
                "registry_health": {
                    "providers_storage_ok": len(self._service_providers) >= 0,
                    "protocols_storage_ok": len(self._protocol_implementations) >= 0,
                    "metadata_storage_ok": len(self._service_metadata) >= 0,
                    "cache_storage_ok": len(self._protocol_cache) >= 0,
                },
            }

            return summary

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Error generating registry summary: {e}"
            )
            return {
                "service": "HostServiceRegistry",
                "error": str(e),
                "registry_health": {"error": True},
            }

    def validate_service_provider(self, service_name: str) -> Dict[str, Any]:
        """
        Validate a registered service provider and its protocols.

        Args:
            service_name: Name of the service to validate

        Returns:
            Validation results with details about any issues
        """
        if service_name not in self._service_providers:
            return {
                "valid": False,
                "error": f"Service '{service_name}' not registered",
                "checks": {},
            }

        try:
            provider = self._service_providers[service_name]
            protocols = self._protocol_cache.get(service_name, [])
            metadata = self._service_metadata.get(service_name, {})

            checks = {
                "provider_exists": provider is not None,
                "provider_is_valid": provider is not None
                and (
                    callable(provider)
                    or inspect.isclass(provider)
                    or hasattr(provider, "__dict__")
                ),
                "has_protocols": len(protocols) > 0,
                "protocols_valid": all(self._is_valid_protocol(p) for p in protocols),
                "has_metadata": len(metadata) > 0,
                "protocol_mappings_consistent": True,
            }

            # Check protocol mapping consistency
            for protocol in protocols:
                if protocol in self._protocol_implementations:
                    mapped_service = self._protocol_implementations[protocol]
                    if mapped_service != service_name:
                        checks["protocol_mappings_consistent"] = False
                        break

            validation_result = {
                "valid": all(checks.values()),
                "service_name": service_name,
                "checks": checks,
                "protocol_count": len(protocols),
                "metadata_keys": list(metadata.keys()) if metadata else [],
            }

            if not validation_result["valid"]:
                failed_checks = [k for k, v in checks.items() if not v]
                validation_result["failed_checks"] = failed_checks
                self.logger.warning(
                    f"[HostServiceRegistry] Service '{service_name}' validation failed: {failed_checks}"
                )

            return validation_result

        except Exception as e:
            self.logger.error(
                f"[HostServiceRegistry] Error validating service '{service_name}': {e}"
            )
            return {
                "valid": False,
                "error": str(e),
                "service_name": service_name,
                "checks": {},
            }

    def _is_valid_protocol(self, protocol: Type) -> bool:
        """
        Validate that an object is a proper protocol type.

        Args:
            protocol: Object to validate as a protocol

        Returns:
            True if the object is a valid protocol type
        """
        try:
            # Must be a type/class
            if not inspect.isclass(protocol):
                return False

            # Check if it looks like a Protocol (has _is_protocol marker)
            if hasattr(protocol, "_is_protocol") and getattr(
                protocol, "_is_protocol", False
            ):
                return True

            # Check if it inherits from typing.Protocol
            import typing

            if hasattr(typing, "Protocol"):
                mro = inspect.getmro(protocol)
                for base in mro:
                    if (
                        getattr(base, "__module__", "") == "typing"
                        and base.__name__ == "Protocol"
                    ):
                        return True

            # Check if it's decorated with @runtime_checkable (has protocol-like attributes)
            if hasattr(protocol, "__class_getitem__") and hasattr(
                protocol, "__subclasshook__"
            ):
                # This is likely a runtime checkable protocol
                return True

            # If none of the above checks pass, it's not a valid protocol
            return False

        except Exception as e:
            self.logger.debug(
                f"[HostServiceRegistry] Error validating protocol {protocol}: {e}"
            )
            return False

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
