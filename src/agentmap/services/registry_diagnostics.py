"""
Diagnostics and validation for HostServiceRegistry.

This module provides mixins for registry summary and service validation operations.
"""

import inspect
from typing import Any, Dict, Type


class DiagnosticsMixin:
    """
    Mixin providing diagnostics and validation operations.

    Requires RegistryStorageMixin to be present in the class hierarchy.
    """

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
