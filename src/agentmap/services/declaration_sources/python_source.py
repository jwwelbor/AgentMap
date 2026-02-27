"""Python dictionary declaration source for built-in agents and services."""

from typing import Dict

from agentmap.builtin_definition_constants import BuiltinDefinitionConstants
from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration
from agentmap.services.declaration_parser import DeclarationParser
from agentmap.services.declaration_sources.base import DeclarationSource
from agentmap.services.logging_service import LoggingService


class PythonDeclarationSource(DeclarationSource):
    """
    Declaration source for built-in Python dictionary declarations.

    Delegates to BuiltinDefinitionConstants for the actual definitions,
    maintaining backward compatibility while eliminating duplication.
    """

    # Legacy attributes for backward compatibility (delegate to BuiltinDefinitionConstants)
    @property
    def BUILTIN_AGENTS(self):
        """Get agent definitions from centralized constants."""
        # Transform to match old format (without category/provider metadata)
        return {
            agent_type: {
                "class_path": agent_data["class_path"],
                "requires": agent_data.get("requires", []),
                "protocols_implemented": agent_data.get("protocols_implemented", []),
            }
            for agent_type, agent_data in BuiltinDefinitionConstants.AGENTS.items()
        }

    @property
    def BUILTIN_SERVICES(self):
        """Get service definitions from centralized constants."""
        # Transform to match old format
        return {
            service_name: {
                "class_path": service_data["class_path"],
                "required_services": service_data.get("required_services", []),
                "optional": service_data.get("optional", []),
                "singleton": service_data.get("singleton", True),
                "implements": service_data.get("implements", []),
            }
            for service_name, service_data in BuiltinDefinitionConstants.SERVICES.items()
        }

    @property
    def CORE_SERVICES(self):
        """Get core service definitions for backward compatibility."""
        core_service_names = [
            "logging_service",
            "config_service",
            "app_config_service",
            "storage_config_service",
            "execution_tracking_service",
        ]
        return {
            name: self.BUILTIN_SERVICES[name]
            for name in core_service_names
            if name in self.BUILTIN_SERVICES
        }

    def __init__(self, parser: DeclarationParser, logging_service: LoggingService):
        """Initialize with dependency injection."""
        self.parser = parser
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug(
            "[PythonDeclarationSource] Initialized with built-in declarations"
        )

    def load_agents(self) -> Dict[str, AgentDeclaration]:
        """
        Load built-in agent declarations from Python dictionaries.

        Returns:
            Dictionary mapping agent types to AgentDeclaration models
        """
        self.logger.debug("Loading built-in agent declarations")
        agents = {}

        for agent_type, agent_data in self.BUILTIN_AGENTS.items():
            try:
                declaration = self.parser.parse_agent(agent_type, agent_data, "builtin")
                agents[agent_type] = declaration
                self.logger.trace(f"Loaded built-in agent: {agent_type}")
            except Exception as e:
                self.logger.error(f"Failed to load built-in agent '{agent_type}': {e}")
                continue

        self.logger.debug(f"Loaded {len(agents)} built-in agent declarations")
        return agents

    def load_services(self) -> Dict[str, ServiceDeclaration]:
        """
        Load built-in service declarations from Python dictionaries.

        Returns:
            Dictionary mapping service names to ServiceDeclaration models
        """
        self.logger.debug("Loading built-in service declarations")
        services = {}

        for service_name, service_data in self.BUILTIN_SERVICES.items():
            try:
                declaration = self.parser.parse_service(
                    service_name, service_data, "builtin"
                )
                services[service_name] = declaration
                self.logger.trace(f"Loaded built-in service: {service_name}")
            except Exception as e:
                self.logger.error(
                    f"Failed to load built-in service '{service_name}': {e}"
                )
                continue

        self.logger.debug(f"Loaded {len(services)} built-in service declarations")
        return services
