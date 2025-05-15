"""
Google Gemini LLM agent implementation.

This module provides an agent for interacting with Google's Gemini language models.
"""

import os
from typing import Any, Dict, List, Optional, Union

from agentmap.agents.builtins.llm.llm_agent import LLMAgent
from agentmap.state.adapter import StateAdapter
from agentmap.config import get_llm_config
from agentmap.logging import get_logger

logger = get_logger(__name__)


class GoogleAgent(LLMAgent):
    """
    Google Gemini agent with LangChain integration.

    Uses Google's Gemini API to generate text completions, with optional
    LangChain integration for memory and prompt management.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None,
                 model: Optional[str] = None, temperature: Optional[float] = None):
        """
        Initialize the Google agent.
        
        Args:
            name: Name of the agent
            prompt: Prompt text or template
            context: Optional context configuration
            model: Optional model override
            temperature: Optional temperature override
        """
        super().__init__(name, prompt, context)
        
        # Get config with fallbacks
        config = get_llm_config("google")
        self.model = model or context.get("model") or config.get("model", "gemini-1.0-pro")
        self.temperature = temperature or context.get("temperature") or config.get("temperature", 0.7)
        self.api_key = config.get("api_key") or os.getenv("GOOGLE_API_KEY")
    
    def _get_llm(self) -> Any:
        """Get LangChain ChatGoogleGenerativeAI instance."""

        if not self.api_key:
            logger.error("Google API key not found in config or environment")
            return None
            
        try:
            from langchain.chat_models import ChatGoogleGenerativeAI
            
            return ChatGoogleGenerativeAI(
                model=self.model,
                temperature=float(self.temperature),
                google_api_key=self.api_key
            )
        except ImportError:
            try:
                # Fallback to earlier version of LangChain
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                return ChatGoogleGenerativeAI(
                    model=self.model,
                    temperature=float(self.temperature),
                    google_api_key=self.api_key
                )
            except Exception as e:
                logger.error(f"Error creating ChatGoogleGenerativeAI: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating ChatGoogleGenerativeAI: {e}")
            return None
    
    def _fallback_process(self, inputs: Dict[str, Any]) -> Any:
        """Direct Google API implementation when LangChain is not available."""
        if not self.api_key:
            return {
                "error": "Google API key not found in config or environment",
                "last_action_success": False
            }
        
        try:
            # Format the prompt
            formatted_prompt = self._format_prompt(inputs)
            
            # Import Google GenerativeAI
            try:
                import google.generativeai as genai
                
                # Configure the API
                genai.configure(api_key=self.api_key)
                
                # Create a model instance
                model = genai.GenerativeModel(
                    model_name=self.model,
                    generation_config={"temperature": float(self.temperature)}
                )
                
                # Generate content
                response = model.generate_content(formatted_prompt)
                
                # Extract the response text
                if hasattr(response, 'text'):
                    result = response.text.strip()
                else:
                    # Handle alternative response formats
                    result = str(response).strip()
                
                return result
                
            except ImportError:
                return {
                    "error": "Google GenerativeAI package not installed. Install with 'pip install google-generativeai'",
                    "last_action_success": False
                }
            
        except Exception as e:
            return {
                "error": str(e),
                "last_action_success": False
            }
    
    def run(self, state: Any) -> Any:
        """Run the agent on the current state."""
        # Extract inputs from state
        inputs = self.state_manager.get_inputs(state)
        
        try:
            # Process inputs
            result = self.process(inputs)
            
            # Update state with output and last_action_success
            if isinstance(result, dict) and "error" in result:
                # Handle error case
                state = self.state_manager.set_output(state, result.get("error", "Unknown error"), success=False)
            else:
                # Handle success case - may be dict with memory or just output string
                if isinstance(result, dict):
                    # Extract memory if present
                    memory = result.pop(self.memory_key, None)
                    
                    # Set the output first
                    if self.output_field and self.output_field in result:
                        output = result[self.output_field]
                        state = self.state_manager.set_output(state, output, success=True)
                    else:
                        # Use the whole result dict as output
                        state = self.state_manager.set_output(state, result, success=True)
                    
                    # Then set memory if present
                    if memory:
                        state = StateAdapter.set_value(state, self.memory_key, memory)
                else:
                    # Just a string output
                    state = self.state_manager.set_output(state, result, success=True)
            
            return state
            
        except Exception as e:
            # Handle any unexpected errors
            error_msg = f"Error in {self.name}: {str(e)}"
            logger.error(error_msg)
            
            # Set error in state
            error_state = StateAdapter.set_value(state, "error", error_msg)
            return self.state_manager.set_output(error_state, None, success=False)