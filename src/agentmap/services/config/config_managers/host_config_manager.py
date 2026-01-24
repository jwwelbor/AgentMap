"""Host application configuration manager."""

from pathlib import Path
from typing import Any, Dict, List

from agentmap.services.config.config_managers.base_config_manager import (
    BaseConfigManager,
)


class HostConfigManager(BaseConfigManager):
    """
    Configuration manager for host application settings.

    Handles all host application configuration including services,
    protocol folders, service discovery, and validation.
    """

    def get_host_application_config(self) -> Dict[str, Any]:
        """
        Get host application configuration with default values.

        Allows host applications to store their configuration in the main AgentMap
        config file under a 'host_application' section. Provides graceful degradation
        when no host config is present.

        Returns:
            Dictionary containing host application configuration
        """
        host_config = self.get_section("host_application", {})

        # Default host application configuration
        defaults = {
            "enabled": True,
            "services": {},
            "protocol_folders": [],
            "service_discovery": {
                "enabled": True,
                "scan_on_startup": True,
                "cache_protocols": True,
            },
            "configuration": {},
            "features": {
                "dynamic_protocols": True,
                "runtime_registration": True,
                "graceful_degradation": True,
            },
        }

        # Merge with defaults
        merged_config = self._merge_with_defaults(host_config, defaults)

        # Log host application status for visibility
        if host_config:
            self._logger.debug(
                f"[HostConfigManager] Host application config loaded with sections: {list(host_config.keys())}"
            )
        else:
            self._logger.debug(
                "[HostConfigManager] No host application config found, using defaults"
            )

        return merged_config

    def get_host_protocol_folders(self) -> List[Path]:
        """
        Get list of folders to scan for host-defined protocols.

        Returns protocol discovery paths from configuration, with sensible defaults
        for common host application structures.

        Returns:
            List of Path objects for protocol discovery folders
        """
        # Get protocol folders from host application config
        protocol_folders_config = self.get_value(
            "host_application.protocol_folders", []
        )

        # Convert strings to Path objects
        protocol_folders = []
        for folder in protocol_folders_config:
            try:
                protocol_folders.append(Path(folder))
            except Exception as e:
                self._logger.warning(
                    f"[HostConfigManager] Invalid protocol folder path '{folder}': {e}"
                )

        # Add default protocol discovery paths if none configured
        if not protocol_folders:
            default_folders = [
                "host_services/protocols",
                "custom_protocols",
                "protocols",
            ]
            protocol_folders = [Path(folder) for folder in default_folders]
            self._logger.debug(
                f"[HostConfigManager] Using default protocol folders: {default_folders}"
            )
        else:
            folder_paths = [str(folder) for folder in protocol_folders]
            self._logger.debug(
                f"[HostConfigManager] Using configured protocol folders: {folder_paths}"
            )

        return protocol_folders

    def get_host_service_config(self, service_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific host service.

        Args:
            service_name: Name of the host service

        Returns:
            Dictionary containing service-specific configuration
        """
        if not service_name:
            self._logger.warning("[HostConfigManager] Empty service name provided")
            return {}

        # Get service configuration from host application config
        service_config = self.get_value(f"host_application.services.{service_name}", {})

        # Provide default service configuration structure
        defaults = {
            "enabled": True,
            "auto_configure": True,
            "dependencies": [],
            "configuration": {},
            "metadata": {},
        }

        # Merge with defaults
        merged_config = self._merge_with_defaults(service_config, defaults)

        if service_config:
            self._logger.debug(
                f"[HostConfigManager] Host service '{service_name}' config loaded"
            )
        else:
            self._logger.debug(
                f"[HostConfigManager] No config found for host service '{service_name}', using defaults"
            )

        return merged_config

    def get_host_configuration_section(self, section_name: str) -> Dict[str, Any]:
        """
        Get a specific configuration section from host application config.

        Args:
            section_name: Name of the configuration section

        Returns:
            Dictionary containing the requested configuration section
        """
        return self.get_value(f"host_application.configuration.{section_name}", {})

    def validate_host_config(self) -> Dict[str, Any]:
        """
        Validate host application configuration and return validation results.

        Returns:
            Dictionary with validation status:
            - 'valid': Boolean indicating if config is valid
            - 'warnings': List of non-critical issues
            - 'errors': List of critical issues
            - 'summary': Summary of validation results
        """
        warnings = []
        errors = []

        try:
            host_config = self.get_host_application_config()

            # Validate protocol folders exist
            protocol_folders = self.get_host_protocol_folders()
            for folder in protocol_folders:
                if not folder.exists():
                    warnings.append(f"Protocol folder does not exist: {folder}")
                elif not folder.is_dir():
                    errors.append(f"Protocol folder path is not a directory: {folder}")

            # Validate services configuration
            services_config = host_config.get("services", {})
            if not isinstance(services_config, dict):
                errors.append(
                    "Host application services configuration must be a dictionary"
                )
            else:
                for service_name, service_config in services_config.items():
                    if not isinstance(service_config, dict):
                        errors.append(
                            f"Service '{service_name}' configuration must be a dictionary"
                        )

            # Validate service discovery configuration
            discovery_config = host_config.get("service_discovery", {})
            if not isinstance(discovery_config, dict):
                warnings.append(
                    "Service discovery configuration should be a dictionary"
                )

            # Validate features configuration
            features_config = host_config.get("features", {})
            if not isinstance(features_config, dict):
                warnings.append("Features configuration should be a dictionary")

            # Check for common configuration issues
            if not host_config.get("enabled", True):
                warnings.append("Host application support is disabled")

            if not protocol_folders:
                warnings.append("No protocol folders configured for service discovery")

        except Exception as e:
            errors.append(f"Error during host config validation: {str(e)}")

        # Determine overall validity
        is_valid = len(errors) == 0

        # Create summary
        summary = {
            "total_issues": len(warnings) + len(errors),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "protocol_folders_count": (
                len(self.get_host_protocol_folders()) if not errors else 0
            ),
            "services_count": (
                len(self.get_host_application_config().get("services", {}))
                if not errors
                else 0
            ),
        }

        # Log validation results
        if is_valid:
            if warnings:
                self._logger.info(
                    f"[HostConfigManager] Host config validation completed with {len(warnings)} warnings"
                )
            else:
                self._logger.debug("[HostConfigManager] Host config validation passed")
        else:
            self._logger.error(
                f"[HostConfigManager] Host config validation failed with {len(errors)} errors"
            )

        return {
            "valid": is_valid,
            "warnings": warnings,
            "errors": errors,
            "summary": summary,
        }

    def is_host_application_enabled(self) -> bool:
        """
        Check if host application support is enabled.

        Returns:
            True if host application support is enabled
        """
        return self.get_value("host_application.enabled", True)
