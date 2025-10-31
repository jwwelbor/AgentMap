"""
Centralized builtin agent and service definitions for AgentMap.

This module consolidates all built-in agent and service declarations,
eliminating duplication between PythonDeclarationSource and AgentConfigService.
Provides a single source of truth for all built-in component definitions.
"""

from typing import Dict, List, Optional


class BuiltinDefinitionConstants:
    """
    Centralized constants for all built-in agents and services.

    Single source of truth to eliminate duplication and maintain consistency
    across the application. All agent class paths, service definitions, and
    metadata are defined here.
    """

    # ============ AGENT DEFINITIONS ============
    AGENTS = {
        # ============ CORE AGENTS ============
        "echo": {
            "class_path": "agentmap.agents.builtins.echo_agent.EchoAgent",
            "category": "core",
            "requires": [],
            "protocols_implemented": ["PromptCapableAgent"],
            "source": "builtin",
        },
        "default": {
            "class_path": "agentmap.agents.builtins.default_agent.DefaultAgent",
            "category": "core",
            "requires": [],
            "protocols_implemented": [],
            "source": "builtin",
        },
        "branching": {
            "class_path": "agentmap.agents.builtins.branching_agent.BranchingAgent",
            "category": "core",
            "requires": [],
            "protocols_implemented": [],
            "source": "builtin",
        },
        "success": {
            "class_path": "agentmap.agents.builtins.success_agent.SuccessAgent",
            "category": "core",
            "requires": [],
            "protocols_implemented": [],
            "source": "builtin",
        },
        "failure": {
            "class_path": "agentmap.agents.builtins.failure_agent.FailureAgent",
            "category": "core",
            "requires": [],
            "protocols_implemented": [],
            "source": "builtin",
        },
        "input": {
            "class_path": "agentmap.agents.builtins.input_agent.InputAgent",
            "category": "core",
            "requires": [],
            "protocols_implemented": [],
            "source": "builtin",
        },
        "suspend": {
            "class_path": "agentmap.agents.builtins.suspend_agent.SuspendAgent",
            "category": "core",
            "requires": [],
            "protocols_implemented": [],
            "source": "builtin",
        },
        "human": {
            "class_path": "agentmap.agents.builtins.human_agent.HumanAgent",
            "category": "core",
            "requires": [],
            "protocols_implemented": [],
            "source": "builtin",
        },
        "graph": {
            "class_path": "agentmap.agents.builtins.graph_agent.GraphAgent",
            "category": "core",
            "requires": ["graph_runner_service"],
            "protocols_implemented": [],
            "source": "builtin",
        },
        # ============ LLM AGENTS ============
        "llm": {
            "class_path": "agentmap.agents.builtins.llm.llm_agent.LLMAgent",
            "category": "llm",
            "provider": None,  # Works with any provider
            "requires": ["llm_service"],
            "protocols_implemented": ["LLMCapableAgent", "PromptCapableAgent"],
            "source": "builtin",
        },
        "anthropic": {
            "class_path": "agentmap.agents.builtins.llm.anthropic_agent.AnthropicAgent",
            "category": "llm",
            "provider": "anthropic",
            "requires": ["llm_service"],
            "protocols_implemented": ["LLMCapableAgent"],
            "source": "builtin",
        },
        "claude": {  # Alias for anthropic
            "class_path": "agentmap.agents.builtins.llm.anthropic_agent.AnthropicAgent",
            "category": "llm",
            "provider": "anthropic",
            "requires": ["llm_service"],
            "protocols_implemented": ["LLMCapableAgent"],
            "source": "builtin",
        },
        "openai": {
            "class_path": "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent",
            "category": "llm",
            "provider": "openai",
            "requires": ["llm_service"],
            "protocols_implemented": ["LLMCapableAgent"],
            "source": "builtin",
        },
        "gpt": {  # Alias for openai
            "class_path": "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent",
            "category": "llm",
            "provider": "openai",
            "requires": ["llm_service"],
            "protocols_implemented": ["LLMCapableAgent"],
            "source": "builtin",
        },
        "chatgpt": {  # Alias for openai
            "class_path": "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent",
            "category": "llm",
            "provider": "openai",
            "requires": ["llm_service"],
            "protocols_implemented": ["LLMCapableAgent"],
            "source": "builtin",
        },
        "google": {
            "class_path": "agentmap.agents.builtins.llm.google_agent.GoogleAgent",
            "category": "llm",
            "provider": "google",
            "requires": ["llm_service"],
            "protocols_implemented": ["LLMCapableAgent"],
            "source": "builtin",
        },
        "gemini": {  # Alias for google
            "class_path": "agentmap.agents.builtins.llm.google_agent.GoogleAgent",
            "category": "llm",
            "provider": "google",
            "requires": ["llm_service"],
            "protocols_implemented": ["LLMCapableAgent"],
            "source": "builtin",
        },
        # ============ STORAGE AGENTS ============
        "csv_reader": {
            "class_path": "agentmap.agents.builtins.storage.csv.reader.CSVReaderAgent",
            "category": "storage",
            "storage_type": "csv",
            "requires": ["storage_service_manager", "csv_service"],
            "protocols_implemented": ["CSVCapableAgent"],
            "source": "builtin",
        },
        "csv_writer": {
            "class_path": "agentmap.agents.builtins.storage.csv.writer.CSVWriterAgent",
            "category": "storage",
            "storage_type": "csv",
            "requires": ["storage_service_manager", "csv_service"],
            "protocols_implemented": ["CSVCapableAgent"],
            "source": "builtin",
        },
        "json_reader": {
            "class_path": "agentmap.agents.builtins.storage.json.reader.JSONDocumentReaderAgent",
            "category": "storage",
            "storage_type": "json",
            "requires": ["storage_service_manager", "json_service"],
            "protocols_implemented": ["JSONCapableAgent"],
            "source": "builtin",
        },
        "json_writer": {
            "class_path": "agentmap.agents.builtins.storage.json.writer.JSONDocumentWriterAgent",
            "category": "storage",
            "storage_type": "json",
            "requires": ["storage_service_manager", "json_service"],
            "protocols_implemented": ["JSONCapableAgent"],
            "source": "builtin",
        },
        "file_reader": {
            "class_path": "agentmap.agents.builtins.storage.file.reader.FileReaderAgent",
            "category": "storage",
            "storage_type": "file",
            "requires": ["storage_service_manager", "file_service"],
            "protocols_implemented": ["FileCapableAgent"],
            "source": "builtin",
        },
        "file_writer": {
            "class_path": "agentmap.agents.builtins.storage.file.writer.FileWriterAgent",
            "category": "storage",
            "storage_type": "file",
            "requires": ["storage_service_manager", "file_service"],
            "protocols_implemented": ["FileCapableAgent"],
            "source": "builtin",
        },
        "vector_reader": {
            "class_path": "agentmap.agents.builtins.storage.vector.reader.VectorReaderAgent",
            "category": "storage",
            "storage_type": "vector",
            "requires": [
                "logging_service",
                "storage_service_manager",
                "vector_service",
            ],
            "protocols_implemented": ["VectorCapableAgent"],
            "source": "builtin",
        },
        "vector_writer": {
            "class_path": "agentmap.agents.builtins.storage.vector.writer.VectorWriterAgent",
            "category": "storage",
            "storage_type": "vector",
            "requires": [
                "logging_service",
                "storage_service_manager",
                "vector_service",
            ],
            "protocols_implemented": ["VectorCapableAgent"],
            "source": "builtin",
        },
        # ============ MIXED DEPENDENCY AGENTS ============
        "summary": {
            "class_path": "agentmap.agents.builtins.summary_agent.SummaryAgent",
            "category": "mixed",
            "requires": ["logging_service"],
            "protocols_implemented": [],
            "source": "builtin",
        },
        "orchestrator": {
            "class_path": "agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent",
            "category": "mixed",
            "requires": ["orchestrator_service"],
            "protocols_implemented": ["LLMCapableAgent", "OrchestrationCapableAgent"],
            "source": "builtin",
        },
        # AGM-TOOLS-001: Tool agent for intelligent tool selection and execution
        "tool_agent": {
            "class_path": "agentmap.agents.builtins.tool_agent.ToolAgent",
            "category": "mixed",
            "requires": ["orchestrator_service"],
            "protocols_implemented": ["LLMCapableAgent", "ToolSelectionCapableAgent"],
            "source": "builtin",
        },
    }

    # ============ SERVICE DEFINITIONS ============
    SERVICES = {
        # ============ CORE SERVICES ============
        "logging_service": {
            "class_path": "agentmap.services.logging_service.LoggingService",
            "singleton": True,
            "required_services": [],
            "implements": [],
            "source": "builtin",
        },
        "config_service": {
            "class_path": "agentmap.services.config.config_service.ConfigService",
            "singleton": True,
            "required_services": [],
            "implements": [],
            "source": "builtin",
        },
        "app_config_service": {
            "class_path": "agentmap.services.config.app_config_service.AppConfigService",
            "singleton": True,
            "required_services": ["config_service", "logging_service"],
            "implements": [],
            "source": "builtin",
        },
        "storage_config_service": {
            "class_path": "agentmap.services.config.storage_config_service.StorageConfigService",
            "singleton": True,
            "required_services": ["config_service", "logging_service"],
            "implements": [],
            "source": "builtin",
        },
        "execution_tracking_service": {
            "class_path": "agentmap.services.execution_tracking_service.ExecutionTrackingService",
            "singleton": True,
            "required_services": ["logging_service"],
            "implements": ["ExecutionTrackingServiceProtocol"],
            "source": "builtin",
        },
        # ============ LLM SERVICES ============
        "llm_service": {
            "class_path": "agentmap.services.llm_service.LLMService",
            "singleton": True,
            "required_services": [
                "logging_service",
                "app_config_service",
                "llm_routing_service",
            ],
            "optional": ["config_service"],
            "implements": ["LLMServiceProtocol", "LLMCapableAgent"],
            "source": "builtin",
        },
        "llm_routing_service": {
            "class_path": "agentmap.services.routing.routing_service.LLMRoutingService",
            "singleton": True,
            "required_services": [
                "logging_service",
                "llm_routing_config_service",
                "routing_cache",
                "prompt_complexity_analyzer",
            ],
            "optional": ["config_service"],
            "implements": ["RoutingCapableAgent"],
            "source": "builtin",
        },
        "llm_routing_config_service": {
            "class_path": "agentmap.services.config.llm_routing_config_service.LLMRoutingConfigService",
            "singleton": True,
            "required_services": ["app_config_service", "logging_service"],
            "implements": [],
            "source": "builtin",
        },
        "routing_cache": {
            "class_path": "agentmap.services.routing.cache.RoutingCache",
            "singleton": True,
            "required_services": ["logging_service"],
            "implements": ["RoutingCacheProtocol"],
            "source": "builtin",
        },
        "prompt_complexity_analyzer": {
            "class_path": "agentmap.services.routing.complexity_analyzer.PromptComplexityAnalyzer",
            "singleton": True,
            "required_services": ["logging_service", "app_config_service"],
            "implements": ["PromptComplexityAnalyzerProtocol"],
            "source": "builtin",
        },
        # ============ ORCHESTRATION SERVICES ============
        "orchestrator_service": {
            "class_path": "agentmap.services.orchestrator_service.OrchestratorService",
            "singleton": True,
            "required_services": ["logging_service"],
            "implements": ["OrchestrationCapableAgent"],
            "source": "builtin",
        },
        # ============ STORAGE SERVICES ============
        "storage_service_manager": {
            "class_path": "agentmap.services.storage.manager.StorageServiceManager",
            "singleton": True,
            "required_services": ["logging_service", "storage_config_service"],
            "implements": ["StorageCapableAgent"],
            "source": "builtin",
        },
        "csv_service": {
            "class_path": "agentmap.services.csv_service.CSVService",
            "singleton": True,
            "required_services": ["logging_service"],
            "implements": ["CSVCapableAgent"],
            "source": "builtin",
        },
        "json_service": {
            "class_path": "agentmap.services.json_service.JSONService",
            "singleton": True,
            "required_services": ["logging_service"],
            "implements": ["JSONCapableAgent"],
            "source": "builtin",
        },
        "vector_service": {
            "class_path": "agentmap.services.storage.vector_service.VectorService",
            "singleton": True,
            "required_services": ["logging_service"],
            "implements": ["VectorCapableAgent"],
            "source": "builtin",
        },
        "file_service": {
            "class_path": "agentmap.services.storage.file_service.FileService",
            "singleton": True,
            "required_services": ["logging_service"],
            "implements": ["FileCapableAgent"],
            "source": "builtin",
        },
        "blob_storage_service": {
            "class_path": "agentmap.services.storage.blob_storage_service.BlobStorageService",
            "singleton": True,
            "required_services": ["logging_service"],
            "implements": ["BlobStorageCapableAgent", "BlobStorageServiceProtocol"],
            "source": "builtin",
        },
        # ============ FEATURE SERVICES ============
        "memory_service": {
            "class_path": "agentmap.services.memory_service.MemoryService",
            "singleton": True,
            "required_services": ["logging_service"],
            "implements": ["MemoryCapableAgent"],
            "source": "builtin",
        },
        "prompt_manager_service": {
            "class_path": "agentmap.services.prompt_manager_service.PromptManagerService",
            "singleton": True,
            "required_services": ["logging_service", "app_config_service"],
            "implements": ["PromptCapableAgent", "PromptManagerServiceProtocol"],
            "source": "builtin",
        },
    }

    # Technical dependency mappings
    LLM_PROVIDER_DEPENDENCIES = {
        "openai": ["langchain_openai"],
        "anthropic": ["langchain_anthropic"],
        "google": ["langchain_google_genai"],
        "langchain": ["langchain_core"],
    }

    STORAGE_TYPE_DEPENDENCIES = {
        "csv": ["pandas"],
        "vector": ["langchain", "chromadb"],
        "firebase": ["firebase_admin"],
        "azure_blob": ["azure-storage-blob"],
        "aws_s3": ["boto3"],
        "gcp_storage": ["google-cloud-storage"],
    }

    @classmethod
    def get_provider_dependencies(cls, provider: str) -> List[str]:
        """Get technical dependencies for LLM provider."""
        return cls.LLM_PROVIDER_DEPENDENCIES.get(provider, [])

    @classmethod
    def get_storage_dependencies(cls, storage_type: str) -> List[str]:
        """Get technical dependencies for storage type."""
        return cls.STORAGE_TYPE_DEPENDENCIES.get(storage_type, [])

    @classmethod
    def get_supported_llm_providers(cls) -> List[str]:
        """Get list of supported LLM providers."""
        return list(cls.LLM_PROVIDER_DEPENDENCIES.keys())

    @classmethod
    def get_supported_storage_types(cls) -> List[str]:
        """Get list of supported storage types."""
        return list(cls.STORAGE_TYPE_DEPENDENCIES.keys())

    # ============ HELPER METHODS ============

    @classmethod
    def get_agents_by_category(cls, category: str) -> Dict:
        """
        Get all agents in a specific category.

        Args:
            category: Category name ('core', 'llm', 'storage', 'mixed')

        Returns:
            Dictionary of agents in the specified category
        """
        return {k: v for k, v in cls.AGENTS.items() if v.get("category") == category}

    @classmethod
    def get_agent_class_path(cls, agent_type: str) -> Optional[str]:
        """
        Get class path for a specific agent type.

        Args:
            agent_type: Agent type name

        Returns:
            Class path string or None if not found
        """
        agent = cls.AGENTS.get(agent_type, {})
        return agent.get("class_path")

    @classmethod
    def get_agent_class_paths(cls) -> Dict[str, str]:
        """
        Get simple mapping of all agent types to class paths.

        Returns:
            Dictionary mapping agent types to class paths
        """
        return {k: v["class_path"] for k, v in cls.AGENTS.items()}

    @classmethod
    def get_service_class_path(cls, service_name: str) -> Optional[str]:
        """
        Get class path for a specific service.

        Args:
            service_name: Service name

        Returns:
            Class path string or None if not found
        """
        service = cls.SERVICES.get(service_name, {})
        return service.get("class_path")

    @classmethod
    def get_service_class_paths(cls) -> Dict[str, str]:
        """
        Get simple mapping of all service names to class paths.

        Returns:
            Dictionary mapping service names to class paths
        """
        return {k: v["class_path"] for k, v in cls.SERVICES.items()}

    @classmethod
    def get_agents_by_provider(cls, provider: str) -> Dict:
        """
        Get all agents for a specific LLM provider.

        Args:
            provider: Provider name ('openai', 'anthropic', 'google')

        Returns:
            Dictionary of agents for the specified provider
        """
        return {k: v for k, v in cls.AGENTS.items() if v.get("provider") == provider}

    @classmethod
    def get_agents_by_storage_type(cls, storage_type: str) -> Dict:
        """
        Get all agents for a specific storage type.

        Args:
            storage_type: Storage type ('csv', 'json', 'file', 'vector')

        Returns:
            Dictionary of agents for the specified storage type
        """
        return {
            k: v for k, v in cls.AGENTS.items() if v.get("storage_type") == storage_type
        }

    @classmethod
    def is_llm_agent(cls, agent_type: str) -> bool:
        """
        Check if an agent is an LLM agent.

        Args:
            agent_type: Agent type name

        Returns:
            True if the agent is an LLM agent, False otherwise
        """
        agent = cls.AGENTS.get(agent_type, {})
        return agent.get("category") == "llm"

    @classmethod
    def is_storage_agent(cls, agent_type: str) -> bool:
        """
        Check if an agent is a storage agent.

        Args:
            agent_type: Agent type name

        Returns:
            True if the agent is a storage agent, False otherwise
        """
        agent = cls.AGENTS.get(agent_type, {})
        return agent.get("category") == "storage"

    @classmethod
    def is_core_agent(cls, agent_type: str) -> bool:
        """
        Check if an agent is a core agent.

        Args:
            agent_type: Agent type name

        Returns:
            True if the agent is a core agent, False otherwise
        """
        agent = cls.AGENTS.get(agent_type, {})
        return agent.get("category") == "core"

    @classmethod
    def is_mixed_dependency_agent(cls, agent_type: str) -> bool:
        """
        Check if an agent has mixed dependencies.

        Args:
            agent_type: Agent type name

        Returns:
            True if the agent has mixed dependencies, False otherwise
        """
        agent = cls.AGENTS.get(agent_type, {})
        return agent.get("category") == "mixed"

    @classmethod
    def get_agent_protocols(cls, agent_type: str) -> list:
        """
        Get protocols implemented by an agent.

        Args:
            agent_type: Agent type name

        Returns:
            List of protocol names
        """
        agent = cls.AGENTS.get(agent_type, {})
        return agent.get("protocols_implemented", [])

    @classmethod
    def get_agent_requirements(cls, agent_type: str) -> list:
        """
        Get required services for an agent.

        Args:
            agent_type: Agent type name

        Returns:
            List of required service names
        """
        agent = cls.AGENTS.get(agent_type, {})
        return agent.get("requires", [])

    @classmethod
    def get_agent_to_storage_type(cls) -> Dict[str, str]:
        """
        Get mapping from agent types to their storage types.

        Returns:
            Dictionary mapping agent types to storage type names
        """
        result = {}
        for agent_type, agent_data in cls.AGENTS.items():
            storage_type = agent_data.get("storage_type")
            if storage_type:
                result[agent_type] = storage_type
        return result

    @classmethod
    def get_llm_agent_to_provider(cls) -> Dict[str, Optional[str]]:
        """
        Get mapping from LLM agent types to their providers.

        Returns:
            Dictionary mapping LLM agent types to provider names (None = any provider)
        """
        result = {}
        for agent_type, agent_data in cls.AGENTS.items():
            if agent_data.get("category") == "llm":
                result[agent_type] = agent_data.get("provider")
        return result
