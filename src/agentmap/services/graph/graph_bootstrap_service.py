"""
GraphBootstrapService for AgentMap.

Lightweight bootstrap service that orchestrates agent registration and service initialization
for a specific graph bundle. Unlike ApplicationBootstrapService which loads everything,
this service only loads what's required by the graph.

Follows the same patterns as ApplicationBootstrapService but with filtered, minimal loading.
"""

from typing import Any, Dict, List, Optional, Set

from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.agent.agent_registry_service import AgentRegistryService
from agentmap.services.config.agent_config_service import AgentConfigService
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.dependency_checker_service import DependencyCheckerService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.logging_service import LoggingService


class GraphBootstrapService:
    """
    Service for orchestrating graph-specific bootstrap including selective agent
    registration and minimal service initialization.

    This provides a lightweight alternative to ApplicationBootstrapService that only
    loads what's needed for a specific graph, improving startup performance.
    """

    def __init__(
        self,
        agent_registry_service: AgentRegistryService,
        features_registry_service: FeaturesRegistryService,
        # dependency_checker_service: DependencyCheckerService,
        app_config_service: AppConfigService,
        logging_service: LoggingService,
    ):
        """Initialize with same dependencies as ApplicationBootstrapService."""
        self.agent_registry = agent_registry_service
        self.features_registry = features_registry_service
        # self.dependency_checker = dependency_checker_service
        self.app_config = app_config_service
        self.logger = logging_service.get_class_logger(self)

        # Track what we've loaded for this graph
        self._loaded_agents = set()

        self.logger.info(
            "[GraphBootstrapService] Initialized for minimal graph-specific bootstrap"
        )

    def bootstrap_from_bundle(self, bundle: GraphBundle) -> Dict[str, Any]:
        """
        Main orchestration method that coordinates graph-specific bootstrap.

        Process (following ApplicationBootstrapService pattern):
        1. Register core agents if needed
        2. Register required LLM agents if needed
        3. Register required storage agents if needed
        4. Register custom agents from mappings
        5. Log bootstrap summary

        Args:
            bundle: GraphBundle containing requirements (pre-filtered by GraphBundleService)

        Returns:
            Dictionary with bootstrap status and loaded components

        Raises:
            RuntimeError: If required agents cannot be registered
        """
        self.logger.info(
            f"🚀 [GraphBootstrapService] Starting bootstrap for graph: {bundle.graph_name}"
        )

        # Reset tracking for this bootstrap
        self._loaded_agents.clear()

        # The bundle's required_services are already filtered by GraphBundleService
        # We trust the bundle and don't need additional filtering
        self.logger.debug(
            f"[GraphBootstrapService] Loading {len(bundle.required_agents)} agents, "
            f"{len(bundle.required_services)} services for graph"
        )

        # Step 1: Register required core agents
        self._register_required_core_agents(bundle.required_agents)

        # Step 2: Register required LLM agents if needed
        self._register_required_llm_agents(
            bundle.required_agents, bundle.agent_mappings
        )

        # Step 3: Register required storage agents if needed
        self._register_required_storage_agents(
            bundle.required_agents, bundle.agent_mappings
        )

        # Step 4: Register any custom agents from mappings
        self._register_custom_agents_from_mappings(
            bundle.required_agents, bundle.agent_mappings
        )

        # Step 5: Verify all required agents were loaded
        missing_agents = bundle.required_agents - self._loaded_agents
        if missing_agents:
            error_msg = (
                f"Failed to register required agents: {sorted(missing_agents)}. "
                f"Graph '{bundle.graph_name}' cannot be executed."
            )
            self.logger.error(f"❌ [GraphBootstrapService] {error_msg}")
            raise RuntimeError(error_msg)

        # Step 6: Log bootstrap summary
        summary = self._log_bootstrap_summary(bundle)

        self.logger.info(
            f"✅ [GraphBootstrapService] Bootstrap completed for graph: {bundle.graph_name}"
        )

        return summary

    def _register_required_core_agents(self, required_agents: Set[str]) -> None:
        """
        Register only the core agents required by the bundle.

        Following ApplicationBootstrapService.register_core_agents() pattern
        but filtered to only what's needed.

        Args:
            required_agents: Set of required agent types from bundle
        """
        self.logger.debug("[GraphBootstrapService] Registering required core agents")

        # Core agents mapping (from ApplicationBootstrapService)
        core_agents = AgentConfigService.get_core_agents()

        registered_count = 0

        # Iterate through required agents and look up in dictionary (O(1) lookup)
        for agent_type in required_agents:
            class_path = core_agents.get(agent_type)
            if class_path and self._register_agent(agent_type, class_path):
                registered_count += 1
                self._loaded_agents.add(agent_type)

        if registered_count > 0:
            self.logger.debug(
                f"[GraphBootstrapService] Registered {registered_count} core agents"
            )

    def _register_required_llm_agents(
        self, required_agents: Set[str], agent_mappings: Optional[Dict[str, str]]
    ) -> None:
        """
        Register only the LLM agents required by the bundle.

        Following ApplicationBootstrapService.discover_and_register_llm_agents() pattern
        but filtered to only what's needed.

        Args:
            required_agents: Set of required agent types from bundle
            agent_mappings: Optional mappings from bundle for agent class paths
        """
        # Standard LLM agent class paths
        llm_agent_class_paths = AgentConfigService.get_llm_agents()

        # Check if any LLM agents are needed
        needed_llm_agents = required_agents.intersection(llm_agent_class_paths.keys())

        if not needed_llm_agents:
            self.logger.debug("[GraphBootstrapService] No LLM agents required")
            return

        self.logger.debug(
            f"[GraphBootstrapService] Registering required LLM agents: {needed_llm_agents}"
        )

        # Enable LLM feature if needed (following ApplicationBootstrapService)
        self.features_registry.enable_feature("llm")

        # Discover available providers TODO: Should this be FeatureRegistryService?
        available_providers = self.dependency_checker.discover_and_validate_providers(
            "llm"
        )

        # Map agent types to providers for availability checking
        agent_to_provider = AgentConfigService.get_llm_agent_to_provider()
        registered_count = 0

        for agent_type in needed_llm_agents:
            # Try bundle mappings first if available
            class_path = None
            if agent_mappings:
                class_path = agent_mappings.get(agent_type)

            # Fall back to standard mappings if provider is available
            if not class_path:
                provider = agent_to_provider.get(agent_type)
                # Base LLM agent needs any provider, specific agents need their provider
                if provider is None and available_providers:  # Base LLM agent
                    class_path = llm_agent_class_paths[agent_type]
                elif provider and available_providers.get(provider):
                    class_path = llm_agent_class_paths[agent_type]

            if class_path and self._register_agent(agent_type, class_path):
                registered_count += 1
                self._loaded_agents.add(agent_type)

        if registered_count > 0:
            self.logger.debug(
                f"[GraphBootstrapService] Registered {registered_count} LLM agents"
            )

    def _register_required_storage_agents(
        self, required_agents: Set[str], agent_mappings: Optional[Dict[str, str]]
    ) -> None:
        """
        Register only the storage agents required by the bundle.

        Following ApplicationBootstrapService.discover_and_register_storage_agents() pattern
        but filtered to only what's needed.

        Args:
            required_agents: Set of required agent types from bundle
            agent_mappings: Optional mappings from bundle for agent class paths
        """
        # Standard storage agent class paths
        storage_class_paths = AgentConfigService.get_storage_agents()

        # Map agent types to storage types for availability checking
        agent_to_storage_type = AgentConfigService.get_agent_to_storage_type()

        # Find needed storage agents - check both standard and potential custom names
        storage_prefixes = ["csv_", "json_", "file_", "vector_", "blob_"]
        needed_storage_agents = {
            agent
            for agent in required_agents
            if any(agent.startswith(prefix) for prefix in storage_prefixes)
        }

        if not needed_storage_agents:
            self.logger.debug("[GraphBootstrapService] No storage agents required")
            return

        self.logger.debug(
            f"[GraphBootstrapService] Registering required storage agents: {needed_storage_agents}"
        )

        # Enable storage feature if needed
        self.features_registry.enable_feature("storage")

        # Discover available storage types
        available_storage_types = (
            self.dependency_checker.discover_and_validate_providers("storage")
        )

        registered_count = 0

        for agent_type in needed_storage_agents:
            # Try bundle mappings first if available
            class_path = None
            if agent_mappings:
                class_path = agent_mappings.get(agent_type)

            # Fall back to standard mappings if storage type is available
            if not class_path and agent_type in storage_class_paths:
                storage_type = agent_to_storage_type.get(agent_type)
                if storage_type and available_storage_types.get(storage_type):
                    class_path = storage_class_paths[agent_type]

            if class_path and self._register_agent(agent_type, class_path):
                registered_count += 1
                self._loaded_agents.add(agent_type)

        if registered_count > 0:
            self.logger.debug(
                f"[GraphBootstrapService] Registered {registered_count} storage agents"
            )

    def _register_custom_agents_from_mappings(
        self, required_agents: Set[str], agent_mappings: Optional[Dict[str, str]]
    ) -> None:
        """
        Register any custom agents that have explicit mappings in the bundle.

        Args:
            required_agents: Set of required agent types from bundle
            agent_mappings: Optional mappings from bundle for agent class paths
        """
        if not agent_mappings:
            return

        # Find agents not yet registered
        unregistered = required_agents - self._loaded_agents

        if not unregistered:
            return

        self.logger.debug(
            f"[GraphBootstrapService] Registering custom agents: {unregistered}"
        )

        registered_count = 0
        for agent_type in unregistered:
            if agent_type in agent_mappings:
                class_path = agent_mappings[agent_type]
                if self._register_agent(agent_type, class_path):
                    registered_count += 1
                    self._loaded_agents.add(agent_type)

        if registered_count > 0:
            self.logger.debug(
                f"[GraphBootstrapService] Registered {registered_count} custom agents from mappings"
            )

    def _register_agent(self, agent_type: str, class_path: str) -> bool:
        """
        Register an agent with the registry.

        Simplified version that trusts bundle requirements and doesn't check
        for duplicates (AgentRegistry just overwrites on duplicates anyway).

        Args:
            agent_type: Type identifier for the agent
            class_path: Full import path to the agent class

        Returns:
            True if agent was registered, False on import error
        """
        try:
            # Import and register directly - no duplicate checking needed
            agent_class = self._import_agent_class(class_path)
            self.agent_registry.register_agent(agent_type, agent_class)
            self.logger.debug(
                f"[GraphBootstrapService] ✅ Registered agent: {agent_type}"
            )
            return True

        except ImportError as e:
            self.logger.debug(
                f"[GraphBootstrapService] ⚠️ Agent {agent_type} not available: {e}"
            )
            return False
        except Exception as e:
            self.logger.error(
                f"[GraphBootstrapService] ❌ Failed to register agent {agent_type}: {e}"
            )
            return False

    def _import_agent_class(self, class_path: str):
        """
        Import an agent class from its full path.

        Exact copy from ApplicationBootstrapService for consistency.

        Args:
            class_path: Full import path

        Returns:
            The imported agent class

        Raises:
            ImportError: If the class cannot be imported
        """
        module_path, class_name = class_path.rsplit(".", 1)

        try:
            module = __import__(module_path, fromlist=[class_name])
            agent_class = getattr(module, class_name)
            return agent_class
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Cannot import {class_path}: {e}")

    def _log_bootstrap_summary(self, bundle: GraphBundle) -> Dict[str, Any]:
        """
        Log a summary of the bootstrap process.

        Following ApplicationBootstrapService._log_startup_summary() pattern.

        Args:
            bundle: The bundle that was bootstrapped

        Returns:
            Summary dictionary
        """
        summary = self._get_bootstrap_summary(bundle)

        self.logger.info(
            f"📊 [GraphBootstrapService] Bootstrap Summary for '{bundle.graph_name}':"
        )
        self.logger.info(f"   Required agents: {len(bundle.required_agents)}")
        self.logger.info(f"   Loaded agents: {len(self._loaded_agents)}")
        self.logger.info(f"   Required services: {len(bundle.required_services)}")

        if self._loaded_agents:
            self.logger.debug(f"   Loaded agent types: {sorted(self._loaded_agents)}")

        return summary

    def _get_bootstrap_summary(self, bundle: GraphBundle) -> Dict[str, Any]:
        """
        Get comprehensive summary of the bootstrap process.

        Following ApplicationBootstrapService.get_bootstrap_summary() pattern.

        Args:
            bundle: The bundle that was bootstrapped

        Returns:
            Dictionary with bootstrap status
        """
        return {
            "service": "GraphBootstrapService",
            "graph_name": bundle.graph_name,
            "bootstrap_completed": True,
            "required_agents": len(bundle.required_agents),
            "loaded_agents": len(self._loaded_agents),
            "loaded_agent_types": sorted(list(self._loaded_agents)),
            "required_services": len(bundle.required_services),
            "agent_breakdown": {
                "core": len(
                    [
                        a
                        for a in self._loaded_agents
                        if a
                        in {
                            "default",
                            "echo",
                            "branching",
                            "failure",
                            "success",
                            "input",
                            "graph",
                            "human",
                        }
                    ]
                ),
                "llm": len(
                    [
                        a
                        for a in self._loaded_agents
                        if a
                        in {
                            "llm",
                            "openai",
                            "anthropic",
                            "google",
                            "claude",
                            "gpt",
                            "gemini",
                            "chatgpt",
                        }
                    ]
                ),
                "storage": len(
                    [
                        a
                        for a in self._loaded_agents
                        if any(
                            a.startswith(p)
                            for p in ["csv_", "json_", "file_", "vector_", "blob_"]
                        )
                    ]
                ),
                "custom": len(
                    [
                        a
                        for a in self._loaded_agents
                        if a
                        not in {
                            "default",
                            "echo",
                            "branching",
                            "failure",
                            "success",
                            "input",
                            "graph",
                            "human",
                            "llm",
                            "openai",
                            "anthropic",
                            "google",
                            "claude",
                            "gpt",
                            "gemini",
                            "chatgpt",
                        }
                        and not any(
                            a.startswith(p)
                            for p in ["csv_", "json_", "file_", "vector_", "blob_"]
                        )
                    ]
                ),
            },
        }
