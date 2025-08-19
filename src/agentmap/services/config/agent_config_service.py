"""
AgentConfigService for AgentMap.

Centralized configuration for all agent mappings and constants.
Provides static methods to access agent class paths and mappings.
"""

from typing import Dict


class AgentConfigService:
    """
    Centralized configuration service for agent mappings and constants.
    
    All agent class paths and type mappings are defined here to maintain DRY principle
    and provide a single source of truth for agent configuration across the application.
    """

    # Core agent mappings - always available regardless of dependencies
    _CORE_AGENTS = {
        "default": "agentmap.agents.builtins.default_agent.DefaultAgent",
        "echo": "agentmap.agents.builtins.echo_agent.EchoAgent",
        "branching": "agentmap.agents.builtins.branching_agent.BranchingAgent",
        "failure": "agentmap.agents.builtins.failure_agent.FailureAgent",
        "success": "agentmap.agents.builtins.success_agent.SuccessAgent",
        "input": "agentmap.agents.builtins.input_agent.InputAgent",
        "graph": "agentmap.agents.builtins.graph_agent.GraphAgent",
        "human": "agentmap.agents.builtins.human_agent.HumanAgent",
    }

    # LLM agent mappings - require LLM provider dependencies
    _LLM_AGENTS = {
        "llm": "agentmap.agents.builtins.llm.llm_agent.LLMAgent",  # Base LLM agent
        "openai": "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent",
        "gpt": "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent",
        "chatgpt": "agentmap.agents.builtins.llm.openai_agent.OpenAIAgent",
        "anthropic": "agentmap.agents.builtins.llm.anthropic_agent.AnthropicAgent",
        "claude": "agentmap.agents.builtins.llm.anthropic_agent.AnthropicAgent",
        "google": "agentmap.agents.builtins.llm.google_agent.GoogleAgent",
        "gemini": "agentmap.agents.builtins.llm.google_agent.GoogleAgent",
    }

    # Storage agent mappings - require storage provider dependencies
    _STORAGE_AGENTS = {
        "csv_reader": "agentmap.agents.builtins.storage.csv.reader.CSVReaderAgent",
        "csv_writer": "agentmap.agents.builtins.storage.csv.writer.CSVWriterAgent",
        "json_reader": "agentmap.agents.builtins.storage.json.reader.JSONDocumentReaderAgent",
        "json_writer": "agentmap.agents.builtins.storage.json.writer.JSONDocumentWriterAgent",
        "file_reader": "agentmap.agents.builtins.storage.file.reader.FileReaderAgent",
        "file_writer": "agentmap.agents.builtins.storage.file.writer.FileWriterAgent",
        "vector_reader": "agentmap.agents.builtins.storage.vector.reader.VectorReaderAgent",
        "vector_writer": "agentmap.agents.builtins.storage.vector.writer.VectorWriterAgent",
    }

    # Mixed dependency agent mappings - may require combinations of features
    _MIXED_DEPENDENCY_AGENTS = {
        "summary": "agentmap.agents.builtins.summary_agent.SummaryAgent",
        "orchestrator": "agentmap.agents.builtins.orchestrator_agent.OrchestratorAgent",
    }

    # Agent to storage type mapping for storage agent organization
    _AGENT_TO_STORAGE_TYPE = {
        "csv_reader": "csv",
        "csv_writer": "csv",
        "json_reader": "json",
        "json_writer": "json",
        "file_reader": "file",
        "file_writer": "file",
        "vector_reader": "vector",
        "vector_writer": "vector",
        "blob_reader": "blob",
        "blob_writer": "blob",
    }

    # LLM agent to provider mapping for conditional registration
    _LLM_AGENT_TO_PROVIDER = {
        "llm": None,  # Base LLM agent works with any provider
        "openai": "openai",
        "gpt": "openai",
        "chatgpt": "openai",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "google": "google",
        "gemini": "google",
    }

    @staticmethod
    def get_core_agents() -> Dict[str, str]:
        """
        Get core agent mappings that are always available.
        
        Returns:
            Dictionary mapping agent types to class paths
        """
        return AgentConfigService._CORE_AGENTS.copy()

    @staticmethod
    def get_llm_agents() -> Dict[str, str]:
        """
        Get LLM agent mappings that require LLM provider dependencies.
        
        Returns:
            Dictionary mapping agent types to class paths
        """
        return AgentConfigService._LLM_AGENTS.copy()

    @staticmethod
    def get_storage_agents() -> Dict[str, str]:
        """
        Get storage agent mappings that require storage provider dependencies.
        
        Returns:
            Dictionary mapping agent types to class paths
        """
        return AgentConfigService._STORAGE_AGENTS.copy()

    @staticmethod
    def get_mixed_dependency_agents() -> Dict[str, str]:
        """
        Get agent mappings for agents with mixed or optional dependencies.
        
        Returns:
            Dictionary mapping agent types to class paths
        """
        return AgentConfigService._MIXED_DEPENDENCY_AGENTS.copy()

    @staticmethod
    def get_agent_to_storage_type() -> Dict[str, str]:
        """
        Get mapping from agent types to their required storage types.
        
        Returns:
            Dictionary mapping agent types to storage type names
        """
        return AgentConfigService._AGENT_TO_STORAGE_TYPE.copy()

    @staticmethod
    def get_llm_agent_to_provider() -> Dict[str, str]:
        """
        Get mapping from LLM agent types to their required providers.
        
        Returns:
            Dictionary mapping LLM agent types to provider names (None = any provider)
        """
        return AgentConfigService._LLM_AGENT_TO_PROVIDER.copy()

    @staticmethod
    def get_all_agents() -> Dict[str, str]:
        """
        Get all agent mappings across all categories.
        
        Returns:
            Dictionary with all agent type to class path mappings
        """
        all_agents = {}
        all_agents.update(AgentConfigService._CORE_AGENTS)
        all_agents.update(AgentConfigService._LLM_AGENTS)
        all_agents.update(AgentConfigService._STORAGE_AGENTS)
        all_agents.update(AgentConfigService._MIXED_DEPENDENCY_AGENTS)
        return all_agents

    @staticmethod
    def get_core_agent_types() -> set:
        """
        Get set of core agent type names for categorization.
        
        Returns:
            Set of core agent type names
        """
        return set(AgentConfigService._CORE_AGENTS.keys())

    @staticmethod
    def get_llm_agent_types() -> set:
        """
        Get set of LLM agent type names for categorization.
        
        Returns:
            Set of LLM agent type names
        """
        return set(AgentConfigService._LLM_AGENTS.keys())

    @staticmethod
    def get_storage_agent_types() -> set:
        """
        Get set of storage agent type names for categorization.
        
        Returns:
            Set of storage agent type names
        """
        return set(AgentConfigService._STORAGE_AGENTS.keys())

    @staticmethod
    def get_mixed_dependency_agent_types() -> set:
        """
        Get set of mixed dependency agent type names for categorization.
        
        Returns:
            Set of mixed dependency agent type names
        """
        return set(AgentConfigService._MIXED_DEPENDENCY_AGENTS.keys())

    @staticmethod
    def get_provider_agents(provider: str) -> Dict[str, str]:
        """
        Get LLM agents for a specific provider.
        
        Args:
            provider: Provider name (openai, anthropic, google)
            
        Returns:
            Dictionary mapping agent types to class paths for the provider
        """
        provider_mapping = {
            "openai": ["openai", "gpt", "chatgpt"],
            "anthropic": ["anthropic", "claude"],
            "google": ["google", "gemini"],
        }
        
        if provider not in provider_mapping:
            return {}
            
        agent_types = provider_mapping[provider]
        return {
            agent_type: AgentConfigService._LLM_AGENTS[agent_type]
            for agent_type in agent_types
            if agent_type in AgentConfigService._LLM_AGENTS
        }

    @staticmethod
    def get_storage_type_agents(storage_type: str) -> Dict[str, str]:
        """
        Get storage agents for a specific storage type.
        
        Args:
            storage_type: Storage type name (csv, json, file, vector, blob)
            
        Returns:
            Dictionary mapping agent types to class paths for the storage type
        """
        type_mapping = {
            "csv": ["csv_reader", "csv_writer"],
            "json": ["json_reader", "json_writer"],
            "file": ["file_reader", "file_writer"],
            "vector": ["vector_reader", "vector_writer"],
            "blob": ["blob_reader", "blob_writer"],
        }
        
        if storage_type not in type_mapping:
            return {}
            
        agent_types = type_mapping[storage_type]
        return {
            agent_type: AgentConfigService._STORAGE_AGENTS[agent_type]
            for agent_type in agent_types
            if agent_type in AgentConfigService._STORAGE_AGENTS
        }

    @staticmethod
    def is_core_agent(agent_type: str) -> bool:
        """
        Check if an agent type is a core agent.
        
        Args:
            agent_type: Agent type to check
            
        Returns:
            True if the agent type is a core agent
        """
        return agent_type in AgentConfigService._CORE_AGENTS

    @staticmethod
    def is_llm_agent(agent_type: str) -> bool:
        """
        Check if an agent type is an LLM agent.
        
        Args:
            agent_type: Agent type to check
            
        Returns:
            True if the agent type is an LLM agent
        """
        return agent_type in AgentConfigService._LLM_AGENTS

    @staticmethod
    def is_storage_agent(agent_type: str) -> bool:
        """
        Check if an agent type is a storage agent.
        
        Args:
            agent_type: Agent type to check
            
        Returns:
            True if the agent type is a storage agent
        """
        return agent_type in AgentConfigService._STORAGE_AGENTS

    @staticmethod
    def get_required_provider(agent_type: str) -> str:
        """
        Get the required provider for an LLM agent type.
        
        Args:
            agent_type: LLM agent type
            
        Returns:
            Required provider name, or None if any provider works
        """
        return AgentConfigService._LLM_AGENT_TO_PROVIDER.get(agent_type)

    @staticmethod
    def get_required_storage_type(agent_type: str) -> str:
        """
        Get the required storage type for a storage agent type.
        
        Args:
            agent_type: Storage agent type
            
        Returns:
            Required storage type name, or None if not a storage agent
        """
        return AgentConfigService._AGENT_TO_STORAGE_TYPE.get(agent_type)
