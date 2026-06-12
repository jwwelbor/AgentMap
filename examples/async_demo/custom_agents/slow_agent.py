"""Slow agent that blocks for a fixed duration — used to prove async concurrency."""

import time
from typing import Any, Dict, Optional

from agentmap.agents.base_agent import BaseAgent

DELAY = 0.3  # seconds per node execution


class SlowAgent(BaseAgent):
    """Passes input through unchanged after sleeping DELAY seconds."""

    def __init__(
        self,
        name: str,
        prompt: str = "",
        context: Optional[Dict[str, Any]] = None,
        logger=None,
        execution_tracking_service=None,
        state_adapter_service=None,
        **kwargs,
    ):
        super().__init__(
            name, prompt, context, logger,
            execution_tracking_service=execution_tracking_service,
            state_adapter_service=state_adapter_service,
            **kwargs,
        )

    def process(self, inputs: Dict[str, Any]) -> Any:
        time.sleep(DELAY)
        return next(iter(inputs.values())) if inputs else None
