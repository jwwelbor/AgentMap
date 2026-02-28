"""YAML file declaration source for agent and service declarations."""

from pathlib import Path
from typing import Dict

from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration
from agentmap.services.declaration_parser import DeclarationParser
from agentmap.services.declaration_sources.base import DeclarationSource
from agentmap.services.declaration_sources.yaml_loader import load_yaml_file
from agentmap.services.logging_service import LoggingService


class YAMLDeclarationSource(DeclarationSource):
    """
    Declaration source for YAML file declarations.

    Loads agent and service declarations from YAML files with optional
    namespace prefixing and graceful error handling for missing files.
    """

    def __init__(
        self,
        path: Path,
        parser: DeclarationParser,
        logging_service: LoggingService,
        namespace: str = "",
    ):
        """
        Initialize YAML declaration source.

        Args:
            path: Path to YAML file containing declarations
            parser: Declaration parser for normalization
            logging_service: Logging service for error reporting
            namespace: Optional namespace prefix for agent/service names
        """
        self.path = Path(path)
        self.parser = parser
        self.namespace = namespace
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug(f"[YAMLDeclarationSource] Initialized for path: {self.path}")

    def load_agents(self) -> Dict[str, AgentDeclaration]:
        """
        Load agent declarations from YAML file.

        Returns:
            Dictionary mapping agent types to AgentDeclaration models
        """
        self.logger.debug(f"Loading agent declarations from YAML: {self.path}")

        yaml_data = load_yaml_file(self.path, self.logger)
        if not yaml_data or "agents" not in yaml_data:
            self.logger.debug("No agents section found in YAML file")
            return {}

        agents = {}
        agents_data = yaml_data["agents"]

        for agent_type, agent_data in agents_data.items():
            try:
                # Apply namespace prefix if provided
                full_agent_type = (
                    f"{self.namespace}.{agent_type}" if self.namespace else agent_type
                )

                declaration = self.parser.parse_agent(
                    full_agent_type, agent_data, f"yaml:{self.path}"
                )
                agents[full_agent_type] = declaration
                self.logger.trace(f"Loaded YAML agent: {full_agent_type}")
            except Exception as e:
                self.logger.error(f"Failed to load YAML agent '{agent_type}': {e}")
                continue

        self.logger.debug(f"Loaded {len(agents)} agent declarations from YAML")
        return agents

    def load_services(self) -> Dict[str, ServiceDeclaration]:
        """
        Load service declarations from YAML file.

        Returns:
            Dictionary mapping service names to ServiceDeclaration models
        """
        self.logger.debug(f"Loading service declarations from YAML: {self.path}")

        yaml_data = load_yaml_file(self.path, self.logger)
        if not yaml_data or "services" not in yaml_data:
            self.logger.debug("No services section found in YAML file")
            return {}

        services = {}
        services_data = yaml_data["services"]

        for service_name, service_data in services_data.items():
            try:
                # Apply namespace prefix if provided
                full_service_name = (
                    f"{self.namespace}.{service_name}"
                    if self.namespace
                    else service_name
                )

                declaration = self.parser.parse_service(
                    full_service_name, service_data, f"yaml:{self.path}"
                )
                services[full_service_name] = declaration
                self.logger.trace(f"Loaded YAML service: {full_service_name}")
            except Exception as e:
                self.logger.error(f"Failed to load YAML service '{service_name}': {e}")
                continue

        self.logger.debug(f"Loaded {len(services)} service declarations from YAML")
        return services
