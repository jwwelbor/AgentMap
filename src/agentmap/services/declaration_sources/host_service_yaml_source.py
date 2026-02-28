"""Host services YAML declaration source."""

from pathlib import Path
from typing import Any, Dict

from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration
from agentmap.services.declaration_parser import DeclarationParser
from agentmap.services.declaration_sources.base import DeclarationSource
from agentmap.services.declaration_sources.yaml_loader import load_yaml_file
from agentmap.services.logging_service import LoggingService


class HostServiceYAMLSource(DeclarationSource):
    """
    Declaration source for host_services.yaml file.

    Loads host service declarations from host_services.yaml file and converts them to
    ServiceDeclaration models for use by DeclarationRegistryService. These declarations
    are later used by the bootstrap process to instantiate and register host services.
    """

    HOST_SERVICES_SOURCE_PREFIX = "yaml:host_services:"

    def __init__(
        self,
        app_config_service,
        parser: DeclarationParser,
        logging_service: LoggingService,
    ):
        """
        Initialize HostServiceYAMLSource with dependency injection.

        Args:
            app_config_service: Application configuration service for file paths
            parser: Declaration parser for normalizing service data
            logging_service: Logging service for error reporting
        """
        self.config = app_config_service
        self.parser = parser
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[HostServiceYAMLSource] Initialized")

    def load_agents(self) -> Dict[str, AgentDeclaration]:
        """Returns empty dict since host_services.yaml only contains services."""
        return {}

    def load_services(self) -> Dict[str, ServiceDeclaration]:
        """
        Load service declarations from host_services.yaml file.

        Returns:
            Dictionary mapping service names to ServiceDeclaration models
        """
        self.logger.debug("Loading host service declarations from YAML")

        file_path = self._get_host_services_path()
        yaml_data = load_yaml_file(file_path, self.logger)
        if not yaml_data or "services" not in yaml_data:
            self.logger.debug("No services section found in host_services.yaml")
            return {}

        services = {}
        services_data = yaml_data["services"]

        for service_name, service_data in services_data.items():
            try:
                normalized_data = self._normalize_service_data(service_data)
                source = f"{self.HOST_SERVICES_SOURCE_PREFIX}{file_path}"
                declaration = self.parser.parse_service(
                    service_name, normalized_data, source
                )
                services[service_name] = declaration
                self.logger.trace(f"Loaded host service: {service_name}")
            except Exception as e:
                self.logger.error(f"Failed to load host service '{service_name}': {e}")
                continue

        self.logger.debug(f"Loaded {len(services)} host service declarations")
        return services

    def _get_host_services_path(self) -> Path:
        """Get the path to the host_services.yaml file from configuration."""
        custom_agents_dir = self.config.get_custom_agents_path()
        return custom_agents_dir / "host_services.yaml"

    def _normalize_service_data(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize host_services.yaml format to parser-expected format.

        Args:
            service_data: Raw service data from host_services.yaml

        Returns:
            Normalized data for DeclarationParser
        """
        normalized = {
            "class_path": service_data.get("class_path") or service_data.get("class"),
        }

        # Map implements -> implements (protocol paths)
        if "implements" in service_data:
            normalized["implements"] = service_data["implements"]

        # Map dependencies -> dependencies
        if "dependencies" in service_data:
            normalized["dependencies"] = service_data["dependencies"]

        # Map config -> config
        if "config" in service_data:
            normalized["config"] = service_data["config"]

        # Map factory_method -> factory_method
        if "factory_method" in service_data:
            normalized["factory_method"] = service_data["factory_method"]

        return normalized
