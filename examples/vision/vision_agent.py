"""
Custom VisionAgent for AgentMap CSV graph workflows.

Extends LLMAgent to support image inputs. The agent reads an image
file path from its input fields and calls LLMService.ask_vision()
instead of the normal text-only call_llm().

CSV usage:
  AgentType column → the registered name (e.g. "vision_agent")
  Input_Fields     → "image_path" (and optionally other text fields)
  Prompt           → the vision prompt (may reference {image_path} etc.)
  Context          → {"provider": "anthropic"} or routing config
"""

import logging
import os
from typing import Any, Dict, Optional

from agentmap.agents.builtins.llm.llm_agent import LLMAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class VisionAgent(LLMAgent):
    """LLMAgent subclass that sends an image to the LLM for analysis."""

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
        execution_tracking_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
    ):
        context = dict(context or {})
        # Default to anthropic if no provider set
        context.setdefault("provider", "anthropic")
        # The context key that holds the image path (default: "image_path")
        self._image_field = context.get("image_field", "image_path")

        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracking_service=execution_tracking_service,
            state_adapter_service=state_adapter_service,
        )

    def process(self, inputs: Dict[str, Any]) -> Any:
        """Process inputs with vision — send the image + prompt to the LLM."""
        llm_service = self.llm_service

        image_path = inputs.get(self._image_field, "")
        if not image_path:
            raise ValueError(
                f"VisionAgent '{self.name}': no image path in "
                f"input field '{self._image_field}'"
            )

        # Resolve relative paths from the CSV's perspective
        if not os.path.isabs(image_path):
            image_path = os.path.abspath(image_path)

        # Build the text prompt — substitute any {field} references
        prompt_text = self.resolved_prompt or self.prompt
        for field, value in inputs.items():
            if isinstance(value, str):
                prompt_text = prompt_text.replace(f"{{{field}}}", value)

        self.log_info(f"VisionAgent processing image: {image_path}")

        # Prepare routing context if routing is enabled
        routing_context = self._prepare_routing_context(inputs)

        result = llm_service.ask_vision(
            prompt=prompt_text,
            image=image_path,
            provider=self.provider_name if not routing_context else None,
            model=self.model,
            temperature=self.temperature,
            routing_context=routing_context,
        )

        self.log_info("Vision processing completed")
        return result
