"""
AgentClassResolver for AgentMap.

Handles agent class resolution, importing, and caching.
Extracted from AgentFactoryService for better separation of concerns.
"""

import importlib
from typing import Any, Dict, Optional, Set, Type

from agentmap.services.custom_agent_loader import CustomAgentLoader
from agentmap.services.logging_service import LoggingService


class AgentClassResolver:
    """
    Resolves and imports agent classes from various sources.

    Handles class path resolution, caching, and fallback logic
    for both built-in and custom agents.
    """

    def __init__(
        self,
        logging_service: LoggingService,
        custom_agent_loader: CustomAgentLoader,
    ):
        """Initialize resolver with dependency injection."""
        self.logger = logging_service.get_class_logger(self)
        self._custom_agent_loader = custom_agent_loader
        self._class_cache: Dict[str, Type] = {}

    def resolve_agent_class(
        self,
        agent_type: str,
        agent_mappings: Dict[str, str],
        custom_agents: Optional[Set[str]] = None,
    ) -> Type:
        """Resolve an agent class using provided mappings."""
        self.logger.debug(
            f"[AgentClassResolver] Resolving agent class: type='{agent_type}'"
        )

        class_path = agent_mappings.get(agent_type)

        if not class_path:
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

    def _import_class_from_path(self, class_path: str) -> Type:
        """Import a class from its fully qualified path."""
        if class_path in self._class_cache:
            self.logger.debug(
                f"[AgentClassResolver] Using cached class for: {class_path}"
            )
            return self._class_cache[class_path]

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
            if "." not in class_path:
                raise ValueError(f"Invalid class path format: {class_path}")

            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            agent_class = getattr(module, class_name)
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

    def resolve_agent_class_with_fallback(self, agent_type: str) -> Type:
        """Resolve agent class with comprehensive fallback logic."""
        agent_type_lower = agent_type.lower() if agent_type else ""

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

    def _try_load_custom_agent(self, agent_type: str) -> Optional[Type]:
        """Try to load a custom agent as fallback."""
        try:
            self.logger.debug(
                f"[AgentClassResolver] Attempting to load custom agent: {agent_type}"
            )
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
        """Get default agent class as fallback."""
        try:
            from agentmap.agents.builtins.default_agent import DefaultAgent

            return DefaultAgent
        except ImportError:
            self.logger.warning(
                "[AgentClassResolver] DefaultAgent not available, creating minimal fallback"
            )

            class BasicAgent:
                def __init__(self, **kwargs):
                    self.name = kwargs.get("name", "default")
                    self.prompt = kwargs.get("prompt", "")
                    self.context = kwargs.get("context", {})
                    self.logger = kwargs.get("logger")

                def run(self, state):
                    return state

            return BasicAgent

    def get_class_cache(self) -> Dict[str, Type]:
        """Get the class cache for inspection."""
        return self._class_cache.copy()

    def clear_class_cache(self) -> None:
        """Clear the class cache."""
        self._class_cache.clear()
