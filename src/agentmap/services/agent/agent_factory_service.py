"""
AgentFactoryService for AgentMap.

Service containing business logic for agent creation and instantiation.
This extracts and wraps the core functionality from the original AgentLoader class.
"""

from typing import Any, Dict, Optional, Set, Type

from agentmap.services.agent.agent_class_resolver import AgentClassResolver
from agentmap.services.agent.agent_constructor_builder import AgentConstructorBuilder
from agentmap.services.agent.agent_validator import AgentValidator
from agentmap.services.custom_agent_loader import CustomAgentLoader
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.logging_service import LoggingService


class AgentFactoryService:
    """
    Factory service for creating and managing agent instances.

    Contains all agent creation business logic extracted from the original AgentLoader class.
    Uses dependency injection and coordinates between registry and features services.
    Follows Factory pattern naming to match existing test fixtures.
    """

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
        """
        Get comprehensive context for agent class resolution.

        Args:
            agent_type: Agent type to get context for
            agent_mappings: Dictionary mapping agent_type to class_path
            custom_agents: Optional set of custom agent types

        Returns:
            Dictionary with resolution context and metadata
        """
        try:
            agent_class = self.resolve_agent_class(
                agent_type, agent_mappings, custom_agents
            )

            return {
                "agent_type": agent_type,
                "agent_class": agent_class,
                "class_name": agent_class.__name__,
                "resolvable": True,
                "dependencies_valid": True,  # Simplified - dependencies are handled by resolve_agent_class
                "missing_dependencies": [],
                "_factory_version": "2.0",
                "_resolution_method": "AgentFactoryService.resolve_agent_class",
            }
        except (ValueError, ImportError) as e:
            return {
                "agent_type": agent_type,
                "agent_class": None,
                "class_name": None,
                "resolvable": False,
                "dependencies_valid": False,
                "missing_dependencies": ["resolution_failed"],
                "resolution_error": str(e),
                "_factory_version": "2.0",
                "_resolution_method": "AgentFactoryService.resolve_agent_class",
            }

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
        """
        Create agent instance with full instantiation and context.

        Extracted from GraphRunnerService to follow factory pattern completely.

        Args:
            node: Node definition containing agent information
            graph_name: Name of the graph for context
            agent_mappings: Dictionary mapping agent_type to class_path
            custom_agents: Optional set of custom agent types
            execution_tracking_service: Service for execution tracking
            state_adapter_service: Service for state management
            prompt_manager_service: Service for prompt management (optional)
            node_registry: Node registry for OrchestratorAgent (optional)
            bundle_tools: Optional dictionary of tools from bundle, keyed by node name (AGM-TOOLS-001)

        Returns:
            Configured agent instance

        Raises:
            ValueError: If agent creation fails or node.agent_type is missing
        """
        from agentmap.exceptions import AgentInitializationError

        # Validate that node has agent_type
        if not hasattr(node, "agent_type") or not node.agent_type:
            raise ValueError(
                f"Node '{node.name}' is missing required 'agent_type' attribute"
            )

        agent_type = node.agent_type
        self.logger.debug(
            f"[AgentFactoryService] Creating agent instance for node: {node.name} (type: {agent_type})"
        )

        # Step 1: Resolve agent class using provided mappings
        agent_class = self.resolve_agent_class(
            agent_type, agent_mappings, custom_agents
        )

        # Step 2: Create comprehensive context with input/output field information
        context = {
            "input_fields": getattr(node, "inputs", []),
            "output_field": getattr(node, "output", None),
            "description": getattr(node, "description", ""),
            "is_custom": custom_agents and agent_type in custom_agents,
        }

        # Add CSV context data if available (extracted from GraphRunnerService logic)
        if hasattr(node, "context") and node.context:
            context.update(node.context)

        self.logger.debug(
            f"[AgentFactoryService] Instantiating {agent_class.__name__} as node '{node.name}'"
        )

        # AGM-TOOLS-001: Retrieve tools for this node if bundle_tools provided
        node_tools = None
        if bundle_tools and node.name in bundle_tools:
            node_tools = bundle_tools[node.name]
            self.logger.debug(
                f"[AgentFactoryService] Found {len(node_tools)} tools for node: {node.name}"
            )
        elif agent_type == "tool_agent":
            # tool_agent expects tools but none found - log warning
            self.logger.warning(
                f"[AgentFactoryService] ToolAgent node '{node.name}' has no tools in bundle"
            )

        # Step 3: Build constructor arguments based on agent signature inspection
        constructor_args = self._build_constructor_args(
            agent_class,
            node,
            context,
            execution_tracking_service,
            state_adapter_service,
            prompt_manager_service,
            tools=node_tools,
        )

        # Step 4: Create agent instance
        try:
            agent_instance = agent_class(**constructor_args)
        except Exception as e:
            raise AgentInitializationError(
                f"Failed to create agent instance for node '{node.name}': {str(e)}"
            )

        # Step 5: Special handling for OrchestratorAgent - inject node registry
        if agent_class.__name__ == "OrchestratorAgent" and node_registry:
            self.logger.debug(
                f"[AgentFactoryService] Injecting node registry for OrchestratorAgent: {node.name}"
            )
            agent_instance.node_registry = node_registry
            self.logger.debug(
                f"[AgentFactoryService] ✅ Node registry injected with {len(node_registry)} nodes"
            )

        self.logger.debug(
            f"[AgentFactoryService] ✅ Successfully created agent instance: {node.name}"
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
