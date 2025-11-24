"""
AgentValidator for AgentMap.

Handles validation of agent instances.
Extracted from AgentFactoryService for better separation of concerns.
"""

from typing import Any

from agentmap.services.logging_service import LoggingService


class AgentValidator:
    """Validates agent instances for proper configuration."""

    def __init__(self, logging_service: LoggingService):
        """Initialize validator with dependency injection."""
        self.logger = logging_service.get_class_logger(self)

    def validate_agent_instance(self, agent_instance: Any, node: Any) -> None:
        """Validate that an agent instance is properly configured."""
        self.logger.debug(
            f"[AgentValidator] Validating agent configuration for: {node.name}"
        )

        if not hasattr(agent_instance, "name") or not agent_instance.name:
            raise ValueError(f"Agent {node.name} missing required 'name' attribute")
        if not hasattr(agent_instance, "run"):
            raise ValueError(f"Agent {node.name} missing required 'run' method")

        from agentmap.services.protocols import (
            LLMCapableAgent,
            PromptCapableAgent,
            StorageCapableAgent,
        )

        if isinstance(agent_instance, LLMCapableAgent):
            try:
                _ = agent_instance.llm_service
                self.logger.debug(f"[AgentValidator] LLM service OK for {node.name}")
            except (ValueError, AttributeError):
                raise ValueError(
                    f"LLM agent {node.name} missing required LLM service configuration"
                )

        if isinstance(agent_instance, StorageCapableAgent):
            try:
                _ = agent_instance.storage_service
                self.logger.debug(
                    f"[AgentValidator] Storage service OK for {node.name}"
                )
            except (ValueError, AttributeError):
                raise ValueError(
                    f"Storage agent {node.name} missing required storage service configuration"
                )

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

        self.logger.debug(f"[AgentValidator] Validation successful for: {node.name}")
