"""Custom agents YAML declaration source."""

from pathlib import Path
from typing import Any, Dict

from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration
from agentmap.services.declaration_parser import DeclarationParser
from agentmap.services.declaration_sources.base import DeclarationSource
from agentmap.services.declaration_sources.yaml_loader import load_yaml_file
from agentmap.services.logging_service import LoggingService


class CustomAgentYAMLSource(DeclarationSource):
    """
    Declaration source for custom_agents.yaml file.

    Loads agent declarations from custom_agents.yaml file and converts them to
    AgentDeclaration models for use by DeclarationRegistryService. Integrates with
    the scaffolding system to enable proper agent registration and service injection.
    """

    def __init__(
        self,
        app_config_service,  # Importing directly would create circular dependency
        parser: DeclarationParser,
        logging_service: LoggingService,
    ):
        """
        Initialize CustomAgentYAMLSource with dependency injection.

        Args:
            app_config_service: Application configuration service for file paths
            parser: Declaration parser for normalizing agent data
            logging_service: Logging service for error reporting
        """
        self.config = app_config_service
        self.parser = parser
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[CustomAgentYAMLSource] Initialized")

    def load_agents(self) -> Dict[str, AgentDeclaration]:
        """
        Load agent declarations from custom_agents.yaml file.

        Returns:
            Dictionary mapping agent types to AgentDeclaration models
        """
        self.logger.debug("Loading custom agent declarations from YAML")

        # Get custom_agents.yaml path from configuration
        file_path = self._get_custom_agents_path()

        # Load YAML data
        yaml_data = load_yaml_file(file_path, self.logger)
        if not yaml_data or "agents" not in yaml_data:
            self.logger.debug("No agents section found in custom_agents.yaml")
            return {}

        agents = {}
        agents_data = yaml_data["agents"]

        for agent_type, agent_data in agents_data.items():
            try:
                # Convert custom_agents.yaml format to parser-expected format
                normalized_data = self._normalize_agent_data(agent_data)

                declaration = self.parser.parse_agent(
                    agent_type, normalized_data, f"yaml:{file_path}"
                )
                agents[agent_type] = declaration
                self.logger.trace(f"Loaded custom agent: {agent_type}")
            except Exception as e:
                self.logger.error(f"Failed to load custom agent '{agent_type}': {e}")
                continue

        self.logger.debug(f"Loaded {len(agents)} custom agent declarations")
        return agents

    def load_services(self) -> Dict[str, ServiceDeclaration]:
        """
        Load service declarations from custom_agents.yaml file.

        Returns:
            Empty dictionary since custom_agents.yaml only contains agent declarations
        """
        self.logger.debug(
            "No custom services - custom_agents.yaml only contains agents"
        )
        return {}

    def _get_custom_agents_path(self) -> Path:
        """
        Get the path to the custom_agents.yaml file from configuration.

        Places the YAML file in the same directory as the Python agent files
        for easier management and co-location of related files.

        Returns:
            Path object pointing to custom_agents.yaml file
        """
        # Use the same directory as the Python agent files
        # This ensures the YAML declarations are co-located with the code
        custom_agents_dir = self.config.get_custom_agents_path()

        # Place custom_agents.yaml in the same directory as the Python files
        return custom_agents_dir / "custom_agents.yaml"

    def _normalize_agent_data(self, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize custom_agents.yaml format to parser-expected format.

        Args:
            agent_data: Raw agent data from custom_agents.yaml

        Returns:
            Normalized data for DeclarationParser
        """
        normalized = {
            "class_path": agent_data.get("class") or agent_data.get("class_path")
        }

        # Handle requires section
        requires = agent_data.get("requires", {})
        if isinstance(requires, dict):
            # Extract services and protocols from requires section
            services = requires.get("services", [])
            protocols = requires.get("protocols", [])

            # Convert to expected format for parser
            if services:
                normalized["services"] = services
            if protocols:
                normalized["protocols_implemented"] = protocols

        return normalized
