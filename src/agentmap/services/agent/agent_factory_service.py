"""
AgentFactoryService for AgentMap.

Service containing business logic for agent creation and instantiation.
This extracts and wraps the core functionality from the original AgentLoader class.
"""

import importlib
import inspect
from typing import Any, Dict, List, Optional, Set, Tuple, Type

from agentmap.services.custom_agent_loader import CustomAgentLoader
from agentmap.services.declaration_registry_service import DeclarationRegistryService
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
        self._custom_agent_loader = custom_agent_loader
        # Cache for imported agent classes for performance
        self._class_cache: Dict[str, Type] = {}

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
        self.logger.debug(
            f"[AgentFactoryService] Resolving agent class: type='{agent_type}'"
        )

        # Get class path from provided mappings
        class_path = agent_mappings.get(agent_type)

        if not class_path:
            # Provide helpful error message
            is_custom = custom_agents and agent_type in custom_agents
            if is_custom:
                error_msg = (
                    f"Custom agent '{agent_type}' declared but no class path mapping provided. "
                    f"Ensure custom agent is properly registered in agent_mappings."
                )
            else:
                error_msg = f"Agent type '{agent_type}' not found in agent_mappings."

            self.logger.error(f"[AgentFactoryService] {error_msg}")
            raise ValueError(error_msg)

        # Import the class
        try:
            agent_class = self._import_class_from_path(class_path)
            self.logger.trace(
                f"[AgentFactoryService] Successfully resolved '{agent_type}' to {agent_class.__name__}"
            )
            return agent_class
        except (ImportError, AttributeError) as e:
            error_msg = f"Failed to import agent class '{class_path}' for type '{agent_type}': {e}"
            self.logger.error(f"[AgentFactoryService] {error_msg}")
            raise ImportError(error_msg) from e

    def _import_class_from_path(self, class_path: str) -> Type:
        """
        Import a class from its fully qualified path.

        Args:
            class_path: Fully qualified class path (e.g., "module.submodule.ClassName")

        Returns:
            The imported class

        Raises:
            ImportError: If the class cannot be imported
            AttributeError: If the class doesn't exist in the module
        """
        # Check cache first
        if class_path in self._class_cache:
            self.logger.debug(
                f"[AgentFactoryService] Using cached class for: {class_path}"
            )
            return self._class_cache[class_path]

        # Try custom agent loader for non-package paths
        if not class_path.startswith("agentmap."):
            try:
                agent_class = self._custom_agent_loader.load_agent_class(class_path)
                if agent_class:
                    self._class_cache[class_path] = agent_class
                    self.logger.debug(
                        f"[AgentFactoryService] Loaded custom agent: {class_path} -> {agent_class.__name__}"
                    )
                    return agent_class
            except Exception as e:
                self.logger.debug(
                    f"[AgentFactoryService] Custom loader failed for '{class_path}': {e}"
                )

        try:
            # Split module path and class name
            if "." not in class_path:
                raise ValueError(f"Invalid class path format: {class_path}")

            module_path, class_name = class_path.rsplit(".", 1)

            # Import the module
            module = importlib.import_module(module_path)

            # Get the class from the module
            agent_class = getattr(module, class_name)

            # Cache the class for performance
            self._class_cache[class_path] = agent_class

            self.logger.debug(
                f"[AgentFactoryService] Successfully imported class: {class_path} -> {agent_class.__name__}"
            )

            return agent_class

        except (ImportError, AttributeError) as e:
            self.logger.debug(
                f"[AgentFactoryService] Failed to import class from path '{class_path}': {e}"
            )
            raise

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

        Extracted from GraphRunnerService validation logic.

        Args:
            agent_instance: Agent instance to validate
            node: Node definition for validation context

        Raises:
            ValueError: If agent configuration is invalid
        """
        self.logger.debug(
            f"[AgentFactoryService] Validating agent configuration for: {node.name}"
        )

        # Basic validation - required attributes
        if not hasattr(agent_instance, "name") or not agent_instance.name:
            raise ValueError(f"Agent {node.name} missing required 'name' attribute")
        if not hasattr(agent_instance, "run"):
            raise ValueError(f"Agent {node.name} missing required 'run' method")

        # Protocol-based service validation (extracted from GraphRunnerService)
        from agentmap.services.protocols import (
            LLMCapableAgent,
            PromptCapableAgent,
            StorageCapableAgent,
        )

        # Validate LLM service configuration
        if isinstance(agent_instance, LLMCapableAgent):
            try:
                _ = agent_instance.llm_service  # Will raise if not configured
                self.logger.debug(
                    f"[AgentFactoryService] LLM service OK for {node.name}"
                )
            except (ValueError, AttributeError):
                raise ValueError(
                    f"LLM agent {node.name} missing required LLM service configuration"
                )

        # Validate storage service configuration
        if isinstance(agent_instance, StorageCapableAgent):
            try:
                _ = agent_instance.storage_service  # Will raise if not configured
                self.logger.debug(
                    f"[AgentFactoryService] Storage service OK for {node.name}"
                )
            except (ValueError, AttributeError):
                raise ValueError(
                    f"Storage agent {node.name} missing required storage service configuration"
                )

        # Validate prompt service if available (extracted from GraphRunnerService)
        if isinstance(agent_instance, PromptCapableAgent):
            has_prompt_service = (
                hasattr(agent_instance, "prompt_manager_service")
                and agent_instance.prompt_manager_service is not None
            )
            if has_prompt_service:
                self.logger.debug(
                    f"[AgentFactoryService] Prompt service OK for {node.name}"
                )
            else:
                self.logger.debug(
                    f"[AgentFactoryService] Using fallback prompts for {node.name}"
                )

        self.logger.debug(
            f"[AgentFactoryService] ✅ Validation successful for: {node.name}"
        )

    def _resolve_agent_class_with_fallback(self, agent_type: str) -> Type:
        """
        Resolve agent class with comprehensive fallback logic.

        Extracted from GraphRunnerService for complete factory pattern.

        Args:
            agent_type: Type of agent to resolve

        Returns:
            Agent class ready for instantiation

        Raises:
            AgentInitializationError: If no suitable agent class can be found
        """
        from agentmap.exceptions import AgentInitializationError

        agent_type_lower = agent_type.lower() if agent_type else ""

        # Handle empty or None agent_type - default to DefaultAgent
        if not agent_type or agent_type_lower == "none":
            self.logger.debug(
                "[AgentFactoryService] Empty or None agent type, defaulting to DefaultAgent"
            )
            return self._get_default_agent_class()

        try:
            # Note: This method is part of fallback logic and may need proper agent_mappings
            # For now, we'll try the custom agent loader approach first
            custom_agent_class = self._try_load_custom_agent(agent_type)
            if custom_agent_class:
                self.logger.debug(
                    f"[AgentFactoryService] Resolved to custom agent: {custom_agent_class.__name__}"
                )
                return custom_agent_class
            else:
                raise ValueError(f"Cannot resolve agent type: {agent_type}")

        except ValueError as e:
            self.logger.debug(
                f"[AgentFactoryService] Failed to resolve agent '{agent_type}': {e}"
            )

        except Exception as e:
            self.logger.debug(
                f"[AgentFactoryService] Failed to resolve agent '{agent_type}': {e}"
            )
            # Final fallback - use default agent
            self.logger.warning(
                f"[AgentFactoryService] Using default agent for unresolvable type: {agent_type}"
            )
            return self._get_default_agent_class()

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

        Extracted from GraphRunnerService for factory pattern.

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
        # Get the agent class constructor signature
        agent_signature = inspect.signature(agent_class.__init__)
        agent_params = list(agent_signature.parameters.keys())

        # Build base constructor arguments
        constructor_args = {
            "name": node.name,
            "prompt": getattr(node, "prompt", ""),
            "context": context,
            "logger": self.logger,
        }

        # Add services based on what the agent constructor supports
        # this should _always_ be there
        if "execution_tracker_service" in agent_params and execution_tracking_service:
            constructor_args["execution_tracker_service"] = execution_tracking_service
            self.logger.trace(
                f"[AgentFactoryService] Adding execution_tracker_service to {node.name}"
            )

        # this should _always_ be there
        if "execution_tracking_service" in agent_params and execution_tracking_service:
            constructor_args["execution_tracking_service"] = execution_tracking_service
            self.logger.trace(
                f"[AgentFactoryService] Adding execution_tracking_service to {node.name}"
            )

        if "state_adapter_service" in agent_params and state_adapter_service:
            constructor_args["state_adapter_service"] = state_adapter_service
            self.logger.debug(
                f"[AgentFactoryService] Adding state_adapter_service to {node.name}"
            )

        if "prompt_manager_service" in agent_params and prompt_manager_service:
            constructor_args["prompt_manager_service"] = prompt_manager_service
            self.logger.debug(
                f"[AgentFactoryService] Adding prompt_manager_service to {node.name}"
            )

        # AGM-TOOLS-001: Add tools for ToolAgent
        if "tools" in agent_params:
            constructor_args["tools"] = tools if tools is not None else []
            tool_count = len(tools) if tools else 0
            self.logger.debug(
                f"[AgentFactoryService] Adding {tool_count} tools to {node.name}"
            )

        return constructor_args

    def _try_load_custom_agent(self, agent_type: str) -> Optional[Type]:
        """
        Try to load a custom agent as fallback.

        Extracted from GraphRunnerService custom agent loading logic.

        Args:
            agent_type: Type of agent to load

        Returns:
            Agent class or None if not found
        """
        try:
            # Import here to avoid circular imports
            import sys

            from agentmap.services.config.app_config_service import AppConfigService

            # For now, this is a simplified version - would need proper config service injection
            # This preserves the pattern from GraphRunnerService but as a start
            self.logger.debug(
                f"[AgentFactoryService] Attempting to load custom agent: {agent_type}"
            )

            # Try basic custom agent import pattern
            modname = f"{agent_type.lower()}_agent"
            classname = f"{agent_type}Agent"

            try:
                module = __import__(modname, fromlist=[classname])
                agent_class = getattr(module, classname)
                self.logger.debug(
                    f"[AgentFactoryService] Successfully loaded custom agent: {agent_class.__name__}"
                )
                return agent_class
            except (ImportError, AttributeError) as e:
                self.logger.debug(
                    f"[AgentFactoryService] Failed to import custom agent {modname}.{classname}: {e}"
                )
                return None

        except Exception as e:
            self.logger.debug(
                f"[AgentFactoryService] Custom agent loading failed for {agent_type}: {e}"
            )
            return None

    def _get_default_agent_class(self) -> Type:
        """
        Get default agent class as fallback.

        Returns:
            Default agent class
        """
        try:
            # Use the real DefaultAgent class
            from agentmap.agents.builtins.default_agent import DefaultAgent

            return DefaultAgent
        except ImportError:
            self.logger.warning(
                "[AgentFactoryService] DefaultAgent not available, creating minimal fallback"
            )

            # Fallback class that implements the basic agent interface
            class BasicAgent:
                def __init__(self, **kwargs):
                    self.name = kwargs.get("name", "default")
                    self.prompt = kwargs.get("prompt", "")
                    self.context = kwargs.get("context", {})
                    self.logger = kwargs.get("logger")

                def run(self, state):
                    """Basic run method that passes through state unchanged."""
                    return state

            return BasicAgent
