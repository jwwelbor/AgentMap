"""
AgentConfigService for AgentMap.

Provides backward compatibility layer for agent configuration access.
Delegates to BuiltinDefinitionConstants for actual definitions.
"""

from typing import Dict, Optional

from agentmap.builtin_definition_constants import BuiltinDefinitionConstants


class AgentConfigService:
    """
    Configuration service providing backward compatibility layer for agent mappings.

    Delegates to BuiltinDefinitionConstants for actual definitions while maintaining
    the existing API for backward compatibility.
    """

    # Legacy attributes now delegate to BuiltinDefinitionConstants
    @classmethod
    def _get_core_agents_dict(cls) -> Dict[str, str]:
        """Get core agents dictionary from centralized constants."""
        agents = BuiltinDefinitionConstants.get_agents_by_category("core")
        return {k: v["class_path"] for k, v in agents.items()}

    @classmethod
    def _get_llm_agents_dict(cls) -> Dict[str, str]:
        """Get LLM agents dictionary from centralized constants."""
        agents = BuiltinDefinitionConstants.get_agents_by_category("llm")
        return {k: v["class_path"] for k, v in agents.items()}

    @classmethod
    def _get_storage_agents_dict(cls) -> Dict[str, str]:
        """Get storage agents dictionary from centralized constants."""
        agents = BuiltinDefinitionConstants.get_agents_by_category("storage")
        return {k: v["class_path"] for k, v in agents.items()}

    @classmethod
    def _get_mixed_agents_dict(cls) -> Dict[str, str]:
        """Get mixed dependency agents dictionary from centralized constants."""
        agents = BuiltinDefinitionConstants.get_agents_by_category("mixed")
        return {k: v["class_path"] for k, v in agents.items()}

    # Backward compatibility properties
    _CORE_AGENTS = property(lambda self: self._get_core_agents_dict())
    _LLM_AGENTS = property(lambda self: self._get_llm_agents_dict())
    _STORAGE_AGENTS = property(lambda self: self._get_storage_agents_dict())
    _MIXED_DEPENDENCY_AGENTS = property(lambda self: self._get_mixed_agents_dict())
    _AGENT_TO_STORAGE_TYPE = property(
        lambda self: BuiltinDefinitionConstants.get_agent_to_storage_type()
    )
    _LLM_AGENT_TO_PROVIDER = property(
        lambda self: BuiltinDefinitionConstants.get_llm_agent_to_provider()
    )

    @staticmethod
    def get_core_agents() -> Dict[str, str]:
        """
        Get core agent mappings that are always available.

        Returns:
            Dictionary mapping agent types to class paths
        """
        return AgentConfigService._get_core_agents_dict()

    @staticmethod
    def get_llm_agents() -> Dict[str, str]:
        """
        Get LLM agent mappings that require LLM provider dependencies.

        Returns:
            Dictionary mapping agent types to class paths
        """
        return AgentConfigService._get_llm_agents_dict()

    @staticmethod
    def get_storage_agents() -> Dict[str, str]:
        """
        Get storage agent mappings that require storage provider dependencies.

        Returns:
            Dictionary mapping agent types to class paths
        """
        return AgentConfigService._get_storage_agents_dict()

    @staticmethod
    def get_mixed_dependency_agents() -> Dict[str, str]:
        """
        Get agent mappings for agents with mixed or optional dependencies.

        Returns:
            Dictionary mapping agent types to class paths
        """
        return AgentConfigService._get_mixed_agents_dict()

    @staticmethod
    def get_agent_to_storage_type() -> Dict[str, str]:
        """
        Get mapping from agent types to their required storage types.

        Returns:
            Dictionary mapping agent types to storage type names
        """
        return BuiltinDefinitionConstants.get_agent_to_storage_type()

    @staticmethod
    def get_llm_agent_to_provider() -> Dict[str, Optional[str]]:
        """
        Get mapping from LLM agent types to their required providers.

        Returns:
            Dictionary mapping LLM agent types to provider names (None = any provider)
        """
        return BuiltinDefinitionConstants.get_llm_agent_to_provider()

    @staticmethod
    def get_all_agents() -> Dict[str, str]:
        """
        Get all agent mappings across all categories.

        Returns:
            Dictionary with all agent type to class path mappings
        """
        return BuiltinDefinitionConstants.get_agent_class_paths()

    @staticmethod
    def get_core_agent_types() -> set:
        """
        Get set of core agent type names for categorization.

        Returns:
            Set of core agent type names
        """
        return set(AgentConfigService._get_core_agents_dict().keys())

    @staticmethod
    def get_llm_agent_types() -> set:
        """
        Get set of LLM agent type names for categorization.

        Returns:
            Set of LLM agent type names
        """
        return set(AgentConfigService._get_llm_agents_dict().keys())

    @staticmethod
    def get_storage_agent_types() -> set:
        """
        Get set of storage agent type names for categorization.

        Returns:
            Set of storage agent type names
        """
        return set(AgentConfigService._get_storage_agents_dict().keys())

    @staticmethod
    def get_mixed_dependency_agent_types() -> set:
        """
        Get set of mixed dependency agent type names for categorization.

        Returns:
            Set of mixed dependency agent type names
        """
        return set(AgentConfigService._get_mixed_agents_dict().keys())

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
        llm_agents = AgentConfigService._get_llm_agents_dict()
        return {
            agent_type: llm_agents[agent_type]
            for agent_type in agent_types
            if agent_type in llm_agents
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
        storage_agents = AgentConfigService._get_storage_agents_dict()
        return {
            agent_type: storage_agents[agent_type]
            for agent_type in agent_types
            if agent_type in storage_agents
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
        return agent_type in AgentConfigService._get_core_agents_dict()

    @staticmethod
    def is_llm_agent(agent_type: str) -> bool:
        """
        Check if an agent type is an LLM agent.

        Args:
            agent_type: Agent type to check

        Returns:
            True if the agent type is an LLM agent
        """
        return agent_type in AgentConfigService._get_llm_agents_dict()

    @staticmethod
    def is_storage_agent(agent_type: str) -> bool:
        """
        Check if an agent type is a storage agent.

        Args:
            agent_type: Agent type to check

        Returns:
            True if the agent type is a storage agent
        """
        return agent_type in AgentConfigService._get_storage_agents_dict()

    @staticmethod
    def get_required_provider(agent_type: str) -> str:
        """
        Get the required provider for an LLM agent type.

        Args:
            agent_type: LLM agent type

        Returns:
            Required provider name, or None if any provider works
        """
        return BuiltinDefinitionConstants.get_llm_agent_to_provider().get(agent_type)

    @staticmethod
    def get_required_storage_type(agent_type: str) -> str:
        """
        Get the required storage type for a storage agent type.

        Args:
            agent_type: Storage agent type

        Returns:
            Required storage type name, or None if not a storage agent
        """
        return BuiltinDefinitionConstants.get_agent_to_storage_type().get(agent_type)
