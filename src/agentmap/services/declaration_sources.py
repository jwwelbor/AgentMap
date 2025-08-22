"""
Declaration source implementations for AgentMap.

Provides pluggable architecture for loading agent and service declarations
from different sources (Python dicts, YAML files, etc.).
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

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

    Provides core agent and service declarations without external dependencies.
    Uses hardcoded dictionaries for fast, reliable access to built-in components.
    """

    # Built-in agent declarations
    BUILTIN_AGENTS = {
        "echo": {
            "class_path": "agentmap.agents.builtins.echo_agent.EchoAgent",
            "requires": ["logging_service"],
            "protocols_implemented": []  # EchoAgent doesn't implement any protocols
        },
        "default": {
            "class_path": "agentmap.agents.builtins.default_agent.DefaultAgent",
            "requires": ["logging_service"],
            "protocols_implemented": []  # DefaultAgent doesn't implement any protocols
        },
        "success": {
            "class_path": "agentmap.agents.builtins.success_agent.SuccessAgent",
            "requires": ["logging_service"],
            "protocols_implemented": []  # SuccessAgent doesn't implement any protocols
        },
        "failure": {
            "class_path": "agentmap.agents.builtins.failure_agent.FailureAgent",
            "requires": ["logging_service"],
            "protocols_implemented": []  # FailureAgent doesn't implement any protocols
        },
        "input": {
            "class_path": "agentmap.agents.builtins.input_agent.InputAgent",
            "requires": ["logging_service"],
            "protocols_implemented": []  # InputAgent doesn't implement any protocols
        },
        "human": {
            "class_path": "agentmap.agents.builtins.human_agent.HumanAgent",
            "requires": ["logging_service"],
            "protocols_implemented": []  # HumanAgent doesn't implement any protocols
        },
        "branching": {
            "class_path": "agentmap.agents.builtins.branching_agent.BranchingAgent",
            "requires": ["logging_service"],
            "protocols_implemented": []  # BranchingAgent doesn't implement any protocols
        },
        "orchestrator": {
            "class_path": "agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent",
            "requires": ["logging_service", "orchestrator_service"],
            "protocols_implemented": ["LLMCapableAgent", "OrchestrationCapableAgent"]
        },
        "graph": {
            "class_path": "agentmap.agents.builtins.graph_agent.GraphAgent",
            "requires": ["logging_service", "graph_runner_service"],
            "protocols_implemented": []  # GraphAgent doesn't implement any protocols yet
        },
        "summary": {
            "class_path": "agentmap.agents.builtins.summary_agent.SummaryAgent",
            "requires": ["logging_service"],
            "protocols_implemented": []  # SummaryAgent doesn't implement any protocols
        },
        
        # LLM agents
        "llm": {
            "class_path": "agentmap.agents.builtins.llm.llm_agent.LLMAgent",
            "requires": ["logging_service", "llm_service"],
            "protocols_implemented": ["LLMCapableAgent", "PromptCapableAgent"]
        },
        "anthropic": {
            "class_path": "agentmap.agents.anthropic.AnthropicAgent",
            "requires": ["logging_service", "llm_service"],
            "protocols_implemented": ["LLMCapableAgent"]
        },
        "openai": {
            "class_path": "agentmap.agents.openai.OpenAIAgent",
            "requires": ["logging_service", "llm_service"],
            "protocols_implemented": ["LLMCapableAgent"]
        },
        "google": {
            "class_path": "agentmap.agents.google.GoogleAgent",
            "requires": ["logging_service", "llm_service"],
            "protocols_implemented": ["LLMCapableAgent"]
        },
        
        # Storage agents - updated with correct paths and protocols
        "csv_reader": {
            "class_path": "agentmap.agents.builtins.storage.csv.reader.CSVReaderAgent",
            "requires": ["logging_service", "storage_service_manager", "csv_service"],
            "protocols_implemented": ["CSVCapableAgent"]
        },
        "csv_writer": {
            "class_path": "agentmap.agents.builtins.storage.csv.writer.CSVWriterAgent",
            "requires": ["logging_service", "storage_service_manager", "csv_service"],
            "protocols_implemented": ["CSVCapableAgent"]
        },
        "json_reader": {
            "class_path": "agentmap.agents.builtins.storage.json.reader.JSONReaderAgent",
            "requires": ["logging_service", "storage_service_manager", "json_service"],
            "protocols_implemented": ["JSONCapableAgent"]
        },
        "json_writer": {
            "class_path": "agentmap.agents.builtins.storage.json.writer.JSONWriterAgent",
            "requires": ["logging_service", "storage_service_manager", "json_service"],
            "protocols_implemented": ["JSONCapableAgent"]
        }
    }

    CORE_SERVICES = {
        "logging_service": {
            "class_path": "agentmap.services.logging_service.LoggingService",
            "singleton": True,
            "implements": []
        },
        "config_service": {
            "class_path": "agentmap.services.config.config_service.ConfigService",
            "singleton": True,
            "implements": []
        },
        "app_config_service": {
            "class_path": "agentmap.services.config.app_config_service.AppConfigService",
            "required_services": ["config_service", "logging_service"],
            "singleton": True,
            "implements": []
        },
        "storage_config_service": {
            "class_path": "agentmap.services.config.storage_config_service.StorageConfigService",
            "required_services": ["config_service", "logging_service"],
            "singleton": True,
            "implements": []
        },
        "execution_tracking_service": {
            "class_path": "agentmap.services.execution_tracking_service.ExecutionTrackingService",
            "required_services": ["logging_service"],
            "singleton": True,
            "implements": ["ExecutionTrackingServiceProtocol"]
        },
        # these would only be used internally
        # "agent_registry_service": {
        #     "class_path": "agentmap.services.agent_registry_service.AgentRegistryService",
        #     "required_services": ["logging_service"],
        #     "singleton": True,
        #     "implements": []
        # },
        # "features_registry_service": {
        #     "class_path": "agentmap.services.features_registry_service.FeaturesRegistryService",
        #     "required_services": ["logging_service"],
        #     "singleton": True,
        #     "implements": ["FeaturesRegistryServiceProtocol"]
        # },
        # "agent_factory_service": {
        #     "class_path": "agentmap.services.agent_factory_service.AgentFactoryService",
        #     "required_services": ["agent_registry_service", "features_registry_service", "logging_service"],
        #     "singleton": True,
        #     "implements": []
        # },
        # "graph_factory_service": {
        #     "class_path": "agentmap.services.graph_factory_service.GraphFactoryService",
        #     "required_services": ["logging_service"],
        #     "singleton": True,
        #     "implements": ["GraphFactoryServiceProtocol"]
        # },
    }


    # Built-in service declarations
    BUILTIN_SERVICES = {
        "llm_service": {
            "class_path": "agentmap.services.llm_service.LLMService",
            "required_services": ["logging_service", "app_config_service", "llm_routing_service"],
            "optional": ["config_service"],
            "singleton": True,
            "implements": ["LLMServiceProtocol", "LLMCapableAgent"]
        },
        "llm_routing_service": {
            "class_path": "agentmap.services.routing.routing_service.LLMRoutingService",
            "required_services": ["logging_service", "llm_routing_config_service", "routing_cache", "prompt_complexity_analyzer"],
            "optional": ["config_service"],
            "singleton": True,
            "implements": ["RoutingCapableAgent"]
        },
        "llm_routing_config_service": {
            "class_path": "agentmap.services.config.llm_routing_config_service.LLMRoutingConfigService",
            "required_services": ["app_config_service", "logging_service"],
            "singleton": True,
            "implements": []
        },
        "routing_cache": {
            "class_path": "agentmap.services.routing.cache.RoutingCache",
            "required_services": ["logging_service"],
            "singleton": True,
            "implements": ["RoutingCacheProtocol"]
        },
        "prompt_complexity_analyzer": {
            "class_path": "agentmap.services.routing.complexity_analyzer.PromptComplexityAnalyzer",
            "required_services": ["logging_service", "app_config_service"],
            "singleton": True,
            "implements": ["PromptComplexityAnalyzerProtocol"]
        },
        "orchestrator_service": {
            "class_path": "agentmap.services.orchestrator_service.OrchestratorService",
            "required_services": ["logging_service"],
            "singleton": True,
            "implements": ["OrchestrationCapableAgent"]
        },
        "node_registry"
        "graph_checkpoint_service": {
            "class_path": "agentmap.services.graph.graph_checkpoint_service.GraphCheckpointService",
            "required_services": ["logging_service"],
            "singleton": True,
            "implements": ["CheckpointCapableAgent", "GraphCheckpointServiceProtocol"]
        },
        "storage_service_manager": {
            "class_path": "agentmap.services.storage.manager.StorageServiceManager",
            "required_services": ["logging_service", "storage_config_service"],
            "singleton": True,
            "implements": ["StorageCapableAgent"]
        },
        "memory_service": {
            "class_path": "agentmap.services.memory_service.MemoryService",
            "required_services": ["logging_service"],
            "singleton": True,
            "implements": ["MemoryCapableAgent"]
        },
        "prompt_manager_service": {
            "class_path": "agentmap.services.prompt_manager_service.PromptManagerService",
            "required_services": ["logging_service", "app_config_service"],
            "singleton": True,
            "implements": ["PromptCapableAgent", "PromptManagerServiceProtocol"]
        },
        "csv_service": {
            "class_path": "agentmap.services.csv_service.CSVService",
            "required_services": ["logging_service"],
            "singleton": True,
            "implements": ["CSVCapableAgent"]
        },
        "json_service": {
            "class_path": "agentmap.services.json_service.JSONService",
            "required_services": ["logging_service"],
            "singleton": True,
            "implements": ["JSONCapableAgent"]
        },
        "vector_service": {
            "class_path": "agentmap.services.storage.vector_service.VectorService",
            "required_services": ["logging_service"],
            "singleton": True,
            "implements": ["VectorCapableAgent"]
        },
        "file_service": {
            "class_path": "agentmap.services.storage.file_service.FileService",
            "required_services": ["logging_service"],
            "singleton": True,
            "implements": ["FileCapableAgent"]
        },
        "blob_storage_service": {
            "class_path": "agentmap.services.storage.blob_storage_service.BlobStorageService",
            "required_services": ["logging_service"],
            "singleton": True,
            "implements": ["BlobStorageCapableAgent", "BlobStorageServiceProtocol"]
        },
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
