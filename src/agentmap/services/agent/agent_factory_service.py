"""
AgentFactoryService for AgentMap.

Service containing business logic for agent creation and instantiation.
Refactored to use composition with extracted modules for better maintainability.
"""

from typing import Any, Dict, Optional, Set, Type
from typing import Any, Dict, Optional, Set, Type

from agentmap.services.agent.agent_class_resolver import AgentClassResolver
from agentmap.services.agent.agent_constructor_builder import AgentConstructorBuilder
from agentmap.services.agent.agent_validator import AgentValidator
from agentmap.services.agent.agent_class_resolver import AgentClassResolver
from agentmap.services.agent.agent_constructor_builder import AgentConstructorBuilder
from agentmap.services.agent.agent_validator import AgentValidator
from agentmap.services.custom_agent_loader import CustomAgentLoader
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.logging_service import LoggingService


class AgentFactoryService:
    """Factory service for creating and managing agent instances."""

    def __init__(
        self,
        features_registry_service: FeaturesRegistryService,
        logging_service: LoggingService,
        custom_agent_loader: CustomAgentLoader,
    ):
        """Initialize service with dependency injection."""
        self.features = features_registry_service
        self.logger = logging_service.get_class_logger(self)
        self._custom_agent_loader = (
            custom_agent_loader  # Keep for backward compatibility with tests
        )
        self._resolver = AgentClassResolver(logging_service, custom_agent_loader)
        self._builder = AgentConstructorBuilder(logging_service)
        self._validator = AgentValidator(logging_service)

    @property
    def _class_cache(self) -> Dict[str, Type]:
        """Property that exposes the resolver's class cache for testing."""
        return self._resolver.get_class_cache()

    def get_class_cache(self) -> Dict[str, Type]:
        """
        Get the class cache for testing purposes.

        Returns:
            Dictionary mapping class paths to cached classes
        """
        return self._resolver.get_class_cache()

    def resolve_agent_class(
        self,
        agent_type: str,
        agent_mappings: Dict[str, str],
        custom_agents: Optional[Set[str]] = None,
    ) -> Type:
        """
        Resolve an agent class using provided mappings.

        Args:
            agent_type: The type identifier for the agent
            agent_mappings: Dictionary mapping agent_type to class_path
            custom_agents: Optional set of custom agent types for better error messages

        Returns:
            Agent class ready for instantiation

        Raises:
            ValueError: If agent type is not found in mappings
            ImportError: If class cannot be imported
        """
        return self._resolver.resolve_agent_class(
            agent_type, agent_mappings, custom_agents
        )

    def get_agent_resolution_context(
        self,
        agent_type: str,
        agent_mappings: Dict[str, str],
        custom_agents: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Get comprehensive context for agent class resolution."""
        return self._resolver.get_agent_resolution_context(
            agent_type, agent_mappings, custom_agents
        )

    def create_agent_instance(
        self,
        node: Any,
        graph_name: str,
        agent_mappings: Dict[str, str],
        custom_agents: Optional[Set[str]] = None,
        execution_tracking_service: Optional[Any] = None,
        state_adapter_service: Optional[Any] = None,
        prompt_manager_service: Optional[Any] = None,
        node_registry: Optional[Dict[str, Any]] = None,
        bundle_tools: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Create agent instance with full instantiation and context."""
        from agentmap.exceptions import AgentInitializationError

        if not hasattr(node, "agent_type") or not node.agent_type:
            raise ValueError(
                f"Node '{node.name}' is missing required 'agent_type' attribute"
            )

        agent_type = node.agent_type
        self.logger.debug(
            f"[AgentFactoryService] Creating agent instance for node: {node.name} (type: {agent_type})"
        )

        agent_class = self.resolve_agent_class(
            agent_type, agent_mappings, custom_agents
        )

        context = {
            "input_fields": getattr(node, "inputs", []),
            "output_field": getattr(node, "output", None),
            "description": getattr(node, "description", ""),
            "is_custom": custom_agents and agent_type in custom_agents,
        }

        if hasattr(node, "context") and node.context:
            context.update(node.context)

        self.logger.debug(
            f"[AgentFactoryService] Instantiating {agent_class.__name__} as node '{node.name}'"
        )

        node_tools = None
        if bundle_tools and node.name in bundle_tools:
            node_tools = bundle_tools[node.name]
            self.logger.debug(
                f"[AgentFactoryService] Found {len(node_tools)} tools for node: {node.name}"
            )
        elif agent_type == "tool_agent":
            self.logger.warning(
                f"[AgentFactoryService] ToolAgent node '{node.name}' has no tools in bundle"
            )

        constructor_args = self._builder.build_constructor_args(
            agent_class,
            node,
            context,
            execution_tracking_service,
            state_adapter_service,
            prompt_manager_service,
            tools=node_tools,
            logger=self.logger,
        )

        try:
            agent_instance = agent_class(**constructor_args)
        except Exception as e:
            raise AgentInitializationError(
                f"Failed to create agent instance for node '{node.name}': {str(e)}"
            )

        if agent_class.__name__ == "OrchestratorAgent" and node_registry:
            self.logger.debug(
                f"[AgentFactoryService] Injecting node registry for OrchestratorAgent: {node.name}"
            )
            agent_instance.node_registry = node_registry
            self.logger.debug(
                f"[AgentFactoryService] Node registry injected with {len(node_registry)} nodes"
            )

        self.logger.debug(
            f"[AgentFactoryService] Successfully created agent instance: {node.name}"
        )
        return agent_instance

    def validate_agent_instance(self, agent_instance: Any, node: Any) -> None:
        """
        Validate that an agent instance is properly configured.

        Args:
            agent_instance: Agent instance to validate
            node: Node definition for validation context

        Raises:
            ValueError: If agent configuration is invalid
        """
        self._validator.validate_agent_instance(agent_instance, node)

    def _build_constructor_args(
        self,
        agent_class: Type,
        node: Any,
        context: Dict[str, Any],
        execution_tracking_service: Optional[Any],
        state_adapter_service: Optional[Any],
        prompt_manager_service: Optional[Any],
        tools: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Build constructor arguments based on agent signature inspection.

        Args:
            agent_class: Agent class to inspect
            node: Node definition
            context: Context dictionary
            execution_tracking_service: Optional execution tracking service
            state_adapter_service: Optional state adapter service
            prompt_manager_service: Optional prompt manager service
            tools: Optional list of LangChain tools for ToolAgent

        Returns:
            Dictionary of constructor arguments
        """
        return self._builder.build_constructor_args(
            agent_class,
            node,
            context,
            execution_tracking_service,
            state_adapter_service,
            prompt_manager_service,
            tools,
            logger=self.logger,
        )

    def _import_class_from_path(self, class_path: str) -> Type:
        """
        Import a class from its fully qualified path.

        Delegates to AgentClassResolver for implementation.

        Args:
            class_path: Fully qualified class path

        Returns:
            The imported class
        """
        return self._resolver._import_class_from_path(class_path)

    def _try_load_custom_agent(self, agent_type: str) -> Optional[Type]:
        """
        Try to load a custom agent as fallback.

        Delegates to AgentClassResolver for implementation.

        Args:
            agent_type: Type of agent to load

        Returns:
            Agent class or None if not found
        """
        return self._resolver._try_load_custom_agent(agent_type)

    def _get_default_agent_class(self) -> Type:
        """
        Get default agent class as fallback.

        Delegates to AgentClassResolver for implementation.

        Returns:
            Default agent class
        """
        return self._resolver._get_default_agent_class()

    def _resolve_agent_class_with_fallback(self, agent_type: str) -> Type:
        """
        Resolve agent class with comprehensive fallback logic.

        Delegates to AgentClassResolver for implementation.

        Args:
            agent_type: Type of agent to resolve

        Returns:
            Agent class ready for instantiation
        """
        return self._resolver.resolve_agent_class_with_fallback(agent_type)
