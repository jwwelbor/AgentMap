"""
Declaration source implementations for AgentMap.

Provides pluggable architecture for loading agent and service declarations
from different sources (Python dicts, YAML files, etc.).
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

from agentmap.core.builtin_definition_constants import BuiltinDefinitionConstants
from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration
from agentmap.services.declaration_parser import DeclarationParser
from agentmap.services.logging_service import LoggingService


class DeclarationSource(ABC):
    """
    Abstract base class for declaration sources.

    Provides a common interface for loading agent and service declarations
    from various sources while ensuring consistent return formats.
    """

    @abstractmethod
    def load_agents(self) -> Dict[str, AgentDeclaration]:
        """
        Load agent declarations from this source.

        Returns:
            Dictionary mapping agent types to AgentDeclaration models
        """
        pass

    @abstractmethod
    def load_services(self) -> Dict[str, ServiceDeclaration]:
        """
        Load service declarations from this source.

        Returns:
            Dictionary mapping service names to ServiceDeclaration models
        """
        pass


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
                "protocols_implemented": agent_data.get("protocols_implemented", [])
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
                "implements": service_data.get("implements", [])
            }
            for service_name, service_data in BuiltinDefinitionConstants.SERVICES.items()
        }
    
    @property
    def CORE_SERVICES(self):
        """Get core service definitions for backward compatibility."""
        core_service_names = [
            "logging_service", "config_service", "app_config_service",
            "storage_config_service", "execution_tracking_service"
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
        self.logger.debug("[PythonDeclarationSource] Initialized with built-in declarations")

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
                self.logger.debug(f"Loaded built-in agent: {agent_type}")
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
                declaration = self.parser.parse_service(service_name, service_data, "builtin")
                services[service_name] = declaration
                self.logger.debug(f"Loaded built-in service: {service_name}")
            except Exception as e:
                self.logger.error(f"Failed to load built-in service '{service_name}': {e}")
                continue

        self.logger.debug(f"Loaded {len(services)} built-in service declarations")
        return services


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
        
        yaml_data = self._load_yaml_file()
        if not yaml_data or "agents" not in yaml_data:
            self.logger.debug("No agents section found in YAML file")
            return {}

        agents = {}
        agents_data = yaml_data["agents"]

        for agent_type, agent_data in agents_data.items():
            try:
                # Apply namespace prefix if provided
                full_agent_type = f"{self.namespace}.{agent_type}" if self.namespace else agent_type
                
                declaration = self.parser.parse_agent(
                    full_agent_type, agent_data, f"yaml:{self.path}"
                )
                agents[full_agent_type] = declaration
                self.logger.debug(f"Loaded YAML agent: {full_agent_type}")
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
        
        yaml_data = self._load_yaml_file()
        if not yaml_data or "services" not in yaml_data:
            self.logger.debug("No services section found in YAML file")
            return {}

        services = {}
        services_data = yaml_data["services"]

        for service_name, service_data in services_data.items():
            try:
                # Apply namespace prefix if provided
                full_service_name = f"{self.namespace}.{service_name}" if self.namespace else service_name
                
                declaration = self.parser.parse_service(
                    full_service_name, service_data, f"yaml:{self.path}"
                )
                services[full_service_name] = declaration
                self.logger.debug(f"Loaded YAML service: {full_service_name}")
            except Exception as e:
                self.logger.error(f"Failed to load YAML service '{service_name}': {e}")
                continue

        self.logger.debug(f"Loaded {len(services)} service declarations from YAML")
        return services

    def _load_yaml_file(self) -> Dict[str, Any]:
        """
        Load and parse YAML file with graceful error handling.

        Returns:
            Parsed YAML data as dictionary, or empty dict if file missing/invalid
        """
        if not self.path.exists():
            self.logger.warning(f"YAML declaration file not found: {self.path}")
            return {}

        if not self.path.is_file():
            self.logger.warning(f"YAML declaration path is not a file: {self.path}")
            return {}

        try:
            import yaml
            
            with open(self.path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                
            if not isinstance(data, dict):
                self.logger.warning(f"YAML file does not contain valid dictionary: {self.path}")
                return {}
                
            self.logger.debug(f"Successfully loaded YAML file: {self.path}")
            return data
            
        except ImportError:
            self.logger.error("PyYAML not available - cannot load YAML declaration files")
            return {}
        except yaml.YAMLError as e:
            self.logger.error(f"Failed to parse YAML file '{self.path}': {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Failed to load YAML file '{self.path}': {e}")
            return {}
