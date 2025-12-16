"""
AgentClassResolver for AgentMap.

Service for resolving agent types to agent classes.
Handles custom agents, built-in agents, and fallback logic.
"""

import importlib
from typing import Any, Dict, Optional, Set, Type

from agentmap.services.custom_agent_loader import CustomAgentLoader
from agentmap.services.logging_service import LoggingService


class AgentClassResolver:
    """
    Service for resolving agent types to agent classes.

    Handles:
    - Agent type to class path mapping resolution
    - Custom agent loading via CustomAgentLoader
    - Fallback to default agent for unresolvable types
    - Class caching for performance
    """

    def __init__(
        self,
        logging_service: LoggingService,
        custom_agent_loader: CustomAgentLoader,
    ):
        """Initialize resolver with dependencies."""
        self.logger = logging_service.get_class_logger(self)
        self._custom_agent_loader = custom_agent_loader
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
            f"[AgentClassResolver] Resolving agent class: type='{agent_type}'"
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

            self.logger.error(f"[AgentClassResolver] {error_msg}")
            raise ValueError(error_msg)

        # Import the class
        try:
            agent_class = self._import_class_from_path(class_path)
            self.logger.trace(
                f"[AgentClassResolver] Successfully resolved '{agent_type}' to {agent_class.__name__}"
            )
            return agent_class
        except (ImportError, AttributeError) as e:
            error_msg = f"Failed to import agent class '{class_path}' for type '{agent_type}': {e}"
            self.logger.error(f"[AgentClassResolver] {error_msg}")
            raise ImportError(error_msg) from e

    def resolve_agent_class_with_fallback(self, agent_type: str) -> Type:
        """
        Resolve agent class with comprehensive fallback logic.

        Tries to load custom agent, falls back to default if not found.

        Args:
            agent_type: Type of agent to resolve

        Returns:
            Agent class ready for instantiation (never returns None)
        """
        agent_type_lower = agent_type.lower() if agent_type else ""

        # Handle empty or None agent_type - default to DefaultAgent
        if not agent_type or agent_type_lower == "none":
            self.logger.debug(
                "[AgentClassResolver] Empty or None agent type, defaulting to DefaultAgent"
            )
            return self._get_default_agent_class()

        try:
            custom_agent_class = self._try_load_custom_agent(agent_type)
            if custom_agent_class:
                self.logger.debug(
                    f"[AgentClassResolver] Resolved to custom agent: {custom_agent_class.__name__}"
                )
                return custom_agent_class
            else:
                raise ValueError(f"Cannot resolve agent type: {agent_type}")
        except (ValueError, Exception) as e:
            self.logger.debug(
                f"[AgentClassResolver] Failed to resolve agent '{agent_type}': {e}"
            )
            self.logger.warning(
                f"[AgentClassResolver] Using default agent for unresolvable type: {agent_type}"
            )
            return self._get_default_agent_class()

    def get_class_cache(self) -> Dict[str, Type]:
        """
        Get the class cache for testing purposes.

        Returns:
            Dictionary mapping class paths to cached classes
        """
        return self._class_cache

    def get_agent_resolution_context(
        self,
        agent_type: str,
        agent_mappings: Dict[str, str],
        custom_agents: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Get comprehensive context for agent class resolution."""
        try:
            agent_class = self.resolve_agent_class(
                agent_type, agent_mappings, custom_agents
            )
            return {
                "agent_type": agent_type,
                "agent_class": agent_class,
                "class_name": agent_class.__name__,
                "resolvable": True,
                "dependencies_valid": True,
                "missing_dependencies": [],
                "_factory_version": "2.0",
                "_resolution_method": "AgentClassResolver.resolve_agent_class",
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
                "_resolution_method": "AgentClassResolver.resolve_agent_class",
            }

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
                f"[AgentClassResolver] Using cached class for: {class_path}"
            )
            return self._class_cache[class_path]

        # Try custom agent loader for non-package paths
        if not class_path.startswith("agentmap."):
            try:
                agent_class = self._custom_agent_loader.load_agent_class(class_path)
                if agent_class:
                    self._class_cache[class_path] = agent_class
                    self.logger.debug(
                        f"[AgentClassResolver] Loaded custom agent: {class_path} -> {agent_class.__name__}"
                    )
                    return agent_class
            except Exception as e:
                self.logger.debug(
                    f"[AgentClassResolver] Custom loader failed for '{class_path}': {e}"
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
                f"[AgentClassResolver] Successfully imported class: {class_path} -> {agent_class.__name__}"
            )

            return agent_class

        except (ImportError, AttributeError) as e:
            self.logger.debug(
                f"[AgentClassResolver] Failed to import class from path '{class_path}': {e}"
            )
            raise

    def _try_load_custom_agent(self, agent_type: str) -> Optional[Type]:
        """
        Try to load a custom agent as fallback.

        Args:
            agent_type: Type of agent to load

        Returns:
            Agent class or None if not found
        """
        try:
            self.logger.debug(
                f"[AgentClassResolver] Attempting to load custom agent: {agent_type}"
            )

            # Try basic custom agent import pattern
            modname = f"{agent_type.lower()}_agent"
            classname = f"{agent_type}Agent"

            try:
                module = __import__(modname, fromlist=[classname])
                agent_class = getattr(module, classname)
                self.logger.debug(
                    f"[AgentClassResolver] Successfully loaded custom agent: {agent_class.__name__}"
                )
                return agent_class
            except (ImportError, AttributeError) as e:
                self.logger.debug(
                    f"[AgentClassResolver] Failed to import custom agent {modname}.{classname}: {e}"
                )
                return None

        except Exception as e:
            self.logger.debug(
                f"[AgentClassResolver] Custom agent loading failed for {agent_type}: {e}"
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
                "[AgentClassResolver] DefaultAgent not available, creating minimal fallback"
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
