"""
OpenAI LLM agent implementation using LangChain.
"""
import os
from typing import Any, Dict, Optional

import openai

from agentmap.agents.builtins.llm.llm_agent import LLMAgent, LANGCHAIN_AVAILABLE
from agentmap.agents.base_agent import StateAdapter
from agentmap.config import get_llm_config
from agentmap.logging import get_logger

logger = get_logger(__name__)


class OpenAIAgent(LLMAgent):
    """OpenAI agent implementation using LangChain."""
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None,
                 model: Optional[str] = None, temperature: Optional[float] = None):
        super().__init__(name, prompt, context)
        
        # Get config with fallbacks
        config = get_llm_config("openai")
        self.model = model or context.get("model") or config.get("model", "gpt-3.5-turbo")
        self.temperature = temperature or context.get("temperature") or config.get("temperature", 0.7)
        self.api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
    
    def _get_llm(self) -> Any:
        """Get LangChain ChatOpenAI instance."""
        if not LANGCHAIN_AVAILABLE:
            return None
            
        if not self.api_key:
            logger.error("OpenAI API key not found in config or environment")
            return None
            
        try:
            from langchain.chat_models import ChatOpenAI
            
            return ChatOpenAI(
                model_name=self.model,
                temperature=float(self.temperature),
                openai_api_key=self.api_key
            )
        except Exception as e:
            logger.error(f"Error creating ChatOpenAI: {e}")
            return None
    
    def _fallback_process(self, inputs: Dict[str, Any]) -> Any:
        """Direct OpenAI API implementation when LangChain is not available."""
        if not self.api_key:
            return {
                "error": "OpenAI API key not found in config or environment",
                "last_action_success": False
            }
        
        try:
            # Format the prompt
            formatted_prompt = self._format_prompt(inputs)
            
            # Set up the API client
            openai.api_key = self.api_key
            
            # Make the API call
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": formatted_prompt}],
                temperature=float(self.temperature)
            )
            
            result = response['choices'][0]['message']['content'].strip()
            
            return result
            
        except Exception as e:
            return {
                "error": str(e),
                "last_action_success": False
            }
    
    def run(self, state: Any) -> Any:
        """Run the agent on the current state."""
        # Extract inputs from state
        inputs = self.state_manager.get_inputs(state)
        
        # Process inputs
        result = self.process(inputs)
        
        # Update state with result
        if isinstance(result, dict):
            # Handle dictionary result (with memory or error)
            if "error" in result:
                # Error case
                state = self.state_manager.set_output(state, result["error"], success=False)
            else:
                # Success with memory case
                memory = result.pop(self.memory_key, None)
                
                # Set output
                if self.output_field and self.output_field in result:
                    state = self.state_manager.set_output(state, result[self.output_field], success=True)
                else:
                    state = self.state_manager.set_output(state, result, success=True)
                
                # Set memory if present
                if memory:
                    state = StateAdapter.set_value(state, self.memory_key, memory)
        else:
            # Simple string result
            state = self.state_manager.set_output(state, result, success=True)
        
        return state