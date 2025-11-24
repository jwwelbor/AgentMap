"""
AgentConstructorBuilder for AgentMap.

Handles building constructor arguments for agent instantiation.
Extracted from AgentFactoryService for better separation of concerns.
"""

import inspect
from typing import Any, Dict, Optional, Type

from agentmap.services.logging_service import LoggingService


class AgentConstructorBuilder:
    """Builds constructor arguments for agent instantiation."""

    def __init__(self, logging_service: LoggingService):
        """Initialize builder with dependency injection."""
        self.logger = logging_service.get_class_logger(self)

    def build_constructor_args(
        self,
        agent_class: Type,
        node: Any,
        context: Dict[str, Any],
        execution_tracking_service: Optional[Any],
        state_adapter_service: Optional[Any],
        prompt_manager_service: Optional[Any],
        tools: Optional[Any] = None,
        logger: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Build constructor arguments based on agent signature inspection."""
        agent_signature = inspect.signature(agent_class.__init__)
        agent_params = list(agent_signature.parameters.keys())

        effective_logger = logger if logger is not None else self.logger

        constructor_args = {
            "name": node.name,
            "prompt": getattr(node, "prompt", ""),
            "context": context,
            "logger": effective_logger,
        }

        if "execution_tracker_service" in agent_params and execution_tracking_service:
            constructor_args["execution_tracker_service"] = execution_tracking_service
            self.logger.trace(
                f"[AgentConstructorBuilder] Adding execution_tracker_service to {node.name}"
            )

        if "execution_tracking_service" in agent_params and execution_tracking_service:
            constructor_args["execution_tracking_service"] = execution_tracking_service
            self.logger.trace(
                f"[AgentConstructorBuilder] Adding execution_tracking_service to {node.name}"
            )

        if "state_adapter_service" in agent_params and state_adapter_service:
            constructor_args["state_adapter_service"] = state_adapter_service
            self.logger.debug(
                f"[AgentConstructorBuilder] Adding state_adapter_service to {node.name}"
            )

        if "prompt_manager_service" in agent_params and prompt_manager_service:
            constructor_args["prompt_manager_service"] = prompt_manager_service
            self.logger.debug(
                f"[AgentConstructorBuilder] Adding prompt_manager_service to {node.name}"
            )

        if "tools" in agent_params:
            constructor_args["tools"] = tools if tools is not None else []
            tool_count = len(tools) if tools else 0
            self.logger.debug(
                f"[AgentConstructorBuilder] Adding {tool_count} tools to {node.name}"
            )

        return constructor_args
