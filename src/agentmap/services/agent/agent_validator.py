"""
AgentValidator for AgentMap.

Service for validating agent instances and their configuration.
"""

from typing import Any

from agentmap.services.logging_service import LoggingService


class AgentValidator:
    """
    Service for validating agent instances.

    Validates:
    - Required agent attributes (name, run method)
    - Protocol-based service configuration (LLM, Storage, Prompt)
    - Agent-specific requirements
    """

    def __init__(self, logging_service: LoggingService):
        """Initialize validator with dependencies."""
        self.logger = logging_service.get_class_logger(self)

    def validate_agent_instance(self, agent_instance: Any, node: Any) -> None:
        """
        Validate that an agent instance is properly configured.

        Args:
            agent_instance: Agent instance to validate
            node: Node definition for validation context

        Raises:
            ValueError: If agent configuration is invalid
        """
        self.logger.debug(
            f"[AgentValidator] Validating agent configuration for: {node.name}"
        )

        # Basic validation - required attributes
        if not hasattr(agent_instance, "name") or not agent_instance.name:
            raise ValueError(f"Agent {node.name} missing required 'name' attribute")
        if not hasattr(agent_instance, "run"):
            raise ValueError(f"Agent {node.name} missing required 'run' method")

        # Protocol-based service validation
        from agentmap.services.protocols import (
            LLMCapableAgent,
            PromptCapableAgent,
            StorageCapableAgent,
        )

        # Validate LLM service configuration
        if isinstance(agent_instance, LLMCapableAgent):
            try:
                _ = agent_instance.llm_service  # Will raise if not configured
                self.logger.debug(f"[AgentValidator] LLM service OK for {node.name}")
            except (ValueError, AttributeError):
                raise ValueError(
                    f"LLM agent {node.name} missing required LLM service configuration"
                )

        # Validate storage service configuration
        if isinstance(agent_instance, StorageCapableAgent):
            try:
                _ = agent_instance.storage_service  # Will raise if not configured
                self.logger.debug(
                    f"[AgentValidator] Storage service OK for {node.name}"
                )
            except (ValueError, AttributeError):
                raise ValueError(
                    f"Storage agent {node.name} missing required storage service configuration"
                )

        # Validate prompt service if available
        if isinstance(agent_instance, PromptCapableAgent):
            has_prompt_service = (
                hasattr(agent_instance, "prompt_manager_service")
                and agent_instance.prompt_manager_service is not None
            )
            if has_prompt_service:
                self.logger.debug(f"[AgentValidator] Prompt service OK for {node.name}")
            else:
                self.logger.debug(
                    f"[AgentValidator] Using fallback prompts for {node.name}"
                )

        self.logger.debug(f"[AgentValidator] ✅ Validation successful for: {node.name}")
