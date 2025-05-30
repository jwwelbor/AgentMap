"""
Google Gemini LLM agent implementation.

Backward compatibility wrapper for the unified LLMAgent.
"""
from typing import Any, Dict, List, Optional

from agentmap.agents.builtins.llm.llm_agent import LLMAgent


class GoogleAgent(LLMAgent):
    """
    Google Gemini agent - backward compatibility wrapper.
    
    This class maintains backward compatibility with existing CSV configurations
    while leveraging the unified LLMAgent implementation.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        # Ensure google provider is set for legacy mode
        if context is None:
            context = {}
        
        # Force provider to google for backward compatibility
        context["provider"] = "google"
        
        # Initialize unified LLMAgent
        super().__init__(name, prompt, context)
