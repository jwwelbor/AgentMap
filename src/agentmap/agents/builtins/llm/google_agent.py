"""
Google Gemini LLM agent implementation.

This module provides an agent for interacting with Google's Gemini language models.
"""

import os
from typing import Any, Dict, List, Optional, Union

from agentmap.agents.builtins.llm.llm_agent import LLMAgent

"""
Google Gemini LLM agent implementation.

This module provides an agent for interacting with Google's Gemini language models.
"""

from typing import Any, Optional, Dict

from agentmap.agents.builtins.llm.llm_agent import LLMAgent


class GoogleAgent(LLMAgent):
    """
    Google Gemini agent implementation.
    
    Uses Google's Gemini API to generate text completions, with provider-specific
    functionality while inheriting common LLM behaviors from the base class.
    """
    
    def _get_provider_name(self) -> str:
        """Get the provider name for configuration loading."""
        return "google"
        
    def _get_api_key_env_var(self) -> str:
        """Get the environment variable name for the API key."""
        return "GOOGLE_API_KEY"
        
    def _get_default_model_name(self) -> str:
        """Get default model name for this provider."""
        return "gemini-1.0-pro"
    
    def _call_api(self, formatted_prompt: str) -> str:
        """
        Call the Google API and return the result text.
        
        Args:
            formatted_prompt: Formatted prompt text
            
        Returns:
            Response text from Gemini
            
        Raises:
            ValueError: If API key is missing
            ImportError: If Google package is not installed
            RuntimeError: If API call fails
        """
        if not self.api_key:
            raise ValueError("Google API key not found in config or environment")
        
        try:
            import google.generativeai as genai
            
            # Configure the API
            genai.configure(api_key=self.api_key)
            
            # Create a model instance
            model = genai.GenerativeModel(
                model_name=self.model,
                generation_config={"temperature": self.temperature}
            )
            
            # Generate content
            try:
                response = model.generate_content(formatted_prompt)
                
                # Extract the response text
                if hasattr(response, 'text'):
                    return response.text.strip()
                elif hasattr(response, 'parts') and len(response.parts) > 0:
                    return response.parts[0].text.strip()
                else:
                    # Handle alternative response formats
                    return str(response).strip()
            except AttributeError:
                # Older API version might use different methods
                response = model.generate_text(formatted_prompt)
                return response.strip()
                    
        except ImportError:
            raise ImportError("Google GenerativeAI package not installed. Install with 'pip install google-generativeai'")
        except Exception as e:
            raise RuntimeError(f"Google Generative AI error: {str(e)}")
    
    def _create_langchain_client(self) -> Optional[Any]:
        """
        Create a LangChain ChatGoogleGenerativeAI client.
        
        Returns:
            LangChain ChatGoogleGenerativeAI client or None if unavailable
        """
        if not self.api_key:
            return None
            
        try:
            # Try langchain-google-genai first
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                return ChatGoogleGenerativeAI(
                    model=self.model,
                    temperature=self.temperature,
                    google_api_key=self.api_key
                )
            except ImportError:
                # Try community package
                try:
                    from langchain_community.chat_models import ChatGoogleGenerativeAI
                    self.log_warning("Using community LangChain import. Consider upgrading to langchain-google-genai.")
                    
                    return ChatGoogleGenerativeAI(
                        model=self.model,
                        temperature=self.temperature,
                        google_api_key=self.api_key
                    )
                except (ImportError, AttributeError):
                    # Legacy fallback
                    self.log_warning("Could not create LangChain Google client. "
                                "Install with 'pip install langchain-google-genai'")
                    return None
        except Exception as e:
            self.log_debug(f"Could not create LangChain Google client: {e}")
            return None