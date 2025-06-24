"""
Google Gemini LLM agent implementation.

Backward compatibility wrapper for the unified LLMAgent.
"""

import logging
from typing import Any, Dict, Optional

from agentmap.agents.builtins.llm.llm_agent import LLMAgent
from agentmap.services.execution_tracking_service import ExecutionTrackingService
from agentmap.services.state_adapter_service import StateAdapterService


class GoogleAgent(LLMAgent):
    """
    Google Gemini agent - backward compatibility wrapper.

    This class maintains backward compatibility with existing CSV configurations
    while leveraging the unified LLMAgent implementation.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        # Infrastructure services only
        logger: Optional[logging.Logger] = None,
        execution_tracker_service: Optional[ExecutionTrackingService] = None,
        state_adapter_service: Optional[StateAdapterService] = None,
    ):
        """Initialize the Google agent with new protocol-based pattern."""
        # Ensure google provider is set for legacy mode
        if context is None:
            context = {}

        # Force provider to google for backward compatibility
        context["provider"] = "google"

        # Initialize unified LLMAgent with new constructor pattern
        super().__init__(
            name=name,
            prompt=prompt,
            context=context,
            logger=logger,
            execution_tracker_service=execution_tracker_service,
            state_adapter_service=state_adapter_service,
        )

        # CRITICAL: Force provider to google even if routing is enabled
        # GoogleAgent should always use Google provider regardless of routing settings
        self.provider_name = "google"

        # Also preserve the model from context if routing was enabled
        # (routing mode sets model=None, but GoogleAgent should preserve context model)
        if self.routing_enabled and context.get("model"):
            self.model = context["model"]
