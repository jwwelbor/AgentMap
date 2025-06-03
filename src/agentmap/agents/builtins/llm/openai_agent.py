"""
OpenAI LLM agent implementation.

Backward compatibility wrapper for the unified LLMAgent.
"""
import logging
from typing import Any, Dict, List, Optional

from agentmap.agents.builtins.llm.llm_agent import LLMAgent
from agentmap.models.execution_tracker import ExecutionTracker


class OpenAIAgent(LLMAgent):
    """
    OpenAI agent - backward compatibility wrapper.
    
    This class maintains backward compatibility with existing CSV configurations
    while leveraging the unified LLMAgent implementation.
    """
    
    def __init__(self, name: str, prompt: str, logger: logging.Logger, execution_tracker: ExecutionTracker, context: Optional[Dict[str, Any]] = None):
        # Ensure openai provider is set for legacy mode
        if context is None:
            context = {}
        
        # Force provider to openai for backward compatibility
        context["provider"] = "openai"
        
        # Initialize unified LLMAgent
        super().__init__(name, prompt, logger, execution_tracker, context)
