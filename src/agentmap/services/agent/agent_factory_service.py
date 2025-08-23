"""
AgentFactoryService for AgentMap.

Service containing business logic for agent creation and instantiation.
This extracts and wraps the core functionality from the original AgentLoader class.
"""

import inspect
from typing import Any, Dict, List, Optional, Tuple, Type

from agentmap.core.builtin_definition_constants import BuiltinDefinitionConstants
from agentmap.services.agent.agent_registry_service import AgentRegistryService
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
        agent_registry_service: AgentRegistryService,
        features_registry_service: FeaturesRegistryService,
        logging_service: LoggingService,
    ):
        """Initialize service with dependency injection."""
        self.agent_registry = agent_registry_service
        self.features = features_registry_service
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[AgentFactoryService] Initialized")


    def resolve_agent_class(self, agent_type: str) -> Type:
        """
        Resolve an agent class by type with dependency validation.

        Args:
            agent_type: The type identifier for the agent

        Returns:
            Agent class ready for instantiation

        Raises:
            ValueError: If agent type is not found or dependencies are missing
        """
        agent_type.lower()

        self.logger.debug(
            f"[AgentFactoryService] Resolving agent class: type='{agent_type}'"
        )

        # Validate dependencies before resolving class
        dependencies_valid, missing_deps = self.validate_agent_dependencies(agent_type)
        if not dependencies_valid:
            error_msg = self._get_dependency_error_message(agent_type, missing_deps)
            self.logger.error(f"[AgentFactoryService] {error_msg}")
            raise ValueError(error_msg)

        # Get the agent class from registry
        agent_class = self.agent_registry.get_agent_class(agent_type)
        if not agent_class:
            self.logger.error(
                f"[AgentFactoryService] Agent type '{agent_type}' not found"
            )
            raise ValueError(f"Agent type '{agent_type}' not found.")

        self.logger.debug(
            f"[AgentFactoryService] Successfully resolved agent class '{agent_type}' "
            f"to {agent_class.__name__}"
        )
        return agent_class

    def get_agent_class(self, agent_type: str) -> Optional[Type]:
        """
        Get an agent class by type without dependency validation.

        Use resolve_agent_class() instead for full validation.

        Args:
            agent_type: Type identifier to look up

        Returns:
            The agent class or None if not found
        """
        return self.agent_registry.get_agent_class(agent_type)

    def can_resolve_agent_type(self, agent_type: str) -> bool:
        """
        Check if an agent type can be resolved (has valid dependencies).

        Args:
            agent_type: The agent type to check

        Returns:
            True if agent type can be resolved
        """
        try:
            self.resolve_agent_class(agent_type)
            return True
        except ValueError:
            return False

    def validate_agent_dependencies(self, agent_type: str) -> Tuple[bool, List[str]]:
        """
        Validate that all dependencies for an agent type are available.

        Args:
            agent_type: The agent type to validate

        Returns:
            Tuple of (dependencies_valid, missing_dependencies)
        """
        agent_type_lower = agent_type.lower()
        missing_deps = []

        # Check LLM dependencies for LLM-related agents
        if self._is_llm_agent(agent_type_lower):
            if not self._check_llm_dependencies(agent_type_lower):
                missing_deps.append("llm")

        # Check storage dependencies for storage-related agents
        if self._is_storage_agent(agent_type_lower):
            if not self._check_storage_dependencies(agent_type_lower):
                missing_deps.append("storage")

        dependencies_valid = len(missing_deps) == 0

        if dependencies_valid:
            self.logger.debug(
                f"[AgentFactoryService] All dependencies valid for agent type '{agent_type}'"
            )
        else:
            self.logger.debug(
                f"[AgentFactoryService] Missing dependencies for '{agent_type}': {missing_deps}"
            )

        return dependencies_valid, missing_deps

    def list_available_agent_types(self) -> List[str]:
        """
        Get a list of all available agent types that can be resolved.

        Returns:
            List of agent type names that have valid dependencies
        """
        all_types = self.agent_registry.get_registered_agent_types()
        available_types = []

        for agent_type in all_types:
            if self.can_resolve_agent_type(agent_type):
                available_types.append(agent_type)

        self.logger.debug(
            f"[AgentFactoryService] Available agent types: {available_types}"
        )
        return available_types

    def get_agent_resolution_context(self, agent_type: str) -> Dict[str, Any]:
        """
        Get comprehensive context for agent class resolution.

        Args:
            agent_type: Agent type to get context for

        Returns:
            Dictionary with resolution context and metadata
        """
        try:
            agent_class = self.resolve_agent_class(agent_type)
            dependencies_valid, missing_deps = self.validate_agent_dependencies(
                agent_type
            )

            return {
                "agent_type": agent_type,
                "agent_class": agent_class,
                "class_name": agent_class.__name__,
                "resolvable": True,
                "dependencies_valid": dependencies_valid,
                "missing_dependencies": missing_deps,
                "_factory_version": "2.0",
                "_resolution_method": "AgentFactoryService.resolve_agent_class",
            }
        except ValueError as e:
            dependencies_valid, missing_deps = self.validate_agent_dependencies(
                agent_type
            )
            return {
                "agent_type": agent_type,
                "agent_class": None,
                "class_name": None,
                "resolvable": False,
                "dependencies_valid": dependencies_valid,
                "missing_dependencies": missing_deps,
                "resolution_error": str(e),
                "_factory_version": "2.0",
                "_resolution_method": "AgentFactoryService.resolve_agent_class",
            }

    def create_agent_instance(
        self, 
        node: Any, 
        graph_name: str,
        execution_tracking_service: Optional[Any] = None,
        state_adapter_service: Optional[Any] = None,
        prompt_manager_service: Optional[Any] = None,
        node_registry: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Create agent instance with full instantiation and context.
        
        Extracted from GraphRunnerService to follow factory pattern completely.
        
        Args:
            node: Node definition containing agent information
            graph_name: Name of the graph for context
            execution_tracking_service: Service for execution tracking
            state_adapter_service: Service for state management
            prompt_manager_service: Service for prompt management (optional)
            node_registry: Node registry for OrchestratorAgent (optional)
            
        Returns:
            Configured agent instance
            
        Raises:
            ValueError: If agent creation fails
        """
        from agentmap.exceptions import AgentInitializationError
        
        self.logger.debug(
            f"[AgentFactoryService] Creating agent instance for node: {node.name} (type: {getattr(node, 'agent_type', 'default')})"
        )
        
        # Step 1: Resolve agent class with comprehensive fallback logic
        agent_class = self._resolve_agent_class_with_fallback(node.agent_type)
        
        # Step 2: Create comprehensive context with input/output field information
        context = {
            "input_fields": getattr(node, 'inputs', []),
            "output_field": getattr(node, 'output', None),
            "description": getattr(node, 'description', "")
        }
        
        # Add CSV context data if available (extracted from GraphRunnerService logic)
        if hasattr(node, "context") and node.context:
            context.update(node.context)
        
        self.logger.debug(
            f"[AgentFactoryService] Instantiating {agent_class.__name__} as node '{node.name}'"
        )
        
        # Step 3: Build constructor arguments based on agent signature inspection
        constructor_args = self._build_constructor_args(
            agent_class, node, context, execution_tracking_service, 
            state_adapter_service, prompt_manager_service
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
            LLMCapableAgent, PromptCapableAgent, StorageCapableAgent
        )
        
        # Validate LLM service configuration
        if isinstance(agent_instance, LLMCapableAgent):
            try:
                _ = agent_instance.llm_service  # Will raise if not configured
                self.logger.debug(f"[AgentFactoryService] LLM service OK for {node.name}")
            except (ValueError, AttributeError):
                raise ValueError(
                    f"LLM agent {node.name} missing required LLM service configuration"
                )
        
        # Validate storage service configuration
        if isinstance(agent_instance, StorageCapableAgent):
            try:
                _ = agent_instance.storage_service  # Will raise if not configured
                self.logger.debug(f"[AgentFactoryService] Storage service OK for {node.name}")
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
                self.logger.debug(f"[AgentFactoryService] Prompt service OK for {node.name}")
            else:
                self.logger.debug(f"[AgentFactoryService] Using fallback prompts for {node.name}")
        
        self.logger.debug(f"[AgentFactoryService] ✅ Validation successful for: {node.name}")
    
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
            # Use existing resolve_agent_class for dependency validation
            agent_class = self.resolve_agent_class(agent_type)
            self.logger.debug(
                f"[AgentFactoryService] Successfully resolved {agent_type} to {agent_class.__name__}"
            )
            return agent_class
        
        except ValueError as e:
            self.logger.debug(
                f"[AgentFactoryService] Failed to resolve agent '{agent_type}': {e}"
            )
            
            # Try to load custom agent as fallback
            try:
                custom_agent_class = self._try_load_custom_agent(agent_type)
                if custom_agent_class:
                    self.logger.debug(
                        f"[AgentFactoryService] Resolved to custom agent: {custom_agent_class.__name__}"
                    )
                    return custom_agent_class
            except Exception as custom_error:
                self.logger.debug(
                    f"[AgentFactoryService] Custom agent fallback failed: {custom_error}"
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
        prompt_manager_service: Optional[Any]
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
            
        Returns:
            Dictionary of constructor arguments
        """
        # Get the agent class constructor signature
        agent_signature = inspect.signature(agent_class.__init__)
        agent_params = list(agent_signature.parameters.keys())
        
        # Build base constructor arguments
        constructor_args = {
            "name": node.name,
            "prompt": getattr(node, 'prompt', ""),
            "context": context,
            "logger": self.logger,
        }
        
        # Add services based on what the agent constructor supports
        if "execution_tracker_service" in agent_params and execution_tracking_service:
            constructor_args["execution_tracker_service"] = execution_tracking_service
            self.logger.debug(
                f"[AgentFactoryService] Adding execution_tracker_service to {node.name}"
            )
        
        if "execution_tracking_service" in agent_params and execution_tracking_service:
            constructor_args["execution_tracking_service"] = execution_tracking_service
            self.logger.debug(
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
            from agentmap.services.config.app_config_service import AppConfigService
            import sys
            
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
                    self.name = kwargs.get('name', 'default')
                    self.prompt = kwargs.get('prompt', '')
                    self.context = kwargs.get('context', {})
                    self.logger = kwargs.get('logger')
                    
                def run(self, state):
                    """Basic run method that passes through state unchanged."""
                    return state
            
            return BasicAgent

    def _is_llm_agent(self, agent_type: str) -> bool:
        """Check if an agent type requires LLM dependencies."""
        # Use centralized constants for categorization
        if BuiltinDefinitionConstants.is_llm_agent(agent_type):
            return True
        
        # Also check additional generic LLM-related types not in builtin definitions
        generic_llm_types = {"chat", "conversation", "text_generation"}
        return agent_type in generic_llm_types

    def _is_storage_agent(self, agent_type: str) -> bool:
        """Check if an agent type requires storage dependencies."""
        # Use centralized constants for categorization
        if BuiltinDefinitionConstants.is_storage_agent(agent_type):
            return True
        
        # Also check additional generic storage-related types not in builtin definitions
        generic_storage_types = {"storage", "database", "persist"}
        return agent_type in generic_storage_types

    def _check_llm_dependencies(self, agent_type: str) -> bool:
        """Check if LLM dependencies are available for the agent type."""
        # Get provider mapping from centralized constants
        llm_agent_to_provider = BuiltinDefinitionConstants.get_llm_agent_to_provider()
        
        # Check if this is a known LLM agent type
        if agent_type in llm_agent_to_provider:
            provider = llm_agent_to_provider[agent_type]
            if provider:
                # Check specific provider
                return self.features.is_provider_available("llm", provider)
            else:
                # Agent works with any provider (like base 'llm' agent)
                available_providers = self.features.get_available_providers("llm")
                return len(available_providers) > 0
        else:
            # For generic LLM agents, check if any LLM provider is available
            available_providers = self.features.get_available_providers("llm")
            return len(available_providers) > 0

    def _check_storage_dependencies(self, agent_type: str) -> bool:
        """Check if storage dependencies are available for the agent type."""
        # Get storage type mapping from centralized constants
        agent_to_storage = BuiltinDefinitionConstants.get_agent_to_storage_type()
        
        # Check if this is a known storage agent type
        if agent_type in agent_to_storage:
            storage_type = agent_to_storage[agent_type]
            return self.features.is_provider_available("storage", storage_type)
        
        # For unknown types, check by name patterns
        if "csv" in agent_type:
            return self.features.is_provider_available("storage", "csv")
        elif "json" in agent_type:
            return self.features.is_provider_available("storage", "json")
        elif "file" in agent_type:
            return self.features.is_provider_available("storage", "file")
        elif "vector" in agent_type:
            return self.features.is_provider_available("storage", "vector")
        else:
            # For generic storage agents, check if core storage is available
            return self.features.is_provider_available("storage", "csv")

    def _get_dependency_error_message(
        self, agent_type: str, missing_deps: List[str]
    ) -> str:
        """Generate a helpful error message for missing dependencies."""
        agent_type_lower = agent_type.lower()

        # Handle multiple dependencies first
        if len(missing_deps) > 1:
            return (
                f"Agent '{agent_type}' requires additional dependencies: {missing_deps}. "
                "Install with: pip install agentmap[llm,storage]"
            )

        # Handle single LLM dependency
        if "llm" in missing_deps:
            if agent_type_lower in ("openai", "gpt"):
                return (
                    f"LLM agent '{agent_type}' requires OpenAI dependencies. "
                    "Install with: pip install agentmap[openai]"
                )
            elif agent_type_lower in ("anthropic", "claude"):
                return (
                    f"LLM agent '{agent_type}' requires Anthropic dependencies. "
                    "Install with: pip install agentmap[anthropic]"
                )
            elif agent_type_lower in ("google", "gemini"):
                return (
                    f"LLM agent '{agent_type}' requires Google dependencies. "
                    "Install with: pip install agentmap[google]"
                )
            else:
                return (
                    f"LLM agent '{agent_type}' requires additional dependencies. "
                    "Install with: pip install agentmap[llm]"
                )

        # Handle single storage dependency
        if "storage" in missing_deps:
            if "vector" in agent_type_lower:
                return (
                    f"Storage agent '{agent_type}' requires vector dependencies. "
                    "Install with: pip install agentmap[vector]"
                )
            else:
                return (
                    f"Storage agent '{agent_type}' requires additional dependencies. "
                    "Install with: pip install agentmap[storage]"
                )

        # Generic fallback (shouldn't be reached with current logic)
        return (
            f"Agent '{agent_type}' requires additional dependencies: {missing_deps}. "
            "Install with: pip install agentmap[llm,storage]"
        )
    
    def get_agent_class_mappings(self, agent_types: set[str]) -> Dict[str, str]:
        """Get mappings from agent types to their class import paths.
        
        This method returns a dictionary mapping agent type names to their
        fully qualified class paths for dynamic import.
        
        Args:
            agent_types: Set of agent type names to map
            
        Returns:
            Dictionary mapping agent types to class import paths
        """
        mappings = {}
        
        for agent_type in agent_types:
            try:
                # Get the agent class
                agent_class = self.agent_registry.get_agent_class(agent_type)
                if agent_class:
                    # Get the full module path and class name
                    module_name = agent_class.__module__
                    class_name = agent_class.__name__
                    full_path = f"{module_name}.{class_name}"
                    mappings[agent_type] = full_path
                    
                    self.logger.debug(
                        f"[AgentFactoryService] Mapped {agent_type} -> {full_path}"
                    )
                else:
                    # Use a default mapping for unknown types
                    mappings[agent_type] = "agentmap.agents.builtins.default_agent.DefaultAgent"
                    self.logger.warning(
                        f"[AgentFactoryService] Unknown agent type '{agent_type}', "
                        "using DefaultAgent"
                    )
            except Exception as e:
                self.logger.warning(
                    f"[AgentFactoryService] Failed to map agent type '{agent_type}': {e}"
                )
                # Fallback to default agent
                mappings[agent_type] = "agentmap.agents.builtins.default_agent.DefaultAgent"
        
        return mappings
